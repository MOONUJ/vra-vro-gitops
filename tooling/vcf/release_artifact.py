# -*- coding: utf-8 -*-
"""불변 release artifact build, provenance와 무결성 검증."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RELEASE_API_VERSION = "gitops.vcf.example/v1alpha1"
RELEASE_KIND = "VcfContentRelease"
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")


class ReleaseArtifactError(RuntimeError):
    """release artifact의 경로, 불변성 또는 무결성이 유효하지 않을 때 발생한다."""


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def validate_version(version: str) -> str:
    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        raise ReleaseArtifactError(f"release version은 SemVer여야 합니다: {version!r}")
    return version


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_staging(releases_root: str | Path, version: str) -> tuple[Path, Path, Path]:
    version = validate_version(version)
    releases_root = Path(releases_root).resolve()
    releases_root.mkdir(parents=True, exist_ok=True)
    destination = (releases_root / version).resolve()
    if not _is_relative_to(destination, releases_root):
        raise ReleaseArtifactError("release 경로가 releases root를 벗어납니다.")
    if destination.exists():
        raise ReleaseArtifactError(f"기존 release를 덮어쓰지 않습니다: {destination}")
    staging_root = Path(tempfile.mkdtemp(prefix=f".release-{version}-", dir=releases_root))
    staged_release = staging_root / version
    staged_release.mkdir()
    return staging_root, staged_release, destination


def _artifact_descriptors(release_root: Path) -> list[dict[str, Any]]:
    artifacts = []
    for path in sorted(item for item in release_root.rglob("*") if item.is_file() and item.name != "manifest.json"):
        artifacts.append(
            {
                "path": path.relative_to(release_root).as_posix(),
                "sha256": sha256_file(path),
                "size": path.stat().st_size,
            }
        )
    return artifacts


def finalize_release(
    staging_root: Path,
    staged_release: Path,
    destination: Path,
    version: str,
    source: str,
    target: dict[str, Any],
    tool_version: str,
    git_commit: str,
    parameters: dict[str, Any] | None = None,
) -> tuple[Path, dict[str, Any]]:
    legacy_manifest = staged_release / "manifest.json"
    components = None
    if legacy_manifest.is_file():
        try:
            legacy = json.loads(legacy_manifest.read_text(encoding="utf-8"))
            components = legacy.get("components") if isinstance(legacy, dict) else None
        except json.JSONDecodeError as exc:
            raise ReleaseArtifactError(f"기존 export manifest가 유효하지 않습니다: {exc}") from exc
        legacy_manifest.unlink()
    artifacts = _artifact_descriptors(staged_release)
    if not artifacts:
        raise ReleaseArtifactError("release에 생성된 artifact가 없습니다.")
    manifest = {
        "apiVersion": RELEASE_API_VERSION,
        "kind": RELEASE_KIND,
        "metadata": {"version": version, "createdAt": _timestamp()},
        "spec": {
            "source": source,
            "target": target,
            "toolVersion": tool_version,
            "gitCommit": git_commit,
            "parameters": parameters or {},
            "artifacts": artifacts,
        },
    }
    if components is not None:
        manifest["spec"]["exportComponents"] = components
    legacy_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        os.replace(staged_release, destination)
    except OSError as exc:
        raise ReleaseArtifactError(f"release를 최종 경로로 이동하지 못했습니다: {exc}") from exc
    shutil.rmtree(staging_root)
    return destination, manifest


def _write_deterministic_zip(source_root: Path, destination: Path) -> None:
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(item for item in source_root.rglob("*") if item.is_file()):
            relative = path.relative_to(source_root).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())


def build_local_release(
    repository_root: str | Path,
    releases_root: str | Path,
    version: str,
    target: dict[str, Any],
    tool_version: str,
    git_commit: str,
) -> tuple[Path, dict[str, Any]]:
    repository_root = Path(repository_root).resolve()
    content_root = repository_root / "content"
    if not content_root.is_dir():
        raise ReleaseArtifactError(f"content 디렉터리가 없습니다: {content_root}")
    staging_root, staged_release, destination = prepare_staging(releases_root, version)
    try:
        artifact = staged_release / f"content-{version}.zip"
        _write_deterministic_zip(content_root, artifact)
        return finalize_release(
            staging_root,
            staged_release,
            destination,
            version,
            "local-content",
            target,
            tool_version,
            git_commit,
            {"contentRoot": "content"},
        )
    except Exception:
        if staging_root.exists():
            shutil.rmtree(staging_root)
        raise


def verify_release(path: str | Path) -> dict[str, Any]:
    release_root = Path(path).resolve()
    manifest_path = release_root / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseArtifactError(f"release manifest를 읽지 못했습니다: {manifest_path}: {exc}") from exc
    if manifest.get("apiVersion") != RELEASE_API_VERSION or manifest.get("kind") != RELEASE_KIND:
        raise ReleaseArtifactError("지원하지 않는 release manifest입니다.")
    artifacts = manifest.get("spec", {}).get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ReleaseArtifactError("release artifact 목록이 없습니다.")
    declared = set()
    for artifact in artifacts:
        relative = artifact.get("path")
        if not isinstance(relative, str):
            raise ReleaseArtifactError("artifact path가 유효하지 않습니다.")
        candidate = (release_root / relative).resolve()
        if not _is_relative_to(candidate, release_root) or not candidate.is_file():
            raise ReleaseArtifactError(f"release artifact가 없거나 경계를 벗어납니다: {relative}")
        if sha256_file(candidate) != artifact.get("sha256") or candidate.stat().st_size != artifact.get("size"):
            raise ReleaseArtifactError(f"release artifact 무결성 검증 실패: {relative}")
        declared.add(relative)
    actual = {
        path.relative_to(release_root).as_posix()
        for path in release_root.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    if actual != declared:
        raise ReleaseArtifactError("release에 manifest에 선언되지 않은 artifact가 있습니다.")
    return manifest
