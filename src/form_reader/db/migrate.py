from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

from .engine import dispose_engine
from .paths import database_url

logger = logging.getLogger(__name__)

ALEMBIC_DIR = Path(__file__).resolve().parent / "alembic"


def alembic_config(url: str | None = None) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(ALEMBIC_DIR))
    cfg.set_main_option("sqlalchemy.url", url or database_url())
    return cfg


def upgrade_to_head(url: str | None = None) -> None:
    command.upgrade(alembic_config(url), "head")


def init_db() -> None:
    """Create/upgrade the SQLite schema, then reset any cached engine."""
    logger.debug("Applying Alembic migrations to %s", database_url())
    upgrade_to_head()
    dispose_engine()
