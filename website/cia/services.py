import json
from pathlib import Path

from django.conf import settings


class CIADataError(Exception):
    """The CIA data directory or one of its JSON files is unusable."""


class CIADataNotFound(CIADataError):
    """A requested CIA resource does not exist."""


def data_root():
    configured = getattr(settings, "CIA_DATA_DIR", None)
    if not configured:
        configured = Path(settings.DATA_DIR) / "cia"
    root = Path(configured).expanduser().resolve()
    if not root.is_dir():
        raise CIADataError("CIA data directory is not available")
    return root


def _safe_path(*parts):
    root = data_root()
    candidate = root.joinpath(*parts).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        raise CIADataNotFound("CIA file not found")
    return candidate


def _load_json(path):
    try:
        with path.open(encoding="utf-8") as stream:
            value = json.load(stream)
    except (OSError, ValueError, TypeError):
        raise CIADataError("CIA metadata could not be read")
    if not isinstance(value, dict):
        raise CIADataError("CIA metadata has an invalid structure")
    return value


def _pair_manifests():
    manifests = []
    for directory in sorted(data_root().iterdir()):
        if not directory.is_dir():
            continue
        candidates = sorted(directory.glob("*.json"))
        for path in candidates:
            value = _load_json(path)
            if "datasets" in value and "collision_pair" in value:
                manifests.append((path, value))
                break
    return manifests


def list_catalogue():
    species = {}
    unassigned_pairs = []
    for _, manifest in _pair_manifests():
        pair = manifest.get("collision_pair", {})
        pair_slug = pair.get("slug")
        if not pair_slug:
            continue
        summary = {
            "slug": pair_slug,
            "formula": pair.get("formula", pair_slug),
            "components": pair.get("components", []),
        }
        active_slug = pair.get("active_species")
        if pair.get("active_species_status") == "unique" and active_slug:
            component = next(
                (item for item in pair.get("components", [])
                 if item.get("slug") == active_slug),
                {},
            )
            entry = species.setdefault(active_slug, {
                "slug": active_slug,
                "formula": component.get("formula", active_slug),
                "pairs": [],
            })
            entry["pairs"].append(summary)
        else:
            unassigned_pairs.append(summary)
    return {
        "species": sorted(species.values(), key=lambda item: item["formula"]),
        "unassigned_pairs": sorted(
            unassigned_pairs, key=lambda item: item["formula"]
        ),
    }


def get_species(species_slug):
    for species in list_catalogue()["species"]:
        if species["slug"] == species_slug:
            return species
    raise CIADataNotFound("CIA species not found")


def get_pair(pair_slug):
    for manifest_path, manifest in _pair_manifests():
        pair = manifest.get("collision_pair", {})
        if pair.get("slug") != pair_slug:
            continue
        datasets = []
        for summary in manifest.get("datasets", []):
            dataset_id = summary.get("dataset_id")
            metadata_file = summary.get("metadata_file")
            if not dataset_id or not metadata_file:
                continue
            datasets.append({
                "id": dataset_id,
                "version": summary.get("dataset_version"),
                "metadata_file": metadata_file,
                "recommended": dataset_id == manifest.get("recommended_dataset"),
            })
        datasets.sort(key=lambda item: (not item["recommended"], item["id"]))
        active_species_slug = pair.get("active_species")
        active_species_component = next(
            (
                component for component in pair.get("components", [])
                if component.get("slug") == active_species_slug
            ),
            {},
        )
        parent_species = None
        if (
            pair.get("active_species_status") == "unique"
            and active_species_slug
        ):
            parent_species = {
                "slug": active_species_slug,
                "formula": active_species_component.get(
                    "formula", active_species_slug
                ),
            }
        return {
            "pair": pair,
            "datasets": datasets,
            "parent_species": parent_species,
        }
    raise CIADataNotFound("CIA collision pair not found")


def get_dataset(pair_slug, dataset_id):
    pair_data = get_pair(pair_slug)
    summary = next(
        (item for item in pair_data["datasets"] if item["id"] == dataset_id),
        None,
    )
    if summary is None:
        raise CIADataNotFound("CIA dataset not found")
    directory = _pair_directory(pair_slug)
    metadata_path = _safe_path(directory.name, summary["metadata_file"])
    if not metadata_path.is_file():
        raise CIADataNotFound("CIA dataset metadata not found")
    metadata = _load_json(metadata_path)
    dataset = metadata.get("dataset")
    if not isinstance(dataset, dict) or dataset.get("id") != dataset_id:
        raise CIADataError("CIA dataset metadata has an invalid structure")
    files = dataset.get("collision_induced_absorption_xsecs", {}).get("files", [])
    return {
        "pair": pair_data["pair"],
        "summary": summary,
        "dataset": dataset,
        "metadata_file": metadata_path.name,
        "files": files if isinstance(files, list) else [],
    }


def _pair_directory(pair_slug):
    for manifest_path, manifest in _pair_manifests():
        if manifest.get("collision_pair", {}).get("slug") == pair_slug:
            return manifest_path.parent
    raise CIADataNotFound("CIA collision pair not found")


def downloadable_file(pair_slug, dataset_id, filename):
    dataset_data = get_dataset(pair_slug, dataset_id)
    allowed = {dataset_data["metadata_file"]}
    allowed.update(
        item.get("filename") for item in dataset_data["files"]
        if isinstance(item, dict) and item.get("filename")
    )
    if filename not in allowed or Path(filename).name != filename:
        raise CIADataNotFound("CIA file not found")
    directory = _pair_directory(pair_slug)
    path = _safe_path(directory.name, filename)
    if not path.is_file():
        raise CIADataNotFound("CIA file not found")
    return path
