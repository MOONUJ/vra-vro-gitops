# Loop 구현 계약

reconciliation loop을 설계하거나 구현할 때만 이 문서를 읽는다.

## 실행 대상 확인

Loop 실행 전 다음 조건을 모두 만족해야 한다.

- Loop 파일명이 `.example.yaml`로 끝나지 않는다.
- `instance.yaml`이 Git에 추적되고 설정 검증을 통과한다.
- `spec.enabled`가 `true`이고 `spec.repositoryMode`가 `instance`이다.
- `spec.instanceRef`가 `instance.yaml`의 `metadata.name`과 일치한다.

조건을 만족하지 않으면 observe도 실행하지 않고 설정 오류로 중단한다. `instance.local.yaml`이나 untracked `instance.yaml`을 Scheduled Loop의 대상으로 사용하지 않는다.

## 필수 상태 전이

`observe → plan → validate → await-approval → apply → verify → record`

정상 상태가 관찰되면 plan 없이 종료할 수 있다. 검증 실패, 거절되거나 만료된 승인, 재시도할 수 없는 오류, 반복되는 수렴 실패에서는 추가 변경을 적용하지 않고 중단한다.

## Plan 식별 조건

변경 plan의 승인은 다음 정보에 결합되어야 한다.

- 환경과 endpoint 식별자
- 수명주기 단계와 제품 집합
- 작업과 리소스 집합
- 원하는 상태 또는 artifact hash
- 생성 및 만료 시각

승인 후 결합된 값이 하나라도 바뀌면 승인을 무효화하고 새 plan을 만든다.

## 재시도 정책

- 일시적 네트워크, throttling, 서버 가용성 오류만 재시도한다.
- 인증, 권한, 스키마, 정책 또는 유효하지 않은 plan 오류는 재시도하지 않는다.
- 시도 횟수와 전체 경과 시간을 제한한다.
- 결과가 불명확한 작업 뒤에는 매 재시도 전에 다시 관찰한다.
- 설정된 수렴 한도를 지난 뒤에도 같은 drift가 남으면 중단한다.

## 증거

관찰 hash, plan, 승인 식별자, 실행 명령 또는 API 작업, 시각, 민감정보를 제거한 결과와 적용 후 검증을 기록한다. refresh token이나 비밀값은 증거에 저장하지 않는다.
