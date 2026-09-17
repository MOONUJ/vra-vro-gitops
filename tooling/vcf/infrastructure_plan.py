# -*- coding: utf-8 -*-
"""Native 인프라 변경 plan, 승인된 apply와 verify를 담당한다."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.parse import unquote, urlparse

import yaml

from infrastructure import InfrastructureError, InfrastructureService, RESOURCE_DEFINITIONS, normalize_local, normalize_remote


PLAN_API_VERSION = "gitops.vcf.example/v1alpha1"
PLAN_KIND = "InfrastructurePlan"
RESULT_KIND = "InfrastructureApplyResult"

MUTATION_CAPABILITIES = {
    "Project": {"create": ("POST", "/iaas/api/projects"), "update": ("PATCH", "/iaas/api/projects/{id}")},
    "NetworkProfile": {
        "create": ("POST", "/iaas/api/network-profiles"),
        "update": ("PATCH", "/iaas/api/network-profiles/{id}"),
    },
    "StorageProfile": {"update": ("PUT", "/iaas/api/storage-profiles/{id}")},
    "ImageProfile": {
        "create": ("POST", "/iaas/api/image-profiles"),
        "update": ("PATCH", "/iaas/api/image-profiles/{id}"),
    },
}

MUTABLE_SPEC_FIELDS = {
    "Project": {
        "administrators",
        "constraints",
        "description",
        "machineNamingTemplate",
        "members",
        "name",
        "operationTimeout",
        "sharedResources",
        "zoneAssignmentConfigurations",
        "zoneAssignments",
        "zones",
    },
    "NetworkProfile": {
        "customProperties",
        "description",
        "fabricNetworkIds",
        "isolationExternalFabricNetworkId",
        "isolationNetworkDomainCIDR",
        "isolationNetworkDomainId",
        "isolationType",
        "isolatedNetworkCIDRPrefix",
        "name",
        "regionId",
        "securityGroupIds",
        "tags",
    },
    "StorageProfile": {
        "defaultItem",
        "description",
        "diskProperties",
        "diskTargetProperties",
        "name",
        "regionId",
        "supportsEncryption",
        "tags",
    },
    "ImageProfile": {"description", "imageMapping", "imageMappings", "name", "regionId"},
}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _project_payload(spec: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "administrators",
        "constraints",
        "description",
        "machineNamingTemplate",
        "members",
        "name",
        "operationTimeout",
        "sharedResources",
        "zoneAssignmentConfigurations",
    }
    payload = {key: value for key, value in spec.items() if key in allowed}
    assignments = spec.get("zoneAssignmentConfigurations", spec.get("zoneAssignments", spec.get("zones")))
    if assignments is not None:
        payload["zoneAssignmentConfigurations"] = assignments
    return payload


def _region_id(remote: dict[str, Any] | None) -> str | None:
    if not remote:
        return None
    if isinstance(remote.get("regionId"), str):
        return remote["regionId"]
    relation = (remote.get("_links") or {}).get("region")
    if isinstance(relation, list):
        relation = relation[0] if relation else None
    href = relation.get("href") if isinstance(relation, dict) else relation
    if not isinstance(href, str) or not href:
        return None
    return unquote(urlparse(href).path.rstrip("/").rsplit("/", 1)[-1])


def _network_profile_payload(spec: dict[str, Any], remote: dict[str, Any] | None) -> dict[str, Any]:
    allowed = {
        "customProperties",
        "description",
        "fabricNetworkIds",
        "isolationExternalFabricNetworkId",
        "isolationNetworkDomainCIDR",
        "isolationNetworkDomainId",
        "isolationType",
        "isolatedNetworkCIDRPrefix",
        "name",
        "regionId",
        "securityGroupIds",
        "tags",
    }
    payload = {key: value for key, value in spec.items() if key in allowed}
    if "regionId" not in payload and _region_id(remote):
        payload["regionId"] = _region_id(remote)
    return payload


def _storage_profile_payload(spec: dict[str, Any], remote: dict[str, Any] | None) -> dict[str, Any]:
    allowed = {
        "defaultItem",
        "description",
        "diskProperties",
        "diskTargetProperties",
        "name",
        "regionId",
        "supportsEncryption",
        "tags",
    }
    payload = {key: value for key, value in spec.items() if key in allowed}
    if "regionId" not in payload and _region_id(remote):
        payload["regionId"] = _region_id(remote)
    return payload


def _image_profile_payload(spec: dict[str, Any], creating: bool) -> dict[str, Any]:
    mappings = spec.get("imageMapping", spec.get("imageMappings"))
    if isinstance(mappings, dict) and "mapping" in mappings:
        mappings = mappings["mapping"]
    if isinstance(mappings, dict):
        normalized_mappings = {}
        for name, mapping in mappings.items():
            if not isinstance(mapping, dict):
                normalized_mappings[name] = mapping
                continue
            image_id = mapping.get("id", mapping.get("externalId"))
            normalized_mappings[name] = {
                key: value
                for key, value in {"id": image_id, "name": mapping.get("name")}.items()
                if value is not None
            }
        mappings = normalized_mappings
    payload = {key: spec[key] for key in ("name", "description") if key in spec}
    if mappings is not None:
        payload["imageMapping"] = mappings
    if creating and "regionId" in spec:
        payload["regionId"] = spec["regionId"]
    return payload


def mutation_payload(
    kind: str,
    spec: dict[str, Any],
    action: str,
    remote: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Canonical manifest spec을 공식 IaaS mutation payload로 변환한다."""
    creating = action == "CREATE"
    if kind == "Project":
        payload = _project_payload(spec)
        required = ("name",)
    elif kind == "NetworkProfile":
        payload = _network_profile_payload(spec, remote)
        required = ("name", "regionId")
    elif kind == "StorageProfile":
        payload = _storage_profile_payload(spec, remote)
        required = ("name", "regionId", "defaultItem")
    elif kind == "ImageProfile":
        payload = _image_profile_payload(spec, creating)
        required = ("name", "imageMapping") + (("regionId",) if creating else ())
    else:
        raise InfrastructureError(f"native mutation을 지원하지 않는 kind입니다: {kind}")

    missing = [key for key in required if key not in payload]
    if missing:
        raise InfrastructureError(f"{kind} {action} payload에 필수 필드가 없습니다: {', '.join(missing)}")
    return payload


def validate_mutable_changes(kind: str, before: dict[str, Any] | None, after: dict[str, Any], action: str) -> None:
    supported = MUTABLE_SPEC_FIELDS.get(kind, set())
    if action == "CREATE":
        changed = set(after)
    else:
        before = before or {}
        changed = {key for key in set(before) | set(after) if before.get(key) != after.get(key)}
        omitted = sorted(key for key in changed if key in before and key not in after)
        if omitted:
            raise InfrastructureError(
                f"{kind} UPDATE에서 기존 필드를 manifest에서 생략해 제거할 수 없습니다. "
                f"명시적인 빈 값 지원이 필요합니다: {', '.join(omitted)}"
            )
        if kind == "ImageProfile":
            supported = supported - {"regionId"}
    unsupported = sorted(changed - supported)
    if unsupported:
        raise InfrastructureError(
            f"{kind} {action}에서 안전하게 변경할 수 없는 spec 필드가 있습니다: {', '.join(unsupported)}"
        )


class InfrastructurePlanService:
    def __init__(
        self,
        infrastructure: InfrastructureService,
        plans_root: str | Path,
        results_root: str | Path,
        instance: dict[str, Any],
        tool_version: str,
        now: Callable[[], datetime] = _utc_now,
    ):
        self.infrastructure = infrastructure
        self.plans_root = Path(plans_root)
        self.results_root = Path(results_root)
        self.instance = instance
        self.tool_version = tool_version
        self.now = now

    def _manifest_snapshot(self) -> tuple[str, list[tuple[Path, dict[str, Any]]]]:
        errors = self.infrastructure.validate()
        if errors:
            raise InfrastructureError("manifest 검증 실패:\n" + "\n".join(errors))
        manifests = self.infrastructure.load_manifests()
        snapshot = [
            {
                "path": str(path.relative_to(self.infrastructure.root)),
                "manifest": manifest,
            }
            for path, manifest in manifests
        ]
        return _hash(snapshot), manifests

    def _operation_for_manifest(self, path: Path, manifest: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        kind = manifest["kind"]
        metadata = manifest["metadata"]
        remote_id = metadata.get("remoteId")
        desired = normalize_local(manifest["spec"])
        base = {
            "kind": kind,
            "name": metadata["name"],
            "manifestPath": str(path.relative_to(self.infrastructure.root)),
            "remoteId": remote_id,
        }
        remote_context = None
        if remote_id:
            remote = self.infrastructure.get_remote(kind, remote_id)
            if remote is None:
                raise InfrastructureError(f"관리 중인 원격 리소스가 없습니다: {kind}/{remote_id}")
            observed = normalize_remote(kind, remote)
            remote_context = remote
            observation = {**base, "spec": observed}
            if desired == observed:
                return None, observation
            action = "UPDATE"
            capability = "update"
            before = observed
        else:
            observation = {**base, "spec": None, "desiredName": desired.get("name")}
            action = "CREATE"
            capability = "create"
            before = None

        capabilities = MUTATION_CAPABILITIES.get(kind, {})
        if capability not in capabilities:
            raise InfrastructureError(f"{kind}은 native {action}를 지원하지 않습니다: {path}")
        validate_mutable_changes(kind, before, desired, action)
        payload = mutation_payload(kind, desired, action, remote_context)
        return {**base, "action": action, "before": before, "after": desired, "payload": payload}, observation

    def _load_reusable_plan(self, fingerprint: str, current_time: datetime) -> tuple[Path, dict[str, Any]] | None:
        if not self.plans_root.exists():
            return None
        for path in sorted(self.plans_root.glob("*.json")):
            try:
                artifact = json.loads(path.read_text(encoding="utf-8"))
                self.validate_artifact(artifact)
                if artifact["spec"].get("fingerprint") != fingerprint:
                    continue
                if _parse_timestamp(artifact["metadata"]["expiresAt"]) <= current_time:
                    continue
                return path, artifact
            except (InfrastructureError, KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue
        return None

    def create_plan(
        self,
        delete_selectors: Iterable[tuple[str, str]] = (),
        expires_in_seconds: int = 1800,
    ) -> tuple[Path, dict[str, Any], bool]:
        if expires_in_seconds < 60:
            raise InfrastructureError("plan 만료 시간은 최소 60초여야 합니다.")
        manifest_hash, manifests = self._manifest_snapshot()
        operations: list[dict[str, Any]] = []
        observations: list[dict[str, Any]] = []
        managed = {
            (manifest["kind"], (manifest.get("metadata") or {}).get("remoteId"))
            for _, manifest in manifests
        }
        for path, manifest in manifests:
            operation, observation = self._operation_for_manifest(path, manifest)
            observations.append(observation)
            if operation:
                operations.append(operation)

        for kind, remote_id in sorted(set(delete_selectors)):
            if kind not in RESOURCE_DEFINITIONS:
                raise InfrastructureError(f"지원하지 않는 kind입니다: {kind}")
            if "update" not in MUTATION_CAPABILITIES.get(kind, {}):
                raise InfrastructureError(f"{kind}은 native DELETE를 지원하지 않습니다.")
            if (kind, remote_id) in managed:
                raise InfrastructureError(f"manifest가 남아 있는 리소스는 삭제 plan을 만들 수 없습니다: {kind}/{remote_id}")
            remote = self.infrastructure.get_remote(kind, remote_id)
            if remote is None:
                raise InfrastructureError(f"삭제할 원격 리소스를 찾을 수 없습니다: {kind}/{remote_id}")
            observed = normalize_remote(kind, remote)
            observations.append({"kind": kind, "remoteId": remote_id, "spec": observed})
            operations.append(
                {
                    "action": "DELETE",
                    "kind": kind,
                    "name": observed.get("name", remote_id),
                    "manifestPath": None,
                    "remoteId": remote_id,
                    "before": observed,
                    "after": None,
                    "payload": None,
                }
            )

        operations.sort(key=lambda item: (item["kind"], item["name"], item["action"]))
        observations.sort(key=lambda item: (item["kind"], item.get("name", ""), item.get("remoteId") or ""))
        observation_hash = _hash(observations)
        fingerprint = _hash(
            {
                "instance": self.instance,
                "manifestHash": manifest_hash,
                "observationHash": observation_hash,
                "operations": operations,
            }
        )
        current_time = self.now()
        reusable = self._load_reusable_plan(fingerprint, current_time)
        if reusable:
            path, artifact = reusable
            return path, artifact, True

        metadata = {
            "createdAt": _timestamp(current_time),
            "expiresAt": _timestamp(current_time + timedelta(seconds=expires_in_seconds)),
            "toolVersion": self.tool_version,
        }
        spec = {
            "instance": self.instance,
            "manifestHash": manifest_hash,
            "observationHash": observation_hash,
            "observations": observations,
            "fingerprint": fingerprint,
            "operations": operations,
        }
        body = {"apiVersion": PLAN_API_VERSION, "kind": PLAN_KIND, "metadata": metadata, "spec": spec}
        plan_hash = _hash(body)
        artifact = {**body, "metadata": {**metadata, "planHash": plan_hash}}
        self.plans_root.mkdir(parents=True, exist_ok=True)
        path = self.plans_root / f"{plan_hash}.json"
        try:
            with path.open("x", encoding="utf-8") as output:
                json.dump(artifact, output, ensure_ascii=False, indent=2, sort_keys=True)
                output.write("\n")
        except FileExistsError as exc:
            raise InfrastructureError(f"기존 plan artifact를 덮어쓰지 않습니다: {path}") from exc
        return path, artifact, False

    @staticmethod
    def validate_artifact(artifact: dict[str, Any]) -> None:
        if artifact.get("apiVersion") != PLAN_API_VERSION or artifact.get("kind") != PLAN_KIND:
            raise InfrastructureError("지원하지 않는 plan artifact입니다.")
        metadata = artifact.get("metadata")
        spec = artifact.get("spec")
        if not isinstance(metadata, dict) or not isinstance(spec, dict):
            raise InfrastructureError("plan metadata와 spec이 필요합니다.")
        plan_hash = metadata.get("planHash")
        body = {**artifact, "metadata": {key: value for key, value in metadata.items() if key != "planHash"}}
        if not isinstance(plan_hash, str) or _hash(body) != plan_hash:
            raise InfrastructureError("plan hash가 artifact 내용과 일치하지 않습니다.")

    def load_plan(self, path: str | Path) -> dict[str, Any]:
        try:
            artifact = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise InfrastructureError(f"plan artifact를 읽지 못했습니다: {path}: {exc}") from exc
        if not isinstance(artifact, dict):
            raise InfrastructureError("plan artifact 최상위 값은 객체여야 합니다.")
        self.validate_artifact(artifact)
        return artifact

    def _assert_plan_is_current(self, artifact: dict[str, Any], approval: str) -> None:
        metadata = artifact["metadata"]
        spec = artifact["spec"]
        if approval != metadata["planHash"]:
            raise InfrastructureError("승인 hash가 plan hash와 일치하지 않습니다.")
        if _parse_timestamp(metadata["expiresAt"]) <= self.now():
            raise InfrastructureError("plan이 만료되었습니다. 원격을 다시 관찰해 새 plan을 만드세요.")
        if spec.get("instance") != self.instance:
            raise InfrastructureError("plan 대상 인스턴스가 현재 설정과 일치하지 않습니다.")
        manifest_hash, _ = self._manifest_snapshot()
        if manifest_hash != spec.get("manifestHash"):
            raise InfrastructureError("plan 생성 후 manifest가 변경되었습니다. 새 plan이 필요합니다.")

        observations = spec.get("observations")
        if not isinstance(observations, list) or _hash(observations) != spec.get("observationHash"):
            raise InfrastructureError("plan의 원격 관찰 정보가 유효하지 않습니다.")
        for observation in observations:
            kind = observation["kind"]
            remote_id = observation.get("remoteId")
            if not remote_id:
                desired_name = observation.get("desiredName")
                for remote in self.infrastructure.discover_kind(kind):
                    if normalize_remote(kind, remote).get("name") == desired_name:
                        raise InfrastructureError(f"plan 이후 같은 이름의 원격 리소스가 생겼습니다: {kind}/{desired_name}")
                continue
            remote = self.infrastructure.get_remote(kind, remote_id)
            if remote is None or normalize_remote(kind, remote) != observation.get("spec"):
                raise InfrastructureError(f"plan 이후 원격 상태가 변경되었습니다: {kind}/{remote_id}")

    def _write_remote_id(self, operation: dict[str, Any], remote_id: str) -> None:
        relative_path = operation.get("manifestPath")
        if not relative_path:
            raise InfrastructureError("CREATE 작업에 manifestPath가 없습니다.")
        path = self.infrastructure.root / relative_path
        manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
        manifest.setdefault("metadata", {})["remoteId"] = remote_id
        path.write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def _execute(self, operation: dict[str, Any]) -> str | None:
        action = operation["action"]
        kind = operation["kind"]
        remote_id = operation.get("remoteId")
        definition = RESOURCE_DEFINITIONS[kind]
        if action == "DELETE":
            response = self.infrastructure.client.request("DELETE", f"{definition.endpoint}/{remote_id}")
            if response.status_code >= 400:
                raise InfrastructureError(f"{kind}/{remote_id} DELETE 실패: HTTP {response.status_code}: {response.text}")
            if self.infrastructure.get_remote(kind, remote_id) is not None:
                raise InfrastructureError(f"{kind}/{remote_id} DELETE 후 원격 리소스가 남아 있습니다.")
            return remote_id

        capability = MUTATION_CAPABILITIES[kind][action.lower()]
        method, path_template = capability
        path = path_template.format(id=remote_id)
        response = self.infrastructure.client.request(method, path, json=operation["payload"])
        result = self.infrastructure._response_json(response, f"{kind} {action}")
        if action == "CREATE":
            remote_id = result.get("id")
            if not isinstance(remote_id, str) or not remote_id:
                raise InfrastructureError(f"{kind} CREATE 응답에 id가 없습니다.")
            operation["remoteId"] = remote_id
            self._write_remote_id(operation, remote_id)

        verified = self.infrastructure.get_remote(kind, remote_id)
        if verified is None or normalize_remote(kind, verified) != operation["after"]:
            raise InfrastructureError(f"{kind}/{remote_id} {action} 후 원하는 상태로 수렴하지 않았습니다.")
        return remote_id

    def apply(
        self,
        artifact: dict[str, Any],
        approval: str,
        approved_deletions: Iterable[tuple[str, str]] = (),
    ) -> tuple[Path, dict[str, Any]]:
        self.validate_artifact(artifact)
        plan_hash = artifact["metadata"]["planHash"]
        approved_deletions = set(approved_deletions)
        required_deletions = {
            (operation["kind"], operation["remoteId"])
            for operation in artifact["spec"]["operations"]
            if operation["action"] == "DELETE"
        }
        if approved_deletions != required_deletions:
            raise InfrastructureError("삭제 승인은 plan의 DELETE 대상과 정확히 일치해야 합니다.")
        self._assert_plan_is_current(artifact, approval)

        self.results_root.mkdir(parents=True, exist_ok=True)
        result_path = self.results_root / f"{plan_hash}.json"
        if result_path.exists():
            raise InfrastructureError(f"이미 실행 결과가 있는 plan은 다시 apply하지 않습니다: {result_path}")

        operations = artifact["spec"]["operations"]
        results: list[dict[str, Any]] = []
        failed = False
        for index, operation in enumerate(operations):
            try:
                remote_id = self._execute(operation)
                results.append(
                    {
                        "action": operation["action"],
                        "kind": operation["kind"],
                        "name": operation["name"],
                        "remoteId": remote_id,
                        "status": "VERIFIED",
                    }
                )
            except (InfrastructureError, OSError, yaml.YAMLError) as exc:
                results.append(
                    {
                        "action": operation["action"],
                        "kind": operation["kind"],
                        "name": operation["name"],
                        "remoteId": operation.get("remoteId"),
                        "status": "FAILED",
                        "error": str(exc),
                    }
                )
                for remaining in operations[index + 1 :]:
                    results.append(
                        {
                            "action": remaining["action"],
                            "kind": remaining["kind"],
                            "name": remaining["name"],
                            "remoteId": remaining.get("remoteId"),
                            "status": "NOT_RUN",
                        }
                    )
                failed = True
                break

        result = {
            "apiVersion": PLAN_API_VERSION,
            "kind": RESULT_KIND,
            "metadata": {"appliedAt": _timestamp(self.now()), "planHash": plan_hash},
            "spec": {"instance": self.instance, "status": "FAILED" if failed else "VERIFIED", "operations": results},
        }
        with result_path.open("x", encoding="utf-8") as output:
            json.dump(result, output, ensure_ascii=False, indent=2, sort_keys=True)
            output.write("\n")
        return result_path, result
