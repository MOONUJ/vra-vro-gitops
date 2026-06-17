# 저장소 구조 (Repository Structure)

이 저장소는 VMware Aria Automation (vRA) 및 vRealize Orchestrator (vRO)에서 사용하는 인프라 구성, 스크립트, 블루프린트, 그리고 메타데이터를 하이브리드 GitOps 방식으로 관리합니다.

---

## 디렉토리 구조

```
vra-vro-gitops/
├── .gitignore                     # Git 제외 설정 (config.json 및 로컬 캐시 제외)
├── gitops/                        # 라이프사이클 관리 스크립트 디렉토리
│   ├── config.json.template       # 사용자 환경설정 템플릿 파일
│   ├── vro_client.py              # vRO REST API 클라이언트 공통 모듈
│   ├── vra_client.py              # vRA REST API 클라이언트 공통 모듈
│   ├── vcf_provision.py           # [Day-1] 프로비저닝 / 백업 / 복구 실행 프로그램 (신규)
│   ├── vcf_gitops.py              # [Day-2] GitOps 코드 동기화 실행 프로그램 (pull-all / push-all / status)
│   └── artifacts/                 # [Day-1] 백업 및 배포 버전별 아티팩트 보관 디렉토리 (자동 생성)
│       └── {version}/
│           ├── manifest.json              # 아티팩트 빌드 메타데이터 명세 파일
│           ├── vra-artifacts-{version}.zip # vRA 서비스 카탈로그 JSON/YAML 아카이브
│           └── vro-package-{version}.package # vRO 바이너리 패키지 파일
│
├── vra/                           # [Day-0] Aria Automation 초기 인프라 레이어 (Terraform)
│   ├── providers.tf               # vRA Provider 선언 및 인증 연동 설정
│   ├── variables.tf               # 공통 입력 변수 선언
│   ├── terraform.tfvars.template  # 사용자 자격 증명 템플릿 파일
│   ├── cloud_accounts.tf          # vSphere & NSX-T Cloud Accounts 설정
│   ├── cloud_zones.tf             # Cloud Zones 그룹화 정의
│   ├── network_profiles.tf        # 서브넷 대역 및 네트워크 정책 정의
│   ├── storage_profiles.tf        # 데이터스토어 및 스토리지 정책 정의
│   ├── image_mappings.tf          # OS 템플릿 이미지 프로필 매핑 정의
│   └── projects.tf                # Projects 바인딩 및 사용자 권한 할당 정의
│
├── auto/                          # [Day-2] Aria Automation 셀프서비스 카탈로그 (GitOps)
│   ├── blueprints/                # Cloud Templates (Blueprint) - 플랫 구조
│   │   └── {BlueprintName}/
│   │       ├── blueprint.json     # 블루프린트 메타데이터 및 projectName 매핑
│   │       └── blueprint.yaml     # 블루프린트 선언적 구성 (YAML)
│   │
│   ├── abx/                       # Action-based Extensibility (ABX) Actions - 플랫 구조
│   │   └── {ActionName}/
│   │       ├── init.json          # ABX 메타데이터 및 projectName 매핑
│   │       └── source.py          # ABX 실행 소스코드 (런타임에 따라 .py 또는 .js)
│   │
│   ├── custom_forms/              # 카탈로그 아이템 커스텀 폼 (.json)
│   ├── custom_resources/          # Custom Resource 정의 (.json)
│   ├── resource_actions/          # Resource Action 정의 (.json)
│   ├── catalog_sources/           # 카탈로그 아이템 소스 정의 (.json)
│   ├── policies/                  # 권한(Entitlement)/승인(Approval) 정책 (.json)
│   └── subscriptions/             # Event Broker 구독 정의 (.json)
│
└── vro/                           # [Day-2] vRealize Orchestrator 오케스트레이션 (GitOps)
    ├── packages/                  # 배포 초기화(부트스트랩)용 .package 바이너리 저장 폴더
    ├── workflows/                 # vRO 내 폴더 경로와 동일한 구조
    │   └── {folder}/
    │       └── {WorkflowName}/
    │           ├── workflow.json  # 워크플로우 기본 정보 (GET /workflows/{id})
    │           ├── content.json   # 워크플로우 전체 스키마 (GET /workflows/{id}/content)
    │           └── workflow-items/ # 스크립트 및 바인딩 추출 폴더
    │               └── {item_name}/ 
    │                   ├── value.js         # 실제 Javascript 소스코드
    │                   ├── in-binding.json  # 입력 매개변수 바인딩 설정
    │                   └── out-binding.json # 출력 매개변수 바인딩 설정
    ├── actions/                   # Actions (Javascript)
    │   └── {module}/
    │       └── {ActionName}/
    │           ├── action.json    # 액션 메타데이터 (FQN, 버전 등)
    │           └── script.js      # 액션 Javascript 소스코드
    ├── configurations/            # Configuration Elements Attributes JSON
    └── resources/                 # Resource Elements Metadata & Binary
```

---

## 파일 규칙 및 동기화 매핑 규칙

### 1. 코어(Core) vs 환경(Environment) 분할 저장소 모델
* **`vra-vro-gitops` 코어 저장소**: 공통 도구(`gitops/` 및 `vra/`)만 존재하며 `auto/` 및 `vro/` 아래 하위 리소스 폴더는 빈 상태로 관리됩니다.
* **환경별 저장소 (Fork)**: 각 환경 저장소(`vra-vro-gitops-dev`, `vra-vro-gitops-prod`)에서 `pull-all`을 최초 1회 수행하여 해당 타겟 서버의 UUID 메타데이터가 담긴 `auto/`, `vro/` 로컬 캐시 디렉토리를 구축해 코드 작업을 진행합니다.

### 2. vRA Blueprints (Cloud Templates)
* **blueprint.json**: 블루프린트의 ID, 설명, 태그, 버전 등의 메타데이터를 저장합니다.
* **blueprint.yaml**: 블루프린트의 본문 디자인 템플릿(YAML) 파일입니다. 로컬 수정 시 `push-all` 실행 시 서버에 반영되고 새로운 릴리즈 버전이 자동 생성됩니다.

### 3. vRA ABX Actions
* **init.json**: 실행 런타임, 진입점 함수명, 기본 입력 매개변수 정의 메타데이터를 저장합니다.
* **source.py / source.js**: 실제 실행 스크립트 소스코드 파일입니다. `init.json`에 선언된 런타임 속성에 따라 알맞은 확장자로 자동 생성/동기화됩니다.

### 4. vRA 공통 구성 요소 (Flat JSON)
Custom Resources, Resource Actions, Catalog Sources, Policies, Subscriptions는 독립적인 JSON 포맷으로 저장됩니다.
* 상태 대조(`status`) 및 동기화(`push-all`) 시 transient(휘발성) ID나 타임스탬프 필드를 제외한 실제 구성 속성들만 노멀라이즈 비교하여 변경 사항을 감지합니다.

### 5. vRO 리소스 규칙
* 이전 규칙과 동일하게 워크플로우 내 JS 스크립트(workflow-items), 액션 모듈 스크립트, configurations 속성, 그리고 리소스 바이너리들이 분리 동기화됩니다.
* **vRO 패키지**: `vcf_provision.py`에 의해 `manifest.json` 명세에 따라 내보내지고 임포트되는 버전 관리 핵심 파일입니다.
