#!/usr/bin/env python3
"""Emette il verdetto del Quality Gate su un contract e le sue evidenze.

    python3 tools/verdict.py --contract <contract.yaml> --evidence <path> [<path> ...]

Regola (QUALITY-GATES.md):

    per ogni gate in required_gates:
      evidenza valida PASS  -> avanti
      evidenza valida FAIL  -> REJECT
      evidenza assente      -> REJECT
    tutti PASS -> ACCEPT

Esito:
    0  ACCEPT
    1  REJECT
    2  contract o evidenze non leggibili

ACCEPT non e' il rilascio: se il contract ha approval.human, decide l'umano.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ad_contract  # noqa: E402
import ad_evidence  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Verdetto del Quality Gate")
    parser.add_argument("--contract", required=True, help="file YAML del contract")
    parser.add_argument(
        "--evidence", nargs="+", required=True, help="file o cartelle di evidenze"
    )
    parser.add_argument("--json", action="store_true", help="output JSON")
    args = parser.parse_args(argv)

    try:
        contract = ad_contract.load(args.contract)
    except ad_contract.ContractError as exc:
        print(f"ERRORE  {exc}", file=sys.stderr)
        return 2
    try:
        evidence = ad_evidence.collect(args.evidence)
    except ad_evidence.EvidenceError as exc:
        print(f"ERRORE  {exc}", file=sys.stderr)
        return 2

    verdict = ad_evidence.evaluate(contract, evidence)

    if args.json:
        print(
            json.dumps(
                {
                    "task_id": contract.get("task_id"),
                    "outcome": verdict.outcome,
                    "human_gate": verdict.human_gate,
                    "gates": [
                        {
                            "gate": result.gate,
                            "state": result.state,
                            "producer": result.producer,
                            "detail": result.detail,
                        }
                        for result in verdict.gates
                    ],
                    "notes": list(verdict.notes),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0 if verdict.outcome == "ACCEPT" else 1

    print(f"contract {contract.get('task_id', '?')} · esecutore {contract.get('agent', '?')}")
    print(f"evidenze lette: {len(evidence)}")
    print()
    for result in verdict.gates:
        line = f"  {result.gate:14} {result.state:8}"
        if result.producer:
            line += f" produttore={result.producer:16}"
        print(line + f" {result.detail}")
    for note in verdict.notes:
        print(f"\n  NOTA  {note}")
    print(f"\nverdetto: {verdict.outcome}")
    if verdict.human_gate:
        print("  approvazione umana richiesta dal contract: ACCEPT non e' il rilascio")
    return 0 if verdict.outcome == "ACCEPT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
