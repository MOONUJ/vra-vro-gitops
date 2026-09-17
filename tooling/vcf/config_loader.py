# -*- coding: utf-8 -*-
"""인스턴스 정의와 비밀값을 읽어 VCF 도구별 입력으로 변환한다."""

import json
from pathlib import Path

import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INSTANCE_PATH = REPOSITORY_ROOT / "instance.yaml"
DEFAULT_SECRETS_PATH = REPOSITORY_ROOT / "secrets.json"
ROOT_LEGACY_CONFIG_PATH = REPOSITORY_ROOT / "config.json"
LEGACY_CONFIG_PATH = REPOSITORY_ROOT / "gitops" / "config.json"
SUPPORTED_SCHEMA_VERSION = 1


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


def load_legacy_config(config_path):
    path = Path(config_path)
    if not path.is_file():
        raise ConfigError(f"설정 파일을 찾을 수 없습니다: {path}")
    return _load_json(path)


def merge_instance_and_secrets(instance, secrets):
    """추적 가능한 인스턴스 정의와 로컬 비밀값을 내부 공통 형식으로 합친다."""
    if instance.get("apiVersion") != "gitops.vcf.example/v1alpha1":
        raise ConfigError(f"지원하지 않는 apiVersion입니다: {instance.get('apiVersion')!r}")
    if instance.get("kind") != "AutomationInstance":
        raise ConfigError(f"지원하지 않는 kind입니다: {instance.get('kind')!r}")

    metadata = _required(instance, "metadata")
    spec = _required(instance, "spec")
    gitops = _required(spec, "gitops")
    package = _required(spec, "orchestrator.package")
    infrastructure = _required(spec, "infrastructure")
    vsphere = dict(_required(infrastructure, "vsphere"))
    nsxt = dict(_required(infrastructure, "nsxt"))
    vsphere.update(username=_required(secrets, "vsphere.username"), password=_required(secrets, "vsphere.password"))
    nsxt.update(username=_required(secrets, "nsxt.username"), password=_required(secrets, "nsxt.password"))

    return {
        "schema_version": SUPPORTED_SCHEMA_VERSION,
        "environment": {"name": _required(metadata, "name"), "tag": _required(spec, "environmentTag")},
        "automation": {
            "url": _required(spec, "endpoint"),
            "organization": spec.get("organization", "default"),
            "refresh_token": _required(secrets, "automation.refresh_token"),
            "verify_ssl": spec.get("verifySsl", True),
            "gitops": {"tag": _required(gitops, "tag"), "projects": gitops.get("projects", [])},
        },
        "orchestrator": {"package": {"name": _required(package, "name"), "local_path": _required(package, "localPath")}},
        "infrastructure": {
            "vsphere": vsphere,
            "nsxt": nsxt,
            "cloud_zone": _required(infrastructure, "cloudZone"),
            "network_profile": _required(infrastructure, "networkProfile"),
            "storage_profile": _required(infrastructure, "storageProfile"),
            "image_profile": _required(infrastructure, "imageProfile"),
            "project": _required(infrastructure, "project"),
        },
    }


def load_source_config(instance_path=None, secrets_path=None, legacy_config_path=None):
    """분리 설정을 우선하고, 없으면 이전 단일 JSON 설정으로 전환한다."""
    if legacy_config_path:
        return load_legacy_config(legacy_config_path)
    instance_path = Path(instance_path or DEFAULT_INSTANCE_PATH)
    secrets_path = Path(secrets_path or DEFAULT_SECRETS_PATH)
    if instance_path.is_file() and secrets_path.is_file():
        return merge_instance_and_secrets(_load_yaml(instance_path), _load_json(secrets_path))
    for legacy_path in (ROOT_LEGACY_CONFIG_PATH, LEGACY_CONFIG_PATH):
        if legacy_path.is_file():
            return load_legacy_config(legacy_path)
    if instance_path.is_file():
        raise ConfigError(f"비밀값 파일이 없습니다: {secrets_path}. secrets.example.json을 secrets.json으로 복사하세요.")
    raise ConfigError(f"인스턴스 정의를 찾을 수 없습니다: {instance_path}")


def normalize_runtime_config(config):
    """공통 형식을 release/sync 도구가 사용하는 평면 구조로 변환한다."""
    if "automation" not in config:
        for key in ("vcf_url", "refresh_token"):
            if key not in config:
                raise ConfigError(f"기존 설정에 필수 값이 없습니다: {key}")
        normalized = dict(config)
        package = dict(normalized.get("package", {}))
        local_path = package.get("local_path")
        if isinstance(local_path, str) and local_path.startswith("vro/"):
            package["local_path"] = f"content/orchestrator/{local_path.removeprefix('vro/')}"
            normalized["package"] = package
        return normalized
    if config.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
        raise ConfigError(f"지원하지 않는 schema_version입니다: {config.get('schema_version')!r}")
    automation = _required(config, "automation")
    gitops = _required(config, "automation.gitops")
    return {
        "vcf_url": _required(automation, "url"),
        "org": automation.get("organization", "default"),
        "refresh_token": _required(automation, "refresh_token"),
        "verify_ssl": automation.get("verify_ssl", True),
        "gitops_tag": _required(gitops, "tag"),
        "projects": gitops.get("projects", []),
        "package": _required(config, "orchestrator.package"),
    }


def load_config():
    return normalize_runtime_config(load_source_config())


def build_terraform_variables(config):
    """공통 형식에서 Day-0 Terraform 입력을 생성한다."""
    if "automation" not in config:
        raise ConfigError("이전 단일 설정에는 infrastructure 정의가 없어 Terraform 입력을 만들 수 없습니다.")
    normalize_runtime_config(config)
    environment = _required(config, "environment")
    automation = _required(config, "automation")
    infrastructure = _required(config, "infrastructure")
    vsphere = _required(infrastructure, "vsphere")
    nsxt = _required(infrastructure, "nsxt")
    cloud_zone = _required(infrastructure, "cloud_zone")
    network_profile = _required(infrastructure, "network_profile")
    storage_profile = _required(infrastructure, "storage_profile")
    image_profile = _required(infrastructure, "image_profile")
    project = _required(infrastructure, "project")
    return {
        "vra_url": _required(automation, "url"),
        "vra_refresh_token": _required(automation, "refresh_token"),
        "vra_insecure": not automation.get("verify_ssl", True),
        "vra_organization": automation.get("organization", "default"),
        "vsphere_cloud_account_name": _required(vsphere, "cloudAccountName"),
        "vsphere_cloud_account_description": vsphere.get("description", "vSphere Cloud Account managed by Terraform"),
        "vsphere_endpoint": _required(vsphere, "endpoint"),
        "vsphere_username": _required(vsphere, "username"),
        "vsphere_password": _required(vsphere, "password"),
        "vsphere_dc": _required(vsphere, "datacenter"),
        "vsphere_region_name": vsphere.get("regionName", _required(vsphere, "datacenter")),
        "nsxt_cloud_account_name": _required(nsxt, "cloudAccountName"),
        "nsxt_cloud_account_description": nsxt.get("description", "NSX-T Cloud Account managed by Terraform"),
        "nsxt_endpoint": _required(nsxt, "endpoint"),
        "nsxt_username": _required(nsxt, "username"),
        "nsxt_password": _required(nsxt, "password"),
        "environment_tag": _required(environment, "tag"),
        "cloud_zone_name": _required(cloud_zone, "name"),
        "cloud_zone_description": cloud_zone.get("description", "vSphere Cloud Zone managed by Terraform"),
        "cloud_zone_placement_policy": cloud_zone.get("placementPolicy", "DEFAULT"),
        "network_profile_name": _required(network_profile, "name"),
        "network_profile_description": network_profile.get("description", "Network Profile managed by Terraform"),
        "network_profile_isolation_type": network_profile.get("isolationType", "NONE"),
        "network_profile_fabric_network_ids": network_profile.get("fabricNetworkIds", []),
        "storage_profile_name": _required(storage_profile, "name"),
        "storage_profile_description": storage_profile.get("description", "vSphere Storage Profile managed by Terraform"),
        "storage_profile_default_item": storage_profile.get("defaultItem", False),
        "storage_profile_provisioning_type": storage_profile.get("provisioningType", "thin"),
        "image_profile_name": _required(image_profile, "name"),
        "image_profile_description": image_profile.get("description", "Image Profile managed by Terraform"),
        "image_mappings": [{"name": _required(item, "name"), "image_id": _required(item, "imageId")} for item in _required(image_profile, "mappings")],
        "project_name": _required(project, "name"),
        "project_description": project.get("description", "Infrastructure Project managed by Terraform"),
        "project_zone_priority": project.get("zonePriority", 1),
        "project_max_instances": project.get("maxInstances", 100),
    }
