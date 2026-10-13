#!/usr/bin/env python3
"""Ambito di scrittura di un percorso: e' coperto da un task contract?

    python3 tools/contract_scope.py check <path> [--json] [--root DIR]
    python3 tools/contract_scope.py list [--json]
    python3 tools/contract_scope.py policy [--json]

Esito di ``check``:
    0  il percorso non e' protetto, oppure e' coperto da un contract
    1  protetto e non coperto
    2  errore di lettura

Questo comando e' l'autorita' del layer di enforcement di runtime: il plugin
DSH lo interroga e non reimplementa la regola.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ad_docs  # noqa: E402
import ad_scope  # noqa: E402


def cmd_check(args: argparse.Namespace) -> int:
    """Evaluate one path."""
    verdict = ad_scope.evaluate(args.path, args.root)
    if args.json:
        print(
            json.dumps(
                {
                    "target": verdict.target,
                    "relative": verdict.relative,
                    "protected": verdict.protected,
                    "covered": verdict.covered,
                    "task_id": verdict.task_id,
                    "allowed": verdict.allowed,
                    "reason": verdict.reason,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0 if verdict.allowed else 1
    if verdict.allowed:
        if verdict.protected:
            print(f"OK   {verdict.relative} — {verdict.reason}")
        else:
            print(f"OK   {verdict.target} — fuori dalle cartelle prodotto")
        return 0
    print(verdict.reason, file=sys.stderr)
    return 1


def cmd_list(args: argparse.Namespace) -> int:
    """List the operational contracts."""
    root = Path(args.root) if args.root else ad_docs.DOCS_ROOT
    scopes = ad_scope.load_write_scopes(root)
    if args.json:
        print(
            json.dumps(
                [
                    {
                        "task_id": scope.task_id,
                        "agent": scope.agent,
                        "write_scope": list(scope.scopes),
                        "source": str(scope.source),
                    }
                    for scope in scopes
                ],
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0
    if not scopes:
        print(f"nessun contract operativo in {ad_scope.contracts_dir(root)}")
        return 0
    for scope in scopes:
        print(f"{scope.task_id:20} agent={scope.agent or '?':20} {scope.source.name}")
        for entry in scope.scopes:
            print(f"    {entry}")
    return 0


def cmd_policy(args: argparse.Namespace) -> int:
    """Print the enforcement view of the current state."""
    data = ad_scope.policy(args.root)
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0
    print(f"root: {data['root']}")
    print(f"contract: {data['contracts_dir']}")
    print(f"cartelle protette ({len(data['protected_folders'])}): "
          + ", ".join(data["protected_folders"]))
    print(f"contract attivi: {len(data['contracts'])}")
    return 0


def cmd_check_command(args: argparse.Namespace) -> int:
    """Evaluate one shell command."""
    verdict = ad_scope.evaluate_command(args.shell_command, args.root, args.cwd)
    if args.json:
        print(
            json.dumps(
                {
                    "target": verdict.relative,
                    "protected": verdict.protected,
                    "covered": verdict.covered,
                    "task_id": verdict.task_id,
                    "allowed": verdict.allowed,
                    "reason": verdict.reason,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0 if verdict.allowed else 1
    if verdict.allowed:
        print("OK   comando ammesso")
        return 0
    print(verdict.reason, file=sys.stderr)
    return 1


# ---------------------------------------------------------------------------
# titolari — chi puo' scrivere dove, ADESSO
#
# Perche' esiste: il 2026-10-13 ho misurato e trovato **5 permessi attivi su `tools/`**,
# **4 su `.brain/`**, e **5 sulla stessa tappa** di Marketing Factory. Nessuno lo sapeva,
# e **non c'era uno strumento per vederlo**: si scopriva solo leggendo 20 file a mano.
#
# La causa non e' la distrazione: e' che **un permesso non finisce quando il lavoro
# finisce**. Vive fino alla scadenza — e quelli di Marketing Factory scadono fra **90
# giorni**. Quindi i permessi si accumulano, e ogni strato nuovo si sovrappone a quelli
# vecchi come una sedimento.
#
# E il danno concreto: **un percorso con due titolari non ha un titolare.** Se qualcosa
# si rompe, nessuno sa di chi era; e due scritture sullo stesso file si sovrascrivono
# senza che nessuno se ne accorga.
# ---------------------------------------------------------------------------


def titolari(base: Path | None = None) -> dict:
    """I percorsi e chi li copre, con i conflitti separati per gravita'.

    - `identici`: due permessi dichiarano **lo stesso** percorso. Conflitto vero.
    - `dentro`: un permesso dichiara una cartella che **contiene** il percorso di un
      altro. Non e' per forza un conflitto — possono toccare file diversi — ma va
      guardato, ed e' la forma che hanno tutti i nostri.
    """
    radice = Path(base) if base else ad_docs.DOCS_ROOT
    scopes = ad_scope.load_write_scopes(radice)

    per: dict[str, list[str]] = {}
    for scope in scopes:
        for voce in scope.scopes:
            per.setdefault(str(voce).strip(), []).append(scope.task_id)

    identici = {k: sorted(v) for k, v in per.items() if len(v) > 1}

    dentro: list[tuple[str, str, list[str]]] = []
    for piccolo, suoi in per.items():
        for grande, altri in per.items():
            if piccolo == grande:
                continue
            if piccolo.startswith(grande) and len(altri) > 0:
                estranei = sorted(set(altri) - set(suoi))
                if estranei:
                    dentro.append((piccolo, grande, estranei))

    return {
        "permessi": {s.task_id: list(s.scopes) for s in scopes},
        "per_percorso": per,
        "identici": identici,
        "dentro": dentro,
    }


def cmd_titolari(args: argparse.Namespace) -> int:
    """Chi puo scrivere dove, adesso — e dove sono i conflitti."""
    esito = titolari(args.root)
    if args.json:
        print(json.dumps(esito, ensure_ascii=False, indent=2))
        return 0

    print(f"  permessi attivi: {len(esito['permessi'])}")
    for tid, scopes in sorted(esito["permessi"].items()):
        print(f"    {tid:10} {', '.join(scopes)[:64]}")

    if esito["identici"]:
        print(f"\n  PERCORSI CON PIU DI UN TITOLARE ({len(esito['identici'])})")
        for percorso, chi in sorted(esito["identici"].items()):
            print(f"    {percorso}")
            print(f"      {', '.join(chi)}")
    else:
        print("\n  nessun percorso con piu di un titolare")

    if esito["dentro"]:
        print(f"\n  CARTELLE CHE NE CONTENGONO ALTRE ({len(esito['dentro'])}) - da guardare, non per forza un conflitto")
        for piccolo, grande, estranei in esito["dentro"][:8]:
            print(f"    {piccolo}")
            print(f"      sta dentro {grande}, che appartiene anche a {', '.join(estranei)}")

    return 1 if esito["identici"] else 0


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="output JSON")
    common.add_argument("--root", help="root di AD Projects (default: la root del checkout)")

    parser = argparse.ArgumentParser(description="Ambito di scrittura dei task contract")
    sub = parser.add_subparsers(dest="action", required=True)

    check = sub.add_parser("check", parents=[common], help="un percorso e' coperto?")
    check.add_argument("path")

    check_command = sub.add_parser(
        "check-command", parents=[common], help="un comando shell e' ammesso?"
    )
    check_command.add_argument("shell_command", metavar="comando")
    check_command.add_argument("--cwd", help="directory di lavoro del comando")

    sub.add_parser("list", parents=[common], help="elenca i contract operativi")
    sub.add_parser("policy", parents=[common], help="stato del layer di enforcement")
    sub.add_parser("titolari", parents=[common], help="chi puo scrivere dove, adesso")

    args = parser.parse_args(argv)
    return {
        "check": cmd_check,
        "check-command": cmd_check_command,
        "list": cmd_list,
        "policy": cmd_policy,
        "titolari": cmd_titolari,
    }[args.action](args)


if __name__ == "__main__":
    raise SystemExit(main())
