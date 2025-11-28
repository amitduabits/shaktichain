"""
Structured logging module for V2G Marketplace.

Provides JSON-structured logging with request tracking, user context,
and configurable output destinations (console, file, log aggregation ready).
"""

import json
import logging
import os
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from typing import Any, Optional

import structlog
from structlog.types import EventDict, WrappedLogger


# Context variables for request tracking
request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
user_id_ctx: ContextVar[Optional[str]] = ContextVar("user_id", default=None)
user_email_ctx: ContextVar[Optional[str]] = ContextVar("user_email", default=None)


def get_request_id() -> Optional[str]:
    """Get the current request ID from context."""
    return request_id_ctx.get()


def set_request_id(request_id: str) -> None:
    """Set the request ID in context."""
    request_id_ctx.set(request_id)


def generate_request_id() -> str:
    """Generate a new unique request ID."""
    return str(uuid.uuid4())[:8]


def get_user_context() -> dict:
    """Get the current user context."""
    return {
        "user_id": user_id_ctx.get(),
        "user_email": user_email_ctx.get(),
    }


def set_user_context(user_id: Optional[str], user_email: Optional[str] = None) -> None:
    """Set the user context for logging."""
    user_id_ctx.set(user_id)
    user_email_ctx.set(user_email)


def clear_context() -> None:
    """Clear all context variables."""
    request_id_ctx.set(None)
    user_id_ctx.set(None)
    user_email_ctx.set(None)


def add_request_context(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add request context to log events."""
    request_id = get_request_id()
    if request_id:
        event_dict["request_id"] = request_id

    user_context = get_user_context()
    if user_context["user_id"]:
        event_dict["user_id"] = user_context["user_id"]
    if user_context["user_email"]:
        event_dict["user_email"] = user_context["user_email"]

    return event_dict


def add_timestamp(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add ISO timestamp to log events."""
    event_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
    return event_dict


def add_service_info(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add service information to log events."""
    event_dict["service"] = "v2g-marketplace"
    event_dict["version"] = os.environ.get("APP_VERSION", "0.1.0")
    return event_dict


class JSONFormatter(logging.Formatter):
    """JSON formatter for standard library logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "service": "v2g-marketplace",
        }

        # Add request context if available
        request_id = get_request_id()
        if request_id:
            log_entry["request_id"] = request_id

        user_context = get_user_context()
        if user_context["user_id"]:
            log_entry["user_id"] = user_context["user_id"]

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)

        return json.dumps(log_entry)


class ConsoleFormatter(logging.Formatter):
    """Human-readable formatter for console output in development."""

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format log record for console."""
        color = self.COLORS.get(record.levelname, "")
        reset = self.RESET if color else ""

        # Build base message
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        request_id = get_request_id()
        request_id_str = f"[{request_id}] " if request_id else ""

        msg = f"{timestamp} {color}{record.levelname:8}{reset} {request_id_str}{record.getMessage()}"

        # Add exception if present
        if record.exc_info:
            msg += f"\n{self.formatException(record.exc_info)}"

        return msg


def setup_logging(
    level: str = "INFO",
    json_format: bool = True,
    log_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
) -> structlog.BoundLogger:
    """
    Configure structured logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR).
        json_format: Use JSON format (production) or console format (development).
        log_file: Optional file path for file logging.
        max_bytes: Max size per log file before rotation.
        backup_count: Number of backup files to keep.

    Returns:
        Configured structlog logger.
    """
    # Determine environment
    is_production = os.environ.get("ENVIRONMENT", "development") == "production"
    use_json = json_format if is_production else False

    # Set up standard library logging
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Clear existing handlers
    root_logger.handlers = []

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))

    if use_json or is_production:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(ConsoleFormatter())

    root_logger.addHandler(console_handler)

    # File handler (if specified or in production)
    if log_file or is_production:
        log_path = log_file or "logs/v2g-marketplace.log"
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
        )
        file_handler.setLevel(getattr(logging, level.upper()))
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)

    # Configure structlog
    shared_processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        add_timestamp,
        add_request_context,
        add_service_info,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if use_json or is_production:
        # JSON output for production
        structlog.configure(
            processors=shared_processors + [
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
    else:
        # Console output for development
        structlog.configure(
            processors=shared_processors + [
                structlog.dev.ConsoleRenderer(colors=True),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )

    return get_logger()


def get_logger(name: str = "v2g-marketplace") -> structlog.BoundLogger:
    """
    Get a configured structlog logger.

    Args:
        name: Logger name.

    Returns:
        Bound structlog logger.
    """
    return structlog.get_logger(name)


# Pre-configured loggers for specific components
class LoggerFactory:
    """Factory for component-specific loggers."""

    @staticmethod
    def get_api_logger() -> structlog.BoundLogger:
        """Get logger for API layer."""
        return get_logger("v2g.api")

    @staticmethod
    def get_auth_logger() -> structlog.BoundLogger:
        """Get logger for authentication."""
        return get_logger("v2g.auth")

    @staticmethod
    def get_simulation_logger() -> structlog.BoundLogger:
        """Get logger for simulations."""
        return get_logger("v2g.simulation")

    @staticmethod
    def get_auction_logger() -> structlog.BoundLogger:
        """Get logger for auction calculations."""
        return get_logger("v2g.auction")

    @staticmethod
    def get_database_logger() -> structlog.BoundLogger:
        """Get logger for database operations."""
        return get_logger("v2g.database")


# Example usage patterns for different log levels
class LogMessages:
    """Standard log message templates."""

    # DEBUG - Detailed auction calculations
    @staticmethod
    def auction_calculation(
        logger: structlog.BoundLogger,
        bids_count: int,
        asks_count: int,
        clearing_price: float,
        **kwargs: Any,
    ) -> None:
        """Log auction calculation details."""
        logger.debug(
            "auction_calculation",
            bids_count=bids_count,
            asks_count=asks_count,
            clearing_price=clearing_price,
            **kwargs,
        )

    # INFO - API requests, simulation events
    @staticmethod
    def api_request(
        logger: structlog.BoundLogger,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        **kwargs: Any,
    ) -> None:
        """Log API request completion."""
        logger.info(
            "api_request",
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=round(duration_ms, 2),
            **kwargs,
        )

    @staticmethod
    def simulation_started(
        logger: structlog.BoundLogger,
        simulation_id: str,
        n_agents: int,
        n_days: int,
        **kwargs: Any,
    ) -> None:
        """Log simulation start."""
        logger.info(
            "simulation_started",
            simulation_id=simulation_id,
            n_agents=n_agents,
            n_days=n_days,
            **kwargs,
        )

    @staticmethod
    def simulation_completed(
        logger: structlog.BoundLogger,
        simulation_id: str,
        duration_seconds: float,
        total_volume: float,
        **kwargs: Any,
    ) -> None:
        """Log simulation completion."""
        logger.info(
            "simulation_completed",
            simulation_id=simulation_id,
            duration_seconds=round(duration_seconds, 2),
            total_volume=total_volume,
            **kwargs,
        )

    # WARNING - Performance issues
    @staticmethod
    def slow_query(
        logger: structlog.BoundLogger,
        query_type: str,
        duration_ms: float,
        threshold_ms: float = 100,
        **kwargs: Any,
    ) -> None:
        """Log slow database query warning."""
        logger.warning(
            "slow_query",
            query_type=query_type,
            duration_ms=round(duration_ms, 2),
            threshold_ms=threshold_ms,
            **kwargs,
        )

    @staticmethod
    def high_memory_usage(
        logger: structlog.BoundLogger,
        memory_mb: float,
        threshold_mb: float,
        **kwargs: Any,
    ) -> None:
        """Log high memory usage warning."""
        logger.warning(
            "high_memory_usage",
            memory_mb=round(memory_mb, 2),
            threshold_mb=threshold_mb,
            **kwargs,
        )

    # ERROR - Exceptions, failed requests
    @staticmethod
    def request_failed(
        logger: structlog.BoundLogger,
        method: str,
        path: str,
        error: str,
        status_code: int = 500,
        **kwargs: Any,
    ) -> None:
        """Log failed request."""
        logger.error(
            "request_failed",
            method=method,
            path=path,
            error=error,
            status_code=status_code,
            **kwargs,
        )

    @staticmethod
    def exception_occurred(
        logger: structlog.BoundLogger,
        error_type: str,
        error_message: str,
        **kwargs: Any,
    ) -> None:
        """Log exception occurrence."""
        logger.error(
            "exception_occurred",
            error_type=error_type,
            error_message=error_message,
            exc_info=True,
            **kwargs,
        )


# Initialize default logger on module import
_default_logger: Optional[structlog.BoundLogger] = None


def init_default_logger() -> structlog.BoundLogger:
    """Initialize the default application logger."""
    global _default_logger
    if _default_logger is None:
        log_level = os.environ.get("LOG_LEVEL", "INFO")
        is_production = os.environ.get("ENVIRONMENT", "development") == "production"
        _default_logger = setup_logging(
            level=log_level,
            json_format=is_production,
        )
    return _default_logger
