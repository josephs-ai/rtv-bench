"""Network conditions on macOS: time-blocked global phases, not per-lane netns.

tc netem is Linux. This rig is Darwin (avfoundation, MPS, brew ffmpeg), and the
macOS shaping tools cannot scope to a lane: Network Link Conditioner is
system-wide and GUI-driven, and dummynet (dnctl/pfctl) - which IS scriptable -
still applies to the whole host's traffic matching a pf ruleset, not to a
network namespace, because macOS has no netns.

So the addendum's per-lane shaping is replaced by PHASES: every lane shares one
condition for a time window, and the window boundary lands on a round boundary,
which the round-based queue makes clean - a phase change between rounds leaves
every product with identical exposure to every condition. The cost is purely
concurrency (no simultaneous C0-and-C2 lanes); the comparison is preserved.

Two hard rules, enforced here:

1.  A phase change may only happen between rounds (`advance()` refuses
    otherwise).
2.  The condition recorded per run is the APPLIED state - dnctl's own view
    plus a live RTT probe - never the schedule's intention. If verification
    fails, runs in that window are E (rig), not silently mislabelled.

Mechanism (requires sudo; day-1 checklist grants NOPASSWD for exactly these):
    dnctl pipe 1 config delay <ms> plr <fraction>
    pfctl: dummynet rule routing all traffic through pipe 1
"""
import re
import subprocess
import time
from typing import Callable, List, NamedTuple, Optional

from .health import CheckResult


class Condition(NamedTuple):
    condition_id: str
    rtt_ms: int  # extra round-trip delay (dnctl takes one-way: rtt/2 per direction)
    loss_pct: float

    @property
    def is_baseline(self) -> bool:
        return self.rtt_ms == 0 and self.loss_pct == 0.0


# Plan sec 5.3.
C0 = Condition("C0", 0, 0.0)
C1 = Condition("C1", 50, 0.5)
C2 = Condition("C2", 100, 1.0)
C3 = Condition("C3", 200, 2.0)
CONDITIONS = {c.condition_id: c for c in (C0, C1, C2, C3)}


class AppliedState(NamedTuple):
    """What is ACTUALLY in force - written into every run row of the phase."""

    condition_id: str
    verified: bool
    dnctl_config: str  # dnctl's own report of the pipe
    probe_rtt_ms: Optional[float]
    detail: str
    at_utc: str


def _utcnow() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _run(cmd: List[str]) -> str:
    return subprocess.run(cmd, check=True, capture_output=True, text=True).stdout


def _default_interface() -> str:
    out = subprocess.run(["route", "-n", "get", "default"],
                         capture_output=True, text=True).stdout
    for line in out.splitlines():
        if "interface:" in line:
            return line.split(":", 1)[1].strip()
    return "en0"


class DummynetShaper:
    """dnctl/pfctl application. Every mutation is followed by a read-back."""

    PIPE = 1

    def apply(self, cond: Condition) -> str:
        if cond.is_baseline:
            self.clear()
            return "cleared (baseline)"
        oneway_ms = cond.rtt_ms // 2
        _run(["sudo", "dnctl", "pipe", str(self.PIPE), "config",
              "delay", "%dms" % oneway_ms, "plr", "%g" % (cond.loss_pct / 100.0)])
        # A pf anchor is inert unless the MAIN ruleset references it (verified
        # live: pipe configured, probe unchanged). Merge the stock pf.conf
        # with our dummynet-anchor hook, then load rules into the anchor.
        main = ('include "/etc/pf.conf"\n'
                'dummynet-anchor "rtveval"\n'
                'anchor "rtveval"\n')
        subprocess.run(["sudo", "pfctl", "-q", "-f", "-"],
                       input=main, check=True, capture_output=True, text=True)
        # Scope to the default-route interface. With VPN tunnels present, an
        # unscoped "all" matches the same packet on utunX AND en0, applying
        # the delay twice (verified live: +219 ms for a 100 ms condition).
        iface = _default_interface()
        rules = ("dummynet in on %s all pipe %d\n"
                 "dummynet out on %s all pipe %d\n"
                 % (iface, self.PIPE, iface, self.PIPE))
        subprocess.run(["sudo", "pfctl", "-q", "-a", "rtveval", "-f", "-"],
                       input=rules, check=True, capture_output=True, text=True)
        subprocess.run(["sudo", "pfctl", "-E"], check=False, capture_output=True, text=True)
        return self.read_back()

    def read_back(self) -> str:
        try:
            return _run(["sudo", "dnctl", "list"]).strip()
        except subprocess.CalledProcessError as e:
            return "dnctl list failed: %s" % e

    def clear(self) -> None:
        subprocess.run(["sudo", "pfctl", "-q", "-a", "rtveval", "-F", "all"],
                       check=False, capture_output=True)
        # Restore the stock ruleset so the dummynet-anchor hook is gone too.
        subprocess.run(["sudo", "pfctl", "-q", "-f", "/etc/pf.conf"],
                       check=False, capture_output=True)
        subprocess.run(["sudo", "dnctl", "-q", "flush"], check=False, capture_output=True)


def probe_rtt_ms(host: str = "1.1.1.1", count: int = 9) -> Optional[float]:
    """Median ICMP RTT - the live verification that shaping is in force."""
    try:
        out = subprocess.run(["ping", "-c", str(count), "-q", host],
                             capture_output=True, text=True, timeout=30).stdout
    except (subprocess.TimeoutExpired, OSError):
        return None
    m = re.search(r"= [\d.]+/([\d.]+)/", out)
    return float(m.group(1)) if m else None


def verify(cond: Condition, baseline_rtt_ms: float, shaper: DummynetShaper,
           probe: Callable[[], Optional[float]] = probe_rtt_ms,
           tolerance_ms: float = 30.0) -> AppliedState:
    """Applied-state verification via the DELTA BAND, not absolute RTT.

    A fixed +-30ms absolute check trips constantly on VPN-tunnel jitter (three
    arms skipped that way). What actually distinguishes the failure modes:
      - shaping silently absent  -> delta ~ 0
      - shaping applied twice    -> delta ~ 2x target (the utun/en0 bug)
      - shaping in force         -> delta ~ target
    So: (shaped - baseline) must land in [0.5x, 1.75x + 30ms] of the target.
    Callers should pass a baseline measured seconds before apply (median-of-
    many pings), not a session-old one.
    """
    rtt = probe()
    dn = shaper.read_back()
    if rtt is None:
        return AppliedState(cond.condition_id, False, dn, None,
                            "probe produced no RTT - cannot verify shaping", _utcnow())

    delta = rtt - baseline_rtt_ms
    lo, hi = 0.5 * cond.rtt_ms, 1.75 * cond.rtt_ms + 30.0
    ok = lo <= delta <= hi
    detail = ("delta %.1f ms vs target %d (band %.0f-%.0f; probe %.1f, "
              "baseline %.1f)" % (delta, cond.rtt_ms, lo, hi, rtt, baseline_rtt_ms))
    if not ok:
        detail += (" - SHAPING NOT IN FORCE" if delta < lo
                   else " - SHAPING DOUBLED?")
    return AppliedState(cond.condition_id, ok, dn, rtt,
                        detail, _utcnow())


def as_check(state: AppliedState) -> CheckResult:
    """Feed verification into RigEvidence: an unverified phase makes its runs
    E on positive evidence, not mislabelled data."""
    return CheckResult("netshape[%s]" % state.condition_id, state.verified,
                       state.detail, time.monotonic(), state.at_utc)


class PhasePlan(NamedTuple):
    condition_id: str
    rounds: range  # round indices this phase covers


class PhaseScheduler:
    """Owns which condition is in force and refuses mid-round changes."""

    def __init__(self, phases: List[PhasePlan], shaper: Optional[DummynetShaper] = None):
        ids = [p.condition_id for p in phases]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate condition in phase plan")
        covered: List[int] = []
        for p in phases:
            covered.extend(p.rounds)
        if sorted(covered) != list(range(len(covered))):
            raise ValueError("phases must tile the round range without gaps/overlaps")
        self.phases = phases
        self.shaper = shaper or DummynetShaper()
        self._active: Optional[AppliedState] = None

    def condition_for_round(self, round_index: int) -> str:
        for p in self.phases:
            if round_index in p.rounds:
                return p.condition_id
        raise KeyError("round %d outside phase plan" % round_index)

    def ensure(self, round_index: int, completed_rounds: int,
               baseline_rtt_ms: float) -> AppliedState:
        """Called at the top of each round. Applies + verifies the phase's
        condition; raises if that would change conditions mid-round."""
        want = self.condition_for_round(round_index)
        if self._active is not None and self._active.condition_id == want:
            return self._active
        if completed_rounds != round_index:
            raise RuntimeError(
                "phase change to %s requested at round %d but only %d rounds "
                "are complete - a mid-round change would split a round across "
                "conditions" % (want, round_index, completed_rounds))
        cond = CONDITIONS[want]
        self.shaper.apply(cond)
        self._active = verify(cond, baseline_rtt_ms, self.shaper)
        return self._active

    def teardown(self) -> None:
        self.shaper.clear()
        self._active = None
