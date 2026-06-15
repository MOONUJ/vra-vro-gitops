# VMware VCF Automation & Orchestrator GitOps

이 저장소는 VMware Aria Automation (vRA) 및 vRealize Orchestrator (vRO)의 소스코드와 인프라 구성을 Git으로 관리하고 자동 동기화(GitOps)하기 위해 사용됩니다.

## 🚀 주요 기능 (Features)

1. **태그(Tag) 기반 자원 탐색 및 Pull**: 
   - `config.json`에 정의된 태그(예: `gvp`)가 지정된 vRO 워크플로우(Workflows), 액션(Actions), 환경설정(Configurations), 리소스(Resources) 자원들을 동적으로 감지하여 로컬 저장소로 한 번에 가져옵니다.
2. **코드 및 구성 분리 추출 (Pull)**:
   - **Workflows**: 워크플로우 전체 스키마(`content.json`) 내에서 JavaScript 코드와 매개변수 바인딩 정보를 파싱하여 `workflow-items/{item_name}/` 경로 아래에 개별 파일(`value.js`, `in-binding.json`, `out-binding.json`)로 자동 분할 저장합니다.
   - **Actions**: 액션 메타데이터와 스크립트 코드를 분리하여 `script.js` 및 `action.json` 형태로 보관합니다.
   - **Configurations**: 환경설정 요소의 속성(Attributes) 값을 `T4-1G.json` 등 깔끔한 속성 정의 JSON 파일로 보관합니다.
   - **Resources**: 리소스 요소의 메타데이터와 본문 파일을 분리하여 개별 폴더 내에 저장합니다.
3. **인메모리 조립 및 동기화 (Push)**:
   - 로컬에서 수정한 코드 및 구성 정보들을 읽어와 서버 API로 전송 시 동적으로 조립하여 vRO 서버에 업데이트합니다.
4. **통합 패키지(.package) 기반 부트스트랩**:
   - 신규 서버 환경이거나 주요 자원이 누락된 경우, 동기화된 모든 자원을 포함하는 바이너리 패키지(`.package`)를 자동으로 임포트하여 전체 인벤토리 뼈대를 빌드(Bootstrap)하고 코드를 덮어씁니다.
5. **토큰 기반 보안 인증**:
   - ID/Password 방식을 차단하고 Refresh Token (API Token)만을 기반으로 단일 OAuth Access Token을 획득하여 vRA/vRO API 연동을 통합합니다.

---

## 📂 파일 구조 (File Structure)

자세한 디렉토리 및 파일 상세 설명은 [STRUCTURE.md](STRUCTURE.md) 문서를 참고해 주세요.

---

## 🛠️ 준비 사항 (Prerequisites)

이 스크립트는 **Python 3** 환경에서 동작하며 HTTP 요청 전송을 위해 `requests` 패키지가 필요합니다:

```bash
pip3 install requests
```

---

## 💻 사용 방법 (Usage)

### 1. 환경설정 파일 준비
템플릿 파일을 복사하여 `gitops/config.json`을 생성하고 VCF Automation 접속 정보 및 Refresh Token 자격 증명을 입력합니다. (`gitops/config.json`은 `.gitignore`에 의해 자동으로 Git 커밋 대상에서 제외됩니다.)

```bash
cp gitops/config.json.template gitops/config.json
```

**`gitops/config.json` 작성 예시:**
```json
{
  "vcf_url": "https://poscodx-auto.gooddi.lab",
  "org": "poscodx",
  "refresh_token": "AZzAiW6dkxVHSCGAkAMR7ZUPOLvjlEbT",
  "verify_ssl": false,
  "gitops_tag": "gvp",
  "package": {
    "name": "com.gvp.poscodx",
    "local_path": "vro/packages/com.gvp.poscodx.package"
  }
}
```

### 2. 동기화 명령어 실행

#### 📥 서버 ➔ 로컬 가져오기 (Pull)
서버에 지정된 태그(예: `gvp`)가 달린 자원들과 최신 패키지 백업 파일을 로컬로 동적 수집합니다:
```bash
python3 gitops/vcf_gitops.py pull-all
```

#### 📤 로컬 ➔ 서버 내보내기 (Push)
로컬 Git의 수정사항을 다시 vRO 서버에 밀어넣습니다 (서버에 워크플로우가 없는 경우 자동으로 설정된 `.package`를 배포하여 부트스트랩을 우선 진행합니다):
```bash
python3 gitops/vcf_gitops.py push-all
```

#### 📊 상태 비교 (Status)
서버와 로컬 Git 저장소의 소스코드 및 구성을 비교하여 변경 리포트(In Sync, Modified, Local Only, Server Only)를 확인합니다:
```bash
python3 gitops/vcf_gitops.py status
```

#### 🔄 강제 패키지 임포트 후 내보내기 (Bootstrap)
임포트 프로세스를 강제하여 패키지를 덮어쓴 뒤 소스코드를 적용하려는 경우 `--bootstrap` 플래그를 추가합니다:
```bash
python3 gitops/vcf_gitops.py push-all --bootstrap
```

#### 🔍 모의 실행 (Dry Run)
실제 서버에 전송하지 않고 로컬 파일 시스템 파싱 및 매핑 결과만 검증하려면 `--dry-run` 플래그를 사용합니다:
```bash
python3 gitops/vcf_gitops.py --dry-run push-all
```

---

## 🔄 권장 개발 워크플로우 (GitOps Workflow)

1. **상태 확인**: `python3 gitops/vcf_gitops.py status` 명령을 실행하여 로컬과 서버의 변경 차이를 먼저 확인합니다.
2. **로컬 수정**: 각 자원 파일(워크플로우 JS, 액션 JS, 구성 요소 JSON, 리소스 본문 파일 등)에서 수정을 진행합니다.
3. **모의 검증**: `python3 gitops/vcf_gitops.py --dry-run push-all`을 실행하여 빌드 에러 및 변경 대상을 검증합니다.
4. **서버 배포**: `python3 gitops/vcf_gitops.py push-all`을 통해 실시간 vRO 서버 배포 및 동작을 확인합니다.
5. **Git 커밋**: 작업 완료 후 수정한 코드 및 설정 파일(`.js`, `.json` 등)과 업데이트된 `.package` 바이너리를 Git에 스테이징하여 커밋 및 푸시합니다.
