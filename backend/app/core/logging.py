import json
import logging
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # Deliberately omit exception details, request bodies, URLs and configuration.
        return json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(),
                           "level": record.levelname, "logger": record.name,
                           "message": record.getMessage()})


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("vocalead")
    logger.handlers = [handler]
    logger.setLevel(level)
    logger.propagate = False
