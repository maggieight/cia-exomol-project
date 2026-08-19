from __future__ import annotations

import argparse
import json
from pathlib import Path

from .build import build_release
from .build_context import BuildContext
from .chandran2025 import convert as convert_chandran2025
from .dong2026 import convert as convert_dong2026
from .finenko2026 import convert as convert_finenko2026
from .inventory import create_inventory, readable_summary, write_inventory
from .ptashnik2011 import convert as convert_ptashnik2011
from .release import publish_release
from .validation import validate_release
from .vitali2026 import convert as convert_vitali2026


CONVERTERS = {
    "ptashnik2011": convert_ptashnik2011,
    "chandran2025": convert_chandran2025,
    "dong2026": convert_dong2026,
    "vitali2026": convert_vitali2026,
    "finenko2026": convert_finenko2026,
}


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""
    parser = argparse.ArgumentParser(prog="cia-pipeline")
    commands = parser.add_subparsers(dest="command", required=True)
    inventory = commands.add_parser(
        "inventory", help="inspect input files and metadata"
    )
    inventory.add_argument("--input", type=Path, required=True)
    inventory.add_argument("--metadata", type=Path, required=True)
    inventory.add_argument("--report", type=Path, required=True)
    inventory.add_argument("--strict", action="store_true")
    inventory.add_argument("--dry-run", action="store_true")
    convert = commands.add_parser(
        "convert", help="convert archived non-HITRAN data into canonical input"
    )
    converters = convert.add_subparsers(dest="converter", required=True)
    for name in CONVERTERS:
        converter = converters.add_parser(name)
        converter.add_argument("--source", type=Path, required=True)
        converter.add_argument("--output", type=Path, required=True)
        converter.add_argument("--metadata", type=Path, required=True)
        if name != "ptashnik2011":
            converter.add_argument("--report", type=Path)
    build = commands.add_parser("build", help="transactionally build a release")
    build.add_argument("--input", type=Path, required=True)
    build.add_argument("--metadata", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--reports", type=Path, default=Path("reports"))
    build.add_argument("--examples", type=Path, default=Path("examples"))
    build.add_argument("--strict", action="store_true", required=True)
    validate = commands.add_parser("validate", help="validate an existing release")
    validate.add_argument("--input", type=Path, required=True)
    validate.add_argument("--metadata", type=Path, required=True)
    validate.add_argument("--output", type=Path, required=True)
    validate.add_argument("--examples", type=Path, default=Path("examples"))
    validate.add_argument("--report", type=Path)
    validate.add_argument("--strict", action="store_true")
    release = commands.add_parser(
        "release", help="back up and atomically publish a validated release"
    )
    release.add_argument("--input", type=Path, required=True)
    release.add_argument("--metadata", type=Path, required=True)
    release.add_argument("--output", type=Path, required=True)
    release.add_argument("--reports", type=Path, default=Path("reports"))
    release.add_argument("--backups", type=Path, default=Path("releases/backups"))
    release.add_argument("--examples", type=Path, default=Path("examples"))
    release.add_argument("--strict", action="store_true", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CIA pipeline CLI."""
    args = build_parser().parse_args(argv)
    if args.command == "inventory":
        report, failed = create_inventory(args.input, args.metadata, args.strict)
        if args.dry_run:
            print(readable_summary(report), end="")
        else:
            write_inventory(report, args.report)
        return int(failed)
    if args.command == "convert":
        result = CONVERTERS[args.converter](
            args.source, args.output, args.metadata
        )
        text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
        report_path = getattr(args, "report", None)
        if report_path:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(text, encoding="utf-8")
        print(text, end="")
        return 0
    if args.command == "build":
        context = BuildContext.capture()
        summary, _ = build_release(
            args.input,
            args.metadata,
            args.output,
            args.reports,
            args.examples,
            context,
        )
        print(
            f"Built {summary['cia_file_count']} CIA files with version "
            f"{context.version}"
        )
        return 0
    if args.command == "validate":
        result = validate_release(
            args.input, args.metadata, args.output, args.examples
        )
        text = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(text, encoding="utf-8")
        else:
            print(text, end="")
        return 0 if result["valid"] else 1
    if args.command == "release":
        context = BuildContext.capture()
        manifest, report_dir = publish_release(
            args.input, args.metadata, args.output, args.reports,
            args.backups, args.examples, context,
        )
        print(
            f"Released {manifest['cia_file_count']} CIA files with version "
            f"{context.version}; reports={report_dir}"
        )
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
