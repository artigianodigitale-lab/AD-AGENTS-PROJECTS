#!/usr/bin/env python3
"""Registry delle Agent Card: consultazione e controllo di integrita'.

    python3 tools/cards.py list [--domain technical|business]
    python3 tools/cards.py show <card-id>
    python3 tools/cards.py match <task-type> [--domain technical|business]
    python3 tools/cards.py check

Nessun token: e' la fascia deterministica di MODEL-ROUTING.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ad_docs  # noqa: E402
import ad_gates  # noqa: E402
import ad_registry  # noqa: E402


def _card_dict(card: ad_registry.Card) -> dict:
    """Return a JSON-serialisable view of a card."""
    return {
        "id": card.id,
        "name": card.name,
        "domain": card.domain,
        "type": card.type,
        "version": card.version,
        "status": card.status,
        "mission": card.mission,
        "capabilities": list(card.capabilities),
        "authorized_task_types": (
            None if card.authorized_task_types is None else list(card.authorized_task_types)
        ),
        "excluded_task_types": (
            None if card.excluded_task_types is None else list(card.excluded_task_types)
        ),
        "permissions": card.permissions,
        "tools": list(card.tools),
        "accessible_memory": list(card.accessible_memory),
        "autonomy": card.autonomy,
        "escalation": list(card.escalation),
        "definition_of_done": list(card.definition_of_done),
        "formation": card.formation,
        "source": card.source,
        "assignable": card.assignable,
        "missing_fields": list(card.missing_fields),
        "governance_missing_fields": list(card.governance_missing_fields),
    }


def cmd_list(args: argparse.Namespace, registry: dict[str, ad_registry.Card]) -> int:
    """List the cards."""
    cards = sorted(registry.values(), key=lambda c: (c.domain, c.id))
    if args.domain:
        cards = [card for card in cards if card.domain == args.domain]
    if args.json:
        print(json.dumps([_card_dict(card) for card in cards], indent=2, ensure_ascii=False))
        return 0
    print(f"{'id':28} {'dominio':9} {'tipo':11} {'stato':9} assegnabile")
    for card in cards:
        print(
            f"{card.id:28} {card.domain:9} {card.type:11} {card.status:9} "
            f"{'si' if card.assignable else 'NO'}"
        )
    print(f"\n{len(cards)} card")
    return 0


def cmd_show(args: argparse.Namespace, registry: dict[str, ad_registry.Card]) -> int:
    """Show one card in full."""
    card = registry.get(args.card_id)
    if card is None:
        print(f"card '{args.card_id}' non trovata nel registry", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(_card_dict(card), indent=2, ensure_ascii=False))
        return 0
    data = _card_dict(card)
    print(f"# {card.id} — {card.name}")
    print(f"dominio: {card.domain} | tipo: {card.type} | versione: {card.version} | stato: {card.status}")
    print(f"fonte: {card.source}")
    print(f"assegnabile: {'si' if card.assignable else 'NO'}")
    if card.mission:
        print(f"\nmissione: {card.mission}")
    for key in (
        "capabilities",
        "authorized_task_types",
        "excluded_task_types",
        "tools",
        "accessible_memory",
        "escalation",
        "definition_of_done",
    ):
        print(f"{key}: {data[key]}")
    print(f"permissions: {card.permissions}")
    print(f"autonomy: {card.autonomy}")
    if card.formation:
        print(f"formation: {card.formation}")
    if card.missing_fields:
        print(f"\nCAMPI CRITICI ASSENTI: {list(card.missing_fields)}")
    if card.governance_missing_fields:
        print(f"campi richiesti da AGENTI-V2.md assenti: {list(card.governance_missing_fields)}")
    return 0


def cmd_match(args: argparse.Namespace, registry: dict[str, ad_registry.Card]) -> int:
    """Return the cards that authorise a task type."""
    index = ad_registry.task_type_index(registry, args.domain)
    matches = index.get(args.task_type, [])
    if args.json:
        print(json.dumps({"task_type": args.task_type, "cards": matches}, indent=2))
        return 0 if matches else 1
    if not matches:
        print(
            f"nessun match per '{args.task_type}': STOP, non si assegna all'agente piu' vicino "
            "(SPECIALIZATION.md)",
            file=sys.stderr,
        )
        return 1
    for card_id in sorted(matches):
        card = registry[card_id]
        print(f"{card_id:28} {card.domain:9} {card.type}")
    return 0


def cmd_check(args: argparse.Namespace, registry: dict[str, ad_registry.Card]) -> int:
    """Check the integrity of the registry against the documents."""
    problems = 0
    technical = ad_registry.by_domain(registry, "technical")
    business = ad_registry.by_domain(registry, "business")
    print(f"registry: {len(registry)} card ({len(technical)} tecniche, {len(business)} business)")

    print("\n-- card non assegnabili: match non verificabile --")
    unassignable = [card for card in registry.values() if not card.assignable]
    for card in sorted(unassignable, key=lambda c: c.id):
        print(f"  {card.id:28} campi assenti: {list(card.missing_fields) or 'nessuno'}")
    if not unassignable:
        print("  nessuna")

    print("\n-- note di completezza: campi richiesti da AGENTI-V2.md ma non dichiarati --")
    gaps: dict[str, list[str]] = {}
    for card in registry.values():
        for field_name in card.governance_missing_fields:
            gaps.setdefault(field_name, []).append(card.id)
    for field_name, card_ids in sorted(gaps.items()):
        print(f"  {field_name:24} assente su {len(card_ids)} card: {', '.join(card_ids[:4])}"
              + (" ..." if len(card_ids) > 4 else ""))
    if not gaps:
        print("  nessuno")

    print("\n-- catalogo gate --")
    for label, names in (
        (ad_docs.QUALITY_GATES, ad_gates.quality_catalog()),
        (ad_docs.GOVERNANCE, ad_gates.governance_catalog()),
    ):
        print(f"  {label}: {len(names)} gate")
    drift = ad_gates.drift()
    for message in drift:
        print(f"  DRIFT {message}")
    problems += len(drift)
    problems += len(unassignable)

    # I problemi contano cio' che rende il registry inutilizzabile: card non
    # assegnabili e drift fra documenti. Un campo mancante che non blocca
    # l'assegnazione e' una nota, non un guasto.
    note = sum(len(card_ids) for card_ids in gaps.values())
    print(f"\nesito: {problems} problemi bloccanti, {note} note di completezza")
    if problems:
        print("  i problemi bloccanti impediscono l'assegnazione o indicano drift fra documenti")
    return 1 if (problems and args.strict) else 0


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Registry delle Agent Card di AD Projects")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="output JSON")
    common.add_argument("--domain", choices=("technical", "business"), help="filtra per dominio")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", parents=[common], help="elenca le card")
    show = sub.add_parser("show", parents=[common], help="mostra una card")
    show.add_argument("card_id")
    match = sub.add_parser("match", parents=[common], help="card che autorizzano un task type")
    match.add_argument("task_type")
    check = sub.add_parser("check", parents=[common], help="controlla l'integrita' del registry")
    check.add_argument(
        "--strict", action="store_true", help="exit 1 se trova problemi di integrita'"
    )

    args = parser.parse_args(argv)
    registry = ad_registry.load()
    handlers = {
        "list": cmd_list,
        "show": cmd_show,
        "match": cmd_match,
        "check": cmd_check,
    }
    return handlers[args.command](args, registry)


if __name__ == "__main__":
    raise SystemExit(main())
