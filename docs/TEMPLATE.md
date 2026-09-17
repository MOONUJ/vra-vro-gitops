# 템플릿 운영

## 역할

이 저장소는 VCF Automation 인스턴스 저장소를 생성하기 위한 기준 템플릿입니다. 실제 인스턴스마다 템플릿으로 새 저장소를 만들고, 저장소와 Automation을 일대일로 대응시킵니다.

일반 fork보다 Template Repository를 기본으로 사용합니다. 생성된 저장소가 독립된 이력과 권한을 가지므로 인스턴스 간 변경과 비밀정보 경계를 분리하기 쉽습니다.

## 템플릿에 포함하는 것

- 디렉터리 구조와 lifecycle manifest
- native 인프라 GitOps, 선택적 Terraform, sync, release와 bootstrap 도구
- `instance.example.yaml`, `secrets.example.json`
- AGENTS, Skill, Loop 계약
- 공통 테스트와 문서
- `.template-version`

## 템플릿에 포함하지 않는 것

- 실제 endpoint가 담긴 `instance.yaml`
- 자격 증명, token, 인증서
- Terraform state와 plan
- 특정 Automation에서 import한 콘텐츠
- 특정 인스턴스용 release artifact와 실행 로그

## 생성과 초기화

GitHub에서 Template Repository로 설정하고 **Use this template**로 저장소를 생성합니다. 새 저장소에서 다음 명령을 실행합니다.

```bash
python3 tooling/template/bootstrap.py \
  --name automation-seoul-prod \
  --endpoint https://automation.example.com \
  --environment-tag seoul-prod
```

생성된 `instance.yaml`은 비밀 없는 연결·관리 정책이므로 Git에 추가합니다. 생성된 `secrets.json`은 권한 `0600`으로 만들고 Git에서 제외하며 placeholder를 실제 값으로 교체합니다. Day-0 원하는 상태는 `infrastructure/`에 별도 manifest로 추가합니다.

AGENTS, Skill과 Loop 예시도 템플릿에서 함께 복사됩니다. 이들은 `instance.yaml`의 Git 추적 여부로 템플릿 모드와 인스턴스 모드를 구분합니다. 생성 직후 `instance.yaml`이 아직 untracked인 동안은 Loop를 활성화하지 않으며, 최초 baseline을 검토·커밋한 뒤 실제 Loop 파일의 `.example`을 제거하고 `instanceRef`와 `enabled`를 명시합니다.

## 버전과 업데이트

`.template-version`은 저장소를 생성하거나 마지막으로 공통 변경을 반영한 템플릿 버전을 나타냅니다. 템플릿 변경은 tag와 changelog로 배포하는 방식을 권장합니다.

초기에는 템플릿 릴리스의 변경 내역을 보고 필요한 commit을 인스턴스 저장소 PR로 선택 적용합니다. 반복 비용이 커지면 공통 Python 패키지 또는 업데이트 도구로 분리합니다. 템플릿 업데이트가 인스턴스의 `instance.yaml`, `content/`, `lifecycle/`을 자동 덮어쓰면 안 됩니다.

## 실제 연동 검증

템플릿 저장소 안에서 검증해야 한다면 `integration/*` 브랜치와 로컬 전용 설정을 사용합니다. 재사용 가능한 수정만 `main`에 병합합니다. 안정화 이후에는 템플릿으로 생성한 pilot 저장소를 사용하여 생성부터 import, plan, sync까지 전체 흐름을 검증합니다.
