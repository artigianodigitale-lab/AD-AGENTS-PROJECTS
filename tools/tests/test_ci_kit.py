#!/usr/bin/env python3
"""Il profilo «kit» di `tests/ci.py` (`DEC-0127`).

Su un kit appena scaricato non ci sono progetti, client MCP né registri usati: alcuni
controlli leggono la macchina e sarebbero rossi per costruzione. Il profilo `--kit` li
**dichiara** e non li esegue; questo test prova che il filtro è quello dichiarato e che il
resto della batteria resta eseguito.

    python3 tools/tests/test_ci_kit.py
"""

from __future__ import annotations

import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE / "tests"))

import ci  # noqa: E402

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
    print("l'elenco dei controlli ambiente e' dichiarato")
    check("e' un insieme non vuoto", bool(ci.CONTROLLI_AMBIENTE))
    check("contiene i cinque controlli che leggono il mondo",
          len(ci.CONTROLLI_AMBIENTE) == 5, str(sorted(ci.CONTROLLI_AMBIENTE)))
    for nome in ("test-arti", "test-100-aap", "test-mcp", "test-sandbox", "test-prodotti"):
        check(f"{nome} e' dichiarato ambiente", nome in ci.CONTROLLI_AMBIENTE)
    for nome in ("coerenza", "drift", "test-sicurezza", "test-codice", "test-memoria"):
        check(f"{nome} NON e' ambiente (un suo rosso resta rosso)", nome not in ci.CONTROLLI_AMBIENTE)

    print("\nil profilo kit esegue il resto e non i controlli ambiente")
    eseguiti: list[str] = []

    def runner(comando: list[str]) -> tuple[int, str]:
        eseguiti.append(comando[1] if len(comando) > 1 else "")
        return 0, ""

    esiti = ci.verifica("kit", runner=runner)
    nomi_eseguiti = {esito.controllo.nome for esito in esiti}
    check("nessun controllo ambiente e' stato eseguito",
          not (nomi_eseguiti & ci.CONTROLLI_AMBIENTE), str(sorted(nomi_eseguiti & ci.CONTROLLI_AMBIENTE)))
    check("gli altri controlli sono stati eseguiti",
          len(nomi_eseguiti) == len(ci.controlli_fast()) - len(ci.CONTROLLI_AMBIENTE),
          f"{len(nomi_eseguiti)} eseguiti")
    check("con runner verde il profilo kit e' verde", ci.fallimenti(esiti) == [])
    check("il test del profilo kit e' nella batteria", "test-ci-kit" in nomi_eseguiti)

    print("\naccendi: il ripiego vale solo per i controlli ambiente")
    sys.path.insert(0, str(RADICE / "tools"))
    import accendi

    solo_ambiente = accendi._fallimenti("verifica\nFALLITO  test-mcp\nFALLITO  test-arti\n")
    check("il parse legge i nomi dei falliti", solo_ambiente == ["test-mcp", "test-arti"], str(solo_ambiente))
    check("le rosse solo-ambiente sono riconosciute",
          set(solo_ambiente) <= accendi._controlli_ambiente())
    misto = accendi._fallimenti("FALLITO  coerenza\nFALLITO  verbali\n")
    check("una rossa vera NON e' coperta dal ripiego",
          not set(misto) <= accendi._controlli_ambiente(), str(misto))
    check("nemmeno una coerenza rotta e' coperta",
          not set(["coerenza"]) <= accendi._controlli_ambiente())
    check("accendi usa la stessa fonte di ci.py",
          accendi._controlli_ambiente() == ci.CONTROLLI_AMBIENTE)

    print("\nil profilo kit non e' il profilo veloce")
    veloce = {c.nome for c in ci.controlli_fast()}
    check("il veloce contiene i controlli ambiente", ci.CONTROLLI_AMBIENTE <= veloce)

    print()
    print(f"  {PASSATI} controlli passati")
    if FALLITI:
        print(f"FALLITI: {len(FALLITI)}")
        return 1
    print("PASS — il profilo kit dichiara la macchina e salva il resto")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
