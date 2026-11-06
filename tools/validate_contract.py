#!/usr/bin/env python3
"""Valida un Task Contract contro i documenti normativi.

    python3 tools/validate_contract.py <contract.yaml> [--strict] [--json]

Esito:
    0  nessuna violazione (le WARNING restano visibili)
    1  almeno una VIOLATION, oppure una WARNING con --strict
    2  il contract non e' leggibile

Il task non parte senza contract valido (TASK-CONTRACTS.md, Regole).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ad_contract  # noqa: E402
import ad_registry  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Valida un Task Contract")
    parser.add_argument("contract", help="file YAML del contract")
    parser.add_argument("--strict", action="store_true", help="tratta le WARNING come errori")
    parser.add_argument("--json", action="store_true", help="output JSON")
    args = parser.parse_args(argv)

    try:
        contract = ad_contract.load(args.contract)
    except ad_contract.ContractError as exc:
        print(f"ERRORE  {exc}", file=sys.stderr)
        return 2

    registry = ad_registry.load()
    findings = ad_contract.validate(contract, registry)
    hard = ad_contract.violations(findings)
    soft = ad_contract.warnings(findings)
    failed = bool(hard) or (args.strict and bool(soft))

    if args.json:
        print(
            json.dumps(
                {
                    "contract": str(args.contract),
                    "task_id": contract.get("task_id"),
                    "agent": contract.get("agent"),
                    "outcome": "FAIL" if failed else "PASS",
                    "violations": [
                        {"code": f.code, "message": f.message} for f in hard
                    ],
                    "warnings": [
                        {"code": f.code, "message": f.message} for f in soft
                    ],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 1 if failed else 0

    task_id = contract.get("task_id", "?")
    print(f"contract {task_id} · agent {contract.get('agent', '?')} · file {args.contract}")
    for finding in findings:
        print(f"  {finding}")
    if not findings:
        print("  nessun rilievo")
    print(
        f"\nesito: {'FAIL' if failed else 'PASS'} — "
        f"{len(hard)} violazioni, {len(soft)} avvisi"
    )
    if failed and not hard:
        print("  (--strict: gli avvisi contano come errori)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
