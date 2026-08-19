import json
from datetime import date
from pathlib import Path

import pytest

from cia_pipeline.extradata import (
    ExtradataError,
    detect_spectral_regions,
    discover_extra,
    load_extradata_descriptor,
    validate_spectral_regions,
)
from cia_pipeline.models import DataPoint, DatasetMapEntry, MetadataRegistry


def registry() -> MetadataRegistry:
    return MetadataRegistry(
        species={"x": {"formula": "X", "slug": "x", "cas_registry_number": "1-2-3"}},
        sources={
            "generic2026": {
                "repository": "Example supplementary material",
                "citation_key": "generic2026", "verified": True, "ref": None
            }
        },
        dataset_files={
            "extra/generic2026/data.csv": DatasetMapEntry(
                raw_relative_path="extra/generic2026/data.csv",
                pair="X-X",
                active_species_status="unique",
                active_species="x",
                collider="x",
                components=("x", "x"),
                variant=None,
            )
        }, references={}, problems=[],
    )


def descriptor(dataset_id="generic2026", pair="X-X"):
    return {
        "collision_pair": {
            "formula": pair, "slug": pair.lower(), "active_species_status": "unique",
            "active_species": "x", "collider": "x",
            "components": [
                {"formula": "X", "slug": "x", "cas_registry_number": "1-2-3"},
                {"formula": "X", "slug": "x", "cas_registry_number": "1-2-3"},
            ],
        },
        "dataset": {
            "id": dataset_id, "recommendation_status": "supplementary",
            "collision_induced_absorption_xsecs": {
                "min_temperature": 100, "max_temperature": 200,
                "min_wavenumber": 10, "max_wavenumber": 40,
                "nominal_wavenumber_step": 10,
                "units": {"temperature": "K", "wavenumber": "cm^-1"},
                "column_schemas": {
                    "native": [
                        {"name": "wavenumber", "units": "cm^-1"},
                        {"name": "signal", "units": "u"},
                        {"name": "uncertainty", "units": "u", "uncertainty_type": "absolute", "applies_to": "signal"},
                    ]
                },
                "default_column_schema": "native", "data_file": "data.csv",
            },
            "sources": ["generic2026"],
        },
    }


def make_input(tmp_path: Path):
    root = tmp_path / "input"
    folder = root / "extra/generic2026"
    folder.mkdir(parents=True)
    path = folder / "X-X.json"
    path.write_text(json.dumps(descriptor()))
    (folder / "data.csv").write_text(
        "temperature,wavenumber,signal,uncertainty\n"
        "100,10,1.00E-2,1.0E-3\n100,20,2.00E-2,2.0E-3\n"
        "200,10,3.00E-2,3.0E-3\n200,40,4.00E-2,4.0E-3\n"
    )
    provenance = tmp_path / "source_data/non_hitran/generic2026"
    provenance.mkdir(parents=True)
    (provenance / "source.dat").write_text("source")
    return root, path


def mutate(path: Path, callback):
    value = json.loads(path.read_text())
    callback(value)
    path.write_text(json.dumps(value))


def test_discovery_generic_dataset_and_pair(tmp_path: Path) -> None:
    root, path = make_input(tmp_path)
    assert discover_extra(root) == [path]
    blocks = load_extradata_descriptor(path, root, registry())
    assert {block.explicit_dataset_id for block in blocks} == {"generic2026"}
    assert {block.normalized_pair for block in blocks} == {"X-X"}


def test_split_groups_excludes_temperature_and_preserves_tokens(tmp_path: Path) -> None:
    root, path = make_input(tmp_path)
    blocks = load_extradata_descriptor(path, root, registry())
    assert [block.temperature for block in blocks] == [100, 200]
    assert blocks[0].points[0].raw_line == "10 1.00E-2 1.0E-3"
    assert all(len(point.raw_line.split()) == 3 for block in blocks for point in block.points)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda root, path: (path.parent / "data.csv").unlink(), "does not exist"),
        (lambda root, path: mutate(path, lambda value: value["dataset"]["collision_induced_absorption_xsecs"].update(data_file="../data.csv")), "unsafe data_file"),
        (lambda root, path: (path.parent / "data.csv").write_text("bad,row\n1\n"), "header"),
        (lambda root, path: (path.parent / "data.csv").write_text("wavenumber,signal,uncertainty\n10,1,0\n"), "header"),
        (lambda root, path: (path.parent / "data.csv").write_text("temperature,signal,uncertainty\n100,1,0\n"), "header"),
        (lambda root, path: (path.parent / "data.csv").write_text("temperature,wavenumber,uncertainty\n100,10,0\n"), "header"),
        (lambda root, path: (path.parent / "data.csv").write_text("temperature,wavenumber,signal,uncertainty,extra\n100,10,1,0,x\n"), "header"),
        (lambda root, path: (path.parent / "data.csv").write_text("temperature,wavenumber,signal,uncertainty\n100,10,1,0\n100,10,1,0\n"), "duplicate"),
        (lambda root, path: (path.parent / "data.csv").write_text("temperature,wavenumber,signal,uncertainty\n200,10,1,0\n100,20,1,0\n"), "not strictly sorted"),
        (lambda root, path: (path.parent / "data.csv").write_text("temperature,wavenumber,signal,uncertainty\n100,20,1,0\n100,10,1,0\n"), "not strictly sorted"),
        (lambda root, path: (path.parent / "data.csv").write_text("temperature,wavenumber,signal,uncertainty\n100,10,NaN,0\n"), "non-finite"),
        (lambda root, path: (path.parent / "data.csv").write_text("temperature,wavenumber,signal,uncertainty\n100,10,1,-1\n"), "negative"),
    ],
)
def test_invalid_csv_and_paths_fail(tmp_path: Path, change, message: str) -> None:
    root, path = make_input(tmp_path)
    change(root, path)
    with pytest.raises(ExtradataError, match=message):
        load_extradata_descriptor(path, root, registry())


def test_source_resolution_requires_verified_null_ref(tmp_path: Path) -> None:
    root, path = make_input(tmp_path)
    bad = registry()
    bad.sources["generic2026"]["ref"] = 7
    with pytest.raises(ExtradataError, match="null ref"):
        load_extradata_descriptor(path, root, bad)


def test_dataset_map_mapping_is_required_and_consistent(tmp_path: Path) -> None:
    root, path = make_input(tmp_path)
    missing = registry()
    missing.dataset_files.clear()
    with pytest.raises(ExtradataError, match="not mapped"):
        load_extradata_descriptor(path, root, missing)
    wrong = registry()
    wrong.dataset_files["extra/generic2026/data.csv"] = DatasetMapEntry(
        "extra/generic2026/data.csv", "Wrong-X", "unique", "x", "x", ("x", "x"), None
    )
    with pytest.raises(ExtradataError, match="does not match dataset_map"):
        load_extradata_descriptor(path, root, wrong)


def test_explicit_repository_filters_collection_and_rejects_unsafe_files(tmp_path: Path) -> None:
    root, path = make_input(tmp_path)
    mutate(path, lambda value: value["dataset"].update(repository={
        "name": "Example supplementary material", "version": None,
        "collection": "generic2026", "original_files": ["source.dat"],
    }))
    assert load_extradata_descriptor(path, root, registry())[0].repository_record["original_files"] == ["source.dat"]
    mutate(path, lambda value: value["dataset"]["repository"].update(original_files=["../source.dat"]))
    with pytest.raises(ExtradataError, match="unsafe or missing"):
        load_extradata_descriptor(path, root, registry())


def test_spectral_gap_detection_and_validation() -> None:
    points = [
        DataPoint(str(value), "1", value, 1, raw_line=f"{value} 1")
        for value in (10, 20, 50, 60)
    ]
    regions = detect_spectral_regions(points, 10)
    assert regions == (
        {"min_wavenumber": 10, "max_wavenumber": 20, "npoints": 2},
        {"min_wavenumber": 50, "max_wavenumber": 60, "npoints": 2},
    )
    validate_spectral_regions(regions, points)


def test_region_validation_rejects_bad_coverage() -> None:
    points = [DataPoint("10", "1", 10, 1), DataPoint("20", "1", 20, 1)]
    with pytest.raises(ExtradataError, match="point counts"):
        validate_spectral_regions(({"min_wavenumber": 10, "max_wavenumber": 20, "npoints": 1},), points)


def test_repeated_load_is_deterministic(tmp_path: Path) -> None:
    root, path = make_input(tmp_path)
    first = [[point.raw_line for point in block.points] for block in load_extradata_descriptor(path, root, registry())]
    second = [[point.raw_line for point in block.points] for block in load_extradata_descriptor(path, root, registry())]
    assert first == second


def test_repeated_extradata_output_naming_is_deterministic(tmp_path: Path) -> None:
    from cia_pipeline.naming import proposed_cia_filenames

    root, path = make_input(tmp_path)
    first = load_extradata_descriptor(path, root, registry())
    second = load_extradata_descriptor(path, root, registry())
    assert proposed_cia_filenames("X-X", "generic2026", first) == proposed_cia_filenames(
        "X-X", "generic2026", second
    )


def test_repeated_small_full_build_is_byte_deterministic(tmp_path: Path, monkeypatch) -> None:
    from cia_pipeline.build_context import BuildContext
    from cia_pipeline.writers import build_release_content
    import cia_pipeline.writers as writers

    raw, _ = make_input(tmp_path)
    metadata = tmp_path / "metadata"
    metadata.mkdir()
    (metadata / "species.json").write_text(json.dumps(registry().species))
    source_record = {
        "repository": "Example supplementary material",
        "citation_key": "generic2026",
        "authors": ["A. Author"], "title": "Title", "year": 2026,
        "doi": "10.1/example", "source_url": "https://doi.org/10.1/example",
        "verified": True, "ref": None,
    }
    (metadata / "sources.json").write_text(json.dumps({"generic2026": source_record}))
    (metadata / "dataset_map.json").write_text(
        json.dumps(
            {
                "files": {
                    "extra/generic2026/data.csv": {
                        "pair": "X-X",
                        "active_species_status": "unique",
                        "active_species": "x",
                        "collider": "x",
                        "components": ["x", "x"],
                    }
                }
            }
        )
    )
    monkeypatch.setattr(writers, "validate_golden", lambda *args: {"passed": True})
    context = BuildContext.from_date(date(2026, 8, 3))
    roots = []
    for label in ("a", "b"):
        output = tmp_path / f"output-{label}"
        reports = tmp_path / f"reports-{label}"
        summary, validation, _ = build_release_content(
            raw, metadata, output, reports, context
        )
        assert summary["strict_build_ready"] and validation["summary"]["errors"] == 0
        roots.append(output)
    def snapshot(root: Path):
        return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    assert snapshot(roots[0]) == snapshot(roots[1])
