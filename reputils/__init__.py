"""Small utilities for composing and sending e-mail reports, logging via loguru.

Re-exports the public mail API (:class:`EmailAddress`, :class:`SMTPServerInfo`,
:class:`SendResult`, :class:`MRSendmail`) from :mod:`reputils.MailReport` and
provides :func:`configure_loguru_default_with_skiplog_filter`.

Importing this package calls ``loguru.logger.disable("reputils")``, so the
library is silent by default; callers opt in with
``logger.enable("reputils")``.
"""

__version__ = "0.0.17"

import os
import sys
from typing import TYPE_CHECKING, Callable, Mapping

from loguru import logger as glogger

if TYPE_CHECKING:
    # ``loguru.Record`` only exists in loguru's type stubs, not at runtime
    from loguru import Record

glogger.disable(__name__)


def _loguru_skiplog_filter(record: "Record") -> bool:
    """Filter function to hide records with ``extra['skiplog']`` set.

    Intended for use with ``loguru``'s ``filter=`` parameter so that callers can
    temporarily suppress verbose logs for specific operations by binding
    ``skiplog=True`` on the logger.

    Args:
        record: Loguru record dictionary.

    Returns:
        ``True`` to keep the record, ``False`` if ``record["extra"]["skiplog"]``
        is truthy.
    """
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
    extra: Mapping[str, object] = record.get("extra", {})
    return not extra.get("skiplog", False)


def configure_loguru_default_with_skiplog_filter(
    loguru_filter: Callable[["Record"], bool] = _loguru_skiplog_filter,
) -> None:
    """Configure a default ``loguru`` sink with a convenient format and filter.

    This sets a colored formatter, applies the given filter (by default
    :func:`_loguru_skiplog_filter`), and ensures a reasonable default log level
    via the ``LOGURU_LEVEL`` environment variable.

    Side effects on global state:

    - Sets ``os.environ["LOGURU_LEVEL"]`` to its current value, or to
      ``"DEBUG"`` if unset.
    - Removes **all** existing handlers of the global ``loguru`` logger,
      including ones added by the application.
    - Adds a single ``sys.stderr`` sink at that level whose format references
      ``{extra[classname]}``.
    - Replaces the logger's global ``extra`` defaults with
      ``{"classname": "None", "skiplog": False}``.

    It does not re-enable the ``reputils`` logger that is disabled on import;
    call ``logger.enable("reputils")`` for that.

    Args:
        loguru_filter: A callable taking a loguru record and returning
            ``True`` if the record should be emitted. Defaults to
            :func:`_loguru_skiplog_filter`.
    """
    glogger.info("configure_loguru_default_with_skiplog_filter")

    os.environ["LOGURU_LEVEL"] = os.getenv("LOGURU_LEVEL", "DEBUG")  # standard is DEBUG
    glogger.remove()  # remove default-handler
    logger_fmt: str = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{module}</cyan>::<cyan>{extra[classname]}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    # logger_fmt: str = "<g>{time:HH:mm:ssZZ}</> | <lvl>{level}</> | <c>{module}::{extra[classname]}:{function}:{line}</> - {message}"

    # TRACE | DEBUG | INFO | WARN | ERROR |  FATAL
    glogger.add(sys.stderr, level=os.environ["LOGURU_LEVEL"], format=logger_fmt, filter=loguru_filter)
    glogger.configure(extra={"classname": "None", "skiplog": False})


from .MailReport import EmailAddress as EmailAddress
from .MailReport import MRSendmail as MRSendmail
from .MailReport import SendResult as SendResult
from .MailReport import SMTPServerInfo as SMTPServerInfo
