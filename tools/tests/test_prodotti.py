#!/usr/bin/env python3
"""I prodotti ammessi si derivano dai progetti reali (`DRIFT-002`, `DEC-0122`).

Prima: `KNOWN_PRODUCTS` aveva quattro valori scritti a mano, mentre i progetti sono 18. Un
contract che nominava un prodotto reale finiva segnalato «fuori elenco», e l'elenco vecchio
nascondeva il prodotto sbagliato.

Ora l'elenco unisce i quattro valori **storici** (i contract firmati li citano: non si
rompono) e gli slug dei progetti che esistono davvero.

    python3 tools/tests/test_prodotti.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE / "tools"))

import ad_contract  # noqa: E402

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
    print("i valori storici restano ammessi")
    for valore in ("artigiano-digitale", "ad-stock-tracker", "gamma", "altro"):
        check(f"storico ammesso: {valore}", valore in ad_contract.KNOWN_PRODUCTS)

    print("\nl'elenco si deriva dai progetti reali")
    with tempfile.TemporaryDirectory(prefix="ad-prodotti-") as tmp:
        base = Path(tmp)
        for cartella in ("12. Alfa Uno", "13. Beta", "17. Cliente Uno Project"):
            (base / cartella).mkdir()
        (base / "notes").mkdir()  # non numerata: non e' un progetto
        ammessi = ad_contract.prodotti_conosciuti(base)
        check("progetto nuovo derivato (slug)", "alfa-uno" in ammessi, str(ammessi))
        check("secondo progetto derivato", "beta" in ammessi, str(ammessi))
        check("il numero non finisce nello slug", "cliente-uno-project" in ammessi, str(ammessi))
        check("la cartella non numerata non entra", "notes" not in ammessi, str(ammessi))
        check("«altro» resta ammesso", "altro" in ammessi)

    print("\nse la cartella progetti non e' leggibile, i valori storici bastano")
    with tempfile.TemporaryDirectory(prefix="ad-prodotti-") as tmp:
        ammessi = ad_contract.prodotti_conosciuti(Path(tmp) / "non-esiste")
        check("nessun errore e valori storici presenti",
              set(ad_contract.KNOWN_PRODUCTS) <= set(ammessi), str(ammessi))

    print()
    print(f"  {PASSATI} controlli passati")
    if FALLITI:
        print(f"FALLITI: {len(FALLITI)}")
        return 1
    print("PASS — nessun prodotto reale finisce piu' in «altro» per un elenco vecchio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
