#!/usr/bin/env python3
"""Il Blueprint distingue rapporto assente, parziale e chiuso (`ERR-0044`, `DEC-0122`).

Prima: ogni passo non chiuso era «aperto, senza rapporto», anche quando il `REPORT.md`
esisteva ma era incompleto. Il Blueprint e' un documento sigillato: se dice il falso, il
sigillo certifica il falso.

    python3 tools/tests/test_blueprint_stati.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE / "tools"))

import blueprint  # noqa: E402

FALLITI: list[str] = []
PASSATI = 0

SEZIONI = "\n\n".join(f"## {sezione}\n\ncontenuto" for sezione in blueprint.SEZIONI_RAPPORTO)


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    global PASSATI
    if condizione:
        print(f"  ok   {etichetta}")
        PASSATI += 1
    else:
        print(f"  NO   {etichetta}  {dettaglio}")
        FALLITI.append(etichetta)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="ad-blueprint-") as tmp:
        base = Path(tmp)

        assente = base / "assente.md"
        check("nessun file: assente", blueprint._stato_rapporto(assente) == "assente")

        parziale = base / "parziale.md"
        parziale.write_text("## Cosa e' stato fatto\n\nsolo questa\n", encoding="utf-8")
        check("rapporto con una sezione: parziale",
              blueprint._stato_rapporto(parziale) == "parziale")

        completo = base / "completo.md"
        completo.write_text(SEZIONI, encoding="utf-8")
        check("rapporto con tutte le sezioni: chiuso",
              blueprint._stato_rapporto(completo) == "chiuso")

    print("\nil testo del Blueprint non confonde i due casi")
    sorgente = (RADICE / "tools" / "blueprint.py").read_text(encoding="utf-8")
    check("c'e' lo stato «parziale»", "rapporto parziale" in sorgente)
    check("c'e' la distinzione assente/parziale/chiuso",
          "assente" in sorgente and "parziale" in sorgente and "chiuso" in sorgente)

    print()
    print(f"  {PASSATI} controlli passati")
    if FALLITI:
        print(f"FALLITI: {len(FALLITI)}")
        return 1
    print("PASS — il Blueprint dice il vero sui rapporti")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
