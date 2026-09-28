# 템플릿 운영

## 역할

이 저장소는 VCF Automation 인스턴스 저장소를 생성하기 위한 기준 템플릿입니다. 실제 인스턴스마다 템플릿으로 새 저장소를 만들고, 저장소와 Automation을 일대일로 대응시킵니다.

일반 fork보다 Template Repository를 기본으로 사용합니다. 생성된 저장소가 독립된 이력과 권한을 가지므로 인스턴스 간 변경과 비밀정보 경계를 분리하기 쉽습니다.

## 템플릿에 포함하는 것

- 디렉터리 구조와 lifecycle manifest
- native 인프라 GitOps, 선택적 Terraform, sync, release와 bootstrap 도구
- `instance.example.yaml`, `secrets.example.json`
- AGENTS, Skill, Loop 계약
- 공통 테스트와 문서
- `.template-version`
- `.vcf-gitops-version`과 installable Python package metadata

## 템플릿에 포함하지 않는 것

- 실제 endpoint가 담긴 `instance.yaml`
- 자격 증명, token, 인증서
- Terraform state와 plan
- 특정 Automation에서 import한 콘텐츠
- 특정 인스턴스용 release artifact와 실행 로그

## 생성과 초기화

GitHub에서 Template Repository로 설정하고 **Use this template**로 저장소를 생성합니다. 새 저장소에서 다음 명령을 실행합니다.

최초 baseline까지의 전체 순서는 [처음 시작하기](GETTING_STARTED.md)를 따릅니다.

```bash
python3 tooling/template/bootstrap.py \
  --name automation-seoul-prod \
  --endpoint https://automation.example.com \
  --environment-tag seoul-prod \
  --package-name com.example.automation.seoul.prod
```

생성된 `instance.yaml`은 비밀 없는 연결·관리 정책이므로 Git에 추가합니다. 생성된 `secrets.json`은 권한 `0600`으로 만들고 Git에서 제외하며 placeholder를 실제 값으로 교체합니다. Day-0 원하는 상태는 `infrastructure/`에 별도 manifest로 추가합니다.

AGENTS, Skill과 Loop 예시도 템플릿에서 함께 복사됩니다. 이들은 `instance.yaml`의 Git 추적 여부로 템플릿 모드와 인스턴스 모드를 구분합니다. 생성 직후 `instance.yaml`이 아직 untracked인 동안은 Loop를 활성화하지 않으며, 최초 baseline을 검토·커밋한 뒤 실제 Loop 파일의 `.example`을 제거하고 `instanceRef`와 `enabled`를 명시합니다.

## 버전과 업데이트

`.template-version`은 저장소를 생성하거나 마지막으로 공통 변경을 반영한 템플릿 버전을 나타냅니다. 템플릿 변경은 tag와 changelog로 배포하는 방식을 권장합니다.

`.vcf-gitops-version`은 인스턴스가 검증한 CLI package 버전을 고정합니다. `pyproject.toml`에서 wheel을 빌드해 설치한 환경에서는 `vcf-gitops` 단일 entry point를 사용할 수 있습니다. 0.x 문서는 저장소에 포함된 `tooling/vcf/cli.py`, `vcf_sync.py`, `vcf_release.py` 경로를 기준으로 하며 기존 script 경로는 1.0에서 제거 여부를 다시 결정합니다.

새 template checkout을 `--source`로 지정한 뒤 먼저 preview합니다.

```bash
python3 ../vcf-gitops-template/tooling/vcf/template_update.py \
  --source ../vcf-gitops-template --destination . --json
python3 ../vcf-gitops-template/tooling/vcf/template_update.py \
  --source ../vcf-gitops-template \
  --destination . \
  --apply --approve-version 0.3.0
```

새 template checkout의 updater를 직접 실행하므로 기존 인스턴스에 설치된 이전 updater가 새 migration 계약을 놓치지 않습니다.

업데이트는 `tooling/`, `schemas/`, `docs/`, `tests/`, `.agents/`, package/version 파일만 생성·갱신하고 파일을 삭제하지 않습니다. 이 경로들은 template 공통 계약으로 취급하며 기존 인스턴스에서 수정한 파일은 preview와 PR에서 충돌 여부를 검토합니다. 인스턴스별 소개를 작성할 수 있도록 최상위 `README.md`는 기존 저장소에서 덮어쓰지 않으며 새 운영 가이드는 `docs/`를 통해 배포합니다. `instance.yaml`, `secrets*`, `infrastructure/`, `content/`, `lifecycle/`, `governance/`, `releases/`와 `.gitops/`는 항상 보호합니다. 보호된 설정 변경이 필요하면 preview의 `spec.migrations`에 표시되고 apply는 중단됩니다. 같은 작업 브랜치에서 `instance.yaml`을 먼저 수정하고 preview를 다시 생성해 migration이 없어져야 공통 tooling을 적용할 수 있습니다. 실제 적용도 인스턴스 저장소의 별도 PR에서 검토합니다.

0.3.0에서 기존 external Orchestrator 인스턴스는 다음 설정을 먼저 추가합니다.

```yaml
spec:
  orchestrator:
    deployment: external
    endpoint: https://orchestrator.example.com
    verifySsl: true
    discovery:
      mode: package
      requireNonEmpty: true
    package:
      name: com.example.automation.dev
      localPath: content/orchestrator/packages/com.example.automation.dev.package
```

설정을 수정한 뒤 preview에서 `migrations: []`를 확인하고 updater를 적용합니다.

```bash
python3 ../vcf-gitops-template/tooling/vcf/template_update.py \
  --source ../vcf-gitops-template \
  --destination . \
  --apply \
  --approve-version 0.3.0
```

## 실제 연동 검증

템플릿 저장소 안에서 검증해야 한다면 `integration/*` 브랜치와 로컬 전용 설정을 사용합니다. 재사용 가능한 수정만 `main`에 병합합니다. 안정화 이후에는 템플릿으로 생성한 pilot 저장소를 사용하여 생성부터 import, plan, sync까지 전체 흐름을 검증합니다.
