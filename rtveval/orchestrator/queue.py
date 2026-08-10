"""Round-based durable queue.

Round-based, not per-product-sequential: every product completes run n before
any product starts run n+1. Interleaving alone does not guarantee this - a
product that fails fast races ahead and bunches its runs into one part of the
night, which both unbalances truncation and concentrates its samples in one
load window. With rounds, a queue that dies at 4 a.m. leaves N=180/180/180
(comparable) instead of 300/300/90 (not).

Durability: an append-only JSONL journal of completed run ids. Resume = replay
the journal and skip. Run ids are deterministic, so a crash between "run
finished" and "journal written" costs at most one duplicated run, which the
idempotent id then identifies for dedup at analysis.
"""
import json
import os
from typing import Dict, Iterator, List, NamedTuple, Optional, Sequence


class RunSpec(NamedTuple):
    run_id: str
    campaign: str  # A | B | C
    product_key: str
    condition_id: str
    round_index: int
    clip_id: Optional[str] = None
    prompt_id: Optional[str] = None

    @staticmethod
    def make_id(campaign: str, product_key: str, condition_id: str,
                round_index: int) -> str:
        return "%s-%s-%s-r%04d" % (campaign, product_key, condition_id, round_index)


def build_rounds(campaign: str, product_keys: Sequence[str], condition_id: str,
                 n_rounds: int,
                 clip_for_round=None, prompt_for_round=None) -> List[List[RunSpec]]:
    """rounds[i] = one run per product. Order within a round rotates so the
    same product is not always first (time-of-day fairness inside the round)."""
    rounds: List[List[RunSpec]] = []
    for r in range(n_rounds):
        rotation = list(product_keys[r % len(product_keys):]) + \
            list(product_keys[:r % len(product_keys)])
        rounds.append([
            RunSpec(run_id=RunSpec.make_id(campaign, p, condition_id, r),
                    campaign=campaign, product_key=p, condition_id=condition_id,
                    round_index=r,
                    clip_id=clip_for_round(r) if clip_for_round else None,
                    prompt_id=prompt_for_round(r) if prompt_for_round else None)
            for p in rotation])
    return rounds


class RoundQueue:
    def __init__(self, rounds: List[List[RunSpec]], journal_path: str):
        self.rounds = rounds
        self.journal_path = journal_path
        self._done: set = set()
        if os.path.exists(journal_path):
            with open(journal_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        self._done.add(json.loads(line)["run_id"])

    def mark_done(self, run_id: str) -> None:
        self._done.add(run_id)
        os.makedirs(os.path.dirname(self.journal_path) or ".", exist_ok=True)
        with open(self.journal_path, "a") as f:
            f.write(json.dumps({"run_id": run_id}) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def pending(self) -> Iterator[RunSpec]:
        """Strict round order: nothing from round r+1 until round r is drained.
        This single loop is the whole guarantee."""
        for rnd in self.rounds:
            for spec in rnd:
                if spec.run_id not in self._done:
                    yield spec

    def completed_rounds(self) -> int:
        """Fully-completed rounds - the balanced-N guarantee made measurable."""
        n = 0
        for rnd in self.rounds:
            if all(s.run_id in self._done for s in rnd):
                n += 1
            else:
                break
        return n

    def balanced_n(self) -> Dict[str, int]:
        """Per-product count *within completed rounds* - what analysis may use
        as matched samples if the queue is truncated right now."""
        k = self.completed_rounds()
        counts: Dict[str, int] = {}
        for rnd in self.rounds[:k]:
            for s in rnd:
                counts[s.product_key] = counts.get(s.product_key, 0) + 1
        return counts

    def project(self, seconds_per_round: float, seconds_remaining: float) -> Dict:
        """The actionable won't-finish projection: how many rounds fit in the
        time left, so N is reduced uniformly instead of losing a product."""
        remaining_rounds = len(self.rounds) - self.completed_rounds()
        affordable = int(seconds_remaining / seconds_per_round) if seconds_per_round > 0 else 0
        return {
            "rounds_total": len(self.rounds),
            "rounds_done": self.completed_rounds(),
            "rounds_remaining": remaining_rounds,
            "rounds_affordable": affordable,
            "will_finish": affordable >= remaining_rounds,
            "suggested_truncation": None if affordable >= remaining_rounds
            else self.completed_rounds() + affordable,
        }
