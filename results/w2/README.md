# Week 2 — quantization ladder

Model weights are not committed (4.5 GB). Reproduce with:

    hf download bartowski/Llama-3.2-1B-Instruct-GGUF --include "*Q4_K_M*" --local-dir ./models
    hf download bartowski/Llama-3.2-1B-Instruct-GGUF --include "*Q5_K_M*" --local-dir ./models
    hf download bartowski/Llama-3.2-1B-Instruct-GGUF --include "*Q8_0*"  --local-dir ./models
    hf download bartowski/Llama-3.2-1B-Instruct-GGUF --include "*f16*"   --local-dir ./models

Sizes on disk: Q4_K_M 763 MiB · Q5_K_M 862 MiB · Q8_0 1.22 GiB · F16 2.30 GiB

## Measurement protocol

llama-bench, build c1d0e7a00 (10621), BLAS backend, 4 threads, -p 512 -n 128 -r 5.

Each level measured in an isolated session on a cool machine, with at least
15 minutes idle between runs. Sequential runs are NOT comparable on this
hardware — see the thermal finding. `ladder.md` and `ladder_reversed.md` are
retained as the evidence for that, not as results.
