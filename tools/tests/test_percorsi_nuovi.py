#!/usr/bin/env python3
"""Le cartelle nuove non numerate si bloccano (`ERR-0050`, `DEC-0121`).

Prima: la regola guardava `(radice / testa).is_dir()`. Bastava **creare una cartella nuova**
e scriverci dentro: la cartella ancora non esisteva, la condizione era falsa, la scrittura
passava. Ora una scrittura dentro una cartella nuova e non numerata e' un rifiuto, e il
rifiuto dice **quale numero usare**.

    python3 tools/tests/test_percorsi_nuovi.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE / "tools"))

import ad_scope  # noqa: E402

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


def _verdetto(radice: Path, relativo: str):
    return ad_scope.evaluate(radice / relativo, root=radice)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="ad-percorsi-") as tmp:
        radice = Path(tmp)
        (radice / "approvazioni").mkdir()

        print("una cartella nuova e non numerata e' un rifiuto")
        verdetto = _verdetto(radice, "rea-main/AGENTS.md")
        check("la scrittura non e' consentita", verdetto.allowed is False)
        check("il messaggio dice che non e' numerata",
              "non e' numerata" in verdetto.reason, verdetto.reason[:200])
        check("il rifiuto dice il numero da usare",
              "Il prossimo numero libero" in verdetto.reason, verdetto.reason[-160:])

        print("\nle cartelle numerate restano prodotto: serve il contract")
        verdetto = _verdetto(radice, "12. Nuovo/x.md")
        check("cartella numerata: protetta", verdetto.protected is True)
        check("cartella numerata senza contract: negata", verdetto.allowed is False)
        check("il messaggio parla di task contract",
              "task contract" in verdetto.reason, verdetto.reason[:200])

        print("\nla macchina e le sue eccezioni restano scrivibili")
        for etichetta, relativo in [
            ("file di root", "README.md"),
            ("cartella di macchina", "tools/x.py"),
            ("backup (dichiarata)", "backup/repo.bundle"),
        ]:
            verdetto = _verdetto(radice, relativo)
            atteso = etichetta != "cartella di macchina"  # tools/ e' governance: protetta
            check(f"{etichetta}: consentito={atteso}", verdetto.allowed is atteso,
                  f"protetto={verdetto.protected} coperto={verdetto.covered}")

        print("\nil percorso che esce dalla radice non e' una cartella nuova")
        verdetto = ad_scope.evaluate(radice.parent / "altro" / "x.md", root=radice)
        check("percorso fuori radice: nessun blocco 'cartella nuova'",
              "non e' numerata" not in verdetto.reason, verdetto.reason[:160])

    print()
    print(f"  {PASSATI} controlli passati")
    if FALLITI:
        print(f"FALLITI: {len(FALLITI)}")
        return 1
    print("PASS — nessuna cartella nuova nasce senza numero")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
