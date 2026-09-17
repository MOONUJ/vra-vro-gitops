# [TICKET-001] 실제 인스턴스 저장소 Pilot과 Native Apply 검증

- **상태:** `TODO`
- **우선순위:** `High`
- **관련 영역:** 별도 인스턴스 저장소, `instance.yaml`, `infrastructure/`, `tooling/vcf/`

---

## 목적

현재 템플릿 저장소에서 완료한 discovery, adopt, status와 불변 plan 검증을 별도의 실제 인스턴스 저장소로 이전합니다. 추적된 `instance.yaml`과 검토된 인프라 baseline을 만든 뒤, 영향이 작은 리소스 한 건으로 `plan → approval → apply → verify` 전체 흐름을 검증합니다.

템플릿 저장소에서는 계속 원격 mutation을 실행하지 않습니다.

## 선행 조건

1. 현재 템플릿의 native 인프라 변경을 검토·커밋하고 재사용 가능한 기준 버전을 정합니다.
2. 실제 인스턴스 저장소의 이름과 생성 경로 또는 Git 원격을 정합니다.
3. 시험 대상 Automation과 저위험 변경 리소스를 명시합니다.
4. `secrets.json`, plan, apply 결과와 cache가 Git에서 제외되는지 확인합니다.

## 작업

1. 템플릿으로 별도 인스턴스 저장소를 생성합니다.
2. bootstrap으로 실제 `instance.yaml`과 로컬 `secrets.json`을 만들고 설정 검증을 통과시킵니다.
3. `import/*` 브랜치에서 기존 Day-0 리소스를 `infrastructure/`에 adopt합니다.
4. 16개 baseline manifest의 관리 범위, `metadata.remoteId`와 원하는 상태를 검토합니다.
5. `instance.yaml`과 baseline manifest를 Git에 추적한 뒤 저장소 모드가 `instance`인지 확인합니다.
6. `validate`, `status`, `plan`을 실행해 초기 plan이 변경 작업 0건인지 확인합니다.
7. Project 또는 지원되는 Profile 한 건에 되돌릴 수 있는 저위험 변경을 준비합니다.
8. 새 plan의 대상, before/after, 만료 시각과 hash를 검토합니다.
9. 사용자가 정확한 plan hash와 대상을 별도로 승인한 경우에만 `apply`합니다.
10. apply 결과가 `VERIFIED`인지 확인하고, 실패 시 추가 mutation 없이 결과를 보존합니다.

## 검증 기준

- [ ] 템플릿 저장소와 실제 인스턴스 데이터가 서로 다른 저장소에 있어야 함.
- [ ] `instance.yaml`과 `infrastructure/`는 추적되고 `secrets.json`, `.gitops/`는 제외되어야 함.
- [ ] 초기 baseline의 `status`와 `plan`이 변경 작업 0건을 보고해야 함.
- [ ] apply 전 plan hash, 대상 인스턴스, before/after와 만료 시각이 검토되어야 함.
- [ ] 명시적 승인 없이는 원격 mutation이 실행되지 않아야 함.
- [ ] 승인된 단일 변경 후 원격 재조회 결과가 `VERIFIED`여야 함.
- [ ] 실행 결과와 복구 방법을 기록하고 템플릿 `main`에는 실제 인스턴스 상태가 남지 않아야 함.
