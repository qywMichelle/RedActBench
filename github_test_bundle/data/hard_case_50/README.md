# Existing hard-case collection: 50 episodes

This self-contained collection aggregates **50 existing frozen development episodes** from `hard_case` (20), `hard_case_02` (10) and `hard_case_03` (20). It contains no new episodes, model runs, Opus evaluation or semantic review.

Use [index.md](index.md) to browse cases, [manifest.json](manifest.json) as the selection entry and [mapping.json](mapping.json) for identity mapping. Collection IDs `h001`–`h050` are metadata only. The original `c01`–`c10`, `h01`–`h10`, `n01`–`n10` and `p01`–`p20` filenames, internal world IDs, episode IDs and source episode IDs are preserved. Core JSON and all current author-record files are byte-identical to their source versions.

The collection has **396 goals, 787 rubric checks and 355 current author-record files**. Reference paths total 2,438 calls, averaging **48.76** per episode. Repeated record hashes remain explicit source aliases; file counts are not counts of independent strategies.

Run the standalone local check with Python 3.10 or newer:

```bash
python data/hard_case_50/verify.py --progress
```

The stdlib verifier checks every copied core/runtime hash and local source-manifest binding, all 50 initial projections, and exact replay of all 355 author records. It writes `verification.json`. It requires no original source directories, network services or third-party packages. Negative author controls are included in replay; replay success does not establish semantic success.

Two complete runtime-file sets were found by actual byte comparison. The first package’s v1 runtime remains separate. Its v2 runtime is identical to the modern runtime used by packages 02 and 03, so those share a deduplicated bundle. Every manifest entry pins its exact runtime root and file hashes; no old world has been upgraded. [runtime-bundles.json](runtime-bundles.json) records all source-version aliases.

Only `visible/<case>.json` plus its manifest-named public tool descriptors should be supplied as initial candidate input. Hidden worlds, rubrics, trajectories, source cards and review evidence contain answers or provenance. Inputs and produced artifacts are textual structured simulations, not actual audiovisual media or real-world transactions.

Exact source manifests, all 50 source cards, applicable tool descriptors and minimal accepted review summaries/reports are retained locally as provenance. Those reports preserve their original scope and identity. Full historical review archives and earlier model-evaluation artifacts remain in the original source packages; they are not current execution dependencies. Original benchmark data and source packages were not modified.

All 50 retain their source package’s structural `hard` label. Earlier source labels remain separate where supplied. This aggregation does not add human review, formal split validation, empirical difficulty calibration or judge calibration; `formal_evaluation_ready` remains false.
