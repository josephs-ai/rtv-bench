"""Latency is three metrics, not one.

The Spec treats "glass-to-glass" as a single number. It is only literally
meaningful for V2V. The three categories measure fundamentally different
intervals, with different instruments, and the results are no more comparable
across categories than the quality rubrics are.

    V2V            input frame            -> corresponding output frame
    Generation     API send timestamp     -> first output frame that visibly
                                             diverges from the pre-steer baseline
    Digital human  audio onset            -> first lip movement

A LatencySample therefore carries its interval kind. Aggregation refuses to mix
kinds, exactly as report tables refuse to mix Lens P and Lens M.
"""
import enum
from typing import List, NamedTuple, Optional


class Interval(enum.Enum):
    """What the number actually measures. Not interchangeable."""

    V2V_FRAME_TO_FRAME = "v2v_frame_to_frame"
    GEN_SEND_TO_DIVERGENCE = "gen_send_to_divergence"
    DH_AUDIO_TO_LIP = "dh_audio_to_lip"

    @property
    def label(self) -> str:
        return {
            Interval.V2V_FRAME_TO_FRAME: "input frame -> output frame",
            Interval.GEN_SEND_TO_DIVERGENCE: "API send -> first divergent frame",
            Interval.DH_AUDIO_TO_LIP: "audio onset -> first lip movement",
        }[self]


class Method(enum.Enum):
    """How the interval was instrumented.

    For V2V, IMPULSE is primary: a hard luminance flash survives arbitrary
    restyling because a transient is still a transient under any style. BLOCK-
    STRIP is secondary and is only trusted on styled clips after the two agree
    on unstyled clips in the pilot.
    """

    IMPULSE_XCORR = "impulse_xcorr"
    BLOCK_STRIP = "block_strip"
    API_TIMESTAMP = "api_timestamp"
    FRAME_DIVERGENCE = "frame_divergence"
    AUDIO_ONSET = "audio_onset"
    EXTERNAL_HIGHSPEED = "external_highspeed"  # 240fps phone, closed products


# Which instrument is authoritative for each interval.
PRIMARY_METHOD = {
    Interval.V2V_FRAME_TO_FRAME: Method.IMPULSE_XCORR,
    Interval.GEN_SEND_TO_DIVERGENCE: Method.FRAME_DIVERGENCE,
    Interval.DH_AUDIO_TO_LIP: Method.AUDIO_ONSET,
}

SECONDARY_METHOD = {
    Interval.V2V_FRAME_TO_FRAME: Method.BLOCK_STRIP,
}


class LatencySample(NamedTuple):
    """One measured event. Campaign A wants >=30 of these per condition."""

    lag_ms: float
    interval: Interval
    method: Method
    # Peak prominence for xcorr, parity-check pass rate for block strip.
    # Samples below the caller's confidence floor are dropped and counted.
    confidence: float
    event_index: Optional[int] = None


class LatencyResult(NamedTuple):
    interval: Interval
    method: Method
    lens: str  # "P" or "M" - never aggregated across
    n: int
    mean_ms: float
    p50_ms: float
    p95_ms: float
    jitter_ms: float  # sigma
    rig_offset_ms: float  # subtracted already; recorded for the report
    dropped_low_confidence: int

    def headline(self) -> str:
        return "p95 %.0f ms [Lens %s] (%s, %s, n=%d)" % (
            self.p95_ms, self.lens, self.interval.label, self.method.value, self.n)


def summarise(samples: List[LatencySample], lens: str, rig_offset_ms: float = 0.0,
              min_confidence: float = 0.0) -> LatencyResult:
    """Reduce samples to the reportable five-number summary.

    Refuses to mix intervals or methods - that would be the latency equivalent
    of a cross-lens table.
    """
    import statistics

    if not samples:
        raise ValueError("no samples")

    intervals = {s.interval for s in samples}
    methods = {s.method for s in samples}
    if len(intervals) > 1:
        raise ValueError("cannot mix intervals: %s" % ", ".join(i.value for i in intervals))
    if len(methods) > 1:
        raise ValueError("cannot mix methods: %s" % ", ".join(m.value for m in methods))

    kept = [s for s in samples if s.confidence >= min_confidence]
    dropped = len(samples) - len(kept)
    if not kept:
        raise ValueError("all %d samples below confidence floor %.2f"
                         % (len(samples), min_confidence))

    lags = sorted(s.lag_ms - rig_offset_ms for s in kept)
    n = len(lags)
    # Nearest-rank percentile; with n>=30 the interpolation choice is immaterial
    # and this one is defensible without argument.
    p50 = lags[min(n - 1, int(round(0.50 * n)) - 1 if n > 1 else 0)]
    p95 = lags[min(n - 1, max(0, int(round(0.95 * n)) - 1))]

    return LatencyResult(
        interval=kept[0].interval,
        method=kept[0].method,
        lens=lens,
        n=n,
        mean_ms=statistics.fmean(lags),
        p50_ms=p50,
        p95_ms=p95,
        jitter_ms=statistics.pstdev(lags) if n > 1 else 0.0,
        rig_offset_ms=rig_offset_ms,
        dropped_low_confidence=dropped,
    )
