"""
Logging configuration for auto-screencap.
"""
import logging
import logging.handlers
import os
from typing import Optional, Dict, Any

# Custom log level for more granular logging below DEBUG
TRACE_LEVEL_NUM = 5

def setup_logging(config: Dict[str, Any]) -> None:
    """Configure logging based on the provided configuration.
    
    Args:
        config: Application configuration dictionary
    """
    # Add TRACE level if it doesn't exist
    if not hasattr(logging, 'TRACE'):
        logging.addLevelName(TRACE_LEVEL_NUM, 'TRACE')
        def trace(self, message, *args, **kws):
            if self.isEnabledFor(TRACE_LEVEL_NUM):
                self._log(TRACE_LEVEL_NUM, message, args, **kws)
        logging.Logger.trace = trace
        logging.TRACE = TRACE_LEVEL_NUM
    
    # Get log level from config or default to INFO
    log_level_str = config.get('log_level', 'INFO').upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    
    # Get log file path from config or use default
    log_dir = os.path.expanduser(config.get('log_dir', 'logs'))
    log_file = os.path.join(log_dir, 'auto_screencap.log')
    
    # Create log directory if it doesn't exist
    os.makedirs(log_dir, exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler (stderr)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler with rotation (10MB per file, keep 5 backups)
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Set log level for noisy libraries
    logging.getLogger('PIL').setLevel(logging.WARNING)
    logging.getLogger('matplotlib').setLevel(logging.WARNING)
    logging.getLogger('PIL.PngImagePlugin').setLevel(logging.WARNING)
    
    logger = logging.getLogger("auto-screencap")
    logger.info("Logging initialized at level %s", log_level_str)
    logger.debug("Debug logging enabled")
    logger.trace("Trace logging enabled")  # type: ignore

def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)

class LogCapture:
    """Context manager for capturing log output during tests."""
    
    def __init__(self, logger_name: str = None, level: int = logging.DEBUG):
        """Initialize the log capture.
        
        Args:
            logger_name: Name of the logger to capture (None for root)
            level: Log level to capture
        """
        self.logger = logging.getLogger(logger_name)
        self.level = level
        self.original_level = self.logger.level
        self.handler = None
        self.records = []
    
    def __enter__(self):
        """Enter the context and start capturing logs."""
        self.original_level = self.logger.level
        self.logger.setLevel(self.level)
        
        # Create a handler that captures the records
        self.handler = _LogCaptureHandler(self.records)
        self.handler.setLevel(self.level)
        
        # Add the handler to the logger
        self.logger.addHandler(self.handler)
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context and restore the original logging configuration."""
        if self.handler:
            self.logger.removeHandler(self.handler)
        self.logger.setLevel(self.original_level)
    
    @property
    def output(self) -> str:
        """Get the captured log output as a string."""
        return "\n".join(record.getMessage() for record in self.records)

class _LogCaptureHandler(logging.Handler):
    """Handler that captures log records for testing."""
    
    def __init__(self, records):
        """Initialize with a list to store records."""
        super().__init__()
        self.records = records
    
    def emit(self, record):
        """Store the log record."""
        self.records.append(record)
