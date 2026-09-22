# Week 3 — cold start to first token

Machine A · same file (Llama-3.2-1B-Instruct-Q4_K_M, 762.81 MiB) · ctx 4096 · 1 token generated
Both files already in the OS disk cache — this is a warm-disk cold start.

## Ollama 0.32.11 (server already running; model unloaded with keep_alive 0 before each run)
| Run | Total | load_duration |
|---|---|---|
| 1 | 2.71 s | 2.36 s |
| 2 | 3.53 s | 2.96 s |
| 3 | 2.44 s | 2.11 s |
| 4 | 2.16 s | 1.84 s |
Median 2.57 s. Model load is ~85% of the total in every run.

## llama-server standalone, Homebrew build c1d0e7a00 (launched from nothing each run)
| Run | Total |
|---|---|
| 1 | 3.60 s |
| 2 | 1.68 s |
| 3 | 1.67 s |
Median 1.68 s. Run 1 shows the first-launch penalty seen in Week 2.

## Caveats
Ollama loads from its own blob copy of the file; standalone loads from models/. Different paths on disk.
Standalone timing includes server process startup; Ollama timing does not.
