# -*- coding: utf-8 -*-
"""Automation과 Orchestrator 콘텐츠 관찰 결과의 안정적인 JSON 계약."""

from __future__ import annotations

from typing import Any


OBSERVATION_API_VERSION = "gitops.vcf.example/v1alpha1"
OBSERVATION_KIND = "ContentObservation"
LEGACY_STATES = ("IN_SYNC", "MODIFIED", "LOCAL_ONLY", "SERVER_ONLY")
STATE_NAMES = {
    "IN_SYNC": "IN_SYNC",
    "MODIFIED": "MODIFIED",
    "LOCAL_ONLY": "LOCAL_ONLY",
    "SERVER_ONLY": "REMOTE_ONLY",
}


class ContentObservationError(RuntimeError):
    """원격 또는 로컬 상태를 완전하게 관찰하지 못했을 때 발생한다."""


def _item(identity: Any) -> dict[str, Any]:
    if not isinstance(identity, (list, tuple)) or not identity:
        raise ContentObservationError(f"유효하지 않은 status 항목입니다: {identity!r}")
    name = identity[0]
    if not isinstance(name, str) or not name:
        raise ContentObservationError(f"status 항목의 식별자가 유효하지 않습니다: {identity!r}")
    result = {"identity": name}
    if len(identity) > 1 and identity[1] is not None:
        result["detail"] = str(identity[1])
    return result


def normalize_product_status(raw: dict[str, Any]) -> dict[str, Any]:
    """기존 status 결과를 정렬된 공통 제품 결과로 변환한다."""
    resources: list[dict[str, Any]] = []
    for resource_type in sorted(raw):
        categories = raw[resource_type]
        if not isinstance(categories, dict):
            raise ContentObservationError(f"{resource_type} status 결과가 객체가 아닙니다.")
        for legacy_state in LEGACY_STATES:
            values = categories.get(legacy_state, [])
            if not isinstance(values, list):
                raise ContentObservationError(f"{resource_type}/{legacy_state} 결과가 목록이 아닙니다.")
            for value in values:
                resources.append(
                    {
                        "type": resource_type,
                        "state": STATE_NAMES[legacy_state],
                        **_item(value),
                    }
                )
    resources.sort(key=lambda value: (value["type"], value["identity"], value["state"], value.get("detail", "")))
    summary = {
        state: sum(item["state"] == state for item in resources)
        for state in ("IN_SYNC", "MODIFIED", "LOCAL_ONLY", "REMOTE_ONLY")
    }
    return {"state": "COMPLETE", "summary": summary, "resources": resources}


def complete_observation(
    target: dict[str, Any],
    orchestrator_status: dict[str, Any],
    automation_status: dict[str, Any],
) -> dict[str, Any]:
    """완전한 두 제품 관찰을 결정론적인 artifact로 만든다."""
    return {
        "apiVersion": OBSERVATION_API_VERSION,
        "kind": OBSERVATION_KIND,
        "metadata": {"complete": True},
        "spec": {
            "target": target,
            "products": {
                "automation": normalize_product_status(automation_status),
                "orchestrator": normalize_product_status(orchestrator_status),
            },
        },
    }


def incomplete_observation(target: dict[str, Any], product: str, error: Exception) -> dict[str, Any]:
    """부분 결과를 drift로 오인하지 않도록 실패 artifact를 만든다."""
    return {
        "apiVersion": OBSERVATION_API_VERSION,
        "kind": OBSERVATION_KIND,
        "metadata": {"complete": False},
        "spec": {
            "target": target,
            "products": {
                product: {
                    "state": "INCOMPLETE",
                    "error": {"type": type(error).__name__, "message": str(error)},
                }
            },
        },
    }
