# 저장소 에이전트 지침

## 목적과 관리 경계

이 저장소의 `main`은 Automation별 GitOps 저장소를 만드는 공통 템플릿이다. 템플릿으로 생성된 저장소 하나는 Automation 인스턴스 하나를 관리하며, 여러 Automation은 저장소를 추가해 분리한다.

- 템플릿 `main`에는 실제 endpoint, 인스턴스 콘텐츠와 상태를 넣지 않는다.
- 생성된 저장소의 `main`은 연결된 Automation의 승인된 원하는 상태다.
- 생성된 저장소의 `instance.yaml`, `infrastructure/`, `content/`는 Git이 소유하는 상태다.
- `secrets.json`, discovery cache와 생성된 Terraform 입력은 로컬 상태이며 커밋하지 않는다.
- 기존 인스턴스는 import 후 검토된 baseline부터 Git 관리 대상으로 삼는다.

수명주기, import, sync, release, 설정 또는 loop 작업에는 `$vcf-gitops-lifecycle` 스킬을 사용한다.

## 저장소 실행 모드

템플릿에서 함께 배포되는 AGENTS, Skill과 Loop는 작업 전에 저장소 실행 모드를 판정한다.

- **템플릿 모드:** `instance.yaml`이 Git에 추적되지 않는다. 실제 연결은 `instance.local.yaml`, `secrets.local.json`, `.gitops/infrastructure-test/`만 사용하고 Loop와 원격 mutation을 실행하지 않는다.
- **인스턴스 모드:** `instance.yaml`이 Git에 추적되고 설정 검증을 통과한다. `infrastructure/`와 `content/`를 해당 Automation의 원하는 상태로 취급한다.
- **모호한 모드:** `instance.yaml`이 존재하지만 untracked이다. 실제 인스턴스 저장소의 승인된 baseline인지 확인할 수 없으므로 템플릿 모드로 취급하고 Loop와 원격 mutation을 중단한다.

판정에는 단순 파일 존재 여부가 아니라 `git ls-files --error-unmatch instance.yaml`을 사용한다. 생성된 인스턴스 저장소도 `instance.yaml`과 최초 baseline이 검토·커밋되기 전에는 Loop를 활성화하지 않는다.

`python3 tooling/vcf/cli.py context`로 판정 결과를 확인한다. 인프라 CLI는 템플릿과 모호한 모드에서 `instance.local.yaml`, `secrets.local.json`, `.gitops/` 출력 경계를 강제하며, 향후 원격 mutation은 인스턴스 모드에서만 허용한다.

## 작성 언어

- `AGENTS.md`, `.agents/skills/**`, 관련 지침과 UI 설명은 기본적으로 한국어로 작성한다.
- 코드 식별자, 명령, API 필드와 제품 고유 명칭은 원문을 유지한다.
- 사용자가 다른 언어를 명시하거나 외부 배포 대상이 요구할 때만 예외로 한다.

## 경로 계약

| 경로 | 책임 |
| --- | --- |
| `instance.example.yaml` | 템플릿에서 제공하는 인스턴스 정의 예시 |
| `instance.yaml` | 생성된 저장소가 추적하는 Automation 연결, 범위와 관리 정책 |
| `secrets.json` | refresh token과 외부 시스템 자격 증명, Git 제외 |
| `infrastructure/` | 리소스별 Day-0 원하는 상태와 원격 ID |
| `foundation/automation/terraform/` | 이전/선택적 Terraform 기반 구성, native와 동시 소유 금지 |
| `content/automation/` | Automation 콘텐츠 원본 |
| `content/orchestrator/` | vRO 콘텐츠 원본 |
| `lifecycle/` | 콘텐츠의 Day-0/1/2 분류 |
| `tooling/vcf/` | 설정, API client, sync, release 도구 |
| `tooling/template/` | 템플릿에서 인스턴스 저장소를 초기화하는 도구 |
| `releases/` | 버전별 불변 릴리스 |
| `automation/loops/` | 향후 승인 기반 reconcile loop |

경로를 바꾸면 호출 코드, 인스턴스 정의, 문서와 테스트를 같은 변경에서 갱신한다.

## Day와 전달 기능

- Day-0: 인스턴스 onboarding, import baseline, Cloud Account, Zone, Profile, Project, vRO bootstrap
- Day-1: Blueprint, Catalog, Form, Custom Resource, ABX와 provisioning Workflow 개발
- Day-2: Resource Action, 운영 Workflow, Policy, Subscription과 remediation
- import, status, pull, push, release, restore는 특정 Day가 아니라 모든 Day를 지원하는 전달 기능이다.

같은 콘텐츠를 Day별 디렉터리에 복제하지 않는다. `lifecycle/*.yaml`에서 경로와 사용 목적을 분류한다.

## 브랜치와 변경 절차

- 환경을 브랜치로 표현하지 않는다. Automation 한 대마다 저장소를 분리한다.
- 템플릿의 실제 연동 검증은 짧은 `integration/*` 브랜치와 무시되는 `instance.local.yaml`, `secrets.local.json`을 사용한다.
- 템플릿 연동의 adopt 출력은 무시되는 `.gitops/infrastructure-test/`에 생성한다. 실제 인스턴스의 `instance.yaml`이나 `infrastructure/` 결과를 템플릿 변경에 섞지 않는다.
- `--instance instance.local.yaml`은 입력 설정만 선택하며 adopt 출력 경로를 바꾸지 않는다. 템플릿 시험에서는 `--infrastructure-root .gitops/infrastructure-test`도 별도로 명시한다. 인프라 CLI는 이 경계를 벗어난 템플릿·모호한 모드 실행을 거부한다.
- 템플릿 `main`에는 재사용 가능한 변경만 병합하고 실제 인스턴스 설정·import 결과·state·시험 릴리스는 병합하지 않는다.
- 생성된 저장소에서는 짧은 `feature/*`, `foundation/*`, `import/*`, `drift/*`, `fix/*`, `hotfix/*`, `ai/*` 브랜치를 사용한다.
- import와 pull 결과는 검토 없이 `main`에 병합하지 않는다.
- PR 브랜치에서는 원격 push를 자동 실행하지 않는다.
- 세부 전략은 `docs/BRANCHING.md`를 따른다.

## 안전 경계

- `apply`, `terraform apply`, `restore`, `push`, `push-all`은 원격 변경이다. 사용자가 작업과 대상을 명시적으로 승인한 경우에만 실행한다.
- `foundation/automation/terraform/`에서 기존 state/backend 연결을 확인하기 전에는 plan 결과를 신뢰하거나 apply하지 않는다.
- `terraform plan`, `status`, 지원되는 dry-run을 먼저 사용한다.
- secret, token, password, Terraform state, cache 또는 생성된 입력 파일을 커밋하지 않는다.
- 템플릿 연동 시험에서는 실제 설정 파일 경로를 `--instance`, `--secrets`로 명시한다.
- `adopt`는 인자 생략으로 전체를 선택하지 않는다. 전체 채택은 `--all`을 명시하고 먼저 `--dry-run`을 실행하며, 필요하면 반복 가능한 `--kind`로 범위를 제한한다.
- `discover`, `adopt`, `status` 중 인증·권한·API·ID 또는 manifest 충돌이 발생하면 불완전한 결과를 적용하지 않고 중단한다.
- 템플릿 실제 연동 후 `git status --short`로 `instance.yaml`, 실제 `infrastructure/`, secret, cache와 시험 산출물이 변경 집합에 없는지 확인한다.
- 릴리스 아티팩트를 직접 수정하지 않고 release 도구로 다시 생성한다.
- 일반 sync를 임의 bootstrap이나 신규 생성으로 확장하지 않는다.
- `metadata.remoteId`가 없는 manifest는 생성 후보일 뿐이며 자동 생성하지 않는다.
- Git에서 manifest가 사라져도 원격 리소스를 자동 삭제하지 않는다.
- loop는 인증·권한·스키마·정책 또는 반복되는 수렴 실패에서 중단한다.
- `.example.yaml` Loop는 실행하지 않는다. 실제 Loop는 인스턴스 모드에서만 허용하며 `spec.enabled: true`, `spec.repositoryMode: instance`, 추적된 `instance.yaml`과 일치하는 `spec.instanceRef`를 요구한다.

## 로컬 검증

```bash
python3 -m py_compile tooling/vcf/*.py tooling/template/*.py
python3 -m unittest discover -s tests
python3 tooling/vcf/configure.py validate \
  --instance instance.example.yaml \
  --secrets secrets.example.json
python3 tooling/vcf/cli.py --infrastructure-root infrastructure validate
python3 tooling/vcf/cli.py context
terraform -chdir=foundation/automation/terraform fmt -check
```

스킬 변경 시 다음을 추가한다.

```bash
python3 /Users/ujmoon/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/vcf-gitops-lifecycle
```

로컬 구문·구조 검증에 실제 자격 증명이나 원격 연결을 요구하지 않는다.
