# 개선 로드맵과 작업 티켓

이 디렉터리는 VCF Automation GitOps를 AI Agent가 안전하게 관찰, 개발, 테스트하고 승인된 변경만 적용할 수 있도록 만드는 활성 backlog입니다. 완료된 티켓은 코드, 문서와 Git 이력에 결과를 남기고 이 디렉터리에서는 제거합니다.

## 우선순위

- `Critical`: 원격 상태 오판이나 승인되지 않은 mutation을 막기 위한 운영 선행 조건
- `High`: GitOps 수렴, 정책과 검증에 필요한 핵심 기능
- `Medium`: 공통 배포 구조와 제한적 자동화 확대

## 단계별 실행 순서

| 단계 | ID | 제목 | 상태 | 우선순위 |
| ---: | --- | --- | :---: | :---: |
| 7 | [012](012-day2-approved-reconcile-pilot.md) | 개발환경 Day-2 승인 기반 Reconcile Pilot | LOCAL_MANUAL_PILOT_COMPLETE | Medium |
| 7 | [015](015-pilot-rbac-and-approval-separation.md) | CI Apply Runner RBAC와 승인자 분리 | DEFERRED_UNTIL_CI_APPLY | Medium |

## 의존 관계

```text
012 로컬 수동 기능·복구 Pilot 완료
          ↓
CI 자동 apply 도입 결정
          ↓
015 runner RBAC·credential·승인자 분리
          ↓
production 확대 여부 별도 결정
```

## 티켓 운영 규칙

1. 티켓마다 짧은 `feature/*`, `fix/*`, `ai/*` 브랜치와 PR을 사용합니다.
2. 구현 PR에는 해당 티켓의 완료 기준과 검증 결과를 포함합니다.
3. 원격 mutation 검증은 별도 인스턴스 저장소와 명시적 사용자 승인으로만 수행합니다.
4. 템플릿 저장소에는 실제 자격 증명, `.gitops/` 산출물, 원격 상태와 인스턴스 전용 콘텐츠를 커밋하지 않습니다.
5. 완료된 티켓은 구현 PR 또는 commit에 결과를 기록한 뒤 파일과 이 README의 항목을 제거합니다.
6. 구현 중 범위가 커지면 티켓을 분리하며, 선행 관계와 로드맵을 같은 변경에서 갱신합니다.
