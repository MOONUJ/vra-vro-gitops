# -*- coding: utf-8 -*-
"""공통 템플릿 파일만 안전하게 preview/apply 한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


COMMON_FILES = {
    ".template-version",
    ".vcf-gitops-version",
    "pyproject.toml",
}
COMMON_ROOTS = {
    "schemas",
    "tooling",
}
PROTECTED_ROOTS = {
    ".git",
    ".gitops",
    "content",
    "foundation",
    "governance",
    "infrastructure",
    "lifecycle",
    "releases",
}
PROTECTED_FILES = {
    "instance.yaml",
    "instance.local.yaml",
    "secrets.json",
    "secrets.local.json",
}


class TemplateUpdateError(RuntimeError):
    """안전한 template update 계약 위반."""


@dataclass(frozen=True)
class FileChange:
    action: str
    path: str
    sha256: str

    def as_dict(self):
        return {"action": self.action, "path": self.path, "sha256": self.sha256}


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _template_version(root: Path) -> str:
    path = root / ".template-version"
    if not path.is_file():
        raise TemplateUpdateError(f"template version 파일이 없습니다: {path}")
    version = path.read_text(encoding="utf-8").strip()
    if not version:
        raise TemplateUpdateError("template version이 비어 있습니다.")
    return version


def _is_common(relative: Path) -> bool:
    if relative.as_posix() in COMMON_FILES:
        return True
    return bool(relative.parts and relative.parts[0] in COMMON_ROOTS)


def _is_protected(relative: Path) -> bool:
    if relative.name.startswith("secrets"):
        return True
    if relative.as_posix() in PROTECTED_FILES:
        return True
    return bool(relative.parts and relative.parts[0] in PROTECTED_ROOTS)


def plan_update(source, destination) -> dict:
    source = Path(source).resolve()
    destination = Path(destination).resolve()
    version = _template_version(source)
    changes = []
    for source_path in sorted(path for path in source.rglob("*") if path.is_file()):
        relative = source_path.relative_to(source)
        if "__pycache__" in relative.parts or source_path.suffix in {".pyc", ".pyo"}:
            continue
        if _is_protected(relative):
            continue
        if not _is_common(relative):
            continue
        destination_path = destination / relative
        digest = _digest(source_path)
        if not destination_path.exists():
            action = "CREATE"
        elif not destination_path.is_file():
            raise TemplateUpdateError(f"파일 대상 경로가 디렉터리입니다: {relative}")
        elif _digest(destination_path) == digest:
            action = "UNCHANGED"
        else:
            action = "UPDATE"
        changes.append(FileChange(action, relative.as_posix(), digest).as_dict())
    return {
        "apiVersion": "gitops.vmware.com/v1alpha1",
        "kind": "TemplateUpdatePreview",
        "metadata": {"templateVersion": version},
        "spec": {
            "source": str(source),
            "destination": str(destination),
            "deleteMissing": False,
            "protectedRoots": sorted(PROTECTED_ROOTS),
            "changes": changes,
        },
    }


def apply_update(preview: dict, approve_version: str) -> list[str]:
    version = preview["metadata"]["templateVersion"]
    if approve_version != version:
        raise TemplateUpdateError(
            f"template version 승인이 일치하지 않습니다: expected --approve-version {version}"
        )
    source = Path(preview["spec"]["source"])
    destination = Path(preview["spec"]["destination"])
    applied = []
    for change in preview["spec"]["changes"]:
        if change["action"] == "UNCHANGED":
            continue
        relative = Path(change["path"])
        if _is_protected(relative) or not _is_common(relative):
            raise TemplateUpdateError(f"허용되지 않은 update 경로입니다: {relative}")
        source_path = source / relative
        if _digest(source_path) != change["sha256"]:
            raise TemplateUpdateError(f"preview 이후 source가 변경되었습니다: {relative}")
        destination_path = destination / relative
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, destination_path)
        shutil.copymode(source_path, destination_path)
        applied.append(relative.as_posix())
    return applied


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="vcf-gitops template-update",
        description="desired state를 보존하며 공통 tooling/schema만 업데이트합니다.",
    )
    parser.add_argument("--source", required=True, help="새 template checkout 경로")
    parser.add_argument("--destination", default=".", help="인스턴스 저장소 경로")
    parser.add_argument("--apply", action="store_true", help="preview의 변경을 적용")
    parser.add_argument("--approve-version", help="적용을 승인할 정확한 .template-version")
    parser.add_argument("--json", action="store_true", help="machine-readable preview 출력")
    args = parser.parse_args(argv)
    try:
        preview = plan_update(args.source, args.destination)
        if args.apply:
            applied = apply_update(preview, args.approve_version or "")
            preview["status"] = {"applied": applied, "count": len(applied)}
        if args.json:
            print(json.dumps(preview, ensure_ascii=False, sort_keys=True, indent=2))
        else:
            print(f"template version: {preview['metadata']['templateVersion']}")
            for change in preview["spec"]["changes"]:
                print(f"{change['action']:9} {change['path']}")
            if args.apply:
                print(f"적용 완료: {preview['status']['count']}개 파일")
            else:
                print("preview만 생성했습니다. 적용하려면 --apply --approve-version을 사용하세요.")
        return 0
    except (OSError, TemplateUpdateError) as exc:
        print(f"template update 오류: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
