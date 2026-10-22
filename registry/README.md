# Registry: what Miqyas can test

Every piece of work is one cell in a matrix: **job × model × machine**.

| File | Holds |
|---|---|
| `jobs/<job>.yaml` | A job: its simulator, episodes (dev / public test / private held-out test), pass marks, difficulty level |
| `models.yaml` | Every model tested or queued: source, quantisation, licence, tool-call format, status |
| `machines.yaml` | The rental menu (floor / middle / ceiling) with cost and how to start each machine |

A trial is a file in `trials/` that picks cells from these three lists. The operating rules (what to test next, cadence, budget) live in the project doc `MIQYAS_OS.md`; the method rules live in `docs/job_trial_standard.md` (v1.1).

**Private held-out test sets** live in `private/<job>/`, which is git-ignored. Only their SHA-256 hash is committed, in the job file, at pre-registration. Never copy a private set into any other folder of this repo.
