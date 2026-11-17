#!/usr/bin/env python3
"""Il troncamento del testo si dichiara (`ERR-0029`, `DEC-0121`).

Prima: il CLI di `ricerca.py` stampava i primi 4.000 caratteri di una pagina e taceva il
resto. Chi leggeva poteva credere di aver letto tutto. Ora c'e' un avviso con i conteggi e il
richiamo a `--json` per il testo intero.

    python3 tools/tests/test_ricerca_troncamento.py
"""

from __future__ import annotations

import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE / "tools"))

import ricerca  # noqa: E402

FALLITI: list[str] = []
PASSATI = 0


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    global PASSATI
    if condizione:
        print(f"  ok   {etichetta}")
        PASSATI += 1
    else:
        print(f"  NO   {etichetta}  {dettaglio}")
        FALLITI.append(etichetta)


def main() -> int:
    print("una pagina corta non ha avvisi")
    corto = "x" * 100
    check("testo corto: identico", ricerca.testo_da_stampare(corto) == corto)
    check("testo di 4.000 caratteri esatti: nessun avviso",
          ricerca.testo_da_stampare("x" * ricerca.LIMITE_STAMPA) == "x" * ricerca.LIMITE_STAMPA)

    print("\nuna pagina lunga dichiara il taglio")
    lungo = "x" * 5000
    stampa = ricerca.testo_da_stampare(lungo)
    check("il testo mostrato e' il limite, non tutto", stampa.startswith("x" * ricerca.LIMITE_STAMPA))
    check("l'avviso dice quanti caratteri sono omessi", "1000 omessi" in stampa, stampa[-160:])
    check("l'avviso dice il totale", "su 5000" in stampa, stampa[-160:])
    check("l'avviso rimanda a --json", "--json" in stampa, stampa[-160:])
    check("il taglio e' dichiarato con una riga riconoscibile",
          "[testo troncato per il terminale:" in stampa, stampa[-160:])

    print("\nil codice del CLI usa la funzione, non un taglio muto")
    sorgente = (RADICE / "tools" / "ricerca.py").read_text(encoding="utf-8")
    check("il CLI stampa con testo_da_stampare", "print(testo_da_stampare(" in sorgente)
    check("non c'e' piu' il taglio muto sulla pagina",
          'print(esito.get("testo", "")[:4000])' not in sorgente)

    print()
    print(f"  {PASSATI} controlli passati")
    if FALLITI:
        print(f"FALLITI: {len(FALLITI)}")
        return 1
    print("PASS — il taglio del testo non e' piu' silenzioso")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
