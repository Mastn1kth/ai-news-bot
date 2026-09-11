from __future__ import annotations

import logging
import re


TOKEN_PATTERN = re.compile(r"(\d{6,}:[A-Za-z0-9_-]{20,})")


class SecretFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = TOKEN_PATTERN.sub("[redacted-token]", str(record.msg))
        if record.args:
            record.args = tuple(TOKEN_PATTERN.sub("[redacted-token]", str(arg)) for arg in record.args)
        return True


def configure_logging(verbose: bool = False) -> None:
    level = logging.INFO if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger().addFilter(SecretFilter())
