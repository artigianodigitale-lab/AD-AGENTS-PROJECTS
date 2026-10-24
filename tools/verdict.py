#!/usr/bin/env python3
"""Verdetto del Quality Gate, e registro delle incognite.

    python3 tools/verdict.py --contract <contract.yaml> --evidence <path> [<path> ...]
    python3 tools/verdict.py --unknown list|show|new|update|resolve|check
    python3 tools/verdict.py --bundle export|import|check
    python3 tools/verdict.py --tree record|check

Verdetto (QUALITY-GATES.md), in forma fail-closed:

    per ogni gate in required_gates:
      evidenza valida PASS *con copertura completa* -> avanti
      esito FAIL/UNKNOWN/TRUNCATED/SKIPPED/UNSUPPORTED -> REJECT
      evidenza assente o non valida                  -> REJECT
    tutti PASS -> ACCEPT

Esito:
    0  ACCEPT (o comando eseguito)
    1  REJECT (o problema del registro)
    2  contract o evidenze non leggibili

ACCEPT non e' il rilascio: se il contract ha approval.human, decide l'umano.

Registro delle incognite (`--unknown`). Le domande aperte sono voci, non prosa:
identita' calcolata da domanda+dominio, revisione esplicita, prove a favore e
contro, e **l'autorita' che serve per chiuderle**. Una domanda si chiude solo con
`--disposition verified` e almeno una prova (`--evidence-ids`); se il registro
delle prove e' disponibile (`--evidence`), la prova deve esistere e avere
l'autorita' e la confidenza richieste. ENG-001, passo 3.

Bundle sigillato (`--bundle`). `export` raccoglie le prove di un lavoro (e le
incognite collegate) in un JSON canonico con un **sigillo** sul contenuto;
`check` verifica il sigillo e l'identita' di ogni record; `import` rifiuta un
pacchetto manomesso e, con `--into`, estrae le prove in una cartella. La garanzia
e' quella del Blueprint di AD: un sigillo sul contenuto, non un puntatore ai
registri. ENG-001, passo 4.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ad_contract  # noqa: E402
import ad_evidence  # noqa: E402

DEFAULT_LEDGER = "evidenze/incognite.yaml"


def _evidence_map(
    targets: list[str] | None, ledger: str | Path | None = None
) -> dict[str, ad_evidence.Evidence]:
    """Load the evidence set, keyed by identity.

    **Mai `None`.** F1 del primo gate di ENG-001: senza `--evidence` il controllo
    di una chiusura veniva saltato del tutto, e un'incognita `critical` si chiudeva
    citando una prova inventata. Una regola applicata solo quando qualcuno passa
    un flag non e' una regola: e' un'opzione. Senza `--evidence` si guarda accanto
    al registro (le prove stanno in `evidenze/`), e se non ce ne sono il registro
    e' vuoto: una chiusura che cita una prova assente viene rifiutata.
    """
    if targets:
        return {record.evidence_id: record for record in ad_evidence.collect(targets)}
    if ledger is not None:
        cartella = Path(ledger).parent
        if cartella.is_dir():
            return {
                record.evidence_id: record
                for record in ad_evidence.collect([cartella])
            }
    return {}


def _find_unknown(
    records: list[dict], identificatore: str
) -> dict | None:
    """Return one entry by id, or None."""
    for record in records:
        if str(record.get("unknown_id")) == identificatore:
            return record
    return None


def _unknown_command(args: argparse.Namespace) -> int:
    """Run one unknowns-registry action."""
    ledger = Path(args.ledger)
    try:
        records = ad_evidence.load_unknowns(ledger)
    except ad_evidence.UnknownRegistryError as exc:
        print(f"ERRORE  {exc}", file=sys.stderr)
        return 2

    azione = args.unknown

    if azione == "list":
        if args.json:
            print(json.dumps(records, indent=2, ensure_ascii=False))
        for record in records:
            print(
                f"{record.get('unknown_id')}  {str(record.get('status', '?')):13} "
                f"{str(record.get('severity', '?')):8} r{record.get('revision')}  "
                f"{record.get('question')}"
            )
        if not records:
            print("nessuna incognita registrata")
        return 0

    if azione == "show":
        if not args.id:
            print("ERRORE  --id obbligatorio per 'show'", file=sys.stderr)
            return 2
        record = _find_unknown(records, args.id)
        if record is None:
            print(f"ERRORE  incognita '{args.id}' non trovata", file=sys.stderr)
            return 1
        print(json.dumps(record, indent=2, ensure_ascii=False))
        return 0

    if azione == "new":
        if not args.question or not args.domain:
            print("ERRORE  --question e --domain obbligatori per 'new'", file=sys.stderr)
            return 2
        record = ad_evidence.new_unknown(
            args.question,
            args.domain,
            severity=args.severity or "medium",
            required_authority=args.authority,
            probes=tuple(args.probes or ()),
            supporting=tuple(args.evidence_ids or ()),
        )
        if _find_unknown(records, str(record["unknown_id"])) is not None:
            print(
                f"ERRORE  esiste gia' {record['unknown_id']}: la domanda e' la stessa. "
                "Usa 'update' per una nuova revisione",
                file=sys.stderr,
            )
            return 1
        # Si valida PRIMA di scrivere, e con la mappa delle prove: una voce che
        # cita prove inesistenti non deve nemmeno nascere (ERR-0052).
        problemi = ad_evidence.check_unknowns(
            records + [record], _evidence_map(args.evidence, args.ledger)
        )
        if problemi:
            for problema in problemi:
                print(f"ERRORE  {problema}", file=sys.stderr)
            return 1
        records.append(record)
        ad_evidence.save_unknowns(ledger, records)
        print(f"{record['unknown_id']}  aperta ({record['severity']})")
        return 0

    if azione in ("update", "resolve"):
        if not args.id:
            print(f"ERRORE  --id obbligatorio per '{azione}'", file=sys.stderr)
            return 2
        record = _find_unknown(records, args.id)
        if record is None:
            print(f"ERRORE  incognita '{args.id}' non trovata", file=sys.stderr)
            return 1
        risoluzione = None
        stato = args.status
        if azione == "resolve":
            if not args.disposition or not args.rationale:
                print(
                    "ERRORE  'resolve' richiede --disposition e --rationale",
                    file=sys.stderr,
                )
                return 2
            risoluzione = {
                "disposition": args.disposition,
                "rationale": args.rationale,
                "evidence_ids": list(args.evidence_ids or ()),
            }
            stato = "resolved"
        aggiornata = ad_evidence.update_unknown(
            record,
            status=stato,
            severity=args.severity,
            probes=tuple(args.probes) if args.probes else None,
            supporting=tuple(args.evidence_ids) if args.evidence_ids and azione == "update" else None,
            resolution=risoluzione,
        )
        nuove = [aggiornata if item is record else item for item in records]
        problemi = ad_evidence.check_unknowns(
            nuove, _evidence_map(args.evidence, args.ledger)
        )
        if problemi:
            for problema in problemi:
                print(f"ERRORE  {problema}", file=sys.stderr)
            return 1
        ad_evidence.save_unknowns(ledger, nuove)
        print(f"{aggiornata['unknown_id']}  ora {aggiornata['status']} (r{aggiornata['revision']})")
        return 0

    if azione == "check":
        problemi = ad_evidence.check_unknowns(
            records, _evidence_map(args.evidence, args.ledger)
        )
        for problema in problemi:
            print(f"ERRORE  {problema}", file=sys.stderr)
        if problemi:
            return 1
        print(f"OK   registro delle incognite coerente: {len(records)} voci")
        return 0

    print(f"ERRORE  azione sconosciuta '{azione}'", file=sys.stderr)
    return 2


ROOT = Path(__file__).resolve().parents[1]


def _tree_root(args: argparse.Namespace) -> Path:
    """Return the root to watch: the caller's, or this machine."""
    return Path(args.tree_root).resolve() if args.tree_root else ROOT


def _tree_command(args: argparse.Namespace) -> int:
    """Record or check the out-of-band witness of the tree."""
    radice = _tree_root(args)
    percorsi = tuple(args.paths) if args.paths else ad_evidence.DEFAULT_TREE_PATHS
    # Se il testimone vive dentro una radice sorvegliata, si esclude da solo:
    # l'esclusione e' dichiarata nel file (non e' un buco silenzioso).
    try:
        relativo = Path(args.witness).resolve().relative_to(radice).as_posix()
        esclusi: tuple[str, ...] = (relativo,)
    except ValueError:
        esclusi = ()
    if args.tree == "record":
        try:
            witness = ad_evidence.create_witness(radice, percorsi, exclude=esclusi)
        except ad_evidence.TreeError as exc:
            print(f"ERRORE  {exc}", file=sys.stderr)
            return 2
        ad_evidence.save_witness(args.witness, witness)
        print(
            f"testimone scritto: {args.witness} · {len(witness['files'])} file · "
            f"{len(percorsi)} radici"
        )
        print(f"sigillo: {witness['digest']}")
        return 0

    try:
        witness = ad_evidence.load_witness(args.witness)
    except ad_evidence.TreeError as exc:
        print(f"ERRORE  {exc}", file=sys.stderr)
        return 2
    guardati = tuple(witness.get("paths") or percorsi)
    esclusi = tuple(witness.get("exclude") or ())
    try:
        corrente = ad_evidence.tree_fingerprint(radice, guardati, esclusi)
    except ad_evidence.TreeError as exc:
        print(f"ERRORE  {exc}", file=sys.stderr)
        return 2
    copertura = None
    if args.evidence:
        try:
            copertura = ad_evidence.coverage_map(ad_evidence.collect(args.evidence))
        except ad_evidence.EvidenceError as exc:
            print(f"ERRORE  {exc}", file=sys.stderr)
            return 2
    problemi = ad_evidence.compare_tree(witness, corrente, copertura)
    for problema in problemi:
        print(f"CONTAMINAZIONE  {problema}", file=sys.stderr)
    if problemi:
        print(
            f"\n{len(problemi)} modifiche fuori banda: nessuna evidenza le nomina. "
            "Non e' un divieto violato, e' un silenzio rotto (DEC-0057)"
        )
        return 1
    print(
        f"OK   nessuna modifica fuori banda: {len(corrente['files'])} file, "
        f"testimone del {witness.get('recorded_at', '?')}"
    )
    return 0


def _bundle_command(args: argparse.Namespace) -> int:
    """Run one bundle action: export, import or check."""
    if args.bundle == "export":
        if not args.evidence or not args.out:
            print("ERRORE  'export' richiede --evidence e --out", file=sys.stderr)
            return 2
        try:
            records = ad_evidence.collect(args.evidence)
        except ad_evidence.EvidenceError as exc:
            print(f"ERRORE  {exc}", file=sys.stderr)
            return 2
        try:
            incognite = ad_evidence.load_unknowns(args.ledger)
        except ad_evidence.UnknownRegistryError as exc:
            print(f"ERRORE  {exc}", file=sys.stderr)
            return 2
        testimone = None
        if not args.no_witness:
            percorso_testimone = Path(args.witness)
            if percorso_testimone.exists():
                try:
                    testimone = ad_evidence.load_witness(percorso_testimone)
                except ad_evidence.TreeError as exc:
                    print(f"ERRORE  {exc}", file=sys.stderr)
                    return 2
        try:
            bundle = ad_evidence.create_bundle(records, incognite, witness=testimone)
        except ad_evidence.BundleError as exc:
            print(f"ERRORE  {exc}", file=sys.stderr)
            return 1
        problemi = ad_evidence.verify_bundle(bundle)
        if problemi:
            for problema in problemi:
                print(f"ERRORE  {problema}", file=sys.stderr)
            return 1
        ad_evidence.save_bundle(args.out, bundle)
        print(
            f"bundle scritto: {args.out} · task {bundle['task_id']} · "
            f"{len(bundle['records'])} prove · {len(bundle['unknowns'])} incognite · "
            f"testimone {'incluso' if testimone else 'non incluso'}"
        )
        print(f"sigillo: {bundle['seal']}")
        return 0

    if not args.bundle_path:
        print(f"ERRORE  '--bundle {args.bundle}' richiede --bundle-path", file=sys.stderr)
        return 2
    try:
        bundle = ad_evidence.load_bundle(args.bundle_path)
    except ad_evidence.BundleError as exc:
        print(f"ERRORE  {exc}", file=sys.stderr)
        return 2
    problemi = ad_evidence.verify_bundle(bundle)
    for problema in problemi:
        print(f"ERRORE  {problema}", file=sys.stderr)
    if problemi:
        return 1
    if args.json:
        print(json.dumps({k: v for k, v in bundle.items() if k != "records"}, indent=2, ensure_ascii=False))
    if args.bundle == "check":
        print(
            f"OK   bundle attendibile: task {bundle['task_id']} · "
            f"{len(bundle['records'])} prove · {len(bundle['unknowns'])} incognite"
        )
        return 0
    if args.into:
        try:
            esito = ad_evidence.extract_bundle(bundle, args.into)
        except ad_evidence.BundleError as exc:
            print(f"ERRORE  {exc}", file=sys.stderr)
            return 1
        print(
            f"bundle importato in {args.into}: {esito['records']} prove, "
            f"{esito['unknowns']} incognite"
        )
    else:
        print(
            f"OK   bundle verificato: task {bundle['task_id']} · "
            f"{len(bundle['records'])} prove · {len(bundle['unknowns'])} incognite"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Verdetto del Quality Gate e incognite")
    parser.add_argument("--contract", help="file YAML del contract (verdetto)")
    parser.add_argument(
        "--evidence", nargs="+", help="file o cartelle di evidenze"
    )
    parser.add_argument(
        "--unknown",
        choices=("list", "show", "new", "update", "resolve", "check"),
        help="gestisci il registro delle incognite invece del verdetto",
    )
    parser.add_argument(
        "--bundle",
        choices=("export", "import", "check"),
        help="bundle sigillato delle prove invece del verdetto",
    )
    parser.add_argument("--bundle-path", help="file del bundle")
    parser.add_argument("--out", help="dove scrivere il bundle (export)")
    parser.add_argument("--into", help="cartella dove estrarre un bundle verificato (import)")
    parser.add_argument(
        "--tree",
        choices=("record", "check"),
        help="impronta dell'albero per il rilevamento fuori banda",
    )
    parser.add_argument(
        "--witness", default="evidenze/albero.yaml", help="file del testimone dell'albero"
    )
    parser.add_argument("--paths", nargs="*", help="radici da sorvegliare (record)")
    parser.add_argument(
        "--tree-root", help="radice da sorvegliare (default: la macchina che contiene tools/)"
    )
    parser.add_argument(
        "--no-witness", action="store_true", help="non includere il testimone nel bundle"
    )
    parser.add_argument("--ledger", default=DEFAULT_LEDGER, help="registro delle incognite")
    parser.add_argument("--id", help="id dell'incognita")
    parser.add_argument("--question", help="domanda dell'incognita")
    parser.add_argument("--domain", help="dominio dell'incognita")
    parser.add_argument("--severity", choices=ad_evidence.SEVERITIES)
    parser.add_argument("--status", choices=ad_evidence.UNKNOWN_STATUSES)
    parser.add_argument("--disposition", choices=ad_evidence.DISPOSITIONS)
    parser.add_argument("--rationale", help="perche' la domanda e' chiusa")
    parser.add_argument("--authority", choices=ad_evidence.AUTHORITY_VALUES)
    parser.add_argument("--evidence-ids", nargs="*", help="id delle prove collegate")
    parser.add_argument("--probes", nargs="*", help="verifiche consigliate")
    parser.add_argument("--json", action="store_true", help="output JSON")
    args = parser.parse_args(argv)

    if args.tree:
        return _tree_command(args)

    if args.bundle:
        return _bundle_command(args)

    if args.unknown:
        return _unknown_command(args)

    if not args.contract or not args.evidence:
        print(
            "ERRORE  --contract e --evidence sono obbligatori per il verdetto "
            "(oppure usa --unknown per il registro delle incognite)",
            file=sys.stderr,
        )
        return 2

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
                            "evidence_id": result.evidence_id,
                            "limitations": list(result.limitations),
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
    limiti = [result for result in verdict.gates if result.limitations]
    if limiti:
        print()
        for result in limiti:
            print(f"  LIMITI dichiarati per {result.gate}:")
            for limite in result.limitations:
                print(f"    - {limite}")
    for note in verdict.notes:
        print(f"\n  NOTA  {note}")
    print(f"\nverdetto: {verdict.outcome}")
    if verdict.human_gate:
        print("  approvazione umana richiesta dal contract: ACCEPT non e' il rilascio")
    return 0 if verdict.outcome == "ACCEPT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
