#!/usr/bin/env python3
"""La memoria del motore: cerca nei registri, e ogni risultato porta la sua fonte (M4, `DEC-0116`).

Perche' esiste. La storia del motore sta in sei posti (`strategic_memory/`, `DECISIONI/`,
`errori/`, `drift/`, `piani/`, `evidenze/`) e si legge con grep: nessuna provenienza, nessuna
misura. E il modello di minaccia LLM09 dice che un recupero non verificato e' un rischio: un
risultato «plausibile» puo' non esistere.

Come funziona. Ricerca **lessicale deterministica** (niente embedding, niente modello): ogni
riga dei registri e' un candidato, i termini rari pesano di piu' (IDF), e i primi k risultati
tornano con:

    file, riga, estratto, sha256 della fonte, punteggio

`verifica` ricontrolla che la fonte citata esista **ancora** con quell'impronta: se un file e'
cambiato, la citazione non e' piu' verificabile e lo dice.

Uso:
    python3 tools/memoria.py cerca "<domanda>" [--k 3] [--json]
    python3 tools/memoria.py verifica --file <percorso> --sha256 <impronta>
    python3 tools/memoria.py fonti

Esiti: 0 ok, 1 fonte non verificabile, 2 uso sbagliato.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

RADICE = Path(__file__).resolve().parents[1]
MAX_RIGHE = 20000  # tetto di lettura per file: un registro enorme non blocca una query

FONTI = (
    "SECURITY.md",
    "CRAWLING.md",
    "drift/README.md",
    "tools/README.md",
    "DECISIONI",
    "errori",
    "piani",
    "evidenze",
    "strategic_memory",
)

FERME = {
    "che", "cosa", "come", "perche", "della", "delle", "degli", "con", "una", "uno", "gli",
    "le", "lo", "il", "la", "i", "e", "di", "a", "da", "in", "su", "per", "tra", "fra",
    "non", "piu", "quale", "quali", "quando", "dove", "chi", "si", "no", "del", "dei",
    "anche", "sono", "essere", "questo", "questa", "quello", "quella", "ha", "hanno",
}


def _parole(testo: str) -> list[str]:
    return [p for p in re.findall(r"[a-z0-9]+", testo.lower()) if len(p) >= 3 and p not in FERME]


def impronta_percorso(percorso: Path) -> str:
    return hashlib.sha256(percorso.read_bytes()).hexdigest()


def _file_fonti() -> list[Path]:
    file: list[Path] = []
    for voce in FONTI:
        percorso = RADICE / voce
        if percorso.is_file():
            file.append(percorso)
        elif percorso.is_dir():
            for estensione in ("*.md", "*.yaml", "*.yml", "*.json"):
                file.extend(sorted(percorso.rglob(estensione)))
    # niente evidenze enormi? si leggono, ma con tetto di righe.
    return [f for f in file if f.is_file()]


def fonti() -> list[str]:
    return [str(f.relative_to(RADICE)) for f in _file_fonti()]


def _righe(percorso: Path, massimo: int = MAX_RIGHE) -> list[str]:
    try:
        testo = percorso.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return testo.splitlines()[:massimo]


def cerca(domanda: str, *, k: int = 3, massimo_righe_per_file: int = MAX_RIGHE) -> dict[str, Any]:
    """Cerca nei registri. Restituisce k risultati con la loro provenienza."""
    termini = _parole(domanda)
    if not termini:
        return {"domanda": domanda, "risultati": [], "costo": {"file_letti": 0, "byte_letti": 0, "token_stimati": 0},
                "nota": "nessun termine utile nella domanda"}

    file = _file_fonti()
    righe_per_file: list[tuple[Path, list[str]]] = []
    byte_letti = 0
    # prima passata: quali file contengono quali termini (per l'IDF)
    presenze: dict[str, int] = {termine: 0 for termine in termini}
    for percorso in file:
        righe = _righe(percorso, massimo_righe_per_file)
        righe_per_file.append((percorso, righe))
        try:
            byte_letti += percorso.stat().st_size
        except OSError:
            pass
        testo_file = " ".join(righe).lower()
        for termine in termini:
            if termine in testo_file:
                presenze[termine] += 1

    totale = max(len(righe_per_file), 1)
    pesi = {termine: 1.0 + math.log((totale + 1) / (presenze[termine] + 1)) for termine in termini}

    candidati: list[dict[str, Any]] = []
    for percorso, righe in righe_per_file:
        nome = percorso.name.lower()
        relativo = str(percorso.relative_to(RADICE))
        for numero, riga in enumerate(righe, 1):
            minuscola = riga.lower()
            if not any(termine in minuscola for termine in termini):
                continue
            punteggio = 0.0
            for termine in termini:
                if termine in minuscola:
                    punteggio += pesi[termine]
                if termine in nome or termine in relativo.lower():
                    punteggio += 2.0
            if not punteggio:
                continue
            candidati.append({
                "file": relativo,
                "riga": numero,
                "estratto": " ".join(riga.split())[:240],
                "punteggio": round(punteggio, 3),
            })

    candidati.sort(key=lambda voce: (-voce["punteggio"], voce["file"], voce["riga"]))
    scelti = []
    for voce in candidati:
        percorso = RADICE / voce["file"]
        if not percorso.is_file():
            continue
        voce = dict(voce)
        voce["sha256"] = impronta_percorso(percorso)
        scelti.append(voce)
        if len(scelti) >= k:
            break

    caratteri = sum(len(voce["estratto"]) for voce in scelti)
    return {
        "domanda": domanda,
        "risultati": scelti,
        "costo": {
            "file_letti": len(righe_per_file),
            "byte_letti": byte_letti,
            "token_stimati": caratteri // 4,
        },
        "nota": "il recupero e' lessicale; ogni risultato porta file:riga e l'impronta della fonte",
    }


def verifica(percorso: str | Path, sha256: str) -> dict[str, Any]:
    """La fonte citata esiste ancora, con quell'impronta?"""
    file = Path(percorso)
    if not file.is_absolute():
        file = RADICE / file
    if not file.is_file():
        return {"file": str(percorso), "ok": False, "motivo": "la fonte non esiste piu'"}
    attuale = impronta_percorso(file)
    if attuale != sha256:
        return {"file": str(percorso), "ok": False, "motivo": "la fonte e' cambiata",
                "sha256_atteso": sha256, "sha256_attuale": attuale}
    return {"file": str(percorso), "ok": True, "sha256": attuale}


def main(argv: list[str] | None = None) -> int:
    analizzatore = argparse.ArgumentParser(description="La memoria del motore: registri con provenienza")
    sotto = analizzatore.add_subparsers(dest="azione", required=True)
    c = sotto.add_parser("cerca", help="cerca nei registri")
    c.add_argument("domanda")
    c.add_argument("--k", type=int, default=3)
    c.add_argument("--json", action="store_true")
    v = sotto.add_parser("verifica", help="ricontrolla una fonte citata")
    v.add_argument("--file", required=True)
    v.add_argument("--sha256", required=True)
    v.add_argument("--json", action="store_true")
    f = sotto.add_parser("fonti", help="elenca le fonti lette")
    f.add_argument("--json", action="store_true")

    args = analizzatore.parse_args(argv)
    if args.azione == "fonti":
        elenco = fonti()
        if args.json:
            print(json.dumps(elenco, indent=2, ensure_ascii=False))
        else:
            for voce in elenco:
                print(f"  {voce}")
        return 0
    if args.azione == "verifica":
        esito = verifica(args.file, args.sha256)
        if args.json:
            print(json.dumps(esito, indent=2, ensure_ascii=False))
        else:
            print(f"  {'verificata' if esito['ok'] else 'NON verificabile'}: {esito.get('file')}"
                  + ("" if esito["ok"] else f" — {esito['motivo']}"))
        return 0 if esito["ok"] else 1
    if args.azione == "cerca":
        esito = cerca(args.domanda, k=args.k)
        if args.json:
            print(json.dumps(esito, indent=2, ensure_ascii=False))
        else:
            print(f"  {len(esito['risultati'])} risultati per «{args.domanda}» "
                  f"({esito['costo']['file_letti']} file, {esito['costo']['byte_letti']} byte, "
                  f"~{esito['costo']['token_stimati']} token)")
            for voce in esito["risultati"]:
                print(f"    - {voce['file']}:{voce['riga']}  [{voce['sha256'][:12]}…] {voce['estratto']}")
            if not esito["risultati"]:
                print("  (nessun risultato: la memoria non inventa)")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
