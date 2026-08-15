from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from .engine import session_factory
from .models import RunStat


@dataclass(frozen=True)
class RunStatRecord:
    id: int
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    worker_threads: int
    method: str
    models: str
    cells_read: int
    cells_accurate: int
    status: str
    export_path: str

    @classmethod
    def from_row(cls, row: RunStat) -> RunStatRecord:
        return cls(
            id=row.id,
            started_at=row.started_at,
            finished_at=row.finished_at,
            duration_ms=row.duration_ms,
            worker_threads=row.worker_threads,
            method=row.method,
            models=row.models,
            cells_read=row.cells_read,
            cells_accurate=row.cells_accurate,
            status=row.status,
            export_path=row.export_path,
        )


class RunStatsRepository:
    def record(
        self,
        *,
        started_at: datetime,
        finished_at: datetime,
        duration_ms: int,
        worker_threads: int,
        method: str,
        models: str,
        cells_read: int,
        cells_accurate: int,
        status: str,
        export_path: str,
    ) -> RunStatRecord:
        row = RunStat(
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            worker_threads=worker_threads,
            method=method,
            models=models,
            cells_read=cells_read,
            cells_accurate=cells_accurate,
            status=status,
            export_path=export_path,
        )
        factory = session_factory()
        with factory() as session:
            session.add(row)
            session.commit()
            session.refresh(row)
            return RunStatRecord.from_row(row)

    def list_all(self) -> list[RunStatRecord]:
        factory = session_factory()
        with factory() as session:
            rows = session.scalars(
                select(RunStat).order_by(RunStat.started_at.desc(), RunStat.id.desc())
            ).all()
            return [RunStatRecord.from_row(row) for row in rows]
