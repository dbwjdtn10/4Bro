"""4Bro 로깅 시스템"""
import logging
import os
from pathlib import Path


def setup_logger(name: str = "4bro", level: int = logging.INFO) -> logging.Logger:
    """앱 로거 설정. 파일 + 콘솔 출력."""
    logger = logging.getLogger(name)
    if logger.handlers:  # already configured
        return logger

    logger.setLevel(level)

    # Log directory
    log_dir = Path.home() / "Documents" / "4Bro" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # File handler (rotating-like: max 5MB, keep last log)
    log_file = log_dir / "4bro.log"
    # Truncate if over 5MB
    if log_file.exists() and log_file.stat().st_size > 5 * 1024 * 1024:
        log_file.write_text("")

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)

    # Format
    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(fmt)
    console_handler.setFormatter(fmt)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


# Convenience: app-wide logger
log = setup_logger()
