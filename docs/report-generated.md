# RTV-Bench report (auto-generated)

Generated: 2026-08-15 05:22 UTC · spec 1.0 · numbers re-derived from journals

## Composite scores (per lens - lenses never merge)

| entity | STREAMER-CN | CREATOR-GLOBAL | LAB |
|---|---|---|---|
| lucy-2.5 (lens P) | 74.1 (cov 90%) | 86.0 (cov 85%) | 79.4 (cov 85%) |
| xmax-x2.0 (lens M) | 55.9 (cov 35%) | 58.2 (cov 15%) | 58.2 (cov 25%) |
| xmax-x2.0 (lens P-browser) | 62.4 | 39.9 | 48.7 |

### Axis detail

| entity | A rel | B qual | C ident | D edit | E lat | F deploy |
|---|---|---|---|---|---|---|
| lucy-2.5 (lens P) | 48.7 | 97.9 | 92.7 | 84.8 | - | 50 |
| xmax-x2.0 (lens M) | 58.2 | - | - | - | - | 50 |
| xmax-x2.0 (lens P-browser) | 63.8 | 2.1 | 84.7 | 54.0 | 58.0 | 100 |

Coverage notes: B.artifact N/A (audit blinding key overwritten); B=pairwise only; E N/A (not instrumented on this lens); renormalized

Weights (override with benchmark_score.py --weights):
```json
{
 "profiles": {
  "STREAMER-CN": {
   "A": 25,
   "B": 10,
   "C": 20,
   "D": 25,
   "E": 10,
   "F": 10
  },
  "CREATOR-GLOBAL": {
   "A": 15,
   "B": 40,
   "C": 15,
   "D": 15,
   "E": 15,
   "F": 0
  },
  "LAB": {
   "A": 25,
   "B": 25,
   "C": 15,
   "D": 20,
   "E": 15,
   "F": 0
  }
 },
 "floors": [
  "reliability floor: total capped at A+15",
  "identity floor: capped at 55"
 ]
}
```

## Reliability (adjudicated, network-fault runs excluded)

| entity | N | S | D | F | clean rate (95% CI) | fail rate (95% CI) | excluded E |
|---|---|---|---|---|---|---|---|
| lucy-2.5 (lens P) | 210 | 75 | 78 | 55 | 35.7% ([0.295, 0.424]) | 26.2% ([0.207, 0.325]) | 356 |
| xmax-x2.0 (lens M) | 85 | 47 | 28 | 10 | 55.3% ([0.447, 0.654]) | 11.8% ([0.065, 0.203]) | 249 |
| xmax-x2.0 (lens P-browser) | 91 | 23 | 68 | 0 | 25.3% ([0.175, 0.351]) | 0.0% ([0, 0.041]) | 0 |

## Same-input blinded pairs (n=64)

Clip-level majority: `{"lucy-2.5": 64}`
- E1: `{"lucy-2.5": 64}`
- E2: `{"lucy-2.5": 60, "xmax-x2.0": 4}`
- E3: `{"lucy-2.5": 61, "tie": 3}`
- E4: `{"lucy-2.5": 64}`

## Live editing (campaign D)

### lucy-2.5

| edit type | n | commit s | committed | collateral | residue | hold | judge full-apply |
|---|---|---|---|---|---|---|---|
| accessory | 3 | 1.24 | 1.0 | 0.263 | 0.761 | 1.0 | 1.0 |
| background | 6 | 1.36 | 0.67 | 0.408 | 0.565 | 1.0 | 1.0 |
| character | 6 | 3.44 | 1.0 | 0.338 | 0.845 | 1.0 | 1.0 |
| garment | 6 | 1.36 | 1.0 | 0.167 | 0.639 | 0.994 | 1.0 |
| hair | 3 | 8.31 | 0.67 | 0.425 | 0.917 | 0.346 | 1.0 |
| style | 2 | 4.55 | 1.0 | 0.0 | 0.481 | 1.0 | 1.0 |

### xmax-x2.0

| edit type | n | commit s | committed | collateral | residue | hold | judge full-apply |
|---|---|---|---|---|---|---|---|
| accessory | 3 | 13.4 | 0.33 | 0.758 | 0.985 | 1.0 | 0.0 |
| background | 6 | 1.0 | 0.5 | 0.984 | 0.994 | 1.0 | 0.5 |
| garment | 6 | 6.6 | 1.0 | 0.397 | 0.74 | 0.909 | 0.33 |
| hair | 3 | None | 0.0 | 0.955 | 0.991 | None | 0.0 |
| style | 3 | 1.0 | 1.0 | 0.0 | 0.519 | 1.0 | 1.0 |

---
xmax native vs via-Reactor delta ~650-710 ms; see docs/final-report.md

Ground rules and methodology: see BENCHMARK.md. Raw journals and adjudication log under data/.
