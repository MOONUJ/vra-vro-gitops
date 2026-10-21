# -*- coding: utf-8 -*-
"""인스턴스 정의와 비밀값을 검증하고 도구별 로컬 입력을 생성한다."""

import argparse
import sys

if __package__:
    from .config_loader import ConfigError, REPOSITORY_ROOT, load_source_config, normalize_runtime_config
else:
    from config_loader import ConfigError, REPOSITORY_ROOT, load_source_config, normalize_runtime_config


def main():
    parser = argparse.ArgumentParser(description="VCF Automation 인스턴스 설정 도구")
    parser.add_argument("action", choices=["validate"])
    parser.add_argument("--instance", default=str(REPOSITORY_ROOT / "instance.yaml"))
    parser.add_argument("--secrets", default=str(REPOSITORY_ROOT / "secrets.json"))
    args = parser.parse_args()
    try:
        config = load_source_config(args.instance, args.secrets)
        runtime = normalize_runtime_config(config)
        print(
            "설정 검증 완료: "
            f"environment={config['environment']['name']}, "
            f"vcf_url={runtime['vcf_url']}, vro_url={runtime['vro_url']}, "
            f"vro_discovery={runtime['vro_discovery_mode']}"
        )
    except (ConfigError, OSError) as exc:
        print(f"설정 오류: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
