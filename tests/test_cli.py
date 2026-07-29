from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuroqp import ValidationIssue, ValidationReport
from neuroqp.cli import main

FIXTURES = Path(__file__).parent / "fixtures"
VALID = FIXTURES / "minimal-v2"
INVALID = FIXTURES / "invalid-v2"


def test_validate_text(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate", str(VALID)]) == 0
    output = capsys.readouterr().out
    assert output.startswith("Valid NeuroQP v2 export:")


def test_validate_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate", str(INVALID), "--json"]) == 1
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["valid"] is False
    assert payload["issues"]


def test_validate_invalid_text(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["validate", str(INVALID)]) == 1
    output = capsys.readouterr().out
    assert "Invalid NeuroQP export:" in output
    assert "(missing_member)" in output


def test_inspect_text(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["inspect", str(VALID)]) == 0
    output = capsys.readouterr().out
    assert "Validation\n  Status: valid" in output
    assert "Project\n  Name: Minimal project\n  ID: project-1" in output
    assert "Modules\n  data: included\n  registration: not included" in output
    assert "Animals: 1\n    - Mouse 1 (animal-1)" in output
    assert "Stainings: 1\n    - DAPI (staining-1)" in output
    assert "Classifier selections\n  None" in output


def test_inspect_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["inspect", str(VALID), "--json"]) == 0
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["valid"] is True
    assert payload["project"]["name"] == "Minimal project"
    assert payload["project"]["wholeSlice"]["micronsPerPixel"] == 4.2975
    assert payload["counts"]["slices"] == 1
    assert payload["animals"] == [{"id": "animal-1", "name": "Mouse 1"}]
    assert payload["stainings"] == [{"id": "staining-1", "name": "DAPI"}]
    assert payload["expiresAt"] == "2026-08-04T12:00:00+00:00"


def test_inspect_invalid(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["inspect", str(INVALID)]) == 1
    output = capsys.readouterr().out
    assert output.startswith("Cannot inspect invalid export:")
    assert "(missing_member)" in output


def test_inspect_invalid_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["inspect", str(INVALID), "--json"]) == 1
    output = capsys.readouterr().out
    assert json.loads(output)["valid"] is False


@pytest.mark.parametrize("as_json", [False, True])
def test_validate_surfaces_large_zip_guidance(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    as_json: bool,
) -> None:
    message = (
        "ZIP exceeds the configured limit. Extract this trusted ZIP and pass "
        "the resulting directory to open_export()."
    )
    report = ValidationReport(
        issues=(
            ValidationIssue(
                path="large.zip",
                code="size_limit",
                message=message,
            ),
        )
    )

    def validate(_source: Path) -> ValidationReport:
        return report

    monkeypatch.setattr("neuroqp.cli.validate_export", validate)
    arguments = ["validate", "large.zip"]
    if as_json:
        arguments.append("--json")
    assert main(arguments) == 1
    output = capsys.readouterr().out
    if as_json:
        assert json.loads(output)["issues"][0]["message"] == message
    else:
        assert message in output
