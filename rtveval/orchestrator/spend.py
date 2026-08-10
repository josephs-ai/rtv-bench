"""Spend cap: reserve before dispatch, reconcile after completion.

Post-hoc accounting fails in exactly the scenario the cap exists for: a hung
session bills continuously while the counter still reads the last completed
run. So the estimated MAXIMUM cost of a run is charged against the budget at
dispatch; completion reconciles the reservation down (or up) to actual. A run
that cannot reserve does not launch.

The companion guard is the per-session wall-clock kill (runner.py): a hung
session is bounded in time, therefore its reservation is a true maximum,
therefore committed = sum(reservations) + sum(actuals) can never silently pass
the cap.

State is journalled so a crashed orchestrator resumes with its spend intact -
open reservations from a dead process replay as their maximum, which is
conservative in the right direction.
"""
import json
import os
import threading
from typing import Dict, NamedTuple, Optional


class CapExceeded(RuntimeError):
    pass


class SpendState(NamedTuple):
    cap_usd: float
    reserved_usd: float
    actual_usd: float

    @property
    def committed_usd(self) -> float:
        return self.reserved_usd + self.actual_usd

    @property
    def headroom_usd(self) -> float:
        return self.cap_usd - self.committed_usd


class SpendCap:
    def __init__(self, cap_usd: float, journal_path: str):
        if cap_usd <= 0:
            raise ValueError("cap must be positive")
        self.cap_usd = cap_usd
        self.journal_path = journal_path
        self._lock = threading.Lock()
        self._open: Dict[str, float] = {}  # run_id -> reserved max
        self._actual: float = 0.0
        self._replay()

    def _replay(self) -> None:
        if not os.path.exists(self.journal_path):
            return
        with open(self.journal_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec["op"] == "reserve":
                    self._open[rec["run_id"]] = rec["usd"]
                elif rec["op"] == "reconcile":
                    self._open.pop(rec["run_id"], None)
                    self._actual += rec["usd"]

    def _journal(self, rec: dict) -> None:
        os.makedirs(os.path.dirname(self.journal_path) or ".", exist_ok=True)
        with open(self.journal_path, "a") as f:
            f.write(json.dumps(rec) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def state(self) -> SpendState:
        with self._lock:
            return SpendState(self.cap_usd, sum(self._open.values()), self._actual)

    def reserve(self, run_id: str, max_cost_usd: float) -> None:
        """Charge the run's maximum against the budget, or refuse to launch."""
        if max_cost_usd < 0:
            raise ValueError("negative cost")
        with self._lock:
            committed = sum(self._open.values()) + self._actual
            if committed + max_cost_usd > self.cap_usd:
                raise CapExceeded(
                    "reserving $%.2f would commit $%.2f of $%.2f cap"
                    % (max_cost_usd, committed + max_cost_usd, self.cap_usd))
            self._open[run_id] = max_cost_usd
            self._journal({"op": "reserve", "run_id": run_id, "usd": max_cost_usd})

    def reconcile(self, run_id: str, actual_cost_usd: float) -> None:
        """Replace the reservation with what the run actually cost."""
        with self._lock:
            if run_id not in self._open:
                raise KeyError("no open reservation for %s" % run_id)
            self._open.pop(run_id)
            self._actual += actual_cost_usd
            self._journal({"op": "reconcile", "run_id": run_id, "usd": actual_cost_usd})


def estimate_max_cost_usd(duration_intended_s: Optional[float],
                          usd_per_second: float,
                          wall_clock_kill_s: float) -> float:
    """A run's cost ceiling. For open-ended streams the kill timer IS the
    bound - which is why the kill is not optional."""
    bound_s = min(duration_intended_s, wall_clock_kill_s) if duration_intended_s \
        else wall_clock_kill_s
    return bound_s * usd_per_second
