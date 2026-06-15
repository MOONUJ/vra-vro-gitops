# 저장소 구조 (Repository Structure)

이 저장소는 VMware Aria Automation (vRA) 및 vRealize Orchestrator (vRO)에서 사용하는 스크립트, 메타데이터, 그리고 패키지를 GitOps 방식으로 관리합니다.
각 디렉토리는 해당 플랫폼의 인벤토리 구조와 Import/Export 경로 규칙을 반영합니다.

---

## 디렉토리 구조

```
poscodx/
├── .gitignore                     # Git 제외 설정 (config.json 및 캐시 제외)
├── gitops/                        # GitOps 동기화 스크립트 디렉토리
│   ├── config.json.template       # 환경설정 템플릿 파일
│   ├── vro_client.py              # vRO REST API 클라이언트 모듈
│   └── vcf_gitops.py              # GitOps CLI 실행 프로그램 (pull-all / push-all)
│
├── auto/                          # Aria Automation 리소스 (ABX Actions, Templates 등)
│   ├── project_scope/             # 특정 프로젝트에 속하는 리소스
│   │   ├── admin/                 # 'admin' 프로젝트
│   │   │   ├── ABX/               # ABX Actions
│   │   │   └── Templates/         # Cloud Templates (Blueprint)
│   │   └── stage/                 # 'stage' 프로젝트
│   │       ├── ABX/
│   │       └── Templates/
│   └── any_project_scope/         # 모든 프로젝트에서 공유하는 리소스
│       ├── Content_Sources/       # Content Source 설정
│       └── Custom_Resources/      # Custom Resource 정의
│
└── vro/                           # vRealize Orchestrator 리소스
    ├── packages/                  # 배포 초기화(부트스트랩)용 .package 바이너리 저장 폴더
    ├── workflows/ (또는 Workflows/) # vRO 내 폴더 경로와 동일한 구조
    │   └── {folder}/
    │       └── {WorkflowName}/
    │           ├── workflow.json  # 워크플로우 기본 정보 (GET /workflows/{id})
    │           ├── content.json   # 워크플로우 전체 스키마 (GET /workflows/{id}/content)
    │           └── workflow-items/ # 스크립트 및 바인딩 추출 폴더
    │               └── {item_name}/ # 각 노드 아이디(예: item1) 기준
    │                   ├── value.js         # 실제 Javascript 소스코드
    │                   ├── in-binding.json  # 입력 매개변수 바인딩 설정
    │                   └── out-binding.json # 출력 매개변수 바인딩 설정
    ├── actions/                   # Actions (Javascript)
    │   └── {module}/
    │       └── {ActionName}/
    │           ├── action.json    # 액션 메타데이터 (FQN, 버전 등)
    │           └── script.js      # 액션 Javascript 소스코드
    ├── configurations/            # Configuration Elements
    │   └── {category}/
    │       └── {ConfigName}.json  # 환경설정 속성(Attributes) 정의 JSON 파일
    └── resources/                 # Resource Elements
        └── {category}/
            └── {ResourceName}/
                ├── resource.json  # 리소스 메타데이터 (ID, Mime-Type 등)
                └── {ResourceName} # 리소스 실제 본문 파일 (바이너리 또는 스크립트)
```

---

## 파일 규칙 및 동기화 매핑 규칙

### 1. vRO Workflows
각 워크플로우는 독립된 디렉토리로 관리하며, 디렉토리명은 vRO 내 워크플로우 이름과 동일합니다.
- **workflow.json**: vRO에 등록된 워크플로우의 고유 ID(UUID), 이름, 버전 등을 보관합니다.
- **content.json**: 워크플로우의 전체 XML/JSON 스키마 데이터입니다.
- **workflow-items/{item_name}/**: `content.json` 내의 스크립트 코드나 바인딩 정보가 존재하는 노드(예: `item1`)들만 자동으로 추출하여 관리하기 편한 개별 텍스트 파일로 저장합니다. 
  - `value.js`에 작성한 코드는 `push-all` 실행 시 `content.json`의 해당 아이템 스키마에 자동으로 결합(Assembly)되어 vRO 서버로 전송됩니다.

### 2. vRO Actions
각 액션은 지정된 모듈 디렉토리 하위에 액션명으로 관리됩니다.
- **action.json**: FQN(Fully Qualified Name), 버전, ID 등의 메타데이터를 저장합니다. 소스코드 노이즈를 최소화하기 위해 스크립트 본문 필드는 비워둡니다.
- **script.js**: 액션의 실행 로직인 실제 Javascript 코드입니다. `push-all` 시 `action.json`에 병합되어 반영됩니다.

### 3. vRO Configurations
환경설정 요소들은 카테고리 디렉토리 내에 개별 JSON 파일로 저장됩니다.
- **{ConfigName}.json**: 고유 ID, 이름, 버전 및 구성 속성(Attributes) 값들의 배열을 깔끔한 JSON 포맷으로 저장합니다. `push-all` 시Attributes 데이터를 서버에 덮어씁니다.

### 4. vRO Resources
리소스 요소들은 파일명과 동일한 이름의 폴더 내에서 관리됩니다.
- **resource.json**: 고유 ID, 이름, 버전, MIME 타입, 설명(Description) 등을 저장합니다.
- **{ResourceName}**: 쉘 스크립트, 바이너리, 설정 파일 등의 실제 리소스 본문 파일입니다.

### 5. ABX Action (Aria Automation)
각 ABX Action은 독립된 디렉토리로 관리하며, 디렉토리명은 Action 이름과 동일합니다.
```
auto/project_scope/{project}/ABX/{ActionName}/
├── init.json     # Action 메타데이터 (프로젝트명, 런타임, 기본입력 등)
└── source.py     # Action 핸들러 코드 (python 런타임 기준)
```

---

## 네이밍 규칙

- **기능 prefix**: `Custom.{기능명}` — 자체 개발 리소스임을 구분 (예: `Custom.VPC.create`)
- **폴더명**: vRO 내 실제 폴더 경로와 동일하게 유지 (예: `GVP/Task`)
- **프로젝트 디렉토리**: vRA 프로젝트명과 동일하게 소문자 사용
