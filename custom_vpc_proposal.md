# VPC · Segment 커스텀 리소스 도입 기획안

> **문서 버전:** 1.1
> **작성일:** 2026-04-27
> **대상 시스템:** P-Cloud 2.0 (Portal + VCF Automation + NSX-T)
> **대상 카탈로그:** `Custom.VPC`, `Custom.Segment`

---

## 1. 배경

### 1.1 P-Cloud 2.0 현황

P-Cloud 2.0은 **VMware Cloud Foundation 9.0** 기반의 차세대 그룹사 클라우드 환경으로 구축되었으며, 다음과 같은 구조로 셀프서비스를 제공하고 있습니다.

```
[그룹사 사용자]
      │
      ▼
[P-Cloud Portal] ── (셀프서비스 UI / 결재 / 빌링)
      │
      ▼
[VCF Automation] ── (자동 프로비저닝 / Day-2 작업)
      │
      ▼
[NSX-T / vSphere / vSAN] ── (실제 인프라)
```

Portal(ClovirONE 2.0)이 **사용자 접점**을 담당하고, VCF Automation이 **실제 자원을 만들어 주는 자동화 엔진**으로 동작하는 구조입니다. 사용자는 Portal에서 카탈로그를 선택하여 신청하고, 결재가 승인되면 Automation이 자동으로 가상머신과 네트워크 자원을 생성합니다.

### 1.2 현재 제공되는 셀프서비스 항목

P-Cloud 2.0 Portal에서 현재 사용자에게 제공되는 주요 카탈로그는 아래와 같습니다.

| 구분 | 제공 기능 |
|------|----------|
| 가상머신(VM) | 신규 생성, 자원변경, 디스크 확장, IP 변경, 네트워크 어댑터 추가 |
| GPU 가상머신 | 신규 생성, 자원변경, 디스크 확장, IP 변경, 네트워크 어댑터 추가 |
| 프로젝트 | 조직별 프로젝트 생성, 자원 이관, 결재 프로세스 |
| 부가서비스 | NAS 등록, 모니터링 활성화, 원격 콘솔 |
| VPC (네트워크 영역) | ❌ 미제공 (운영자 수동 작업) |
| Segment (망/서브넷) | ❌ 미제공 (운영자 수동 작업) |

즉, **컴퓨팅 자원(VM/GPU VM)에 대한 셀프서비스는 갖춰져 있으나, 네트워크 자원(VPC·Segment)을 사용자(또는 운영자)가 직접 셀프로 만드는 체계는 부재**합니다. 현재 네트워크 자원은 모두 운영자가 NSX-T Manager 콘솔에서 수동으로 만들고, Aria Automation에 별도로 등록해주는 형태로 운영됩니다.

### 1.3 P-Cloud 2.0의 개선 방향

P-Cloud 2.0은 P-Cloud 1.0 대비 다음과 같은 개선 방향을 지향합니다.

- **멀티 테넌트 기반 리소스 분리 및 관리 체계 도입**
  계열사(조직)별로 컴퓨팅·네트워크 리소스를 논리적으로 분리하고 독립적으로 관리할 수 있는 테넌트 체계를 갖춘다.

- **NSX-T Gateway Firewall 기반 보안 강화**
  그룹사 간 VPC 구간에 방화벽을 구성하여, 네트워크 트래픽을 보안 정책에 따라 통제할 수 있도록 한다.

즉, **VPC**는 이미 P-Cloud 2.0의 멀티테넌트 아키텍처에서 **계열사(조직) 단위 네트워크 격리의 핵심 단위**로 정의되어 있고, 그 안에서 실제 워크로드(VM)가 붙는 단위가 **Segment(서브넷)** 입니다. 그러나 현재까지 VPC와 Segment는 모두 운영자가 NSX-T Manager에 직접 접속해 **수동으로 Tier-1 Gateway와 Segment를 만드는 방식**으로 운영되고 있습니다.

---

## 2. 문제 정의

### 2.1 운영상의 한계점

| # | 문제점 | 영향 |
|---|--------|------|
| 1 | **VPC·Segment 생성이 모두 수동 작업**으로 이루어짐 (NSX 운영자가 콘솔에서 직접 Tier-1 Gateway / Segment 생성) | 신규 계열사 온보딩·신규 망 추가 리드타임 증가 |
| 2 | Segment를 만든 뒤 Aria Network Profile에 등록·Capability Tag 부여 작업을 **운영자가 별도로 수행** | 등록 누락 시 VM 신청 시 해당 Segment를 선택할 수 없는 장애 발생 |
| 3 | VPC와 Network Profile, Segment의 **소속 관계를 운영자가 머릿속으로 관리** | 휴먼 에러로 인한 잘못된 연결 가능성 |
| 4 | VPC·Segment 자원 현황이 **Portal에서 보이지 않음** (NSX 콘솔에서만 조회 가능) | 그룹사 사용자가 자신의 네트워크 자원을 가시적으로 파악 불가 |
| 5 | VPC 삭제 시 **연결된 Segment 존재 여부를 운영자가 일일이 확인** | 잘못된 삭제로 서비스 영향 발생 가능 |
| 6 | 기존 운영 중인 Tier-1·Segment를 P-Cloud로 **흡수(Import)할 표준 절차 부재** | 마이그레이션 시 일관성 결여 |

### 2.2 사용자/운영자 관점의 불편

- **그룹사 사용자**: "우리 조직의 네트워크 영역(VPC)과 그 안의 망(Segment)이 어떻게 구성되어 있는지 Portal에서 보고, 필요한 망은 셀프로 신청하고 싶다."
- **클라우드 운영자**: "신규 계열사가 들어올 때마다 Tier-1을 만들고, 망(Segment)을 만들고, Network Profile에 등록하고, Capability Tag를 부여하는 일을 반복하고 있다."
- **보안 관리자**: "VPC와 Segment 단위로 누가 언제 만들었고, 결재 이력이 어떻게 되는지 추적하고 싶다."

---

## 3. 추진 목적

### 3.1 한 줄 요약

> **VPC와 Segment를 P-Cloud Portal의 정식 셀프서비스 카탈로그로 등록하여, 계열사(조직) 단위 네트워크 영역과 그 안의 망(서브넷)을 결재 기반으로 자동 생성·관리하는 체계를 구축한다.**

### 3.2 추진 범위 (대상 카탈로그)

본 기획에서는 다음 두 종류의 **커스텀 리소스(Custom Resource Type)** 를 신규로 만들어 카탈로그에 등록합니다.

| 카탈로그 | 한 줄 설명 | 실제 만들어지는 자원 |
|---------|-----------|-------------------|
| **`Custom.VPC`** | 계열사 단위 네트워크 영역 | NSX Tier-1 Gateway + Aria Network Profile |
| **`Custom.Segment`** | VPC 안의 서브넷(망) | NSX Segment + Network Profile에 등록 + Capability Tag 부여 |

VPC가 **"건물 안의 사무실 단위"** 라면, Segment는 **"사무실 안의 책상(워크스테이션) 단위"** 로 이해하면 됩니다. VM은 Segment 위에서 IP를 부여받아 동작합니다.

### 3.3 세부 목표

1. **자동화** — VPC·Segment 생성/삭제를 운영자 수동작업에서 **결재 기반 자동 프로비저닝**으로 전환
2. **표준화** — 명명 규칙(Naming Convention)과 소속 관계(VPC ↔ Network Profile ↔ Segment ↔ Capability Tag)를 **시스템적으로 강제**
3. **가시화** — VPC와 Segment를 Portal에서 **각각 하나의 자원 항목**으로 노출하여 조직별 네트워크 자원을 한눈에 파악
4. **확장성** — 향후 추가될 **CaaS, LBaaS, 3rd-party-aaS** 카탈로그가 VPC·Segment 위에서 동작할 수 있는 기반 확보
5. **안전성** — VPC·Segment 삭제 시 연결 자원(상위 VPC 또는 Segment 위에 떠 있는 VM 등) **자동 검증**으로 휴먼 에러 차단

---

## 4. 개념 정의 (비개발자 대상)

### 4.1 VPC란?

**VPC(Virtual Private Cloud, 가상 사설 클라우드)** 는 *"한 조직(계열사)이 클라우드 안에서 독점적으로 사용하는 격리된 네트워크 공간"* 을 의미합니다.

쉽게 비유하자면, 거대한 데이터센터 건물 안에서 **계열사별로 벽으로 분리된 전용 사무실**을 갖는 것과 같습니다. 같은 건물(P-Cloud)에 있지만, 다른 계열사의 트래픽이 우리 영역에 들어올 수 없도록 **논리적으로 차단된 네트워크 영역**입니다.

### 4.2 P-Cloud에서 VPC의 실체

P-Cloud의 VPC는 기술적으로 다음 두 가지 요소가 묶인 단위입니다.

| 구성 요소 | 역할 | 비유 |
|----------|------|------|
| **NSX Tier-1 Gateway** | 계열사 전용 라우터 | 사무실 출입구 |
| **Aria Network Profile** | 자동화 엔진이 인식하는 네트워크 영역 정의 (Segment 묶음) | 사무실 평면도 |

사용자는 이 두 가지를 **"VPC 하나"** 로 인식하면 되며, 내부적으로는 시스템이 알아서 묶어서 관리합니다.

> **참고 — VM은 어떻게 VPC의 네트워크에 연결되나?**
> Automation에는 별도의 "vpc 식별자"라는 자원이 존재하지 않습니다. 대신 **Network Profile에 등록된 Segment(네트워크) 목록**과 **Capability Tag(특성 태그)** 매칭 방식을 사용합니다.
> 즉, VM 신청 시 사용자는 Segment를 직접 고르거나, 시스템이 조직(테넌트)에 해당하는 Capability Tag로 적합한 Segment를 자동 매칭하여 연결합니다. VPC 커스텀 리소스는 이 Network Profile과 그 안에 등록될 Segment의 **소속 관계와 명명 규칙**을 자동으로 관리해주는 역할을 합니다.

### 4.3 Segment란?

**Segment(세그먼트)** 는 *"VPC 안에서 VM이 실제로 IP를 받아 연결되는 가상 서브넷(망)"* 입니다.

- 하나의 VPC 안에는 여러 Segment를 둘 수 있음 (예: 서비스망, DB망, 관리망 등)
- Segment는 NSX에서 **Overlay Segment** 또는 **VLAN Segment**로 구현됨
- VM이 Segment에 연결되면 해당 Segment의 IP 대역에서 IP를 받음

### 4.4 P-Cloud에서 Segment의 실체

Segment 카탈로그가 자동으로 처리해주는 작업은 다음과 같습니다.

| 단계 | 작업 |
|-----|------|
| ① | NSX에 Segment 생성 (Overlay 또는 VLAN) |
| ② | 해당 Segment를 **VPC의 Network Profile**에 등록 |
| ③ | Segment에 **Capability Tag** 부여 (조직/VPC 식별용) |
| ④ | Portal에 Segment 자원 카드로 등록 |

이 4단계는 현재 운영자가 일일이 손으로 하는 작업으로, Segment 카탈로그가 도입되면 한 번의 결재로 자동 수행됩니다.

### 4.5 VPC와 Segment의 관계

```
조직(계열사)
   │
   ├─ VPC #1 ─┬─ Segment(서브넷) A ─ VM, GPU VM ...
   │         ├─ Segment(서브넷) B ─ VM ...
   │         └─ Segment(서브넷) C ─ VM ...
   │
   └─ VPC #2 ─┬─ Segment(서브넷) D ─ VM ...
             └─ Segment(서브넷) E ─ VM ...
```

- **한 조직은 여러 개의 VPC**를 가질 수 있음
- **한 VPC 안에는 여러 Segment(서브넷)** 가 존재
- **VM/GPU VM은 Segment에 연결**되어 IP를 받음
- **Segment를 만들 때는 반드시 소속 VPC를 지정**해야 함 (VPC 없이 Segment만 만들 수 없음)

---

## 5. 사용자 시나리오

### 5.1 시나리오 A — 신규 계열사 온보딩 (VPC 신규 생성)

**상황**: 새로운 계열사 'ABC주식회사'가 P-Cloud를 신규 도입함.

**기존 (As-Is)**:
1. 클라우드 운영자가 NSX 콘솔 접속
2. Tier-1 Gateway 수동 생성 (이름 규칙 직접 기억해서 입력)
3. Aria Automation 콘솔에서 Network Profile 수동 생성
4. 두 자원의 연결을 직접 매핑
5. 운영자만 결과를 알 수 있음
- 소요시간: **30분 ~ 1시간 / 휴먼 에러 가능성 존재**

**개선 후 (To-Be)**:
1. 계열사 관리자가 Portal 접속 → "VPC 신청" 카탈로그 선택
2. 조직코드, VPC 이름, 요청사유 입력 → 결재 상신
3. 결재 승인 시 자동으로 Tier-1 Gateway + Network Profile 생성
4. Portal에 VPC 자원 카드 등장 (조직 자원 화면에서 즉시 확인 가능)
- 소요시간: **2~3분(자동) / 표준 명명 규칙 자동 적용**

### 5.2 시나리오 B — 신규 망(서브넷) 추가 (Segment 신규 생성)

**상황**: 계열사 A가 새로운 서비스를 위한 망(예: DB망)을 신규로 신청함.

**기존 (As-Is)**:
1. 사용자가 운영자에게 망 추가 요청 (메일/티켓)
2. 운영자가 NSX 콘솔에서 Overlay 또는 VLAN Segment 수동 생성 (CIDR, 게이트웨이 입력)
3. 운영자가 Aria Automation에서 해당 Segment를 Network Profile에 등록
4. 운영자가 Capability Tag를 수동 부여
5. 사용자에게 완료 통보
- 소요시간: **수십 분 ~ 1시간 / 단계별 휴먼 에러 가능**

**개선 후 (To-Be)**:
1. 사용자가 Portal에서 "Segment 신청" 카탈로그 선택
2. 소속 VPC 드롭다운 선택, Segment 명, 용도(서비스/DB/관리), CIDR 정책, 요청사유 입력 → 결재
3. 승인 시 자동으로 ① NSX Segment 생성 → ② Network Profile에 등록 → ③ Capability Tag 부여 → ④ Portal에 자원 등록
4. VM 신청 화면에서 즉시 해당 Segment를 선택 가능
- 소요시간: **3~5분(자동)**

### 5.3 시나리오 C — 기존 Tier-1 / Segment 흡수(Import)

**상황**: 마이그레이션 과정에서 이미 NSX에 만들어둔 Tier-1과 Segment를 P-Cloud Portal 관리 대상으로 흡수해야 함.

**개선 후 (To-Be)**:
1. 운영자가 Portal에서 "VPC 신청" → **Import 모드** 체크 → 기존 Tier-1 경로 입력
2. 이어서 "Segment 신청" → **Import 모드** 체크 → 기존 Segment 경로 입력 (소속 VPC 선택)
3. 시스템이 NSX에서 자원 존재 확인 → Portal 자원으로 등록 + Network Profile에 등록 + Capability Tag 부여
4. 단, **삭제 시 NSX 자원은 보존** (외부에서 가져온 자원이므로)

### 5.4 시나리오 D — Segment 삭제

**상황**: 더 이상 사용하지 않는 망을 정리 요청.

**개선 후 (To-Be)**:
1. 사용자/운영자가 Portal에서 해당 Segment → "삭제" 클릭
2. 시스템이 자동으로 **Segment 위에 떠 있는 VM 존재 여부 검증**
   - VM이 남아 있으면 → ❌ 삭제 차단 + 안내 메시지
   - VM이 모두 정리됨 → ✅ NSX Segment 삭제 + Network Profile에서 등록 해제 + Portal 자원 카드 제거
3. Import한 Segment는 **NSX Segment를 보존하고 Portal 등록만 해제**

### 5.5 시나리오 E — VPC 삭제

**상황**: 계열사 A가 P-Cloud에서 철수하면서 VPC 정리 요청.

**개선 후 (To-Be)**:
1. 운영자/관리자가 Portal에서 해당 VPC → "삭제" 클릭
2. 시스템이 자동으로 **연결된 Segment 존재 여부 검증**
   - Segment가 남아 있으면 → ❌ 삭제 차단 + 안내 메시지 ("먼저 Segment부터 삭제하세요")
   - Segment가 모두 정리됨 → ✅ Tier-1 + Network Profile 자동 삭제
3. Import 모드로 들어왔던 VPC는 **Tier-1을 NSX에 그대로 남기고 Portal 등록만 해제**

---

## 6. 시스템 구성도

### 6.1 결재-자동화 흐름 (VPC / Segment 공통)

```
┌──────────────────┐  ① VPC / Segment 신청  ┌──────────────────┐
│   사용자/관리자   │ ──────────────────────▶│   P-Cloud Portal │
└──────────────────┘                        └─────────┬────────┘
                                                      │ ② 결재 프로세스
                                                      ▼
                                            ┌──────────────────┐
                                            │      결재자       │
                                            └─────────┬────────┘
                                                      │ ③ 승인
                                                      ▼
                                            ┌──────────────────┐
                                            │  VCF Automation  │
                                            │ (Catalog 요청)   │
                                            └─────────┬────────┘
                                                      │ ④ 자동 실행
   ┌──────────────────────────────────────────────────┼──────────────────────────────────────────┐
   │                                                  │                                          │
   ▼ [Custom.VPC 카탈로그]                            ▼ [Custom.Segment 카탈로그]                 ▼
 ┌────────────────────┐                       ┌─────────────────────────┐                ┌──────────────┐
 │ NSX Tier-1 Gateway │                       │ NSX Segment 생성        │                │  Portal에    │
 │       (생성)       │                       │  + Network Profile 등록 │                │  자원 등록    │
 │ Aria Network       │                       │  + Capability Tag 부여  │                │              │
 │  Profile (생성)    │                       │                         │                │              │
 └────────────────────┘                       └─────────────────────────┘                └──────────────┘
```

### 6.2 Portal — Automation — NSX 역할 분담

| 계층 | 컴포넌트 | 역할 |
|------|---------|------|
| **사용자 접점** | P-Cloud Portal (ClovirONE 2.0) | VPC·Segment 신청 화면 / 결재 / 자원 조회 / 빌링 |
| **자동화 엔진** | VCF Automation (Service Broker) | `Custom.VPC`, `Custom.Segment` 카탈로그 노출, 결재 후 ABX/vRO 워크플로우 실행 |
| **자동화 로직** | ABX Action / vRO Workflow | NSX·Aria API 호출, 자원 간 연결·태깅 관리 |
| **인프라** | NSX-T / Aria Network Profile | 실제 네트워크 라우터(Tier-1), Segment, Network Profile 객체 |

---

## 7. 기능 요구사항

### 7.1 필수 기능 (Must)

#### `Custom.VPC` 카탈로그

| ID | 기능 | 설명 |
|----|------|------|
| V-01 | VPC 신규 생성 | 조직코드 기반으로 Tier-1 + Network Profile 자동 생성 |
| V-02 | VPC Import | 기존 NSX Tier-1을 Portal 관리 자원으로 등록 |
| V-03 | VPC 조회 | Portal에서 조직별 VPC 목록 및 상세 정보 표시 |
| V-04 | VPC 삭제 | 연결 Segment 검증 후 안전하게 삭제 |
| V-05 | VPC 표준 명명 규칙 적용 | `vpc-{조직코드}-{랜덤8자리}`, `netprofile-{조직코드}` |

#### `Custom.Segment` 카탈로그

| ID | 기능 | 설명 |
|----|------|------|
| S-01 | Segment 신규 생성 | 소속 VPC 지정 → NSX Segment(Overlay/VLAN) 생성 |
| S-02 | Network Profile 자동 등록 | 생성된 Segment를 해당 VPC의 Network Profile에 자동 등록 |
| S-03 | Capability Tag 자동 부여 | 조직/VPC 식별 태그를 Segment에 자동 부여 (VM 매칭용) |
| S-04 | Segment Import | 기존 NSX Segment를 Portal 관리 자원으로 등록 |
| S-05 | Segment 조회 | Portal에서 VPC별 Segment 목록 및 IP 사용 현황 표시 |
| S-06 | Segment 삭제 | 연결 VM 존재 여부 검증 후 안전하게 삭제 |
| S-07 | Segment 표준 명명 규칙 적용 | `LS-{조직코드}-{용도}-{IP/서브넷}` 등 (기존 보고서 명명 정책 준용) |

#### 공통

| ID | 기능 | 설명 |
|----|------|------|
| C-01 | 결재 연동 | 기존 P-Cloud 결재 프로세스에 두 카탈로그 모두 통합 |
| C-02 | 자원 계층 무결성 | Segment 생성은 반드시 사전 등록된 VPC 위에서만 가능 |
| C-03 | VM 카탈로그 연동 | 기존 VM/GPU VM 신청 화면에서 본 카탈로그가 등록한 Segment를 즉시 선택 가능 |

### 7.2 선택 기능 (Should / Nice to Have)

| ID | 기능 | 설명 |
|----|------|------|
| O-01 | VPC별 자원 사용량 표시 | VPC에 속한 Segment/VM 수, IP 사용 현황 |
| O-02 | VPC별 방화벽 정책 설정 화면 | NSX Gateway Firewall 정책 관리 (향후 LBaaS와 연계) |
| O-03 | Segment IPAM 연계 | Aria IPAM과 연동하여 IP 대역 자동 할당 |
| O-04 | 변경 이력 로그 | 누가 언제 어떤 VPC/Segment를 만들었는지 감사 로그 |

### 7.3 비기능 요구사항

| 항목 | 요구사항 |
|------|---------|
| 성능 | VPC 생성 ≤ 3분 / Segment 생성 ≤ 5분 (자동화 종료 기준) |
| 안정성 | 자동화 실패 시 NSX·Aria 양측에 **잔존 자원 없이 롤백** |
| 보안 | NSX/Aria 자격증명은 vRO Configuration Element에 암호화 저장 |
| 멀티 테넌시 | 같은 조직의 두 번째 VPC부터는 **기존 Network Profile 재사용** (조직당 1 Profile 원칙) |
| 호환성 | 기존 운영 중인 NSX Tier-1·Segment와 충돌 없이 Import 가능 |
| 일관성 | Segment 생성 시 부모 VPC 부재 또는 Network Profile 부재 시 **차단** (고아 자원 방지) |

---

## 8. 주요 입력 정보 (사용자 화면 기준)

자세한 필드 정의는 별도 설계서를 참조하며, Portal 신청 화면에서 사용자가 입력하는 핵심 항목은 다음과 같습니다.

### 8.1 VPC 신청 화면

| 입력 항목 | 사용자 입력 방식 | 필수 여부 |
|----------|-----------------|----------|
| 조직(계열사) | 드롭다운 (AD 연동된 조직 목록) | 필수 |
| VPC 표시명 | 자유 입력 | 필수 |
| 요청 사유 | 텍스트 영역 | 필수 |
| Cloud Zone(클라우드 영역) | 드롭다운 | 필수 |
| **신규 / Import** | 라디오 버튼 | 필수 |
| Tier-0 Gateway | 드롭다운 (신규 생성 시) | 조건부 |
| Edge Cluster | 드롭다운 (신규 생성 시) | 조건부 |
| 기존 Tier-1 경로 | 드롭다운 (Import 시) | 조건부 |

### 8.2 Segment 신청 화면

| 입력 항목 | 사용자 입력 방식 | 필수 여부 |
|----------|-----------------|----------|
| 소속 VPC | 드롭다운 (조직이 보유한 VPC 목록) | 필수 |
| Segment 표시명 | 자유 입력 | 필수 |
| 용도 (서비스/DB/관리/백업 등) | 드롭다운 | 필수 |
| Segment 유형 | 라디오 버튼 (Overlay / VLAN) | 필수 |
| CIDR (서브넷 대역) | 자유 입력 또는 IPAM 자동 할당 | 필수 |
| Gateway IP | 자유 입력 또는 자동 계산 | 필수 |
| 요청 사유 | 텍스트 영역 | 필수 |
| **신규 / Import** | 라디오 버튼 | 필수 |
| 기존 Segment 경로 | 드롭다운 (Import 시) | 조건부 |

---

## 9. 기대 효과

### 9.1 정량 효과

| 지표 | 현재 (As-Is) | 도입 후 (To-Be) | 개선율 |
|------|-------------|----------------|-------|
| VPC 생성 소요시간 | 30~60분 (수동) | 2~3분 (자동) | **약 95% 단축** |
| Segment 생성 소요시간 | 30~60분 (수동, 4단계 작업) | 3~5분 (자동) | **약 90% 단축** |
| 운영자 개입 횟수 | 5~6회 / 자원당 | 0회 (결재 승인 외) | **100% 자동화** |
| 명명 규칙 위반 | 빈번 발생 | 0건 (시스템 강제) | **휴먼에러 제거** |
| Capability Tag 누락 | 가끔 발생 (VM 신청 장애) | 0건 (자동 부여) | **장애 예방** |
| 잘못된 삭제로 인한 사고 | 잠재 위험 존재 | 자동 검증으로 차단 | **사고 예방** |

### 9.2 정성 효과

- **계열사 사용자 만족도 향상**: "내 조직의 네트워크 자원을 Portal에서 직접 보고, 신청할 수 있다."
- **운영 표준화**: 모든 VPC가 동일한 명명 규칙과 동일한 구성으로 관리됨
- **추적성 확보**: 결재 이력 + 자동화 로그로 완전한 감사 추적 가능
- **확장 기반**: VPC가 자원으로 등록됨에 따라 향후 CaaS, LBaaS, 3rd-party-aaS 카탈로그가 VPC 위에 자연스럽게 얹힐 수 있음

---

## 10. 추진 일정 (안)

| 단계 | 주요 활동 | 산출물 | 일정(예상) |
|------|----------|-------|-----------|
| ① 기획 확정 | 본 기획안 검토·승인 | 확정 기획안 | W1 |
| ② 설계 확정 | VPC / Segment 기술 설계서 검토 | 확정 설계서 (VPC, Segment 각각) | W1~W2 |
| ③ 개발 (VPC) | `Custom.VPC` ABX Action + vRO Workflow + Custom Resource Type 정의 | 코드 / Workflow | W2~W4 |
| ④ 개발 (Segment) | `Custom.Segment` ABX Action + vRO Workflow + Custom Resource Type 정의 | 코드 / Workflow | W3~W5 |
| ⑤ Portal 연동 | VCF Automation 카탈로그 노출, Portal UI 연계 (VPC·Segment 신청 화면) | Portal 화면 | W5~W6 |
| ⑥ 테스트 | 시나리오 A~E 검증, 롤백 테스트, 부하 테스트 | 테스트 결과서 | W6~W7 |
| ⑦ 운영 이관 | 운영자 교육, 운영 매뉴얼 작성 | 운영 매뉴얼 | W7 |
| ⑧ 정식 오픈 | 그룹사 대상 서비스 시작 | 오픈 공지 | W8~ |

---

## 11. 향후 확장 (Roadmap)

본 VPC·Segment 커스텀 리소스를 기반으로 다음과 같은 후속 과제를 추진할 수 있습니다.

1. **VPC Peering** — 계열사 간 안전한 네트워크 연결 카탈로그
2. **VPC/Segment 단위 방화벽 정책 셀프서비스** — NSX Gateway Firewall / Distributed Firewall과 연계
3. **LBaaS** — VPC·Segment 위에 로드밸런서 자동 배포
4. **CaaS(Container as a Service)** — Supervisor Cluster를 VPC에 매핑
5. **Segment IPAM 자동화 고도화** — IP 풀 정의 → Segment 신청 시 자동 할당
6. **VPC·Segment 단위 빌링** — 조직별 네트워크 사용량 기반 과금

---

## 12. 결론

P-Cloud 2.0이 지향하는 **"멀티 테넌트 기반 리소스 분리"** 와 **"NSX-T를 활용한 셀프서비스 자동화"** 를 실현하기 위해서는, **VPC와 Segment를 모두 Portal의 정식 자원으로 만들어 결재·자동화·감사 체계 안으로 끌어오는 작업**이 반드시 필요합니다. VPC만 자동화하고 Segment를 수동으로 운영한다면 사용자가 실제로 체감하는 셀프서비스 가치가 절반으로 줄어들고, VPC를 신청하더라도 "그 안에 망을 만드는 일"은 여전히 운영자에게 요청해야 하기 때문입니다.

본 VPC·Segment 커스텀 리소스 도입을 통해 P-Cloud 2.0은 *"VM은 셀프, 네트워크는 수동"* 이라는 비대칭적 운영을 해소하고, **컴퓨팅과 네트워크 모두 결재 기반 셀프서비스로 통합 운영**할 수 있게 됩니다. 이는 P-Cloud 2.0이 지향하는 "퍼블릭 클라우드 수준의 셀프서비스·자동화 환경"이라는 사업 목적에도 부합합니다.

---

## 부록 A. 용어 정리

| 용어 | 설명 |
|------|------|
| **VPC** | Virtual Private Cloud — 조직 단위로 격리된 가상 네트워크 영역 |
| **Tier-1 Gateway** | NSX-T에서 조직(계열사) 단위 트래픽을 라우팅하는 라우터 |
| **Tier-0 Gateway** | 외부망과 연결되는 상위 라우터 |
| **Segment** | 가상 서브넷 (VM이 IP를 받는 단위) |
| **Network Profile** | Aria Automation이 네트워크 자원을 인식하는 추상화 객체 (Segment 목록과 Capability Tag를 묶어 관리) |
| **Capability Tag** | Automation이 VM과 Segment(네트워크)를 매칭할 때 사용하는 특성 태그. 본 체계에서는 조직/VPC를 식별하는 키 역할 |
| **Custom Resource Type** | VCF Automation에서 사용자 정의 자원을 카탈로그로 만드는 메커니즘 |
| **ABX** | Aria Automation의 코드 기반 자동화 액션 (Python/Node.js) |
| **vRO** | vRealize Orchestrator — 워크플로우 기반 자동화 엔진 |
| **IPAM** | IP Address Management — IP 자동 할당·관리 |
| **Tenant** | 테넌트, 본 시스템에서는 **계열사(조직)** 와 동일 개념 |
