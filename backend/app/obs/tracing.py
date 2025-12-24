# app/obs/tracing.py
import time
import json
import asyncio
import uuid
import os
import logging
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, AsyncIterator, List, Set

@dataclass
class TraceEvent:
    run_id: str
    step_id: str
    agent: str
    phase: str           # start|delta|end|error
    ts: float
    meta: Dict[str, Any]
    progress: Dict[str, int]
    telemetry: Dict[str, Any]
    message_delta: Optional[str] = None
    summary: Optional[str] = None
    error: Optional[str] = None

logger = logging.getLogger(__name__)


class Tracer:
    """Fan-out to multiple listeners (SSE, WebSocket, logs, OTEL)."""

    def __init__(self, persist_dir: Optional[str] = None):
        # Each run_id fans out to zero or more subscriber queues
        self._subscribers: Dict[str, List[asyncio.Queue[Optional[str]]]] = {}
        configured_dir = (
            persist_dir
            if persist_dir is not None
            else os.getenv("TRACE_LOG_DIR", "storage/traces")
        )
        self._persist_dir: Optional[Path]
        if configured_dir:
            path = Path(configured_dir)
            path.mkdir(parents=True, exist_ok=True)
            self._persist_dir = path
        else:
            self._persist_dir = None
        self._active_runs: Set[str] = set()

    def new_run(self) -> str:
        return f"lz-{time.strftime('%Y-%m-%d-%H%M%SZ', time.gmtime())}-{uuid.uuid4().hex[:4]}"

    def ensure_run(self, run_id: str) -> None:
        """Ensure an entry exists for the run so producers can emit before listeners attach."""
        self._subscribers.setdefault(run_id, [])
        self._active_runs.add(run_id)

    def attach(self, run_id: str) -> asyncio.Queue[Optional[str]]:
        queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
        self._subscribers.setdefault(run_id, []).append(queue)
        return queue

    def detach(self, run_id: str, queue: asyncio.Queue[Optional[str]]) -> None:
        subscribers = self._subscribers.get(run_id)
        if not subscribers:
            return
        try:
            subscribers.remove(queue)
        except ValueError:
            pass
        if not subscribers:
            self._subscribers.pop(run_id, None)

    async def emit(self, ev: TraceEvent):
        subscribers = self._subscribers.get(ev.run_id, [])
        if subscribers:
            payload = json.dumps(asdict(ev))
            for queue in list(subscribers):
                await queue.put(payload)
        await self._persist(ev)
        # Always log too
        print("[TRACE]", ev.agent, ev.phase, ev.step_id)

    async def finish(self, run_id: str) -> None:
        """Signal all listeners that the run is complete."""
        subscribers = self._subscribers.get(run_id, [])
        for queue in list(subscribers):
            await queue.put(None)
        self._active_runs.discard(run_id)

    async def stream(self, run_id: str) -> AsyncIterator[str]:
        queue = self.attach(run_id)
        try:
            while True:
                data = await queue.get()
                if data is None:
                    break
                yield data
        finally:
            self.detach(run_id, queue)

    async def _persist(self, ev: TraceEvent) -> None:
        """Append the event to the on-disk journal so we can replay reasoning later."""
        if self._persist_dir is None:
            return
        payload = json.dumps(asdict(ev))
        path = self._persist_dir / f"{ev.run_id}.jsonl"
        loop = asyncio.get_running_loop()

        def _write_line():
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="utf-8") as handle:
                    handle.write(payload + "\n")
            except OSError as exc:  # pragma: no cover - best effort logging
                logger.warning("Failed to persist trace event for run %s: %s", ev.run_id, exc)

        await loop.run_in_executor(None, _write_line)

    async def read_persisted(self, run_id: str) -> List[Dict[str, Any]]:
        """Load the persisted events for a run (if any) in chronological order."""
        if self._persist_dir is None:
            return []
        path = self._persist_dir / f"{run_id}.jsonl"
        if not path.exists():
            return []
        loop = asyncio.get_running_loop()

        def _read_lines() -> List[Dict[str, Any]]:
            records: List[Dict[str, Any]] = []
            try:
                with path.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        raw = line.strip()
                        if not raw:
                            continue
                        try:
                            records.append(json.loads(raw))
                        except json.JSONDecodeError:
                            logger.warning("Skipping malformed trace line for run %s", run_id)
                            continue
            except OSError as exc:  # pragma: no cover - best effort logging
                logger.warning("Failed to read trace log for run %s: %s", run_id, exc)
                return []
            return records

        return await loop.run_in_executor(None, _read_lines)

    def is_active(self, run_id: str) -> bool:
        return run_id in self._active_runs

    def persisted_path(self, run_id: str) -> Optional[Path]:
        if self._persist_dir is None:
            return None
        return self._persist_dir / f"{run_id}.jsonl"


tracer = Tracer()
