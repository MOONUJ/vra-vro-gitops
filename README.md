# VMware VCF Automation & Orchestrator GitOps

이 저장소는 VMware Aria Automation (vRA) 및 vRealize Orchestrator (vRO)의 소스코드와 인프라 구성을 Git으로 관리하고 자동 동기화(GitOps)하기 위해 사용됩니다.

## 🚀 주요 기능 (Features)

1. **하이브리드 아키텍처 역할 분담**:
   - **Terraform (`/vra`)**: 초기 인프라 레이어(Cloud Account, Cloud Zone, Network/Storage Profiles, Image Mappings, Project)를 IaC로 선언적 구축 및 초기화합니다.
   - **Python GitOps (`/auto`, `/vro`, `gitops/`)**: 셀프서비스 카탈로그 구성요소(Blueprints, Custom Resources, Resource Actions, Catalog, Policies, ABX, Subscriptions) 및 vRO 오케스트레이션 코드(Workflows, Actions, Configurations, Resources)를 동적 동기화합니다.
2. **태그(Tag) 기반 자원 탐색 및 Pull**: 
   - `config.json`에 정의된 태그(예: `gvp`)가 지정된 vRO/vRA 자원들을 동적으로 감지하여 로컬 저장소로 한 번에 가져옵니다.
3. **코드 및 구성 분리 추출 (Pull)**:
   - **Workflows/ABX Actions**: 코드를 매개변수 및 메타데이터와 분리하여 스크립트 파일(`.js`/`.py`)로 깔끔하게 추출합니다.
   - **Configurations/Forms**: 환경설정 및 속성 정의를 직관적인 JSON 파일로 저장합니다.
4. **인메모리 조립 및 동기화 (Push)**:
   - 로컬에서 수정된 코드 및 설정 파일들을 로드하여 서버 전송 시 동적으로 병합 조립 후 업데이트합니다.
5. **보안 인증 통합**:
   - Refresh Token (API Token) 기반의 단일 Access Token 획득 방식을 공유하여 vRA/vRO API 연동을 통합 처리합니다.

---

## 📂 파일 구조 (File Structure)

자세한 디렉토리 및 파일 상세 설명은 [STRUCTURE.md](STRUCTURE.md) 문서를 참고해 주세요.

---

## 🛠️ 준비 사항 (Prerequisites)

이 도구들은 **Terraform** 및 **Python 3** 환경에서 동작합니다:

```bash
# Python dependencies
pip3 install requests

# Terraform 설치 (macOS 예시)
brew tap hashicorp/tap
brew install hashicorp/tap/terraform
```

---

## 💻 사용 방법 (Usage)

### 1. 환경설정 파일 준비
템플릿 파일을 복사하여 `gitops/config.json`을 생성하고 VCF Automation 접속 정보 및 Refresh Token 자격 증명을 입력합니다. (`gitops/config.json`은 `.gitignore`에 의해 자동으로 Git 커밋 대상에서 제외됩니다.)

```bash
cp gitops/config.json.template gitops/config.json
```

### 2. 초기 인프라 세팅 (Terraform)
`/vra` 디렉토리로 이동하여 초기 인프라를 프로비저닝합니다:

```bash
cd vra
cp terraform.tfvars.template terraform.tfvars
# terraform.tfvars 수정 후:
terraform init
terraform plan
terraform apply
```

### 3. GitOps 동기화 명령어 실행 (CLI)

#### 📥 서버 ➔ 로컬 가져오기 (Pull)
서버에 지정된 태그(예: `gvp`)가 달린 vRO/vRA 자원들을 로컬로 일괄 동적 수집합니다:
```bash
python3 gitops/vcf_gitops.py pull-all
```

#### 📤 로컬 ➔ 서버 내보내기 (Push)
로컬 Git의 수정사항을 vRO 및 vRA 서버에 밀어넣습니다:
```bash
python3 gitops/vcf_gitops.py push-all
```

#### 📊 상태 비교 (Status)
서버와 로컬 Git 저장소의 소스코드 및 구성을 비교하여 변경 리포트(In Sync, Modified, Local Only, Server Only)를 확인합니다:
```bash
python3 gitops/vcf_gitops.py status
```

#### 🔍 모의 실행 (Dry Run)
실제 서버에 전송하지 않고 로컬 파일 시스템 파싱 및 매핑 결과만 검증하려면 `--dry-run` 플래그를 사용합니다:
```bash
python3 gitops/vcf_gitops.py --dry-run push-all
```

---

## 🔄 권장 개발 워크플로우 (GitOps Workflow)

1. **상태 확인**: `python3 gitops/vcf_gitops.py status` 명령을 실행하여 로컬과 서버의 변경 차이를 확인합니다.
2. **로컬 수정**: 각 자원 파일(JS/Python 코드, JSON 설정, YAML 블루프린트 등)에서 수정을 진행합니다.
3. **모의 검증**: `python3 gitops/vcf_gitops.py --dry-run push-all`을 실행하여 변경 대상을 최종 검증합니다.
4. **서버 배포**: `python3 gitops/vcf_gitops.py push-all`을 통해 실시간 서버 배포 및 동작을 반영합니다.
5. **Git 커밋**: 작업 완료 후 수정한 코드 및 설정 파일들을 Git에 스테이징하여 커밋 및 푸시합니다.
