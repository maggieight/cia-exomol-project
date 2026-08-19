from __future__ import annotations

import re
from collections import defaultdict

from .models import CIABlock


def safe_id(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9.-]+", "-", value)
    return re.sub(r"-+", "-", value).strip("-")


def assign_proposed_groups(blocks: list[CIABlock]) -> list[str]:
    ambiguities: list[str] = []
    main_files: dict[tuple[str, str], set[str]] = defaultdict(set)
    main_citations: dict[tuple[str, str], set[str]] = defaultdict(set)
    for block in blocks:
        if block.collection == "main":
            key = (block.normalized_pair, block.repository_version)
            main_files[key].add(block.raw_relative_path)
            main_citations[key].update(block.citation_keys)

    main_versions: dict[str, set[str]] = defaultdict(set)
    for pair, version in main_files:
        main_versions[pair].add(version)
    for pair, versions in sorted(main_versions.items()):
        if len(versions) > 1:
            ambiguities.append(
                f"{pair}: multiple recommended main repository versions: {', '.join(sorted(versions))}"
            )

    for block in blocks:
        citations = "-".join(block.citation_keys)
        if block.collection == "main":
            key = (block.normalized_pair, block.repository_version)
            if len(main_files[key]) == 1 and len(main_citations[key]) == 1:
                dataset_id = next(iter(main_citations[key]))
            else:
                dataset_id = f"hitran{block.repository_version}-main"
            group = f"main:{block.normalized_pair}:{block.repository_version}"
        else:
            if block.citation_keys:
                dataset_id = citations
            else:
                dataset_id = f"unresolved-ref-{block.reference_number}"
            group = (
                f"sup:{block.normalized_pair}:refs={citations or block.reference_number}:"
                "variants=merged"
            )
        block.proposed_dataset_group = group
        block.proposed_dataset_id = safe_id(dataset_id)
    return ambiguities
