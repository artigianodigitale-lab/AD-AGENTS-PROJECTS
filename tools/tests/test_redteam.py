#!/usr/bin/env python3
"""L'eval di iniezione morde (M2, `DEC-0112`).

Un eval che passa sempre non e' un eval. Questo test esegue `tools/redteam.py` e pretende
che i casi **provabili** passino: un manifest alterato va rosso, un tool fuori allowlist non
passa, un'istruzione mascherata viene riconosciuta, un traversal viene rifiutato, una
scrittura non coperta viene negata, una chiave larga viene rifiutata, un segreto tracciato
viene trovato. Se una prova non e' possibile (bubblewrap o gitleaks assenti) il caso e'
`skip`, e il test lo dice invece di fingere un verde.

Si esegue dalla radice:
    python3 tools/tests/test_redteam.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
FALLITI: list[str] = []


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    if condizione:
        print(f"  ok   {etichetta}")
    else:
        print(f"  NO   {etichetta}  {dettaglio}")
        FALLITI.append(etichetta)


def main() -> int:
    print("eval di iniezione sui controlli")
    esito = subprocess.run(
        [sys.executable, str(RADICE / "tools" / "redteam.py"), "--json"],
        cwd=str(RADICE), capture_output=True, text=True, timeout=300,
    )
    try:
        dati = json.loads(esito.stdout)
    except json.JSONDecodeError:
        check("l'eval produce JSON", False, (esito.stdout + esito.stderr)[-300:])
        print("\nFALLITI: 1")
        return 1

    check("l'eval produce JSON", True)
    check("nessun caso fallito", dati.get("falliti") == 0, str([e for e in dati["esiti"] if e["stato"] == "fail"]))
    check("gli skip sono dichiarati", all(
        e["stato"] in ("pass", "fail", "skip") for e in dati["esiti"]
    ))
    check("ci sono almeno 6 casi provati", casi_provati(dati) >= 6,
          f"pass={dati['passati']} skip={dati['saltati']}")
    check("l'esito umano esce 0", esito.returncode == 0, (esito.stdout + esito.stderr)[-200:])

    print()
    if FALLITI:
        print(f"FALLITI: {len(FALLITI)}")
        return 1
    print("PASS — i controlli mordono sui casi provabili")
    return 0


def casi_provati(dati: dict) -> int:
    """Casi che hanno davvero provato qualcosa (pass): e' il numero che conta."""
    return sum(1 for e in dati.get("esiti", []) if e["stato"] == "pass")


if __name__ == "__main__":
    raise SystemExit(main())
