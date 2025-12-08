"""
Tezaver Mac - Logging Utilities (M20_LOGGING_CORE)

Provides centralized logging configuration for the entire application.
Outputs logs to both console and a file in the 'logs' directory.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

# Global flag to ensure we only configure the root logger once
_LOGGER_INITIALIZED = False

def _ensure_log_dir() -> Path:
    """
    Ensures the 'logs' directory exists at the project root.
    Returns the path to the logs directory.
    """
    # Assuming this file is at src/tezaver/core/logging_utils.py
    # parents[0] = core
    # parents[1] = tezaver
    # parents[2] = src
    # parents[3] = project_root
    project_root = Path(__file__).resolve().parents[3]
    log_dir = project_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir

def init_logging(level: int = logging.INFO) -> None:
    """
    Configures the root logger with StreamHandler and FileHandler.
    This should be called once at the start of the application or script.
    """
    global _LOGGER_INITIALIZED
    if _LOGGER_INITIALIZED:
        return

    log_dir = _ensure_log_dir()
    log_file = log_dir / "tezaver_mac.log"

    # Define format
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Force Turkey Time (UTC+3) for logs
    from datetime import datetime, timezone, timedelta
    from tezaver.core.config import TIMEZONE_OFFSET_HOURS
    
    def turkey_time_converter(*args):
        offset = timedelta(hours=TIMEZONE_OFFSET_HOURS)
        tz = timezone(offset)
        return datetime.now(tz).timetuple()
        
    formatter.converter = turkey_time_converter

    # Configure root logger
    root = logging.getLogger()
    root.setLevel(level)
    
    # Clear existing handlers to avoid duplicates if re-initialized
    if root.handlers:
        root.handlers.clear()

    # 1. Stream Handler (Console)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(formatter)
    root.addHandler(ch)

    # 2. File Handler
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(formatter)
    root.addHandler(fh)

    _LOGGER_INITIALIZED = True
    
    # Log startup
    logging.getLogger("tezaver.core.logging_utils").info(f"Logging initialized. Log file: {log_file}")

def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Returns a configured logger instance.
    Ensures logging is initialized before returning.
    """
    if not _LOGGER_INITIALIZED:
        init_logging()
    
    return logging.getLogger(name if name else "tezaver")
