# -*- coding: utf-8 -*-
"""Release restore의 불변 plan, 승인, apply와 verify."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from release_artifact import verify_release


PLAN_API_VERSION = "gitops.vcf.example/v1alpha1"
PLAN_KIND = "ReleaseRestorePlan"
RESULT_KIND = "ReleaseRestoreResult"


class RestorePlanError(RuntimeError):
    """restore plan 또는 apply 계약이 유효하지 않을 때 발생한다."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class RestorePlanService:
    def __init__(
        self,
        plans_root: str | Path,
        results_root: str | Path,
        locks_root: str | Path,
        target: dict[str, Any],
        tool_version: str,
        policy_hash: str = "",
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self.plans_root = Path(plans_root)
        self.results_root = Path(results_root)
        self.locks_root = Path(locks_root)
        self.target = target
        self.tool_version = tool_version
        self.policy_hash = policy_hash
        self.now = now

    @staticmethod
    def validate_artifact(artifact: dict[str, Any]) -> None:
        if artifact.get("apiVersion") != PLAN_API_VERSION or artifact.get("kind") != PLAN_KIND:
            raise RestorePlanError("지원하지 않는 restore plan입니다.")
        metadata = artifact.get("metadata")
        spec = artifact.get("spec")
        if not isinstance(metadata, dict) or not isinstance(spec, dict):
            raise RestorePlanError("restore plan metadata와 spec이 필요합니다.")
        plan_hash = metadata.get("planHash")
        body = {**artifact, "metadata": {key: value for key, value in metadata.items() if key != "planHash"}}
        if not isinstance(plan_hash, str) or _hash(body) != plan_hash:
            raise RestorePlanError("restore plan hash가 artifact 내용과 일치하지 않습니다.")

    def create_plan(
        self,
        release_path: str | Path,
        observation: dict[str, Any],
        expires_in_seconds: int = 1800,
    ) -> tuple[Path, dict[str, Any]]:
        if expires_in_seconds < 60:
            raise RestorePlanError("restore plan 만료 시간은 최소 60초여야 합니다.")
        if not observation.get("metadata", {}).get("complete"):
            raise RestorePlanError("불완전한 observation으로 restore plan을 만들 수 없습니다.")
        release_path = Path(release_path).resolve()
        release = verify_release(release_path)
        artifacts = release["spec"]["artifacts"]
        approvals = [f"artifact:{item['path']}:{item['sha256']}" for item in artifacts]
        current_time = self.now()
        metadata = {
            "createdAt": _timestamp(current_time),
            "expiresAt": _timestamp(current_time + timedelta(seconds=expires_in_seconds)),
            "toolVersion": self.tool_version,
        }
        spec = {
            "target": self.target,
            "releasePath": str(release_path),
            "releaseVersion": release["metadata"]["version"],
            "releaseManifestHash": _hash(release),
            "requiredApprovals": approvals,
            "observationHash": _hash(observation),
            "observation": observation,
            "operation": {"action": "RESTORE_RELEASE", "artifacts": artifacts},
            "policyHash": self.policy_hash,
        }
        body = {"apiVersion": PLAN_API_VERSION, "kind": PLAN_KIND, "metadata": metadata, "spec": spec}
        plan_hash = _hash(body)
        plan = {**body, "metadata": {**metadata, "planHash": plan_hash}}
        self.plans_root.mkdir(parents=True, exist_ok=True)
        path = self.plans_root / f"{plan_hash}.json"
        try:
            with path.open("x", encoding="utf-8") as output:
                json.dump(plan, output, ensure_ascii=False, indent=2, sort_keys=True)
                output.write("\n")
        except FileExistsError as exc:
            raise RestorePlanError(f"기존 restore plan을 덮어쓰지 않습니다: {path}") from exc
        return path, plan

    def load_plan(self, path: str | Path) -> dict[str, Any]:
        try:
            plan = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RestorePlanError(f"restore plan을 읽지 못했습니다: {path}: {exc}") from exc
        if not isinstance(plan, dict):
            raise RestorePlanError("restore plan 최상위 값은 객체여야 합니다.")
        self.validate_artifact(plan)
        return plan

    def apply(
        self,
        plan: dict[str, Any],
        approval: str,
        approved_artifacts: Iterable[str],
        current_observation: dict[str, Any],
        executor: Callable[[Path], None],
        verifier: Callable[[dict[str, Any]], bool],
    ) -> tuple[Path, dict[str, Any]]:
        self.validate_artifact(plan)
        metadata = plan["metadata"]
        spec = plan["spec"]
        if approval != metadata["planHash"]:
            raise RestorePlanError("승인 hash가 restore plan hash와 일치하지 않습니다.")
        if set(approved_artifacts) != set(spec["requiredApprovals"]):
            raise RestorePlanError("artifact 승인은 restore plan의 대상과 정확히 일치해야 합니다.")
        if _parse_timestamp(metadata["expiresAt"]) <= self.now():
            raise RestorePlanError("restore plan이 만료되었습니다.")
        if spec.get("target") != self.target:
            raise RestorePlanError("restore plan 대상 인스턴스가 현재 설정과 일치하지 않습니다.")
        if spec.get("policyHash", "") != self.policy_hash:
            raise RestorePlanError("restore plan 생성 후 GitOps policy가 변경되었습니다.")
        if not current_observation.get("metadata", {}).get("complete"):
            raise RestorePlanError("현재 원격 observation이 불완전합니다.")
        if spec.get("observationHash") != _hash(current_observation):
            raise RestorePlanError("restore plan 생성 후 원격 상태가 변경되었습니다.")
        release_path = Path(spec["releasePath"])
        release = verify_release(release_path)
        if _hash(release) != spec.get("releaseManifestHash"):
            raise RestorePlanError("restore plan 생성 후 release manifest가 변경되었습니다.")

        plan_hash = metadata["planHash"]
        self.results_root.mkdir(parents=True, exist_ok=True)
        result_path = self.results_root / f"{plan_hash}.json"
        if result_path.exists():
            raise RestorePlanError(f"이미 실행 결과가 있는 restore plan입니다: {result_path}")
        self.locks_root.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(
            character if character.isalnum() or character in "-." else "-"
            for character in str(self.target.get("name") or "instance")
        )
        lock_path = self.locks_root / f"{safe_name}.restore.lock"
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise RestorePlanError(f"다른 restore가 실행 중입니다: {lock_path}") from exc
        journal_path = self.results_root / f"{plan_hash}.in-progress.json"
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as lock_file:
                lock_file.write(plan_hash + "\n")
            journal = {
                "apiVersion": PLAN_API_VERSION,
                "kind": "ReleaseRestoreJournal",
                "metadata": {"startedAt": _timestamp(self.now()), "planHash": plan_hash},
                "spec": {"target": self.target, "status": "IN_PROGRESS"},
            }
            with journal_path.open("x", encoding="utf-8") as output:
                json.dump(journal, output, ensure_ascii=False, indent=2, sort_keys=True)
                output.write("\n")
            status = "VERIFIED"
            error = None
            try:
                executor(release_path)
                if not verifier(release):
                    raise RestorePlanError("restore 후 release 구성요소 검증에 실패했습니다.")
            except Exception as exc:
                status = "FAILED"
                error = str(exc)
            operation = {**spec["operation"], "status": status}
            if error:
                operation["error"] = error
            result = {
                "apiVersion": PLAN_API_VERSION,
                "kind": RESULT_KIND,
                "metadata": {"appliedAt": _timestamp(self.now()), "planHash": plan_hash},
                "spec": {"target": self.target, "status": status, "operation": operation},
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
