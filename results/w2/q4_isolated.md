| model                          |       size |     params | backend    | threads |            test |                  t/s |
| ------------------------------ | ---------: | ---------: | ---------- | ------: | --------------: | -------------------: |
| llama 1B Q4_K - Medium         | 762.81 MiB |     1.24 B | BLAS       |       4 |           pp512 |       172.60 ± 12.77 |
| llama 1B Q4_K - Medium         | 762.81 MiB |     1.24 B | BLAS       |       4 |           tg128 |         36.36 ± 1.67 |

build: c1d0e7a00 (10621)
