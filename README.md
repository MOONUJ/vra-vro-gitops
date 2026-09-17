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
- 비밀값과 상태: `secrets.json`, token, Terraform state는 어느 브랜치에도 커밋하지 않음
- 여러 Automation: 환경 브랜치가 아니라 저장소를 추가하여 격리

Template Repository와 버전 정책은 [템플릿 운영 문서](docs/TEMPLATE.md), 브랜치와 실제 연동 검증은 [브랜치 전략](docs/BRANCHING.md)을 참고합니다.

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
  --environment-tag seoul-dev
```

명령은 `instance.example.yaml`을 바탕으로 추적 대상 `instance.yaml`을 만들고, Git에서 제외되는 `secrets.json`을 준비합니다. `instance.yaml`의 인프라 항목과 `secrets.json`의 자격 증명을 채운 뒤 검증합니다.

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

.venv/bin/python tooling/vcf/vcf_sync.py status \
  --instance instance.local.yaml \
  --secrets secrets.local.json
```

`main`에는 실제 인스턴스 설정, import 결과, Terraform state 또는 시험용 릴리스가 아니라 재사용 가능한 코드·구조·문서만 병합합니다. 구조가 안정화된 뒤에는 템플릿으로 만든 별도의 pilot 저장소에서 최종 통합 검증하는 방식이 가장 안전합니다.

## 생성된 인스턴스 저장소 사용

### 기존 Automation 가져오기

```bash
git switch -c import/initial-baseline
.venv/bin/python tooling/vcf/vcf_sync.py pull-all
git diff -- content
```

가져온 파일의 비밀값, 서버 종속 ID와 관리 범위를 검토한 후 PR로 `main`에 병합합니다.

### Day-0 기반 구성

```bash
.venv/bin/python tooling/vcf/configure.py terraform
terraform -chdir=foundation/automation/terraform init
terraform -chdir=foundation/automation/terraform plan
# 검토와 승인 후에만 실행
terraform -chdir=foundation/automation/terraform apply
```

기존 Automation을 채택할 때는 remote backend와 import 계획을 먼저 준비해야 합니다. state 연결 없이 apply하면 기존 리소스를 신규 생성 대상으로 판단할 수 있습니다.

### 콘텐츠 동기화

```bash
.venv/bin/python tooling/vcf/vcf_sync.py status
.venv/bin/python tooling/vcf/vcf_sync.py pull
.venv/bin/python tooling/vcf/vcf_sync.py push --dry-run
# 검토와 승인 후에만 실행
.venv/bin/python tooling/vcf/vcf_sync.py push
```

### 릴리스와 복구

```bash
.venv/bin/python tooling/vcf/vcf_release.py backup --version 1.0.0
.venv/bin/python tooling/vcf/vcf_release.py restore --version 1.0.0
```

`restore`, `push`, `terraform apply`는 원격 환경을 변경하므로 대상과 계획을 검토하고 승인 후 실행합니다.

## 주요 경로

```text
instance.example.yaml   템플릿용 인스턴스 정의 예시
foundation/             Day-0 Terraform
content/                Automation과 Orchestrator 콘텐츠
lifecycle/              Day-0/1/2 분류 manifest
tooling/vcf/            설정, API client, sync, release CLI
tooling/template/       인스턴스 저장소 초기화 도구
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
- [브랜치 전략](docs/BRANCHING.md)
- [Loop 설계](docs/LOOP.md)
- [마이그레이션 상태](docs/MIGRATION.md)

## License

[MIT License](LICENSE)
