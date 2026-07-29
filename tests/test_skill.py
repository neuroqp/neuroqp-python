from __future__ import annotations

import hashlib
import importlib.metadata
import io
import json
import shutil
import zipfile
from pathlib import Path

import pytest

from neuroqp import _skill
from neuroqp.cli import main


def _archive_with_version(tmp_path: Path, version: str) -> bytes:
    source = Path(__file__).parents[1] / "skills" / "neuroqp-python"
    bundle = tmp_path / "neuroqp-python"
    shutil.copytree(source, bundle)
    metadata_path = bundle / "skill.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["version"] = version
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for path in sorted(bundle.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(tmp_path))
    return output.getvalue()


def _manifest_payload(
    *,
    latest: str | None = "0.1.0",
    skill_version: str = "0.1.0",
) -> bytes:
    payload = {
        "schemaVersion": 1,
        "latestPackageVersion": latest,
        "packageUrl": "https://pypi.org/project/neuroqp/",
        "changelogUrl": "https://python.neuroqp.com/latest/changelog/",
        "skills": {
            "0.1": {
                "version": skill_version,
                "url": (
                    "https://python.neuroqp.com/skill/"
                    f"neuroqp-python-{skill_version}.zip"
                ),
                "sha256": "0" * 64,
            }
        },
    }
    return json.dumps(payload).encode()


@pytest.mark.parametrize(
    ("agent", "relative_paths"),
    [
        ("codex", (".agents/skills/neuroqp-python",)),
        ("claude", (".claude/skills/neuroqp-python",)),
        (
            "all",
            (
                ".agents/skills/neuroqp-python",
                ".claude/skills/neuroqp-python",
            ),
        ),
    ],
)
def test_install_skill_project_targets(
    tmp_path: Path,
    agent: _skill.Agent,
    relative_paths: tuple[str, ...],
) -> None:
    installed = _skill.install_skill(agent, project_root=tmp_path)

    assert installed == tuple(tmp_path / path for path in relative_paths)
    for path in installed:
        assert (path / "SKILL.md").is_file()
        assert _skill._load_skill_metadata(path).version == "0.1.0"


def test_install_skill_user_targets(tmp_path: Path) -> None:
    installed = _skill.install_skill("all", "user", user_home=tmp_path)

    assert installed == (
        tmp_path / ".agents/skills/neuroqp-python",
        tmp_path / ".claude/skills/neuroqp-python",
    )


def test_install_skill_refuses_existing_destination(tmp_path: Path) -> None:
    _skill.install_skill("codex", project_root=tmp_path)

    with pytest.raises(_skill.SkillError, match="already exists"):
        _skill.install_skill("codex", project_root=tmp_path)


def test_update_skill_downloads_verified_compatible_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = _skill.install_skill("codex", project_root=tmp_path)[0]
    archive = _archive_with_version(tmp_path / "remote", "0.1.1")
    remote = _skill.RemoteSkill(
        "0.1.1",
        "https://python.neuroqp.com/skill/neuroqp-python-0.1.1.zip",
        hashlib.sha256(archive).hexdigest(),
    )
    manifest = _skill.RemoteManifest(
        "0.1.0",
        "https://pypi.org/project/neuroqp/",
        "https://python.neuroqp.com/latest/changelog/",
        {"0.1": remote},
    )
    monkeypatch.setattr(_skill, "_fetch_manifest", lambda *, force: manifest)
    monkeypatch.setattr(_skill, "_download", lambda _url: archive)
    monkeypatch.setattr(importlib.metadata, "version", lambda _name: "0.1.0")

    assert _skill.update_skill("codex", project_root=tmp_path) == (target,)
    assert _skill._load_skill_metadata(target).version == "0.1.1"
    assert _skill.update_skill("codex", project_root=tmp_path) == ()


def test_update_skill_rejects_bad_hash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _skill.install_skill("codex", project_root=tmp_path)
    archive = _archive_with_version(tmp_path / "remote", "0.1.1")
    manifest = _skill.RemoteManifest(
        None,
        "https://pypi.org/project/neuroqp/",
        "https://python.neuroqp.com/latest/changelog/",
        {
            "0.1": _skill.RemoteSkill(
                "0.1.1",
                "https://python.neuroqp.com/skill/neuroqp-python-0.1.1.zip",
                "0" * 64,
            )
        },
    )
    monkeypatch.setattr(_skill, "_fetch_manifest", lambda *, force: manifest)
    monkeypatch.setattr(_skill, "_download", lambda _url: archive)
    monkeypatch.setattr(importlib.metadata, "version", lambda _name: "0.1.0")

    with pytest.raises(_skill.SkillError, match="SHA-256"):
        _skill.update_skill("codex", project_root=tmp_path)


def test_update_skill_requires_an_installation(tmp_path: Path) -> None:
    with pytest.raises(_skill.SkillError, match="not installed"):
        _skill.update_skill("claude", project_root=tmp_path)


def test_update_skill_requires_a_compatible_published_skill(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _skill.install_skill("codex", project_root=tmp_path)
    manifest = _skill.RemoteManifest(
        None,
        "https://pypi.org/project/neuroqp/",
        "https://python.neuroqp.com/latest/changelog/",
        {},
    )
    monkeypatch.setattr(_skill, "_fetch_manifest", lambda *, force: manifest)
    monkeypatch.setattr(importlib.metadata, "version", lambda _name: "0.1.0")

    with pytest.raises(_skill.SkillError, match="no published skill"):
        _skill.update_skill("codex", project_root=tmp_path)


def test_update_skill_checks_downloaded_metadata(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _skill.install_skill("codex", project_root=tmp_path)
    archive = _archive_with_version(tmp_path / "remote", "0.1.2")
    remote = _skill.RemoteSkill(
        "0.1.1",
        "https://python.neuroqp.com/skill/neuroqp-python-0.1.1.zip",
        hashlib.sha256(archive).hexdigest(),
    )
    manifest = _skill.RemoteManifest(
        None,
        "https://pypi.org/project/neuroqp/",
        "https://python.neuroqp.com/latest/changelog/",
        {"0.1": remote},
    )
    monkeypatch.setattr(_skill, "_fetch_manifest", lambda *, force: manifest)
    monkeypatch.setattr(_skill, "_download", lambda _url: archive)
    monkeypatch.setattr(importlib.metadata, "version", lambda _name: "0.1.0")

    with pytest.raises(_skill.SkillError, match="does not match"):
        _skill.update_skill("codex", project_root=tmp_path)


def test_update_notifications_report_skill_and_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    skill_root = _skill.install_skill("codex", project_root=tmp_path)[0]
    manifest = _skill.RemoteManifest(
        "0.2.0",
        "https://pypi.org/project/neuroqp/",
        "https://python.neuroqp.com/latest/changelog/",
        {
            "0.1": _skill.RemoteSkill(
                "0.1.1",
                "https://python.neuroqp.com/skill/neuroqp-python-0.1.1.zip",
                "0" * 64,
            )
        },
    )
    monkeypatch.setattr(_skill, "_fetch_manifest", lambda *, force: manifest)
    monkeypatch.setattr(importlib.metadata, "version", lambda _name: "0.1.0")

    notifications = _skill.update_notifications(skill_root)

    assert len(notifications) == 2
    assert "skill 0.1.1" in notifications[0]
    assert "NeuroQP Python 0.2.0" in notifications[1]


def test_update_notifications_report_incompatible_skill(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    skill_root = _skill.install_skill("codex", project_root=tmp_path)[0]
    manifest = _skill.RemoteManifest(
        None,
        "https://pypi.org/project/neuroqp/",
        "https://python.neuroqp.com/latest/changelog/",
        {},
    )
    monkeypatch.setattr(_skill, "_fetch_manifest", lambda *, force: manifest)
    monkeypatch.setattr(importlib.metadata, "version", lambda _name: "0.2.0")

    assert "targets NeuroQP 0.1.x" in _skill.update_notifications(skill_root)[0]


def test_update_notifications_are_silent_on_check_failure(
    tmp_path: Path,
) -> None:
    assert _skill.update_notifications(tmp_path / "missing") == ()


def test_cli_requires_an_explicit_agent() -> None:
    with pytest.raises(SystemExit):
        main(["skill", "install"])


def test_cli_installs_all_agents(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)

    assert main(["skill", "install", "--agent", "all"]) == 0

    output = capsys.readouterr().out
    assert output.count("Installed NeuroQP skill:") == 2
    assert (tmp_path / ".agents/skills/neuroqp-python/SKILL.md").is_file()
    assert (tmp_path / ".claude/skills/neuroqp-python/SKILL.md").is_file()


def test_cli_reports_skill_install_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["skill", "install", "--agent", "codex"]) == 0

    assert main(["skill", "install", "--agent", "codex"]) == 1

    assert "already exists" in capsys.readouterr().err


def test_fetch_manifest_uses_fresh_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _manifest_payload()
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.setattr(_skill, "_download", lambda _url: payload)

    first = _skill._fetch_manifest(force=False)
    monkeypatch.setattr(
        _skill,
        "_download",
        lambda _url: pytest.fail("fresh cache should avoid a download"),
    )
    second = _skill._fetch_manifest(force=False)

    assert first == second
    assert second.skills["0.1"].version == "0.1.0"


def test_fetch_manifest_wraps_download_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

    def fail(_url: str) -> bytes:
        raise OSError("offline")

    monkeypatch.setattr(_skill, "_download", fail)

    with pytest.raises(_skill.SkillError, match="could not check"):
        _skill._fetch_manifest(force=True)


def test_parse_manifest_rejects_unsafe_download_url() -> None:
    payload = {
        "schemaVersion": 1,
        "latestPackageVersion": None,
        "packageUrl": "https://pypi.org/project/neuroqp/",
        "changelogUrl": "https://python.neuroqp.com/latest/changelog/",
        "skills": {
            "0.1": {
                "version": "0.1.1",
                "url": "https://example.com/skill.zip",
                "sha256": "0" * 64,
            }
        },
    }

    with pytest.raises(_skill.SkillError, match="unsafe URL"):
        _skill._parse_manifest(json.dumps(payload).encode())


@pytest.mark.parametrize(
    "payload",
    [
        b"not-json",
        b"[]",
        json.dumps({"schemaVersion": 1, "skills": []}).encode(),
        json.dumps(
            {
                "schemaVersion": 1,
                "latestPackageVersion": None,
                "packageUrl": "https://pypi.org/project/neuroqp/",
                "changelogUrl": "https://python.neuroqp.com/latest/changelog/",
                "skills": {"0.1": {"version": 1}},
            }
        ).encode(),
    ],
)
def test_parse_manifest_rejects_invalid_payloads(payload: bytes) -> None:
    with pytest.raises(_skill.SkillError, match="manifest is invalid"):
        _skill._parse_manifest(payload)


def test_extract_skill_rejects_unsafe_archive(tmp_path: Path) -> None:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("../SKILL.md", "unsafe")

    with pytest.raises(_skill.SkillError, match="archive is unsafe"):
        _skill._extract_skill(output.getvalue(), tmp_path)


def test_version_parser_orders_development_releases() -> None:
    assert _skill._is_newer("0.1.0", "0.1.0.dev0")
    with pytest.raises(_skill.SkillError, match="unsupported"):
        _skill._version_key("next")
