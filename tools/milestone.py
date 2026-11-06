#!/usr/bin/env python3
"""Milestone e sprint di un progetto: apertura e verifica.

    python3 tools/milestone.py check "<progetto>" [--json]
    python3 tools/milestone.py new-milestone "<progetto>" [--goal "..." ]
    python3 tools/milestone.py new-sprint "<progetto>" <milestone> [--objective "..."]

Esito di ``check``:
    0  la storia e' completa
    1  manca un report, un prompt, o la numerazione ha un buco
    2  errore di lettura, oppure scrittura rifiutata perche' nessun contract
       approvato copre il percorso

Lo strumento interroga `contract_scope.py` prima di scrivere: le scritture fatte
da uno script non passano dall'euristica della shell, quindi il controllo sta qui.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ad_milestone  # noqa: E402


# ---------------------------------------------------------------------------
# Le sei sezioni del rapporto di passo
#
# Perche' esiste: il 2026-10-13 ho misurato i rapporti di passo dei progetti, e
# **solo 9 su 23 seguivano il modello**. La sezione che mancava di piu' era
# «cosa passa allo sprint successivo» — 11 su 23 — cioe' **proprio quella che serve
# all'agente che viene dopo**.
#
# E' lo stesso difetto dei verbali: il modello c'era, era giusto, e **nessuno lo
# controllava**. Per 36 verbali ho scritto sezioni mie; da quando `verbali.py` le
# pretende, sono 56 su 56.
#
# **Le sezioni si leggono dal modello**, non si riscrivono qui: se domani il modello
# cambia, il controllo lo segue. E' la lezione di `ERR-0012` — una lista scritta a
# mano dentro il codice invecchia in silenzio.
# ---------------------------------------------------------------------------

MODELLO_RAPPORTO = "milestone/_TEMPLATE-SPRINT-REPORT.md"


def sezioni_del_rapporto(radice: Path | None = None) -> tuple[str, ...]:
    """Le sezioni che il modello del rapporto chiede, lette dal modello."""
    base = radice or Path(__file__).resolve().parents[1]
    modello = base / MODELLO_RAPPORTO
    if not modello.is_file():
        return ()
    return tuple(
        riga.strip()
        for riga in modello.read_text(encoding="utf-8").splitlines()
        if riga.startswith("## ")
    )


#: Da quando il modello e' preteso. Prima e' storia, e la storia non si riscrive:
#: quei rapporti sono **chiusi**, dentro progetti che non si toccano, e alcuni non sono
#: nemmeno nostri. Un controllo che fallisce per sempre su 14 rapporti e' **un allarme
#: permanente** — il difetto di ERR-0016, e non lo ricreo qui. E' la stessa scelta di
#: DEC-0037 per i verbali: esenzione DICHIARATA per il passato, regola dal presente.
MODELLO_PRETESO_DAL = "2026-10-13"


def _sezioni_presenti(testo: str, sezioni: tuple[str, ...]) -> list[str]:
    """Quali sezioni del modello ci sono, **tollerando la numerazione**.

    Un rapporto che scrive `## 3. Cosa e' stato fatto` segue il modello: ha solo
    aggiunto il numero. Rifiutarlo sarebbe punire una forma, non un contenuto.
    """
    import re as _re

    intestazioni = [
        _re.sub(r"^##\s*(?:\d+\.?\s*)*", "", riga).strip().lower()
        for riga in testo.splitlines()
        if riga.startswith("## ")
    ]
    mancanti = []
    for sezione in sezioni:
        attesa = _re.sub(r"^##\s*", "", sezione).strip().lower()
        if not any(attesa in h for h in intestazioni):
            mancanti.append(sezione)
    return mancanti


def controlla_rapporti(progetto: Path | str, radice: Path | None = None) -> list[str]:
    """I rapporti **chiusi** che non seguono il modello.

    Si guardano solo i rapporti chiusi: un passo aperto non ha ancora un rapporto, e
    pretenderlo sarebbe chiedere il consuntivo prima del lavoro.
    """
    import ad_milestone as _am

    sezioni = sezioni_del_rapporto(radice)
    if not sezioni:
        return []
    fuori: list[str] = []
    for tappa in _am.scan(progetto):
        for passo in tappa.sprints:
            rapporto = passo.path / _am.SPRINT_REPORT
            if not rapporto.is_file():
                continue
            testo = rapporto.read_text(encoding="utf-8", errors="replace")
            if "stato: chiusa" not in testo and "stato: chiuso" not in testo:
                continue
            # L'esenzione del passato: si guarda la data dichiarata di chiusura.
            import re as _re

            # La data di chiusura si cerca in tre posti, e il terzo e' il ripiego:
            # il rapporto del 2026-10-11 per a client dichiara `data:`, non
            # `chiuso:` — e il mio primo controllo, troppo rigido, lo segnalava.
            # Un controllo che pretende un campo che il modello non impone e' un
            # controllo che sbaglia.
            quando = _re.search(
                r"^(?:chius[oa]|data):\s*[\"']?(\d{4}-\d{2}-\d{2})", testo, _re.M
            )
            giorno = quando.group(1) if quando else None
            if giorno is None:
                import datetime as _dt

                giorno = _dt.date.fromtimestamp(rapporto.stat().st_mtime).isoformat()
            if giorno < MODELLO_PRETESO_DAL:
                continue
            mancanti = _sezioni_presenti(testo, sezioni)
            if mancanti:
                fuori.append(
                    f"{tappa.path.name}/{passo.path.name}: il rapporto non ha "
                    + ", ".join(f"«{m}»" for m in mancanti[:3])
                    + (f" e altre {len(mancanti) - 3}" if len(mancanti) > 3 else "")
                )
    return fuori


def cmd_check(args: argparse.Namespace) -> int:
    """Verify the milestone history of a project."""
    project = Path(args.project)
    issues = ad_milestone.problems(project)
    # Un rapporto chiuso che non dice «cosa passa allo sprint successivo» e' un diario,
    # non un passaggio di consegne: l'agente che viene dopo non sa da dove ripartire.
    issues = issues + controlla_rapporti(project)
    milestones = ad_milestone.scan(project)
    sprints = sum(len(milestone.sprints) for milestone in milestones)
    # Un passo chiuso senza biglietto di consegna non e' un errore (DEC-0089: avvisa,
    # non blocca), ma `check` deve dirlo: e' la scorciatoia che poi si paga.
    avvisi: list[str] = []
    for tappa in milestones:
        for passo in tappa.sprints:
            if passo.has_report and not passo.has_consegna:
                avvisi.append(
                    f"{tappa.path.name}/{passo.path.name}: chiuso ma senza "
                    f"{ad_milestone.SPRINT_CONSEGNA} (il passo dopo riparte piu' lento)"
                )

    if args.json:
        print(
            json.dumps(
                {
                    "project": str(project),
                    "milestones": len(milestones),
                    "sprints": sprints,
                    "issues": issues,
                    "warnings": avvisi,
                    "ok": not issues,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0 if not issues else 1

    if not issues:
        print(f"OK   {project.name}: {len(milestones)} milestone, {sprints} sprint, storia completa")
        for avviso in avvisi:
            print(f"  avviso: {avviso}")
        return 0
    for issue in issues:
        print(f"  {issue}")
    for avviso in avvisi:
        print(f"  avviso: {avviso}")
    print(f"\nesito: {len(issues)} problemi — la storia non e' completa")
    return 1


def cmd_new_milestone(args: argparse.Namespace) -> int:
    """Open the next milestone."""
    try:
        target = ad_milestone.scaffold_milestone(args.project, args.goal or "")
    except PermissionError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"aperta {target}")
    return 0


def cmd_new_sprint(args: argparse.Namespace) -> int:
    """Open the next sprint of a milestone."""
    try:
        target = ad_milestone.scaffold_sprint(args.project, args.milestone, args.objective or "")
    except PermissionError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"aperto {target}")
    return 0


def _ultimo_sprint_aperto(project: Path) -> tuple[int, int] | None:
    """L'ultimo sprint che ha il PROMPT: quello che si sta chiudendo."""
    ultimo: tuple[int, int] | None = None
    for milestone in ad_milestone.scan(project):
        for sprint in milestone.sprints:
            ultimo = (milestone.number, sprint.number)
    return ultimo


def cmd_consegna(args: argparse.Namespace) -> int:
    """Chiude un passo e prepara la chat nuova: biglietto, poi il passo successivo.

    Regola (DEC-0089): **blocca** se il passo che si chiude non ha il ``REPORT.md`` —
    senza rapporto non c'e' la prova che il lavoro sia stato fatto. **Avvisa**, senza
    bloccare, se un passo precedente non ha il biglietto: un file di cortesia non deve
    diventare un vicolo cieco.
    """
    project = Path(args.project)
    if not project.is_dir():
        print(f"milestone: il progetto non esiste: {project}", file=sys.stderr)
        return 2

    ultimo = _ultimo_sprint_aperto(project)
    if ultimo is None:
        print(f"  {project.name}: nessuno sprint aperto — non c'e' niente da consegnare")
        print(f'  Aprilo: python3 tools/milestone.py new-sprint "{project.name}" 1 --objective "…"')
        return 1
    milestone, sprint = ultimo

    # 1) Il passo che si chiude deve avere il rapporto. Questo BLOCCA.
    rapporti = ad_milestone.problems(project)
    mancanti = [r for r in rapporti if "manca REPORT.md" in r]
    if mancanti:
        print("  NON consegno: la storia del progetto non e' completa.", file=sys.stderr)
        for voce in mancanti:
            print(f"    {voce}", file=sys.stderr)
        print(
            "  Il passo che si chiude ha bisogno del suo rapporto: senza, non c'e' la "
            "prova che il lavoro sia stato fatto.",
            file=sys.stderr,
        )
        return 1

    # 2) Il biglietto: si scrive. Se un passo precedente non ce l'ha, si AVVISA.
    try:
        destinazione = ad_milestone.scrivi_consegna(project, milestone, sprint)
    except PermissionError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    avvisi: list[str] = []
    for tappa in ad_milestone.scan(project):
        for passo in tappa.sprints:
            if (tappa.number, passo.number) == (milestone, sprint):
                continue
            if passo.has_report and not passo.has_consegna:
                avvisi.append(
                    f"{tappa.path.name}/{passo.path.name}: chiuso ma senza "
                    f"{ad_milestone.SPRINT_CONSEGNA}"
                )

    relativo = destinazione.relative_to(ad_milestone.docs_dir(project)).as_posix()
    if args.json:
        print(
            json.dumps(
                {
                    "project": str(project),
                    "milestone": milestone,
                    "sprint": sprint,
                    "consegna": relativo,
                    "avvisi": avvisi,
                    "ok": True,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    print(f"  consegna scritta: {relativo}")
    for avviso in avvisi:
        print(f"  avviso: {avviso}")
    if avvisi:
        print(
            "  (avviso, non blocco: un biglietto mancante peggiora la chat dopo, "
            "non toglie l'autorita' a nessuno)"
        )
    print()
    print("  --- Da incollare nella chat nuova ---")
    print()
    print(f'  Collegati al progetto "{project.name}" e prosegui dal passo {sprint + 1}.')
    print(f'  Leggi prima {relativo}: dice dove siamo e cosa resta.')
    print()
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Milestone e sprint di un progetto")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="output JSON")
    sub = parser.add_subparsers(dest="action", required=True)

    check = sub.add_parser("check", parents=[common], help="la storia e' completa?")
    check.add_argument("project")

    milestone = sub.add_parser("new-milestone", parents=[common], help="apri la prossima milestone")
    milestone.add_argument("project")
    milestone.add_argument("--goal", help="obiettivo in una riga")

    consegna = sub.add_parser(
        "consegna",
        parents=[common],
        help="chiudi un passo e prepara la chat nuova (biglietto + passo successivo)",
    )
    consegna.add_argument("project")

    sprint = sub.add_parser("new-sprint", parents=[common], help="apri il prossimo sprint")
    sprint.add_argument("project")
    sprint.add_argument("milestone", type=int)
    sprint.add_argument("--objective", help="obiettivo in una riga")

    args = parser.parse_args(argv)
    return {
        "check": cmd_check,
        "new-milestone": cmd_new_milestone,
        "new-sprint": cmd_new_sprint,
        "consegna": cmd_consegna,
    }[args.action](args)


if __name__ == "__main__":
    raise SystemExit(main())
