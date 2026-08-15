from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy.engine import URL

ENV_DB_PATH = "FORM_READER_DB"
_ORG = "Digidoocs"
_APP = "FormReaderComparitor"
_DB_NAME = "form_reader.db"


def database_path() -> Path:
    """SQLite file path. `FORM_READER_DB` overrides the default app-data location."""
    override = os.environ.get(ENV_DB_PATH, "").strip()
    if override:
        path = Path(override).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        return path.resolve()

    try:
        from PyQt6.QtCore import QCoreApplication, QStandardPaths

        if QCoreApplication.instance() is not None:
            base = Path(
                QStandardPaths.writableLocation(
                    QStandardPaths.StandardLocation.GenericDataLocation
                )
            )
            folder = base / _ORG / _APP
            folder.mkdir(parents=True, exist_ok=True)
            return folder / _DB_NAME
    except ImportError:
        pass

    folder = Path.home() / ".local/share" / _ORG / _APP
    folder.mkdir(parents=True, exist_ok=True)
    return folder / _DB_NAME


def database_url(path: Path | None = None) -> str:
    db_path = path or database_path()
    return URL.create("sqlite", database=db_path.as_posix()).render_as_string(
        hide_password=False
    )
