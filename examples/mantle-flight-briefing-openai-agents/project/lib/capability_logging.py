"""Redact briefing capabilities before standard logging formats a record."""
import logging
import re

_CAPABILITY = re.compile(r"brf_[A-Za-z0-9_-]{43}")
_installed = False


def redact(value):
    if isinstance(value, str):
        return _CAPABILITY.sub("[briefing capability redacted]", value)
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    return value


def install():
    global _installed
    if _installed:
        return
    previous = logging.getLogRecordFactory()

    def factory(*args, **kwargs):
        record = previous(*args, **kwargs)
        record.msg = redact(record.getMessage())
        record.args = ()
        return record

    logging.setLogRecordFactory(factory)
    # Mantle also uses structlog's direct console path, which can bypass the
    # standard LogRecord factory. Redact structured values before rendering.
    try:
        import structlog
    except ImportError:
        pass
    else:
        def redact_event(logger, method_name, event_dict):
            return redact(event_dict)
        config = structlog.get_config()
        structlog.configure(processors=[redact_event, *config["processors"]])
    _installed = True
