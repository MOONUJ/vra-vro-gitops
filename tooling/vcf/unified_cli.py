# -*- coding: utf-8 -*-
"""사람, CI와 AI Agent가 공유하는 단일 vcf-gitops entry point."""

from __future__ import annotations

import argparse


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="vcf-gitops", description="VCF Automation GitOps CLI")
    parser.add_argument(
        "command",
        choices=[
            "context",
            "infrastructure",
            "content",
            "release",
            "schema",
            "identity",
            "template-update",
            "observe-loop",
        ],
    )
    args, remaining = parser.parse_known_args(argv)
    if args.command in {"context", "infrastructure"}:
        from cli import main as infrastructure_main

        return infrastructure_main((["context"] if args.command == "context" else []) + remaining)
    if args.command == "content":
        from vcf_sync import main as content_main

        return content_main(remaining)
    if args.command == "release":
        from vcf_release import main as release_main

        return release_main(remaining)
    if args.command == "schema":
        from schema_validation import main as schema_main

        return schema_main(remaining)
    if args.command == "identity":
        from content_identity import main as identity_main

        return identity_main(remaining)
    if args.command == "template-update":
        from template_update import main as template_update_main

        return template_update_main(remaining)
    if args.command == "observe-loop":
        from observe_loop import main as observe_loop_main

        return observe_loop_main(remaining)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
