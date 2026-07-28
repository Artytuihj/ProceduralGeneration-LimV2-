import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

COLORS = {
    logging.DEBUG: "\033[90m",     # gray
    logging.INFO: "\033[36m",      # cyan
    logging.WARNING: "\033[33m",   # yellow
    logging.ERROR: "\033[31m",     # red
    logging.CRITICAL: "\033[41m",  # red bg
}
RESET = "\033[0m"


class TagFormatter(logging.Formatter):
    """Turns logger name 'GenTest.Generation.SnakePass' into '[GenTest][Generation][SnakePass]'"""
    def __init__(self, color: bool = False):
        super().__init__()
        self.color = color

    def format(self, record: logging.LogRecord) -> str:
        tags = "".join(f"[{part}]" for part in record.name.split("."))
        msg = f"{tags} {record.getMessage()}"
        if self.color:
            c = COLORS.get(record.levelno, "")
            msg = f"{c}{msg}{RESET}"
        if record.exc_info:
            msg += "\n" + self.formatException(record.exc_info)
        return msg


def setup_logging(log_file: Path = Path("gentest.log"), level: int = logging.DEBUG):
    root = logging.getLogger("GenTest")
    root.setLevel(level)
    root.handlers.clear()

    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(TagFormatter(color=True))
    root.addHandler(console)

    file_handler = RotatingFileHandler(log_file, maxBytes=2_000_000, backupCount=3)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(TagFormatter(color=False))
    root.addHandler(file_handler)

    return root


def get_logger(*tags: str) -> logging.Logger:
    """get_logger('Generation', 'SnakePass') -> logs as [GenTest][Generation][SnakePass]"""
    return logging.getLogger(".".join(("GenTest", *tags)))