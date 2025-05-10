import os
from enum import Enum, auto
from typing import Optional, Any
import logging
from dataclasses import dataclass
from colorama import init, Fore, Style
from datetime import datetime

init(autoreset=True)


class LogLevel(Enum):
    DEBUG = auto()
    INFO = auto()
    WARNING = auto()
    ERROR = auto()
    CRITICAL = auto()


@dataclass
class LogStyle:
    color: str
    prefix: str
    style: str = Style.NORMAL


LOG_STYLES = {
    LogLevel.DEBUG: LogStyle(Fore.CYAN, "DEBUG"),
    LogLevel.INFO: LogStyle(Fore.GREEN, "INFO"),
    LogLevel.WARNING: LogStyle(Fore.YELLOW, "WARNING"),
    LogLevel.ERROR: LogStyle(Fore.RED, "ERROR"),
    LogLevel.CRITICAL: LogStyle(Fore.RED + Style.BRIGHT, "CRITICAL"),
}


class Logger:
    def __init__(self, name: Optional[str] = None):
        self.name = name or os.path.basename(__file__).replace(".py", "")
        self.logger = logging.getLogger(self.name)
        self._setup_logging()

    def _setup_logging(self):
        """Initialize basic logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    def log(self,
            message: str,
            level: LogLevel = LogLevel.INFO,
            exc_info: Optional[Any] = None,
            **kwargs):
        """Main logging method"""
        style = LOG_STYLES[level]
        formatted_message = (
            f"{Style.BRIGHT}{style.color}[{self.name}] {style.prefix}: "
            f"{style.style}{message}{Style.RESET_ALL}"
        )

        # Also log to standard logging module
        log_method = {
            LogLevel.DEBUG: self.logger.debug,
            LogLevel.INFO: self.logger.info,
            LogLevel.WARNING: self.logger.warning,
            LogLevel.ERROR: self.logger.error,
            LogLevel.CRITICAL: self.logger.critical,
        }[level]

        log_method(message, exc_info=exc_info, **kwargs)
        print(formatted_message)

    # Convenience methods
    def debug(self, message: str, **kwargs):
        self.log(message, LogLevel.DEBUG, **kwargs)

    def info(self, message: str, **kwargs):
        self.log(message, LogLevel.INFO, **kwargs)

    def warning(self, message: str, **kwargs):
        self.log(message, LogLevel.WARNING, **kwargs)

    def error(self, message: str, exc_info: Optional[Any] = None, **kwargs):
        self.log(message, LogLevel.ERROR, exc_info=exc_info, **kwargs)

    def critical(self, message: str, exc_info: Optional[Any] = None, **kwargs):
        self.log(message, LogLevel.CRITICAL, exc_info=exc_info, **kwargs)


# Usage example
if __name__ == "__main__":
    logger = Logger()
    logger.info("Notification sent.")
    logger.error("Something went wrong!", exc_info=Exception("Test error"))
