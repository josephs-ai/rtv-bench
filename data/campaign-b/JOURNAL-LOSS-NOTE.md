# Journal incident note — 2026-08-15

During the pre-publication history rewrite (`git filter-repo`, run to purge
an oversize blob and PII), tracked-but-uncommitted working-tree changes
were reset. Three Campaign B journals lost their night-2/3 row tails:
`runs.jsonl`, `queue-journal.jsonl`, `spend.jsonl`.

**What survives (committed before the loss, authoritative):**
- `data/benchmark-scorecard.json` — full adjudicated tallies computed FROM
  the complete journals hours before the loss (lucy-2.5 N=210 measured,
  xmax Lens M N=85, xmax P-browser N=91, with CIs)
- all capture files + per-capture metadata (untracked, untouched)
- `adjudications.json`, pairwise/edit/audit records, sentinel history

**What was lost:** raw row-level entries for the affected stints. They are
summarized in the scorecard but can no longer be re-derived row-by-row.

**Remediation:**
- queue-journal reconstructed from surviving evidence: lucy marked
  complete (she finished her queue on 08-14, attested by capture metas +
  scorecard); xmax Lens M slots whose rows were lost remain PENDING and
  will be re-run, producing fresh replacement rows.
- process rule added: journals are committed after every session/stint;
  no history-rewriting git operation runs without `git stash -u` first.

This note exists because the benchmark's honesty rules apply to the
benchmark itself.
