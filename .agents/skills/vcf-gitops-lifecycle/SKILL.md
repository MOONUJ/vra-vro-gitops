---
name: vcf-gitops-lifecycle
description: VCF Automation GitOps 템플릿과 Automation 한 대당 하나인 인스턴스 저장소의 수명주기 변경을 계획, 구현 또는 검토한다. 템플릿 bootstrap, 기존 Automation import, Day-0 기반, Day-1 개발, Day-2 동기화, release, 구조 개편과 reconcile loop에 사용한다. 관련 없는 VMware 질문에는 사용하지 않는다.
---

# VCF Automation GitOps 수명주기

이 프로젝트는 공통 GitOps 템플릿과 그 템플릿으로 생성된 인스턴스 저장소를 구분한다. 템플릿은 실제 인스턴스 상태를 갖지 않으며, 생성된 저장소 하나가 Automation 한 대를 관리한다. 여러 Automation은 저장소를 추가해 격리한다.

이 스킬과 이 스킬이 만드는 지침, 참조 문서와 UI 설명은 사용자가 다른 언어를 요구하지 않는 한 한국어로 작성한다. 코드 식별자, 명령, API 필드와 제품 고유 명칭은 원문을 유지한다.

## 시작 절차

1. `AGENTS.md`, `STRUCTURE.md`와 관련 문서를 읽는다.
2. `git ls-files --error-unmatch instance.yaml`로 현재 작업 대상이 공통 템플릿인지 생성된 인스턴스 저장소인지 확인한다. 단순 파일 존재 여부로 판정하지 않는다.
3. 작업을 서비스 수명주기와 전달 기능으로 각각 분류한다.
4. `instance.yaml`, 콘텐츠, 도구, 원격 상태 중 어느 계약이 바뀌는지 확인한다.
5. 경로·payload·설정·명령 변경 전에 호출자를 조사한다.

## 저장소 실행 모드

- **템플릿 모드:** `instance.yaml`이 Git에 추적되지 않는다. 실제 연결은 local 설정과 `.gitops/infrastructure-test/`에 한정하고 Loop와 원격 mutation을 실행하지 않는다.
- **인스턴스 모드:** `instance.yaml`이 Git에 추적되고 설정 검증을 통과한다. `infrastructure/`와 `content/`를 승인된 원하는 상태로 취급한다.
- **모호한 모드:** `instance.yaml`이 존재하지만 untracked이다. 승인된 인스턴스 baseline으로 간주하지 않고 템플릿 모드의 안전 경계를 적용한다.

인스턴스 저장소도 최초 baseline을 검토하고 `instance.yaml`을 커밋하기 전에는 Loop를 활성화하지 않는다. 사용자의 실제 저장소라는 설명만으로 추적되지 않은 설정에 원격 변경 권한을 부여하지 않는다.

판정 결과가 필요하면 `python3 tooling/vcf/cli.py context`를 사용한다. 인프라 CLI는 템플릿과 모호한 모드의 local 설정·`.gitops/` 출력 경계를 검증하며, 원격 mutation 구현은 `repository.require_instance_mode()`를 통과해야 한다.

## 서비스 수명주기

| 단계 | 목적 | 주요 경로 |
| --- | --- | --- |
| Day-0 | 인스턴스 onboarding과 기반 구성 | `instance.yaml`, `infrastructure/`, package bootstrap |
| Day-1 | 카탈로그와 신규 리소스 프로비저닝 개발 | Blueprint, ABX, Form, Custom Resource, provisioning Workflow |
| Day-2 | 기존 리소스 운영과 변경 | Resource Action, 운영 Workflow, Policy, Subscription, remediation |

Workflow와 Action처럼 여러 단계에서 사용되는 콘텐츠는 복제하지 않는다. `lifecycle/*.yaml`에서 용도를 분류한다.

## 전달 기능

- **Import/adopt:** discovery inventory에서 Git이 소유할 리소스만 선택하고, `metadata.remoteId`가 포함된 리소스별 manifest를 `import/*` 브랜치에서 검토한 뒤 baseline으로 병합한다.
- **Sync:** `status`로 drift를 관찰하고 방향을 결정한 후 `pull` 또는 승인된 `push`를 실행한다.
- **Release:** 변경된 릴리스마다 새 버전을 만들고 manifest, vRA archive, vRO package를 한 단위로 유지한다.
- **Restore/bootstrap:** 대상과 버전을 확인하고 명시적 승인 후 실행한다.
- **Loop:** [references/loop-contract.md](references/loop-contract.md)와 `docs/LOOP.md`를 읽고 observe, plan, approval, apply, verify, record를 분리한다.

## 설정

- 템플릿에는 `instance.example.yaml`만 두고 실제 endpoint와 인스턴스 콘텐츠를 넣지 않는다.
- `instance.yaml`에는 비밀 없는 endpoint, 조직, GitOps 범위와 관리 정책을 기록한다.
- `infrastructure/`에는 리소스별 원하는 상태와 `metadata.remoteId`를 기록한다. timestamp, owner, 링크 같은 관측 필드는 기록하지 않는다.
- `secrets.json`에는 refresh token 같은 자격 증명만 기록하고 커밋하지 않는다.
- 설정 스키마를 바꾸면 loader, 예시, 문서와 테스트를 함께 갱신한다.
- 단일 `config.json`과 `gitops/` 호환 경로를 다시 도입하지 않는다.
- native와 Terraform이 동일 원격 리소스를 동시에 소유하게 하지 않는다.

## 브랜치

템플릿 `main`은 재사용 가능한 기준 구조이고, 생성된 저장소의 `main`은 승인된 원하는 상태다. 환경을 브랜치로 사용하지 않는다. 템플릿의 실제 연동 시험은 `integration/*`와 Git에서 제외된 로컬 설정을 사용하며, 인스턴스 데이터는 템플릿 `main`에 병합하지 않는다. 생성된 저장소의 작업에는 짧은 `feature/*`, `foundation/*`, `import/*`, `drift/*`, `fix/*`, `hotfix/*`, `ai/*` 브랜치와 PR을 사용한다.

## 실제 연동 검증

템플릿에서 Automation 연결을 검증할 때는 실제 endpoint나 가져온 상태가 변경 집합에 섞이지 않도록 다음 경계를 지킨다.

- `instance.local.yaml`, `secrets.local.json`을 사용하고 모든 CLI에 `--instance`, `--secrets`를 명시한다.
- 입력 설정 경로와 adopt 출력 경로는 독립적이다. `--instance instance.local.yaml`만으로 출력이 시험 경로로 전환되지 않으므로 템플릿에서는 `--infrastructure-root .gitops/infrastructure-test`도 반드시 명시한다. 인프라 CLI는 이 경계를 벗어난 실행을 거부한다.
- read-only `discover`로 인증, 권한, endpoint와 페이지네이션을 먼저 확인한다.
- 전체 채택은 인자 생략이 아니라 `adopt --all --dry-run`으로 preflight한 뒤 실행한다. 필요하면 반복 가능한 `--kind`로 범위를 제한한다.
- 템플릿의 adopt 출력은 `.gitops/infrastructure-test/`에 만들고 `validate`, `status`로 adopt 직후 `IN_SYNC`인지 확인한다.
- 인증·권한·API·ID·상세 응답 또는 경로 충돌이 하나라도 있으면 전체 adopt를 중단한다.
- 연동 시험 후 `git status --short`를 확인하고 실제 `instance.yaml`, `infrastructure/`, secret, cache와 시험 산출물을 템플릿 PR에서 제외한다.
- 템플릿 모드와 모호한 모드에서는 `automation/loops/`를 예시·계약으로만 다루고 실행하지 않는다.

## 검증

변경된 Python compile, 설정·인프라·lifecycle manifest parsing, 테스트, 남아 있는 Terraform의 format, skill validation과 `git diff`를 확인한다. 실제 연결 검증은 별도 단계이며 일반 로컬 검증에 자격 증명을 요구하지 않는다. 원격 변경 전에는 status와 불변 plan을 우선한다. 권한이나 일부 discovery 실패는 빈 목록으로 처리하지 않으며, manifest 파일 부재만으로 원격 리소스를 삭제하지 않는다.
