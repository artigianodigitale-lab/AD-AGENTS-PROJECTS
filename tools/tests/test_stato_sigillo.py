#!/usr/bin/env python3
"""Il sigillo della vista non dipende dal giorno (`ERR-0031`, `ERR-0038`, `DEC-0122`).

Prima: il corpo sigillato di `orchestrazione/stato.md` conteneva «scade fra N giorni». N cambia
ogni giorno, il corpo cambia, e il sigillo si autoinvalida: `stato.py check` diceva MANOMESSO o
INDIETRO per un file autentico — l'allarme diventava rumore.

Ora nel corpo sta la **data** di scadenza, stabile; il conteggio puo' stare fuori dal sigillo.

    python3 tools/tests/test_stato_sigillo.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE / "tools"))

import stato  # noqa: E402

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
    sorgente = (RADICE / "tools" / "stato.py").read_text(encoding="utf-8")
    print("il corpo sigillato non contiene valori che cambiano col tempo")
    check("non c'e' piu' il conteggio nel corpo", "**scade fra" not in sorgente)
    check("il corpo dice la data di scadenza", "scade il" in sorgente)
    check("non c'e' piu' il «(N gg)» (ERR-0038)", "(f\" ({giorni} gg)" not in sorgente)
    check("non c'e' «oggi sono N giorni»", "oggi sono {giorni}" not in sorgente)

    print("\nla generazione e' deterministica e senza numeri relativi a oggi")
    prima = stato.genera_con_sigillo()
    seconda = stato.genera_con_sigillo()
    check("due generazioni identiche a parita' di registri", prima == seconda,
          f"lunghezze {len(prima)} e {len(seconda)}")
    check("il sigillo c'e' ed e' in cima", prima.lstrip().startswith(">"), prima[:80])
    check("nessun «(N gg)» nel corpo sigillato",
          re.search(r"\(\d+ gg\)", prima) is None, str(re.findall(r"\(\d+ gg\)", prima))[:120])
    check("nessun «oggi sono N giorni» nel corpo sigillato", "oggi sono" not in prima)
    check("nessun «scade fra N giorni» nel corpo sigillato", "scade fra" not in prima)
    if "scade il" in prima:
        check("una scadenza vicina e' dichiarata con la data, non coi giorni",
              "scade il" in prima)
    else:
        check("nessuna scadenza vicina: il corpo resta stabile", "scade il" not in prima)

    print()
    print(f"  {PASSATI} controlli passati")
    if FALLITI:
        print(f"FALLITI: {len(FALLITI)}")
        return 1
    print("PASS — il sigillo non si autodistrugge col passare dei giorni")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
