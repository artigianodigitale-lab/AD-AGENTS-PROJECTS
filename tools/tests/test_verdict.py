#!/usr/bin/env python3
"""Due difetti del validatore che producevano REJECT falsi (M2, `DEC-0112`).

Trovati dalla revisione indipendente di M2, non dal lavoro:

1. `ad_evidence.DATA_HINTS` cercava `db` come **sottostringa**: `db` sta dentro
   `sandbox`, quindi un contract che tocca `tools/sandbox.py` sembrava toccare un
   database, e un'evidenza onesta con `database: NO` diventava INVALID. Il rimedio
   suggerito era scrivere `NOT_VERIFIED`: un finto verde per far passare il gate.
2. `tools/verdict.py --evidence a --evidence b` teneva solo l'ultimo file: il secondo
   gate risultava MISSING anche con l'evidenza depositata.

Questo test li tiene chiusi: la parola si cerca a inizio parola, e le evidenze si
accumulano sia con il flag ripetuto sia con la forma a elenco.

Si esegue dalla radice:
    python3 tools/tests/test_verdict.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE / "tools"))

import ad_evidence  # noqa: E402

FALLITI: list[str] = []

CONTRATTO = RADICE / "contratti" / "societa" / "ENG-041.yaml"
EVIDENZE = [
    RADICE / "evidenze" / "ENG-041-Security.yaml",
    RADICE / "evidenze" / "ENG-041-CodeReview.yaml",
]


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    if condizione:
        print(f"  ok   {etichetta}")
    else:
        print(f"  NO   {etichetta}  {dettaglio}")
        FALLITI.append(etichetta)


def test_parola_non_sottostringa() -> None:
    print("\nla parola si cerca a inizio parola")
    check("sandbox NON tocca il database", not ad_evidence.tocca_dati("tools/sandbox.py"))
    check("test_sandbox NON tocca il database", not ad_evidence.tocca_dati("tools/tests/test_sandbox.py"))
    check("db/migrations tocca il database", ad_evidence.tocca_dati("db/migrations/001.sql"))
    check("schema/ tocca il database", ad_evidence.tocca_dati("schema/users.sql"))
    check("migrations/ tocca il database", ad_evidence.tocca_dati("4. Progetto/migrations"))
    check("database tocca il database", ad_evidence.tocca_dati("config/database.yml"))


def test_evidenze_ripetute() -> None:
    print("\nle evidenze si accumulano")
    if not CONTRATTO.is_file() or not all(e.is_file() for e in EVIDENZE):
        print("  SKIP — le evidenze di ENG-041 non ci sono in questa copia")
        return
    for nome, argomenti in (
        (
            "flag ripetuto",
            ["--evidence", str(EVIDENZE[0]), "--evidence", str(EVIDENZE[1])],
        ),
        ("forma a elenco", ["--evidence", str(EVIDENZE[0]), str(EVIDENZE[1])]),
    ):
        esito = subprocess.run(
            [sys.executable, str(RADICE / "tools" / "verdict.py"),
             "--contract", str(CONTRATTO), *argomenti],
            cwd=str(RADICE), capture_output=True, text=True, timeout=120,
        )
        testo = esito.stdout + esito.stderr
        check(f"{nome}: Security e' PASS", "Security" in testo and "PASS" in testo, testo[-300:])
        check(f"{nome}: Code Review e' PASS", "Code Review" in testo and "PASS" in testo, testo[-300:])
        check(f"{nome}: verdetto ACCEPT", "verdetto: ACCEPT" in testo, testo[-300:])


def main() -> int:
    test_parola_non_sottostringa()
    test_evidenze_ripetute()
    print()
    if FALLITI:
        print(f"FALLITI: {len(FALLITI)}")
        return 1
    print("PASS — il validatore non produce piu' REJECT falsi su questi due casi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
