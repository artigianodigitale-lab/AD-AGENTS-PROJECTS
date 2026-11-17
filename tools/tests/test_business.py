#!/usr/bin/env python3
"""La tela business: completa e tracciabile si', «bella» no (M7, `DEC-0119`).

Si prova il comportamento sulle tele di esempio:
  - la tela buona passa;
  - senza fonti: fallisce per le righe con cifre e per la sezione Numeri;
  - sezione vuota: fallisce per la sezione;
  - la tela **appena generata** non passa (i segnaposto non sono un'analisi);
  - il check non scrive niente e non cambia il file; niente modello, solo libreria standard.

Si esegue dalla radice:
    python3 tools/tests/test_business.py
"""

from __future__ import annotations

import hashlib
import io
import contextlib
import json
import sys
import tempfile
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE / "tools"))

import business  # noqa: E402

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


def _codici(esito: dict) -> set[str]:
    return {errore["codice"] for errore in esito["errori"]}


def main() -> int:
    campioni = RADICE / "evals" / "business"

    print("le tele di esempio")
    buona = business.check(campioni / "buona.md")
    check("la tela buona passa", buona["ok"] is True, str(buona["errori"])[:300])
    check("la tela buona ha tutte le sezioni", buona["sezioni_trovate"] == 11, str(buona["sezioni_trovate"]))

    senza_fonti = business.check(campioni / "senza-fonti.md")
    check("senza fonti: NON passa", senza_fonti["ok"] is False, str(senza_fonti)[:200])
    check("senza fonti: riga senza fonte e numeri senza fonte",
          {"riga-senza-fonte", "numeri-senza-fonte"} <= _codici(senza_fonti), str(_codici(senza_fonti)))

    vuota = business.check(campioni / "sezione-vuota.md")
    check("sezione vuota: NON passa", vuota["ok"] is False, str(vuota)[:200])
    check("sezione vuota: il motivo e' la sezione", "sezione-vuota" in _codici(vuota), str(_codici(vuota)))

    print("\nla tela generata non e' un'analisi")
    with tempfile.TemporaryDirectory(prefix="ad-business-") as tmp:
        percorso = Path(tmp) / "tela.md"
        generata = business.main(["genera", "--progetto", "Prova", "--out", str(percorso)])
        check("genera scrive la tela", generata == 0 and percorso.is_file())
        esito = business.check(percorso)
        check("la tela generata NON passa", esito["ok"] is False, str(esito)[:200])
        check("il motivo e' il segnaposto", "segnaposto" in _codici(esito), str(_codici(esito)))

        # Il check e' di sola lettura.
        prima = hashlib.sha256(percorso.read_bytes()).hexdigest()
        business.check(percorso)
        dopo = hashlib.sha256(percorso.read_bytes()).hexdigest()
        check("il check non cambia il file", prima == dopo)

        # La CLI JSON e' leggibile e deterministica.
        cattura = io.StringIO()
        with contextlib.redirect_stdout(cattura):
            codice = business.main(["check", str(campioni / "buona.md"), "--json"])
        dati = json.loads(cattura.getvalue())
        check("la CLI JSON esce 0 sulla tela buona", codice == 0 and dati["ok"] is True, cattura.getvalue()[:200])

        # Un file inesistente e' un errore d'uso (2), non un verde.
        cattura = io.StringIO()
        with contextlib.redirect_stdout(cattura):
            codice = business.main(["check", str(Path(tmp) / "non-esiste.md")])
        check("file inesistente: uso sbagliato (2)", codice == 2, str(codice))

    print("\ni casi limite del parser (ERR-0105)")
    base = (campioni / "buona.md").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="ad-business-limiti-") as tmp:
        def _controlla(nome: str, contenuto: str, atteso: str) -> None:
            percorso = Path(tmp) / nome
            percorso.write_text(contenuto, encoding="utf-8")
            esito = business.check(percorso)
            check(f"{nome}: NON passa e cita {atteso}",
                  esito["ok"] is False and atteso in _codici(esito), str(_codici(esito)))

        finta = base.replace(
            "— fonte: file interno analisi-vendite.pdf — 2026-09-30",
            "— fonte: ignota — 2026-09-30",
        )
        _controlla("fonte-finta.md", finta, "fonte-non-valida")

        fuori = "Budget complessivo: 5000 euro.\n\n" + base
        _controlla("fuori-sezione.md", fuori, "fuori-sezione")

        non_numerata = base.replace("## 3. Problema", "## Problema", 1)
        _controlla("titolo-non-numerato.md", non_numerata, "sezione-non-numerata")

        duplicata = base + "\n## 1. Richiesta\n\nRipetuta per errore.\n"
        _controlla("sezione-duplicata.md", duplicata, "sezione-duplicata")

        # CR-1: un nome di file con una data dentro resta valido.
        nome_con_data = base.replace(
            "— fonte: file interno analisi-vendite.pdf — 2026-09-30",
            "— fonte: analisi-2026-01-01.pdf — 2026-09-30",
        )
        percorso = Path(tmp) / "nome-con-data.md"
        percorso.write_text(nome_con_data, encoding="utf-8")
        esito = business.check(percorso)
        check("un file con una data nel nome resta una fonte valida",
              esito["ok"] is True, str(_codici(esito)))

        # CR-2: dopo un titolo non numerato, una cifra non e' «prima della prima sezione».
        dopo_non_numerata = base.replace(
            "## 3. Problema",
            "## Problema\n\nBudget: 5000 euro.\n",
            1,
        )
        percorso = Path(tmp) / "dopo-non-numerata.md"
        percorso.write_text(dopo_non_numerata, encoding="utf-8")
        esito = business.check(percorso)
        check("dopo un titolo non numerato il motivo e' il titolo, non la sezione",
              "fuori-sezione" not in _codici(esito) and "sezione-non-numerata" in _codici(esito),
              str(_codici(esito)))

    print("\nil limite e' dichiarato")
    testo = (RADICE / "tools" / "business.py").read_text(encoding="utf-8")
    check("il tool dichiara che non giudica la strategia", "non la qualita'" in testo)
    check("il tool dichiara che non verifica la fonte", "non verifica la fonte" in testo or "non verifica" in testo)

    print()
    print(f"  {PASSATI} controlli passati")
    if FALLITI:
        print(f"FALLITI: {len(FALLITI)}")
        return 1
    print("PASS — la tela e' verificabile, e i suoi limiti sono scritti")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
