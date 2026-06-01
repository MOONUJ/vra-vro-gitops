# Custom.VPC 설계서

> **버전:** 1.0  
> **작성일:** 2026-04-21  
> **대상 환경:** VCF Automation (Aria Automation) + NSX-T  

---

## 1. 개요

### 1.1 목적

VCF Automation의 Custom Resource Type으로 **VPC(Virtual Private Cloud)** 를 정의한다.  
VPC의 실체는 NSX-T **Tier-1 Gateway**이며, Tenant(조직) 단위로 생성·관리된다.  
Aria Automation **Network Profile**은 Tenant(조직) 단위로 하나만 존재하며, Tenant의 첫 번째 VPC 생성(또는 Import) 시에만 생성된다. 이후 동일 Tenant의 VPC는 기존 Network Profile을 공유한다.

### 1.2 적용 범위

| 대상 | 내용 |
|------|------|
| Custom Resource Type | `Custom.VPC` |
| NSX 오브젝트 | Tier-1 Gateway |
| Aria 오브젝트 | Network Profile |
| Tenant 구분 | `organizationCode` 기반 |
| 지원 케이스 | 신규 생성 (Case A) / 기존 Tier-1 Import (Case B) |

---

## 2. 아키텍처

### 2.1 전체 흐름

```
사용자 요청 (Catalog)
    │
    ▼
ABX: Custom.VPC.create
    ├─ [NSX 작업] vRO Workflow 호출 (runOrchWorkflow)
    │       └─ com.gvp/NsxManager(hostname)
    │               ├─ Case A: PUT /policy/api/v1/infra/tier-1s/{id}  (신규)
    │               └─ Case B: GET /policy/api/v1/infra/tier-1s/{id}  (import)
    │
    └─ [Aria 작업] AaManager 직접 호출
            ├─ GET /iaas/api/zones/{cloudZoneId}         → cloudAccountId
            ├─ GET /iaas/api/cloud-accounts/{id}         → nsxAccountId
            ├─ GET /iaas/api/cloud-accounts-nsx-t/{id}  → hostname
            ├─ GET /iaas/api/network-profiles            → 기존 Tenant Network Profile 조회
            └─ POST /iaas/api/network-profiles           → networkProfileId (Tenant 첫 VPC인 경우에만)
```

### 2.2 NSX Hostname 조회 체인

```
cloudZoneId
  → /iaas/api/zones/{cloudZoneId}
      .cloudAccountId
  → /iaas/api/cloud-accounts/{cloudAccountId}
      .linkedCloudAccountIds[0]  (NSX-T Account ID)
  → /iaas/api/cloud-accounts-nsx-t/{nsxAccountId}
      .hostname
  → NsxManager(hostname)
      ConfManager.load("GVP/Endpoint/{hostname}")
      → { hostname, username, password }
```

### 2.3 신규 생성 vs Import 분기

| 구분 | Case A (신규) | Case B (Import) |
|------|--------------|-----------------|
| `importMode` | `false` | `true` |
| NSX 작업 | `PUT /infra/tier-1s/{id}` 로 Tier-1 생성 | `GET /infra/tier-1s/{id}` 로 존재 확인 |
| Tier-1 이름 규칙 | `vpc-{orgCode}-{random8}` | 기존 Tier-1 이름 그대로 사용 |
| Delete 시 Tier-1 처리 | **삭제** | **삭제 안 함** (import한 것이므로) |
| Network Profile | Tenant 첫 VPC면 생성, 아니면 기존 재사용 | Tenant 첫 VPC면 생성, 아니면 기존 재사용 |

---

## 3. Custom Resource Type: `Custom.VPC`

### 3.1 Properties 정의

#### Input Properties (사용자 입력)

| 필드명 | 타입 | Required | 설명 |
|--------|------|----------|------|
| `organizationCode` | string | ✅ | Tenant 식별자 (조직코드) |
| `displayName` | string | ✅ | VPC 표시명 |
| `requestMessage` | string | ✅ | 요청 사유 |
| `cloudZoneId` | string | ✅ | Placement Zone ID (Cloud Zone) |
| `importMode` | boolean | ✅ | `false`=신규 생성, `true`=기존 import |
| `tier0Path` | string | Case A | 연결할 Tier-0 Gateway NSX path |
| `edgeClusterPath` | string | Case A | Edge Cluster NSX path |
| `existingTier1Path` | string | Case B | Import할 기존 Tier-1 full path |

#### Computed Properties (시스템 자동 설정)

| 필드명 | 타입 | 설명 |
|--------|------|------|
| `id` | string | Tier-1 Gateway ID (Custom Resource 식별자) |
| `name` | string | Tier-1 Gateway 이름 |
| `tier1Path` | string | NSX Tier-1 full path (e.g. `/infra/tier-1s/vpc-abc-12345678`) |
| `networkProfileId` | string | Aria Automation Network Profile ID |
| `vpcProfile` | string | Segment 연결용 profileLink (e.g. `/provisioning/uerp/resources/network-profiles/{id}`) |
| `nsxAccountId` | string | 연결된 NSX-T Cloud Account ID |
| `nsxHostname` | string | NSX Manager hostname |

### 3.2 Main Actions

| Action | 타입 | 설명 |
|--------|------|------|
| `create` | ABX Python | VPC 생성 (Tier-1 + Network Profile) |
| `read` | ABX Python | inputs bypass |
| `delete` | ABX Python | 연결 Segment 존재 시 삭제 차단, Case A만 Tier-1 삭제, Tenant 마지막 VPC면 Network Profile 삭제 |

---

## 4. vRO Workflow: `Custom.VPC.nsxTier1Manager`

### 4.1 목적

ABX에서 호출되어 NSX Manager에 직접 API를 호출하는 레이어.  
`com.gvp/NsxManager` 액션을 통해 NSX REST API를 실행한다.

### 4.2 Input Parameters

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| `cloudZoneId` | string | ✅ | Cloud Zone ID → NSX hostname 조회용 |
| `importMode` | boolean | ✅ | `false`=신규, `true`=import |
| `organizationCode` | string | ✅ | Tier-1 이름 생성에 사용 |
| `tier0Path` | string | Case A | Tier-0 Gateway path |
| `edgeClusterPath` | string | Case A | Edge Cluster path |
| `existingTier1Path` | string | Case B | 기존 Tier-1 path |

### 4.3 Output Parameters

| 파라미터 | 타입 | 설명 |
|---------|------|------|
| `tier1Id` | string | Tier-1 Gateway ID |
| `tier1Path` | string | Tier-1 full path |
| `tier1Name` | string | Tier-1 이름 |
| `nsxHostname` | string | 사용된 NSX Manager hostname |

### 4.4 처리 로직

```
1. AaManager로 CloudZone → Cloud Account → NSX-T Account → hostname 조회
2. NsxManager(hostname) 초기화

3. if importMode == false (Case A):
   - randomStr = 8자리 랜덤 영숫자 생성
   - tier1Id = "vpc-" + organizationCode + "-" + randomStr
   - PUT /policy/api/v1/infra/tier-1s/{tier1Id}
       {
         "display_name": tier1Id,
         "tier0_path": tier0Path,
         "edge_cluster_path": edgeClusterPath,
         "route_advertisement_types": ["TIER1_STATIC_ROUTES", "TIER1_CONNECTED"],
         "ha_mode": "ACTIVE_STANDBY"
       }
   - GET /policy/api/v1/infra/tier-1s/{tier1Id} 로 생성 확인

4. if importMode == true (Case B):
   - tier1Id = existingTier1Path에서 마지막 segment 추출
   - tier1 = GET /policy/api/v1/infra/tier-1s/{tier1Id}
   - tier1이 없으면 예외 throw

5. Output 반환: { tier1Id, tier1Path, tier1Name, nsxHostname }
```

---

## 5. ABX Actions

### 5.1 `Custom.VPC.create`

**Runtime:** Python 3.11  
**Provider:** on-prem  

#### 처리 순서

```
1. AaManager 초기화

2. vRO Workflow 호출 (runOrchWorkflow)
   - Workflow: Custom.VPC.nsxTier1Manager
   - Input: cloudZoneId, importMode, organizationCode, tier0Path, edgeClusterPath, existingTier1Path
   - Output: tier1Id, tier1Path, tier1Name, nsxHostname

3. NSX Account 정보 조회
   - GET /iaas/api/zones/{cloudZoneId} → cloudAccountId, regionId
   - GET /iaas/api/cloud-accounts/{cloudAccountId} → linkedCloudAccountIds[0] (nsxAccountId)

4. Network Profile 조회 또는 생성 (Tenant 기준)
   - GET /iaas/api/network-profiles?$filter=name eq 'netprofile-{organizationCode}'
   - 조회 결과가 있으면 → 기존 networkProfileId 재사용
   - 조회 결과가 없으면 (Tenant 첫 번째 VPC) → 신규 생성
     - POST /iaas/api/network-profiles
         {
           "name": "netprofile-{organizationCode}",
           "regionId": regionId,
           "isolationType": "PRIVATE_PEERED"
         }
   - networkProfileId 추출

5. vpcProfile 생성
   - "/provisioning/uerp/resources/network-profiles/{networkProfileId}"

6. Output 반환 (inputs에 computed fields 추가)
```

### 5.2 `Custom.VPC.read`

```python
def handler(context, inputs):
    return inputs  # bypass
```

### 5.3 `Custom.VPC.delete`

#### 처리 순서

```
1. AaManager 초기화

2. 연결 Segment 존재 여부 확인
   - GET /iaas/api/network-profiles/{networkProfileId}
       → fabricNetworkIds 목록 확인
   - fabricNetworkIds가 비어있지 않으면 → 예외 throw
       ("연결된 Segment가 존재하여 VPC를 삭제할 수 없습니다.")

3. if importMode == false (Case A만):
   - vRO Workflow 호출로 Tier-1 삭제
   - DELETE /policy/api/v1/infra/tier-1s/{tier1Id}

4. if importMode == true (Case B):
   - Tier-1은 삭제하지 않음 (import한 외부 리소스)

5. Network Profile 삭제
   - DELETE /iaas/api/network-profiles/{networkProfileId}
```

---

## 6. Naming Convention

| 리소스 | 규칙 | 예시 |
|--------|------|------|
| Tier-1 Gateway (신규) | `vpc-{orgCode}-{random8}` | `vpc-posco-a3f8b21c` |
| Network Profile | `netprofile-{orgCode}` | `netprofile-posco` |
| vpcProfile link | `/provisioning/uerp/resources/network-profiles/{id}` | - |

---

## 7. 연동 관계

```
Custom.VPC (Custom Resource)
    │
    ├─ 생성 → NSX Tier-1 Gateway
    ├─ 생성 → Aria Network Profile
    │
    └─ 참조됨 ← Custom.Segment (Cloud.NSX.Network)
                    └─ vpc property = vpcProfile
```

- `Custom.Project.create` 에서 VPC Catalog를 자동 요청할 때 `vpcProfile` 값을 Segment에 전달
- Segment는 `vpcProfile`로 Network Profile을 찾아 배포됨

---

## 8. 구현 파일 목록

| 파일 | 타입 | 위치 |
|------|------|------|
| `Custom.VPC.create` | ABX Python Action | VCF Automation |
| `Custom.VPC.read` | ABX Python Action | VCF Automation |
| `Custom.VPC.delete` | ABX Python Action | VCF Automation |
| `Custom.VPC.nsxTier1Manager` | vRO Workflow | vRO |
| `Custom.VPC` | Custom Resource Type | VCF Automation |

---

## 9. 의존성

| 의존 항목 | 설명 |
|----------|------|
| `com.gvp/NsxManager` | vRO Action - NSX REST API 클라이언트 |
| `com.gvp/AaManager` | vRO Action - Aria Automation REST API 클라이언트 |
| `com.gvp/ConfManager` | vRO Action - Configuration Element 로더 |
| `GVP/Endpoint/{hostname}` | vRO Configuration Element - NSX 자격증명 |
| `/iaas/api/zones` | Aria API - Cloud Zone 정보 |
| `/iaas/api/cloud-accounts-nsx-t` | Aria API - NSX-T Cloud Account 정보 |
| `/iaas/api/network-profiles` | Aria API - Network Profile 관리 |
