"""Build the portable NeuroQP skill archive and update manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).parents[1]
SKILL_ROOT = ROOT / "skills" / "neuroqp-python"
SOURCE_MANIFEST = ROOT / "skills" / "manifest.json"
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


def _read_object(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    return payload


def _skill_details() -> tuple[str, str]:
    payload = _read_object(SKILL_ROOT / "skill.json")
    version = payload.get("version")
    minor = payload.get("neuroqpMinor")
    if (
        not isinstance(version, str)
        or VERSION_PATTERN.fullmatch(version) is None
        or not isinstance(minor, str)
        or re.fullmatch(r"\d+\.\d+", minor) is None
    ):
        raise SystemExit("skill.json has invalid version metadata")
    return version, minor


def _build_archive(output: Path) -> str:
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for source in sorted(SKILL_ROOT.rglob("*")):
            if not source.is_file() or "__pycache__" in source.parts:
                continue
            relative = source.relative_to(SKILL_ROOT)
            info = zipfile.ZipInfo(
                str(Path("neuroqp-python") / relative),
                date_time=(1980, 1, 1, 0, 0, 0),
            )
            info.external_attr = (0o755 if source.suffix == ".py" else 0o644) << 16
            archive.writestr(info, source.read_bytes())
    return hashlib.sha256(output.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--base-manifest", type=Path)
    parser.add_argument("--package-version")
    args = parser.parse_args()

    version, minor = _skill_details()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    archive_name = f"neuroqp-python-{version}.zip"
    archive_path = args.output_dir / archive_name
    digest = _build_archive(archive_path)

    base = (
        args.base_manifest
        if args.base_manifest is not None and args.base_manifest.is_file()
        else SOURCE_MANIFEST
    )
    manifest = _read_object(base)
    raw_skills = manifest.get("skills")
    if not isinstance(raw_skills, dict):
        raise SystemExit(f"{base} has no skills object")
    skills = dict(raw_skills)
    existing = skills.get(minor)
    if isinstance(existing, dict) and existing.get("version") == version:
        existing_hash = existing.get("sha256")
        if existing_hash != digest:
            raise SystemExit(
                f"skill {version} was already published with different content; "
                "bump skills/neuroqp-python/skill.json"
            )

    skills[minor] = {
        "version": version,
        "url": f"https://python.neuroqp.com/skill/{archive_name}",
        "sha256": digest,
    }
    manifest["skills"] = skills
    if args.package_version is not None:
        manifest["latestPackageVersion"] = args.package_version
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(archive_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
