#!/usr/bin/env python3
"""Lotto A di M10: quattro guardie di registro e gate (`DEC-0123`, `ENG-059`).

Si prova ognuna sul suo punto:
  1. `ERR-0063` — il pre-commit vede le cancellazioni (`--diff-filter=ACMRD`); il brief non
     trasforma un file falsy in una cicatrice finta; l'autodetect non inventa «web».
  2. `DRIFT-019` — un permesso `active` scaduto produce il rilievo `contract-scaduto`.
  3. `DRIFT-029` — i numeri dichiarati nei verbali si confrontano con i misurati.
  4. `DRIFT-021` — AGENTI-V2 dichiara che il Transient Worker non esiste.

    python3 tools/tests/test_m10_lotto_a.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE / "tools"))
sys.path.insert(0, str(RADICE / "tests"))

import ad_contract  # noqa: E402
import gate_kit  # noqa: E402
import verbali  # noqa: E402

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
    print("ERR-0063 — pre-commit, brief, autodetect")
    hook = (RADICE / ".githooks" / "pre-commit").read_text(encoding="utf-8")
    check("il pre-commit vede le cancellazioni", "diff-filter=ACMRD" in hook, hook[:120])
    check("il commento spiega perche' (ERR-0063)", "ERR-0063" in hook)
    check("il gancio controlla anche se stesso (.githooks/*)",
          ".brain/*|.githooks/*|" in hook, hook[hook.find("case"):hook.find("case")+160])

    with tempfile.TemporaryDirectory(prefix="ad-m10-") as tmp:
        base = Path(tmp)
        (base / "errori").mkdir()
        (base / "errori" / "ERR-9999-vuoto.yaml").write_text("[]\n", encoding="utf-8")
        (base / "errori" / "ERR-9998-numero.yaml").write_text("42\n", encoding="utf-8")
        info = gate_kit._registri(base)
        problemi = " ".join(str(p) for p in info["problemi"])
        check("il file vuoto e' detto «vuoto», non una mappatura vuota",
              "ERR-9999-vuoto.yaml vuoto" in problemi, problemi[:240])
        check("un valore non-mappa e' detto «non e' una mappatura»",
              "non e' una mappatura" in problemi, problemi[:240])
        check("non inventa una cicatrice «None: diventa None»",
              all("None:" not in str(e) for e in info["errori"]))

    setup = (RADICE / "tools" / "setup.py").read_text(encoding="utf-8")
    check("l'autodetect non inventa piu' «web»", "return [PROFILO]" not in setup)
    check("la cartella assente restituisce la lista vera (vuota)", "return []" in setup)

    print("\nDRIFT-019 — un permesso scaduto non resta «attivo» in silenzio")
    with tempfile.TemporaryDirectory(prefix="ad-m10-") as tmp:
        base = Path(tmp)
        contract = {
            "task_id": "TST-999",
            "status": "active",
            "expires": "2020-01-01",
        }
        codici = {f.code for f in ad_contract.validate(contract, {}, root=base)}
        check("il rilievo contract-scaduto c'e'", "contract-scaduto" in codici, str(sorted(codici))[:300])

    print("\nDRIFT-029 — i numeri dichiarati si confrontano con i misurati")
    with tempfile.TemporaryDirectory(prefix="ad-m10-") as tmp:
        base = Path(tmp)
        (base / "DECISIONI").mkdir()
        (base / "errori").mkdir()
        (base / "DECISIONI" / "DEC-0001-prova.md").write_text(
            "```yaml\nid: DEC-0001\nstato: approvato\ndata: 2026-01-01\n```\n\n"
            "Nella migrazione c'erano 21 progetti e 72 voci.\n",
            encoding="utf-8",
        )
        _, da_rivedere = verbali.problemi(base)
        testo = " ".join(da_rivedere)
        check("il numero superato e' segnalato",
              "21 progetti invece di" in testo, testo[:240])
        check("il rilievo e' nel registro (non un errore fatale)",
              "DRIFT-029" in testo)

    print("\nDRIFT-021 — il Transient Worker non e' promesso")
    agenti = (RADICE / "AGENTI-V2.md").read_text(encoding="utf-8")
    check("AGENTI-V2 dichiara che non esiste", "Transient Worker non esiste" in agenti)
    check("il match fallito e' spiegato come corretto", "agent-unknown" in agenti)

    print()
    print(f"  {PASSATI} controlli passati")
    if FALLITI:
        print(f"FALLITI: {len(FALLITI)}")
        return 1
    print("PASS — le guardie del lotto A mordono")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
