"""
Centralized logging configuration for the application.
Logs to both console and rotating file.
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime

# Create logs directory if it doesn't exist
LOGS_DIR = Path(__file__).parent.parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Log file path with date
LOG_FILE = LOGS_DIR / f"shuttle_tracker_{datetime.now().strftime('%Y%m%d')}.log"


def setup_logger(name: str = "shuttle_tracker") -> logging.Logger:
    """
    Setup and configure application logger.
    
    Args:
        name: Logger name
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.INFO)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (rotating, max 10MB per file, keep 5 backups)
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger


# Create default logger instance
logger = setup_logger()


def log_request(endpoint: str, method: str, user: str = "anonymous"):
    """Log incoming request"""
    logger.info(f"Request: {method} {endpoint} - User: {user}")


def log_success(endpoint: str, message: str, user: str = "anonymous"):
    """Log successful operation"""
    logger.info(f"Success: {endpoint} - {message} - User: {user}")


def log_error(endpoint: str, error: Exception, user: str = "anonymous"):
    """Log error with full traceback"""
    logger.error(f"Error: {endpoint} - User: {user} - {type(error).__name__}: {str(error)}", exc_info=True)


def log_warning(endpoint: str, message: str, user: str = "anonymous"):
    """Log warning"""
    logger.warning(f"Warning: {endpoint} - {message} - User: {user}")


def log_auth_attempt(username: str, success: bool, reason: str = ""):
    """Log authentication attempt"""
    if success:
        logger.info(f"Auth Success: User '{username}' logged in successfully")
    else:
        logger.warning(f"Auth Failed: User '{username}' - Reason: {reason}")


def log_gps_request(vehicle_id: int, success: bool, error: str = ""):
    """Log GPS API requests"""
    if success:
        logger.debug(f"GPS Request: Vehicle {vehicle_id} - Data fetched successfully")
    else:
        logger.error(f"GPS Request: Vehicle {vehicle_id} - Failed: {error}")


def log_osrm_request(origin: tuple, destinations: int, success: bool, error: str = ""):
    """Log OSRM API requests"""
    if success:
        logger.debug(f"OSRM Request: Origin {origin}, Destinations: {destinations} - Success")
    else:
        logger.warning(f"OSRM Request: Origin {origin}, Destinations: {destinations} - Failed: {error}")
