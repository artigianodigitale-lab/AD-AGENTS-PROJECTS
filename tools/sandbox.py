#!/usr/bin/env python3
"""Esegue un comando dentro una sandbox vera (M2, `DEC-0112`).

Perche' esiste. Il motore esegue codice — suoi strumenti, e in futuro quello che scarica
dal web. Fino a oggi l'unica difesa era il `write_scope` del contract: un confine di
**autorizzazione**, non di **capacita'**. La differenza conta quando il codice e' sbagliato
o ostile: un contract valido non impedisce a un comando di aprire una connessione o di
leggere `~/.ssh`.

Cosa fa bubblewrap (`bwrap`), e cosa NON fa:

  - rete **spenta** per default (`--unshare-net`): si accende solo con `--rete`;
  - filesystem in **sola lettura**; `/tmp` e `$HOME` scrivibili solo dentro la sandbox;
  - niente PID esterni (`--unshare-pid`), niente variabili d'ambiente ereditate;
  - `--scrittura DIR` e' l'unico modo per dare una cartella scrivibile all'esterno.

**Limite dichiarato:** questa sandbox riguarda cio' che il motore esegue come comando. Non
incapsula DSH e non incapsula il modello: quelli sono il programma che ci ospita, non un
file che possiamo scrivere. Chi ha bisogno di quel confine piu' forte deve metterlo a livello
di sistema operativo (`SECURITY.md`, sezione «Limiti»).

Uso:
    python3 tools/sandbox.py --autotest                 # prova che le difese funzionano
    python3 tools/sandbox.py -- python3 -c 'print(1)'   # esegue un comando, rete spenta
    python3 tools/sandbox.py --rete -- curl -sI https://example.com
    python3 tools/sandbox.py --scrittura /tmp/build -- make

Esito: 0 il comando e' riuscito (o l'autotest e' verde), 1 comando fallito,
       2 sandbox non disponibile / uso sbagliato.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]
TMP = Path("/tmp")


def bwrap_disponibile() -> str | None:
    return shutil.which("bwrap")


def comando_bwrap(
    comando: list[str],
    *,
    rete: bool = False,
    scrittura: tuple[Path, ...] = (),
    cwd: Path | None = None,
    nascondi: tuple[Path, ...] = (),
) -> list[str]:
    """Costruisce il comando bubblewrap. Solleva se `bwrap` manca."""
    bwrap = bwrap_disponibile()
    if bwrap is None:
        raise FileNotFoundError(
            "bubblewrap non e' installato: la sandbox non c'e'. Installalo (`sudo apt install bubblewrap`) "
            "oppure dichiara che il comando gira senza confini."
        )
    parti = [
        bwrap,
        "--die-with-parent",
        "--unshare-pid",
        "--ro-bind", "/", "/",
        "--dev", "/dev",
        "--proc", "/proc",
        "--tmpfs", "/tmp",
        "--chdir", str((cwd or RADICE).resolve()),
    ]
    if not rete:
        parti += ["--unshare-net"]
    for cartella in scrittura:
        parti += ["--bind", str(cartella.resolve()), str(cartella.resolve())]
    # `--tmpfs` sopra una cartella la rende VUOTA dentro la sandbox: si usa per non far
    # leggere al codice generato cio' che non deve (per esempio la chiave di firma in ~/.dsh).
    for nascosto in nascondi:
        parti += ["--tmpfs", str(nascosto.resolve())]
    parti += [
        "--clearenv",
        "--setenv", "PATH", "/usr/local/bin:/usr/bin:/bin",
        "--setenv", "HOME", "/tmp",
        "--setenv", "LANG", "C.UTF-8",
        "--",
    ]
    return parti + list(comando)


def esegui(
    comando: list[str],
    *,
    rete: bool = False,
    scrittura: tuple[Path, ...] = (),
    cwd: Path | None = None,
    timeout: int = 120,
    env: dict[str, str] | None = None,
    nascondi: tuple[Path, ...] = (),
) -> subprocess.CompletedProcess:
    """Esegue il comando nella sandbox. `env` serve solo alle prove: il figlio non lo vede.

    L'ambiente EXTRA viene passato al processo `bwrap`, non al comando: dentro la
    sandbox `--clearenv` lo azzera comunque. Serve a poter dimostrare che l'azzeramento
    avviene davvero (una prova che non puo' fallire non prova niente).
    """
    ambiente = {**os.environ, **env} if env else None
    return subprocess.run(
        comando_bwrap(comando, rete=rete, scrittura=scrittura, cwd=cwd, nascondi=nascondi),
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(cwd or RADICE),
        env=ambiente,
    )


def _probe(testo: str) -> list[str]:
    return ["/bin/sh", "-c", testo]


def autotest() -> int:
    """Prova che le tre promesse della sandbox sono vere, non scritte."""
    if bwrap_disponibile() is None:
        print("SKIP — bubblewrap non installato: nessuna sandbox da provare")
        return 2

    # Controllo della prova, prima della prova: fuori dalla sandbox la sentinella si
    # vede. Se non si vedesse, «dentro non si vede» sarebbe vero per caso, e il test
    # sull'ambiente non proverebbe niente.
    fuori = subprocess.run(
        _probe("test -n \"$AD_SEGRETO_DI_PROVA\""),
        env={**os.environ, "AD_SEGRETO_DI_PROVA": "1"},
        capture_output=True,
    )
    if fuori.returncode != 0:
        print("  NO   la sentinella, fuori, non si vede: la prova sull'ambiente e' invalida")
        return 1

    prove = [
        (
            "la rete e' spenta",
            esegui(_probe(
                "python3 -c \"import socket,sys; s=socket.socket(); s.settimeout(2); "
                "s.connect(('1.1.1.1',443))\" 2>/dev/null"
            )),
            lambda esito: esito.returncode != 0,
        ),
        (
            "dentro /tmp si scrive",
            esegui(_probe("echo prova > /tmp/sandbox-prova && cat /tmp/sandbox-prova")),
            lambda esito: esito.returncode == 0 and "prova" in esito.stdout,
        ),
        (
            "fuori da /tmp non si scrive",
            esegui(_probe("echo prova > /etc/sandbox-prova 2>/dev/null")),
            lambda esito: esito.returncode != 0,
        ),
        (
            "l'ambiente non si eredita",
            # La sentinella viene passata al processo padre: DENTRO la sandbox deve
            # sparire. Senza impostarla, la prova sarebbe tautologica (vuoto perche'
            # nessuno l'ha mai messa), e una prova che non puo' fallire non prova niente.
            esegui(
                _probe("test -z \"$AD_SEGRETO_DI_PROVA\""),
                env={"AD_SEGRETO_DI_PROVA": "1"},
            ),
            lambda esito: esito.returncode == 0,
        ),
    ]
    # Una cartella nascosta non si legge, una non nascosta si'. Il controllo «si legge»
    # serve a dimostrare che la prova non e' tautologica (se la sandbox non partisse,
    # entrambe sarebbero leggibili e il secondo controllo sarebbe l'unico rosso).
    # La cartella di prova sta FUORI da /tmp: la sandbox maschera /tmp con un tmpfs,
    # quindi una cartella in /tmp non sarebbe leggibile nemmeno senza nasconderla.
    import uuid

    _cartella = Path.home() / ".cache" / f"ad-sandbox-prova-{uuid.uuid4().hex}"
    _cartella.mkdir(parents=True)
    (_cartella / "chiave").write_text("x", encoding="utf-8")
    try:
        prove.append((
            "una cartella non nascosta si legge",
            esegui(_probe(f"test -r {_cartella}/chiave")),
            lambda esito: esito.returncode == 0,
        ))
        prove.append((
            "una cartella nascosta NON si legge",
            esegui(_probe(f"test -r {_cartella}/chiave"), nascondi=(_cartella,)),
            lambda esito: esito.returncode != 0,
        ))
    finally:
        shutil.rmtree(_cartella, ignore_errors=True)

    falliti = 0
    for nome, esito, atteso in prove:
        ok = atteso(esito)
        print(f"  {'ok  ' if ok else 'NO  '} {nome}")
        if not ok:
            falliti += 1
            print(f"       exit={esito.returncode} stdout={esito.stdout.strip()[:120]!r} stderr={esito.stderr.strip()[:120]!r}")
    if falliti:
        print(f"\nesito: ROSSO — {falliti} promesse della sandbox non reggono")
        return 1
    print("\nesito: la sandbox fa quello che dichiara")
    return 0


def main(argv: list[str] | None = None) -> int:
    analizzatore = argparse.ArgumentParser(
        description="Esegue un comando in una sandbox bubblewrap",
        usage="%(prog)s [--autotest] [--rete] [--scrittura DIR] [--timeout N] -- <comando...>",
    )
    analizzatore.add_argument("--autotest", action="store_true", help="prova le difese e esce")
    analizzatore.add_argument("--rete", action="store_true", help="concede la rete (default: spenta)")
    analizzatore.add_argument("--scrittura", action="append", default=[], metavar="DIR",
                              help="cartella scrivibile oltre a /tmp (ripetibile)")
    analizzatore.add_argument("--timeout", type=int, default=120)
    analizzatore.add_argument("--nascondi", action="append", default=[], metavar="DIR",
                              help="cartella resa vuota dentro la sandbox, per non leggerla (ripetibile)")
    analizzatore.add_argument("--cwd", default="")
    analizzatore.add_argument("comando", nargs=argparse.REMAINDER,
                              help="il comando, dopo `--`")
    args = analizzatore.parse_args(argv)

    if args.autotest:
        return autotest()

    comando = args.comando
    if comando and comando[0] == "--":
        comando = comando[1:]
    if not comando:
        print("serve un comando dopo `--` (oppure --autotest)", file=sys.stderr)
        return 2
    cwd = Path(args.cwd) if args.cwd else None
    try:
        esito = esegui(comando, rete=args.rete,
                       scrittura=tuple(Path(c) for c in args.scrittura),
                       cwd=cwd, timeout=args.timeout,
                       nascondi=tuple(Path(c) for c in args.nascondi))
    except FileNotFoundError as errore:
        print(f"  {errore}", file=sys.stderr)
        return 2
    except subprocess.TimeoutExpired:
        print(f"  il comando ha superato {args.timeout}s ed e' stato fermato", file=sys.stderr)
        return 1
    if esito.stdout:
        sys.stdout.write(esito.stdout)
    if esito.stderr:
        sys.stderr.write(esito.stderr)
    return esito.returncode


if __name__ == "__main__":
    raise SystemExit(main())
