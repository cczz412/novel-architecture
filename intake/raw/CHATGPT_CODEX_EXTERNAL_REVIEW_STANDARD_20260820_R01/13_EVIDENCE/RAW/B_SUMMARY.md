# Probe B summary

## Run identity

- A_RUN_ID: `A-20260820-004405-3C39D7`
- B_RUN_ID: `B-20260820-010634-11E80C`
- Project source public ID expected by the probe: `PSR04-29EB6E3CC550`
- Expected Project Source ZIP SHA-256: `79ec6040a36285f043a7feba200aeedc215e0726b62a3da97f01fa1ba78ccf4e`
- Result directory: `/mnt/data/CHATGPT_PROBE_B_RESULT_B-20260820-010634-11E80C`

## Consolidated status

`B_STATUS: A_FS=NOT_FOUND; PROJECT_SOURCE_SEMANTIC=NOT_RETRIEVABLE; RAW_BYTES=NOT_FOUND; A_MEMORY=RETRIEVED; LIBRARY_A=NOT_FOUND`

## A filesystem carry-over

The mechanical probe checked its bounded known locations for `CHATGPT_PROBE_A_FS_SEED_A-20260820-004405-3C39D7.json` and returned no hit. A separate bounded check of `/mnt/data`, `/tmp`, and `/home/oai` also found neither the A seed nor the A result ZIP.

Result: `A_FS=NOT_FOUND`.

## Mechanical probe results

### B01 — A cross-chat filesystem seed

No A seed was found in the known paths. The returned list is empty.

### B02 — execution environment

- Platform: `Linux-6.18.35-x86_64-with-glibc2.41`
- Python: `3.13.5`
- Visible CPU count / affinity: 5 CPUs
- cgroup memory ceiling: 4 GiB
- Node.js: `v22.16.0`
- Git: `2.47.3`
- Root filesystem: ext4, approximately 63 GiB total and 38 GiB available at probe time

### B03 — DNS and TCP

DNS resolution failed for all four fixed public hosts tested by the script: `example.com`, `api.openai.com`, `pypi.org`, and `github.com`. TCP 443 therefore also failed for each host. The recorded error was temporary name-resolution failure.

### B04 — pip install

A fresh virtual environment was created. Installing `humanize==4.12.3` failed because the environment could not resolve `pypi.org`. This is recorded as a network/DNS failure, not as proof that the package or version does not exist.

### B05 — remote Git

`git ls-remote https://github.com/git/git.git HEAD` failed because `github.com` could not be resolved.

### B06 — raw Project Source ZIP bytes

The bounded raw-byte search found no file matching the Project Source probe namespace and no object with the expected SHA-256.

Result: `RAW_BYTES=NOT_FOUND`.

### B07 — fake environment variable

`FAKE_API_KEY` was absent. No environment-variable value was printed.

### B08 — B filesystem seeds for Round 3

The B seed was written successfully to four locations:

- `/mnt/data/round2_work/CHATGPT_PROBE_B_FS_SEED_B-20260820-010634-11E80C.json`
- `/mnt/data/CHATGPT_PROBE_B_FS_SEED_B-20260820-010634-11E80C.json`
- `/tmp/CHATGPT_PROBE_B_FS_SEED_B-20260820-010634-11E80C.json`
- `/home/oai/CHATGPT_PROBE_B_FS_SEED_B-20260820-010634-11E80C.json`

All four copies have SHA-256 `bba284c27fac5a97e486c473e0ad007498bcdacc4ac53ea66f3ff8d97c3ce971`. The secret itself was not printed. The probe separately recorded the secret hash `e6ada1e392a47ad6ba014d3987e200e42c42a38f9488da855e64a3fd2cf17b79`.

## Project Sources semantic retrieval

The target Project Source ZIP was not available as a current attachment or a retrievable Project Source. Searches were made through the actual file/project retrieval path using:

- exact ZIP name `02_第二轮_ProjectSources_先加入项目源.zip`;
- project public ID `PSR04-29EB6E3CC550`;
- expected SHA-256 `79ec6040a36285f043a7feba200aeedc215e0726b62a3da97f01fa1ba78ccf4e`;
- namespace terms such as `PROJECT_SOURCE_PROBE` and `PSR04`;
- all ten canary labels and combinations.

The retrieval path returned unrelated project documents but did not return the requested source ZIP or any verifiable canary content. The Project Source ZIP was not unpacked with Python or treated as a normal chat attachment.

All ten values are therefore recorded as `NOT_RETRIEVABLE` rather than guessed:

| Canary | Result |
|---|---|
| root | NOT_RETRIEVABLE |
| nested1 | NOT_RETRIEVABLE |
| nested2 | NOT_RETRIEVABLE |
| inner_zip | NOT_RETRIEVABLE |
| hidden | NOT_RETRIEVABLE |
| dupe_a | NOT_RETRIEVABLE |
| dupe_b | NOT_RETRIEVABLE |
| unicode | NOT_RETRIEVABLE |
| csv | NOT_RETRIEVABLE |
| long_tail | NOT_RETRIEVABLE |

Result: `PROJECT_SOURCE_SEMANTIC=NOT_RETRIEVABLE`.

## Ordinary chat → Project memory

The exact A canary was recovered from prior ordinary-chat history without asking the user and without loading an A result ZIP:

`A_MEMORY_CANARY=MEM-A-RZk7ea-HNC7M05hYg8Numg`

The same prior-history retrieval also recovered:

- `A_RUN_ID=A-20260820-004405-3C39D7`
- prior result ZIP name `CHATGPT_PROBE_A_RESULT_A-20260820-004405-3C39D7.zip`
- prior result SHA-256 `c3edc12d9b7fc94d9f8cdb316f713a0add5e59ba3804e13aa3584176cbf84a3c`

Result: `A_MEMORY=RETRIEVED`.

## Library

This check was performed after the memory test. Exact and recall-oriented File Library searches did not find `CHATGPT_PROBE_A_RESULT_A-20260820-004405-3C39D7.zip`. Since the file was not found, it could not be re-added to the current chat.

- Found: `false`
- Re-attachable: `false`

Result: `LIBRARY_A=NOT_FOUND`.

## Project chat memory block for Round 3

`PROJECT_MEMORY_BLOCK.json` contains the twelve values that were printed in the final chat. Round 3 should recover them from same-Project chat history rather than from manually copied parameters or the B result ZIP.

## Execution notes

Two foreground invocations were terminated by the surrounding command wrapper before completion while the network-dependent pip step was retrying. Their incomplete temporary result directories were removed. A fresh third invocation completed normally and produced the B run recorded above. No incomplete run was packaged as the result.

## Final interpretation

- The Project execution environment did not expose the A filesystem seed.
- The requested Project Source semantic canaries were not retrievable through the actual source/file retrieval path available in this chat.
- The raw Project Source ZIP bytes were not present in the bounded filesystem search.
- The prior ordinary-chat memory canary was recoverable.
- The exact A result ZIP was not found in File Library and could not be attached.
