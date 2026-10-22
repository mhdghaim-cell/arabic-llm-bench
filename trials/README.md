# Trials

One file per trial. A trial picks a job, models and machines from `registry/` and fixes everything that must not change after pre-registration.

- `jt-NN-<job>.yaml`: a full Job Trial (standard R1-R10, verdicts allowed).
- `qt-NN-<model>-<job>.yaml`: a Quick Trial (numbers only, no verdict, labelled exploratory; standard v1.1).

Lifecycle: `planned → preregistered (commit hash recorded) → run → scored → validated → published`. The file is committed before the run; later changes are amendments with a date and a reason.
