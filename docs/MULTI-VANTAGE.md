# Multi-vantage runbook

The last v1.2 critical-path gate. A second vantage turns "measured from
one apartment in mainland China" into "measured from N declared points" —
and it is deliberately a ~30-minute human task on any cloud VM.

## Why it can't run from here

A vantage is a *network position*. Everything this machine produces —
however many times we run it — is one vantage. The point of the second
run is that someone else's packets take someone else's route.

## Recipe (US cloud VM, ~$5)

1. Provision any small VM (2 vCPU / 4 GB, Ubuntu; us-east or us-west),
   with Chrome or chromium installable.
2. `git clone https://github.com/josephs-ai/rtv-bench && cd rtv-bench`
3. `python3 setup.py` — follow the wizard; put keys in `.env`:
   - `DECART_API_KEY`: the same account is fine (usage is metered, not
     vantage-locked).
   - `XMAX_API_KEY`: mint a **temporary key at the origin machine**
     (`tools/live_ab.mint_xmax_temp_key`, points-capped + expiring) so
     the vendor account key never leaves home.
4. `.venv/bin/python tools/build_stimulus_pack.py` — hash-verified,
   nothing hand-fetched.
5. `.venv/bin/python tools/benchmark_run.py core` (~2 h, ~$40).
6. Fill `vantage.json` honestly (`cloud us-east-1 direct` is fine) and
   submit per `docs/SUBMITTING.md` — scores are re-derived from your
   journals, published with the vantage as a first-class dimension,
   never merged with the CN rows.

## What the second vantage answers immediately

- **Lucy clean-route latency** (Q5.1's open half): motion-to-glass
  without the VPN tunnel — the number our CN vantage structurally
  cannot produce.
- **Xmax reachability from abroad**: possibly slow or blocked — that is
  itself a market-access datapoint (mirror of Lucy's CN story).
- **Whether the reliability gap is vantage or product**: Lucy's 26%
  failure rate clusters in tunnel-sag windows; a direct-route vantage
  either reproduces it (product) or erases it (vantage) — the single
  most consequential open question in the reference run.

## Status

Pending a human with a credit card. Everything downstream (submission
verification, per-vantage reporting) is already built.
