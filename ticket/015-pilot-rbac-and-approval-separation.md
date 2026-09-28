# [TICKET-015] CI Apply Runner RBAC와 승인자 분리

- **상태:** `DEFERRED_UNTIL_CI_APPLY`
- **우선순위:** `Medium`
- **단계:** 7 - 제한적 자동화 Pilot 운영 통제
- **관련 영역:** VCF Automation 권한, credential, 승인 로그, CI runner
- **선행 티켓:** TICKET-012 기능·복구 Pilot

---

## 목적

GitHub Actions 같은 CI runner가 `main` 변경을 자동 적용하는 단계를 도입할 때 관찰·plan 생성 주체, 승인자와 원격 apply runner를 분리하고 apply credential이 대상에 필요한 최소 권한만 갖는다는 증거를 남긴다.

현재는 로컬 수동 운영을 우선하므로 CLI에 별도 credential과 identity 입력을 강제하지 않는다. 이 티켓은 자동 적용을 실제로 도입하기로 결정한 시점에 재개한다.

## 작업

1. CI 자동 apply의 trigger, 승인 방식과 적용 범위를 먼저 결정한다.
2. observe/plan 역할과 approve/apply 역할의 책임자를 분리한다.
3. read-only observer와 제한된 apply runner credential을 별도로 발급한다.
4. Automation/vRO API와 대상 project/content 범위별 필수 권한을 문서화한다.
5. 과도한 권한과 production 접근을 제거한다.
6. 승인 로그가 exact plan hash, 대상, 만료와 실행 주체를 연결하도록 한다.
7. 제한된 credential로 개발환경 단일 dry-run 또는 승인된 저위험 변경을 재검증한다.

## 완료 기준

- [ ] observer와 apply runner가 서로 다른 credential을 사용해야 함.
- [ ] 승인자가 plan 생성/실행 주체와 분리되어야 함.
- [ ] apply runner에 production 접근 권한이 없어야 함.
- [ ] 허용 API·project·content 범위와 거부 검증 증거가 있어야 함.
- [ ] exact approval과 실행 주체가 journal/audit log로 연결되어야 함.

## 진행 기록

- Embedded와 external Orchestrator endpoint를 명시적으로 분리하되, 양쪽 모두 Automation과 같은 identity provider의 OAuth bearer를 사용하도록 제한했다.
- External baseline은 package membership으로 범위를 선택할 수 있고 4종 discovery가 모두 0건이면 `INCOMPLETE`로 중단하는 guard를 추가했다.
- Template 0.3.0 update preview가 기존 인스턴스의 protected `instance.yaml` migration을 탐지하고 설정 반영 전 공통 tooling apply를 차단하도록 했다.
- 로컬 수동 운영을 우선하기로 결정해 `content-apply`의 별도 apply credential, approver와 executor identity 강제는 현재 범위에서 제거했다.
- External Orchestrator도 `secrets.json`의 Automation refresh token을 공통 OAuth bearer로 교환해 사용하며 별도 Basic credential은 두지 않는다.
- CI 자동 apply를 도입할 때 secret manager, runner principal, approval audit와 원격 `403` 증거 설계를 함께 재개한다.
