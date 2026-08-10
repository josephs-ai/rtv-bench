# Morning auto-plan (2026-08-11) — execute when overnight run completes

Standing instruction from the user ("can u auto move on to next step after the
results come in") — run these without waiting, in order, when task
`overnight_calibration` finishes:

1. **Analysis pass** — read `data/overnight-summary.json`; check every arm for
   `VANTAGE_TAINTED` / skipped; `tools/floor_analysis.py` output: new C0 floor
   + CI, C0-minimal rig verdict, C1/C2/C3 degradation curve. Compare nothing
   to `data/stale-vantage/` (contaminated, different vantage).
2. **Encoder contamination** — if the 6 pilot captures in
   `data/pilot-captures/*.mkv` exist and are non-trivial:
   `.venv-metrics/bin/python tools/encoder_contamination.py data/pilot-captures/*.mkv`
   Marginal verdict → default FFV1 (user rule). Closes pilot blocker #2.
3. **Bridge Lens M leg** — with `RTVEVAL_FORCE_TURN_TCP=1`: 5-8 short runs of
   `xmax/x2` via ReactorWebRTCAdapter publishing the instrumented
   `data/lucy-clip/lucy-720p.mp4` (input spec caveat: xmax-via-Reactor served
   resolution unconfirmed — annotate); impulse lag → summarise (Lens M, SDK
   path) → **Reactor delta = Lens M minus Lens P 367 ms**
   (`data/xmax-lensP-composite.json`). Write `data/bridge-measurement.json`.
4. **Commit everything**, write the morning report (one readable summary:
   floor, curve, rig verdict, contamination verdict, bridge delta, taint
   list, what remains human-only).

Human-only items to surface in the report, not attempt:
- Eyeball the captures: `tools/eyeball.py capture data/pilot-captures`
- Rater trial, shoot, PixVerse/Vidu gates.
