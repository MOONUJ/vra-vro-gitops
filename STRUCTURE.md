# 저장소 구조

## 구조 원칙

- 이 저장소의 `main`은 Automation별 저장소를 생성하는 공통 템플릿이다.
- 템플릿으로 생성된 저장소 하나는 Automation 인스턴스 하나만 관리한다.
- 생성된 저장소의 `main`은 해당 Automation의 승인된 원하는 상태다.
- 비밀 없는 인스턴스 정의와 콘텐츠는 Git에 추적하고 자격 증명만 제외한다.
- Day-0/1/2는 서비스 수명주기이며 import/sync/release는 별도의 전달 기능이다.
- Workflow나 Action처럼 여러 Day에서 쓰이는 콘텐츠를 복제하지 않고 `lifecycle/*.yaml`에서 용도를 분류한다.

## 현재 구조

```text
vcf-automation-gitops-template/
├── .template-version                    # 템플릿 기준 버전
├── instance.example.yaml                 # 인스턴스 정의 예시
├── instance.yaml                         # 생성된 저장소에서 추적, 템플릿에는 없음
├── secrets.example.json                  # 비밀값 형식 예시
├── secrets.json                          # 실제 비밀값, Git 제외
├── foundation/
│   └── automation/terraform/             # Day-0 기반 구성
├── content/
│   ├── automation/                       # Blueprint, ABX, 정책 등
│   └── orchestrator/                     # Workflow, Action, Package 등
├── lifecycle/
│   ├── day0.yaml
│   ├── day1.yaml
│   └── day2.yaml
├── tooling/vcf/
│   ├── config_loader.py
│   ├── configure.py
│   ├── vra_client.py
│   ├── vro_client.py
│   ├── vcf_sync.py
│   └── vcf_release.py
├── tooling/template/bootstrap.py         # instance.yaml 초기화
├── releases/                             # 불변 릴리스 아티팩트
├── automation/loops/                     # 승인 기반 loop 정의
├── .agents/skills/                       # 저장소 전용 Codex 스킬
├── tests/
└── docs/
```

## 제품별 콘텐츠

### Automation

- `content/automation/blueprints/{name}/blueprint.json|yaml`
- `content/automation/abx/{name}/init.json|source.py|source.js`
- `content/automation/custom_forms/`
- `content/automation/custom_resources/`
- `content/automation/resource_actions/`
- `content/automation/catalog_sources/`
- `content/automation/policies/`
- `content/automation/subscriptions/`

### Orchestrator

- `content/orchestrator/workflows/{category}/{name}/`
- `content/orchestrator/actions/{module}/{name}/`
- `content/orchestrator/configurations/`
- `content/orchestrator/resources/`
- `content/orchestrator/packages/`

서버의 카테고리 경로를 보존하고 ID·timestamp 같은 휘발 필드는 비교 전에 정규화합니다.

## 이전 경로 매핑

| 이전 경로 | 새 경로 | 전환 결과 |
| --- | --- | --- |
| `vra/` | `foundation/automation/terraform/` | 템플릿 소스 이동 후 이전 로컬 디렉터리 제거 완료 |
| `auto/` | `content/automation/` | sync 도구가 새 경로 사용 |
| `vro/` | `content/orchestrator/` | sync와 package 경로 갱신 |
| `gitops/artifacts/` | `releases/` | release 도구 기본 출력 변경 |

이전 `gitops/` 호환 계층과 단일 `config.json` 형식은 지원하지 않습니다. 생성된 저장소는 `instance.yaml`과 `secrets.json`을 사용합니다. 템플릿에서 실제 연동을 시험할 때는 Git에서 제외되는 `instance.local.yaml`과 `secrets.local.json`을 명령 옵션으로 전달합니다.
