from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


class ViewMode(StrEnum):
    AUTO = "auto"
    WIDTH = "width"
    HEIGHT = "height"
    RECTANGLE = "rectangle"


@dataclass
class ViewConfig:
    mode: ViewMode = ViewMode.AUTO
    rectangle: list[float] | None = None  # normalized x, y, w, h

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "rectangle": self.rectangle,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ViewConfig:
        if not data:
            return cls()
        mode_str = data.get("mode", ViewMode.AUTO.value)
        try:
            mode = ViewMode(mode_str)
        except ValueError:
            mode = ViewMode.AUTO
        rect = data.get("rectangle")
        if rect is not None and len(rect) == 4:
            rect = [float(v) for v in rect]
        else:
            rect = None
        return cls(mode=mode, rectangle=rect)


@dataclass
class FieldConfig:
    column: int
    name: str = ""
    prompt: str = ""
    active: bool = True
    view: ViewConfig = field(default_factory=ViewConfig)

    def display_label(self, use_names: bool) -> str:
        if use_names and self.name.strip():
            return self.name.strip()
        return str(self.column)

    def to_dict(self) -> dict[str, Any]:
        return {
            "column": self.column,
            "name": self.name,
            "prompt": self.prompt,
            "active": self.active,
            "view": self.view.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FieldConfig:
        return cls(
            column=int(data["column"]),
            name=str(data.get("name", "")),
            prompt=str(data.get("prompt", "")),
            active=bool(data.get("active", True)),
            view=ViewConfig.from_dict(data.get("view")),
        )


@dataclass
class FieldsConfig:
    fields: list[FieldConfig] = field(default_factory=list)
    schema_version: int = SCHEMA_VERSION

    @property
    def is_defined(self) -> bool:
        return bool(self.fields) and all(f.name.strip() for f in self.fields)

    def field_for_column(self, column: int) -> FieldConfig | None:
        for f in self.fields:
            if f.column == column:
                return f
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "fields": [f.to_dict() for f in self.fields],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FieldsConfig:
        version = int(data.get("schema_version", 1))
        fields = [FieldConfig.from_dict(item) for item in data.get("fields", [])]
        return cls(fields=fields, schema_version=version)

    @classmethod
    def for_column_count(cls, column_count: int) -> FieldsConfig:
        return cls(
            fields=[
                FieldConfig(column=i, name="", prompt="", active=True)
                for i in range(1, column_count + 1)
            ]
        )


def fields_json_path(export_path: Path) -> Path:
    return export_path.parent / "fields.json"


def load_fields_config(path: Path) -> FieldsConfig | None:
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return FieldsConfig.from_dict(data)


def save_fields_config(path: Path, config: FieldsConfig) -> None:
    config.schema_version = SCHEMA_VERSION
    path.write_text(
        json.dumps(config.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
