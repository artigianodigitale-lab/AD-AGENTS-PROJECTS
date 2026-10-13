#!/usr/bin/env python3
"""Coerenza fra il livello sempre caricato e cio' che il sistema e'.

    python3 tools/coherence.py [--json]

Confronta `.brain/COSTITUZIONE.md` — cio' che ogni agente legge all'avvio — con
la realta': skill, comandi, cartelle, documenti, sequenza dei passi, ganci
globali, plugin montato.

Esito:
    0  la descrizione corrisponde al sistema
    1  almeno una divergenza
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ad_coherence  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Coerenza del livello sempre caricato")
    parser.add_argument("--json", action="store_true", help="output JSON")
    args = parser.parse_args(argv)

    problemi = ad_coherence.problemi()
    if args.json:
        print(json.dumps({"problemi": problemi, "ok": not problemi}, indent=2, ensure_ascii=False))
        return 1 if problemi else 0

    if not problemi:
        skill = len(ad_coherence.skills_nel_cervello())
        comandi = len(ad_coherence.comandi_nel_progetto())
        passi = ad_coherence.sequenza(
            (ad_coherence.ad_docs.DOCS_ROOT / ad_coherence.COSTITUZIONE).read_text(encoding="utf-8")
        )
        print(
            f"OK   il livello sempre caricato corrisponde al sistema: "
            f"{skill} skill, {comandi} comandi, {len(passi)} passi, ganci integri"
        )
        return 0

    for problema in problemi:
        print(f"  {problema}")
    print(f"\nesito: {len(problemi)} divergenze — la descrizione non corrisponde al sistema")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
