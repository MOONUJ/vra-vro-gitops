# 템플릿 전환 상태

## 완료

- 공통 템플릿과 생성된 인스턴스 저장소 역할 분리
- Automation 한 대를 생성된 저장소의 관리 경계로 정의
- 템플릿용 `instance.example.yaml`과 생성 저장소용 `instance.yaml` 분리
- 인스턴스 저장소 bootstrap 도구 추가
- Terraform을 `foundation/automation/terraform/`으로 이동
- Automation/vRO 콘텐츠를 `content/`로 이동
- sync/release 도구를 `tooling/vcf/`로 이동
- 릴리스 기본 위치를 `releases/`로 이동
- 기존 `gitops/` wrapper와 legacy 단일 설정 제거
- Day-0/1/2 lifecycle manifest 추가
- `v1alpha2` 인스턴스 설정과 리소스별 native 인프라 manifest 도입
- read-only `discover`, 선택적 `adopt`, `validate`, `status` CLI 도입
- native 인프라 불변 plan, 승인 hash, 제한적 apply와 verify 도입
- 콘텐츠 status의 공통 JSON observation과 fail-closed 오류 처리 도입
- 원격 mutation operation registry와 instance/clean-worktree 실행 경계 통합
- 콘텐츠별 identity sidecar, canonical normalization/hash와 migration preview 도입
- 콘텐츠 pull-preview, hash 승인 accept와 direct pull 쓰기 제거
- 콘텐츠 immutable plan, exact resource/create approval, lock, journal, selective apply와 verify 도입
- read-only export, local-content release build, SemVer·불변 경로와 SHA-256 provenance 도입
- restore immutable plan, artifact 승인, 단일 project mapping, lock/journal과 적용 후 검증 도입
- versioned manifest schema, policy hash 기반 apply gate와 credential 없는 PR CI 도입
- installable `vcf-gitops` package, tool version pin과 desired-state 보호 template update 도입
- instance 전용 observe-only Loop, lock, 제한 재시도, journal과 반복 drift escalation 도입

## 남은 작업

1. 별도 Pilot 인스턴스에서 package 기반 CLI와 native apply 검증
2. 개발환경 Day-2 콘텐츠 한 건으로 승인 기반 reconcile Pilot 수행
3. Pilot 증거를 바탕으로 1.0 package 경계와 기존 script 제거 여부 결정

이전 `vra/`의 로컬 Terraform state, tfvars와 provider cache는 템플릿 전환 과정에서 제거했습니다. Terraform 구성은 이전/선택적 greenfield 호환 경로로 남아 있으나 `management.infrastructure: native`와 같은 리소스를 동시에 소유하지 않습니다.
