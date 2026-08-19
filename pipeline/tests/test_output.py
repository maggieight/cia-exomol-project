import csv
import json
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from cia_pipeline.build_context import BuildContext
from cia_pipeline.extradata_validation import validate_extra_collection, validate_ptashnik
from cia_pipeline.master_validation import validate_master
from cia_pipeline.writers import validate_golden

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"
INPUT = ROOT / "input"


def read_json(relative: str):
    return json.loads((ROOT / relative).read_text())


def test_current_output_summary_and_validation() -> None:
    master = read_json("output/cia.all.json")
    context = BuildContext.from_date(
        datetime.strptime(master["version"], "%Y%m%d").date()
    )
    validation = validate_master(ROOT / "output", context)
    assert master["pair_count"] == 29
    assert master["dataset_count"] == 50
    assert (master["recommended_dataset_count"], master["supplementary_dataset_count"]) == (23, 27)
    null_pairs = [
        item["formula"] for item in master["pairs"]
        if item["recommended_dataset"] is None
    ]
    assert null_pairs == ["Ar-He", "Ar-Ne", "CH4-Ar", "CH4-CH4", "H2O-H2O", "He-Ne"]
    assert len(list((ROOT / "output").glob("*/*.cia"))) == 1339
    assert validation["valid"] is True
    assert validation["errors"] == []
    assert validation["orphan_pair_json"] == []
    assert validation["orphan_dataset_json"] == []
    assert validation["orphan_cia_files"] == []


def test_sup_only_pairs_have_null_recommendation() -> None:
    for pair in ("CH4-Ar", "CH4-CH4"):
        pair_json = read_json(f"output/{pair}/{pair}.json")
        assert pair_json["recommended_dataset"] is None


def test_h2_ch4_variants_share_recommended_dataset() -> None:
    pair_json = read_json("output/H2-CH4/H2-CH4.json")
    assert pair_json["recommended_dataset"] == "hitran2011-main"
    metadata = read_json(
        "output/H2-CH4/"
        + pair_json["datasets"][0]["metadata_file"]
    )
    assert metadata["dataset"]["variants"] == ["equilibrium", "normal"]
    assert {
        entry["variant"]
        for entry in metadata["dataset"]["collision_induced_absorption_xsecs"]["files"]
    } == {"equilibrium", "normal"}


def test_ref53_keeps_both_sources() -> None:
    pair_json = read_json("output/O2-O2/O2-O2.json")
    main = next(
        entry
        for entry in pair_json["datasets"]
        if entry["dataset_id"] == "hitran2024-main"
    )
    metadata = read_json(f"output/O2-O2/{main['metadata_file']}")
    ref53 = [
        entry
        for entry in metadata["dataset"]["collision_induced_absorption_xsecs"]["files"]
        if entry["reference_number"] == 53
    ]
    assert ref53
    assert all(
        entry["citation_keys"] == ["kassi2021", "mondelain2018"]
        for entry in ref53
    )
    source_keys = {
        source["citation_key"] for source in metadata["dataset"]["sources"]
    }
    assert {"kassi2021", "mondelain2018"} <= source_keys


def test_all_hitran_datasets_include_shared_sources_and_extra_does_not() -> None:
    shared = ["hitran_cia_repository", "terragni_hitran", "gordon2026_hitran"]
    for pair_entry in read_json("output/cia.all.json")["pairs"]:
        pair = read_json(f"output/{pair_entry['pair_file']}")
        for dataset_entry in pair["datasets"]:
            metadata = read_json(
                f"output/{pair_entry['formula']}/{dataset_entry['metadata_file']}"
            )["dataset"]
            keys = [source["citation_key"] for source in metadata["sources"]]
            assert len(keys) == len(set(keys))
            collection = metadata["repository"]["collection"]
            if collection in {"main", "sup"}:
                assert keys[-3:] == shared
            else:
                assert not set(shared).intersection(keys)


def test_ch4_ar_preserves_original_source_before_shared_hitran_sources() -> None:
    pair = read_json("output/CH4-Ar/CH4-Ar.json")
    entry = next(item for item in pair["datasets"] if item["dataset_id"] == "samuelson1997")
    metadata = read_json(f"output/CH4-Ar/{entry['metadata_file']}")
    assert [source["citation_key"] for source in metadata["dataset"]["sources"]] == [
        "samuelson1997",
        "hitran_cia_repository",
        "terragni_hitran",
        "gordon2026_hitran",
    ]


def test_golden_full_comparison_passed() -> None:
    golden = validate_golden(ROOT / "output", ROOT / "examples")
    assert golden["passed"]
    assert golden["exact_text_match"]
    assert golden["generated_rows"] == 16956


def test_no_legacy_cas_number_field() -> None:
    for path in (ROOT / "output").rglob("*.json"):
        assert '"cas_number"' not in path.read_text()


def test_n2_n2_three_column_files_and_nested_json() -> None:
    pair_json = read_json("output/N2-N2/N2-N2.json")
    main = next(
        entry
        for entry in pair_json["datasets"]
        if entry["dataset_id"] == "hitran2021-main"
    )
    metadata = read_json(f"output/N2-N2/{main['metadata_file']}")
    xsecs = metadata["dataset"]["collision_induced_absorption_xsecs"]
    assert xsecs["default_column_schema"] == "standard"
    assert set(xsecs["column_schemas"]) == {
        "standard",
        "with_absolute_uncertainty",
    }
    files = xsecs["files"]
    three_column = [
        entry
        for entry in files
        if entry.get("column_schema") == "with_absolute_uncertainty"
    ]
    two_column = [entry for entry in files if "column_schema" not in entry]
    assert len(three_column) == 4
    assert two_column
    for entry in three_column:
        rows = (
            ROOT / "output" / "N2-N2" / entry["filename"]
        ).read_text().splitlines()
        assert rows
        assert all(len(row.split()) == 3 for row in rows)
    assert all("data_columns" not in entry for entry in files)


def test_standard_only_dataset_defines_no_unused_uncertainty_schema() -> None:
    pair_json = read_json("output/CO2-CH4/CO2-CH4.json")
    metadata_entry = next(
        entry
        for entry in pair_json["datasets"]
        if entry["dataset_id"] == "fakhardji2022"
    )
    metadata = read_json(
        f"output/CO2-CH4/{metadata_entry['metadata_file']}"
    )
    xsecs = metadata["dataset"]["collision_induced_absorption_xsecs"]
    assert list(xsecs["column_schemas"]) == ["standard"]
    assert xsecs["default_column_schema"] == "standard"
    assert all("column_schema" not in entry for entry in xsecs["files"])


def test_ptashnik_pair_dataset_and_six_files() -> None:
    pair = read_json("output/H2O-H2O/H2O-H2O.json")
    assert pair["recommended_dataset"] is None
    assert len(pair["datasets"]) == 1
    link = pair["datasets"][0]
    assert link["dataset_id"] == "ptashnik2011"
    dataset = read_json(f"output/H2O-H2O/{link['metadata_file']}")["dataset"]
    assert "recommendation_status" not in dataset
    assert dataset["repository"] == {
        "name": "JGR supplementary material",
        "version": None,
        "collection": "ptashnik2011",
        "original_files": ["water-data.doc"],
    }
    xsecs = dataset["collision_induced_absorption_xsecs"]
    assert xsecs["spectral_averaging_width"] == 20
    assert xsecs["nominal_wavenumber_step"] == 10
    assert [entry["npoints"] for entry in xsecs["files"]] == [295, 381, 527, 516, 543, 509]
    assert len(xsecs["files"]) == 6
    assert all(entry["wavenumber_resolution"] is None for entry in xsecs["files"])
    assert all("reference_number" not in entry for entry in xsecs["files"])


def test_ptashnik_output_matches_canonical_input() -> None:
    validation = validate_ptashnik(OUTPUT, INPUT)
    assert validation["file_count"] == 6
    assert validation["matched_rows"] == 2771
    assert validation["token_mismatches"] == 0


def test_chandran_output_matches_canonical_input() -> None:
    validation = validate_extra_collection(OUTPUT, INPUT, "chandran2025")
    assert validation["descriptor_count"] == 3
    assert validation["file_count"] == 11
    assert validation["matched_rows"] == 7200
    assert validation["token_mismatches"] == 0
    for pair, count in (("Ar-He", 4), ("Ar-Ne", 4), ("He-Ne", 3)):
        pair_json = read_json(f"output/{pair}/{pair}.json")
        assert pair_json["recommended_dataset"] is None
        assert pair_json["datasets"][0]["dataset_id"] == "chandran2025"
        metadata = read_json(
            f"output/{pair}/{pair_json['datasets'][0]['metadata_file']}"
        )["dataset"]
        assert len(metadata["collision_induced_absorption_xsecs"]["files"]) == count
        assert metadata["repository"]["name"] == "JQSRT supplementary material"
        assert all(
            "spectral_regions" not in entry
            for entry in metadata["collision_induced_absorption_xsecs"]["files"]
        )


def test_spectral_regions_are_only_written_for_real_gaps() -> None:
    pair = read_json("output/H2O-H2O/H2O-H2O.json")
    metadata = read_json(
        f"output/H2O-H2O/{pair['datasets'][0]['metadata_file']}"
    )["dataset"]
    files = metadata["collision_induced_absorption_xsecs"]["files"]
    assert any("spectral_regions" in entry for entry in files)
    assert all(
        len(entry["spectral_regions"]) > 1
        for entry in files if "spectral_regions" in entry
    )


def test_dong_and_vitali_join_existing_pairs_without_changing_recommendation() -> None:
    expectations = {
        "O2-O2": ("dong2026", "hitran2024-main", 1),
        "CO2-H2": ("vitali2026", "turbet2020", 6),
    }
    for pair_name, (dataset_id, recommended, file_count) in expectations.items():
        pair = read_json(f"output/{pair_name}/{pair_name}.json")
        assert pair["recommended_dataset"] == recommended
        link = next(item for item in pair["datasets"] if item["dataset_id"] == dataset_id)
        dataset = read_json(f"output/{pair_name}/{link['metadata_file']}")["dataset"]
        assert len(dataset["collision_induced_absorption_xsecs"]["files"]) == file_count


def test_dong_vitali_output_matches_canonical_input() -> None:
    dong = validate_extra_collection(OUTPUT, INPUT, "dong2026")
    vitali = validate_extra_collection(OUTPUT, INPUT, "vitali2026")
    assert (dong["file_count"], dong["matched_rows"], dong["token_mismatches"]) == (1, 70001, 0)
    assert (vitali["file_count"], vitali["matched_rows"], vitali["token_mismatches"]) == (6, 7583, 0)


def test_finenko_single_dataset_two_variants_and_recommendation() -> None:
    pair = read_json("output/CO2-CH4/CO2-CH4.json")
    assert pair["recommended_dataset"] == "fakhardji2022"
    links = [item for item in pair["datasets"] if item["dataset_id"] == "finenko2026"]
    assert len(links) == 1
    dataset = read_json(f"output/CO2-CH4/{links[0]['metadata_file']}")["dataset"]
    assert dataset["variants"] == ["d3-schofield", "d4a-frommhold"]
    files = dataset["collision_induced_absorption_xsecs"]["files"]
    assert len(files) == 68
    assert sum(item["variant"] == "d3-schofield" for item in files) == 34
    assert sum(item["variant"] == "d4a-frommhold" for item in files) == 34
    assert len({item["filename"] for item in files}) == 68
    assert all(item["variant"] in item["filename"] for item in files)


def test_finenko_output_matches_canonical_input() -> None:
    validation = validate_extra_collection(OUTPUT, INPUT, "finenko2026")
    assert validation["descriptor_count"] == 1
    assert validation["file_count"] == 68
    assert validation["token_mismatches"] == 0
    assert validation["numeric_mismatches"] == 0


def test_ptashnik_canonical_csv_and_json() -> None:
    csv_path = INPUT / "extra/ptashnik2011/H2O-H2O.csv"
    json_path = INPUT / "extra/ptashnik2011/H2O-H2O.json"
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8", newline="")))
    assert len(rows) == 2771
    assert list(rows[0]) == [
        "temperature", "wavenumber", "self_continuum_cross_section", "uncertainty"
    ]
    assert "--" not in csv_path.read_text(encoding="utf-8")
    counts = Counter(int(row["temperature"]) for row in rows)
    assert counts == {293: 295, 350: 381, 374: 527, 402: 516, 431: 543, 472: 509}
    assert all(
        Decimal(row[field]).is_finite() and Decimal(row[field]) >= 0
        for row in rows
        for field in ("self_continuum_cross_section", "uncertainty")
    )
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    xsecs = payload["dataset"]["collision_induced_absorption_xsecs"]
    assert payload["dataset"]["sources"] == ["ptashnik2011"]
    assert payload["dataset"]["recommendation_status"] == "supplementary"
    assert payload["collision_pair"]["active_species_status"] == "no_unique_active_species"
    assert payload["collision_pair"]["active_species"] is None
    assert payload["collision_pair"]["collider"] is None
    assert (xsecs["min_temperature"], xsecs["max_temperature"]) == (293, 472)
    assert (xsecs["min_wavenumber"], xsecs["max_wavenumber"]) == (2010, 9590)
    schema = xsecs["column_schemas"][xsecs["default_column_schema"]]
    assert schema[-1]["uncertainty_type"] == "absolute"


def test_ptashnik_source_resolution() -> None:
    sources = read_json("metadata/sources.json")
    assert sources["ptashnik2011"]["ref"] is None
    assert sources["anisman2022"]["ref"] is None
