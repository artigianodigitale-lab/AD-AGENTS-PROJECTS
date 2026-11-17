#!/usr/bin/env python3
"""Prova di installazione pulita — M1, `DEC-0111`.

La promessa di M1 e' una frase verificabile: **una copia del motore, senza i progetti e
senza i dati locali, diventa una macchina accesa.** Questo file la esegue:

  1. copia i file **tracciati** del motore in una cartella temporanea (niente progetti,
     niente `sede.yaml`, niente `backup/`, niente `studio/`);
  2. esegue `tools/init.py` la' dentro: crea la sede e i registri, e **verifica** da solo
     di averli creati;
  3. chiede l'accensione con `tools/accendi.py --senza-macchina` (i controlli della
     macchina — profili DSH, MCP — non si applicano a una copia);
  4. controlla che nella copia non ci siano cartelle numerate: il motore non contiene
     progetti.

Si esegue dalla radice:
    python3 tests/test_installazione_pulita.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]
FALLITI: list[str] = []


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    if condizione:
        print(f"  ok   {etichetta}")
    else:
        print(f"  NO   {etichetta}  {dettaglio}")
        FALLITI.append(etichetta)


def _git(*argomenti: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *argomenti], cwd=str(RADICE), capture_output=True, text=True
    )


def copia_tracciata(destinazione: Path) -> int:
    """Copia i soli file tracciati, conservando i collegamenti relativi."""
    esito = _git("ls-files", "-z")
    if esito.returncode != 0:
        raise SystemExit(f"git ls-files fallisce: {esito.stderr.strip()}")
    copiati = 0
    for nome in esito.stdout.split("\0"):
        if not nome:
            continue
        origine = RADICE / nome
        if not origine.exists() and not origine.is_symlink():
            continue
        arrivo = destinazione / nome
        arrivo.parent.mkdir(parents=True, exist_ok=True)
        if origine.is_symlink():
            os.symlink(os.readlink(origine), arrivo)
        else:
            shutil.copy2(origine, arrivo)
        copiati += 1
    return copiati


def main() -> int:
    print("installazione pulita del motore")

    with tempfile.TemporaryDirectory(prefix="prova-installazione-") as tmp:
        base = Path(tmp) / "motore"
        base.mkdir()

        copiati = copia_tracciata(base)
        check("la copia contiene i file del motore", copiati > 300, f"copiati {copiati}")

        numerate = sorted(
            voce.name
            for voce in base.iterdir()
            if voce.is_dir() and voce.name.split(".")[0].isdigit()
        )
        check("la copia non contiene progetti", not numerate, str(numerate))
        check("la copia non ha sede.yaml", not (base / "sede.yaml").exists())

        init = subprocess.run(
            [sys.executable, str(base / "tools" / "init.py"),
             "--nome", "Motore di prova", "--ceo", "Prova"],
            cwd=str(base), capture_output=True, text=True, timeout=300,
        )
        testo_init = (init.stdout + init.stderr).strip()
        check("init.py esce 0", init.returncode == 0, testo_init[-400:])
        check("init.py crea sede.yaml", (base / "sede.yaml").is_file())

        accensione = subprocess.run(
            [sys.executable, str(base / "tools" / "accendi.py"), "--senza-macchina"],
            cwd=str(base), capture_output=True, text=True, timeout=300,
        )
        testo = (accensione.stdout + accensione.stderr).strip()
        check(
            "accendi.py --senza-macchina dice che l'engine e' acceso",
            accensione.returncode == 0 and "L'ENGINE E' ACCESO" in testo,
            testo[-400:],
        )
        check("la copia resta senza progetti", not any(
            voce.is_dir() and voce.name.split(".")[0].isdigit()
            for voce in base.iterdir()
        ))

        print("  (la cartella di prova viene rimossa: nessun residuo)")
    print()
    if FALLITI:
        print(f"FALLITI: {len(FALLITI)}")
        return 1
    print("PASS — una copia pulita del motore si installa e si accende")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
