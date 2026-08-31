| model                          |       size |     params | backend    | threads |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | ------: | --------------: | -------------------: |
| llama 1B Q5_K - Medium         | 861.81 MiB |     1.24 B | BLAS       |       4 |           pp512 |         80.13 ± 6.89 |
| llama 1B Q5_K - Medium         | 861.81 MiB |     1.24 B | BLAS       |       4 |           tg128 |         22.98 ± 0.87 |

build: c1d0e7a00 (10621)
