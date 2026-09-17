# 브랜치 전략

## 저장소 역할 구분

- 템플릿 저장소의 `main`: 실제 인스턴스 상태가 없는 재사용 가능한 기준 구조
- 생성된 인스턴스 저장소의 `main`: 연결된 Automation의 승인된 원하는 상태
- Automation 환경: 브랜치가 아니라 저장소로 분리

## 템플릿 저장소

일반 개발에는 `feature/*`, `fix/*`, `ai/*`를 사용합니다. 실제 Automation과 연결해야 하는 검증에는 짧은 `integration/*` 브랜치를 사용합니다.

```text
feature 또는 fix → local validation → integration/* → 실제 lab 검증
                → 민감/인스턴스 산출물 제거 확인 → PR → main
```

`integration/*`는 환경을 장기간 표현하는 브랜치가 아니라 일회성 검증 브랜치입니다. 다음 파일은 커밋하지 않습니다.

- `instance.local.yaml`, `secrets.local.json`, token과 인증서
- Terraform state, plan과 생성된 tfvars
- 실제 Automation에서 가져온 인스턴스 전용 콘텐츠
- 시험 중 생성된 릴리스와 로그

실제 연결 시 모든 CLI에 로컬 설정 경로를 명시합니다.

```bash
python3 tooling/vcf/vcf_sync.py status \
  --instance instance.local.yaml \
  --secrets secrets.local.json
```

PR에는 실제 연결로 확인한 재사용 가능한 코드, 테스트, 문서만 남깁니다. 가능하면 최종 검증은 템플릿으로 생성한 별도의 pilot 저장소에서 수행합니다.

## 생성된 인스턴스 저장소

| 패턴 | 용도 |
| --- | --- |
| `feature/*` | Blueprint, Workflow, Action, ABX 개발 |
| `foundation/*` | Cloud Account, Zone, Profile, Project 변경 |
| `import/*` | 기존 Automation baseline import |
| `drift/*` | 서버 변경을 Git에 수용할지 검토 |
| `fix/*` | 일반 수정 |
| `hotfix/*` | 긴급 운영 수정 |
| `ai/*` | AGENTS, Skill, Tool, Loop 변경 |

```text
branch → local validation → PR → review → main merge
       → plan/dry-run → environment approval → apply → verify → tag
```

`main`에는 직접 push와 force push를 금지하고 PR·검증·승인을 요구합니다. PR 브랜치에서 원격 Automation으로 자동 push하지 않습니다. native 인프라 변경은 status와 승인 가능한 plan을, Terraform 변경은 plan을, 콘텐츠 변경은 normalized diff를 검토합니다.

## Import와 drift

- 최초 import는 `import/initial-baseline`에서 수행하고 비밀값과 서버 종속 필드를 검토합니다.
- UI 변경을 발견하면 `drift/YYYY-MM-DD` 브랜치에서 pull 결과를 검토합니다.
- 서버 변경을 수용하면 PR을 병합하고, 거부하면 `main` 상태를 승인 후 다시 적용합니다.

## 릴리스

장기 `release/*` 브랜치를 두지 않고 `vMAJOR.MINOR.PATCH` tag와 불변 아티팩트를 사용합니다. 여러 Automation 저장소 간 승격도 브랜치 병합이 아니라 승인된 릴리스 버전을 대상 저장소의 PR로 가져오는 방식으로 수행합니다.
