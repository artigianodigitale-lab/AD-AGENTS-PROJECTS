#!/usr/bin/env python3
"""La build incrementale: non ripete cio' che non e' cambiato (M5, `DEC-0117`).

Si prova il comportamento, non l'esistenza delle funzioni:
  - primo giro: la fase gira; secondo giro con input invariati: la fase e' SALTATA;
  - modifica di un input: la fase torna a girare;
  - `--forza`: la fase gira anche se invariata;
  - una fase ROSSA non si cacha: il giro dopo la rifa';
  - `pulisca` svuota lo stato; la cache non vive nel repository.

La prova vera usa una fase temporanea con input in una cartella temporanea, cosi' non
dipende dai file del motore; poi si prova anche la fase `sintassi` vera.

Si esegue dalla radice:
    python3 tools/tests/test_build.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE / "tools"))

import build  # noqa: E402

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


def _fase_vera(input_dir: Path, codice: str = "print('ok')") -> dict:
    return {
        "nome": "prova",
        "descrizione": "fase di prova",
        "comando": [sys.executable, "-c", codice],
        "input": [str(input_dir)],
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="ad-build-prova-") as tmp:
        os.environ["AD_BUILD_DIR"] = str(Path(tmp) / "stato")
        input_dir = Path(tmp) / "input"
        input_dir.mkdir()
        (input_dir / "dato.txt").write_text("uno", encoding="utf-8")
        fase = _fase_vera(input_dir)

        print("la build incrementale")
        primo = build.esegui(fasi=[fase])
        check("primo giro: la fase gira", primo["fasi"][0]["stato"] == "eseguita", str(primo))
        check("primo giro: verde", primo["verde"] is True)
        check("primo giro: nessun risparmio", primo["risparmio_stimato_secondi"] == 0)

        secondo = build.esegui(fasi=[fase])
        check("secondo giro: la fase e' saltata", secondo["fasi"][0]["stato"] == "saltata", str(secondo))
        check("secondo giro: risparmio dichiarato", secondo["risparmio_stimato_secondi"] >= 0)

        (input_dir / "dato.txt").write_text("due", encoding="utf-8")
        terzo = build.esegui(fasi=[fase])
        check("input cambiato: la fase torna a girare", terzo["fasi"][0]["stato"] == "eseguita", str(terzo))

        forzato = build.esegui(fasi=[fase], forza=True)
        check("--forza: la fase gira sempre", forzato["fasi"][0]["stato"] == "eseguita", str(forzato))

        # Un rosso non si cacha.
        rossa = _fase_vera(input_dir, codice="raise SystemExit(1)")
        rosso = build.esegui(fasi=[rossa])
        check("fase rossa: esito rosso", rosso["verde"] is False, str(rosso))
        dopo = build.esegui(fasi=[rossa])
        check("un rosso non si cacha: la fase riprova", dopo["fasi"][0]["stato"] == "eseguita", str(dopo))

        pulita = build.esegui(pulisca=True)
        check("pulisca svuota lo stato", pulita.get("pulita") is True and not Path(pulita["stato"]).exists())

        # Guardia: niente cache della build dentro il repository.
        os.environ["AD_BUILD_DIR"] = str(RADICE / "build-vietata")
        try:
            build.cartella_stato()
            check("una cache della build nel repository e' rifiutata", False)
        except build.ErroreBuild:
            check("una cache della build nel repository e' rifiutata", True)
        os.environ["AD_BUILD_DIR"] = str(Path(tmp) / "stato")

        # La fase vera `sintassi`: primo giro eseguita, secondo saltata (se il primo e' verde).
        print("\nla fase vera `sintassi`")
        sintassi = next(f for f in build.FASI if f["nome"] == "sintassi")
        primo_vero = build.esegui(fasi=[sintassi], forza=True, timeout=180)
        check("sintassi: primo giro verde", primo_vero["verde"] is True, str(primo_vero["fasi"]))
        secondo_vero = build.esegui(fasi=[sintassi], timeout=180)
        check("sintassi: secondo giro saltata", secondo_vero["fasi"][0]["stato"] == "saltata", str(secondo_vero))

        os.environ.pop("AD_BUILD_DIR", None)

    print()
    print(f"  {PASSATI} controlli passati")
    if FALLITI:
        print(f"FALLITI: {len(FALLITI)}")
        return 1
    print("PASS — la build salta cio' che non e' cambiato, e lo dice")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
