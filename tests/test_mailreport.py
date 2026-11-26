"""Offline tests for ``MRSendmail.send()`` against a fake SMTP server.

They pin down the rendered message and the ``SendResult`` bookkeeping without
any network access, so the package can be checked against different
dependency versions.
"""

import re
import smtplib
from email import message_from_bytes, message_from_string, policy
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pytest

import reputils.MailReport as mr
from reputils import EmailAddress, MRSendmail, SMTPServerInfo


class FakeSMTP:
    """Stand-in for ``smtplib.SMTP`` that records calls instead of connecting."""

    instances: List["FakeSMTP"] = []
    refused: Dict[str, Tuple[int, bytes]] = {}
    raise_on_send: Optional[Exception] = None

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.calls: List[str] = []
        self.sent: List[Tuple[Any, str, List[str]]] = []
        self.login_args: Optional[Tuple[str, str]] = None
        FakeSMTP.instances.append(self)

    def __enter__(self) -> "FakeSMTP":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def set_debuglevel(self, level: int) -> None:
        self.calls.append(f"debug:{level}")

    def ehlo(self) -> None:
        self.calls.append("ehlo")

    def starttls(self, context: Any = None) -> None:
        self.calls.append("starttls")

    def login(self, user: str, password: str) -> None:
        self.login_args = (user, password)

    def send_message(self, message: Any, from_addr: str, to_addrs: List[str]) -> Dict[str, Tuple[int, bytes]]:
        if FakeSMTP.raise_on_send is not None:
            raise FakeSMTP.raise_on_send
        self.sent.append((message, from_addr, to_addrs))
        return dict(FakeSMTP.refused)

    def quit(self) -> None:
        self.calls.append("quit")


@pytest.fixture(autouse=True)
def fake_smtp(monkeypatch: pytest.MonkeyPatch) -> type[FakeSMTP]:
    FakeSMTP.instances = []
    FakeSMTP.refused = {}
    FakeSMTP.raise_on_send = None
    monkeypatch.setattr("reputils.MailReport.smtplib.SMTP", FakeSMTP)
    return FakeSMTP


def _mailer(**kwargs: Any) -> MRSendmail:
    m = MRSendmail(
        serverinfo=SMTPServerInfo(smtp_server="smtp.example.com", smtp_port=587, **kwargs),
        returnpath=EmailAddress(email="bounce@example.com", name="Mailer"),
        senderfrom=EmailAddress(email="noreply@example.org", name="No Reply"),
        subject="Status für Prüfstände",
    )
    m.add_to(EmailAddress(email="alice@example.com", name="Jörg Hübner"))
    m.add_cc(EmailAddress(email="bob@example.com"))
    m.add_bcc(EmailAddress(email="carol@example.com"))
    return m


def _hdr(value: str) -> str:
    return str(make_header(decode_header(value)))


def test_send_text_renders_headers_and_envelope() -> None:
    raw, res = _mailer().send(txt="Grüße aus München", additional_headers={"X-Trace-ID": "12345"})

    assert res.all_succeeded() and not res.all_failed()
    assert res.num_recipients == 3 and res.get_all_errors() == []

    msg = message_from_string(raw)
    assert _hdr(msg["Subject"]) == "Status für Prüfstände"
    assert _hdr(msg["To"]) == "Jörg Hübner <alice@example.com>"
    assert msg["Cc"] == "bob@example.com"
    assert msg["Bcc"] is None
    assert msg["Return-Path"] == "Mailer <bounce@example.com>"
    assert _hdr(msg["X-Trace-ID"]) == "12345"
    # Message-ID domain is taken from the last of From/Reply-To/Return-Path that is set.
    assert re.fullmatch(r"<[^<>@]+@example\.com>", msg["Message-ID"])
    body = msg.get_payload(decode=True)
    assert isinstance(body, bytes) and body.decode("utf-8").strip() == "Grüße aus München"

    date = parsedate_to_datetime(msg["Date"])
    assert date.utcoffset() == date.astimezone(mr._tzberlin).utcoffset()

    (smtp,) = FakeSMTP.instances
    assert (smtp.host, smtp.port) == ("smtp.example.com", 587)
    _, envelope_from, rcpts = smtp.sent[0]
    assert envelope_from == "Mailer <bounce@example.com>"
    assert [r.rsplit("<", 1)[-1].rstrip(">") for r in rcpts] == [
        "alice@example.com",
        "bob@example.com",
        "carol@example.com",
    ]
    assert smtp.calls == ["ehlo", "quit"]
    assert smtp.login_args is None


def test_send_txt_html_and_attachment_is_multipart(tmp_path: Path) -> None:
    att = tmp_path / "report.txt"
    att.write_bytes(b"payload")

    raw, res = _mailer(use_start_tls=True, smtp_user="u", smtp_pass="p").send(
        txt="plain", html="<p>html</p>", files=[att], msgid="<fixed@example.net>"
    )

    assert res.all_succeeded()
    msg = message_from_string(raw)
    assert msg["Message-ID"] == "<fixed@example.net>"
    assert msg.get_content_type() == "multipart/mixed"
    types = [p.get_content_type() for p in msg.walk()]
    assert types == ["multipart/mixed", "multipart/alternative", "text/plain", "text/html", "application/octet-stream"]
    attachment = list(msg.walk())[-1]
    assert attachment.get_filename() == "report.txt"
    assert attachment.get_payload(decode=True) == b"payload"

    (smtp,) = FakeSMTP.instances
    assert smtp.calls == ["ehlo", "starttls", "ehlo", "quit"]
    assert smtp.login_args == ("u", "p")


def test_generated_message_id_uses_address_domain_in_multipart() -> None:
    # Multipart (compat32) messages render the Message-ID verbatim, so a domain taken from the
    # formatted "Name <user@domain>" string used to leak the closing ">" into it.
    m = _mailer()
    m.replyto = EmailAddress(email="reply@example.net", name="Reply Desk")
    raw, _ = m.send(txt="plain", html="<p>html</p>")

    msg = message_from_string(raw)
    assert msg.get_content_type() == "multipart/mixed"
    assert re.fullmatch(r"<[^<>@]+@example\.com>", msg["Message-ID"])


@pytest.mark.parametrize(
    "filename",
    ["my report.txt", "Prüfbericht März.pdf", 'a;b"c.txt', "x\\y.txt"],
)
def test_attachment_filename_survives_round_trip(tmp_path: Path, filename: str) -> None:
    att = tmp_path / filename
    att.write_bytes(b"payload")

    raw, _ = _mailer().send(txt="plain", files=[att])

    for msg in (message_from_string(raw), message_from_bytes(raw.encode(), policy=policy.default)):
        attachment = list(msg.walk())[-1]
        assert attachment.get_content_disposition() == "attachment"
        assert attachment.get_filename() == filename


def test_send_requires_body() -> None:
    with pytest.raises(Exception, match="txt and html"):
        _mailer().send()


def test_partially_refused_recipients_are_reported() -> None:
    FakeSMTP.refused = {"bob@example.com": (550, b"no such user")}

    _, res = _mailer().send(txt="x")

    assert not res.all_succeeded() and not res.all_failed()
    assert res.num_failed == 1
    assert res.get_all_errors() == [("bob@example.com", 550, "no such user")]
    assert res.get_error_for_recipient(EmailAddress(email="bob@example.com")) == (550, "no such user")
    assert res.get_error_for_recipient(EmailAddress(email="alice@example.com")) is None


def test_smtp_errors_are_folded_into_result_not_raised() -> None:
    FakeSMTP.raise_on_send = smtplib.SMTPRecipientsRefused({"alice@example.com": (550, b"rejected")})

    _, res = _mailer().send(txt="x")

    assert res.all_failed() and res.num_failed == 3
    assert res.get_all_errors() == [("alice@example.com", 550, "rejected")]
    assert FakeSMTP.instances[0].calls[-1] == "quit"
