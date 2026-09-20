# [TICKET-015] Pilot Apply Runner RBAC와 승인자 분리 증거

- **상태:** `TODO`
- **우선순위:** `High`
- **단계:** 7 - 제한적 자동화 Pilot 운영 통제
- **관련 영역:** VCF Automation 권한, credential, 승인 로그, CI runner
- **선행 티켓:** TICKET-012 기능·복구 Pilot

---

## 목적

관찰·plan 생성 Agent, 승인자와 원격 apply runner를 분리하고 apply credential이 Pilot 대상에 필요한 최소 권한만 갖는다는 증거를 남긴다. 이 티켓 전에는 production 확대를 승인하지 않는다.

## 작업

1. observe/plan 역할과 approve/apply 역할의 책임자를 분리한다.
2. read-only observer와 제한된 apply runner credential을 별도로 발급한다.
3. Automation/vRO API와 대상 project/content 범위별 필수 권한을 문서화한다.
4. 과도한 권한과 production 접근을 제거한다.
5. 승인 로그가 exact plan hash, 대상, 만료와 실행 주체를 연결하도록 한다.
6. 제한된 credential로 개발환경 단일 dry-run 또는 승인된 저위험 변경을 재검증한다.

## 완료 기준

- [ ] observer와 apply runner가 서로 다른 credential을 사용해야 함.
- [ ] 승인자가 plan 생성/실행 주체와 분리되어야 함.
- [ ] apply runner에 production 접근 권한이 없어야 함.
- [ ] 허용 API·project·content 범위와 거부 검증 증거가 있어야 함.
- [ ] exact approval과 실행 주체가 journal/audit log로 연결되어야 함.
