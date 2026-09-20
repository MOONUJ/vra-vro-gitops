# -*- coding: utf-8 -*-
"""Automation과 Orchestrator 콘텐츠의 불변 plan, apply와 verify."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from content_pull import tree_hash


PLAN_API_VERSION = "gitops.vcf.example/v1alpha1"
PLAN_KIND = "ContentChangePlan"
RESULT_KIND = "ContentApplyResult"


class ContentPlanError(RuntimeError):
    """콘텐츠 plan 또는 apply 계약을 위반했을 때 발생한다."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def approval_key(operation: dict[str, Any]) -> str:
    return f"{operation['product']}:{operation['type']}:{operation['identity']}"


def operations_from_observation(observation: dict[str, Any], products: Iterable[str]) -> list[dict[str, Any]]:
    if not observation.get("metadata", {}).get("complete"):
        raise ContentPlanError("불완전한 observation으로 콘텐츠 plan을 만들 수 없습니다.")
    selected = set(products)
    operations: list[dict[str, Any]] = []
    product_results = observation.get("spec", {}).get("products", {})
    for product in sorted(selected):
        result = product_results.get(product)
        if not isinstance(result, dict) or result.get("state") != "COMPLETE":
            raise ContentPlanError(f"{product} observation이 완전하지 않습니다.")
        for resource in result.get("resources", []):
            state = resource.get("state")
            if state not in {"MODIFIED", "LOCAL_ONLY"}:
                continue
            operation = {
                "action": "UPDATE" if state == "MODIFIED" else "CREATE",
                "product": product,
                "type": resource["type"],
                "identity": resource["identity"],
            }
            if resource.get("detail"):
                operation["detail"] = resource["detail"]
            operation["approvalKey"] = approval_key(operation)
            operations.append(operation)
    return sorted(operations, key=lambda item: (item["product"], item["type"], item["identity"], item["action"]))


class ContentPlanService:
    def __init__(
        self,
        content_root: str | Path,
        plans_root: str | Path,
        results_root: str | Path,
        locks_root: str | Path,
        target: dict[str, Any],
        tool_version: str,
        git_commit: str,
        policy_hash: str = "",
        now: Callable[[], datetime] = _utc_now,
    ):
        self.content_root = Path(content_root)
        self.plans_root = Path(plans_root)
        self.results_root = Path(results_root)
        self.locks_root = Path(locks_root)
        self.target = target
        self.tool_version = tool_version
        self.git_commit = git_commit
        self.policy_hash = policy_hash
        self.now = now

    @staticmethod
    def validate_artifact(artifact: dict[str, Any]) -> None:
        if artifact.get("apiVersion") != PLAN_API_VERSION or artifact.get("kind") != PLAN_KIND:
            raise ContentPlanError("지원하지 않는 콘텐츠 plan artifact입니다.")
        metadata = artifact.get("metadata")
        spec = artifact.get("spec")
        if not isinstance(metadata, dict) or not isinstance(spec, dict):
            raise ContentPlanError("콘텐츠 plan metadata와 spec이 필요합니다.")
        plan_hash = metadata.get("planHash")
        body = {**artifact, "metadata": {key: value for key, value in metadata.items() if key != "planHash"}}
        if not isinstance(plan_hash, str) or _hash(body) != plan_hash:
            raise ContentPlanError("콘텐츠 plan hash가 artifact 내용과 일치하지 않습니다.")

    def create_plan(
        self,
        observation: dict[str, Any],
        lifecycle: str,
        products: Iterable[str],
        resource_selectors: Iterable[str],
        expires_in_seconds: int = 1800,
    ) -> tuple[Path, dict[str, Any]]:
        if lifecycle not in {"day1", "day2"}:
            raise ContentPlanError("콘텐츠 plan lifecycle은 day1 또는 day2여야 합니다.")
        if expires_in_seconds < 60:
            raise ContentPlanError("plan 만료 시간은 최소 60초여야 합니다.")
        products = sorted(set(products))
        if not products or any(product not in {"automation", "orchestrator"} for product in products):
            raise ContentPlanError("지원되는 product를 하나 이상 선택해야 합니다.")
        operations = operations_from_observation(observation, products)
        selectors = set(resource_selectors)
        if not selectors:
            raise ContentPlanError("콘텐츠 plan은 --resource product:type:identity를 하나 이상 명시해야 합니다.")
        available = {operation["approvalKey"] for operation in operations}
        missing = sorted(selectors - available)
        if missing:
            raise ContentPlanError(f"현재 drift에 없는 콘텐츠 선택자입니다: {', '.join(missing)}")
        operations = [operation for operation in operations if operation["approvalKey"] in selectors]
        current_time = self.now()
        metadata = {
            "createdAt": _timestamp(current_time),
            "expiresAt": _timestamp(current_time + timedelta(seconds=expires_in_seconds)),
            "toolVersion": self.tool_version,
        }
        spec = {
            "target": self.target,
            "gitCommit": self.git_commit,
            "lifecycle": lifecycle,
            "products": products,
            "resourceSelectors": sorted(selectors),
            "contentHash": tree_hash(self.content_root),
            "observationHash": _hash(observation),
            "observation": observation,
            "operations": operations,
            "policyHash": self.policy_hash,
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
            raise ContentPlanError(f"기존 콘텐츠 plan을 덮어쓰지 않습니다: {path}") from exc
        return path, artifact

    def load_plan(self, path: str | Path) -> dict[str, Any]:
        try:
            artifact = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ContentPlanError(f"콘텐츠 plan을 읽지 못했습니다: {path}: {exc}") from exc
        if not isinstance(artifact, dict):
            raise ContentPlanError("콘텐츠 plan 최상위 값은 객체여야 합니다.")
        self.validate_artifact(artifact)
        return artifact

    def _assert_current(
        self,
        artifact: dict[str, Any],
        approval: str,
        current_observation: dict[str, Any],
        current_git_commit: str,
    ) -> None:
        metadata = artifact["metadata"]
        spec = artifact["spec"]
        if approval != metadata["planHash"]:
            raise ContentPlanError("승인 hash가 콘텐츠 plan hash와 일치하지 않습니다.")
        if _parse_timestamp(metadata["expiresAt"]) <= self.now():
            raise ContentPlanError("콘텐츠 plan이 만료되었습니다.")
        if spec.get("target") != self.target:
            raise ContentPlanError("콘텐츠 plan 대상 인스턴스가 현재 설정과 일치하지 않습니다.")
        if spec.get("policyHash", "") != self.policy_hash:
            raise ContentPlanError("콘텐츠 plan 생성 후 GitOps policy가 변경되었습니다.")
        if spec.get("gitCommit") != current_git_commit:
            raise ContentPlanError("콘텐츠 plan 생성 후 Git commit이 변경되었습니다.")
        if spec.get("contentHash") != tree_hash(self.content_root):
            raise ContentPlanError("콘텐츠 plan 생성 후 local content가 변경되었습니다.")
        if not current_observation.get("metadata", {}).get("complete"):
            raise ContentPlanError("현재 원격 observation이 불완전합니다.")
        if spec.get("observationHash") != _hash(current_observation):
            raise ContentPlanError("콘텐츠 plan 생성 후 원격 상태가 변경되었습니다.")

    def _lock_path(self) -> Path:
        name = str(self.target.get("name") or "instance")
        safe_name = "".join(character if character.isalnum() or character in "-." else "-" for character in name)
        return self.locks_root / f"{safe_name}.lock"

    def apply(
        self,
        artifact: dict[str, Any],
        approval: str,
        approved_creations: Iterable[str],
        current_observation: dict[str, Any],
        current_git_commit: str,
        executor: Callable[[dict[str, Any]], None],
        verifier: Callable[[dict[str, Any]], bool],
    ) -> tuple[Path, dict[str, Any]]:
        self.validate_artifact(artifact)
        operations = artifact["spec"].get("operations", [])
        required_creations = {item["approvalKey"] for item in operations if item["action"] == "CREATE"}
        if set(approved_creations) != required_creations:
            raise ContentPlanError("생성 승인은 콘텐츠 plan의 CREATE 대상과 정확히 일치해야 합니다.")
        self._assert_current(artifact, approval, current_observation, current_git_commit)
        plan_hash = artifact["metadata"]["planHash"]
        self.results_root.mkdir(parents=True, exist_ok=True)
        result_path = self.results_root / f"{plan_hash}.json"
        if result_path.exists():
            raise ContentPlanError(f"이미 실행 결과가 있는 콘텐츠 plan입니다: {result_path}")

        self.locks_root.mkdir(parents=True, exist_ok=True)
        lock_path = self._lock_path()
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise ContentPlanError(f"다른 콘텐츠 apply가 실행 중입니다: {lock_path}") from exc
        journal_path = self.results_root / f"{plan_hash}.in-progress.json"
        results: list[dict[str, Any]] = []
        failed = False
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as lock_file:
                lock_file.write(plan_hash + "\n")
            journal = {
                "apiVersion": PLAN_API_VERSION,
                "kind": "ContentApplyJournal",
                "metadata": {"startedAt": _timestamp(self.now()), "planHash": plan_hash},
                "spec": {"target": self.target, "status": "IN_PROGRESS"},
            }
            with journal_path.open("x", encoding="utf-8") as output:
                json.dump(journal, output, ensure_ascii=False, indent=2, sort_keys=True)
                output.write("\n")

            for index, operation in enumerate(operations):
                try:
                    executor(operation)
                    if not verifier(operation):
                        raise ContentPlanError("적용 후 원하는 상태로 수렴하지 않았습니다.")
                    results.append({**operation, "status": "VERIFIED"})
                except Exception as exc:
                    results.append({**operation, "status": "FAILED", "error": str(exc)})
                    for remaining in operations[index + 1 :]:
                        results.append({**remaining, "status": "NOT_RUN"})
                    failed = True
                    break

            result = {
                "apiVersion": PLAN_API_VERSION,
                "kind": RESULT_KIND,
                "metadata": {"appliedAt": _timestamp(self.now()), "planHash": plan_hash},
                "spec": {
                    "target": self.target,
                    "status": "FAILED" if failed else "VERIFIED",
                    "operations": results,
                },
            }
            with result_path.open("x", encoding="utf-8") as output:
                json.dump(result, output, ensure_ascii=False, indent=2, sort_keys=True)
                output.write("\n")
            journal_path.unlink()
            return result_path, result
        finally:
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass
