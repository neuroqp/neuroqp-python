from __future__ import annotations

import json
from pathlib import Path

import pytest

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
    assert "Minimal project (project-1)" in output
    assert "Animals: 1" in output


def test_inspect_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["inspect", str(VALID), "--json"]) == 0
    output = capsys.readouterr().out
    payload = json.loads(output)
    assert payload["project"]["name"] == "Minimal project"
    assert payload["counts"]["slices"] == 1


def test_inspect_invalid(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["inspect", str(INVALID)]) == 1
    output = capsys.readouterr().out
    assert output.startswith("Cannot inspect invalid export:")


def test_inspect_invalid_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["inspect", str(INVALID), "--json"]) == 1
    output = capsys.readouterr().out
    assert json.loads(output)["valid"] is False
