import logging


def init_sysd_friendly_logging(level: int = logging.INFO):
    """
    Initializes logging appropriate for running the daemon as a SystemD service. Specifically:

    - The time is omitted (SystemD already attaches the timestamp)
    - The level is translated to a syslog-style priority which is prepended to the message - SystemD can recognize this
      and use it to filter and highlight messages
    """
    handler = logging.StreamHandler()
    handler.setFormatter(SysDFriendlyFormatter())

    logging.root.addHandler(handler)
    logging.root.setLevel(level)


def init_console_friendly_logging(level: int = logging.INFO):
    """
    Initializes logging appropriate for debugging the daemon in the console. Specifically:

    - A timestamp is attached to each message
    - The level is attached to each message as a string (INFO, ERROR etc)
    """
    logging.basicConfig(
        level=level,
        style='{',
        format='[{asctime}] {levelname}: {message}',
        datefmt='%Y-%m-%d %H:%M:%S'  # We omit the milliseconds by default
    )


class SysDFriendlyFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return f"<{level_to_syslog_priority(record.levelno)}>{super().format(record)}"


def level_to_syslog_priority(level: int) -> int:
    return _LEVEL_TO_SYSLOG_PRIO.get(level, 4)


_LEVEL_TO_SYSLOG_PRIO: dict[int, int] = {
    logging.CRITICAL: 2,
    logging.ERROR: 3,
    logging.WARNING: 4,
    logging.INFO: 6,
    logging.DEBUG: 7,
}
