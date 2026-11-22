import logging
import re

SENSITIVE_QUERY = re.compile(
    r"(?i)([?&](?:token|reset_token|verification_token|share_token)=)[^&\s\"']+"
)
SHARE_PATH = re.compile(r"(/c/p/)[A-Za-z0-9_-]+")
PUBLIC_DOC_PATH = re.compile(
    r"(/public/documents/)[A-Za-z0-9_-]+"
)
COOKIE_PAIR = re.compile(
    r"(?i)((?:c_session|c_csrf|session|sessionid)=)[^;\s\"']+"
)
PASSWORD_PAIR = re.compile(
    r"(?i)((?:password|current_password|new_password)=)[^&\s\"']+"
)


def redact_sensitive(text: str) -> str:
    text = SENSITIVE_QUERY.sub(r"\1[REDACTED]", text)
    text = SHARE_PATH.sub(r"\1[REDACTED]", text)
    text = PUBLIC_DOC_PATH.sub(r"\1[REDACTED]", text)
    text = COOKIE_PAIR.sub(r"\1[REDACTED]", text)
    text = PASSWORD_PAIR.sub(r"\1[REDACTED]", text)
    return text


def _redact_value(value):
    return redact_sensitive(value) if isinstance(value, str) else value


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_sensitive(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(_redact_value(value) for value in record.args)
        elif isinstance(record.args, dict):
            record.args = {
                key: _redact_value(value)
                for key, value in record.args.items()
            }
        elif isinstance(record.args, str):
            record.args = redact_sensitive(record.args)
        if record.exc_text:
            record.exc_text = redact_sensitive(record.exc_text)
        return True


def install_logging_redaction() -> None:
    for name in (
        "uvicorn.access",
        "uvicorn.error",
        "c_notes",
        "c_notes.auth",
    ):
        logger = logging.getLogger(name)
        if not any(
            isinstance(existing, RedactionFilter)
            for existing in logger.filters
        ):
            logger.addFilter(RedactionFilter())
