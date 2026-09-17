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

## 남은 작업

1. `vcf_sync.py`와 `vcf_release.py`를 import 가능한 하위 패키지로 분리
2. native 인프라 plan 스키마와 승인 hash 도입
3. pull-preview와 명시적 accept 흐름 추가
4. Project/Profile부터 제한적 apply와 verify 구현
5. 신규 Automation용 local-content release build 명령 추가
6. lifecycle manifest 스키마 검증 추가
7. observe-only loop부터 단계적으로 구현

이전 `vra/`의 로컬 Terraform state, tfvars와 provider cache는 템플릿 전환 과정에서 제거했습니다. Terraform 구성은 이전/선택적 greenfield 호환 경로로 남아 있으나 `management.infrastructure: native`와 같은 리소스를 동시에 소유하지 않습니다.
