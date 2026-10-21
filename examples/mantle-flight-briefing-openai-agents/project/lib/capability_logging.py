"""Redact briefing capabilities before standard logging formats a record."""
import logging
import os
import re
import sys
import traceback

_CAPABILITY = re.compile(r"brf_[A-Za-z0-9_-]{43}")
_API_KEY = re.compile(r"(?:(?<![A-Za-z0-9])|(?<=\\[ntr]))sk-(?:ant-|proj-)?[A-Za-z0-9_-]{12,}")
_installed = False


def configured_secrets():
    # Short/blank values are not usable keys and must not rewrite common text.
    return tuple(value for name in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY')
                 if len(value := os.environ.get(name, '').strip()) >= 16)


def redact_api(value):
    if isinstance(value, str):
        for secret in configured_secrets():
            value = value.replace(secret, '[API credential redacted]')
            # Framework error reprs can clip either end. Every remaining run
            # of eight secret characters is removed, independently of prefix.
            fragments = {secret[i:i + 8] for i in range(len(secret) - 7)}
            pattern = '|'.join(re.escape(fragment) for fragment in sorted(fragments))
            value = re.sub(pattern, '[API fragment redacted]', value)
            value = re.sub(r'(?:\*{2,}|\.{2,}|…)' + re.escape(secret[-4:]),
                           '[API fragment redacted]', value)
        return _API_KEY.sub('[API credential redacted]', value)
    if isinstance(value, dict):
        return {redact_api(key): redact_api(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_api(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_api(item) for item in value)
    return value


def redact(value):
    value = redact_api(value)
    if isinstance(value, str):
        return _CAPABILITY.sub('[briefing capability redacted]', value)
    if isinstance(value, dict):
        return {redact(key): redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact(item) for item in value)
    return value


def contains_api_key(value):
    if isinstance(value, str):
        return bool(_API_KEY.search(value)) or any(
            any(secret[i:i + 8] in value for i in range(len(secret) - 7))
            for secret in configured_secrets())
    if isinstance(value, dict):
        return any(contains_api_key(k) or contains_api_key(v) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return any(contains_api_key(v) for v in value)
    return False


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
    # A final formatter boundary also covers extra fields and formatted
    # exception text, which are attached after LogRecordFactory runs.
    previous_format = logging.Formatter.format

    def safe_format(formatter, record):
        return redact(previous_format(formatter, record))

    logging.Formatter.format = safe_format

    def safe_exception(kind, value, tb):
        sys.stderr.write(redact(''.join(traceback.format_exception(kind, value, tb))))

    sys.excepthook = safe_exception
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
        structlog.configure(processors=[redact_event, *config["processors"], redact_event])
    _installed = True
