"""
Logger Module

This module provides a centralized logging functionality for our application.
It implements a singleton Logger class that can be used throughout the application for
consistent log formatting and output.

The Logger uses Python's built-in logging module and supports both console and file logging,
with rotating file handler to manage log file sizes.

Usage:
    from utils.logger import Logger
    
    class YourClass:
        def __init__(self):
            self.logger = Logger()
            self.logger.info("This is an information message")

Configuration:
    Logging settings (level and file path) are read from the application's config file.
"""

import logging
from logging.handlers import RotatingFileHandler
import os
from PyQt6.QtCore import QObject


class Logger:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._logger = logging.getLogger("YouTubeMaster")

    def setup_logger(self, config):
        if self._logger.handlers:
            return  # Logger is already set up
        log_level = config.get("logging", {}).get("level", "INFO")
        log_file = config.get("logging", {}).get("file", "app.log")
        app_mode = config.get("app_mode", "production")

        # Ensure the log directory exists
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # Clear the log file if in debug mode
        if app_mode == "debug":
            with open(log_file, "w") as f:
                f.write("")  # Clear the file

        # Set the logging level
        self._logger.setLevel(getattr(logging, log_level))

        # Create handlers
        console_handler = logging.StreamHandler()
        file_handler = RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5
        )

        # Create formatters and add it to handlers
        """
        asctime: The time the log was created.
        name: The logger name.
        levelname: The severity level of the log (INFO, ERROR, etc.).
        message: The actual log message.
        """
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        formatter = logging.Formatter(log_format)
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)

        # Add handlers to the logger
        self._logger.addHandler(console_handler)
        self._logger.addHandler(file_handler)

    def debug(self, message):
        self._logger.debug(message)

    def info(self, message):
        self._logger.info(message)

    def warning(self, message):
        self._logger.warning(message)

    def error(self, message):
        self._logger.error(message)

    def critical(self, message):
        self._logger.critical(message)
