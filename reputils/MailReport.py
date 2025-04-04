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
from typing import List, Optional, Tuple, Union, Dict

# from dateutil.tz import gettz
import pytz
from loguru import logger

logger.disable("reputils")

# os.environ["LOGURU_LEVEL"] = os.getenv("LOGURU_LEVEL", "INFO")  # standard is DEBUG
# logger.remove()  # remove default-handler
# # https://buildmedia.readthedocs.org/media/pdf/loguru/latest/loguru.pdf
# logger.add(sys.stderr, level=os.getenv("LOGURU_LEVEL"))  # TRACE | DEBUG | INFO | WARN | ERROR |  FATAL


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


@dataclass
class EmailAddress:
    email: str
    name: Optional[str] = None

    @staticmethod
    def fromSTR(ema: str) -> EmailAddress:
        tp: Tuple[str | None, str] = parseaddr(ema)
        return EmailAddress(name=tp[0], email=tp[1])

    @staticmethod
    def formataddr(ema: EmailAddress) -> str:
        return formataddr_ext((ema.name, ema.email), _csqp)

    def formataddr_self(self) -> str:
        return EmailAddress.formataddr(self)


def _formatdate(dt: datetime.datetime, tz: datetime.tzinfo = _tzberlin) -> str:  # type: ignore
    return formatdate_ext(dt.astimezone(tz))
    # return dt.astimezone(tz).strftime("%a, %d %b %Y  %H:%M:%S %Z")

    # Returns a date string as specified by RFC 2822, e.g.:
    # Fri, 09 Nov 2001 01:08:47 -0000
    # return formatdate_ext(date, _csqp)
    # return formataddr_ext((addr, addr))


@dataclass
class SMTPServerInfo:
    smtp_server: str
    smtp_port: int = 25
    smtp_user: Optional[str] = None
    smtp_pass: Optional[str] = None
    useStartTLS: bool = False
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
    serverinfo: SMTPServerInfo
    returnpath: EmailAddress  # das ist der im MAIL FROM: header im smtp
    subject: str = ""
    senderfrom: Optional[EmailAddress] = None  # das ist der From-Header im Header der E-Mail
    replyto: Optional[EmailAddress] = None

    tos: list[EmailAddress] = field(default_factory=list)
    ccs: list[EmailAddress] = field(default_factory=list)
    bccs: list[EmailAddress] = field(default_factory=list)

    def addTo(self, receiver: EmailAddress) -> None:
        self.tos.append(receiver)

    def addCC(self, cc: EmailAddress) -> None:
        self.ccs.append(cc)

    def addBCC(self, bcc: EmailAddress) -> None:
        self.bccs.append(bcc)

    def send(
        self,
        txt: Optional[str] = None,
        html: Optional[str] = None,
        files: Optional[List[Path]] = None,
        msgid: Optional[str] = None,
        wantsdebug: bool = False,
        additional_headers: Optional[Dict[str, str]] = None,
    ) -> str:
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

        with smtplib.SMTP(self.serverinfo.smtp_server, self.serverinfo.smtp_port) as server:
            if self.serverinfo.wantsdebug:
                server.set_debuglevel(1)
            if self.serverinfo.useStartTLS:
                # context = ssl._create_unverified_context()
                context = ssl.create_default_context()
                # context.verify_mode = ssl.CERT_NONE
                if self.serverinfo.ignoresslerrors:
                    context.check_hostname = False
                    context.verify_mode = ssl.CERT_NONE

            # Try to log in to server and send email
            try:
                server.ehlo()  # Can be omitted
                if self.serverinfo.useStartTLS:
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

                logger.debug(message.as_string())

                server.send_message(message, sendme, rcpts)
            finally:
                server.quit()

        return message.as_string()
