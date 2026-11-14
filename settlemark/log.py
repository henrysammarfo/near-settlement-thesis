"""One logger for the whole pipeline."""

from __future__ import annotations

import logging
import sys

LOGGER_NAME = "settlemark"


def setup(verbose: bool = False) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        h = logging.StreamHandler(sys.stderr)
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S"))
        logger.addHandler(h)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    return logger


def get() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)
