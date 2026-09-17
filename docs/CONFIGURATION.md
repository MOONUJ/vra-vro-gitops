# 인스턴스와 비밀값 설정

## 파일 경계

| 파일 | Git | 내용 |
| --- | --- | --- |
| `instance.example.yaml` | 추적 | 템플릿의 placeholder 인스턴스 정의 |
| `instance.yaml` | 생성된 저장소에서 추적 | Automation endpoint, 조직, GitOps 범위와 관리 정책 |
| `infrastructure/**/*.yaml` | 생성된 저장소에서 추적 | Day-0 리소스별 원하는 상태와 `metadata.remoteId` |
| `secrets.example.json` | 추적 | 필요한 비밀 필드의 placeholder |
| `secrets.json` | 제외 | Automation refresh token |
| `instance.local.yaml` | 템플릿에서 제외 | 실제 연동 시험용 인스턴스 정의 |
| `secrets.local.json` | 제외 | 실제 연동 시험용 비밀값 |

이 구분을 통해 Cloud Zone, Project, Profile 같은 원하는 상태는 리소스별 Git 이력에 남기고 자격 증명만 제외합니다.

## 준비와 검증

생성된 인스턴스 저장소에서는 bootstrap 도구로 `instance.yaml`과 `secrets.json`을 준비합니다.

```bash
python3 tooling/template/bootstrap.py \
  --name automation-dev \
  --endpoint https://automation.example.com
.venv/bin/python tooling/vcf/configure.py validate \
  --instance instance.yaml \
  --secrets secrets.json
```

검증은 원격 API를 호출하지 않습니다.

인프라 manifest도 로컬에서 별도로 검증합니다.

```bash
.venv/bin/python tooling/vcf/cli.py validate
```

템플릿 저장소에서 실제 연동을 시험할 때는 `instance.local.yaml`과 `secrets.local.json`을 사용하고 `--instance`, `--secrets` 옵션으로 경로를 전달합니다.

## 기존 Automation 채택

```bash
.venv/bin/python tooling/vcf/cli.py discover
.venv/bin/python tooling/vcf/cli.py adopt \
  --resource CloudZone:<remote-id> \
  --resource Project:<remote-id>
.venv/bin/python tooling/vcf/cli.py validate
.venv/bin/python tooling/vcf/cli.py status
```

`adopt`는 `infrastructure/`에 manifest를 만들며 기존 파일을 기본적으로 덮어쓰지 않습니다. `remoteId`가 없는 manifest는 신규 생성 후보지만 현재 read-only 단계에서는 원격에 자동 생성하지 않습니다.

전체 리소스를 채택할 때는 명시적인 `--all`을 사용합니다.

```bash
# 파일 변경 없이 전체 preflight
.venv/bin/python tooling/vcf/cli.py adopt --all --dry-run

# Project와 Cloud Zone만 일괄 채택
.venv/bin/python tooling/vcf/cli.py adopt --all \
  --kind Project \
  --kind CloudZone
```

`--all`은 discovery된 모든 지원 리소스를 Git 소유 대상으로 등록합니다. 동일 `remoteId`는 건너뛰고, 같은 파일 경로가 다른 원격 ID를 가리키는 충돌이나 불완전한 discovery가 있으면 어떤 파일도 생성하지 않습니다. 전체 adopt에서는 `--force`를 허용하지 않습니다.

## Native plan과 apply

`management.infrastructure: native`인 인스턴스 저장소에서는 먼저 불변 plan을 생성합니다.

```bash
.venv/bin/python tooling/vcf/cli.py status --json
.venv/bin/python tooling/vcf/cli.py plan
```

Plan artifact의 작업, before/after, 대상 인스턴스, 만료 시각과 hash를 검토한 뒤 정확한 hash를 승인해 적용합니다.

```bash
.venv/bin/python tooling/vcf/cli.py apply \
  --plan .gitops/plans/<plan-hash>.json \
  --approve-plan <plan-hash>
```

`apply`는 원격 변경이며 추적된 `instance.yaml`이 있는 인스턴스 모드에서만 실행됩니다. 삭제는 `plan --delete Kind:<remote-id>`와 `apply --approve-delete Kind:<remote-id>` 양쪽에 정확한 대상을 명시해야 합니다. plan과 실행 결과는 `.gitops/` 아래의 로컬 증거이며 Git에 커밋하지 않습니다.

초기 native mutation 지원 범위는 다음과 같습니다.

| Kind | CREATE | UPDATE | DELETE |
| --- | :---: | :---: | :---: |
| `Project` | 지원 | 지원 | 명시적 승인 |
| `NetworkProfile` | 지원 | 지원 | 명시적 승인 |
| `StorageProfile` | 미지원 | 지원 | 명시적 승인 |
| `ImageProfile` | 지원 | 지원 | 명시적 승인 |
| `CloudAccount`, `CloudZone` | 관찰 전용 | 관찰 전용 | 미지원 |

공식 mutation payload가 표현하지 못하는 필드 변경이나 기존 필드의 암묵적 제거는 plan 단계에서 거부합니다. Profile CREATE에는 `regionId`가 필요하며, 기존 Profile UPDATE는 원격 region 링크에서 ID를 안전하게 보완할 수 있습니다.

## Terraform 호환 경로

`foundation/automation/terraform/`은 이전 또는 선택적 greenfield 흐름을 위해 남아 있습니다. `management.infrastructure: native`인 저장소에서는 Terraform 입력을 생성하지 않으며 동일 리소스를 native 도구와 Terraform이 동시에 소유하면 안 됩니다.

## 자동화 실행 환경

단일 `config.json` 형식과 `gitops/` 호환 경로는 지원하지 않습니다. CI/CD와 장기 실행 loop에서는 `secrets.json`을 저장소에 배포하기보다 secret manager에서 실행 시점에 주입하는 방식을 권장합니다.
