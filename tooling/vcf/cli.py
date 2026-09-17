# -*- coding: utf-8 -*-
"""VCF Automation 인프라를 Git manifest로 관리하는 read-only 우선 CLI."""

import argparse
import json
import sys
from pathlib import Path

from config_loader import ConfigError, REPOSITORY_ROOT, load_source_config, normalize_runtime_config
from infrastructure import InfrastructureError, InfrastructureService, RESOURCE_DEFINITIONS
from infrastructure_plan import InfrastructurePlanService
from repository import RepositoryContextError, detect_repository_context, require_instance_mode, validate_infrastructure_paths


def _runtime_context(instance_path, secrets_path):
    from vra_client import VraClient

    source = load_source_config(instance_path, secrets_path)
    runtime = normalize_runtime_config(source)
    client = VraClient(
        vcf_url=runtime["vcf_url"],
        refresh_token=runtime["refresh_token"],
        org=runtime.get("org", "default"),
        verify_ssl=runtime.get("verify_ssl", True),
    )
    management = source["automation"].get("management", {})
    identity = {
        "name": source["environment"]["name"],
        "endpoint": runtime["vcf_url"],
        "organization": runtime.get("org", "default"),
        "management": {
            "infrastructure": management.get("infrastructure"),
            "deletionPolicy": management.get("deletionPolicy"),
        },
    }
    return client, identity, management


def _tool_version():
    path = REPOSITORY_ROOT / ".template-version"
    return path.read_text(encoding="utf-8").strip() if path.is_file() else "development"


def _parse_resource(value):
    try:
        kind, remote_id = value.split(":", 1)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("리소스는 Kind:remote-id 형식이어야 합니다.") from exc
    if kind not in RESOURCE_DEFINITIONS or not remote_id:
        raise argparse.ArgumentTypeError(f"지원하지 않는 리소스 선택자입니다: {value}")
    return kind, remote_id


def build_parser():
    parser = argparse.ArgumentParser(description="VCF Automation 인프라 GitOps 도구")
    parser.add_argument("--instance", default=str(REPOSITORY_ROOT / "instance.yaml"))
    parser.add_argument("--secrets", default=str(REPOSITORY_ROOT / "secrets.json"))
    parser.add_argument("--infrastructure-root", default=str(REPOSITORY_ROOT / "infrastructure"))
    parser.add_argument("--plans-root", default=str(REPOSITORY_ROOT / ".gitops" / "plans"))
    parser.add_argument("--results-root", default=str(REPOSITORY_ROOT / ".gitops" / "apply-results"))
    subparsers = parser.add_subparsers(dest="action", required=True)

    context = subparsers.add_parser("context", help="현재 저장소 실행 모드 확인")
    context.add_argument("--json", action="store_true", help="JSON으로 출력")

    discover = subparsers.add_parser("discover", help="원격 Day-0 리소스를 읽기 전용으로 조회")
    discover.add_argument("--kind", action="append", choices=sorted(RESOURCE_DEFINITIONS))
    discover.add_argument("--output", help="JSON 결과 파일. 생략하면 stdout에 출력")

    adopt = subparsers.add_parser("adopt", help="선택한 원격 리소스를 Git manifest로 채택")
    selection = adopt.add_mutually_exclusive_group(required=True)
    selection.add_argument("--resource", action="append", type=_parse_resource, metavar="Kind:remote-id")
    selection.add_argument("--all", action="store_true", help="발견된 모든 지원 리소스를 명시적으로 채택")
    adopt.add_argument("--kind", action="append", choices=sorted(RESOURCE_DEFINITIONS), help="--all 대상 종류 제한")
    adopt.add_argument("--dry-run", action="store_true", help="생성·건너뜀·충돌을 출력하고 파일은 쓰지 않음")
    adopt.add_argument("--force", action="store_true", help="기존 manifest 덮어쓰기")

    subparsers.add_parser("validate", help="로컬 인프라 manifest 검증")
    status = subparsers.add_parser("status", help="로컬 manifest와 원격 상태 비교")
    status.add_argument("--json", action="store_true", help="JSON으로 출력")

    plan = subparsers.add_parser("plan", help="원격을 다시 관찰해 불변 변경 plan 생성")
    plan.add_argument("--delete", action="append", type=_parse_resource, metavar="Kind:remote-id")
    plan.add_argument("--expires-in", type=int, default=1800, metavar="SECONDS")

    apply = subparsers.add_parser("apply", help="승인된 plan 적용 후 원격 상태 검증")
    apply.add_argument("--plan", required=True, help="plan artifact JSON 경로")
    apply.add_argument("--approve-plan", required=True, metavar="HASH", help="명시적으로 승인할 plan hash")
    apply.add_argument(
        "--approve-create",
        action="append",
        type=_parse_resource,
        metavar="Kind:name",
        help="CREATE할 manifest 대상을 별도로 승인",
    )
    apply.add_argument("--approve-delete", action="append", type=_parse_resource, metavar="Kind:remote-id")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    service = InfrastructureService(None, args.infrastructure_root)
    try:
        repository_context = detect_repository_context(REPOSITORY_ROOT)
        if args.action == "context":
            result = {"repositoryRoot": str(repository_context.root), "mode": repository_context.mode.value}
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(f"저장소 모드: {result['mode']}")
                print(f"저장소 루트: {result['repositoryRoot']}")
            return 0

        validate_infrastructure_paths(
            repository_context,
            args.action,
            args.instance,
            args.secrets,
            args.infrastructure_root,
            args.plans_root,
            args.results_root,
        )
        if args.action == "validate":
            errors = service.validate()
            if errors:
                for error in errors:
                    print(error, file=sys.stderr)
                return 1
            print("인프라 manifest 검증 완료")
            return 0

        service.client, instance_identity, management = _runtime_context(args.instance, args.secrets)
        if args.action in {"plan", "apply"} and management.get("infrastructure") != "native":
            raise InfrastructureError("management.infrastructure가 native인 저장소에서만 plan/apply를 실행할 수 있습니다.")
        if args.action == "plan":
            requested_deletions = args.delete or []
        elif args.action == "apply":
            requested_deletions = args.approve_delete or []
        else:
            requested_deletions = []
        if requested_deletions and management.get("deletionPolicy") != "require-explicit-approval":
            raise InfrastructureError("현재 management.deletionPolicy에서는 원격 삭제를 허용하지 않습니다.")
        plan_service = InfrastructurePlanService(
            service,
            args.plans_root,
            args.results_root,
            instance_identity,
            _tool_version(),
        )
        if args.action == "discover":
            result = service.discover(args.kind)
            rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
            if args.output:
                output = Path(args.output)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(rendered, encoding="utf-8")
                print(f"discovery 결과 저장 완료: {output.resolve()}")
            else:
                print(rendered, end="")
            return 0
        if args.action == "adopt":
            if args.kind and not args.all:
                raise InfrastructureError("--kind는 --all과 함께 사용해야 합니다.")
            if args.all and args.force:
                raise InfrastructureError("전체 adopt에서는 --force를 사용할 수 없습니다.")
            selectors = service.discover_selectors(args.kind) if args.all else args.resource
            plan = service.plan_adopt(selectors, force=args.force)
            counts = {action: sum(item["action"] == action for item in plan) for action in ("CREATE", "OVERWRITE", "SKIP", "CONFLICT")}
            print("Adopt plan")
            for kind in sorted({item["kind"] for item in plan}):
                print(f"  {kind:16} {sum(item['kind'] == kind for item in plan)}")
            print("Actions")
            for action in ("CREATE", "OVERWRITE", "SKIP", "CONFLICT"):
                print(f"  {action:9} {counts[action]}")
            for item in plan:
                if item["action"] == "CONFLICT":
                    print(f"  CONFLICT {item['kind']}/{item['remoteId']}: {item['path']} ({item['reason']})")
            if counts["CONFLICT"]:
                print("충돌이 있어 manifest를 생성하지 않았습니다.", file=sys.stderr)
                return 1
            if args.dry_run:
                print("Dry-run 완료: 파일을 변경하지 않았습니다.")
                return 0
            created = service.apply_adopt_plan(plan)
            for path in created:
                print(f"manifest 생성 완료: {path.resolve()}")
            return 0
        if args.action == "status":
            result = service.status()
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            elif not result:
                print("관리 대상 인프라 manifest가 없습니다.")
            else:
                for item in result:
                    print(f"{item['state']:14} {item['kind']}/{item['name']}")
            return 2 if any(item["state"] != "IN_SYNC" for item in result) else 0
        if args.action == "plan":
            path, artifact, reused = plan_service.create_plan(args.delete or [], args.expires_in)
            operations = artifact["spec"]["operations"]
            print("Infrastructure plan")
            print(f"  planHash    {artifact['metadata']['planHash']}")
            print(f"  expiresAt   {artifact['metadata']['expiresAt']}")
            print(f"  operations  {len(operations)}")
            for action in ("CREATE", "UPDATE", "DELETE"):
                print(f"  {action:10} {sum(item['action'] == action for item in operations)}")
            print(f"  artifact    {path.resolve()}")
            if reused:
                print("동일한 관찰 결과의 유효한 기존 plan을 재사용했습니다.")
            return 0
        if args.action == "apply":
            require_instance_mode(repository_context, "apply")
            artifact = plan_service.load_plan(args.plan)
            result_path, result = plan_service.apply(
                artifact,
                args.approve_plan,
                args.approve_create or [],
                args.approve_delete or [],
            )
            for item in result["spec"]["operations"]:
                print(f"{item['status']:10} {item['action']:6} {item['kind']}/{item['name']}")
            print(f"apply 결과: {result_path.resolve()}")
            return 0 if result["spec"]["status"] == "VERIFIED" else 1
    except (ConfigError, InfrastructureError, RepositoryContextError, OSError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
