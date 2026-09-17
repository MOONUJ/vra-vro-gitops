# -*- coding: utf-8 -*-
"""VCF Automation 인스턴스 저장소의 초기 설정 파일을 생성한다."""

import argparse
import shutil
import sys
from pathlib import Path

import yaml


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INSTANCE_EXAMPLE = REPOSITORY_ROOT / "instance.example.yaml"
DEFAULT_SECRETS_EXAMPLE = REPOSITORY_ROOT / "secrets.example.json"


def write_instance(source, destination, name, endpoint, organization, environment_tag, force=False):
    destination = Path(destination)
    if destination.exists() and not force:
        raise FileExistsError(f"이미 파일이 존재합니다: {destination}")

    with Path(source).open("r", encoding="utf-8") as source_file:
        instance = yaml.safe_load(source_file)

    instance["metadata"]["name"] = name
    instance["spec"]["endpoint"] = endpoint.rstrip("/")
    instance["spec"]["organization"] = organization
    instance["spec"]["environmentTag"] = environment_tag
    instance["spec"]["gitops"]["tag"] = environment_tag

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as destination_file:
        yaml.safe_dump(instance, destination_file, allow_unicode=True, sort_keys=False)


def copy_secrets_example(source, destination):
    destination = Path(destination)
    if destination.exists():
        return False
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return True


def main():
    parser = argparse.ArgumentParser(description="템플릿에서 Automation 인스턴스 저장소 설정을 생성합니다.")
    parser.add_argument("--name", required=True, help="Automation 인스턴스 또는 저장소 식별 이름")
    parser.add_argument("--endpoint", required=True, help="VCF Automation URL")
    parser.add_argument("--organization", default="default", help="Automation 조직 이름")
    parser.add_argument("--environment-tag", help="GitOps 범위 태그, 기본값은 --name")
    parser.add_argument("--output", default=str(REPOSITORY_ROOT / "instance.yaml"), help="생성할 인스턴스 파일")
    parser.add_argument("--secrets-output", default=str(REPOSITORY_ROOT / "secrets.json"), help="생성할 비밀값 파일")
    parser.add_argument("--force", action="store_true", help="기존 인스턴스 파일 덮어쓰기")
    args = parser.parse_args()

    try:
        write_instance(
            DEFAULT_INSTANCE_EXAMPLE,
            args.output,
            args.name,
            args.endpoint,
            args.organization,
            args.environment_tag or args.name,
            args.force,
        )
        secrets_created = copy_secrets_example(DEFAULT_SECRETS_EXAMPLE, args.secrets_output)
    except (OSError, KeyError, TypeError, yaml.YAMLError) as exc:
        print(f"초기화 오류: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(f"인스턴스 정의 생성 완료: {Path(args.output).resolve()}")
    if secrets_created:
        print(f"비밀값 예시 복사 완료: {Path(args.secrets_output).resolve()}")
    else:
        print(f"기존 비밀값 파일 유지: {Path(args.secrets_output).resolve()}")
    print("instance.yaml은 Git에 추적하고 secrets.json은 커밋하지 마세요.")


if __name__ == "__main__":
    main()
