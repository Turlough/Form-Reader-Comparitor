from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .fields_config import FieldsConfig


@dataclass
class BatchRow:
    relative_path: str
    ground_truth: list[str]  # columns 1..n
    read_values: dict[int, str] = field(default_factory=dict)  # column -> LLM output

    def filename(self) -> str:
        return Path(self.relative_path).name

    def resolve_path(self, batch_dir: Path) -> Path:
        return (batch_dir / self.relative_path).resolve()

    def cell_display(self, column: int) -> str:
        if column in self.read_values:
            return self.read_values[column]
        idx = column - 1
        if 0 <= idx < len(self.ground_truth):
            return self.ground_truth[idx]
        return ""

    def ground_truth_for(self, column: int) -> str:
        idx = column - 1
        if 0 <= idx < len(self.ground_truth):
            return self.ground_truth[idx]
        return ""

    def values_match(self, column: int) -> bool:
        if column not in self.read_values:
            return True
        return self.read_values[column].strip().upper() == self.ground_truth_for(column).strip().upper()


@dataclass
class Batch:
    export_path: Path
    rows: list[BatchRow]
    fields_config: FieldsConfig
    column_count: int

    @property
    def batch_dir(self) -> Path:
        return self.export_path.parent

    @property
    def fields_json_path(self) -> Path:
        return self.batch_dir / "fields.json"
