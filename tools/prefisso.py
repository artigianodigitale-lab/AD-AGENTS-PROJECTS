#!/usr/bin/env python3
"""Il costo del prefisso: quanto paga ogni sessione, e se e' cache-friendly.

Perche' esiste. `AGENTS.md` e' il **prefisso stabile**: il testo che ogni sessione legge
prima di dire una parola. Misurato il 2026-11-06: 31.047 byte, circa 7.761 token. Le dieci
skill sono altri 61.000 byte.

Perche' conta, e non e' una questione di gusto. Uno studio su 500 sessioni di agenti
(Don't Break the Cache, PwC — https://arxiv.org/html/2601.06007) misura che la cache dei
prompt riduce il costo del **41-81%** e il tempo alla prima parola del 6-31%, e che il
risparmio cresce **linearmente** con la dimensione del prefisso stabile: a 50.000 token
l'89%. Ma il beneficio arriva solo se il prefisso **non cambia**: ogni modifica invalida
la cache per tutte le sessioni successive.

Due controlli, che misurano due cose diverse:

  A — **quanto costa**. Se il prefisso cresce senza che nessuno lo decida, questo lo dice.
  B — **dove sta il testo dinamico**. Una data in testa rompe la cache a ogni sessione; la
      stessa data in fondo no. Il controllo guarda le prime righe.

La soglia non e' un obiettivo: e' una **guardia**. Oggi 31 KB: c'e' margine per crescere,
e un avviso quando sfugge. Si legge dal file, non si stima.

Uso:
    python3 tools/prefisso.py            # misura e controlla
    python3 tools/prefisso.py --json

Esito: 0 tutto a posto · 1 una delle due guardie e' scattata.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]
COSTITUZIONE = RADICE / ".brain" / "COSTITUZIONE.md"
SKILLS = RADICE / ".brain" / "skills"

#: Le guardie. Non sono obiettivi da raggiungere: sono il punto in cui si dice «basta».
LIMITE_COSTITUZIONE = 48 * 1024
LIMITE_TOTALE = 100 * 1024

#: Quante righe in testa non devono contenere testo che cambia da sessione a sessione.
RIGHE_DI_TESTA = 400

#: Il testo che cambia da una sessione all'altra. Una data in testa a `AGENTS.md` invalida
#: il prefisso cachabile; la stessa data in fondo no, perche' il prefisso resta uguale.
#: La differenza e' dove sta, non cosa e'.
DINAMICO = (
    re.compile(r"\b20\d\d-\d\d-\d\dT\d\d:"),                       # un istante
    re.compile(r"\b(?:oggi|adesso)\s+(?:\u00e8|e'|sono)\b", re.I),  # «oggi e' …»
    re.compile(r"\bcurrent(?:ly)?\s+(?:is|time|date)\b", re.I),
    re.compile(r"\bsession[_-]?id\b", re.I),
    re.compile(r"\b(?:sessione|session)\s+[0-9a-f]{8}-", re.I),    # un id di sessione
)


def token_stimati(byte: int) -> int:
    """Una stima grossolana: 4 byte per token. Basta per una guardia, non per un conto."""
    return byte // 4


def misura() -> dict:
    """Byte del livello sempre caricato: costituzione piu' skill."""
    if not COSTITUZIONE.is_file():
        return {"costituzione": 0, "skills": 0, "totale": 0, "file_skill": 0}
    byte_costituzione = COSTITUZIONE.stat().st_size
    byte_skill = 0
    file_skill = 0
    if SKILLS.is_dir():
        for percorso in sorted(SKILLS.glob("*/SKILL.md")):
            byte_skill += percorso.stat().st_size
            file_skill += 1
    return {
        "costituzione": byte_costituzione,
        "skills": byte_skill,
        "totale": byte_costituzione + byte_skill,
        "file_skill": file_skill,
    }


def dinamico_in_testa() -> list[str]:
    """Le righe dinamiche nelle prime ``RIGHE_DI_TESTA`` righe della costituzione.

    Le citazioni storiche sono **ammesse**: «il 2026-10-11 e' successo questo» racconta un
    fatto e non cambia. Si guarda solo cio' che si presenta come stato corrente: un istante
    con l'ora, una dichiarazione di «adesso», un identificatore di sessione.
    """
    if not COSTITUZIONE.is_file():
        return []
    try:
        righe = COSTITUZIONE.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return ["la costituzione non si legge"]
    trovate: list[str] = []
    for numero, riga in enumerate(righe[:RIGHE_DI_TESTA], 1):
        spoglia = riga.strip()
        if not spoglia or spoglia.startswith("#"):
            continue
        for espressione in DINAMICO:
            if espressione.search(riga):
                trovate.append(f"riga {numero}: {spoglia[:90]}")
                break
    return trovate


def controlli() -> tuple[list[str], dict]:
    """I problemi trovati, e i numeri che li giustificano."""
    numeri = misura()
    problemi: list[str] = []

    if numeri["totale"] == 0:
        return ["il livello sempre caricato non si legge"], numeri

    if numeri["costituzione"] > LIMITE_COSTITUZIONE:
        problemi.append(
            f"AGENTS.md e' {numeri['costituzione'] // 1024} KB "
            f"(~{token_stimati(numeri['costituzione'])} token), oltre la guardia di "
            f"{LIMITE_COSTITUZIONE // 1024} KB: ogni sessione lo paga. "
            "Sposta cio' che non serve sempre in un documento a chiamata."
        )
    if numeri["totale"] > LIMITE_TOTALE:
        problemi.append(
            f"il livello sempre caricato e' {numeri['totale'] // 1024} KB "
            f"(~{token_stimati(numeri['totale'])} token), oltre la guardia di "
            f"{LIMITE_TOTALE // 1024} KB. Le skill si caricano a chiamata "
            "(MODEL-ROUTING.md): se questa somma cresce, qualcuno le sta caricando tutte."
        )

    in_testa = dinamico_in_testa()
    if in_testa:
        problemi.append(
            "testo dinamico nelle prime righe di AGENTS.md: rompe il prefisso cachabile a "
            "ogni sessione. Va in fondo.\n  " + "\n  ".join(in_testa[:5])
        )
    return problemi, numeri


def main(argv: list[str] | None = None) -> int:
    argomenti = argv if argv is not None else sys.argv[1:]
    problemi, numeri = controlli()
    if "--json" in argomenti:
        print(
            json.dumps(
                {
                    "numeri": numeri,
                    "problemi": problemi,
                    "token_stimati": token_stimati(numeri["totale"]),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1 if problemi else 0
    if problemi:
        for problema in problemi:
            print(f"  NO   {problema}")
        return 1
    print(
        f"  ok   prefisso: AGENTS.md {numeri['costituzione'] // 1024} KB "
        f"(~{token_stimati(numeri['costituzione'])} token), "
        f"{numeri['file_skill']} skill, totale {numeri['totale'] // 1024} KB"
    )
    print("  ok   nessun testo dinamico in testa")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
