# 인스턴스와 비밀값 설정

## 파일 경계

| 파일 | Git | 내용 |
| --- | --- | --- |
| `instance.example.yaml` | 추적 | 템플릿의 placeholder 인스턴스 정의 |
| `instance.yaml` | 생성된 저장소에서 추적 | Automation endpoint, 조직, GitOps 범위와 관리 정책 |
| `infrastructure/**/*.yaml` | 생성된 저장소에서 추적 | Day-0 리소스별 원하는 상태와 `metadata.remoteId` |
| `secrets.example.json` | 추적 | 필요한 비밀 필드의 placeholder |
| `secrets.json` | 제외 | Automation과 연결된 Orchestrator에 함께 사용하는 refresh token |
| `instance.local.yaml` | 템플릿에서 제외 | 실제 연동 시험용 인스턴스 정의 |
| `secrets.local.json` | 제외 | 실제 연동 시험용 비밀값 |

이 구분을 통해 Cloud Zone, Project, Profile 같은 원하는 상태는 리소스별 Git 이력에 남기고 자격 증명만 제외합니다.

## 준비와 검증

생성된 인스턴스 저장소에서는 bootstrap 도구로 `instance.yaml`과 `secrets.json`을 준비합니다.

```bash
python3 tooling/template/bootstrap.py \
  --name automation-dev \
  --endpoint https://automation.example.com \
  --package-name com.example.automation.dev
.venv/bin/python tooling/vcf/configure.py validate \
  --instance instance.yaml \
  --secrets secrets.json
```

검증은 원격 API를 호출하지 않습니다.
실제 `instance.yaml`에서 템플릿 placeholder인 `com.example.vcf` package 이름과 경로는 거부됩니다. vRO package는 인스턴스에 맞는 고유 이름을 bootstrap 시 명시합니다.

## Embedded와 external Orchestrator

Embedded Orchestrator는 Automation endpoint의 `/vco/api`를 사용하며 기본 설정은 다음과 같습니다.

```yaml
spec:
  orchestrator:
    deployment: embedded
    discovery:
      mode: tag
      requireNonEmpty: false
```

Automation에 외부 Orchestrator integration이 연결되어 있어도 GitOps 도구가 Automation endpoint의 embedded `/vco`를 조회해서는 외부 서버의 Workflow와 Action 원본을 얻을 수 없습니다. 외부 서버를 직접 지정합니다.

```yaml
spec:
  orchestrator:
    deployment: external
    endpoint: https://vro.example.com
    verifySsl: true
    discovery:
      mode: package
      requireNonEmpty: true
    package:
      name: com.example.automation.dev
      localPath: content/orchestrator/packages/com.example.automation.dev.package
```

이 저장소가 관리하는 external Orchestrator는 Automation integration과 같은 identity provider에 연결된 구성을 전제로 합니다. `secrets.json`의 Automation refresh token을 Automation OAuth endpoint에서 bearer token으로 교환한 뒤 Automation API와 외부 vRO `/vco/api` 양쪽에 사용합니다. 별도 vRO username/password와 Basic authentication은 지원하지 않습니다. 현재 로컬 수동 운영에서는 이 credential 하나를 사용하며, 역할별 credential 분리는 향후 CI 자동 적용 범위에서 다룹니다.

외부 vRO의 `GET /vco/api/server/authentication`은 연결 진단에 사용할 수 있습니다. 응답이 공통 OAuth/VIDM 구성이 아니라면 이 템플릿의 지원 경계 밖으로 보고 중단합니다.

External에서는 `discovery.mode: package`를 권장합니다. `GET /vco/api/packages/{packageName}`의 membership을 Workflow, Action, Configuration과 Resource의 관리 범위로 사용하므로 Automation integration에 노출된 항목이나 이름 검색과 혼동하지 않습니다. `tag`도 호환 discovery 방식으로 지원합니다.

`requireNonEmpty: true`는 external baseline을 가져올 때 권장합니다. 선택한 package 또는 tag discovery가 4종 모두 0건이면 정상 빈 상태로 기록하지 않고 `INCOMPLETE`로 중단하므로 잘못된 endpoint, 권한 또는 범위를 조기에 발견할 수 있습니다. Package export도 같은 `package.name`을 사용합니다.

저장소 실행 준비 상태는 다음 명령으로 확인합니다.

```bash
.venv/bin/python tooling/vcf/cli.py context --json
```

`repositoryMode`, `baselineTracked`, `configValid`, `worktreeClean`, `mutationReady`를 각각 출력합니다. 원격 mutation은 인스턴스 모드, 유효한 설정과 커밋된 clean working tree를 모두 요구합니다. 무시되는 `secrets.json`과 `.gitops/` 결과는 clean working tree 판정에서 제외됩니다.

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

`apply`는 원격 변경이며 추적된 `instance.yaml`이 있는 인스턴스 모드에서만 실행됩니다. CREATE는 `apply --approve-create Kind:<manifest-name>`으로 정확한 대상을 별도 승인해야 합니다. 삭제는 `plan --delete Kind:<remote-id>`와 `apply --approve-delete Kind:<remote-id>` 양쪽에 정확한 대상을 명시해야 합니다. plan과 실행 결과는 `.gitops/` 아래의 로컬 증거이며 Git에 커밋하지 않습니다.

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
