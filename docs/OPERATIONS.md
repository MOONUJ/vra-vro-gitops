# 로컬 수동 운영

이 문서는 최초 baseline이 검토·커밋된 인스턴스 저장소의 반복 운영 절차입니다. 최초 설정과 import는 [처음 시작하기](GETTING_STARTED.md)를 먼저 완료합니다.

## 운영 원칙

- 작업 전 `context`와 현재 branch를 확인합니다.
- 원격 상태를 Git에 수용하는 작업과 Git 상태를 원격에 적용하는 작업을 분리합니다.
- 모든 원격 변경은 불변 plan과 exact hash를 검토한 뒤 실행합니다.
- 한 번에 하나의 lifecycle, product와 작은 변경 집합을 선택합니다.
- 원격 부재만으로 삭제하지 않고 생성과 삭제는 별도 승인합니다.
- 인증·권한·스키마·정책 또는 수렴 실패가 발생하면 중단합니다.

```bash
.venv/bin/python tooling/vcf/cli.py context --json
git status --short
```

원격 변경 전에는 `repositoryMode: instance`, `configValid: true`, `worktreeClean: true`, `mutationReady: true`여야 합니다.

## Drift 판단

| 상황 | 선택할 흐름 |
| --- | --- |
| UI/API의 원격 변경을 Git이 받아들임 | `pull-preview → accept-pull → PR` |
| 원격 변경을 거부하고 Git 상태로 되돌림 | `content-plan → content-apply → verify` |
| Day-0 manifest를 원격에 반영 | `plan → apply → verify` |
| 원격 상태를 증거로 보관 | `release export` |
| 검증된 원격 export로 복구 | `restore-plan → restore-apply` |

## 콘텐츠 관찰

```bash
.venv/bin/python tooling/vcf/vcf_sync.py status --json
```

Automation과 Orchestrator 조회가 모두 완료돼야 observation의 `metadata.complete`가 `true`가 됩니다. 일부 실패를 빈 원격 상태로 처리하지 않습니다.

## 원격 변경을 Git에 수용

```bash
git switch -c drift/YYYY-MM-DD
.venv/bin/python tooling/vcf/vcf_sync.py pull-preview
```

Preview의 파일과 hash를 검토한 뒤 정확한 artifact만 수용합니다.

```bash
.venv/bin/python tooling/vcf/vcf_sync.py accept-pull \
  --preview .gitops/pull-previews/<preview-hash> \
  --approve-preview <preview-hash>

.venv/bin/python tooling/vcf/content_identity.py validate
.venv/bin/python tooling/vcf/schema_validation.py
git diff -- content lifecycle
```

Preview 생성 후 local content가 바뀌었거나 preview가 변조되면 accept가 거부됩니다. 원격에 없는 파일을 자동 삭제하지 않습니다. 검토 후 commit과 PR로 `main`에 병합합니다.

## Git 콘텐츠를 원격에 적용

콘텐츠를 수정하고 로컬 검증과 commit을 마친 뒤 정확한 대상만 plan에 넣습니다. `content-apply`는 추적 파일 변경이 없는 작업 트리만 허용하며 plan의 source commit과 현재 commit이 같아야 합니다.

```bash
.venv/bin/python tooling/vcf/vcf_sync.py status --json
.venv/bin/python tooling/vcf/vcf_sync.py content-plan \
  --lifecycle day2 \
  --product automation \
  --resource automation:ResourceAction:resize
```

Plan artifact에서 다음을 확인합니다.

- 대상 instance와 endpoint
- source Git commit
- lifecycle과 product
- 정확한 operation과 `approvalKey`
- local content와 원격 observation hash
- policy hash와 만료 시각

```bash
.venv/bin/python tooling/vcf/vcf_sync.py content-apply \
  --plan .gitops/content-plans/<plan-hash>.json \
  --approve-plan <plan-hash>
```

CREATE가 포함되면 각 `approvalKey`를 다음처럼 모두 추가합니다.

```text
--approve-create automation:Subscription:<identity>
```

Apply는 같은 `secrets.json` credential을 사용하고 instance별 lock 아래에서 실행됩니다. 각 작업은 원격 재조회에서 `IN_SYNC`가 되어야 `VERIFIED`로 기록됩니다. 기존 `push`와 `push-all` direct mutation은 비활성화되어 있습니다.

## Day-0 인프라 변경

Manifest 변경을 검토·커밋하고 작업 트리를 정리한 뒤 plan을 생성합니다.

```bash
.venv/bin/python tooling/vcf/cli.py validate
.venv/bin/python tooling/vcf/cli.py status --json
.venv/bin/python tooling/vcf/cli.py plan
```

Plan의 CREATE, UPDATE와 DELETE 목록을 검토합니다.

```bash
.venv/bin/python tooling/vcf/cli.py apply \
  --plan .gitops/plans/<plan-hash>.json \
  --approve-plan <plan-hash>
```

CREATE에는 `--approve-create Kind:<manifest-name>`, DELETE에는 plan과 동일한 `--approve-delete Kind:<remote-id>`가 추가로 필요합니다. Manifest가 Git에서 사라졌다는 이유만으로 원격 삭제를 만들지 않습니다.

`management.infrastructure: native`에서는 동일 리소스를 `foundation/automation/terraform/`과 동시에 관리하지 않습니다.

## 릴리스와 복구

원격을 변경하지 않는 export:

```bash
.venv/bin/python tooling/vcf/vcf_release.py export --version 1.0.0
```

Git의 local content에서 불변 release 생성과 검증:

```bash
.venv/bin/python tooling/vcf/vcf_release.py release-build --version 1.0.0
.venv/bin/python tooling/vcf/vcf_release.py verify --version 1.0.0
```

검증된 remote-export release 복구:

```bash
.venv/bin/python tooling/vcf/vcf_release.py restore-plan --version 1.0.0
.venv/bin/python tooling/vcf/vcf_release.py restore-apply \
  --version 1.0.0 \
  --plan .gitops/restore-plans/<plan-hash>.json \
  --approve-plan <plan-hash> \
  --approve-artifact artifact:<path>:<sha256>
```

출력된 모든 artifact digest를 각각 승인해야 합니다. Direct `restore`는 비활성화되어 있고, 현재 restore는 `remote-export` release만 지원합니다.

## Observe-only Loop

Loop는 원격을 변경하지 않습니다. 실제 인스턴스 저장소에서 예시를 복사하고 `instanceRef`, `repositoryMode: instance`, `enabled: true`를 검토한 뒤 실행합니다.

```bash
.venv/bin/python tooling/vcf/observe_loop.py \
  --loop automation/loops/dev-day2-drift.yaml
```

동일 정상 상태는 조용히 유지하고 drift, 실패, 상태 변화와 반복 drift만 journal에 남깁니다. 자세한 계약은 [Loop 설계](LOOP.md)를 따릅니다.

## External Orchestrator 운영

- Automation refresh token 하나를 Automation OAuth endpoint에서 bearer로 교환해 사용합니다.
- External endpoint의 `/vco/api`를 직접 조회합니다.
- Package discovery는 기존 package membership만 읽으며 pull 과정에서 package를 생성하거나 membership을 변경하지 않습니다.
- `requireNonEmpty: true`에서 네 종류의 discovery가 모두 0건이면 `INCOMPLETE`로 중단합니다.
- 공통 OAuth/VIDM 구성이 아니면 현재 지원 범위 밖입니다.

## 실패와 재시도

Plan이나 apply가 실패하면 기존 artifact를 수정하지 않습니다.

1. 인증·권한·설정·원격 변경 여부를 확인합니다.
2. `status --json`으로 완전한 새 observation을 만듭니다.
3. 로컬 상태와 정책을 다시 검증합니다.
4. 만료되거나 무효화된 plan 대신 새 plan을 생성합니다.
5. 새 hash를 다시 검토하고 승인합니다.

실패한 결과와 in-progress journal을 지워 재사용하거나, 원격 상태를 확인하지 않고 같은 mutation을 반복하지 않습니다.

## 현재 운영 한계

- Production 확대는 별도 검증과 승인 대상입니다.
- CI 자동 apply와 역할별 credential 분리는 아직 도입하지 않았습니다.
- 콘텐츠 원격 삭제는 지원하지 않습니다.
- External Orchestrator 실제 환경은 endpoint, OAuth와 package 권한을 별도로 통합 검증해야 합니다.
- Release restore는 지원되는 `remote-export` 형식에 한정됩니다.
