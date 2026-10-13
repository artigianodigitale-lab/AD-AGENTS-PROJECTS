#!/usr/bin/env python3
"""Registro drift: verifica e consultazione.

    python3 tools/drift.py check          # il registro e' coerente?
    python3 tools/drift.py list [--open]  # le voci

Esito di ``check``:
    0  registro coerente
    1  una voce incompleta, un ID non contiguo, o una chiusura senza Decision Record
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ad_drift  # noqa: E402


def cmd_check(args: argparse.Namespace) -> int:
    """Verify the drift register."""
    entries = ad_drift.load()
    issues = ad_drift.problems()
    if args.json:
        print(json.dumps({"entries": len(entries), "issues": issues, "ok": not issues},
                         indent=2, ensure_ascii=False))
        return 0 if not issues else 1
    if not issues:
        aperti = sum(1 for entry in entries if not entry.closed)
        print(f"OK   {len(entries)} voci, {aperti} aperte, registro coerente")
        return 0
    for issue in issues:
        print(f"  {issue}")
    print(f"\nesito: {len(issues)} problemi")
    return 1


def cmd_list(args: argparse.Namespace) -> int:
    """List the entries."""
    entries = ad_drift.load()
    if args.open:
        entries = [entry for entry in entries if not entry.closed]
    for entry in entries:
        print(f"{entry.id}  {entry.severity:13} {entry.state:9} {entry.title}")
    print(f"\n{len(entries)} voci")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Registro drift")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="output JSON")
    sub = parser.add_subparsers(dest="action", required=True)

    sub.add_parser("check", parents=[common], help="il registro e' coerente?")
    listing = sub.add_parser("list", parents=[common], help="elenca le voci")
    listing.add_argument("--open", action="store_true", help="solo le voci aperte")

    args = parser.parse_args(argv)
    return {"check": cmd_check, "list": cmd_list}[args.action](args)


if __name__ == "__main__":
    raise SystemExit(main())
