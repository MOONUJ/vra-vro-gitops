# -*- coding: utf-8 -*-
"""VCF Automation Day-0 리소스 manifest의 발견, 채택, 검증과 비교를 담당한다."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml


API_VERSION = "gitops.vcf.example/v1alpha1"


class InfrastructureError(RuntimeError):
    """원격 조회나 manifest 계약을 안전하게 처리할 수 없을 때 발생한다."""


@dataclass(frozen=True)
class ResourceDefinition:
    kind: str
    endpoint: str
    directory: str


RESOURCE_DEFINITIONS = {
    definition.kind: definition
    for definition in (
        ResourceDefinition("CloudAccount", "/iaas/api/cloud-accounts", "cloud-accounts"),
        ResourceDefinition("CloudZone", "/iaas/api/zones", "cloud-zones"),
        ResourceDefinition("NetworkProfile", "/iaas/api/network-profiles", "network-profiles"),
        ResourceDefinition("StorageProfile", "/iaas/api/storage-profiles", "storage-profiles"),
        ResourceDefinition("ImageProfile", "/iaas/api/image-profiles", "image-profiles"),
        ResourceDefinition("Project", "/iaas/api/projects", "projects"),
    )
}

VOLATILE_FIELDS = {
    "_links",
    "createdAt",
    "createdBy",
    "organizationId",
    "orgId",
    "owner",
    "updatedAt",
    "updatedBy",
}


def _compact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _compact(child)
            for key, child in sorted(value.items())
            if key not in VOLATILE_FIELDS and child is not None
        }
    if isinstance(value, list):
        compacted = [_compact(child) for child in value]
        if all(isinstance(child, dict) for child in compacted):
            return sorted(compacted, key=lambda child: json.dumps(child, ensure_ascii=False, sort_keys=True))
        return compacted
    return value


def _copy_fields(source: dict[str, Any], names: Iterable[str]) -> dict[str, Any]:
    return {name: source[name] for name in names if name in source and source[name] is not None}


def normalize_remote(kind: str, remote: dict[str, Any]) -> dict[str, Any]:
    """API 응답을 Git에 기록할 안정적인 spec으로 정규화한다."""
    if kind == "CloudAccount":
        spec = _copy_fields(
            remote,
            ("name", "description", "cloudAccountType", "cloudAccountTypeId", "hostname", "enabledRegions", "tags"),
        )
    elif kind == "CloudZone":
        spec = _copy_fields(
            remote,
            ("name", "description", "regionId", "placementPolicy", "computeIds", "tags", "tagsToMatch"),
        )
    elif kind == "NetworkProfile":
        spec = _copy_fields(
            remote,
            (
                "name",
                "description",
                "externalRegionId",
                "isolationType",
                "isolationNetworkDomainCIDR",
                "isolatedNetworkCIDRPrefix",
                "fabricNetworkIds",
                "tags",
            ),
        )
    elif kind == "StorageProfile":
        spec = _copy_fields(
            remote,
            ("name", "description", "regionId", "externalRegionId", "defaultItem", "provisioningType", "supportsEncryption", "tags"),
        )
    elif kind == "ImageProfile":
        spec = _copy_fields(remote, ("name", "description", "regionId", "externalRegionId", "imageMappings", "imageMapping"))
        if "imageMapping" in spec and "imageMappings" not in spec:
            spec["imageMappings"] = spec.pop("imageMapping")
    elif kind == "Project":
        spec = _copy_fields(remote, ("name", "description", "zoneAssignments", "constraints", "properties"))
    else:
        raise InfrastructureError(f"지원하지 않는 리소스 kind입니다: {kind}")
    return _compact(spec)


def normalize_local(spec: dict[str, Any]) -> dict[str, Any]:
    return _compact(spec)


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "resource"


class InfrastructureService:
    def __init__(self, client, root: str | Path):
        self.client = client
        self.root = Path(root)

    def _response_json(self, response, operation: str) -> dict[str, Any]:
        if response.status_code == 403:
            raise InfrastructureError(f"권한 부족으로 {operation}을 완료하지 못했습니다. 불완전한 결과는 사용하지 않습니다.")
        if response.status_code >= 400:
            raise InfrastructureError(f"{operation} 실패: HTTP {response.status_code}: {response.text}")
        try:
            value = response.json()
        except ValueError as exc:
            raise InfrastructureError(f"{operation} 응답이 유효한 JSON이 아닙니다.") from exc
        if not isinstance(value, dict):
            raise InfrastructureError(f"{operation} 응답이 JSON 객체가 아닙니다.")
        return value

    def discover_kind(self, kind: str, page_size: int = 200) -> list[dict[str, Any]]:
        definition = RESOURCE_DEFINITIONS.get(kind)
        if not definition:
            raise InfrastructureError(f"지원하지 않는 리소스 kind입니다: {kind}")

        page = 0
        discovered: list[dict[str, Any]] = []
        while True:
            response = self.client.request("GET", definition.endpoint, params={"page": page, "size": page_size})
            payload = self._response_json(response, f"{kind} discovery")
            content = payload.get("content", [])
            if not isinstance(content, list):
                raise InfrastructureError(f"{kind} discovery 응답의 content가 목록이 아닙니다.")
            discovered.extend(item for item in content if isinstance(item, dict))

            total_elements = payload.get("totalElements")
            total_pages = payload.get("totalPages")
            if isinstance(total_elements, int) and len(discovered) >= total_elements:
                break
            if isinstance(total_pages, int) and page + 1 >= total_pages:
                break
            if len(content) < page_size or not content:
                break
            page += 1
        return discovered

    def discover(self, kinds: Iterable[str] | None = None) -> dict[str, list[dict[str, Any]]]:
        selected = list(kinds or RESOURCE_DEFINITIONS)
        return {
            kind: [
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "spec": normalize_remote(kind, item),
                }
                for item in self.discover_kind(kind)
            ]
            for kind in selected
        }

    def discover_selectors(self, kinds: Iterable[str] | None = None) -> list[tuple[str, str]]:
        """전체 adopt에 사용할 리소스 선택자를 fail-closed 방식으로 만든다."""
        selectors: list[tuple[str, str]] = []
        for kind in list(kinds or RESOURCE_DEFINITIONS):
            for item in self.discover_kind(kind):
                remote_id = item.get("id")
                if not isinstance(remote_id, str) or not remote_id:
                    raise InfrastructureError(f"{kind} discovery 결과에 유효한 id가 없습니다. 전체 adopt를 중단합니다.")
                selectors.append((kind, remote_id))
        return selectors

    def get_remote(self, kind: str, remote_id: str) -> dict[str, Any] | None:
        definition = RESOURCE_DEFINITIONS.get(kind)
        if not definition:
            raise InfrastructureError(f"지원하지 않는 리소스 kind입니다: {kind}")
        response = self.client.request("GET", f"{definition.endpoint}/{remote_id}")
        if response.status_code == 404:
            return None
        return self._response_json(response, f"{kind}/{remote_id} 조회")

    def plan_adopt(self, selectors: Iterable[tuple[str, str]], force: bool = False) -> list[dict[str, Any]]:
        """파일을 쓰기 전에 모든 상세 조회와 충돌 검사를 완료한다."""
        existing_by_identity: dict[tuple[str, str], Path] = {}
        for existing_path, existing in self.load_manifests():
            metadata = existing.get("metadata") or {}
            remote_id = metadata.get("remoteId")
            if isinstance(existing.get("kind"), str) and isinstance(remote_id, str):
                existing_by_identity[(existing["kind"], remote_id)] = existing_path

        plan: list[dict[str, Any]] = []
        seen_selectors: set[tuple[str, str]] = set()
        reserved_paths: dict[Path, tuple[str, str]] = {}
        for kind, remote_id in selectors:
            definition = RESOURCE_DEFINITIONS.get(kind)
            if not definition:
                raise InfrastructureError(f"지원하지 않는 리소스 kind입니다: {kind}")
            identity = (kind, remote_id)
            if identity in seen_selectors:
                continue
            seen_selectors.add(identity)
            if identity in existing_by_identity:
                plan.append(
                    {
                        "action": "SKIP",
                        "kind": kind,
                        "remoteId": remote_id,
                        "path": existing_by_identity[identity],
                        "reason": "already-adopted",
                    }
                )
                continue

            remote = self.get_remote(kind, remote_id)
            if remote is None:
                raise InfrastructureError(f"원격 리소스를 찾을 수 없습니다: {kind}/{remote_id}")
            remote_name = str(remote.get("name") or remote_id)
            logical_name = slugify(remote_name)
            destination = self.root / definition.directory / f"{logical_name}.yaml"
            spec = normalize_remote(kind, remote)
            if not isinstance(spec.get("name"), str) or not spec["name"]:
                raise InfrastructureError(f"{kind}/{remote_id} 상세 응답에 name이 없어 adopt를 중단합니다.")
            manifest = {
                "apiVersion": API_VERSION,
                "kind": kind,
                "metadata": {"name": logical_name, "remoteId": remote_id},
                "spec": spec,
            }

            conflicting_identity = reserved_paths.get(destination)
            if conflicting_identity and conflicting_identity != identity:
                plan.append(
                    {
                        "action": "CONFLICT",
                        "kind": kind,
                        "remoteId": remote_id,
                        "path": destination,
                        "reason": "duplicate-generated-path",
                    }
                )
                continue
            reserved_paths[destination] = identity

            if destination.exists() and not force:
                plan.append(
                    {
                        "action": "CONFLICT",
                        "kind": kind,
                        "remoteId": remote_id,
                        "path": destination,
                        "reason": "path-exists",
                    }
                )
                continue
            plan.append(
                {
                    "action": "OVERWRITE" if destination.exists() else "CREATE",
                    "kind": kind,
                    "remoteId": remote_id,
                    "path": destination,
                    "manifest": manifest,
                }
            )
        return plan

    def apply_adopt_plan(self, plan: Iterable[dict[str, Any]]) -> list[Path]:
        """충돌 없는 adopt plan의 로컬 manifest만 생성한다."""
        plan = list(plan)
        conflicts = [item for item in plan if item["action"] == "CONFLICT"]
        if conflicts:
            raise InfrastructureError("adopt 충돌이 있어 manifest를 생성하지 않았습니다.")
        created: list[Path] = []
        for item in plan:
            if item["action"] not in {"CREATE", "OVERWRITE"}:
                continue
            destination = item["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(
                yaml.safe_dump(item["manifest"], allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            created.append(destination)
        return created

    def adopt(self, kind: str, remote_id: str, force: bool = False) -> Path:
        plan = self.plan_adopt([(kind, remote_id)], force=force)
        if plan[0]["action"] == "SKIP":
            raise InfrastructureError(f"이미 채택된 원격 리소스입니다: {kind}/{remote_id}: {plan[0]['path']}")
        created = self.apply_adopt_plan(plan)
        return created[0]

    def load_manifests(self) -> list[tuple[Path, dict[str, Any]]]:
        manifests: list[tuple[Path, dict[str, Any]]] = []
        if not self.root.exists():
            return manifests
        for path in sorted(self.root.glob("*/*.yaml")):
            try:
                value = yaml.safe_load(path.read_text(encoding="utf-8"))
            except yaml.YAMLError as exc:
                raise InfrastructureError(f"YAML 형식이 올바르지 않습니다: {path}: {exc}") from exc
            if not isinstance(value, dict):
                raise InfrastructureError(f"manifest 최상위 값은 객체여야 합니다: {path}")
            manifests.append((path, value))
        return manifests

    def validate_manifest(self, path: Path, manifest: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        kind = manifest.get("kind")
        metadata = manifest.get("metadata")
        spec = manifest.get("spec")
        if manifest.get("apiVersion") != API_VERSION:
            errors.append(f"{path}: 지원하지 않는 apiVersion: {manifest.get('apiVersion')!r}")
        if kind not in RESOURCE_DEFINITIONS:
            errors.append(f"{path}: 지원하지 않는 kind: {kind!r}")
        if not isinstance(metadata, dict) or not isinstance(metadata.get("name"), str):
            errors.append(f"{path}: metadata.name이 필요합니다.")
        elif metadata["name"] != slugify(metadata["name"]):
            errors.append(f"{path}: metadata.name은 소문자 kebab-case여야 합니다.")
        if isinstance(metadata, dict) and "remoteId" in metadata and not isinstance(metadata["remoteId"], str):
            errors.append(f"{path}: metadata.remoteId는 문자열이어야 합니다.")
        if not isinstance(spec, dict) or not isinstance(spec.get("name"), str):
            errors.append(f"{path}: spec.name이 필요합니다.")
        if kind in RESOURCE_DEFINITIONS:
            expected_parent = RESOURCE_DEFINITIONS[kind].directory
            if path.parent.name != expected_parent:
                errors.append(f"{path}: {kind} manifest는 infrastructure/{expected_parent}/에 있어야 합니다.")
        return errors

    def validate(self) -> list[str]:
        errors: list[str] = []
        identities: dict[tuple[str, str], Path] = {}
        for path, manifest in self.load_manifests():
            errors.extend(self.validate_manifest(path, manifest))
            kind = manifest.get("kind")
            remote_id = (manifest.get("metadata") or {}).get("remoteId")
            if isinstance(kind, str) and isinstance(remote_id, str):
                identity = (kind, remote_id)
                if identity in identities:
                    errors.append(f"{path}: remoteId가 {identities[identity]}와 중복됩니다: {kind}/{remote_id}")
                identities[identity] = path
        return errors

    def status(self) -> list[dict[str, Any]]:
        validation_errors = self.validate()
        if validation_errors:
            raise InfrastructureError("manifest 검증 실패:\n" + "\n".join(validation_errors))

        results: list[dict[str, Any]] = []
        for path, manifest in self.load_manifests():
            kind = manifest["kind"]
            metadata = manifest["metadata"]
            remote_id = metadata.get("remoteId")
            base = {"kind": kind, "name": metadata["name"], "path": str(path)}
            if not remote_id:
                results.append({**base, "state": "CREATE_PENDING"})
                continue
            remote = self.get_remote(kind, remote_id)
            if remote is None:
                results.append({**base, "remoteId": remote_id, "state": "REMOTE_MISSING"})
                continue
            local_spec = normalize_local(manifest["spec"])
            remote_spec = normalize_remote(kind, remote)
            if local_spec == remote_spec:
                results.append({**base, "remoteId": remote_id, "state": "IN_SYNC"})
            else:
                results.append(
                    {
                        **base,
                        "remoteId": remote_id,
                        "state": "MODIFIED",
                        "local": local_spec,
                        "remote": remote_spec,
                    }
                )
        return results
