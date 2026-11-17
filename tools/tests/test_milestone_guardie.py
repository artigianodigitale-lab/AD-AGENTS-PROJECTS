#!/usr/bin/env python3
"""Una tappa chiusa non si riapre (`ERR-0019`, `DEC-0122`).

Prima: `scaffold_sprint` non guardava lo stato della milestone. Ora lo legge dal blocco YAML
del rapporto e rifiuta se la tappa e' `chiusa`/`chiusa`.

La prima versione della guardia rifiutava quando il `REPORT.md` **esisteva**: ma
`scaffold_milestone` lo scrive all'apertura con `stato: aperta`, quindi il flusso di
produzione era rotto (trovato dalla revisione indipendente di ENG-058). Questo test chiama il
flusso vero: `scaffold_milestone` e poi `scaffold_sprint`.

    python3 tools/tests/test_milestone_guardie.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE / "tools"))

import ad_milestone  # noqa: E402

# La prova e' sulla guardia della tappa, non sull'autorita' dei percorsi: i progetti finti
# vivono in /tmp, fuori dall'albero di autorita'. Il cancello vero e' provato altrove.
ad_milestone.ad_scope.guard = lambda target, root=None: None

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


def _progetto(base: Path) -> Path:
    progetto = base / "1. Prova"
    progetto.mkdir()
    return progetto


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="ad-milestone-") as tmp:
        base = Path(tmp)
        progetto = _progetto(base)

        print("il flusso di produzione non si rompe")
        # `new-milestone` scrive il REPORT con `stato: aperta`: `new-sprint` deve funzionare.
        ad_milestone.scaffold_milestone(progetto, "obiettivo di prova")
        try:
            percorso = ad_milestone.scaffold_sprint(progetto, 1)
            check("milestone aperta: lo sprint si apre", percorso.is_file(), str(percorso))
        except (ValueError, PermissionError) as e:
            check("milestone aperta: lo sprint si apre", False, f"{type(e).__name__}: {e}")

        print("\nuna tappa chiusa non si riapre")
        rapporto = progetto / "Analisi-Prompt-Report" / "Milestone 1" / "REPORT.md"
        testo = rapporto.read_text(encoding="utf-8").replace("stato: aperta", "stato: chiusa")
        rapporto.write_text(testo, encoding="utf-8")
        errore = None
        try:
            ad_milestone.scaffold_sprint(progetto, 1)
        except ValueError as e:
            errore = e
        check("scaffold_sprint rifiuta una tappa chiusa", errore is not None)
        if errore:
            check("il messaggio dice che la tappa e' chiusa",
                  "e' chiusa" in str(errore), str(errore))
            check("il messaggio dice la via d'uscita (tappa nuova o REJECT)",
                  "tappa nuova" in str(errore) or "REJECT" in str(errore), str(errore))

    print()
    print(f"  {PASSATI} controlli passati")
    if FALLITI:
        print(f"FALLITI: {len(FALLITI)}")
        return 1
    print("PASS — la tappa chiusa non si riapre, e quella aperta funziona")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
