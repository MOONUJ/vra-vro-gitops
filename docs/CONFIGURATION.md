# 인스턴스와 비밀값 설정

## 파일 경계

| 파일 | Git | 내용 |
| --- | --- | --- |
| `instance.example.yaml` | 추적 | 템플릿의 placeholder 인스턴스 정의 |
| `instance.yaml` | 생성된 저장소에서 추적 | Automation endpoint, 조직, GitOps 범위, 인프라 원하는 상태 |
| `secrets.example.json` | 추적 | 필요한 비밀 필드의 placeholder |
| `secrets.json` | 제외 | refresh token, vCenter/NSX 사용자명과 암호 |
| `instance.local.yaml` | 템플릿에서 제외 | 실제 연동 시험용 인스턴스 정의 |
| `secrets.local.json` | 제외 | 실제 연동 시험용 비밀값 |

이 구분을 통해 Cloud Zone, Project, Profile 같은 원하는 상태는 Git 이력에 남기고 자격 증명만 제외합니다.

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

템플릿 저장소에서 실제 연동을 시험할 때는 `instance.local.yaml`과 `secrets.local.json`을 사용하고 `--instance`, `--secrets` 옵션으로 경로를 전달합니다.

## Terraform 입력

```bash
.venv/bin/python tooling/vcf/configure.py terraform
terraform -chdir=foundation/automation/terraform plan
```

생성되는 `foundation/automation/terraform/generated.auto.tfvars.json`에는 비밀값이 포함되므로 Git에서 제외됩니다.

## 자동화 실행 환경

단일 `config.json` 형식과 `gitops/` 호환 경로는 지원하지 않습니다. CI/CD와 장기 실행 loop에서는 `secrets.json`을 저장소에 배포하기보다 secret manager에서 실행 시점에 주입하는 방식을 권장합니다.
