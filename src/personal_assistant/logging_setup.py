import logging
import os
import structlog
try:
    # Newer import path per deprecation notice
    from pythonjsonlogger import json
    JsonFormatter = json.JsonFormatter
except Exception:
    from pythonjsonlogger import jsonlogger
    JsonFormatter = jsonlogger.JsonFormatter


def configure_logging():
    # Configure stdlib logger to emit JSON to stdout and file
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    formatter = JsonFormatter()

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    log_path = os.environ.get("AGENT_LOG_FILE")
    handlers = [stream_handler]
    if log_path:
        file_handler = logging.FileHandler(log_path)
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    logger.handlers = handlers
    logger.propagate = False

    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str):
    return structlog.get_logger(name)
