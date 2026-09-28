# [TICKET-012] 개발환경 Day-2 승인 기반 Reconcile Pilot

- **상태:** `LOCAL_MANUAL_PILOT_COMPLETE`
- **우선순위:** `Medium`
- **단계:** 7 - 제한적 자동화 Pilot
- **관련 영역:** 별도 개발 인스턴스 저장소, Day-2 콘텐츠, Loop
- **선행 작업:** 기능 구현과 복구 검증 완료

---

## 목적

실제 개발 Automation 인스턴스에서 영향이 작고 되돌릴 수 있는 Day-2 콘텐츠 한 건으로 `observe → plan → validate → await-approval → apply → verify → record` 전체 흐름을 검증한다. production과 Day-0 자동 apply는 계속 제외한다.

## 선행 조건

1. 별도 인스턴스 저장소의 baseline과 `instance.yaml`이 검토·커밋되어 있어야 한다.
2. 지원되는 Day-2 리소스와 되돌리기 방법을 명시해야 한다.
3. 로컬 실행자가 exact plan hash와 대상, 만료와 복구 방법을 직접 검토해야 한다.
4. Pilot 중단 조건과 연락 대상을 정해야 한다.

## 작업

1. observe-only loop를 최소 두 주기 실행해 안정적인 baseline hash를 확인한다.
2. Resource Action, 비활성 Subscription 또는 테스트 Workflow 중 저위험 대상 하나를 선택한다.
3. Agent가 별도 브랜치에서 변경, 테스트, plan과 위험 요약을 만든다.
4. 로컬 실행자가 exact plan hash와 대상을 명시적으로 승인한다.
5. 같은 로컬 credential로 승인된 plan만 apply한다.
6. 원격 재조회와 기능 테스트로 결과를 검증한다.
7. 동일 release 또는 역변경 plan으로 복구 절차를 시험한다.
8. 실행 시간, 오류, 수동 개입, journal과 개선점을 Pilot 보고서에 기록한다.

## 범위 밖

- production 인스턴스
- Day-0 인프라 자동 apply
- 여러 lifecycle 또는 제품을 섞은 변경
- 승인 없는 자동 mutation

## 완료 기준

- [x] 승인 전 원격 mutation이 없어야 함.
- [x] plan과 승인에 instance, lifecycle, product, 작업, hash와 만료가 결합되어야 함.
- [x] 로컬 수동 운영에서는 연결된 개발 인스턴스 credential만 사용하고 production endpoint를 대상으로 하지 않아야 함.
- [x] 적용 후 상태와 기능이 모두 검증되어야 함.
- [x] 실패 또는 비수렴 시 추가 mutation 없이 중단되어야 함.
- [x] 복구 절차와 Pilot 결과가 문서화되어야 함.
- [x] production 확대 여부를 별도 의사결정으로 남겨야 함.

## 실제 연동 검증

실제 endpoint와 credential은 별도 인스턴스 저장소에서만 사용한다. 템플릿 저장소에는 plan, journal, release, secret과 실제 콘텐츠를 커밋하지 않는다.

## Pilot 진행 기록

- observe-only Loop를 세 주기 실행했고 동일 observation hash와 세 번째 반복 drift escalation을 확인했다.
- 콘텐츠 observation은 완전했지만 Automation 콘텐츠 41개가 `REMOTE_ONLY`여서 승인된 baseline으로 간주할 수 없다.
- pull preview 도중 기존 package mutation 결함을 발견해 즉시 중단하고 read-only 동작으로 수정했다.
- 현재 인스턴스 설정의 예시 vRO package 이름을 실제 고유 이름으로 결정해야 한다.
- package 이름 수정, pull preview 수렴, baseline accept·검토·커밋 후에만 저위험 Day-2 대상을 고르고 새 content plan을 만든다.
- 실제 package 이름을 반영하고 수정된 read-only pull preview가 수렴하는 것을 확인했다. 51개 신규 파일로 구성된 exact preview의 승인과 accept 후 검토가 남았다.
- exact preview 승인 후 51개 파일을 accept·커밋했고 재관찰에서 Automation 콘텐츠 41개가 모두 `IN_SYNC`였다.
- Day-2 대상은 이미 비활성화된 `Compute Power Init` Subscription의 description 단일 UPDATE로 제한했다. 변경 commit과 instance/lifecycle/product/operation/observation/content hash/만료가 결합된 content plan을 생성했으며 exact hash 승인을 기다린다.
- exact content plan 승인 후 단일 UPDATE와 원격 검증이 `VERIFIED`였다. Subscription은 계속 `disabled: true`, 동일 event topic과 blocking 설정을 유지했고 observe-only Loop는 전체 상태를 `IN_SYNC`로 기록했다.
- 원래 description으로 되돌리는 별도 commit과 2시간 유효한 단일 UPDATE rollback plan을 생성했으며 exact hash 승인을 기다린다. 복구가 검증되기 전에는 production 확대를 승인하지 않는다.
- 만료된 rollback plan은 실행하지 않고 재관찰 후 새 exact plan 승인을 받았다. 복구 UPDATE와 재조회가 `VERIFIED`였고 원래 description, `disabled: true`, event topic과 blocking 설정이 유지됐다.
- 복구 후 Catalog Source의 import 시각 때문에 발생한 false drift를 정규화하고 전체 Loop가 다시 `IN_SYNC`임을 확인했다.
- 기능·복구 Pilot은 완료했다. 현재 운영 범위는 로컬 수동 실행이며 하나의 credential로 observe, plan과 승인된 apply를 수행한다.
- CI 자동 apply, 별도 runner credential과 승인자 분리는 현재 Pilot의 완료 조건에서 제외하고 TICKET-015로 유예했다. Production 확대는 별도 의사결정으로 계속 보류한다.
