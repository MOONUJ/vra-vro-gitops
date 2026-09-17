# 인프라 manifest

생성된 인스턴스 저장소에서 Git이 관리하는 VCF Automation Day-0 리소스를 종류별 YAML로 보관합니다.

```text
infrastructure/
├── cloud-accounts/
├── cloud-zones/
├── network-profiles/
├── storage-profiles/
├── image-profiles/
└── projects/
```

템플릿에는 실제 리소스 manifest를 넣지 않습니다. `tooling/vcf/cli.py adopt`가 원격 리소스의
원하는 상태와 `metadata.remoteId`를 함께 기록합니다. 파일 삭제는 원격 삭제 승인을 의미하지 않습니다.

현재 저장소 실행 모드는 `python3 tooling/vcf/cli.py context`로 확인할 수 있습니다. 템플릿 저장소의 연동 시험에서는 CLI가 `instance.local.yaml`, `secrets.local.json`, `.gitops/infrastructure-test/` 경계를 강제합니다.

선택 채택에는 `adopt --resource Kind:remote-id`를 사용합니다. 전체 채택은 의도하지 않은 소유권 확대를 막기 위해 인자 생략이 아니라 명시적인 `adopt --all`을 요구하며, `--dry-run`으로 생성·건너뜀·충돌 수를 먼저 확인할 수 있습니다.
