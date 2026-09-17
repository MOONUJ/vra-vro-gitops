# -*- coding: utf-8 -*-
"""인스턴스 정의와 비밀값을 검증하고 도구별 로컬 입력을 생성한다."""

import argparse
import json
import sys
from pathlib import Path

from config_loader import ConfigError, build_terraform_variables, load_source_config, normalize_runtime_config

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TERRAFORM_OUTPUT = REPOSITORY_ROOT / "foundation" / "automation" / "terraform" / "generated.auto.tfvars.json"


def main():
    parser = argparse.ArgumentParser(description="VCF Automation 인스턴스 설정 도구")
    parser.add_argument("action", choices=["validate", "terraform"])
    parser.add_argument("--instance", default=str(REPOSITORY_ROOT / "instance.yaml"))
    parser.add_argument("--secrets", default=str(REPOSITORY_ROOT / "secrets.json"))
    parser.add_argument("--output", default=str(DEFAULT_TERRAFORM_OUTPUT))
    args = parser.parse_args()
    try:
        config = load_source_config(args.instance, args.secrets)
        runtime = normalize_runtime_config(config)
        terraform_variables = build_terraform_variables(config)
        if args.action == "validate":
            print(f"설정 검증 완료: environment={config['environment']['name']}, vcf_url={runtime['vcf_url']}")
            return
        output_path = Path(args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as output_file:
            json.dump(terraform_variables, output_file, ensure_ascii=False, indent=2)
            output_file.write("\n")
        print(f"Terraform 입력 생성 완료: {output_path}")
    except (ConfigError, OSError) as exc:
        print(f"설정 오류: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
