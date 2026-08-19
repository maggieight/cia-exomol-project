"""read all collision-pair-level JSON and load master JSON file cia.all.json"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .build_context import BuildContext

MASTER_FILENAME = "cia.all.json"
MASTER_ID = "CIA.master"


@dataclass(frozen=True)
class MasterRecommendedDataset:
    dataset: str
    dataset_version: str
    metadata_file: str


@dataclass(frozen=True)
class MasterPairEntry:
    formula: str
    slug: str
    dataset_count: int
    pair_file: str
    recommended_dataset: MasterRecommendedDataset | None


@dataclass(frozen=True)
class MasterDocument:
    id: str
    version: str
    pair_count: int
    dataset_count: int
    recommended_dataset_count: int
    supplementary_dataset_count: int
    pairs: tuple[MasterPairEntry, ...]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def pair_json_paths(output_root: Path) -> list[Path]:
    return sorted(
        path
        for path in output_root.glob("*/*.json")
        if path.name == f"{path.parent.name}.json"
    )


def generate_master(output_root: Path, context: BuildContext) -> MasterDocument:
    entries: list[MasterPairEntry] = []
    total_datasets = 0
    supplementary_datasets = 0
    for pair_path in pair_json_paths(output_root):
        pair_json = json.loads(pair_path.read_text(encoding="utf-8"))
        collision_pair = pair_json["collision_pair"]
        recommended_id = pair_json["recommended_dataset"]
        datasets = pair_json["datasets"]
        total_datasets += len(datasets)
        for dataset_link in datasets:
            dataset_path = pair_path.parent / dataset_link["metadata_file"]
            dataset_json = json.loads(dataset_path.read_text(encoding="utf-8"))
            dataset = dataset_json["dataset"]
            if dataset["id"] != dataset_link["dataset_id"]:
                raise ValueError(f"{dataset_path}: dataset.id mismatch")
            if dataset["version"] != dataset_link["dataset_version"]:
                raise ValueError(f"{dataset_path}: dataset version mismatch")
            if dataset_link["dataset_id"] != recommended_id:
                supplementary_datasets += 1
        recommended = None
        if recommended_id is not None:
            matches = [
                item
                for item in pair_json["datasets"]
                if item["dataset_id"] == recommended_id
            ]
            if len(matches) != 1:
                raise ValueError(
                    f"{pair_path}: recommended_dataset {recommended_id!r} "
                    f"must match exactly one datasets[] entry"
                )
            recommended = MasterRecommendedDataset(
                dataset=recommended_id,
                dataset_version=matches[0]["dataset_version"],
                metadata_file=PurePosixPath(
                    pair_path.parent.name, matches[0]["metadata_file"]
                ).as_posix(),
            )
        entries.append(
            MasterPairEntry(
                formula=collision_pair["formula"],
                slug=collision_pair["slug"],
                dataset_count=len(datasets),
                pair_file=PurePosixPath(
                    pair_path.parent.name, pair_path.name
                ).as_posix(),
                recommended_dataset=recommended,
            )
        )
    entries.sort(key=lambda item: item.formula)
    recommended_count = sum(
        item.recommended_dataset is not None for item in entries
    )
    return MasterDocument(
        id=MASTER_ID,
        version=context.version,
        pair_count=len(entries),
        dataset_count=total_datasets,
        recommended_dataset_count=recommended_count,
        supplementary_dataset_count=supplementary_datasets,
        pairs=tuple(entries),
    )


def write_master(
    output_root: Path, context: BuildContext, payload: MasterDocument | None = None
) -> Path:
    master = payload or generate_master(output_root, context)
    destination = output_root / MASTER_FILENAME
    destination.write_text(
        json.dumps(master.as_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return destination


def load_master(output_root: Path) -> dict[str, Any]:
    return json.loads(
        (output_root / MASTER_FILENAME).read_text(encoding="utf-8")
    )
