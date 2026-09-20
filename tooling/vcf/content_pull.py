# -*- coding: utf-8 -*-
"""콘텐츠 pull preview와 명시적 accept를 담당한다."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from content_identity import validate_identities


PREVIEW_API_VERSION = "gitops.vcf.example/v1alpha1"
PREVIEW_KIND = "ContentPullPreview"
RESULT_KIND = "ContentPullAcceptResult"


class ContentPullError(RuntimeError):
    """pull preview 또는 accept 계약이 유효하지 않을 때 발생한다."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_snapshot(root: Path) -> list[dict[str, str]]:
    if not root.exists():
        return []
    return [
        {"path": path.relative_to(root).as_posix(), "sha256": _file_hash(path)}
        for path in sorted(value for value in root.rglob("*") if value.is_file())
    ]


def tree_hash(root: Path) -> str:
    return _hash(tree_snapshot(root))


def changes_between(before: list[dict[str, str]], after: list[dict[str, str]]) -> list[dict[str, Any]]:
    before_map = {item["path"]: item["sha256"] for item in before}
    after_map = {item["path"]: item["sha256"] for item in after}
    changes: list[dict[str, Any]] = []
    for path in sorted(set(before_map) | set(after_map)):
        if path not in before_map:
            changes.append({"action": "CREATE", "path": path, "after": after_map[path]})
        elif path not in after_map:
            changes.append({"action": "DELETE", "path": path, "before": before_map[path]})
        elif before_map[path] != after_map[path]:
            changes.append({"action": "UPDATE", "path": path, "before": before_map[path], "after": after_map[path]})
    return changes


class ContentPullService:
    def __init__(self, repository_root: str | Path, previews_root: str | Path, tool_version: str):
        self.repository_root = Path(repository_root).resolve()
        self.content_root = self.repository_root / "content"
        self.previews_root = Path(previews_root).resolve()
        self.tool_version = tool_version

    @staticmethod
    def validate_preview(preview: dict[str, Any]) -> None:
        if preview.get("apiVersion") != PREVIEW_API_VERSION or preview.get("kind") != PREVIEW_KIND:
            raise ContentPullError("지원하지 않는 pull preview입니다.")
        metadata = preview.get("metadata")
        spec = preview.get("spec")
        if not isinstance(metadata, dict) or not isinstance(spec, dict):
            raise ContentPullError("pull preview metadata와 spec이 필요합니다.")
        preview_hash = metadata.get("previewHash")
        body = {**preview, "metadata": {key: value for key, value in metadata.items() if key != "previewHash"}}
        if not isinstance(preview_hash, str) or _hash(body) != preview_hash:
            raise ContentPullError("pull preview hash가 내용과 일치하지 않습니다.")

    def create_preview(
        self,
        renderer: Callable[[Path], None],
        target: dict[str, Any],
    ) -> tuple[Path, dict[str, Any]]:
        self.previews_root.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=".pull-preview-", dir=self.previews_root))
        staged_content = temporary / "content"
        try:
            if self.content_root.exists():
                shutil.copytree(self.content_root, staged_content)
            else:
                staged_content.mkdir(parents=True)
            before_snapshot = tree_snapshot(self.content_root)
            renderer(temporary)
            errors = validate_identities(temporary)
            if errors:
                raise ContentPullError("preview 콘텐츠 identity 검증 실패:\n" + "\n".join(errors))
            after_snapshot = tree_snapshot(staged_content)
            changes = changes_between(before_snapshot, after_snapshot)
            deletions = [item for item in changes if item["action"] == "DELETE"]
            if deletions:
                raise ContentPullError("pull preview는 로컬 파일 삭제를 자동 수용하지 않습니다.")
            metadata = {"createdAt": _timestamp(), "toolVersion": self.tool_version}
            spec = {
                "target": target,
                "beforeHash": _hash(before_snapshot),
                "afterHash": _hash(after_snapshot),
                "changes": changes,
            }
            body = {"apiVersion": PREVIEW_API_VERSION, "kind": PREVIEW_KIND, "metadata": metadata, "spec": spec}
            preview_hash = _hash(body)
            preview = {**body, "metadata": {**metadata, "previewHash": preview_hash}}
            (temporary / "preview.json").write_text(
                json.dumps(preview, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            destination = self.previews_root / preview_hash
            if destination.exists():
                existing = self.load_preview(destination)
                if existing["spec"] == preview["spec"]:
                    shutil.rmtree(temporary)
                    return destination, existing
                raise ContentPullError(f"같은 hash 경로에 다른 preview가 있습니다: {destination}")
            os.replace(temporary, destination)
            return destination, preview
        except Exception:
            if temporary.exists():
                shutil.rmtree(temporary)
            raise

    def load_preview(self, path: str | Path) -> dict[str, Any]:
        path = Path(path)
        manifest_path = path / "preview.json" if path.is_dir() else path
        try:
            preview = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ContentPullError(f"pull preview를 읽지 못했습니다: {manifest_path}: {exc}") from exc
        if not isinstance(preview, dict):
            raise ContentPullError("pull preview 최상위 값은 객체여야 합니다.")
        self.validate_preview(preview)
        return preview

    def accept(self, path: str | Path, approval: str) -> tuple[Path, dict[str, Any]]:
        preview_path = Path(path).resolve()
        if not _is_relative_to(preview_path, self.previews_root):
            raise ContentPullError(f"pull preview는 {self.previews_root} 아래에 있어야 합니다.")
        preview = self.load_preview(preview_path)
        preview_hash = preview["metadata"]["previewHash"]
        result_path = preview_path / "accept-result.json"
        if result_path.exists():
            raise ContentPullError(f"이미 accept한 preview입니다: {preview_path}")
        if approval != preview_hash:
            raise ContentPullError("승인 hash가 pull preview hash와 일치하지 않습니다.")
        if tree_hash(self.content_root) != preview["spec"]["beforeHash"]:
            raise ContentPullError("preview 생성 후 로컬 content가 변경되었습니다. 새 preview가 필요합니다.")
        staged_content = preview_path / "content"
        if tree_hash(staged_content) != preview["spec"]["afterHash"]:
            raise ContentPullError("preview content hash가 artifact와 일치하지 않습니다.")
        errors = validate_identities(preview_path)
        if errors:
            raise ContentPullError("preview 콘텐츠 identity 검증 실패:\n" + "\n".join(errors))
        if any(item["action"] == "DELETE" for item in preview["spec"]["changes"]):
            raise ContentPullError("파일 삭제가 포함된 pull preview는 accept할 수 없습니다.")

        applied: list[str] = []
        for change in preview["spec"]["changes"]:
            source = (staged_content / change["path"]).resolve()
            destination = (self.content_root / change["path"]).resolve()
            if not _is_relative_to(source, staged_content) or not _is_relative_to(destination, self.content_root):
                raise ContentPullError(f"preview 변경 경로가 content 경계를 벗어납니다: {change['path']}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name(f".{destination.name}.accept-{preview_hash[:12]}")
            shutil.copy2(source, temporary)
            os.replace(temporary, destination)
            applied.append(change["path"])

        accepted_hash = tree_hash(self.content_root)
        if accepted_hash != preview["spec"]["afterHash"]:
            raise ContentPullError("pull accept 후 content hash가 preview와 일치하지 않습니다.")

        result = {
            "apiVersion": PREVIEW_API_VERSION,
            "kind": RESULT_KIND,
            "metadata": {"acceptedAt": _timestamp(), "previewHash": preview_hash},
            "spec": {"status": "ACCEPTED", "applied": applied, "contentHash": accepted_hash},
        }
        try:
            with result_path.open("x", encoding="utf-8") as output:
                json.dump(result, output, ensure_ascii=False, indent=2, sort_keys=True)
                output.write("\n")
        except FileExistsError as exc:
            raise ContentPullError(f"이미 accept한 preview입니다: {preview_path}") from exc
        return result_path, result
