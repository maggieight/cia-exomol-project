import json
from datetime import date
from pathlib import Path

import pytest

from cia_pipeline.build_context import BuildContext
from cia_pipeline.master import generate_master, write_master
from cia_pipeline.master_validation import validate_master


def dump(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n")


def create_tree(root: Path) -> BuildContext:
    context = BuildContext.from_date(date(2026, 7, 30))
    for index in range(25):
        formula = f"Pair{index:02d}"
        slug = formula.lower()
        pair_dir = root / formula
        pair_dir.mkdir()
        dataset_specs = [
            (
                f"source{index:02d}",
                "sup" if index < 2 else "main",
            )
        ]
        if index == 2:
            dataset_specs.extend(
                (f"supplementary{extra:02d}", "sup") for extra in range(18)
            )
        links = []
        for dataset_id, collection in dataset_specs:
            cia_name = f"{formula}_{dataset_id}_0_1_100.cia"
            metadata_name = f"{formula}_{dataset_id}_0_1_100_100.json"
            (pair_dir / cia_name).write_text(" 0 1E-47\n 1 2E-47\n")
            dump(
                pair_dir / metadata_name,
                {
                    "collision_pair": {"formula": formula, "slug": slug},
                    "dataset": {
                        "id": dataset_id,
                        "version": context.version,
                        "repository": {"collection": collection},
                        "collision_induced_absorption_xsecs": {
                            "files": [{"filename": cia_name}]
                        },
                    },
                },
            )
            links.append(
                {
                    "dataset_id": dataset_id,
                    "dataset_version": context.version,
                    "metadata_file": metadata_name,
                }
            )
        recommended = dataset_specs[0][0] if index >= 2 else None
        dump(
            pair_dir / f"{formula}.json",
            {
                "collision_pair": {"formula": formula, "slug": slug},
                "version": context.version,
                "recommended_dataset": recommended,
                "datasets": links,
            },
        )
    write_master(root, context)
    return context


def mutate_json(path: Path, callback) -> None:
    value = json.loads(path.read_text())
    callback(value)
    dump(path, value)


def test_generated_master_is_valid_and_deterministic(tmp_path: Path) -> None:
    context = create_tree(tmp_path)
    first = (tmp_path / "cia.all.json").read_bytes()
    write_master(tmp_path, context, generate_master(tmp_path, context))
    second = (tmp_path / "cia.all.json").read_bytes()
    assert first == second
    report = validate_master(tmp_path, context)
    assert report["valid"]
    assert report["pair_count"] == 25


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (
            lambda root: (root / "Pair00" / "Pair00.json").unlink(),
            "pair_file does not exist",
        ),
        (
            lambda root: (root / "Pair00" / "Pair00_source00_0_1_100_100.json").unlink(),
            "dataset metadata is missing",
        ),
        (
            lambda root: mutate_json(
                root / "Pair00" / "Pair00.json",
                lambda value: value["collision_pair"].update(formula="Wrong"),
            ),
            "pair formula mismatch",
        ),
        (
            lambda root: mutate_json(
                root / "Pair00" / "Pair00.json",
                lambda value: value["collision_pair"].update(slug="wrong"),
            ),
            "pair slug mismatch",
        ),
        (
            lambda root: mutate_json(
                root / "Pair00" / "Pair00_source00_0_1_100_100.json",
                lambda value: value["dataset"].update(id="wrong"),
            ),
            "dataset.id linkage mismatch",
        ),
        (
            lambda root: mutate_json(
                root / "Pair02" / "Pair02_source02_0_1_100_100.json",
                lambda value: value["dataset"].update(version="20260731"),
            ),
            "dataset version mismatch",
        ),
        (
            lambda root: mutate_json(
                root / "cia.all.json",
                lambda value: value["pairs"].append(value["pairs"][0]),
            ),
            "duplicate collision pairs",
        ),
        (
            lambda root: mutate_json(
                root / "cia.all.json",
                lambda value: value["pairs"][0].update(pair_file="../unsafe.json"),
            ),
            "unsafe pair_file",
        ),
        (
            lambda root: mutate_json(
                root / "cia.all.json",
                lambda value: value.update(pairs=list(reversed(value["pairs"]))),
            ),
            "not sorted",
        ),
        (
            lambda root: mutate_json(
                root / "cia.all.json", lambda value: value["pairs"].pop()
            ),
            "master pair_count does not equal len(pairs)",
        ),
    ],
)
def test_master_validation_failures(
    tmp_path: Path, mutation, expected: str
) -> None:
    context = create_tree(tmp_path)
    mutation(tmp_path)
    report = validate_master(tmp_path, context)
    assert not report["valid"]
    assert any(expected in item["problem"] for item in report["errors"])


@pytest.mark.parametrize(
    ("relative_path", "expected"),
    [
        ("Orphan/Orphan.json", "orphan pair JSON"),
        ("Pair00/orphan.json", "orphan dataset JSON"),
        ("Pair00/orphan.cia", "orphan CIA"),
    ],
)
def test_orphan_files_fail(
    tmp_path: Path, relative_path: str, expected: str
) -> None:
    context = create_tree(tmp_path)
    path = tmp_path / relative_path
    path.parent.mkdir(exist_ok=True)
    if path.suffix == ".json":
        dump(
            path,
            {
                "collision_pair": {
                    "formula": path.parent.name,
                    "slug": path.parent.name.lower(),
                },
                "version": context.version,
                "recommended_dataset": None,
                "datasets": [],
            },
        )
    else:
        path.write_text("0 0\n")
    report = validate_master(tmp_path, context)
    assert not report["valid"]
    assert any(expected in item["problem"] for item in report["errors"])
