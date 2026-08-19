import json
from pathlib import Path

from cia_pipeline.writers import DatasetGroup, dataset_source_keys, group_blocks
from cia_pipeline.grouping import assign_proposed_groups
from cia_pipeline.metadata import load_metadata
from cia_pipeline.models import CIABlock


def write_registries(root: Path) -> None:
    (root / "species.json").write_text(
        json.dumps(
            {
                "air": {
                    "formula": "Air",
                    "slug": "air",
                    "cas_registry_number": None,
                    "cas_registry_number_status": "not_applicable_mixture",
                },
                "h": {"formula": "H", "slug": "h", "cas_registry_number": "x"},
                "he": {"formula": "He", "slug": "he", "cas_registry_number": "y"},
            }
        )
    )
    base = {
        "repository": "HITRAN CIA",
        "authors": ["A"],
        "title": "T",
        "year": 2020,
        "doi": None,
        "source_url": "https://example.invalid/source",
        "verified": True,
        "ref": 53,
    }
    (root / "sources.json").write_text(
        json.dumps(
            {
                "paper-a": {**base, "citation_key": "paper-a"},
                "paper-b": {**base, "citation_key": "paper-b"},
            }
        )
    )
    (root / "dataset_map.json").write_text(
        json.dumps(
            {
                "files": {
                    "main/He-H_2011.cia.txt": {
                        "pair": "H-He",
                        "active_species_status": "no_unique_active_species",
                        "active_species": None,
                        "collider": None,
                        "components": ["h", "he"],
                    }
                }
            }
        )
    )


def test_reference_maps_to_multiple_papers_and_air_null_cas(tmp_path: Path) -> None:
    write_registries(tmp_path)
    registry = load_metadata(tmp_path, strict=True)
    assert registry.references[53] == ("paper-a", "paper-b")
    assert not registry.problems


def test_h_he_no_unique_active_species(tmp_path: Path) -> None:
    write_registries(tmp_path)
    entry = load_metadata(tmp_path).dataset_files["main/He-H_2011.cia.txt"]
    assert entry.pair == "H-He"
    assert entry.active_species is None
    assert entry.collider is None
    assert entry.components == ("h", "he")


def make_block(path: str, variant: str) -> CIABlock:
    return CIABlock(
        raw_relative_path=path,
        source_path=Path(path),
        header_line_number=1,
        header_pair="H2-CH4",
        min_wavenumber=0,
        max_wavenumber=1,
        declared_npoints=0,
        temperature=100,
        max_coefficient=0,
        resolution=None,
        resolution_raw="-.999",
        description=None,
        reference_number=16,
        points=[],
        collection="main",
        repository_version="2011",
        normalized_pair="H2-CH4",
        variant=variant,
        citation_keys=("borysow1986",),
    )


def test_h2_ch4_main_variants_group_as_compilation() -> None:
    blocks = [
        make_block("main/H2-CH4_eq_2011.cia.txt", "equilibrium"),
        make_block("main/H2-CH4_norm_2011.cia.txt", "normal"),
    ]
    assert assign_proposed_groups(blocks) == []
    assert {block.proposed_dataset_id for block in blocks} == {"hitran2011-main"}
    assert {block.variant for block in blocks} == {"equilibrium", "normal"}


def test_supplementary_variants_with_same_citation_merge() -> None:
    blocks = [
        make_block("sup/H2-H2_eq_2018.cia.txt", "equilibrium"),
        make_block("sup/H2-H2_norm_2018.cia.txt", "normal"),
    ]
    for block in blocks:
        block.collection = "sup"
        block.normalized_pair = "H2-H2"
        block.citation_keys = ("fletcher2018",)
    groups = group_blocks(blocks)
    assert len(groups) == 1
    assert groups[0].dataset_id == "fletcher2018"
    assert {block.variant for block in groups[0].blocks} == {
        "equilibrium",
        "normal",
    }


def test_hitran_groups_append_shared_sources_after_original_papers() -> None:
    block = make_block("sup/example.cia.txt", "alternate")
    block.collection = "sup"
    block.citation_keys = ("terragni_hitran", "paper-b", "paper-a")
    group = DatasetGroup("H2-He", "example", "sup", False, [block])
    assert dataset_source_keys(group) == [
        "paper-a",
        "paper-b",
        "hitran_cia_repository",
        "terragni_hitran",
        "gordon2026_hitran",
    ]


def test_extra_group_does_not_gain_shared_hitran_sources() -> None:
    block = make_block("extra/example/data.csv", "alternate")
    block.collection = "extra"
    block.input_kind = "extradata"
    block.citation_keys = ("paper-a",)
    group = DatasetGroup("H2-He", "example", "extra", False, [block])
    assert dataset_source_keys(group) == ["paper-a"]
