from cia_pipeline.writers import _column_schemas, _component_tokens, _validate_column_schemas


def test_header_pair_component_canonicalization() -> None:
    assert sorted(_component_tokens("He-H")) == sorted(_component_tokens("H-He"))
    assert sorted(_component_tokens("eq-H2 -- eq-H2")) == ["h2", "h2"]
    assert sorted(_component_tokens("n-H2 -- n-H2")) == ["h2", "h2"]


def test_two_and_three_column_json_definitions() -> None:
    standard_only = _column_schemas(False)
    mixed = _column_schemas(True)
    assert list(standard_only) == ["standard"]
    assert [column["name"] for column in standard_only["standard"]] == [
        "wavenumber",
        "cia_coefficient",
    ]
    assert mixed["with_absolute_uncertainty"][-1] == {
        "name": "uncertainty",
        "units": "cm^5 molecule^-2",
        "uncertainty_type": "absolute",
        "applies_to": "cia_coefficient",
    }
def test_source_native_absolute_uncertainty_schema_is_valid(tmp_path) -> None:
    xsecs = {
        "column_schemas": {
            "with_absolute_uncertainty": [
                {"name": "wavenumber", "units": "cm^-1"},
                {"name": "cia_coefficient", "units": "cm^-1 amagat^-2"},
                {"name": "uncertainty", "units": "cm^-1 amagat^-2", "uncertainty_type": "absolute", "applies_to": "cia_coefficient"},
            ]
        },
        "default_column_schema": "with_absolute_uncertainty",
        "files": [{"filename": "native.cia"}],
    }
    assert _validate_column_schemas(xsecs, tmp_path / "dataset.json") == []
