# Vendor Evaluation Permissions

Methodology-section artifact. The plan (addendum Part 1) names written eval
permission as the single highest-value action; this records what we hold.

| Vendor | Scope | Granted by | Date | Form | Condition | Evidence |
|---|---|---|---|---|---|---|
| Reactor | Comparative evaluation / benchmarking of served models (Xmax X2, LingBot-World 2, Happy Oyster) via the API, incl. the unlisted Happy Oyster endpoint | Reactor (existing commercial relationship, via user's company) | 2026-08-10 | **Verbal** — to confirm in writing | "Fine as long as we're not intentionally harming their system" | pending 1-line email |
| Decart | (native Lucy 2.5 API access) | — | — | Standard API terms | — | — |

## The Reactor condition, operationalised

"Not intentionally harming the system" maps to concrete harness behaviour,
already enforced elsewhere in the repo:

- **Rate limits respected** — discovered in the pilot, honoured with capped
  exponential backoff (addendum Part 8; `orchestrator/runner.py`).
- **Lane starts staggered** — no simultaneous connection storms (addendum
  Part 3).
- **Spend-capped** — a hard ceiling halts the queue (`orchestrator/spend.py`).
- **No gratuitous GPU sessions** — adapter development tests against fakes and
  a single create-then-delete, never a validation loop against billed GPU
  models.

## Open

- [ ] Written (email) confirmation of the Reactor verbal grant, filed here.
- [ ] Reactor AUP otherwise prohibits "benchmarking or competitive analysis"
      and reverse engineering (`reactor.inc/legal/acceptable-use`); the direct
      grant supersedes for this engagement. The written confirmation should
      name that it does.
