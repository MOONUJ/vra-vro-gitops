# -*- coding: utf-8 -*-
"""저장소 실행 모드와 템플릿/인스턴스 경계를 판정한다."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class RepositoryMode(str, Enum):
    TEMPLATE = "template"
    INSTANCE = "instance"
    AMBIGUOUS = "ambiguous"


class RepositoryContextError(RuntimeError):
    """현재 저장소 모드에서 요청한 작업을 안전하게 실행할 수 없을 때 발생한다."""


@dataclass(frozen=True)
class RepositoryContext:
    root: Path
    mode: RepositoryMode


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def detect_repository_context(root: str | Path) -> RepositoryContext:
    """추적된 instance.yaml을 기준으로 저장소 실행 모드를 판정한다."""
    root = Path(root).resolve()
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--error-unmatch", "--", "instance.yaml"],
            capture_output=True,
            check=False,
            text=True,
        )
    except OSError as exc:
        raise RepositoryContextError(f"Git 저장소 모드를 판정하지 못했습니다: {exc}") from exc
    if result.returncode not in {0, 1}:
        detail = result.stderr.strip() or f"git 종료 코드 {result.returncode}"
        raise RepositoryContextError(f"Git 저장소 모드를 판정하지 못했습니다: {detail}")
    if result.returncode == 0:
        mode = RepositoryMode.INSTANCE
    elif (root / "instance.yaml").exists():
        mode = RepositoryMode.AMBIGUOUS
    else:
        mode = RepositoryMode.TEMPLATE
    return RepositoryContext(root=root, mode=mode)


def validate_infrastructure_paths(
    context: RepositoryContext,
    action: str,
    instance_path: str | Path,
    secrets_path: str | Path,
    infrastructure_root: str | Path,
    plans_root: str | Path | None = None,
    results_root: str | Path | None = None,
) -> None:
    """템플릿 연동 산출물이 추적 대상 경로에 섞이지 않게 한다."""
    if action in {"context", "validate"} or context.mode == RepositoryMode.INSTANCE:
        return

    instance_path = Path(instance_path).resolve()
    secrets_path = Path(secrets_path).resolve()
    infrastructure_root = Path(infrastructure_root).resolve()
    expected_instance = context.root / "instance.local.yaml"
    expected_secrets = context.root / "secrets.local.json"
    integration_root = context.root / ".gitops"

    errors: list[str] = []
    if instance_path != expected_instance:
        errors.append(f"--instance {expected_instance}")
    if secrets_path != expected_secrets:
        errors.append(f"--secrets {expected_secrets}")
    if action in {"adopt", "status", "plan", "apply"} and not _is_relative_to(infrastructure_root, integration_root):
        errors.append(f"--infrastructure-root {integration_root / 'infrastructure-test'}")
    if action in {"plan", "apply"} and plans_root is not None and not _is_relative_to(Path(plans_root).resolve(), integration_root):
        errors.append(f"--plans-root {integration_root / 'plans'}")
    if action == "apply" and results_root is not None and not _is_relative_to(Path(results_root).resolve(), integration_root):
        errors.append(f"--results-root {integration_root / 'apply-results'}")

    if errors:
        mode_label = "모호한" if context.mode == RepositoryMode.AMBIGUOUS else "템플릿"
        required = " ".join(errors)
        raise RepositoryContextError(
            f"{mode_label} 저장소 모드에서는 실제 연동 파일을 Git 추적 경로와 분리해야 합니다. "
            f"다음 옵션을 사용하세요: {required}"
        )


def require_instance_mode(context: RepositoryContext, operation: str) -> None:
    """향후 원격 mutation이 템플릿이나 모호한 저장소에서 실행되지 않게 한다."""
    if context.mode != RepositoryMode.INSTANCE:
        raise RepositoryContextError(
            f"{operation}은 추적된 instance.yaml이 있는 인스턴스 저장소에서만 실행할 수 있습니다. "
            f"현재 모드: {context.mode.value}"
        )
