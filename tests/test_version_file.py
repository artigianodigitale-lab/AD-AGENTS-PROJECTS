"""La versione del motore non e' un numero di comodo.

Il 2026-10-30 il `VERSION` del motore e' stato portato a `9.9.9 / 2026-10-31` da una
scrittura esterna che nessun contract copriva (ERR-0078): un valore identico a una fixture di
test. Questo controllo lo avrebbe preso: la versione nel file deve essere quella che l'ultimo
commit che ha toccato `VERSION` dichiara nel proprio messaggio.
"""

from __future__ import annotations

import re
import subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "VERSION"


def _righe() -> list[str]:
    return [r.strip() for r in VERSION_FILE.read_text(encoding="utf-8").splitlines() if r.strip()]


def test_version_file_has_version_and_date() -> None:
    righe = _righe()
    assert len(righe) == 2, f"VERSION deve avere due righe (versione, data), ne ha {len(righe)}"
    assert re.fullmatch(r"\d+\.\d+\.\d+", righe[0]), f"versione non semver: {righe[0]!r}"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", righe[1]), f"data non ISO: {righe[1]!r}"


def test_version_date_is_not_in_the_future() -> None:
    anno, mese, giorno = (int(p) for p in _righe()[1].split("-"))
    assert date(anno, mese, giorno) <= date.today(), "VERSION dichiara una data futura"


def test_version_is_the_one_the_last_commit_declares() -> None:
    versione = _righe()[0]
    try:
        stato = subprocess.run(
            ["git", "-C", str(ROOT), "status", "--porcelain", "--", "VERSION"],
            capture_output=True, text=True, check=True,
        ).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):  # senza git non si puo' verificare
        return
    if stato:
        # In staging: il commit non e' ancora fatto, quindi il suo messaggio non esiste.
        # Il controllo sul messaggio lo fa il giro successivo (dopo il commit). Se invece
        # il file e' modificato SENZA staging, e' una scrittura fuori dal cancello: ERR-0078.
        if stato[0][:1] == " ":
            raise AssertionError(
                "VERSION modificato senza staging: una scrittura fuori dal cancello "
                "(ERR-0078). Mettilo in staging e dichiara la versione nel messaggio del commit."
            )
        return
    try:
        result = subprocess.run(
            ["git", "-C", str(ROOT), "log", "-1", "--format=%s", "--", "VERSION"],
            capture_output=True, text=True, check=True,
        )
    except (OSError, subprocess.CalledProcessError):  # senza git non si puo' verificare
        return
    messaggio = result.stdout.strip()
    assert versione in messaggio, (
        f"VERSION dice {versione!r} ma l'ultimo commit che lo ha toccato dice {messaggio!r}: "
        "sospetta una scrittura fuori dal cancello (ERR-0078)"
    )


def _main() -> int:
    """Esecuzione diretta (la macchina usa script, non pytest)."""
    controlli = (
        test_version_file_has_version_and_date,
        test_version_date_is_not_in_the_future,
        test_version_is_the_one_the_last_commit_declares,
    )
    falliti = 0
    for controllo in controlli:
        try:
            controllo()
        except AssertionError as errore:
            print(f"FAIL {controllo.__name__}: {errore}")
            falliti += 1
    print(f"esito: {'OK' if not falliti else f'{falliti} controlli falliti'}")
    return 0 if not falliti else 1


if __name__ == "__main__":
    raise SystemExit(_main())
