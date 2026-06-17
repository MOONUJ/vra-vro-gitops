# VMware VCF Automation & Orchestrator Day-0/1/2 형상관리

이 저장소는 VMware Aria Automation (vRA) 및 vRealize Orchestrator (vRO)의 인프라 구축, 서비스 카탈로그 아티팩트 관리 및 소스코드 변경을 GitOps 사상에 맞춰 안정적으로 분리 운영(Day-0, Day-1, Day-2)할 수 있도록 관리합니다.

---

## 🚀 아키텍처 및 역할 분담 (Day-0/1/2)

```mermaid
graph TD
    subgraph Day-0 : 인프라 IaC (Terraform)
        TF[vra/] -->|IaC 프로비저닝| Infrastructure[Cloud Accounts, Zones, Networks, Storages, Projects]
    end

    subgraph Day-1 : 논리적 카탈로그 & 패키징 (vcf_provision.py)
        Provision[gitops/vcf_provision.py] -->|backup / provision / restore| Artifacts[gitops/artifacts/ - vRO Package, vRA Config Zip, Manifest]
        Artifacts -->|초기 뼈대 구축| Servers[Target vRA/vRO Servers]
    end

    subgraph Day-2 : 지속적 코드 동기화 (vcf_gitops.py)
        GitOps[gitops/vcf_gitops.py] -->|pull-all| Local[Local Workspace: auto/, vro/]
        Local -->|push-all: 오직 수정만 허용| Servers
    end
```

### 1. Day-0 (인프라 인프라 레이어 - Terraform)
* **경로**: `/vra`
* **역할**: 클라우드 계정 연동, 네트워크/스토리지 프로필, 이미지 매핑, 프로젝트 세팅 등 vRA 테넌트 내 초기 물리적/논리적 인프라 구성을 IaC로 선언적 구축 및 초기화합니다.

### 2. Day-1 (서비스 카탈로그 & 패키징 - Provisioning CLI)
* **경로**: `gitops/vcf_provision.py`
* **역할**: 서비스 카탈로그(`blueprints`, `abx`, `custom_forms`, `custom_resources`, `policies`, `resource_actions`, `subscriptions`, `catalog_sources`) 및 vRO 패키지(`.package`)를 **배포용 독립 아티팩트(Artifact)**로 묶어 관리하고, 대상 서버에 신규 생성 및 복원(Restore)을 전담합니다.

### 3. Day-2 (지속적 소스코드 동기화 - GitOps CLI)
* **경로**: `gitops/vcf_gitops.py`
* **역할**: 개발 과정에서의 스크립트 코드(JS 워크플로우/액션, Python ABX, YAML 블루프린트 구성 등)의 실시간 상태 비교(`status`) 및 수정 내용 동기화(`push-all`)를 전담합니다. **(※ 서버에 없는 리소스의 임의 신규 생성은 안전을 위해 차단됩니다.)**

---

## 📂 파일 구조 (File Structure)

자세한 디렉토리 및 파일 매핑 상세 설명은 [STRUCTURE.md](STRUCTURE.md) 문서를 참고해 주세요.

---

## 🛠️ 사용 방법 (Usage)

### 1. 환경설정 파일 준비
템플릿 파일을 복사하여 `gitops/config.json`을 생성하고 VCF Automation 접속 정보 및 Refresh Token 자격 증명을 입력합니다. (`gitops/config.json`은 Git 추적에서 제외됩니다.)

```bash
cp gitops/config.json.template gitops/config.json
```

### 2. 초기 인프라 세팅 (Day-0 - Terraform)
`/vra` 디렉토리로 이동하여 초기 인프라 레이어를 구축합니다.

```bash
cd vra
cp terraform.tfvars.template terraform.tfvars
# terraform.tfvars 수정 후:
terraform init
terraform plan
terraform apply
```

### 3. 카탈로그 & 패키지 프로비저닝 (Day-1 - Provision CLI)

#### 📥 서버 ➔ 로컬 백업 (아티팩트 패키징)
서버에 배포된 카탈로그 정의들을 수집하여 버전명이 부여된 zip 및 package 배포용 아티팩트를 생성합니다.
```bash
python3 gitops/vcf_provision.py backup --version 1.0.0
```
* **생성 파일**: `gitops/artifacts/1.0.0/` 폴더 내에 `manifest.json`, `vra-artifacts-1.0.0.zip`, `vro-package-1.0.0.package` 생성.

#### 📤 로컬 아티팩트 ➔ 대상 서버 배포 및 복구 (Restore)
백업된 아티팩트를 읽어와 대상 서버에 신규 배포(초기 뼈대 생성)하거나, 문제가 발생할 경우 이전 안정화 버전의 아티팩트로 복구(Rollback)합니다.
```bash
python3 gitops/vcf_provision.py restore --version 1.0.0
```

### 4. 코드 동기화 및 상태 비교 (Day-2 - GitOps CLI)

#### 📥 서버 ➔ 로컬 가져오기 (Pull)
서버의 자원을 로컬 Git 저장소(`auto/`, `vro/`)로 일괄 동적 가져옵니다.
```bash
python3 gitops/vcf_gitops.py pull-all
```

#### 📤 로컬 ➔ 서버 코드 반영 (Push)
로컬에서 수정한 코드 및 설정을 서버에 실시간 업데이트합니다. (서버에 없는 자원은 생성이 차단되고 Skip 처리됩니다.)
```bash
python3 gitops/vcf_gitops.py push-all
```

#### 📊 상태 비교 (Status)
서버와 로컬 Git 저장소의 소스코드 상태를 비교하여 불일치 건을 탐색합니다.
```bash
python3 gitops/vcf_gitops.py status
```

---

## 📄 라이선스 (License)

이 프로젝트는 [MIT License](LICENSE) 라이선스 하에 배포됩니다. 자세한 내용은 `LICENSE` 파일을 참고해 주세요.
