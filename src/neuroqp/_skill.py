"""Install and update the bundled NeuroQP agent skill."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import re
import shutil
import stat
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal, cast
from urllib.parse import urlparse

Agent = Literal["codex", "claude", "all"]
Scope = Literal["project", "user"]

_MANIFEST_URL = "https://python.neuroqp.com/skill/manifest.json"
_CACHE_SECONDS = 24 * 60 * 60
_VERSION_PATTERN = re.compile(
    r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"
    r"(?:(?:\.dev)(?P<dev>\d+))?$"
)


class SkillError(RuntimeError):
    """Raised when a skill installation or update cannot be completed."""


@dataclass(frozen=True)
class SkillMetadata:
    """Metadata stored with a NeuroQP skill bundle."""

    version: str
    neuroqp_minor: str


@dataclass(frozen=True)
class RemoteSkill:
    """A downloadable skill described by the update manifest."""

    version: str
    url: str
    sha256: str


@dataclass(frozen=True)
class RemoteManifest:
    """Validated remote update information."""

    latest_package_version: str | None
    package_url: str
    changelog_url: str
    skills: dict[str, RemoteSkill]


def install_skill(
    agent: Agent,
    scope: Scope = "project",
    *,
    project_root: Path | None = None,
    user_home: Path | None = None,
) -> tuple[Path, ...]:
    """Install the bundled skill into explicit agent destinations."""

    source = _bundled_skill_root()
    targets = _skill_targets(agent, scope, project_root, user_home)
    conflicts = [target for target in targets if target.exists()]
    if conflicts:
        paths = ", ".join(str(path) for path in conflicts)
        raise SkillError(
            f"skill destination already exists: {paths}. "
            "Use `neuroqp skill update` for an installed NeuroQP skill."
        )

    installed: list[Path] = []
    try:
        for target in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, target)
            installed.append(target)
    except OSError as error:
        for target in installed:
            shutil.rmtree(target, ignore_errors=True)
        raise SkillError(f"could not install the skill: {error}") from error
    return tuple(installed)


def update_skill(
    agent: Agent,
    scope: Scope = "project",
    *,
    project_root: Path | None = None,
    user_home: Path | None = None,
) -> tuple[Path, ...]:
    """Update installed targets to the newest compatible skill."""

    targets = _skill_targets(agent, scope, project_root, user_home)
    local_metadata: dict[Path, SkillMetadata] = {}
    for target in targets:
        if not target.is_dir():
            raise SkillError(
                f"NeuroQP skill is not installed at {target}. "
                "Run `neuroqp skill install` first."
            )
        local_metadata[target] = _load_skill_metadata(target)

    package_version = importlib.metadata.version("neuroqp")
    package_minor = _minor_version(package_version)
    manifest = _fetch_manifest(force=True)
    remote = manifest.skills.get(package_minor)
    if remote is None:
        raise SkillError(
            f"no published skill supports NeuroQP Python {package_version}"
        )

    outdated = [
        target
        for target, metadata in local_metadata.items()
        if _is_newer(remote.version, metadata.version)
    ]
    if not outdated:
        return ()

    archive = _download(remote.url)
    digest = hashlib.sha256(archive).hexdigest()
    if digest != remote.sha256:
        raise SkillError("downloaded skill archive failed SHA-256 verification")

    with tempfile.TemporaryDirectory(prefix="neuroqp-skill-update-") as temporary:
        source = _extract_skill(archive, Path(temporary))
        downloaded_metadata = _load_skill_metadata(source)
        if downloaded_metadata != SkillMetadata(remote.version, package_minor):
            raise SkillError("downloaded skill metadata does not match the manifest")
        for target in outdated:
            _replace_directory(source, target)
    return tuple(outdated)


def update_notifications(skill_root: Path) -> tuple[str, ...]:
    """Return non-blocking update notices for a loaded skill."""

    try:
        local = _load_skill_metadata(skill_root)
        package_version = importlib.metadata.version("neuroqp")
        package_minor = _minor_version(package_version)
        manifest = _fetch_manifest(force=False)
    except (OSError, SkillError, importlib.metadata.PackageNotFoundError):
        return ()

    notifications: list[str] = []
    remote = manifest.skills.get(package_minor)
    if local.neuroqp_minor != package_minor:
        notifications.append(
            f"The installed NeuroQP agent skill targets NeuroQP "
            f"{local.neuroqp_minor}.x, but the analysis environment uses "
            f"{package_version}. Reinstall the skill from this environment."
        )
    elif remote is not None and _is_newer(remote.version, local.version):
        notifications.append(
            f"NeuroQP agent skill {remote.version} is available for installed "
            f"NeuroQP Python {package_version} (skill {local.version} is installed). "
            "Run `neuroqp skill update --agent codex|claude|all` with the "
            "appropriate agent."
        )

    latest = manifest.latest_package_version
    if latest is not None and _is_newer(latest, package_version):
        notifications.append(
            f"NeuroQP Python {latest} is available; {package_version} is installed. "
            f"Review {manifest.changelog_url} before updating the package and skill."
        )
    return tuple(notifications)


def _skill_targets(
    agent: Agent,
    scope: Scope,
    project_root: Path | None,
    user_home: Path | None,
) -> tuple[Path, ...]:
    project_root = project_root or Path.cwd()
    user_home = user_home or Path.home()
    bases = {
        ("codex", "project"): project_root / ".agents" / "skills",
        ("codex", "user"): user_home / ".agents" / "skills",
        ("claude", "project"): project_root / ".claude" / "skills",
        ("claude", "user"): user_home / ".claude" / "skills",
    }
    agents = ("codex", "claude") if agent == "all" else (agent,)
    return tuple(bases[(item, scope)] / "neuroqp-python" for item in agents)


def _bundled_skill_root() -> Path:
    packaged = Path(__file__).with_name("_skill_bundle") / "neuroqp-python"
    if packaged.is_dir():
        return packaged
    checkout = Path(__file__).parents[2] / "skills" / "neuroqp-python"
    if checkout.is_dir():
        return checkout
    raise SkillError("the NeuroQP agent skill is missing from this installation")


def _load_skill_metadata(root: Path) -> SkillMetadata:
    try:
        payload = json.loads((root / "skill.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SkillError(f"{root} is not a valid NeuroQP skill") from error
    if not isinstance(payload, dict):
        raise SkillError(f"{root} is not a valid NeuroQP skill")
    if payload.get("name") != "neuroqp-python":
        raise SkillError(f"{root} is not a NeuroQP Python skill")
    version = payload.get("version")
    neuroqp_minor = payload.get("neuroqpMinor")
    manifest_url = payload.get("manifestUrl")
    if (
        not isinstance(version, str)
        or not isinstance(neuroqp_minor, str)
        or manifest_url != _MANIFEST_URL
    ):
        raise SkillError(f"{root} has invalid skill metadata")
    _version_key(version)
    if not re.fullmatch(r"\d+\.\d+", neuroqp_minor):
        raise SkillError(f"{root} has invalid NeuroQP compatibility metadata")
    return SkillMetadata(version, neuroqp_minor)


def _fetch_manifest(*, force: bool) -> RemoteManifest:
    cache = _cache_path()
    if not force and cache.is_file():
        age = time.time() - cache.stat().st_mtime
        if age < _CACHE_SECONDS:
            try:
                return _parse_manifest(cache.read_bytes())
            except (OSError, SkillError):
                pass

    try:
        payload = _download(_MANIFEST_URL)
        manifest = _parse_manifest(payload)
    except (OSError, SkillError, urllib.error.URLError) as error:
        raise SkillError("could not check NeuroQP skill updates") from error

    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(payload)
    except OSError:
        pass
    return manifest


def _parse_manifest(payload: bytes) -> RemoteManifest:
    try:
        data = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SkillError("the skill update manifest is invalid") from error
    if not isinstance(data, dict) or data.get("schemaVersion") != 1:
        raise SkillError("the skill update manifest is invalid")

    latest = data.get("latestPackageVersion")
    package_url = data.get("packageUrl")
    changelog_url = data.get("changelogUrl")
    raw_skills = data.get("skills")
    if (
        (latest is not None and not isinstance(latest, str))
        or not isinstance(package_url, str)
        or not isinstance(changelog_url, str)
        or not isinstance(raw_skills, dict)
    ):
        raise SkillError("the skill update manifest is invalid")
    if latest is not None:
        _version_key(latest)

    skills: dict[str, RemoteSkill] = {}
    for minor, raw_skill in raw_skills.items():
        if not isinstance(minor, str) or not isinstance(raw_skill, dict):
            raise SkillError("the skill update manifest is invalid")
        version = raw_skill.get("version")
        url = raw_skill.get("url")
        sha256 = raw_skill.get("sha256")
        if (
            not isinstance(version, str)
            or not isinstance(url, str)
            or not isinstance(sha256, str)
            or not re.fullmatch(r"[0-9a-f]{64}", sha256)
        ):
            raise SkillError("the skill update manifest is invalid")
        _version_key(version)
        parsed_url = urlparse(url)
        if parsed_url.scheme != "https" or parsed_url.netloc != "python.neuroqp.com":
            raise SkillError("the skill update manifest contains an unsafe URL")
        skills[minor] = RemoteSkill(version, url, sha256)
    return RemoteManifest(latest, package_url, changelog_url, skills)


def _download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "neuroqp-python"})
    with urllib.request.urlopen(request, timeout=5) as response:
        return cast(bytes, response.read())


def _cache_path() -> Path:
    cache_root = os.environ.get("XDG_CACHE_HOME")
    base = Path(cache_root) if cache_root else Path.home() / ".cache"
    return base / "neuroqp" / "skill-manifest.json"


def _extract_skill(archive: bytes, destination: Path) -> Path:
    archive_path = destination / "skill.zip"
    archive_path.write_bytes(archive)
    with zipfile.ZipFile(archive_path) as skill_zip:
        seen: set[str] = set()
        for info in skill_zip.infolist():
            path = PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            if (
                path.is_absolute()
                or not path.parts
                or path.parts[0] != "neuroqp-python"
                or ".." in path.parts
                or info.filename in seen
                or stat.S_ISLNK(mode)
            ):
                raise SkillError("downloaded skill archive is unsafe")
            seen.add(info.filename)
        skill_zip.extractall(destination)
    root = destination / "neuroqp-python"
    if not root.is_dir():
        raise SkillError("downloaded skill archive has no skill directory")
    return root


def _replace_directory(source: Path, target: Path) -> None:
    temporary = Path(tempfile.mkdtemp(prefix=".neuroqp-skill-", dir=target.parent))
    staged = temporary / "new"
    backup = temporary / "old"
    try:
        shutil.copytree(source, staged)
        target.rename(backup)
        try:
            staged.rename(target)
        except OSError:
            backup.rename(target)
            raise
    except OSError as error:
        raise SkillError(f"could not update {target}: {error}") from error
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def _minor_version(version: str) -> str:
    key = _version_key(version)
    return f"{key[0]}.{key[1]}"


def _is_newer(candidate: str, current: str) -> bool:
    return _version_key(candidate) > _version_key(current)


def _version_key(version: str) -> tuple[int, int, int, int, int]:
    match = _VERSION_PATTERN.fullmatch(version)
    if match is None:
        raise SkillError(f"unsupported NeuroQP version {version!r}")
    dev = match.group("dev")
    return (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        1 if dev is None else 0,
        0 if dev is None else int(dev),
    )


def _as_agent(value: str) -> Agent:
    return cast(Agent, value)


def _as_scope(value: str) -> Scope:
    return cast(Scope, value)
