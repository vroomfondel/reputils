from __future__ import annotations

import datetime
import os

# Import the email modules we'll need
import smtplib
import ssl
import sys
from dataclasses import dataclass, field
from email import charset, encoders, utils
from email.message import EmailMessage, MIMEPart
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import format_datetime as formatdate_ext
from email.utils import formataddr as formataddr_ext
from email.utils import parseaddr
from pathlib import Path
from typing import List, Optional, Tuple, Union, Dict, ClassVar, Callable, Any

# from dateutil.tz import gettz
import pytz

from loguru import logger as glogger

glogger.disable(__name__)  # reputils.MailReport

# logger_fmt: str = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{module}</cyan>::<cyan>{extra[classname]}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
# # logger_fmt: str = "<g>{time:HH:mm:ssZZ}</> | <lvl>{level}</> | <c>{module}::{extra[classname]}:{function}:{line}</> - {message}"
#
# def _loguru_skiplog_filter(record: dict) -> bool:
#     return not record.get("extra", {}).get("skiplog", False)
#
# logger.add(sys.stderr, level=os.getenv("LOGURU_LEVEL"), format=logger_fmt, filter=_loguru_skiplog_filter)  # type: ignore # TRACE | DEBUG | INFO | WARN | ERROR |  FATAL
# logger.configure(extra={"classname": "None", "skiplog": False})


# from email.encoders import encode_base64
# import mimetypes

# https://docs.python.org/3.9/library/email.examples.html
# https://realpython.com/python-send-email/
# Date-Header: https://petermolnar.net/article/not-mime-email-python-3/

# rom email.mime.text import MIMEText
# from email import charset
#
# cs = charset.Charset('utf-8')
# cs.body_encoding = charset.QP
# message = MIMEText(your_body_here, 'plain', cs)

_csqp = charset.Charset("utf-8")
_csqp.header_encoding = charset.QP
_csqp.body_encoding = charset.QP
_tzberlin: datetime.tzinfo = pytz.timezone("Europe/Berlin")


def _loguru_skiplog_filter(record: dict) -> bool:
    # {
    #     "elapsed": timedelta,      # Zeit seit Programmstart
    #     "exception": tuple,         # Exception-Info (type, value, traceback) oder None
    #     "extra": dict,             # Benutzerdefinierte Extra-Felder
    #     "file": RecordFile,        # Datei-Info (name, path)
    #     "function": str,           # Name der Funktion
    #     "level": RecordLevel,      # Level-Info (name, no, icon)
    #     "line": int,               # Zeilennummer
    #     "message": str,            # Formatierte Nachricht
    #     "module": str,             # Modulname
    #     "name": str,               # Logger-Name
    #     "process": RecordProcess,  # Process-Info (id, name)
    #     "thread": RecordThread,    # Thread-Info (id, name)
    #     "time": datetime           # Zeitstempel des Log-Eintrags
    # }
    return not record.get("extra", {}).get("skiplog", False)


def configure_loguru_default_with_skiplog_filter(loguru_filter: Callable[[Dict[str, Any]], bool]=_loguru_skiplog_filter) -> None:
    glogger.info("configure_loguru_default_with_skiplog_filter")

    os.environ["LOGURU_LEVEL"] = os.getenv("LOGURU_LEVEL", "DEBUG")  # standard is DEBUG
    glogger.remove()  # remove default-handler
    logger_fmt: str = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{module}</cyan>::<cyan>{extra[classname]}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    # logger_fmt: str = "<g>{time:HH:mm:ssZZ}</> | <lvl>{level}</> | <c>{module}::{extra[classname]}:{function}:{line}</> - {message}"

    glogger.add(sys.stderr, level=os.getenv("LOGURU_LEVEL"), format=logger_fmt, filter=loguru_filter)  # type: ignore # TRACE | DEBUG | INFO | WARN | ERROR |  FATAL
    glogger.configure(extra={"classname": "None", "skiplog": False})


# using slots=True lets my ide choke
# @dataclass(slots=True)
@dataclass
class SendResult:
    """Result of an email send operation.

    Represents the outcome of attempting to deliver a message to one or more
    recipients. It records how many recipients were targeted, how many failed,
    and preserves the underlying SMTP exceptions so that detailed per-recipient
    error information can be inspected.

    Attributes:
        num_recipients (int):
            Total number of recipients that were attempted during the send.
        num_failed (int):
            Number of recipients for which delivery failed.
        fail_exceptions (list[SMTPRecipientsRefused | SMTPSenderRefused |
            SMTPResponseException] | None):
            Collected exceptions raised by the SMTP layer while sending. May be
            ``None`` when no failures occurred or when the sending code opted
            not to keep exception details.

    Notes:
        - Use ``get_all_errors()`` to flatten per-recipient SMTP errors into a
          simple list of ``(email, code, message)`` tuples.
        - Use ``get_error_for_recipient()`` to look up an individual
          recipient's SMTP error.
        - ``all_succeeded()`` is a convenience to check for zero failures.
    """
    num_recipients: int
    num_failed: int
    fail_exceptions: Optional[List[smtplib.SMTPRecipientsRefused|smtplib.SMTPSenderRefused|smtplib.SMTPResponseException]] = field(default=None)

    def get_all_errors(self) -> List[Tuple[str, int, str]]:
        """Collect all per-recipient SMTP errors from the send attempt.

        Iterates over ``fail_exceptions`` and aggregates any recipient-specific
        errors exposed via the ``recipients`` mapping on exceptions such as
        ``smtplib.SMTPRecipientsRefused``. Each entry in the returned list is a
        tuple consisting of the recipient email address, the SMTP status code,
        and the decoded textual error message.

        Returns:
            list[tuple[str, int, str]]: A list of ``(email, code, message)``
            tuples. Returns an empty list when there are no recorded failures
            or when none of the exceptions include per-recipient details.

        Notes:
            - Only exceptions that provide a ``recipients`` attribute are
              considered; other exception types are ignored here.
            - Error messages are decoded from bytes using UTF-8 (messages may
              also be ASCII-compatible).
        """
        ret: List[Tuple[str, int, str]] = []

        if self.fail_exceptions is None:
            glogger.debug("self.fail_exceptions is None")
            return ret

        for ex in self.fail_exceptions:
            if hasattr(ex, "recipients"):
                recdict: Dict[str, Tuple[int, bytes]] = ex.recipients
                for email, (errorcode, errormsg) in recdict.items():
                    ret.append((email, errorcode, errormsg.decode("utf-8")))  # may also be ascii

        return ret

    def get_error_for_recipient(self, recipient: EmailAddress) -> Tuple[int, str]|None:
        """Return the SMTP error for a specific recipient, if available.

        Looks through ``fail_exceptions`` for a per-recipient entry matching
        ``recipient.email`` and returns its SMTP code and message. If multiple
        exceptions contain information for the same recipient, the first match
        encountered is returned.

        Args:
            recipient (EmailAddress): The recipient whose error information is
                requested.

        Returns:
            tuple[int, str] | None: ``(code, message)`` when an error entry for
            the recipient exists; otherwise ``None``.

        Notes:
            The error message is decoded from bytes using UTF-8 (messages may
            also be ASCII-compatible).
        """
        if self.fail_exceptions is None:
            return None

        for ex in self.fail_exceptions:
            if hasattr(ex, "recipients"):
                recdict: Dict[str, Tuple[int, bytes]] = ex.recipients
                if recipient.email in recdict:
                    p: Tuple[int, bytes] = recdict[recipient.email]
                    return p[0], p[1].decode("utf-8")  # may also be ascii

        return None

    def all_succeeded(self):
        return self.num_failed == 0

    def all_failed(self):
        return self.num_failed == self.num_recipients


@dataclass
class EmailAddress:
    """Represents an email address with an optional display name.

    This utility encapsulates an RFC 2822 style address consisting of a
    mailbox (``email``) and an optional display ``name``. It also provides
    helpers to parse and format addresses using the same policy as the
    standard library email utilities with proper encoding.

    Attributes:
        email: The mailbox part of the address (e.g., ``user@example.com``).
        name: Optional human-readable display name (e.g., ``"Jane Doe"``).
    """

    email: str
    name: Optional[str] = None

    @staticmethod
    def from_str(ema: str) -> EmailAddress:
        """Create an ``EmailAddress`` from a string.

        The input may be in plain mailbox form (``user@example.com``) or in
        display-name form (``"Jane Doe" <user@example.com>``). Parsing is
        delegated to ``email.utils.parseaddr``.

        Args:
            ema: Address string to parse.

        Returns:
            An ``EmailAddress`` instance with ``name`` and ``email`` set.
        """
        tp: Tuple[str | None, str] = parseaddr(ema)
        return EmailAddress(name=tp[0], email=tp[1])

    @staticmethod
    def formataddr(ema: EmailAddress) -> str:
        """Format an address into an RFC 2822 compliant string.

        Uses the module's configured charset and quoted-printable header
        encoding policy to properly encode non-ASCII display names.

        Args:
            ema: The address to format.

        Returns:
            The formatted address string, e.g., ``"Jane Doe" <user@example.com>``.
        """
        return formataddr_ext((ema.name, ema.email), _csqp)

    def formataddr_self(self) -> str:
        """Format this address as a string.

        Returns:
            The RFC 2822 formatted address string for ``self``.
        """
        return EmailAddress.formataddr(self)


def _formatdate(dt: datetime.datetime, tz: datetime.tzinfo = _tzberlin) -> str:  # type: ignore
    """Format a datetime as an RFC 2822 compliant Date header value.

    The datetime is converted to the provided timezone before formatting.

    Args:
        dt: The datetime to format.
        tz: The timezone to convert ``dt`` into before formatting. Defaults to
            Europe/Berlin.

    Returns:
        A string suitable for use in the ``Date`` header of an email message.
    """
    return formatdate_ext(dt.astimezone(tz))
    # return dt.astimezone(tz).strftime("%a, %d %b %Y  %H:%M:%S %Z")

    # Returns a date string as specified by RFC 2822, e.g.:
    # Fri, 09 Nov 2001 01:08:47 -0000
    # return formatdate_ext(date, _csqp)
    # return formataddr_ext((addr, addr))


@dataclass
class SMTPServerInfo:
    """SMTP server configuration.

    Attributes:
        smtp_server: Hostname or IP address of the SMTP server.
        smtp_port: Port number used to connect to the server.
        smtp_user: Optional username for authentication.
        smtp_pass: Optional password for authentication.
        use_start_tls: Whether to upgrade the connection via STARTTLS.
        wantsdebug: If true, enables SMTP debug output on the connection.
        ignoresslerrors: If true, disables certificate verification when
            using STARTTLS (use with caution).
    """

    smtp_server: str
    smtp_port: int = 25
    smtp_user: Optional[str] = None
    smtp_pass: Optional[str] = None
    use_start_tls: bool = False
    wantsdebug: bool = False
    ignoresslerrors: bool = True

    # @validator('mailfrom', pre=True, always=True)
    # def set_default_mailfrom(cls, v):
    #     return v or EmailAddress.getDefaultFrom

    # https://pydantic-docs.helpmanual.io/usage/validators/
    # @validator('password2')
    #     def passwords_match(cls, v, values, **kwargs):
    #         if 'password1' in values and v != values['password1']:
    #             raise ValueError('passwords do not match')
    #         return v


@dataclass
class MRSendmail:
    """Compose and send RFC 5322/RFC 2047 compliant email via SMTP.

    MRSendmail helps you construct MIME messages (plain text and/or HTML), add
    attachments, and populate common headers (``From``, ``Reply-To``,
    ``Return-Path``, ``To``, ``Cc``). It then connects to a configured SMTP
    server to deliver the message, optionally enabling STARTTLS and
    authentication according to :class:`SMTPServerInfo`.

    Key behavior
    - ``returnpath`` is used as the SMTP envelope sender (``MAIL FROM``) and
      is also written to the ``Return-Path`` header.
    - If ``senderfrom`` is not provided, ``From`` defaults to ``returnpath``.
    - Recipients used for SMTP delivery are the union of ``tos``, ``ccs`` and
      ``bccs``. ``bccs`` are not written to headers.
    - The class emits logs via ``loguru``; you can opt-in to per-call verbose
      logging in :meth:`send`.

    Attributes:
        serverinfo: SMTP connectivity and security parameters.
        returnpath: Address used for SMTP envelope sender (``MAIL FROM``) and
            ``Return-Path`` header.
        subject: Message subject line.
        senderfrom: Optional ``From`` header; falls back to ``returnpath`` if
            omitted.
        replyto: Optional ``Reply-To`` header address.
        tos: Primary recipient addresses (``To``).
        ccs: Carbon-copy recipient addresses (``Cc``).
        bccs: Blind carbon-copy recipient addresses; used for SMTP only, not
            added to headers.

    Example:
        >>> mailer = MRSendmail(
        ...     serverinfo=SMTPServerInfo(hostname="smtp.example.com"),
        ...     returnpath=EmailAddress.from_str("no-reply@example.com"),
        ...     subject="Hello"
        ... )
        >>> mailer.add_to(EmailAddress.from_str("Alice <alice@example.com>"))
        >>> raw, result = mailer.send(txt="Hi there")
        >>> result.all_succeeded()
        True
    """

    logger: ClassVar = glogger.bind(classname=__qualname__)

    serverinfo: SMTPServerInfo
    returnpath: EmailAddress  # das ist der im MAIL FROM: header im smtp
    subject: str = ""
    senderfrom: Optional[EmailAddress] = None  # das ist der From-Header im Header der E-Mail
    replyto: Optional[EmailAddress] = None

    tos: list[EmailAddress] = field(default_factory=list)
    ccs: list[EmailAddress] = field(default_factory=list)
    bccs: list[EmailAddress] = field(default_factory=list)

    def add_to(self, receiver: EmailAddress) -> None:
        """Add a primary recipient.

        Args:
            receiver: Address to append to the ``To`` list.
        """
        self.tos.append(receiver)

    def add_cc(self, cc: EmailAddress) -> None:
        """Add a carbon-copy recipient.

        Args:
            cc: Address to append to the ``Cc`` list.
        """
        self.ccs.append(cc)

    def add_bcc(self, bcc: EmailAddress) -> None:
        """Add a blind carbon-copy recipient.

        Args:
            bcc: Address to append to the ``Bcc`` list (not exposed in headers).
        """
        self.bccs.append(bcc)

    def send(
        self,
        txt: Optional[str] = None,
        html: Optional[str] = None,
        files: Optional[List[Path]] = None,
        msgid: Optional[str] = None,
        wantsdebuglogging: bool = False,
        wants_smtp_level_debug: bool = False,
        additional_headers: Optional[Dict[str, str]] = None,
    ) -> Tuple[str, SendResult]:
        """Build, deliver, and return the serialized email message.

        Compose a MIME message from the provided parts, send it using the
        configured SMTP server, and return the raw RFC 5322 message as a
        string together with a :class:`SendResult` detailing per-recipient
        success or failure.

        Behavior
        - Body: At least one of ``txt`` or ``html`` must be provided. If both
          are provided, a ``multipart/alternative`` part is created. When
          attachments are present, the top-level message becomes multipart and
          attachments are added as base64-encoded ``application/octet-stream``.
        - Headers: ``From``, ``To``, ``Date``, and ``Subject`` are set from the
          instance fields. ``Reply-To`` and ``Return-Path`` are added when
          available. Additional headers may be supplied via
          ``additional_headers``.
        - Message-ID: Uses provided ``msgid`` or generates one using the
          sender domain.
        - SMTP envelope: Sender is ``returnpath``; recipients are the union of
          ``tos``, ``ccs``, and ``bccs``.
        - Debugging: ``wants_smtp_level_debug`` enables low-level ``smtplib``
          debug output for this call; ``wantsdebuglogging`` enables extra
          application-level logging.

        Args:
            txt: Plaintext body content.
            html: HTML body content.
            files: File paths to attach to the message.
            msgid: Explicit ``Message-ID`` to set; a suitable value is
                generated if omitted.
            wantsdebuglogging: Emit additional application-level debug logs for
                this call.
            wants_smtp_level_debug: Enable ``smtplib`` debug output
                (``SMTP.set_debuglevel(1)``) for this connection.
            additional_headers: Extra headers to add to the message.

        Returns:
            A tuple ``(raw_message, result)`` where ``raw_message`` is the full
            RFC 5322 message string and ``result`` is a :class:`SendResult`
            describing per-recipient delivery outcomes.

        Raises:
            Exception: If both ``txt`` and ``html`` are ``None``.
            OSError: If an attachment file cannot be read.
            smtplib.SMTPException: For SMTP errors during connection/login/send.

        Example:
            >>> raw, res = mailer.send(
            ...     txt="Hello",
            ...     files=[Path("/tmp/report.txt")],
            ...     wants_smtp_level_debug=False,
            ... )
            >>> res.all_succeeded()
            True
        """

        logger = self.logger.bind(skiplog=not wantsdebuglogging)  # self.logger is MRSendMail.logger

        if txt is None and html is None:
            raise Exception("either on of txt and html must not be null")
        kk: int = 0
        hastxtandhtml: bool = False
        if txt is not None and html is not None:
            hastxtandhtml = True
        if txt is not None:
            kk += 1
        if html is not None:
            kk += 1
        if files is not None and len(files) > 0:
            kk += 1

        message: EmailMessage | MIMEMultipart = EmailMessage() if kk == 1 else MIMEMultipart()

        ################ Set Headers ###################
        fromme: EmailAddress = self.returnpath if not self.senderfrom else self.senderfrom
        logger.debug(f"{fromme=}")

        fromdomain: str | None = None

        if fromme:
            message.add_header("From", fromme.formataddr_self())
            fromdomain = fromme.formataddr_self().split("@")[1]
        if self.replyto:
            message.add_header("Reply-To", self.replyto.formataddr_self())
            fromdomain = self.replyto.formataddr_self().split("@")[1]
        if self.returnpath:
            message.add_header("Return-Path", self.returnpath.formataddr_self())
            fromdomain = self.returnpath.formataddr_self().split("@")[1]

        logger.debug(f"{fromdomain=}")
        if msgid is not None:
            # msg['message-id'] = utils.make_msgid(domain='mydomain.com')
            message.add_header("Message-ID", msgid)
        else:
            msgid = utils.make_msgid(domain=fromdomain)
            message.add_header("Message-ID", msgid)

        logger.debug(f"set Message-ID to {msgid=}")

        message.add_header("To", ", ".join(k.formataddr_self() for k in self.tos))
        nowdate: datetime.datetime = datetime.datetime.now(tz=_tzberlin)
        logger.debug(f"{nowdate.tzinfo=}")
        logger.debug(f"{nowdate=}")
        nowdate_str: str = _formatdate(nowdate)
        logger.debug(f"{nowdate_str=}")
        message.add_header("Date", nowdate_str)
        message.add_header("Subject", _csqp.header_encode(self.subject))

        if additional_headers:
            for k, v in additional_headers.items():
                # message.add_header(k, _csqp.header_encode_lines(v, 100))
                message.add_header(k, _csqp.header_encode(v))

        if len(self.ccs) > 0:
            message.add_header("Cc", ", ".join(k.formataddr_self() for k in self.ccs))

        # message.set_charset(_csqp)
        # message.set_payload(txt, _csqp)

        if kk == 1:
            if html is not None:
                message.set_content(html, "html")  # type: ignore
                # message.set_default_type("text/html")
            else:
                message.set_content(txt, "plain")  # type: ignore
                # message.set_default_type("text/plain")
        else:
            txtpart: Optional[MIMEText] = None
            htmlpart: Optional[MIMEText] = None

            if txt is not None:
                txtpart = MIMEText(txt, "plain")
                # txtpart.set_charset(_csqp)
                # txtpart.add_header("Content-Transfer-Encoding", "quoted-printable")  #Content-Type: text/plain; charset="utf-8"

            if html is not None:
                htmlpart = MIMEText(html, "html")
                # htmlpart.set_charset(_csqp)

            if hastxtandhtml:
                submsg: MIMEMultipart = MIMEMultipart("alternative")
                submsg.attach(txtpart)  # type: ignore
                submsg.attach(htmlpart)  # type: ignore
                message.attach(submsg)  # type: ignore
            else:
                if txtpart is not None:
                    message.attach(txtpart)  # type: ignore
                if htmlpart is not None:
                    message.attach(htmlpart)  # type: ignore

        ############# Add Attachments #############################
        if files:
            for path in files:
                # mime_type, encoding = mimetypes.guess_type(str(path.absolute()))
                # print(f"{path=} {mime_type=} {encoding=}")
                # with open(path, "rb") as fp:
                #     data = fp.read()
                #     message.add_attachment(data, maintype=mime_type.split("/")[0],
                #         subtype=mime_type.split("/")[1],
                #         filename=path.name)

                part = MIMEBase("application", "octet-stream")
                with open(path, "rb") as file:
                    part.set_payload(file.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", "attachment; filename={}".format(path.name))
                message.attach(part)  # type: ignore

        # sendme ist der technische sender im "MAIL FROM: {}"-header
        sendme: str = EmailAddress.formataddr(
            self.senderfrom if not self.returnpath else self.returnpath  # type: ignore
        )
        rcpts: list[str] = [k.formataddr_self() for k in self.tos + self.ccs + self.bccs]

        logger.debug(f"{sendme=}")

        sr: SendResult = SendResult(
            num_recipients=len(self.tos) + len(self.ccs) + len(self.bccs),
            num_failed=0
        )

        with smtplib.SMTP(self.serverinfo.smtp_server, self.serverinfo.smtp_port) as server:
            if self.serverinfo.wantsdebug or wants_smtp_level_debug:
                server.set_debuglevel(1)
            if self.serverinfo.use_start_tls:
                # context = ssl._create_unverified_context()
                context = ssl.create_default_context()
                # context.verify_mode = ssl.CERT_NONE
                if self.serverinfo.ignoresslerrors:
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE

            # Try to log in to server and send email
            try:
                server.ehlo()  # Can be omitted
                if self.serverinfo.use_start_tls:
                    server.starttls(context=context)  # Secure the connection
                    server.ehlo()  # Can be omitted

                if self.serverinfo.smtp_pass and self.serverinfo.smtp_user:
                    server.login(self.serverinfo.smtp_user, self.serverinfo.smtp_pass)

                # # server.sendmail(sendme, rcpts, message.as_string())
                # print(f"SENDING MAIL FROM ||{sendme}||:")
                # print(message.as_string())
                #
                # ########################## Content  Type #################
                # print("\nContent Type           : {}".format(message.get_content_type()))
                # print("Is Multipart?          : {}".format(message.is_multipart()))
                # print("Content Disposition    : {}".format(message.get_content_disposition()))
                #
                # ################# Message Parts #####################
                # print("\n================ Message Parts ===================")
                # for part in message.walk():  # message.iter_parts() || message.iter_attachments():
                #     print("\nAttachment Type        : {}".format(type(part)))
                #     print("Content Type           : {}".format(part.get_content_type()))
                #     print("Is Multipart?          : {}".format(part.is_multipart()))
                #     # print("Is Attachment?         : {}".format(part.is_attachment()))
                #     print("Content Disposition    : {}".format(part.get_content_disposition()))

                if wantsdebuglogging:
                    logger.debug(message.as_string())

                # it returns a dictionary, with one entry for each recipient that was refused. Each entry contains a tuple of the SMTP error code and the accompanying error message sent by the server.
                # if only one recipient is supplied and that one recipient fails, SMTPRecipientsRefused is thrown (even if it rather should have been "SMTPSenderRefused")
                failed_recipients: Dict[str, tuple[int, bytes]] = server.send_message(message, sendme, rcpts)
                sr.num_failed = len(failed_recipients)

                if sr.num_failed > 0:
                    logger.debug("EXCEPTIONS FOUND")

                    sr.fail_exceptions = [smtplib.SMTPRecipientsRefused(failed_recipients)]

                    if wantsdebuglogging:
                        for failed_recipient, (smtp_error_code, smtp_error_msg_bytes) in failed_recipients.items():
                            logger.debug(f"Failed to send to: {failed_recipient} SMTP-ERROR-CODE: {smtp_error_code} SMTP-ERROR-MESSAGE: {smtp_error_msg_bytes.decode("utf-8")}")  # probably rather ascii
                elif wantsdebuglogging:
                    logger.debug("Sending (in terms of delivery into smtp-server) to all recipients was successfull.")

            except smtplib.SMTPRecipientsRefused as srr:
                logger.opt(exception=srr).error(srr)
                # all failed
                sr.num_failed = sr.num_recipients
                sr.fail_exceptions = [srr]
            except smtplib.SMTPSenderRefused as ssr:
                logger.opt(exception=ssr).error(ssr)
                # all failed
                sr.num_failed = sr.num_recipients
                sr.fail_exceptions = [ssr]
            except smtplib.SMTPResponseException as sother:
                logger.opt(exception=sother).error(sother)
                sr.num_failed = sr.num_recipients
                sr.fail_exceptions = [sother]

            finally:
                server.quit()

        return message.as_string(), sr

