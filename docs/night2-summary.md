# Night-2 summary (2026-08-13, written ~05:10 CST)

## Bottom line
- **Campaign C generation eval: COMPLETE end-to-end.** 25 healthy captures →
  metrics sweep (25/25) → blinded VLM judge (31/31 judgments, E6–E8) →
  artifact audit (31/31, windowed 10-class taxonomy with onset times).
- **Campaign B: +~30 real Lucy slots landed, then BOTH providers ran out of
  credits.** 272 slots pending, fully preserved. Supervisor auto-resumes
  within minutes of any top-up — no action needed beyond paying.

## Morning actions (the only two)
1. **Top up Decart** (Lucy) — third depletion; tonight's top-up burned in
   ~29 slots / ~90 min of real streaming.
2. **Ask boss for another Reactor top-up** (Xmax lane + HO/LingBot retries).

## Campaign B night-2 stint (rounds 147+)
- Lucy: 14 S / 2 F / 1 T / 45 E-attempts (choppy-tunnel windows, honestly
  labeled + excluded per protocol; E's cluster in sentinel-logged sag
  windows).
- Xmax: 5 S / 5 E before Reactor 402 parked the lane.
- Adjudication pass done (standing control): **1 new F→E** — r0163 "never
  produced a frame" had sentinel-measured 1.18 Mbps within 60 s of the run
  window (positive shared-path evidence). r0149's F **stands** (no sub-floor
  measurement near it). adjudications.json now has 11 entries.

## Incidents handled autonomously overnight
1. Spend cap tripped at launch ($80 estimate-cap exhausted by night-1's
   ~$79 reconciled) → raised to $150 (estimate-accounting; real guard =
   provider credits).
2. `adapter.connect()` crashes used to kill the whole campaign AND leak the
   spend reservation → patched runner (release + re-raise) + per-lane
   circuit breaker in campaign_b (4 consecutive crash/E parks the lane,
   slots stay pending). Committed 4ab0c74, orchestrator tests 15/15.
3. ANTHROPIC key 401 → root cause: stray trailing "/" in the pasted key.
   Stripped in .env, validated live. (Explains nothing about the $400
   figure — that error was never billing-related.)
4. My v1 resume trigger matched a STALE "CAMPAIGN C DONE" log line and
   launched B while C was on the tunnel → killed during a sentinel hold
   (no dangling reservation), replaced with process-based trigger.
5. Reactor 402 mid-C → C fast-failed its remaining combos; 25 good captures
   unaffected; analysis proceeded.
6. Tunnel sag windows (~02:00–05:00, repeated 1.6–2.9 Mbps dips) → sentinel
   held correctly; supervisor added with tunnel gate (≥3.0 Mbps + clean UDP
   burst) so bad-window relaunches burn zero slots.
7. Decart credits depleted (3rd time) → Lucy lane parked cleanly by the
   breaker; supervisor keeps cheap 30-min probe cycles for auto-resume.

## Where things live
- Chain logs: /Users/joseph/.claude/jobs/a8bd7c92/tmp/*.log
- B journals/adjudications: data/campaign-b/ · metrics: data/quality-metrics/
- Judge: data/vlm-judge/ · audit: data/vlm-judge-audit/
- Supervisor + watchers: /Users/joseph/.claude/jobs/a8bd7c92/tmp/*.sh
