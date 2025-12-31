import logging
import structlog
try:
    # Newer import path per deprecation notice
    from pythonjsonlogger import json
    JsonFormatter = json.JsonFormatter
except Exception:
    from pythonjsonlogger import jsonlogger
    JsonFormatter = jsonlogger.JsonFormatter


def configure_logging():
    # Configure stdlib logger to emit JSON
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    formatter = JsonFormatter()
    handler.setFormatter(formatter)
    logger.handlers = [handler]

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
