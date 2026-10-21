# -*- coding: utf-8 -*-
"""로컬 Python 환경과 Automation 인스턴스 설정을 한 번에 준비한다."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import subprocess
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VENV = REPOSITORY_ROOT / ".venv"
DEFAULT_TOKEN_ENV = "VCF_AUTOMATION_REFRESH_TOKEN"


class SetupError(RuntimeError):
    """로컬 setup 입력 또는 실행이 안전하게 완료되지 않았을 때 발생한다."""


def _prompt(value, label, *, default=None, secret=False, non_interactive=False):
    if value:
        return value
    if non_interactive:
        if default is not None:
            return default
        raise SetupError(f"비대화식 실행에는 {label} 값이 필요합니다.")
    suffix = f" [{default}]" if default is not None else ""
    reader = getpass.getpass if secret else input
    entered = reader(f"{label}{suffix}: ").strip()
    if entered:
        return entered
    if default is not None:
        return default
    raise SetupError(f"{label} 값은 비워둘 수 없습니다.")


def _venv_python(venv: Path) -> Path:
    return venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def write_refresh_token(path, token, *, overwrite=False):
    """refresh token을 출력하지 않고 권한 0600의 로컬 JSON에 기록한다."""
    path = Path(path)
    if path.exists() and not overwrite:
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SetupError(f"기존 비밀값 파일을 읽지 못했습니다: {path}: {exc}") from exc
        existing = current.get("automation", {}).get("refresh_token")
        if existing not in {None, "", "CHANGE_ME"}:
            return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"automation": {"refresh_token": token}}, indent=2) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)
    return True


def run(command):
    subprocess.run([str(item) for item in command], cwd=REPOSITORY_ROOT, check=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="로컬 venv와 Automation 인스턴스 설정을 준비합니다.")
    parser.add_argument("--name")
    parser.add_argument("--endpoint")
    parser.add_argument("--organization", default="default")
    parser.add_argument("--environment-tag")
    parser.add_argument("--package-name")
    parser.add_argument("--project", action="append", help="관리할 project 이름, 반복 가능")
    parser.add_argument("--orchestrator-deployment", choices=["embedded", "external"])
    parser.add_argument("--orchestrator-endpoint")
    parser.add_argument("--venv", default=str(DEFAULT_VENV))
    parser.add_argument("--python", default=sys.executable, help="venv 생성에 사용할 Python")
    parser.add_argument("--refresh-token-env", default=DEFAULT_TOKEN_ENV)
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--force", action="store_true", help="기존 instance.yaml 덮어쓰기")
    parser.add_argument("--force-secrets", action="store_true", help="기존 secrets.json token 덮어쓰기")
    args = parser.parse_args(argv)

    try:
        name = _prompt(args.name, "인스턴스 이름", non_interactive=args.non_interactive)
        endpoint = _prompt(args.endpoint, "Automation endpoint", non_interactive=args.non_interactive)
        environment_tag = _prompt(
            args.environment_tag,
            "Environment tag",
            default=name,
            non_interactive=args.non_interactive,
        )
        package_name = _prompt(args.package_name, "vRO package 이름", non_interactive=args.non_interactive)
        projects = args.project
        if not projects:
            projects = [_prompt(None, "관리할 Automation project", non_interactive=args.non_interactive)]
        deployment = _prompt(
            args.orchestrator_deployment,
            "Orchestrator 유형 (embedded/external)",
            default="embedded",
            non_interactive=args.non_interactive,
        )
        if deployment not in {"embedded", "external"}:
            raise SetupError("Orchestrator 유형은 embedded 또는 external이어야 합니다.")
        orchestrator_endpoint = args.orchestrator_endpoint
        if deployment == "external":
            orchestrator_endpoint = _prompt(
                orchestrator_endpoint,
                "Orchestrator endpoint",
                non_interactive=args.non_interactive,
            )
        token = os.environ.get(args.refresh_token_env)
        token = _prompt(
            token,
            f"Automation refresh token ({args.refresh_token_env})",
            secret=True,
            non_interactive=args.non_interactive,
        )
        if token in {"CHANGE_ME", "REPLACE_WITH_LOCAL_SECRET"}:
            raise SetupError("실제 Automation refresh token이 필요합니다.")
        # Token은 setup 프로세스 안에서만 유지하고 pip/bootstrap 하위 프로세스에는 전달하지 않는다.
        os.environ.pop(args.refresh_token_env, None)

        venv = Path(args.venv).expanduser().resolve()
        run([args.python, "-m", "venv", venv])
        python = _venv_python(venv)
        run([python, "-m", "pip", "install", "-r", REPOSITORY_ROOT / "tooling/vcf/requirements.txt"])

        bootstrap = [
            python,
            REPOSITORY_ROOT / "tooling/template/bootstrap.py",
            "--name", name,
            "--endpoint", endpoint,
            "--organization", args.organization,
            "--environment-tag", environment_tag,
            "--package-name", package_name,
            "--orchestrator-deployment", deployment,
        ]
        for project in projects:
            bootstrap.extend(["--project", project])
        if orchestrator_endpoint:
            bootstrap.extend(["--orchestrator-endpoint", orchestrator_endpoint])
        if args.force:
            bootstrap.append("--force")
        run(bootstrap)

        secrets_path = REPOSITORY_ROOT / "secrets.json"
        token_written = write_refresh_token(secrets_path, token, overwrite=args.force_secrets)
        run([
            python,
            REPOSITORY_ROOT / "tooling/vcf/configure.py",
            "validate",
            "--instance", REPOSITORY_ROOT / "instance.yaml",
            "--secrets", secrets_path,
        ])
        run([python, REPOSITORY_ROOT / "tooling/vcf/schema_validation.py"])
    except (OSError, subprocess.CalledProcessError, SetupError) as exc:
        print(f"로컬 setup 오류: {exc}", file=sys.stderr)
        return 1

    print(f"로컬 Python 환경 준비 완료: {venv}")
    print("refresh token 기록 완료" if token_written else "기존 refresh token 유지")
    print("instance.yaml을 검토한 뒤 import/initial-baseline branch에서 커밋하세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
