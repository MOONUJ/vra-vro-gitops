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

## 남은 작업

1. `vcf_sync.py`와 `vcf_release.py`를 import 가능한 하위 패키지로 분리
2. `import/adopt` 전용 명령과 민감정보 검사 추가
3. 신규 Automation용 local-content release build 명령 추가
4. lifecycle manifest 스키마 검증 추가
5. JSON status/plan 출력과 승인 가능한 변경 계획 도입
6. observe-only loop부터 단계적으로 구현

이 작업 트리에 남아 있는 기존 `vra/`의 로컬 Terraform state와 `.terraform`은 템플릿 파일이 아니며 Git에도 포함하지 않습니다. 기존 인스턴스를 채택하는 저장소에서 backend와 state 이전 계획을 별도로 검토해야 합니다. 연결 전 plan은 기존 리소스를 신규 생성 대상으로 표시할 수 있으므로 apply하지 않습니다.
