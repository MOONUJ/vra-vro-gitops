# -*- coding: utf-8 -*-
"""Automation과 Orchestrator 콘텐츠 identity 및 정규화 계약."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

from config_loader import REPOSITORY_ROOT


API_VERSION = "gitops.vcf.example/v1alpha1"
KIND = "ContentIdentity"
VOLATILE_FIELDS = {
    "_links",
    "createdAt",
    "createdBy",
    "lastUpdatedAt",
    "lastUpdatedBy",
    "lastImportCompletedAt",
    "lastImportErrors",
    "lastImportStartedAt",
    "itemsFound",
    "itemsImported",
    "links",
    "orgId",
    "organizationId",
    "owner",
    "updatedAt",
    "updatedBy",
    "userId",
}


class ContentIdentityError(RuntimeError):
    """콘텐츠 identity 또는 정규화 계약이 유효하지 않을 때 발생한다."""


@dataclass(frozen=True)
class ContentDefinition:
    product: str
    resource_type: str
    relative_root: str
    layout: str
    primary_names: tuple[str, ...] = ()


CONTENT_DEFINITIONS = {
    (definition.product, definition.resource_type): definition
    for definition in (
        ContentDefinition("automation", "Blueprint", "content/automation/blueprints", "directory", ("blueprint.json",)),
        ContentDefinition("automation", "ABXAction", "content/automation/abx", "directory", ("init.json",)),
        ContentDefinition("automation", "CatalogSource", "content/automation/catalog_sources", "json-file"),
        ContentDefinition("automation", "CustomForm", "content/automation/custom_forms", "json-file"),
        ContentDefinition("automation", "CustomResource", "content/automation/custom_resources", "json-file"),
        ContentDefinition("automation", "Policy", "content/automation/policies", "json-file"),
        ContentDefinition("automation", "ResourceAction", "content/automation/resource_actions", "json-file"),
        ContentDefinition("automation", "Subscription", "content/automation/subscriptions", "json-file"),
        ContentDefinition("orchestrator", "Workflow", "content/orchestrator/workflows", "directory", ("workflow.json",)),
        ContentDefinition("orchestrator", "Action", "content/orchestrator/actions", "directory", ("action.json",)),
        ContentDefinition("orchestrator", "Configuration", "content/orchestrator/configurations", "json-file"),
        ContentDefinition("orchestrator", "Resource", "content/orchestrator/resources", "directory", ("resource.json",)),
    )
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _secure_attribute(value: dict[str, Any]) -> bool:
    if value.get("type") == "SecureString":
        return True
    child = value.get("value")
    return isinstance(child, dict) and "secure-string" in child


def normalize_content(value: Any) -> Any:
    """휘발 필드와 비밀값을 제거하고 비교 가능한 canonical 값을 만든다."""
    if isinstance(value, dict):
        if _secure_attribute(value):
            return {
                key: normalize_content(child)
                for key, child in sorted(value.items())
                if key not in VOLATILE_FIELDS and key != "value"
            } | {"value": {"redacted": True}}
        return {
            key: normalize_content(child)
            for key, child in sorted(value.items())
            if key not in VOLATILE_FIELDS and child is not None
        }
    if isinstance(value, list):
        normalized = [normalize_content(child) for child in value]
        if all(isinstance(child, dict) for child in normalized):
            return sorted(normalized, key=_canonical_json)
        return normalized
    if isinstance(value, str):
        return value.replace("\r\n", "\n")
    return value


def content_hash(value: Any) -> str:
    normalized = normalize_content(value)
    return hashlib.sha256(_canonical_json(normalized).encode("utf-8")).hexdigest()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def identity_key(manifest: dict[str, Any]) -> tuple[str, str, str, str]:
    metadata = manifest["metadata"]
    spec = manifest["spec"]
    scope = spec.get("scope", {})
    return spec["product"], spec["type"], metadata["name"], _canonical_json(scope)


def load_identity(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ContentIdentityError(f"identity manifest를 읽지 못했습니다: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContentIdentityError(f"identity manifest 최상위 값은 객체여야 합니다: {path}")
    return value


def validate_identity(repository_root: Path, path: Path, manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    metadata = manifest.get("metadata")
    spec = manifest.get("spec")
    if manifest.get("apiVersion") != API_VERSION:
        errors.append(f"{path}: 지원하지 않는 apiVersion입니다: {manifest.get('apiVersion')!r}")
    if manifest.get("kind") != KIND:
        errors.append(f"{path}: kind는 {KIND}여야 합니다.")
    if not isinstance(metadata, dict) or not isinstance(metadata.get("name"), str) or not metadata["name"]:
        errors.append(f"{path}: metadata.name이 필요합니다.")
    if isinstance(metadata, dict) and "remoteId" in metadata:
        if not isinstance(metadata["remoteId"], str) or not metadata["remoteId"]:
            errors.append(f"{path}: metadata.remoteId는 비어 있지 않은 문자열이어야 합니다.")
    if not isinstance(spec, dict):
        errors.append(f"{path}: spec 객체가 필요합니다.")
        return errors
    product = spec.get("product")
    resource_type = spec.get("type")
    definition = CONTENT_DEFINITIONS.get((product, resource_type))
    if definition is None:
        errors.append(f"{path}: 지원하지 않는 product/type입니다: {product!r}/{resource_type!r}")
    relative_path = spec.get("path")
    if not isinstance(relative_path, str) or not relative_path:
        errors.append(f"{path}: spec.path가 필요합니다.")
        return errors
    target = (repository_root / relative_path).resolve()
    content_root = (repository_root / "content").resolve()
    if not _is_relative_to(target, content_root):
        errors.append(f"{path}: spec.path는 content/ 아래여야 합니다: {relative_path}")
    elif not target.exists():
        errors.append(f"{path}: spec.path 대상이 없습니다: {relative_path}")
    if definition is not None:
        expected_root = (repository_root / definition.relative_root).resolve()
        if not _is_relative_to(target, expected_root):
            errors.append(f"{path}: {product}/{resource_type} 경로는 {definition.relative_root}/ 아래여야 합니다.")
    scope = spec.get("scope", {})
    if not isinstance(scope, dict):
        errors.append(f"{path}: spec.scope는 객체여야 합니다.")
    usages = spec.get("usages", [])
    if not isinstance(usages, list) or any(not isinstance(item, str) or not item for item in usages):
        errors.append(f"{path}: spec.usages는 문자열 목록이어야 합니다.")
    return errors


def find_identity_paths(repository_root: Path) -> list[Path]:
    content_root = repository_root / "content"
    if not content_root.exists():
        return []
    return sorted(path for path in content_root.rglob("*.gitops.yaml") if path.is_file())


def validate_identities(repository_root: str | Path) -> list[str]:
    repository_root = Path(repository_root).resolve()
    errors: list[str] = []
    logical: dict[tuple[str, str, str, str], Path] = {}
    remotes: dict[tuple[str, str, str], Path] = {}
    targets: dict[str, Path] = {}
    for path in find_identity_paths(repository_root):
        manifest = load_identity(path)
        item_errors = validate_identity(repository_root, path, manifest)
        errors.extend(item_errors)
        if item_errors:
            continue
        key = identity_key(manifest)
        if key in logical:
            errors.append(f"{path}: logical identity가 {logical[key]}와 중복됩니다: {key}")
        logical[key] = path
        metadata = manifest["metadata"]
        remote_id = metadata.get("remoteId")
        if remote_id:
            remote_key = (manifest["spec"]["product"], manifest["spec"]["type"], remote_id)
            if remote_key in remotes:
                errors.append(f"{path}: remote identity가 {remotes[remote_key]}와 중복됩니다: {remote_key}")
            remotes[remote_key] = path
        target = manifest["spec"]["path"]
        if target in targets:
            errors.append(f"{path}: spec.path가 {targets[target]}와 중복됩니다: {target}")
        targets[target] = path
    return errors


def _candidate_paths(repository_root: Path, definition: ContentDefinition) -> Iterable[Path]:
    root = repository_root / definition.relative_root
    if not root.exists():
        return []
    if definition.layout == "json-file":
        return sorted(path for path in root.glob("*.json") if path.is_file())
    candidates: list[Path] = []
    for primary_name in definition.primary_names:
        candidates.extend(path.parent for path in root.rglob(primary_name) if path.is_file())
    return sorted(set(candidates))


def sidecar_path(target: Path, definition: ContentDefinition) -> Path:
    if definition.layout == "directory":
        return target / ".gitops.yaml"
    return target.with_suffix(".gitops.yaml")


def identity_preview(repository_root: str | Path) -> list[dict[str, Any]]:
    """파일을 쓰지 않고 기존 콘텐츠의 identity sidecar 후보를 만든다."""
    repository_root = Path(repository_root).resolve()
    preview: list[dict[str, Any]] = []
    for definition in CONTENT_DEFINITIONS.values():
        for target in _candidate_paths(repository_root, definition):
            sidecar = sidecar_path(target, definition)
            relative_target = target.relative_to(repository_root).as_posix()
            preview.append(
                {
                    "action": "SKIP" if sidecar.exists() else "CREATE",
                    "sidecar": sidecar.relative_to(repository_root).as_posix(),
                    "manifest": {
                        "apiVersion": API_VERSION,
                        "kind": KIND,
                        "metadata": {"name": target.stem if target.is_file() else target.name},
                        "spec": {
                            "product": definition.product,
                            "type": definition.resource_type,
                            "path": relative_target,
                            "scope": {},
                            "usages": [],
                        },
                    },
                }
            )
    return sorted(preview, key=lambda item: item["sidecar"])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="VCF 콘텐츠 identity 검증 도구")
    parser.add_argument("action", choices=["validate", "preview"])
    parser.add_argument("--repository-root", default=str(REPOSITORY_ROOT))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.action == "validate":
            errors = validate_identities(args.repository_root)
            if errors:
                for error in errors:
                    print(error, file=sys.stderr)
                return 1
            print("콘텐츠 identity 검증 완료")
            return 0
        preview = identity_preview(args.repository_root)
        if args.json:
            print(json.dumps(preview, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            for item in preview:
                print(f"{item['action']:6} {item['sidecar']}")
        return 0
    except (ContentIdentityError, OSError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
