from cia_pipeline.metadata import validate_sources


def source(key: str, repository: str, ref):
    return {
        "repository": repository,
        "citation_key": key,
        "authors": ["A. Author"],
        "title": "Title",
        "year": 2022,
        "doi": "10.1/example",
        "source_url": "https://doi.org/10.1/example",
        "verified": True,
        "ref": ref,
    }


def test_integer_hitran_ref_is_indexed() -> None:
    references, problems = validate_sources(
        {"paper": source("paper", "HITRAN CIA", 7)}, strict=True
    )
    assert references == {7: ("paper",)}
    assert problems == []


def test_non_hitran_null_refs_are_valid_distinct_and_not_indexed() -> None:
    sources = {
        "first": source("first", "JGR supplementary material", None),
        "second": source("second", "JQSRT supplementary material", None),
    }
    references, problems = validate_sources(sources, strict=True)
    assert references == {}
    assert problems == []


def test_hitran_null_ref_is_rejected() -> None:
    _, problems = validate_sources({"paper": source("paper", "HITRAN CIA", None)})
    assert any("positive integer" in problem["problem"] for problem in problems)


def test_shared_hitran_null_refs_are_valid_and_not_indexed() -> None:
    sources = {
        key: source(key, "HITRAN CIA", None)
        for key in (
            "hitran_cia_repository",
            "terragni_hitran",
            "gordon2026_hitran",
        )
    }
    references, problems = validate_sources(sources, strict=True)
    assert references == {}
    assert problems == []


def test_shared_hitran_source_rejects_numeric_ref() -> None:
    _, problems = validate_sources(
        {"terragni_hitran": source("terragni_hitran", "HITRAN CIA", 99)}
    )
    assert any("shared HITRAN source ref must be null" in item["problem"] for item in problems)


def test_empty_zero_and_boolean_refs_are_rejected() -> None:
    for ref in ("", 0, True):
        _, problems = validate_sources({"paper": source("paper", "HITRAN CIA", ref)})
        assert problems


def test_source_key_must_equal_citation_key() -> None:
    _, problems = validate_sources(
        {"object-key": source("different-key", "HITRAN CIA", 9)}
    )
    assert any("key does not equal" in problem["problem"] for problem in problems)
