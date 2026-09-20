# 콘텐츠 Identity와 정규화 계약

Automation과 Orchestrator 콘텐츠는 이름이나 부분 tag만으로 mutation 대상을 결정하지 않습니다. Tag와 project는 discovery 범위를 좁히는 데만 사용하고, Git이 소유하는 대상은 콘텐츠별 `ContentIdentity` sidecar로 결합합니다.

## Sidecar 위치

디렉터리 기반 콘텐츠는 리소스 디렉터리의 `.gitops.yaml`을 사용합니다.

```text
content/automation/blueprints/application/.gitops.yaml
content/automation/abx/notify/.gitops.yaml
content/orchestrator/workflows/Operations/Resize/.gitops.yaml
content/orchestrator/actions/com.example/format/.gitops.yaml
content/orchestrator/resources/logo/.gitops.yaml
```

단일 JSON 파일 기반 콘텐츠는 같은 디렉터리에 `{name}.gitops.yaml`을 사용합니다.

```text
content/automation/policies/lease.json
content/automation/policies/lease.gitops.yaml
content/orchestrator/configurations/endpoints.json
content/orchestrator/configurations/endpoints.gitops.yaml
```

## 형식

```yaml
apiVersion: gitops.vcf.example/v1alpha1
kind: ContentIdentity
metadata:
  name: application
  remoteId: CHANGE_AFTER_ADOPT
spec:
  product: automation
  type: Blueprint
  path: content/automation/blueprints/application
  scope:
    project: application-team
  usages: [provisioning]
```

`metadata.remoteId`가 없는 항목은 생성 후보일 뿐이며 자동 생성하지 않습니다. `scope`는 같은 이름이 여러 project나 category에 존재할 때 logical identity를 분리합니다. `usages`는 lifecycle 용도를 설명하지만 콘텐츠를 복제하지 않습니다.

## 지원 종류

| Product | Type | 경로 형식 |
| --- | --- | --- |
| automation | `Blueprint`, `ABXAction` | 리소스 디렉터리 |
| automation | `CatalogSource`, `CustomForm`, `CustomResource`, `Policy`, `ResourceAction`, `Subscription` | JSON 파일 |
| orchestrator | `Workflow`, `Action`, `Resource` | 리소스 디렉터리 |
| orchestrator | `Configuration` | JSON 파일 |

## Preview와 검증

기존 콘텐츠의 sidecar 후보는 파일을 쓰지 않는 preview로 확인합니다.

```bash
python3 tooling/vcf/content_identity.py preview --json
python3 tooling/vcf/content_identity.py validate
```

Preview에는 remote ID를 추측하지 않습니다. 실제 ID와 scope는 discovery 결과를 검토하여 채택하는 후속 흐름에서 기록합니다.

## 정규화

비교 hash에서는 timestamp, owner, organization ID와 링크 같은 관측 필드를 제거합니다. 줄바꿈과 dictionary key 순서를 정규화하고 dictionary 목록은 canonical JSON 순서로 정렬합니다. `SecureString` 값은 값 자체를 저장하지 않고 redacted marker로 대체합니다.

Identity 중복, remote ID 중복, path 중복, 지원 경로 밖 참조 또는 존재하지 않는 대상은 전체 검증을 실패시킵니다.
