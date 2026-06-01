# Repository Structure

이 저장소는 VMware Aria Automation(이하 AA)과 vRealize Orchestrator(이하 vRO)에서 사용하는 스크립트 및 메타데이터를 관리합니다.
각 디렉토리는 해당 플랫폼의 import/export 경로 구조를 그대로 반영합니다.

---

## 디렉토리 구조

```
poscodx/
├── auto/                          # Aria Automation 리소스
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
    ├── workflows/                 # Workflows
    │   └── {folder}/              # vRO 내 폴더 경로와 동일
    ├── actions/                   # Actions (JavaScript)
    ├── configurations/            # Configuration Elements
    └── resources/                 # Resource Elements
```

---

## 파일 규칙

### ABX Action

각 ABX Action은 독립된 디렉토리로 관리하며, 디렉토리명은 Action 이름과 동일합니다.

```
auto/project_scope/{project}/ABX/{ActionName}/
├── init.json     # Action 메타데이터
└── source.py     # Action 핸들러 코드 (python 런타임 기준)
```

**init.json 필드**

| 필드 | 설명 |
|---|---|
| `name` | AA에 등록된 Action 이름 |
| `project` | 소속 프로젝트명 |
| `mainFunction` | 진입 함수명 (기본값: `handler`) |
| `runtime` | 런타임 (`python`, `nodejs` 등) |
| `defaultInputs` | 기본 입력값 목록 |

### vRO Workflow

각 Workflow는 독립된 디렉토리로 관리하며, 디렉토리명은 Workflow 이름과 동일합니다.

```
vro/workflows/{folder}/{WorkflowName}/
└── init.json     # Workflow 메타데이터
```

**init.json 필드**

| 필드 | 설명 |
|---|---|
| `workflowName` | vRO에 등록된 Workflow 이름 |
| `id` | vRO Workflow UUID |
| `version` | 버전 |
| `folder` | vRO 내 폴더 경로 |

---

## 기능 간 연결 관계

리소스 간 호출 관계는 각 기능의 설계서에서 관리합니다. 디렉토리 구조는 플랫폼별 분류만 표현하며, 기능 단위의 묶음은 표현하지 않습니다.

**현재 구현된 기능**

| 기능 | AA 리소스 | vRO 리소스 | 설계서 |
|---|---|---|---|
| Custom VPC 생성 | `auto/project_scope/admin/ABX/Custom.VPC.create` | `vro/workflows/GVP/Custom.VPC.nsxTier1Manager` | [custom_vpc_design.md](custom_vpc_design.md) |

---

## 네이밍 규칙

- **기능 prefix**: `Custom.{기능명}` — 자체 개발 리소스임을 구분
- **폴더명**: vRO 내 실제 폴더 경로와 동일하게 유지 (예: `GVP`)
- **프로젝트 디렉토리**: AA 프로젝트명과 동일하게 소문자 사용
