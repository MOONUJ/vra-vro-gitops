# VCF Automation GitOps Template

Automation UI에 직접 접근하지 않고 VMware Cloud Foundation Automation과 Orchestrator를 Git으로 관리하는 **인스턴스 저장소 템플릿**입니다.

이 템플릿 자체는 실제 Automation 인스턴스의 원하는 상태를 보관하지 않습니다. 템플릿으로 생성한 저장소 하나가 Automation 한 대를 관리하며, 생성된 저장소의 `main` 브랜치가 해당 인스턴스의 승인된 원하는 상태가 됩니다.

## 운영 모델

```mermaid
flowchart LR
    Template[GitOps Template<br/>구조 · 도구 · AI 지침] --> RepoA[Automation A 저장소]
    Template --> RepoB[Automation B 저장소]
    RepoA <--> AutomationA[VCF Automation A]
    RepoB <--> AutomationB[VCF Automation B]
```

- 이 저장소: 공통 구조, CLI, 문서, AGENTS, Skill, Loop 예시 관리
- 생성된 저장소: `instance.yaml`, 실제 콘텐츠, lifecycle 분류와 릴리스 관리
- 비밀값과 캐시: `secrets.json`, token, discovery cache와 Terraform state는 어느 브랜치에도 커밋하지 않음
- 여러 Automation: 환경 브랜치가 아니라 저장소를 추가하여 격리

Template Repository와 버전 정책은 [템플릿 운영 문서](docs/TEMPLATE.md), 브랜치와 실제 연동 검증은 [브랜치 전략](docs/BRANCHING.md)을 참고합니다.

공통 도구는 version pin `.vcf-gitops-version`과 `pyproject.toml`로 package화됩니다. wheel 설치 후 사람, CI와 AI Agent는 `vcf-gitops context|infrastructure|content|release|schema|identity|template-update|observe-loop` entry point를 함께 사용합니다. 기존 Python script 경로는 0.x 호환 경로입니다.

## 관리 범위

- Day-0 기반: Cloud Account, Cloud Zone, Network/Storage/Image Profile, Project
- Automation 콘텐츠: Blueprint, ABX, Catalog Source, Custom Form, Custom Resource, Resource Action, Policy, Subscription
- Orchestrator 콘텐츠: Workflow, Action, Configuration, Resource, Package
- GitOps 전달: import, status, pull, push, release, restore
- AI 운영 계층: `AGENTS.md`, Skills, 결정론적 Tools, 승인 기반 Loops

Day-0/1/2는 콘텐츠의 서비스 수명주기입니다. `pull`, `push`, `backup`, `restore`는 모든 단계를 지원하는 전달 기능입니다. 자세한 정의는 [수명주기 문서](docs/LIFECYCLE.md)를 참고합니다.

## 저장소 생성

GitHub에서 이 저장소를 Template Repository로 설정한 뒤 **Use this template**로 Automation별 저장소를 생성합니다. 생성된 저장소에서 다음을 실행합니다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r tooling/vcf/requirements.txt
.venv/bin/python tooling/template/bootstrap.py \
  --name automation-seoul-dev \
  --endpoint https://automation.example.com \
  --environment-tag seoul-dev \
  --package-name com.example.automation.seoul.dev
```

명령은 `instance.example.yaml`을 바탕으로 추적 대상 `instance.yaml`을 만들고, Git에서 제외되는 `secrets.json`을 권한 `0600`으로 준비합니다. `instance.yaml`에는 연결·범위·관리 정책만 두고 Day-0 원하는 상태는 `infrastructure/`에 리소스별로 기록합니다.

```bash
.venv/bin/python tooling/vcf/configure.py validate \
  --instance instance.yaml \
  --secrets secrets.json
git add instance.yaml
```

## 템플릿에서 실제 Automation 연동 시험

템플릿 기능 개발 중에는 `integration/*` 브랜치를 짧게 사용합니다. 실제 endpoint와 자격 증명은 커밋하지 않도록 무시되는 로컬 파일을 사용합니다.

```bash
git switch -c integration/lab-connection
cp instance.example.yaml instance.local.yaml
cp secrets.example.json secrets.local.json

.venv/bin/python tooling/vcf/configure.py validate \
  --instance instance.local.yaml \
  --secrets secrets.local.json
```

먼저 범위가 작은 read-only discovery로 인증과 권한을 확인합니다. 전역 옵션은 하위 명령 앞에 둡니다.

```bash
.venv/bin/python tooling/vcf/cli.py \
  --instance instance.local.yaml \
  --secrets secrets.local.json \
  discover --kind Project
```

전체 API 조회가 성공하면 결과를 Git에서 제외되는 경로에 저장하고, 채택할 리소스를 preflight합니다.

```bash
.venv/bin/python tooling/vcf/cli.py \
  --instance instance.local.yaml \
  --secrets secrets.local.json \
  discover --output .gitops/discovery.json

.venv/bin/python tooling/vcf/cli.py \
  --instance instance.local.yaml \
  --secrets secrets.local.json \
  --infrastructure-root .gitops/infrastructure-test \
  adopt --all --kind Project --kind CloudZone --dry-run
```

preflight에 충돌이 없으면 테스트 manifest를 생성하고 원격과 다시 비교합니다. `adopt`는 로컬 파일만 만들고 Automation을 수정하지 않습니다.

```bash
.venv/bin/python tooling/vcf/cli.py \
  --instance instance.local.yaml \
  --secrets secrets.local.json \
  --infrastructure-root .gitops/infrastructure-test \
  adopt --all --kind Project --kind CloudZone

.venv/bin/python tooling/vcf/cli.py \
  --infrastructure-root .gitops/infrastructure-test \
  validate

.venv/bin/python tooling/vcf/cli.py \
  --instance instance.local.yaml \
  --secrets secrets.local.json \
  --infrastructure-root .gitops/infrastructure-test \
  status --json
```

adopt 직후 모든 항목이 `IN_SYNC`인지, 실제 응답에서 Profile 관계 필드나 Project zone assignment가 누락되지 않았는지 확인합니다. 403, 일부 endpoint 실패, ID 누락 또는 경로 충돌은 빈 결과나 부분 성공으로 처리하지 않습니다.

마지막으로 템플릿 변경만 남았는지 확인합니다.

```bash
git status --short
```

템플릿 루트의 실제 `instance.yaml`, 실제 `infrastructure/` 결과, secret, `.gitops/` cache와 시험 릴리스는 변경 집합에 포함하지 않습니다. `main`에는 재사용 가능한 코드·구조·문서만 병합합니다. 구조가 안정화된 뒤에는 템플릿으로 만든 별도의 pilot 저장소에서 최종 통합 검증하는 방식이 가장 안전합니다.

## 생성된 인스턴스 저장소 사용

`context`는 저장소 모드뿐 아니라 baseline 추적, 설정, 작업 트리와 원격 변경 준비 상태를 확인합니다.

```bash
.venv/bin/python tooling/vcf/cli.py context --json
```

`apply`, `push`, `push-all`, 현재의 `backup`, `restore`는 공통 operation registry에서 원격 mutation으로 분류됩니다. 이 명령은 유효한 `instance.yaml`이 추적되고 원하는 상태가 커밋되어 추적 파일 변경이 없는 인스턴스 저장소에서만 실행됩니다. 템플릿과 모호한 모드에서는 API client를 사용하기 전에 거부됩니다.

### 기존 Automation 가져오기

```bash
git switch -c import/initial-baseline
.venv/bin/python tooling/vcf/cli.py discover
.venv/bin/python tooling/vcf/cli.py adopt \
  --resource CloudZone:<remote-id> \
  --resource Project:<remote-id>
.venv/bin/python tooling/vcf/cli.py validate
.venv/bin/python tooling/vcf/cli.py status
.venv/bin/python tooling/vcf/vcf_sync.py pull-all
git diff -- infrastructure content
```

인프라 manifest의 `metadata.remoteId`, 원하는 상태, 콘텐츠의 민감정보와 관리 범위를 검토한 후 PR로 `main`에 병합합니다.

Automation의 지원 대상 리소스를 모두 채택하려면 먼저 전체 preflight를 확인합니다.

```bash
.venv/bin/python tooling/vcf/cli.py adopt --all --dry-run
.venv/bin/python tooling/vcf/cli.py adopt --all
```

일부 종류만 일괄 채택하려면 `--kind Project --kind CloudZone`처럼 제한합니다. 인자 없는 `adopt`는 실행되지 않으며, `--all`은 발견된 모든 지원 리소스를 Git 관리 대상으로 삼겠다는 명시적 선택입니다. 권한·API·ID 오류나 경로 충돌이 있으면 manifest를 만들기 전에 전체 작업을 중단합니다.

### Day-0 기반 관리

```bash
.venv/bin/python tooling/vcf/cli.py validate
.venv/bin/python tooling/vcf/cli.py status --json
.venv/bin/python tooling/vcf/cli.py plan
```

`plan`은 원격을 다시 관찰하고 `.gitops/plans/<plan-hash>.json`에 불변 artifact를 만듭니다. 같은 manifest와 원격 관찰에 대한 유효한 plan은 재사용합니다. 생성·갱신 대상, before/after, manifest와 원격 관찰 hash, 만료 시각을 검토한 뒤에만 정확한 artifact와 hash를 승인합니다.

```bash
# 아래 명령은 원격을 변경합니다.
.venv/bin/python tooling/vcf/cli.py apply \
  --plan .gitops/plans/<plan-hash>.json \
  --approve-plan <plan-hash>
```

Apply는 추적된 `instance.yaml`이 있는 인스턴스 저장소에서만 실행되며, plan 생성 후 manifest나 원격 상태가 바뀌었거나 plan이 만료되면 거부됩니다. 성공한 작업도 원격을 다시 조회하여 원하는 상태와 일치해야 `VERIFIED`가 됩니다. 결과는 `.gitops/apply-results/`에 기록되고 같은 plan은 다시 실행할 수 없습니다.

신규 리소스 생성은 apply에 `--approve-create Kind:<manifest-name>`을 별도로 전달해야 합니다. 파일 삭제만으로 원격 삭제를 추론하지 않습니다. 삭제가 필요한 경우 `plan --delete Kind:<remote-id>`로 대상을 명시하고 apply에도 같은 `--approve-delete Kind:<remote-id>`를 별도로 전달해야 합니다.

`foundation/automation/terraform/`은 이전 또는 선택적 greenfield 호환 경로입니다. `management.infrastructure: native`인 저장소에서는 같은 리소스를 Terraform과 동시에 관리하지 않습니다.

### 콘텐츠 동기화

```bash
.venv/bin/python tooling/vcf/vcf_sync.py status
.venv/bin/python tooling/vcf/vcf_sync.py status --json
.venv/bin/python tooling/vcf/vcf_sync.py pull-preview
.venv/bin/python tooling/vcf/vcf_sync.py content-plan \
  --lifecycle day2 \
  --product automation \
  --resource automation:ResourceAction:resize
```

`status --json`은 Automation과 Orchestrator 결과를 하나의 결정론적 observation으로 출력합니다. 인증, 권한, API, 페이지네이션, 응답 또는 로컬 콘텐츠 해석이 하나라도 실패하면 빈 원격 상태로 계속하지 않고 `INCOMPLETE`와 non-zero exit code로 중단합니다.

`pull-preview`는 원격 콘텐츠를 `.gitops/pull-previews/<preview-hash>/content/`에 완전히 렌더링하고 원격 상태와 다시 비교합니다. `content/`는 변경하지 않습니다. 파일별 변경과 hash를 검토한 후 정확한 preview만 수용합니다.

vRO package는 이미 존재할 때만 GET export합니다. pull과 preview는 package를 생성하거나 membership을 갱신하지 않으며, package가 없으면 개별 콘텐츠만 preview하고 package export는 건너뜁니다.

```bash
.venv/bin/python tooling/vcf/vcf_sync.py accept-pull \
  --preview .gitops/pull-previews/<preview-hash> \
  --approve-preview <preview-hash>
```

Preview 생성 후 로컬 콘텐츠가 바뀌거나 preview가 변조되면 accept가 거부됩니다. 원격 부재만으로 로컬 파일을 삭제하지 않습니다. 기존 `pull`과 `pull-all`은 호환성을 위해 preview 생성 alias로 동작하며 더 이상 `content/`를 직접 변경하지 않습니다.

콘텐츠 원격 변경은 `content-plan`이 출력한 작업, 대상 instance, Git commit, local content hash, 원격 observation hash와 만료를 검토한 후 실행합니다.

```bash
# CREATE가 있으면 해당 approvalKey를 --approve-create로 모두 추가합니다.
.venv/bin/python tooling/vcf/vcf_sync.py content-apply \
  --plan .gitops/content-plans/<plan-hash>.json \
  --approve-plan <plan-hash>
```

`content-apply`는 plan 직후 Git이나 원격 상태가 변하면 거부되며, instance별 lock과 in-progress journal을 사용합니다. 각 작업은 원격 재조회에서 `IN_SYNC`가 확인되어야 `VERIFIED`가 됩니다. 기존 `push`와 `push-all`의 직접 mutation은 비활성화되었습니다.

### 릴리스와 복구

```bash
# 원격을 변경하지 않는 export
.venv/bin/python tooling/vcf/vcf_release.py export --version 1.0.0

# Git의 local content에서 불변 release build
.venv/bin/python tooling/vcf/vcf_release.py release-build --version 1.0.0

# artifact SHA-256과 manifest 검증
.venv/bin/python tooling/vcf/vcf_release.py verify --version 1.0.0

# 원격과 artifact를 다시 검증해 불변 restore plan 생성
.venv/bin/python tooling/vcf/vcf_release.py restore-plan --version 1.0.0

# plan hash와 출력된 모든 artifact approval을 검토한 뒤 실행
.venv/bin/python tooling/vcf/vcf_release.py restore-apply \
  --version 1.0.0 \
  --plan .gitops/restore-plans/<plan-hash>.json \
  --approve-plan <plan-hash> \
  --approve-artifact artifact:<path>:<sha256>
```

`export`는 서버의 vRO 객체 version이나 package membership을 변경하지 않습니다. 기존 `backup`은 read-only `export` alias입니다. `release-build`와 `export`는 기존 `releases/<version>`을 덮어쓰지 않으며 SemVer, source commit, target, tool version과 모든 artifact SHA-256을 manifest에 기록합니다.

Direct `restore`는 비활성화되었습니다. `restore-plan`은 현재 지원되는 remote-export release만 대상으로 하며 release digest, 정확히 하나인 target project, 대상 instance, 현재 원격 observation과 만료를 결합합니다. `restore-apply`는 모든 artifact digest에 대한 exact approval을 요구하고, 적용 후 구성요소와 vRO package를 다시 확인합니다.

`restore`, native `apply`, 콘텐츠 `content-apply`, `terraform apply`는 원격 환경을 변경하므로 대상과 plan을 검토하고 승인 후 실행합니다.

### Observe-only Loop

실제 인스턴스 저장소에서 Loop 예시를 복사해 `.example`을 제거하고 `instanceRef`와 `enabled: true`를 검토한 뒤 실행합니다.

```bash
vcf-gitops observe-loop --loop automation/loops/dev-day2-drift.yaml
```

현재 Loop는 원격 mutation을 하지 않습니다. instance 모드와 설정을 먼저 검증하고, instance별 lock 아래에서 observation을 생성해 `.gitops/loop-runs/`에 journal을 남깁니다. 동일 정상 상태는 조용히 유지하며 drift, 실패, 상태 변화와 반복 drift escalation만 알림 대상으로 표시합니다. 자세한 계약은 [Loop 문서](docs/LOOP.md)를 따릅니다.

## 주요 경로

```text
instance.example.yaml   템플릿용 인스턴스 정의 예시
infrastructure/         리소스별 Day-0 원하는 상태와 원격 ID
foundation/             이전/선택적 Day-0 Terraform
content/                Automation과 Orchestrator 콘텐츠
lifecycle/              Day-0/1/2 분류 manifest
tooling/vcf/            설정, API client, sync, release CLI
tooling/template/       인스턴스 저장소 초기화와 안전한 update wrapper
releases/               버전 릴리스 아티팩트
automation/loops/       향후 승인 기반 loop 정의
.agents/skills/         Codex 작업 절차
```

## AI 구조

- [AGENTS.md](AGENTS.md): 템플릿과 인스턴스 저장소의 전체 정책
- [.agents/skills/vcf-gitops-lifecycle/SKILL.md](.agents/skills/vcf-gitops-lifecycle/SKILL.md): 수명주기 작업 절차
- `tooling/vcf/`: AI와 사람이 함께 사용하는 결정론적 도구
- [automation/loops](automation/loops): observe, plan, approval, apply, verify 흐름

## 문서

- [템플릿 운영](docs/TEMPLATE.md)
- [저장소 구조](STRUCTURE.md)
- [인스턴스와 비밀값 설정](docs/CONFIGURATION.md)
- [Day-0/1/2 정의](docs/LIFECYCLE.md)
- [콘텐츠 Identity와 정규화](docs/CONTENT_IDENTITY.md)
- [Schema, Policy와 CI](docs/SCHEMA_POLICY.md)
- [브랜치 전략](docs/BRANCHING.md)
- [Loop 설계](docs/LOOP.md)
- [마이그레이션 상태](docs/MIGRATION.md)

## License

[MIT License](LICENSE)
