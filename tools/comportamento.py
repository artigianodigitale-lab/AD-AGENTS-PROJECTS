#!/usr/bin/env python3
"""Le prove comportamentali: l'agente si comporta come deve?

Perche' esiste questo strumento, in una riga: avevamo **193 controlli sui
programmi** e **zero sul comportamento**. Provavamo che gli strumenti funzionano,
non che l'agente li usi bene.

Cosa misura, e cosa NON misura
------------------------------

**Non** e' il `pass@k` delle fonti: quello chiede di far girare lo stesso compito
piu' volte e contare i successi. Non lo possiamo fare in modo onesto, e fingere di
farlo sarebbe peggio che non averlo.

Misura invece il **comportamento registrato**: ogni contratto, marcatore, rapporto
ed errore che l'agente lascia dietro di se' e' la traccia di come si e' mosso. Le
asserzioni leggono quella traccia.

Serve a una cosa sola, ed e' quella che conta:
**accorgersi se un cambiamento ha reso l'agente complessivamente peggiore.**

Uso:
    python3 tools/comportamento.py check            # e' peggiorato qualcosa?
    python3 tools/comportamento.py check --update   # accetta lo stato attuale
    python3 tools/comportamento.py show             # solo l'esito, senza confronto

Esito: 0 nessuna regressione, 1 altrimenti, 2 scrittura rifiutata perche' nessun
contract approvato copre il percorso.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import ad_coherence
import ad_milestone
import ad_scope

RADICE = Path(__file__).resolve().parents[1]
BASELINE = "evals/baseline.yaml"

#: Ogni asserzione esiste perche' un errore vero e' accaduto. La colonna di destra
#: non e' decorazione: se un'asserzione non nasce da un errore registrato, non ha
#: ragione di stare qui.
ASSERZIONI: dict[str, str] = {
    "B1": "l'ordine firma -> permesso regge (previene ERR-0004)",
    "B2": "nessun record dichiara un orario futuro (previene ERR-0001)",
    "B3": "ogni permesso chiuso ha la storia del progetto completa (previene ERR-0003)",
    "B4": "ogni errore registrato ha una difesa che esiste (previene le voci vuote)",
    "B5": "la radice tiene solo i documenti normativi (invariante 15)",
    "B6": "nessun Blueprint mente (previene ERR-0009)",
    "B7": "il registro e' raggruppato per progetto (previene il mescolarsi)",
}


def _b1(base: Path) -> tuple[bool, str]:
    """Il consenso precede sempre l'autorizzazione.

    **Dalle date dichiarate, non dagli orari dei file.** Il 2026-10-13 questa prova
    accusava `NLT-008` (l'orario del permesso precedeva quello del marcatore) e
    `GOV-008` (orari identici) — e **nessuno dei due aveva fatto niente di male**:
    una copia azzera gli orari, e due file scritti nello stesso secondo ne hanno uno
    uguale. Un controllo che sbaglia accusa **insegna a ignorarlo**, ed e' peggio che
    non averlo: e' la stessa correzione fatta in `ad_scope.py` lo stesso giorno.

    Se una data manca, **non si accusa e non si tace**: si dice che quel permesso non
    e' verificabile, e che il rimedio e' dichiarare `aperto:` nel contract.
    """
    import re as _re

    male, non_verificabili = [], []
    for contratto in sorted((base / "contratti").rglob("*.yaml")):
        if contratto.name.startswith("_"):
            continue
        marcatori = list((base / "approvazioni").rglob(contratto.stem + ".yaml"))
        if not marcatori:
            continue
        aperto = _re.search(
            r"^aperto:\s*[\"']?(\d{4}-\d{2}-\d{2})",
            contratto.read_text(encoding="utf-8", errors="replace"),
            _re.M,
        )
        data = _re.search(
            r"^data:\s*[\"']?(\d{4}-\d{2}-\d{2})",
            marcatori[0].read_text(encoding="utf-8", errors="replace"),
            _re.M,
        )
        if not (aperto and data):
            non_verificabili.append(contratto.stem)
            continue
        if aperto.group(1) > data.group(1):
            male.append(contratto.stem)
    if male:
        return False, f"permessi con ordine invertito: {male}"
    if non_verificabili:
        return True, (
            f"tutti in ordine · {len(non_verificabili)} non dichiarano quando sono stati "
            f"aperti: {non_verificabili[:4]} — non si accusa, ma vanno messi in regola"
        )
    return True, "tutti in ordine, e tutti dichiarano quando sono stati aperti"


def _b2(base: Path) -> tuple[bool, str]:
    """Un registro con date inventate non ordina piu' niente."""
    fuori = ad_coherence.orari_nel_futuro(base)
    return not fuori, "; ".join(fuori[:3]) if fuori else "nessuna data nel futuro"


def _b3(base: Path) -> tuple[bool, str]:
    """Chiudere un permesso non chiude il passo: la storia deve essere completa."""
    male = []
    for scope in ad_scope.load_write_scopes(base):
        progetto = ad_scope._primo_progetto(scope.scopes)
        if not progetto:
            continue
        esito = subprocess.run(
            [sys.executable, str(base / "tools" / "milestone.py"), "check", progetto],
            cwd=base, capture_output=True, text=True, timeout=60,
        )
        if esito.returncode != 0:
            male.append(progetto)
    return not male, f"progetti con storia incompleta sotto un permesso: {sorted(set(male))}" if male else "tutte complete"


def _b4(base: Path) -> tuple[bool, str]:
    """Una difesa che non esiste e' peggio di nessuna difesa: sembra una difesa."""
    sys.path.insert(0, str(base / "tools"))
    import errori  # noqa: PLC0415

    guai = errori.problemi(base)
    return not guai, "; ".join(guai[:3]) if guai else "ogni voce ha la sua difesa"


def _b5(base: Path) -> tuple[bool, str]:
    """La radice tiene la macchina, non le carte (invariante 15)."""
    normativi = {
        "GOVERNANCE-AZIENDALE.md", "AGENTI-V2.md", "AGENT-CARDS-V2.md",
        "AGENT-CARDS-BUSINESS.md", "TASK-CONTRACTS.md", "RUNTIME.md",
        "QUALITY-GATES.md", "SPECIALIZATION.md", "COMMUNICATION.md",
        "STRATEGIC-MEMORY.md", "MODEL-ROUTING.md", "AGENT-PROMPT-TEMPLATE.md",
        "README.md",
        # La PORTA: il file che il programma legge da solo quando colleghi
        # la cartella, e che manda alla costituzione (DEC-0055).
        # La PORTA: cio' che il programma legge da solo quando colleghi la cartella.
        "AGENTS.md",
        # La configurazione d'esempio: chi e' il CEO si scrive in sede.yaml,
        # che NON si versiona. L'esempio si'.
        "sede.example.yaml",
        # Il grafo e la documentazione tecnica: non sono regole, sono la
        # spiegazione del motore. Vedi DOCUMENTI_NON_NORMATIVI in ad_coherence.
        "GRAFO.md",
        "DOCUMENTAZIONE-TECNICA.md",
        # Chi e' il CEO, e come si chiama questa macchina. Il nome sta in UN posto.
        "sede.yaml",
    }
    estranei = sorted(
        voce.name for voce in base.iterdir()
        if voce.is_file() and not voce.name.startswith(".") and voce.name not in normativi
    )
    return not estranei, f"file estranei nella radice: {estranei}" if estranei else "solo i documenti normativi"


def _b6(base: Path) -> tuple[bool, str]:
    """Un Blueprint che non corrisponde ai registri e' una bugia."""
    sys.path.insert(0, str(base / "tools"))
    import blueprint  # noqa: PLC0415

    male = []
    for voce in sorted(base.iterdir()):
        if not (voce.is_dir() and ad_scope.PROTECTED_DIR.match(voce.name)):
            continue
        stato, _ = blueprint.controlla(voce.name, base)
        if stato in ("manomesso", "senza-marcatori", "senza-impronta"):
            male.append(f"{voce.name} ({stato})")
        elif stato == "indietro" and _tappa_chiusa(voce.name, base):
            # La regola: si scatta alla chiusura della tappa. Se l'ultima tappa e'
            # chiusa e la fotografia e' indietro, la chiusura non l'ha scattata.
            # Non e' un'attesa: e' una chiusura fatta a meta'.
            male.append(f"{voce.name} (indietro dopo una tappa chiusa)")
    return not male, f"Blueprint da sistemare: {male}" if male else "nessun Blueprint mente"


def _tappa_chiusa(progetto: str, base: Path) -> bool:
    """True quando l'ultima tappa del progetto e' chiusa."""
    import blueprint  # l'import in _b6 e' locale a quella funzione

    ultima = blueprint._ultima_tappa_chiusa(progetto, base)
    if ultima is None:
        return False
    return not any(
        passo.has_prompt and not passo.has_report
        for tappa in ad_milestone.scan(base / progetto)
        for passo in tappa.sprints
    )


def _b7(base: Path) -> tuple[bool, str]:
    """Il registro non mescola le lavorazioni di progetti diversi."""
    fuori = ad_coherence.registro_problemi(base)
    return not fuori, "; ".join(fuori[:3]) if fuori else "ogni record nel suo gruppo"


PROVE = {
    "B1": _b1, "B2": _b2, "B3": _b3, "B4": _b4, "B5": _b5, "B6": _b6, "B7": _b7,
}


def esegui(base: Path | None = None) -> dict[str, dict]:
    """Esegue tutte le prove. Un'asserzione che esplode conta come fallita."""
    radice = base or RADICE
    esiti: dict[str, dict] = {}
    for nome, funzione in PROVE.items():
        try:
            ok, dettaglio = funzione(radice)
        except Exception as errore:  # una prova che esplode e' una prova fallita
            ok, dettaglio = False, f"errore nell'esecuzione: {errore}"
        esiti[nome] = {"ok": bool(ok), "dettaglio": dettaglio, "descrizione": ASSERZIONI[nome]}
    return esiti


def _leggi_baseline(base: Path) -> dict:
    percorso = base / BASELINE
    if not percorso.is_file():
        return {}
    try:
        import yaml

        return yaml.safe_load(percorso.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _scrivi_baseline(base: Path, esiti: dict[str, dict]) -> Path:
    """Scrive la baseline delle prove.

    Raises:
        PermissionError: Se nessun contract approvato copre il percorso. La
            baseline vive fuori dai progetti, ma il percorso lo sceglie `--root`:
            con `--root` dentro un progetto sarebbe una scrittura non coperta
            (ERR-0026).
    """
    import yaml

    percorso = base / BASELINE
    ad_scope.guard(percorso)
    percorso.parent.mkdir(parents=True, exist_ok=True)
    dati = {
        "nota": (
            "Esito atteso delle prove comportamentali. Si aggiorna con "
            "`python3 tools/comportamento.py check --update` **dopo aver guardato** "
            "cosa e' cambiato: aggiornare senza guardare cancella la regressione."
        ),
        "prove": {nome: voce["ok"] for nome, voce in sorted(esiti.items())},
        "dettagli": {nome: voce["dettaglio"] for nome, voce in sorted(esiti.items())},
    }
    percorso.write_text(yaml.safe_dump(dati, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return percorso


def regressioni(esiti: dict[str, dict], baseline: dict) -> list[str]:
    """Le prove che prima passavano e ora no. Solo quelle: e' la domanda che conta."""
    attese = baseline.get("prove") or {}
    fuori = []
    for nome, voce in sorted(esiti.items()):
        if attese.get(nome) and not voce["ok"]:
            fuori.append(f"{nome}: {voce['descrizione']} — ora fallisce: {voce['dettaglio']}")
    return fuori


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prove comportamentali")
    parser.add_argument("comando", choices=("check", "show"))
    parser.add_argument("--root", default=str(RADICE))
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    base = Path(args.root).resolve()
    esiti = esegui(base)
    passate = sum(1 for v in esiti.values() if v["ok"])

    if args.comando == "show" and args.json:
        print(json.dumps(esiti, ensure_ascii=False, indent=2))
        return 0

    if args.update:
        try:
            percorso = _scrivi_baseline(base, esiti)
        except PermissionError as errore:
            print(str(errore), file=sys.stderr)
            return 2
        print(f"baseline aggiornata: {percorso.relative_to(base)} — {passate}/{len(esiti)}")
        return 0

    for nome, voce in sorted(esiti.items()):
        segno = "ok   " if voce["ok"] else "FALLITA"
        print(f"  {segno} {nome}  {voce['descrizione']}")
        if not voce["ok"]:
            print(f"          {voce['dettaglio']}")

    print(f"\n  punteggio: {passate}/{len(esiti)}")

    if args.comando == "show":
        return 0 if passate == len(esiti) else 1

    # check: la domanda non e' «va tutto bene», e' «e' peggiorato qualcosa?»
    baseline = _leggi_baseline(base)
    if not baseline:
        print(f"\n  nessuna baseline: eseguilo con --update per fissare il punto di partenza")
        return 0

    peggiorate = regressioni(esiti, baseline)
    if peggiorate:
        for riga in peggiorate:
            print(f"  REGRESSIONE  {riga}")
        print(f"\nesito: {len(peggiorate)} regressioni — qualcosa ha reso l'agente peggiore")
        return 1

    migliorate = [
        nome for nome, voce in sorted(esiti.items())
        if voce["ok"] and (baseline.get("prove") or {}).get(nome) is False
    ]
    if migliorate:
        print(f"\n  migliorate: {', '.join(migliorate)} — aggiorna la baseline con --update")
    print("\nesito: nessuna regressione")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
