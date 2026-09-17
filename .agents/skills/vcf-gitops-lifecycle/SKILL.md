---
name: vcf-gitops-lifecycle
description: VCF Automation GitOps 템플릿과 Automation 한 대당 하나인 인스턴스 저장소의 수명주기 변경을 계획, 구현 또는 검토한다. 템플릿 bootstrap, 기존 Automation import, Day-0 기반, Day-1 개발, Day-2 동기화, release, 구조 개편과 reconcile loop에 사용한다. 관련 없는 VMware 질문에는 사용하지 않는다.
---

# VCF Automation GitOps 수명주기

이 프로젝트는 공통 GitOps 템플릿과 그 템플릿으로 생성된 인스턴스 저장소를 구분한다. 템플릿은 실제 인스턴스 상태를 갖지 않으며, 생성된 저장소 하나가 Automation 한 대를 관리한다. 여러 Automation은 저장소를 추가해 격리한다.

이 스킬과 이 스킬이 만드는 지침, 참조 문서와 UI 설명은 사용자가 다른 언어를 요구하지 않는 한 한국어로 작성한다. 코드 식별자, 명령, API 필드와 제품 고유 명칭은 원문을 유지한다.

## 시작 절차

1. `AGENTS.md`, `STRUCTURE.md`와 관련 문서를 읽는다.
2. 현재 작업 대상이 공통 템플릿인지 생성된 인스턴스 저장소인지 확인한다.
3. 작업을 서비스 수명주기와 전달 기능으로 각각 분류한다.
4. `instance.yaml`, 콘텐츠, 도구, 원격 상태 중 어느 계약이 바뀌는지 확인한다.
5. 경로·payload·설정·명령 변경 전에 호출자와 호환 wrapper를 조사한다.

## 서비스 수명주기

| 단계 | 목적 | 주요 경로 |
| --- | --- | --- |
| Day-0 | 인스턴스 onboarding과 기반 구성 | `instance.yaml`, `foundation/`, package bootstrap |
| Day-1 | 카탈로그와 신규 리소스 프로비저닝 개발 | Blueprint, ABX, Form, Custom Resource, provisioning Workflow |
| Day-2 | 기존 리소스 운영과 변경 | Resource Action, 운영 Workflow, Policy, Subscription, remediation |

Workflow와 Action처럼 여러 단계에서 사용되는 콘텐츠는 복제하지 않는다. `lifecycle/*.yaml`에서 용도를 분류한다.

## 전달 기능

- **Import/adopt:** 기존 서버 상태를 `import/*` 브랜치로 가져오고 민감정보와 휘발 필드를 검토한 뒤 baseline으로 병합한다.
- **Sync:** `status`로 drift를 관찰하고 방향을 결정한 후 `pull` 또는 승인된 `push`를 실행한다.
- **Release:** 변경된 릴리스마다 새 버전을 만들고 manifest, vRA archive, vRO package를 한 단위로 유지한다.
- **Restore/bootstrap:** 대상과 버전을 확인하고 명시적 승인 후 실행한다.
- **Loop:** [references/loop-contract.md](references/loop-contract.md)와 `docs/LOOP.md`를 읽고 observe, plan, approval, apply, verify, record를 분리한다.

## 설정

- 템플릿에는 `instance.example.yaml`만 두고 실제 endpoint와 인스턴스 콘텐츠를 넣지 않는다.
- `instance.yaml`에는 비밀 없는 endpoint, 조직, GitOps 범위와 인프라 원하는 상태를 기록한다.
- `secrets.json`에는 refresh token과 외부 시스템 자격 증명만 기록하고 커밋하지 않는다.
- 설정 스키마를 바꾸면 loader, 예시, 문서와 테스트를 함께 갱신한다.
- 기존 단일 JSON 설정은 호환 경로로만 유지하고 새 사용법으로 안내하지 않는다.

## 브랜치

템플릿 `main`은 재사용 가능한 기준 구조이고, 생성된 저장소의 `main`은 승인된 원하는 상태다. 환경을 브랜치로 사용하지 않는다. 템플릿의 실제 연동 시험은 `integration/*`와 Git에서 제외된 로컬 설정을 사용하며, 인스턴스 데이터는 템플릿 `main`에 병합하지 않는다. 생성된 저장소의 작업에는 짧은 `feature/*`, `foundation/*`, `import/*`, `drift/*`, `fix/*`, `hotfix/*`, `ai/*` 브랜치와 PR을 사용한다.

## 검증

변경된 Python compile, 설정과 lifecycle manifest parsing, 테스트, Terraform format, skill validation과 `git diff`를 확인한다. 원격 변경 전에는 plan 또는 dry-run을 우선하고 로컬 검증에 실제 자격 증명을 요구하지 않는다.
