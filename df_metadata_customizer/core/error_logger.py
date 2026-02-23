"""Error logging utilities for the application."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional


class ErrorLogger:
    """Manages error logging to file."""
    
    _logger: Optional[logging.Logger] = None
    _file_handler: Optional[logging.FileHandler] = None
    _enabled: bool = True
    
    @classmethod
    def initialize(cls, log_dir: Path, enabled: bool = True) -> None:
        """
        Initialize the error logger.
        
        Args:
            log_dir: Directory where the log file should be created
            enabled: Whether logging is enabled
        """
        cls._enabled = enabled
        
        if not enabled:
            return
        
        # Create logger
        cls._logger = logging.getLogger("df_metadata_customizer.errors")
        cls._logger.setLevel(logging.ERROR)
        
        # Remove existing handlers
        cls._logger.handlers.clear()
        
        # Create log file path
        log_file = log_dir / "error.log"
        
        # Create file handler
        cls._file_handler = logging.FileHandler(log_file, encoding='utf-8')
        cls._file_handler.setLevel(logging.ERROR)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        cls._file_handler.setFormatter(formatter)
        
        # Add handler to logger
        cls._logger.addHandler(cls._file_handler)
        
        # Log initialization
        cls._logger.info("=" * 50)
        cls._logger.info(f"Error logging initialized at {datetime.now()}")
        cls._logger.info("=" * 50)
    
    @classmethod
    def set_enabled(cls, enabled: bool, log_dir: Optional[Path] = None) -> None:
        """
        Enable or disable error logging.
        
        Args:
            enabled: Whether to enable logging
            log_dir: Directory for log file (required if enabling)
        """
        if enabled == cls._enabled:
            return
        
        cls._enabled = enabled
        
        if enabled and log_dir:
            cls.initialize(log_dir, enabled=True)
        elif not enabled and cls._file_handler:
            # Disable logging
            if cls._logger:
                cls._logger.removeHandler(cls._file_handler)
            cls._file_handler.close()
            cls._file_handler = None
    
    @classmethod
    def log_error(cls, message: str, exception: Optional[Exception] = None) -> None:
        """
        Log an error message.
        
        Args:
            message: Error message to log
            exception: Optional exception object
        """
        if not cls._enabled or not cls._logger:
            return
        
        if exception:
            cls._logger.error(f"{message}: {type(exception).__name__}: {str(exception)}")
        else:
            cls._logger.error(message)
    
    @classmethod
    def log_remux_error(cls, filename: str, error_details: str) -> None:
        """
        Log a remux-specific error.
        
        Args:
            filename: Name of the file that failed
            error_details: Details about the error
        """
        cls.log_error(f"Remux failed for '{filename}': {error_details}")
    
    @classmethod
    def is_enabled(cls) -> bool:
        """Check if error logging is currently enabled."""
        return cls._enabled
