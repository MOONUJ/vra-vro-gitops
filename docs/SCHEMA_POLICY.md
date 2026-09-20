# Schema, Policy와 CI 계약

## Versioned schema

추적 대상 manifest의 구조는 `schemas/`의 versioned JSON Schema로 관리합니다.

| Kind | 현재 버전 |
| --- | --- |
| `AutomationInstance` | `gitops.vcf.example/v1alpha2` |
| Infrastructure resource | `gitops.vcf.example/v1alpha1` |
| `ContentIdentity` | `gitops.vcf.example/v1alpha1` |
| `LifecycleManifest` | `gitops.vcf.example/v1alpha1` |
| `ReconciliationLoop` | `gitops.vcf.example/v1alpha1` |
| `GitOpsPolicy` | `gitops.vcf.example/v1alpha1` |

```bash
python3 tooling/vcf/schema_validation.py
```

Schema의 major 또는 alpha 버전을 변경할 때는 기존 문서를 자동으로 덮어쓰지 않습니다. 새 schema와 preview 가능한 migration을 먼저 추가하고, loader가 이전·신규 버전을 함께 읽는 전환 기간을 둔 뒤 별도 템플릿 release에서 기존 버전 지원을 종료합니다.

## Policy-as-code

기본 정책은 `governance/policy.yaml`에 있습니다. 최대 plan 작업 수, production mutation, CREATE와 DELETE의 별도 승인 요구를 정의합니다. Infrastructure, content와 restore plan은 policy hash를 포함하며 apply 전에 현재 policy와 다시 비교합니다. 정책이 변경되면 기존 승인은 무효가 됩니다.

기본 정책은 이름에 `prod` 또는 `production` 경계를 포함하는 instance의 원격 mutation을 차단합니다. Production 적용은 정책 변경 자체에 대한 별도 검토 없이는 허용하지 않습니다.

## CI

`.github/workflows/validate.yaml`은 다음 검사를 credential과 원격 연결 없이 실행합니다.

- Python compile과 전체 unit test
- versioned repository schema
- instance와 secret example 설정
- infrastructure와 content identity
- Terraform format

저장소 branch protection에서는 `repository`와 `terraform-format` job을 PR 필수 check로 사용합니다.
