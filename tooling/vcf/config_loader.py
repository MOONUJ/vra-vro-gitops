# -*- coding: utf-8 -*-
"""인스턴스 정의와 비밀값을 읽어 VCF 도구별 입력으로 변환한다."""

import json
import os
from pathlib import Path

import yaml

def detect_repository_root() -> Path:
    """source script와 설치된 package가 같은 저장소 경계를 사용하게 한다."""
    explicit = os.environ.get("VCF_GITOPS_REPOSITORY_ROOT")
    if explicit:
        return Path(explicit).expanduser().resolve()
    current = Path.cwd().resolve()
    if (current / ".git").exists() and (
        (current / ".template-version").is_file() or (current / "instance.yaml").is_file()
    ):
        return current
    source_root = Path(__file__).resolve().parents[2]
    if (source_root / ".git").exists():
        return source_root
    return current


REPOSITORY_ROOT = detect_repository_root()
DEFAULT_INSTANCE_PATH = REPOSITORY_ROOT / "instance.yaml"
DEFAULT_SECRETS_PATH = REPOSITORY_ROOT / "secrets.json"
SUPPORTED_SCHEMA_VERSION = 2
SUPPORTED_API_VERSIONS = {
    "gitops.vcf.example/v1alpha1": 1,
    "gitops.vcf.example/v1alpha2": 2,
}


class ConfigError(ValueError):
    """설정 파일이 없거나 지원되지 않는 형식일 때 발생한다."""


def _required(mapping, key_path):
    value = mapping
    traversed = []
    for key in key_path.split("."):
        traversed.append(key)
        if not isinstance(value, dict) or key not in value:
            raise ConfigError(f"필수 설정이 없습니다: {'.'.join(traversed)}")
        value = value[key]
    return value


def _load_json(path):
    try:
        with Path(path).open("r", encoding="utf-8") as config_file:
            value = json.load(config_file)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"JSON 형식이 올바르지 않습니다: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ConfigError(f"설정 최상위 값은 객체여야 합니다: {path}")
    return value


def _load_yaml(path):
    try:
        with Path(path).open("r", encoding="utf-8") as config_file:
            value = yaml.safe_load(config_file)
    except yaml.YAMLError as exc:
        raise ConfigError(f"YAML 형식이 올바르지 않습니다: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ConfigError(f"설정 최상위 값은 객체여야 합니다: {path}")
    return value


def merge_instance_and_secrets(instance, secrets):
    """추적 가능한 인스턴스 정의와 로컬 비밀값을 내부 공통 형식으로 합친다."""
    api_version = instance.get("apiVersion")
    if api_version not in SUPPORTED_API_VERSIONS:
        raise ConfigError(f"지원하지 않는 apiVersion입니다: {instance.get('apiVersion')!r}")
    if instance.get("kind") != "AutomationInstance":
        raise ConfigError(f"지원하지 않는 kind입니다: {instance.get('kind')!r}")

    metadata = _required(instance, "metadata")
    spec = _required(instance, "spec")
    gitops = _required(spec, "gitops")
    orchestrator = _required(spec, "orchestrator")
    package = _required(orchestrator, "package")
    deployment = orchestrator.get("deployment", "embedded")
    if deployment not in {"embedded", "external"}:
        raise ConfigError(f"지원하지 않는 Orchestrator deployment입니다: {deployment!r}")
    orchestrator_endpoint = orchestrator.get("endpoint")
    if deployment == "external" and not orchestrator_endpoint:
        raise ConfigError("external Orchestrator에는 spec.orchestrator.endpoint가 필요합니다.")
    if deployment == "embedded" and orchestrator_endpoint:
        raise ConfigError("embedded Orchestrator에는 별도 endpoint를 지정하지 않습니다.")
    discovery = orchestrator.get("discovery", {})
    discovery_mode = discovery.get("mode", "tag") if isinstance(discovery, dict) else None
    if discovery_mode not in {"tag", "package"}:
        raise ConfigError("Orchestrator discovery.mode는 tag 또는 package여야 합니다.")
    management = spec.get(
        "management",
        {"infrastructure": "native", "deletionPolicy": "require-explicit-approval"},
    )
    if management.get("infrastructure") != "native":
        raise ConfigError("Day-0 인프라는 management.infrastructure: native만 지원합니다.")

    result = {
        "schema_version": SUPPORTED_API_VERSIONS[api_version],
        "environment": {"name": _required(metadata, "name"), "tag": _required(spec, "environmentTag")},
        "automation": {
            "url": _required(spec, "endpoint"),
            "organization": spec.get("organization", "default"),
            "refresh_token": _required(secrets, "automation.refresh_token"),
            "verify_ssl": spec.get("verifySsl", True),
            "gitops": {"tag": _required(gitops, "tag"), "projects": gitops.get("projects", [])},
            "management": management,
        },
        "orchestrator": {
            "deployment": deployment,
            "url": orchestrator_endpoint or _required(spec, "endpoint"),
            "verify_ssl": orchestrator.get("verifySsl", spec.get("verifySsl", True)),
            "refresh_token": _required(secrets, "automation.refresh_token"),
            "discovery": {
                "mode": discovery_mode,
                "require_non_empty": discovery.get("requireNonEmpty", False),
            },
            "package": {"name": _required(package, "name"), "local_path": _required(package, "localPath")},
        },
    }
    return result


def load_source_config(instance_path=None, secrets_path=None):
    """인스턴스 정의와 로컬 비밀값을 읽어 내부 공통 형식으로 합친다."""
    instance_path = Path(instance_path or DEFAULT_INSTANCE_PATH)
    secrets_path = Path(secrets_path or DEFAULT_SECRETS_PATH)
    if instance_path.is_file() and secrets_path.is_file():
        instance = _load_yaml(instance_path)
        if instance_path.name == "instance.yaml":
            package = _required(instance, "spec.orchestrator.package")
            if package.get("name") in {"com.example.vcf", "CHANGE_ME"}:
                raise ConfigError("instance.yaml의 vRO package 이름이 placeholder입니다.")
            if "com.example.vcf.package" in str(package.get("localPath", "")):
                raise ConfigError("instance.yaml의 vRO package localPath가 placeholder입니다.")
        return merge_instance_and_secrets(instance, _load_json(secrets_path))
    if instance_path.is_file():
        raise ConfigError(f"비밀값 파일이 없습니다: {secrets_path}. secrets.example.json을 secrets.json으로 복사하세요.")
    raise ConfigError(f"인스턴스 정의를 찾을 수 없습니다: {instance_path}")


def normalize_runtime_config(config):
    """공통 형식을 release/sync 도구가 사용하는 평면 구조로 변환한다."""
    if config.get("schema_version") not in {1, SUPPORTED_SCHEMA_VERSION}:
        raise ConfigError(f"지원하지 않는 schema_version입니다: {config.get('schema_version')!r}")
    automation = _required(config, "automation")
    gitops = _required(config, "automation.gitops")
    orchestrator = _required(config, "orchestrator")
    return {
        "vcf_url": _required(automation, "url"),
        "org": automation.get("organization", "default"),
        "refresh_token": _required(automation, "refresh_token"),
        "verify_ssl": automation.get("verify_ssl", True),
        "gitops_tag": _required(gitops, "tag"),
        "projects": gitops.get("projects", []),
        "package": _required(orchestrator, "package"),
        "vro_url": _required(orchestrator, "url"),
        "vro_verify_ssl": orchestrator.get("verify_ssl", automation.get("verify_ssl", True)),
        "vro_refresh_token": _required(automation, "refresh_token"),
        "vro_discovery_mode": orchestrator.get("discovery", {}).get("mode", "tag"),
        "vro_require_non_empty": orchestrator.get("discovery", {}).get("require_non_empty", False),
    }
