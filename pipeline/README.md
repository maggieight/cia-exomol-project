# CIA Pipeline v1

This project converts HITRAN collision-induced absorption files into a deterministic ExoMol-style release. It parses raw blocks, resolves curate metadata, groups datasets, writes pair and dataset metadata, preserves numerical text, creates `cia.all.json`, and performs strict end-to-end validation.

## Layout

`input/main` contains recommended inputs and `input/sup` supplementary inputs.
`metadata` contains the only accepted species, source, and dataset mappings.
Unprocessed publisher supplements live under `source_data/non_hitran`; canonical
non-HITRAN inputs produced by dedicated preprocessors live under `input/extra`.
`examples` contains the CO2-CH4 golden files. Python code is under
`src/cia_pipeline`, tests under `tests`, generated scientific data under
`output`, and release records under `reports`.

The three build input collections are:

- `input/main`: recommended HITRAN CIA files;
- `input/sup`: supplementary HITRAN CIA files;
- `input/extra`: canonical, preprocessed non-HITRAN datasets, grouped by source ID.

`source_data/non_hitran` is provenance storage for unprocessed publisher
material and is never read by the main build.

## Installation

```bash
python -m pip install -e '.[test]'
```

The package has no runtime dependencies outside the Python standard library.

## Inputs and metadata

Raw files are never modified. `species.json` supplies formulas, slugs, and
`cas_registry_number`; `sources.json` supplies verified bibliography and HITRAN
reference mappings; `dataset_map.json` supplies canonical pairs, collection
paths, active-species semantics, and variants. Missing metadata is reported and
never inferred.

Non-HITRAN bibliography records use `ref: null`. Only records whose repository
is exactly `HITRAN CIA` participate in the numeric raw-header reference index.

## Ptashnik 2011 supplementary data

The dedicated `cia-pipeline convert ptashnik2011` preprocessor converts
the binary Word supplementary table through a temporary DOCX, reconstructs its
13 vertical token streams, and writes long-format CSV plus a canonical input
descriptor. It preserves scientific-notation tokens and absolute uncertainty;
it performs no unit conversion, interpolation, or CIA output generation.

```bash
cia-pipeline convert ptashnik2011 \
  --source source_data/non_hitran/ptashnik2011/water-data.doc \
  --output input/extra/ptashnik2011 \
  --metadata metadata
```

The main pipeline discovers `input/extra/*/*.json`. Each descriptor names a
long-format CSV through its safe relative `data_file`; the temperature column
forms output groups and is omitted from numerical CIA rows. Extradata does not
imitate a HITRAN header. Its source-native quantity names and units are defined
by the reusable column schema and may differ from HITRAN units. Ptashnik remains
`cm^2 molecule^-1 atm^-1`; it is not relabelled or converted to a HITRAN CIA
coefficient. Recommendation status is mandatory and explicit.

To add another extradata dataset, first create a reproducible source-specific
preprocessor, place its canonical CSV and pair-name JSON under
`input/extra/<dataset-id>/`, reference verified null-ref bibliography keys, and
describe the actual output columns and units. The formal build/release command
builds and strictly validates the candidate in a temporary directory, then
atomically publishes it as `output`; no persistent `staging` tree is required.

The Chandran & Karman 2025 preprocessor reads the exact archived `.data`
collection and creates three canonical pair descriptors in one source folder:

```bash
cia-pipeline convert chandran2025 \
  --source source_data/non_hitran/chandran2025 \
  --output input/extra/chandran2025 \
  --metadata metadata
```

Its source-native coefficient and absolute-uncertainty units are
`cm^-1 amagat^-2`; no conversion to HITRAN coefficient units is performed.

Dong 2026 and Vitali 2026 use the same canonical long-CSV descriptor path and
the same downstream extra loader. Their source-specific preprocessors are:

```bash
cia-pipeline convert dong2026 \
  --source source_data/non_hitran/dong2026 --output input/extra/dong2026 --metadata metadata
cia-pipeline convert vitali2026 \
  --source source_data/non_hitran/vitali2026 --output input/extra/vitali2026 --metadata metadata
```

Dong retains `cm^-1 amagat^-2` combined standard absolute uncertainty and a
0.01 cm^-1 nominal grid step without claiming an instrumental resolution.
Vitali retains `cm^5 molecule^-2` systematic absolute uncertainty, its stated
1 cm^-1 resolution, and all three discontinuous spectral regions. Zero values
are valid scientific data and are not treated as missing.

Finenko et al. 2026 supplies two HITRAN-style files as non-HITRAN provenance.
The dedicated preprocessor canonicalizes their original `CH4-CO2` label to the
existing `CO2-CH4` pair and writes one dataset with two file-level variants,
`d3-schofield` and `d4a-frommhold`:

```bash
cia-pipeline convert finenko2026 \
  --source source_data/non_hitran/finenko2026 \
  --output input/extra/finenko2026 --metadata metadata
```

The signed desymmetrized spectra are preserved verbatim, including small
negative tail values. Their standard HCIA/HITRAN two-column coefficient is
recorded in `cm^5 molecule^-2`; the header-provided 0.1 cm^-1 resolution is
retained and is not replaced by a calculated spacing.

## Grouping and recommendation

`main` data are recommended and each pair may have at most one recommended
dataset. Main compilations use `hitran<repository-version>-main`; a single-source
main dataset uses its citation key. H2-CH4 equilibrium and normal data form
`hitran2011-main`, retaining variants at file level. Supplementary blocks with
the same pair and citation set form one dataset; variants remain dataset/file
metadata and do not enter the supplementary dataset ID. CH4-Ar and CH4-CH4
remain supplementary-only with a null recommendation.

## Output hierarchy

`cia.all.json` is the `CIA.master` entry point. It reaches every pair JSON; each
pair JSON reaches all dataset JSON files; each dataset JSON reaches its physical
CIA files. The master contains pointers and counts, not duplicated scientific
metadata.

Pair JSON records the canonical collision pair, release version, recommended
dataset ID (or null), and every dataset pointer with `dataset_version`. Dataset
JSON records repository provenance, sources, variants, ranges, reusable column
schemas, and file entries.

## Columns and uncertainty

Two-column datasets use the reusable `standard` schema. Only datasets containing
three-column input define `with_absolute_uncertainty`; only affected files select
it. The third column is finite, non-negative absolute uncertainty in the same
units as the CIA coefficient. File-level duplicate column definitions and null
uncertainty placeholders are not used.

## Naming

Dataset JSON names use outward-rounded wavenumber and temperature ranges.
CIA names use outward-rounded wavenumber bounds and the actual temperature with
a normal decimal point. Collisions are resolved by variant, then exact maximum
and minimum (`_<exact-max>_r<exact-min>`), then reference and deterministic block
identity. Random hashes are never used.

## Versions

At build start, one `BuildContext` captures the date in `Europe/London`.
Versions use `YYYYMMDD`. The master, pair JSON, dataset JSON, pair dataset
pointers, and master recommendation pointers all use that one value. Currently
`dataset_version = build_version`; no registry or incremental dataset versioning
is implemented. HITRAN repository versions such as 2011 or 2024 remain separate.

## Commands

```bash
cia-pipeline inventory --input input --metadata metadata \
  --report reports/inventory.json --strict

cia-pipeline build --input input --metadata metadata --output output \
  --reports reports --examples examples --strict

cia-pipeline validate --input input --metadata metadata --output output \
  --examples examples --strict
```

Build refuses an existing output and non-empty reports directory. It writes to a
sibling staging directory, validates there, and only then atomically publishes
the output. A failed build never creates a complete-looking formal output.

## Validation

Validation checks metadata resolution, grouping, safe paths, counts, duplicate
IDs and names, master reachability, orphans, versions, effective column schemas,
point counts, monotonic and finite values, reference/variant/source attribution,
selected raw rows, complete three-column text, and the complete 16,956-line
CO2-CH4 golden comparison.

## Adding data

Add an untouched raw file under `input/main` or `input/sup`, add its explicit mapping
to `dataset_map.json`, and ensure all species and reference records already exist
in the curated registries. Run inventory, tests, then a strict build into a new
empty output directory.

## Tests and release reproduction

```bash
pytest
cia-pipeline build --input input --metadata metadata --output output \
  --reports reports --examples examples --strict
```

The release manifest records environment details and SHA-256 for every output
file. Independent dataset version management can be added in a future release
without changing these pointer fields.
