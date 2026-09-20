# -*- coding: utf-8 -*-
"""원격 변경 없이 콘텐츠 drift를 관찰하고 실행 증거를 기록한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import yaml

try:
    import requests
except ImportError:  # schema/runner 단위 테스트는 HTTP client 의존성이 없어도 실행한다.
    requests = None

from config_loader import ConfigError, load_source_config, normalize_runtime_config
from content_observation import complete_observation, normalize_product_status
from repository import RepositoryMode, detect_repository_context
from schema_validation import SchemaValidationError, validate_document


class LoopError(RuntimeError):
    """Loop 설정 또는 실행 계약 위반."""


class RetryableObservationError(RuntimeError):
    """제한적으로 재시도할 수 있는 관찰 실패."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_hash(value: dict) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_yaml(path: Path) -> dict:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise LoopError(f"Loop 파일을 읽지 못했습니다: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise LoopError(f"Loop 문서 최상위 값은 객체여야 합니다: {path}")
    return value


def validate_loop_target(repository_root, loop_path, secrets_path=None) -> tuple[dict, dict]:
    repository_root = Path(repository_root).resolve()
    loop_path = Path(loop_path).resolve()
    if loop_path.name.endswith(".example.yaml"):
        raise LoopError(".example.yaml Loop는 실행할 수 없습니다.")
    context = detect_repository_context(repository_root)
    if context.mode != RepositoryMode.INSTANCE:
        raise LoopError(f"Loop는 instance 저장소에서만 실행할 수 있습니다: {context.mode.value}")
    schema_errors = validate_document(loop_path, repository_root / "schemas")
    if schema_errors:
        raise LoopError("Loop schema 검증 실패: " + "; ".join(schema_errors))
    loop = _load_yaml(loop_path)
    spec = loop["spec"]
    if spec["enabled"] is not True:
        raise LoopError("비활성화된 Loop는 실행할 수 없습니다.")
    if spec["repositoryMode"] != "instance" or spec["mode"] != "observe":
        raise LoopError("현재는 instance/observe Loop만 지원합니다.")
    instance_path = repository_root / "instance.yaml"
    secret_path = Path(secrets_path or repository_root / "secrets.json")
    source_config = load_source_config(instance_path, secret_path)
    if spec["instanceRef"] != source_config["environment"]["name"]:
        raise LoopError(
            f"instanceRef가 instance.yaml과 일치하지 않습니다: {spec['instanceRef']!r}"
        )
    return loop, source_config


def _is_retryable(error: BaseException) -> bool:
    current = error
    seen = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, RetryableObservationError):
            return True
        if requests is not None:
            if isinstance(current, (requests.Timeout, requests.ConnectionError)):
                return True
            if isinstance(current, requests.HTTPError):
                status = current.response.status_code if current.response is not None else None
                return status == 429 or bool(status and status >= 500)
        current = current.__cause__ or current.__context__
    return False


def _redact(message: str, secrets: list[str]) -> str:
    result = message
    for secret in secrets:
        if secret:
            result = result.replace(secret, "[REDACTED]")
    return result


@contextmanager
def _exclusive_lock(path: Path, invocation_id: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise LoopError(f"동일 인스턴스 Loop가 이미 실행 중입니다: {path}") from exc
    try:
        os.write(descriptor, invocation_id.encode("utf-8"))
        os.close(descriptor)
        descriptor = None
        yield
    finally:
        if descriptor is not None:
            os.close(descriptor)
        path.unlink(missing_ok=True)


class ObserveLoopRunner:
    def __init__(self, repository_root, tool_version="development", sleep: Callable = time.sleep):
        self.repository_root = Path(repository_root).resolve()
        self.tool_version = tool_version
        self.sleep = sleep

    def run(self, loop: dict, observe: Callable[[], dict], redactions=None) -> tuple[Path, dict]:
        redactions = list(redactions or [])
        name = loop["metadata"]["name"]
        instance_ref = loop["spec"]["instanceRef"]
        invocation_id = str(uuid.uuid4())
        started_at = _now()
        start_clock = time.monotonic()
        lock_path = self.repository_root / ".gitops" / "locks" / f"{instance_ref}.observe.lock"
        journal_root = self.repository_root / ".gitops" / "loop-runs"
        state_path = self.repository_root / ".gitops" / "loop-state" / f"{name}.json"
        retry = loop["spec"]["retry"]
        max_attempts = retry["maxAttempts"]
        max_elapsed = retry.get("maxElapsedSeconds", 300)
        backoff = retry.get("backoffSeconds", 1)
        attempts = 0
        observation = None
        failure = None

        with _exclusive_lock(lock_path, invocation_id):
            while attempts < max_attempts and time.monotonic() - start_clock <= max_elapsed:
                attempts += 1
                try:
                    observation = observe()
                    if observation.get("metadata", {}).get("complete") is not True:
                        raise LoopError("불완전한 observation은 Loop 증거로 사용할 수 없습니다.")
                    break
                except Exception as exc:  # callback 경계를 fail-closed로 유지한다.
                    failure = exc
                    if not _is_retryable(exc) or attempts >= max_attempts:
                        break
                    delay = backoff * (2 ** (attempts - 1))
                    if time.monotonic() - start_clock + delay > max_elapsed:
                        break
                    self.sleep(delay)

            finished_at = _now()
            journal = {
                "apiVersion": "gitops.vcf.example/v1alpha1",
                "kind": "ObserveLoopRun",
                "metadata": {
                    "invocationId": invocation_id,
                    "loop": name,
                    "instanceRef": instance_ref,
                    "startedAt": started_at,
                    "finishedAt": finished_at,
                    "toolVersion": self.tool_version,
                },
                "spec": {"attempts": attempts, "mode": "observe"},
            }
            if observation is None:
                message = _redact(str(failure or "observation 실패"), redactions)
                journal["status"] = {
                    "state": "FAILED",
                    "retryable": bool(failure and _is_retryable(failure)),
                    "notify": True,
                    "needsAction": True,
                    "error": {"type": type(failure).__name__, "message": message},
                }
            else:
                observation_hash = _canonical_hash(observation)
                drift = any(
                    sum(product["summary"].get(state, 0) for state in ("MODIFIED", "LOCAL_ONLY", "REMOTE_ONLY"))
                    for product in observation["spec"]["products"].values()
                )
                previous = {}
                if state_path.is_file():
                    try:
                        previous = json.loads(state_path.read_text(encoding="utf-8"))
                    except (OSError, json.JSONDecodeError):
                        previous = {}
                same = previous.get("observationHash") == observation_hash
                repeat_count = previous.get("repeatCount", 0) + 1 if same and drift else (1 if drift else 0)
                threshold = loop["spec"].get("repeatDriftThreshold", 3)
                escalation = drift and repeat_count >= threshold
                state_path.parent.mkdir(parents=True, exist_ok=True)
                state_path.write_text(
                    json.dumps(
                        {"observationHash": observation_hash, "drift": drift, "repeatCount": repeat_count},
                        ensure_ascii=False,
                        sort_keys=True,
                        indent=2,
                    ) + "\n",
                    encoding="utf-8",
                )
                journal["spec"]["observation"] = observation
                journal["status"] = {
                    "state": "DRIFT" if drift else "IN_SYNC",
                    "observationHash": observation_hash,
                    "changed": bool(previous) and not same,
                    "repeatCount": repeat_count,
                    "escalation": escalation,
                    "notify": (drift and not previous)
                    or (bool(previous) and not same)
                    or (drift and repeat_count == threshold),
                    "needsAction": drift,
                }
            journal_root.mkdir(parents=True, exist_ok=True)
            journal_path = journal_root / f"{invocation_id}.json"
            journal_path.write_text(
                json.dumps(journal, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                encoding="utf-8",
            )
            return journal_path, journal


def _build_observer(repository_root: Path, source_config: dict, products: list[str]):
    from vcf_sync import get_vra_status, get_vro_status
    from vra_client import VraClient
    from vro_client import VroClient

    config = normalize_runtime_config(source_config)
    target = {
        "name": source_config["environment"]["name"],
        "endpoint": config["vcf_url"],
        "organization": config.get("org", "default"),
        "gitopsTag": config["gitops_tag"],
        "projects": sorted(config.get("projects", [])),
    }
    vro_client = VroClient(config["vcf_url"], config["refresh_token"], config.get("org", "default"), config.get("verify_ssl", True))
    vra_client = VraClient(config["vcf_url"], config["refresh_token"], config.get("org", "default"), config.get("verify_ssl", True))

    def observe():
        raw = {}
        if "orchestrator" in products:
            raw["orchestrator"] = get_vro_status(vro_client, config, str(repository_root))
        if "automation" in products:
            raw["automation"] = get_vra_status(vra_client, config, str(repository_root))
        return {
            "apiVersion": "gitops.vcf.example/v1alpha1",
            "kind": "ContentObservation",
            "metadata": {"complete": True},
            "spec": {"target": target, "products": {key: normalize_product_status(value) for key, value in raw.items()}},
        }

    return observe, config["refresh_token"]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="vcf-gitops observe-loop", description="observe-only reconciliation loop")
    parser.add_argument("--loop", required=True)
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--secrets")
    args = parser.parse_args(argv)
    repository_root = Path(args.repository_root).resolve()
    try:
        loop, source_config = validate_loop_target(repository_root, args.loop, args.secrets)
        observer, refresh_token = _build_observer(repository_root, source_config, loop["spec"]["products"])
        version_path = repository_root / ".vcf-gitops-version"
        version = version_path.read_text(encoding="utf-8").strip() if version_path.is_file() else "development"
        path, journal = ObserveLoopRunner(repository_root, version).run(loop, observer, [refresh_token])
        print(json.dumps({"journal": str(path), "status": journal["status"]}, ensure_ascii=False, sort_keys=True))
        return 1 if journal["status"]["state"] == "FAILED" else (2 if journal["status"]["state"] == "DRIFT" else 0)
    except (ConfigError, LoopError, SchemaValidationError, OSError) as exc:
        print(f"Loop 오류: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
