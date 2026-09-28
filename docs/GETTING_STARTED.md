# 처음 시작하기

이 문서는 Template Repository로 Automation 인스턴스 저장소를 만들고, 기존 원격 상태를 최초 Git baseline으로 확정하는 데까지 안내합니다. 현재 지원 모델은 개발 인스턴스에서 사람이 명령을 실행하고 exact plan을 직접 승인하는 로컬 수동 운영입니다.

## 완료 상태

이 가이드를 마치면 다음 상태가 되어야 합니다.

- `instance.yaml`, `infrastructure/`, `content/`가 검토된 Git baseline으로 커밋됨
- `secrets.json`과 `.gitops/`는 Git에서 제외됨
- `context`가 `repositoryMode: instance`, `configValid: true`를 반환함
- Day-0와 콘텐츠 status가 오류 없이 완료됨
- 기존 원격 리소스가 의도치 않게 변경되지 않음

## 1. 사전 준비

다음 값을 먼저 준비합니다.

| 항목 | 설명 |
| --- | --- |
| Python | 3.10 이상 |
| Automation endpoint | 예: `https://automation.example.com` |
| Organization | 기본값은 `default` |
| Project | 이 저장소가 관리할 실제 project 이름 |
| Environment tag | 인스턴스별 GitOps discovery 범위 |
| vRO package | 인스턴스별 고유 package 이름 |
| Refresh token | Automation API에 접근 가능한 사용자 token |
| Orchestrator 유형 | `embedded` 또는 `external` |

External Orchestrator는 Automation과 같은 identity provider의 OAuth bearer를 받아들이는 구성을 전제로 합니다. 별도 username/password와 Basic authentication은 지원하지 않습니다.

## 2. 저장소 생성과 도구 설치

GitHub에서 이 저장소의 **Use this template**를 선택해 Automation 하나를 위한 새 저장소를 만듭니다. 생성된 저장소를 clone한 뒤 다음을 실행합니다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r tooling/vcf/requirements.txt
```

0.x 가이드는 저장소에 포함된 Python script를 기준으로 합니다. Wheel을 별도로 설치한 환경에서만 `vcf-gitops` 통합 명령을 사용합니다.

## 3. 인스턴스 설정 생성

```bash
.venv/bin/python tooling/template/bootstrap.py \
  --name automation-seoul-dev \
  --endpoint https://automation.example.com \
  --organization default \
  --environment-tag seoul-dev \
  --package-name com.example.automation.seoul.dev
```

이 명령은 다음 파일을 준비합니다.

- `instance.yaml`: Git에 추적할 비밀 없는 연결과 관리 범위
- `secrets.json`: 권한 `0600`인 로컬 비밀값 파일

Bootstrap은 실제 project를 자동으로 알 수 없습니다. `instance.yaml`의 placeholder를 반드시 실제 값으로 바꿉니다.

```yaml
spec:
  gitops:
    tag: seoul-dev
    projects:
      - actual-project-name
```

### Embedded Orchestrator

Automation에 포함된 Orchestrator를 사용하면 기본 설정을 유지합니다.

```yaml
spec:
  orchestrator:
    deployment: embedded
    discovery:
      mode: tag
      requireNonEmpty: false
```

### External Orchestrator

외부 Orchestrator를 직접 관리한다면 endpoint와 discovery 범위를 명시합니다.

```yaml
spec:
  orchestrator:
    deployment: external
    endpoint: https://orchestrator.example.com
    verifySsl: true
    discovery:
      mode: package
      requireNonEmpty: true
    package:
      name: com.example.automation.seoul.dev
      localPath: content/orchestrator/packages/com.example.automation.seoul.dev.package
```

`package` discovery는 `GET /vco/api/packages/{packageName}`의 membership을 관리 범위로 사용합니다. `requireNonEmpty: true`이면 잘못된 endpoint, 권한 또는 package로 인해 0건이 반환될 때 정상 빈 상태로 받아들이지 않습니다.

## 4. 비밀값과 로컬 설정 검증

`secrets.json`의 placeholder를 실제 refresh token으로 바꿉니다.

```json
{
  "automation": {
    "refresh_token": "REPLACE_WITH_LOCAL_SECRET"
  }
}
```

이 token은 Automation OAuth endpoint에서 bearer token으로 교환되며 Automation API와 연결된 Orchestrator API에 함께 사용됩니다. `secrets.json`을 Git에 추가하지 않습니다.

```bash
.venv/bin/python tooling/vcf/configure.py validate \
  --instance instance.yaml \
  --secrets secrets.json

git status --short
```

출력의 Automation URL, Orchestrator URL과 discovery 방식이 의도한 값인지 확인합니다. `git status`에 `secrets.json`이 나타나면 진행하지 말고 `.gitignore`를 확인합니다.

설정을 첫 commit으로 확정합니다.

```bash
git switch -c import/initial-baseline
git add instance.yaml
git commit -m "chore: initialize automation instance"
.venv/bin/python tooling/vcf/cli.py context --json
```

최소한 다음 값이 필요합니다.

```json
{
  "repositoryMode": "instance",
  "baselineTracked": true,
  "configValid": true,
  "worktreeClean": true,
  "mutationReady": true
}
```

`mutationReady`는 저장소 경계가 준비됐다는 뜻일 뿐, 기존 원격 상태의 baseline 검토가 끝났다는 뜻은 아닙니다. 다음 import가 완료되기 전에는 apply하지 않습니다.

## 5. 기존 Automation baseline 가져오기

### 5.1 Read-only 연결 확인

먼저 범위를 작게 잡아 인증, 권한과 endpoint를 확인합니다.

```bash
.venv/bin/python tooling/vcf/cli.py discover --kind Project
.venv/bin/python tooling/vcf/vcf_sync.py status --json
```

403, 일부 API 실패, 잘못된 응답, ID 누락 또는 Orchestrator discovery 0건 guard가 발생하면 결과를 baseline으로 사용하지 않습니다.

### 5.2 Day-0 리소스 채택

관리하려는 종류만 dry-run으로 확인합니다.

```bash
.venv/bin/python tooling/vcf/cli.py adopt \
  --all \
  --kind Project \
  --kind CloudZone \
  --dry-run
```

충돌과 예상 개수를 확인한 뒤 같은 선택으로 manifest를 만듭니다. `adopt`는 로컬 파일만 생성하며 원격을 변경하지 않습니다.

```bash
.venv/bin/python tooling/vcf/cli.py adopt \
  --all \
  --kind Project \
  --kind CloudZone

.venv/bin/python tooling/vcf/cli.py validate
.venv/bin/python tooling/vcf/cli.py status --json
```

모든 채택 대상이 `IN_SYNC`인지 확인합니다. 전체 지원 리소스를 채택하려는 경우에만 종류 제한 없는 `adopt --all --dry-run`과 `adopt --all`을 사용합니다.

### 5.3 콘텐츠 preview와 수용

`pull-preview`는 원격 콘텐츠를 `.gitops/pull-previews/<preview-hash>/content/`에 렌더링할 뿐 `content/`를 변경하지 않습니다.

```bash
.venv/bin/python tooling/vcf/vcf_sync.py pull-preview
```

출력된 preview 경로의 파일, 민감정보, ID와 변경 범위를 검토합니다. 정확한 preview만 hash로 승인합니다.

```bash
.venv/bin/python tooling/vcf/vcf_sync.py accept-pull \
  --preview .gitops/pull-previews/<preview-hash> \
  --approve-preview <preview-hash>

.venv/bin/python tooling/vcf/content_identity.py validate
.venv/bin/python tooling/vcf/schema_validation.py
git diff -- infrastructure content lifecycle
```

기존 `pull`과 `pull-all`도 preview 생성 alias이며 `accept-pull` 없이 `content/`를 변경하지 않습니다.

### 5.4 Baseline 확정

리소스 범위와 콘텐츠를 검토한 뒤 PR로 `main`에 병합합니다.

```bash
git add instance.yaml infrastructure content lifecycle
git commit -m "chore: import initial automation baseline"
git status --short
```

Secret, `.gitops/`, Terraform state와 생성 입력이 commit에 포함되지 않았는지 반드시 확인합니다.

## 6. 첫 변경 시험

처음에는 비활성 Subscription의 description이나 테스트 Workflow처럼 영향이 작고 되돌릴 수 있는 대상 하나를 선택합니다. 여러 제품과 lifecycle을 섞지 않습니다.

변경 파일을 검토·커밋해 작업 트리를 정리한 뒤 plan을 생성합니다. Plan 이후 commit이 달라지면 기존 plan은 무효가 됩니다.

```bash
.venv/bin/python tooling/vcf/vcf_sync.py status --json
.venv/bin/python tooling/vcf/vcf_sync.py content-plan \
  --lifecycle day2 \
  --product automation \
  --resource automation:Subscription:<identity>
```

Plan의 target, Git commit, 작업, local content, 원격 observation hash와 만료를 검토합니다. 승인한 hash만 apply에 전달합니다.

```bash
.venv/bin/python tooling/vcf/vcf_sync.py content-apply \
  --plan .gitops/content-plans/<plan-hash>.json \
  --approve-plan <plan-hash>
```

CREATE 작업이 있으면 출력된 모든 `approvalKey`를 `--approve-create`로 별도 승인해야 합니다. Apply 후 결과가 `VERIFIED`이고 새 status가 `IN_SYNC`인지 확인합니다.

자세한 반복 운영과 복구 절차는 [로컬 수동 운영](OPERATIONS.md)을 참고합니다.

## 중단해야 하는 경우

- 인증, 권한, API, 페이지네이션 또는 응답 해석 실패
- External Orchestrator의 package/tag discovery가 예상과 다름
- Preview에 secret 또는 범위 밖 콘텐츠가 포함됨
- Adopt 직후 `IN_SYNC`가 아님
- Plan 이후 Git commit, local content 또는 원격 상태가 변경됨
- 적용 후 `VERIFIED`가 아니거나 기능 검증이 실패함

오류를 빈 상태로 간주하거나 불완전한 결과를 commit·apply하지 않습니다.
