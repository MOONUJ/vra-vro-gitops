# -*- coding: utf-8 -*-
"""외부 의존성 없이 저장소의 versioned JSON Schema subset을 검증한다."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

from config_loader import REPOSITORY_ROOT


SCHEMA_BY_KIND = {
    "AutomationInstance": "automation-instance-v1alpha2.schema.json",
    "ContentIdentity": "content-identity-v1alpha1.schema.json",
    "LifecycleManifest": "lifecycle-manifest-v1alpha1.schema.json",
    "ReconciliationLoop": "reconciliation-loop-v1alpha1.schema.json",
    "GitOpsPolicy": "gitops-policy-v1alpha1.schema.json",
}
INFRASTRUCTURE_KINDS = {"CloudAccount", "CloudZone", "NetworkProfile", "StorageProfile", "ImageProfile", "Project"}


class SchemaValidationError(RuntimeError):
    pass


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return True


def validate_value(value: Any, schema: dict[str, Any], location: str = "$") -> list[str]:
    errors: list[str] = []
    expected_type = schema.get("type")
    if expected_type and not _type_matches(value, expected_type):
        return [f"{location}: {expected_type} 형식이어야 합니다."]
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{location}: 허용 값이 아닙니다: {value!r}")
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{location}: 비어 있지 않은 문자열이어야 합니다.")
        pattern = schema.get("pattern")
        if pattern and re.search(pattern, value) is None:
            errors.append(f"{location}: 패턴과 일치하지 않습니다: {pattern}")
    if isinstance(value, int) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{location}: 최소값은 {schema['minimum']}입니다.")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{location}: 최대값은 {schema['maximum']}입니다.")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{location}: 항목이 최소 {schema['minItems']}개 필요합니다.")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(validate_value(item, item_schema, f"{location}[{index}]"))
    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{location}: 필수 필드가 없습니다: {key}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    errors.append(f"{location}: 알 수 없는 필드입니다: {key}")
        for key, child_schema in properties.items():
            if key in value:
                errors.extend(validate_value(value[key], child_schema, f"{location}.{key}"))
    return errors


def load_document(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise SchemaValidationError(f"문서를 읽지 못했습니다: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise SchemaValidationError(f"문서 최상위 값은 객체여야 합니다: {path}")
    return value


def schema_path_for(document: dict[str, Any], schemas_root: Path) -> Path:
    kind = document.get("kind")
    if kind in INFRASTRUCTURE_KINDS:
        filename = "infrastructure-resource-v1alpha1.schema.json"
    else:
        filename = SCHEMA_BY_KIND.get(kind)
    if filename is None:
        raise SchemaValidationError(f"등록되지 않은 manifest kind입니다: {kind!r}")
    return schemas_root / filename


def validate_document(path: Path, schemas_root: Path) -> list[str]:
    document = load_document(path)
    schema_path = schema_path_for(document, schemas_root)
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SchemaValidationError(f"schema를 읽지 못했습니다: {schema_path}: {exc}") from exc
    return [f"{path}: {error}" for error in validate_value(document, schema)]


def repository_manifest_paths(repository_root: Path) -> list[Path]:
    paths = [repository_root / "instance.example.yaml", repository_root / "governance" / "policy.yaml"]
    instance = repository_root / "instance.yaml"
    if instance.exists():
        paths.append(instance)
    paths.extend(sorted((repository_root / "infrastructure").glob("*/*.yaml")))
    paths.extend(sorted((repository_root / "lifecycle").glob("*.yaml")))
    paths.extend(sorted((repository_root / "automation" / "loops").glob("*.yaml")))
    paths.extend(sorted((repository_root / "content").rglob("*.gitops.yaml")))
    return [path for path in paths if path.is_file()]


def validate_repository(repository_root: str | Path) -> list[str]:
    repository_root = Path(repository_root).resolve()
    schemas_root = repository_root / "schemas"
    errors: list[str] = []
    for path in repository_manifest_paths(repository_root):
        try:
            errors.extend(validate_document(path, schemas_root))
        except SchemaValidationError as exc:
            errors.append(str(exc))
    return errors


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="VCF GitOps versioned schema 검증")
    parser.add_argument("--repository-root", default=str(REPOSITORY_ROOT))
    args = parser.parse_args(argv)
    errors = validate_repository(args.repository_root)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("저장소 manifest schema 검증 완료")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
