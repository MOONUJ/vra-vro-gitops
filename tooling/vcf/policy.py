# -*- coding: utf-8 -*-
"""GitOps plan에 적용하는 저장소 policy-as-code."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml


class PolicyError(RuntimeError):
    """정책 문서 또는 plan이 정책을 위반할 때 발생한다."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def policy_hash(policy: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(policy)).hexdigest()


def load_policy(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    try:
        policy = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise PolicyError(f"GitOps policy를 읽지 못했습니다: {path}: {exc}") from exc
    if not isinstance(policy, dict) or policy.get("kind") != "GitOpsPolicy":
        raise PolicyError(f"지원하지 않는 GitOps policy입니다: {path}")
    spec = policy.get("spec")
    if not isinstance(spec, dict):
        raise PolicyError("GitOps policy spec이 필요합니다.")
    try:
        re.compile(spec["productionPattern"])
    except (KeyError, re.error) as exc:
        raise PolicyError(f"productionPattern이 유효하지 않습니다: {exc}") from exc
    maximum = spec.get("maxPlanOperations")
    if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 1:
        raise PolicyError("maxPlanOperations는 1 이상의 정수여야 합니다.")
    return policy


def _operations(plan: dict[str, Any]) -> list[dict[str, Any]]:
    spec = plan.get("spec", {})
    operations = spec.get("operations")
    if isinstance(operations, list):
        return operations
    operation = spec.get("operation")
    return [operation] if isinstance(operation, dict) else []


def evaluate_plan(plan: dict[str, Any], policy: dict[str, Any], phase: str) -> None:
    """plan 생성과 apply 직전에 동일한 정책을 평가한다."""
    spec = policy["spec"]
    operations = _operations(plan)
    if len(operations) > spec["maxPlanOperations"]:
        raise PolicyError(
            f"plan 작업 수 {len(operations)}개가 정책 최대값 {spec['maxPlanOperations']}개를 초과합니다."
        )
    target = plan.get("spec", {}).get("target") or plan.get("spec", {}).get("instance") or {}
    target_name = str(target.get("name") or "")
    if phase == "apply" and not spec.get("allowProductionMutation", False):
        if re.search(spec["productionPattern"], target_name, flags=re.IGNORECASE):
            raise PolicyError(f"정책이 production 대상의 원격 mutation을 금지합니다: {target_name}")
    if spec.get("requireExplicitCreate", True):
        for operation in operations:
            if operation.get("action") == "CREATE" and not (
                operation.get("approvalKey") or operation.get("name")
            ):
                raise PolicyError("CREATE 작업에 승인 식별자가 없습니다.")
    if spec.get("requireExplicitDelete", True):
        for operation in operations:
            if operation.get("action") == "DELETE" and not operation.get("remoteId"):
                raise PolicyError("DELETE 작업에 remoteId가 없습니다.")
