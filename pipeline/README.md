# CIA Pipeline v1

This project converts HITRAN collision-induced absorption data and non-HITRAN CIA data found in independent literature into a unified ExoMol-style release. 

## Layout

```text
input/
├── main/                 recommended HITRAN CIA input
├── sup/                  supplementary HITRAN CIA input
└── extra/                canonical non-HITRAN CSV/JSON input

metadata/
├── species.json          accepted species records
├── sources.json          bibliography and HITRAN reference mappings
└── dataset_map.json      explicit input-to-dataset mappings

source_data/non_hitran/   provenance storage for unprocessed publisher material; never read by the main build
examples/                 golden comparison files
src/cia_pipeline/         Python package
tests/                    unit and output acceptance tests
output/                   current formal release
releases/backups/         previous formal outputs, grouped by old version
reports/release/          JSON reports for successful releases
```

## Requirements

Python 3.10 or newer is required.

## Installation

Install the package and test dependencies:

```bash
python -m pip install -e '.[test]'
```

To use the Ptashnik Word-table converter, install the extra Python dependency:

```bash
python -m pip install -e '.[test,extradata]'
```

The Ptashnik converter also requires a local LibreOffice installation with an available `soffice` executable. 
The main build, validation, and release commands otherwise use only the Python standard library.

After installation, inspect the available commands with:

```bash
cia-pipeline --help
```

## Workflow
<img width="447" height="542" alt="pipeline" src="https://github.com/user-attachments/assets/8ce88f67-8584-49bc-a98d-b4312cb162d1" />

## Commands

### `inventory`

`inventory` checks the HITRAN input collection against `dataset_map.json`, parses the input blocks, and reports missing, unexpected, or invalid records.
```bash
cia-pipeline inventory \
  --input input \
  --metadata metadata \
  --report reports/inventory.json \
  --strict
```

Use `--dry-run` to print the readable summary instead of writing the JSON file.
The `--report` argument is still required by the command-line interface.

### `convert`

`convert` transforms archived non-HITRAN publisher files into the canonical CSV/JSON format consumed from `input/extra`.

Available converters:
```text
ptashnik2011
chandran2025
dong2026
vitali2026
finenko2026
```
Examples:
```bash
cia-pipeline convert ptashnik2011 \
  --source source_data/non_hitran/ptashnik2011/water-data.doc \
  --output input/extra/ptashnik2011 \
  --metadata metadata

cia-pipeline convert chandran2025 \
  --source source_data/non_hitran/chandran2025 \
  --output input/extra/chandran2025 \
  --metadata metadata

cia-pipeline convert dong2026 \
  --source source_data/non_hitran/dong2026 \
  --output input/extra/dong2026 \
  --metadata metadata

cia-pipeline convert vitali2026 \
  --source source_data/non_hitran/vitali2026 \
  --output input/extra/vitali2026 \
  --metadata metadata

cia-pipeline convert finenko2026 \
  --source source_data/non_hitran/finenko2026 \
  --output input/extra/finenko2026 \
  --metadata metadata
```

Each converter prints a JSON result to standard output. Chandran, Dong, Vitali, and Finenko also accept an optional `--report PATH` argument. Ptashnik performs the same conversion validation but does not write a persistent report.

The converters preserve source-native scientific units. They do not normalize all datasets to HITRAN coefficient units.

### `build`

`build` is only for the first formal build, when `output` does not exist. It also requires an empty reports directory.

```bash
cia-pipeline build \
  --input input \
  --metadata metadata \
  --output output \
  --reports reports \
  --examples examples \
  --strict
```

The command builds in a temporary sibling directory, validates the candidate, and atomically renames it to `output`. A failed build does not leave a complete-looking formal output.

Do not use `build` to update an existing `output`; use `release` instead.

### `validate`

`validate` reads the version from `output/cia.all.json`, rebuilds the same version in a temporary directory, and compares every generated file with the formal output. It reports: missing files, orphan files, content mismatches and internal structural or numerical errors. It does not modify `output`.

```text
cia-pipeline validate \
  --input input \
  --metadata metadata \
  --output output \
  --examples examples \
  --strict
```

### `release`

`release` validates and verifies a reproducible build, backs up the current output, atomically publishes the new version, and automatically restores the previous version if post-release validation fails. Backups are named from the version stored in the old `output/cia.all.json`:

```text
releases/backups/20260817
releases/backups/20260817-1
releases/backups/20260817-2
```
The numeric suffix prevents an existing backup from being overwritten.

## Inputs and metadata
Raw source files are never modified. Every accepted HITRAN file under `input/main` or `input/sup` must have an explicit entry in `metadata/dataset_map.json`; missing metadata is reported and never inferred.

`metadata/species.json` defines the accepted formulas, slugs, and `cas_registry_number` values. 
`metadata/sources.json` supplies verified bibliographic metadata and HITRAN raw-header reference mappings. Ordinary records whose `repository` is exactly `HITRAN CIA` use a positive integer `ref` and participate in the numeric raw-header reference index. Shared HITRAN provenance records and non-HITRAN bibliography records use `ref: null`.
`metadata/dataset_map.json` defines canonical collision pairs, collection paths, active-species semantics, dataset mappings, and variants.

Canonical non-HITRAN data is discovered at:
```text
input/extra/<dataset-id>/*.json
```
Each JSON descriptor references a local long-format CSV through a safe relative `data_file` path and explicitly defines the source-native column names and units. 

## Output structure

```text
output/
├── cia.all.json
└── <pair>/
    ├── <pair>.json
    ├── <dataset-metadata>.json
    └── <data-file>.cia
```

`cia.all.json` is the `CIA.master` entry point. It references every pair JSON.
Each pair JSON references its dataset metadata, and each dataset JSON references its .cia files. The master stores pointers and counts rather than duplicating scientific metadata.

Also output reports under:
```text
reports/release/<new-version>/

final_build_summary.json       candidate build statistics and warnings
final_validation.json          candidate internal validation
post_release_validation.json   validation of the published output
previous_output_manifest.json  path, size, and SHA-256 for old output files
release_manifest.json          release metadata, hashes, and backup location
```

## Grouping and recommendation
`input/main` records are recommended data. Each collision pair can have at most one recommended dataset. 
Main compilations use IDs such as `hitran<repository-version>-main`; a single-source main dataset can use its citation key.

Supplementary records are grouped by pair and source identity. Variants remain dataset or file metadata and do not automatically create separate datasets.
Pairs with supplementary data only use a null recommendation.

## Columns and uncertainty

Two-column files contain wavenumber and absorption quantities. Datasets with absolute uncertainty can use a three-column schema containing wavenumber, coefficient, and uncertainty.

## Naming

General form:
```
<pair> <dataset-id> <min-wavenumber> <max-wavenumber> <min-temperature> <max-temperature>.json
<pair> <dataset-id> <min-wavenumber> <max-wavenumber> <temperature>.cia
```

## Versions

At build start, one `BuildContext` captures the date in `Europe/London`. Versions use `YYYYMMDD`. 
The master, pair JSON, dataset JSON, pair dataset pointers, and master recommendation pointers all use that one value. 
Currently `dataset_version = build_version`; no registry or incremental dataset versioning is implemented. 
HITRAN repository versions such as 2011 or 2024 remain separate.

## Adding data

For a HITRAN file:
1. Add the untouched file under `input/main` or `input/sup`.
2. Add its explicit mapping to `metadata/dataset_map.json`.
3. Ensure all species and reference records exist in the curated registries.
4. Run `inventory` and the test suite.
5. Run a strict build into a new empty output directory, or use `release` to update the formal output.

For a non-HITRAN source:
1. Archive the original files under `source_data/non_hitran/<dataset-id>`.
2. Add its explicit mapping to `metadata/dataset_map.json`.
3. Add a source-specific converter under `src/cia_pipeline`.
4. Generate canonical CSV/JSON files under `input/extra/<dataset-id>`.
5. Ensure all species and verified bibliography records exist; non-HITRAN records use `ref: null`.
6. Define the source-native columns and units.
7. Run the relevant converter and tests, then publish the data with build or release.
