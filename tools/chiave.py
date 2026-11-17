#!/usr/bin/env python3
"""La chiave di firma: quella che rende un consenso un consenso.

Perche' esiste. Le approvazioni del CEO sono firmate con HMAC-SHA256, e la chiave vive
**fuori** dal repository — scelta giusta, e per questo il 2026-11-08 l'analisi di
`100.AAP` ha trovato una mancanza precisa: `~/.dsh/ad-consenso.key` esiste solo su questo
PC. Su un altro PC:

    nessuna chiave  ->  nessuna firma  ->  nessuna approvazione
                    ->  nessun contract  ->  il cancello blocca tutto

Un motore acceso e inutilizzabile. E' peggio di un motore spento, perche' sembra vivo.

## La regola che questo comando rispetta: non rigenera una chiave

Se la chiave c'e', si usa. Rigenerarla **invaliderebbe ogni approvazione gia' firmata**:
le firme vecchie non tornerebbero, e il registro direbbe `tampered` su documenti che
nessuno ha toccato. Percio' `--rigenera` esiste, ma e' esplicito e dice cosa rompe.

## La regola che questo comando rispetta: la chiave non si legge

`--check` verifica tre cose e non stampa mai il contenuto:
  1. esiste
  2. e' leggibile **solo dal proprietario** (`0600`): una chiave leggibile dagli altri
     non e' una chiave
  3. ha la lunghezza giusta (32 byte)
E dice quante approvazioni dipendono da lei: cosi' chi la tocca sa quanto costa.

Uso:
    python3 tools/chiave.py                  # crea la chiave se manca
    python3 tools/chiave.py --check          # verifica, senza scrivere
    python3 tools/chiave.py --rigenera       # DISTRUGGE le firme esistenti
    python3 tools/chiave.py --home /tmp/x    # su una home diversa (per le prove)

Esito: 0 a posto · 1 problema · 2 uso sbagliato.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import stat
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]

#: Dove vive la chiave, **fuori** dal repository. Un segreto in un repository e' un
#: segreto che qualcuno ha gia' letto.
PERCORSO_CHIAVE = Path(".dsh") / "ad-consenso.key"

#: Quanti byte. Trentadue bastano per HMAC-SHA256 e sono la convenzione di `ad_consenso`.
BYTE = 32

#: Dove stanno le approvazioni da cui dipende la chiave.
CARTELLA_APPROVAZIONI = "approvazioni"


def _home(esplicita: Path | None) -> Path:
    if esplicita is not None:
        return Path(esplicita).expanduser().resolve()
    return Path.home()


def _percorso_chiave(home: Path) -> Path:
    return home / PERCORSO_CHIAVE


def quante_approvazioni() -> int:
    """Quante approvazioni firmate esistono. Serve a dire quanto costa rigenerare."""
    cartella = RADICE / CARTELLA_APPROVAZIONI
    if not cartella.is_dir():
        return 0
    return sum(1 for p in cartella.rglob("*.yaml") if p.is_file())


def controlla(home: Path) -> list[tuple[str, bool, str]]:
    """Verifica la chiave, senza stamparne il contenuto."""
    esiti: list[tuple[str, bool, str]] = []
    chiave = _percorso_chiave(home)

    if not chiave.is_file():
        esiti.append(("esiste", False, f"manca {chiave}: nessuna approvazione si puo' firmare"))
        return esiti
    esiti.append(("esiste", True, str(chiave)))

    # I permessi: una chiave leggibile dagli altri non e' una chiave.
    modo = stat.S_IMODE(chiave.stat().st_mode)
    solo_proprietario = modo & (stat.S_IRWXG | stat.S_IRWXO) == 0
    esiti.append(
        (
            "permessi",
            solo_proprietario,
            f"0{modo:o}" + (" (solo il proprietario)" if solo_proprietario else
                            " — leggibile da altri: va corretto con --check e poi a mano"),
        )
    )

    # La lunghezza, senza leggere il valore in chiaro: solo quanti byte.
    dimensione = chiave.stat().st_size
    esiti.append(
        ("lunghezza", dimensione >= BYTE, f"{dimensione} byte (servono almeno {BYTE})")
    )

    return esiti


def crea(home: Path, rigenera: bool = False, asciutto: bool = False) -> int:
    """Crea la chiave se manca. Non la rigenera senza chiedere."""
    chiave = _percorso_chiave(home)
    print(f"  home: {home}")
    print(f"  chiave: {chiave}")
    print()

    if chiave.is_file() and not rigenera:
        approvazioni = quante_approvazioni()
        print(f"  ok   la chiave c'e' gia': non la tocco.")
        print(f"       {approvazioni} approvazioni dipendono da lei. Rigenerarla le")
        print("       invaliderebbe tutte: le firme vecchie non tornerebbero.")
        return 0

    if rigenera and chiave.is_file():
        approvazioni = quante_approvazioni()
        print(f"  ATTENZIONE: questo DISTRUGGE le firme esistenti.")
        print(f"  {approvazioni} approvazioni diventerebbero «tampered».")
        if asciutto:
            print("  (prova: non ho fatto niente)")
            return 0

    if asciutto:
        print(f"  ..   creerei una chiave di {BYTE} byte con permessi 0600")
        return 0

    chiave.parent.mkdir(parents=True, exist_ok=True)
    # `secrets` e non `random`: questa e' una chiave, non un numero per una prova.
    valore = secrets.token_bytes(BYTE)
    # `os.open` con i permessi giusti NASCE 0600: creare e poi correggere lascerebbe
    # una finestra in cui il file e' leggibile dagli altri.
    descrittore = os.open(
        str(chiave),
        os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
        stat.S_IRUSR | stat.S_IWUSR,
    )
    try:
        os.write(descrittore, valore)
    finally:
        os.close(descrittore)
    os.chmod(chiave, stat.S_IRUSR | stat.S_IWUSR)

    print(f"  ok   chiave creata: {BYTE} byte, permessi 0600 (solo il proprietario)")
    print("       Da questo momento un consenso si puo' firmare su questa macchina.")
    return 0


def main(argv: list[str] | None = None) -> int:
    analizzatore = argparse.ArgumentParser(
        description="La chiave di firma: la crea se manca, e verifica che sia sana."
    )
    analizzatore.add_argument("--check", action="store_true", help="verifica, senza scrivere")
    analizzatore.add_argument("--rigenera", action="store_true", help="DISTRUGGE le firme esistenti")
    analizzatore.add_argument("--home", help="la home su cui lavorare (per le prove)")
    analizzatore.add_argument("--json", action="store_true", help="esito in JSON")
    args = analizzatore.parse_args(argv)

    home = _home(Path(args.home) if args.home else None)

    if args.check:
        esiti = controlla(home)
        if args.json:
            print(json.dumps(
                [{"controllo": c, "ok": ok, "dettaglio": d} for c, ok, d in esiti],
                ensure_ascii=False, indent=2,
            ))
            return 0 if all(ok for _, ok, _ in esiti) else 1
        print(f"  home:   {home}")
        print(f"  chiave: {_percorso_chiave(home)}")
        print()
        for controllo, ok, dettaglio in esiti:
            print(f"  {'ok  ' if ok else 'NO  '} {controllo:10} {dettaglio}")
        print()
        print(f"  {quante_approvazioni()} approvazioni dipendono da questa chiave.")
        if all(ok for _, ok, _ in esiti):
            return 0
        print("  La chiave non e' a posto: senza, nessun consenso si puo' firmare.")
        return 1

    return crea(home, rigenera=args.rigenera)


if __name__ == "__main__":
    raise SystemExit(main())
