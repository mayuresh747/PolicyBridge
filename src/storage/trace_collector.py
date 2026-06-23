"""In-memory accumulator for pipeline trace stages (PERS-04).

TraceCollector is always instantiated before run_pipeline() and passed
as a parameter. Inside the generator, stages are recorded on the collector.
After the generator is exhausted, the caller reads collector.stages and
saves via TraceStore.

Stage format matches existing SSE audit_* event payloads per D-17:
    {stage, elapsed_ms, timestamp, data}
"""

import time
import uuid


class TraceCollector:
    """In-memory accumulator for pipeline trace stages. Always instantiated."""

    def __init__(self):
        self.trace_id: str = uuid.uuid4().hex
        self.stages: list[dict] = []
        self._start: float = time.perf_counter()

    def add_stage(self, stage: str, data: dict) -> None:
        """Record a pipeline stage with timing and payload data.

        Args:
            stage: Stage name (e.g. 'classify', 'retrieve', 'decompose').
            data: Stage-specific payload (same as audit event data).
        """
        elapsed = (time.perf_counter() - self._start) * 1000
        self.stages.append({
            "stage": stage,
            "elapsed_ms": round(elapsed, 1),
            "timestamp": time.time(),
            "data": data,
        })

    @property
    def total_ms(self) -> float:
        """Total elapsed time up to the last recorded stage."""
        if self.stages:
            return self.stages[-1]["elapsed_ms"]
        return 0.0
