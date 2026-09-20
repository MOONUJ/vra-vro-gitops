# Day-0/1/2 서비스 수명주기

Day는 CLI 명령의 종류가 아니라 Automation이 제공하는 서비스와 리소스가 사용되는 시점을 나타냅니다.

| 단계 | 정의 | 대표 관리 대상 |
| --- | --- | --- |
| Day-0 | Automation 온보딩과 서비스 제공 기반 준비 | import baseline, Cloud Account, Zone, Profile, Project, vRO bootstrap |
| Day-1 | 새로운 서비스와 리소스 프로비저닝 | Blueprint, Catalog, Form, Custom Resource, ABX, provisioning Workflow |
| Day-2 | 생성된 리소스 운영과 변경 | Resource Action, resize, snapshot, retire, 운영 Workflow, Policy, Subscription |

## Day-0

- 기존 Automation을 가져와 Git baseline을 만든다.
- 신규 Automation의 연결 정보와 관리 범위를 등록한다.
- `infrastructure/` manifest로 Cloud Account, Zone, Profile, Project의 원하는 상태를 관리한다.
- 기존 리소스는 discovery 후 선택적으로 adopt하고 `metadata.remoteId`로 원격 객체와 결합한다.
- vRO package와 공통 Configuration을 bootstrap한다.

## Day-1

- Blueprint와 Catalog Item을 개발하고 게시한다.
- Custom Form, Custom Resource와 ABX를 개발한다.
- 신규 리소스 생성을 위한 Workflow와 Action을 관리한다.
- 프로비저닝 이벤트를 처리하는 Subscription을 관리한다.

## Day-2

- 기존 리소스의 resize, snapshot, backup, retire를 자동화한다.
- Resource Action, 운영 Workflow와 Action을 관리한다.
- 정책, Subscription, remediation과 drift를 관리한다.
- 운영 상태를 관찰하고 승인된 변경으로 수렴시킨다.

## GitOps 전달 수명주기

다음 기능은 특정 Day에 속하지 않고 모든 콘텐츠를 전달합니다.

```text
import/adopt → author → validate → sync → release → restore → observe/reconcile
```

- `vcf_sync.py`: status, pull, push, reconcile 기반
- `vcf_release.py`: backup, version artifact, restore
- `cli.py`: Day-0 discovery, adopt, validate와 status
- `configure.py`: 인스턴스 설정 검증과 이전 Terraform 입력 호환
- 향후 loop: observe, plan, approval, apply, verify, record

Release는 `export`와 `release-build`를 분리합니다. `export`는 원격을 변경하지 않는 추출이고, `release-build`는 Git의 local content를 입력으로 불변 artifact를 만듭니다. 기존 version 디렉터리는 덮어쓰지 않으며 manifest에는 source commit, target, tool version과 artifact SHA-256을 기록합니다. 기존 `backup` 명령은 read-only `export` alias입니다.

복구는 `restore-plan → review/approval → restore-apply → verify → record`로 실행합니다. Plan은 검증된 remote-export release digest, 대상 instance와 단일 target project, 현재 원격 observation에 결합됩니다. 모든 artifact hash를 별도 승인해야 하며 direct `restore`는 실행할 수 없습니다. 임의의 첫 project나 placeholder project로 fallback하지 않습니다.

`vcf_sync.py status --json`은 Loop와 AI Agent가 사용하는 read-only observe 계약입니다. 모든 제품 조회가 완료된 경우에만 `metadata.complete: true`를 반환하며, 일부 API나 로컬 콘텐츠 조회 실패를 빈 목록으로 취급하지 않습니다. 불완전한 observation은 `INCOMPLETE`로 종료되고 plan, pull 또는 push 입력으로 사용할 수 없습니다.

원격 변경을 Git에 수용할 때는 `pull-preview → review → accept-pull`을 사용합니다. Preview는 `.gitops/`에 생성되는 로컬 증거이며 Git이 소유하는 `content/`를 바꾸지 않습니다. Accept는 preview hash, preview 생성 당시 local content hash와 preview content hash가 모두 일치할 때만 신규·수정 파일을 반영합니다. 파일 삭제는 별도 명시적 흐름을 구현하기 전까지 수용하지 않습니다.

Git의 콘텐츠를 원격에 적용할 때는 `content-plan → review/approval → content-apply → verify → record`를 사용합니다. Plan은 lifecycle과 정확한 `product:type:identity` 선택자를 요구하며, 모든 drift를 암묵적으로 선택하지 않습니다. CREATE는 plan hash와 별도로 exact `approvalKey` 승인이 필요합니다. 원격 삭제는 지원하지 않습니다.

## 불변 조건

- 같은 콘텐츠를 Day별로 복제하지 않는다.
- `lifecycle/*.yaml`은 콘텐츠 경로와 사용 목적을 분류한다.
- import 결과는 검토 없이 `main`에 병합하지 않는다.
- 원격 변경은 대상, 변경 집합과 승인이 명확해야 한다.
- 릴리스 버전은 생성 후 덮어쓰지 않는다.
