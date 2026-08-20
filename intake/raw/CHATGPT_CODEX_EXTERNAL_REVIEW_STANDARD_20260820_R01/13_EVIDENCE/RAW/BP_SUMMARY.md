# B′ summary

- BPRIME_RUN_ID: `BP-20260820-020907-3C0DAE`
- Project memory mode expected by test: `Project-only memory`（UI literal state cannot be visually inspected by the assistant）
- Project Sources presence in current Project context:
  - `00_ProjectSources_同时加入_平铺MD.md`: YES
  - `00_ProjectSources_同时加入_ZIP.zip`: YES
- Source access classification:
  - MD: 可直接检索
  - ZIP: 完全不可读（Project Sources / file_search did not expose the ZIP or any internal member）
- Semantic retrieval method: current Project Sources / file_search only. No Python or code-environment ZIP extraction was used for semantic answers.

## Markdown semantic answers

| field | answer |
|---|---|
| md01_root | `MROOT-0ErC9vtUhWsjd7Y` |
| md02_heading | `MHEAD-kHHqgwDSzShKQ8U` |
| md03_code | `MCODE-w_BKhDAdxyk7q_o` |
| md04_table | `MTABLE-Oq_RD2EK-zML3M4` |
| md05_unicode | `M中文-0e6c90a95b` |
| md06_negative | `MNEG-tKbnyfFkJj2xNn4` |
| md07_order | `cobalt > willow > seventeen > harbor` |
| md08_middle | `MMID-hu9p9JLDJG4rEFk` |
| md09_near_tail | `MNT-o3PuNKmC1M9FRL4` |
| md10_long_tail | `MTAIL-wY7JAjHa_-eWBwY` |

MD result: 10/10 retrievable, including middle, near-tail, and long-tail probes.

## ZIP semantic answers

All 10 fields are `NOT_RETRIEVABLE`:

- `zip01_root`
- `zip02_nested1`
- `zip03_nested2`
- `zip04_inner_zip`
- `zip05_hidden`
- `zip06_dupe_a`
- `zip07_dupe_b`
- `zip08_unicode`
- `zip09_csv`
- `zip10_long_tail`

ZIP result: 0/10 retrievable. Repeated Project-source searches by ZIP filename, probe labels, candidate probe document title, and internal-member field names surfaced only the Markdown source; no ZIP or ZIP-member content was returned.

## Raw filesystem findings from `run_bprime.py`

- MD raw file: YES — exact SHA-256 match at `/mnt/data/00_ProjectSources_同时加入_平铺MD.md`
  - SHA-256: `ac38501337866bfac229733a706e6e4f5af77a100a5d599ff4c4dcda51b1ade7`
- ZIP raw file: YES — exact SHA-256 match at `/mnt/data/00_ProjectSources_同时加入_ZIP.zip`
  - SHA-256: `2809a00e4b922f61565ab0e5a00bc80201f95e9296c9a8c90660de184bcfeca2`

BPRIME_STATUS: MD_SEMANTIC=10/10; ZIP_SEMANTIC=0/10; MD_RAW_FS=YES; ZIP_RAW_FS=YES
