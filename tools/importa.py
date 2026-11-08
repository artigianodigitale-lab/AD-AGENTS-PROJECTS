#!/usr/bin/env python3
"""Importa un progetto da un altro motore, e lo tratta come nuovo.

Perche' esiste (`GOV-027`). Il CEO ha detto il 2026-11-07: *«Se prendo un «8. Progetto» lui
deve fregarsene che stava in un'altra cartella e trattarlo come se fosse un nuovo
progetto da analizzare e sviluppare»*.

Una cartella progetto che viene da un altro motore porta con se' tre cose che non deve
portarsi qui:

  1. **la sua storia git** — commit, branch, remote di un'altra macchina;
  2. **i file che portano istruzioni** — `AGENTS.md`, `CLAUDE.md`, regole di `.cursor/`:
     un agente li legge come propri ordini, e sono ordini di un'altra casa (`ERR-0090`);
  3. **il suo vecchio `governance/`** — contratti e approvazioni di un'altra macchina.
     Inerti, ma confusionari: questo motore guarda i suoi registri, e quelli vecchi
     mentirebbero su cosa e' stato approvato qui.

L'import fa tre cose, in quest'ordine: **copia** senza la zavorra, **disattiva** i file
che portano ordini, **toglie** la vecchia governance. Poi **verifica** che il cancello
protegga il progetto — perche' un progetto importato che il cancello non vede e' un
progetto indifeso, non un progetto nuovo.

## Perche' disattiva invece di cancellare

`ERR-0090` insegna che un file di istruzioni non fa danno finche' qualcuno lo legge come
tale. Rinominarlo in `*.disattivato` toglie l'effetto e conserva l'informazione: chi vuole
sapere cosa diceva l'altra macchina, lo legge; chi non lo sa, non lo esegue.

Uso:
    python3 tools/importa.py --da <percorso> --come "<nome>"     # importa
    python3 tools/importa.py --da <percorso> --dry-run           # dice cosa farebbe

Esito: 0 importato e protetto · 1 qualcosa manca · 2 uso sbagliato.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]

#: Cosa non si copia: zavorra che non serve a lavorare.
ESCLUSI = shutil.ignore_patterns(
    ".git",
    "node_modules",
    "dist",
    ".next",
    ".nuxt",
    "build",
    "backups",
    "__pycache__",
    "*.pyc",
    ".venv",
    "venv",
    ".cache",
)

#: I file che un agente legge come propri ordini. Si **disattivano**, non si cancellano:
#: togliere l'effetto, conservare l'informazione (`ERR-0090`).
ISTRUZIONI = (
    "AGENTS.md",
    "CLAUDE.md",
    "GEMINI.md",
    ".cursorrules",
)

#: Le cartelle che contengono regole di altri strumenti.
CARTELLE_ISTRUZIONI = (".cursor", ".claude", ".agents", ".devin")

#: La vecchia memoria del progetto: contratti e approvazioni di un'altra macchina.
#: Inerte, ma mentirebbe su cosa e' stato approvato **qui**.
VECCHIA_GOVERNANCE = "governance"


def importa(da: Path, come: str | None = None, asciutto: bool = False,
            radice: Path | None = None) -> int:
    """Importa un progetto. Restituisce l'exit code."""
    base = Path(radice) if radice is not None else RADICE

    if not da.is_dir():
        print(f"  NO   {da} non e' una cartella", file=sys.stderr)
        return 2

    nome = come if come else da.name
    destinazione = base / nome
    if destinazione.exists():
        print(f"  NO   {nome} esiste gia': non sovrascrivo un progetto", file=sys.stderr)
        return 1

    print(f"  da:          {da}")
    print(f"  come:        {nome}")
    print(f"  destinazione {destinazione}")

    if asciutto:
        print("\n  PROVA (non scrive niente)")
        print("  Da copiare, escludendo: .git, node_modules, dist, build, backups, cache")
        print("  Da disattivare: " + ", ".join(ISTRUZIONI))
        print(f"  Da togliere:    {VECCHIA_GOVERNANCE}/ (la memoria di un'altra macchina)")
        return 0

    # 1. Copia senza zavorra
    print("\n  COPIA")
    shutil.copytree(da, destinazione, ignore=ESCLUSI, symlinks=True)
    print(f"  {nome}/ copiato")

    # 2. Toglie la vecchia governance
    vecchia = destinazione / VECCHIA_GOVERNANCE
    if vecchia.is_dir():
        shutil.rmtree(vecchia, ignore_errors=True)
        print(f"  {VECCHIA_GOVERNANCE}/ tolto: era la memoria di un'altra macchina")

    # 3. Disattiva i file che portano ordini
    print("\n  DISATTIVAZIONE")
    disattivati: list[str] = []
    for istruzione in ISTRUZIONI:
        file = destinazione / istruzione
        if file.is_file():
            nuovo_nome = destinazione / f"{istruzione}.disattivato"
            file.rename(nuovo_nome)
            disattivati.append(f"{istruzione} -> {nuovo_nome.name}")
    for cartella in CARTELLE_ISTRUZIONI:
        regole = destinazione / cartella
        if regole.is_dir():
            nuova = destinazione / f"{cartella}.disattivato"
            if not nuova.exists():
                regole.rename(nuova)
                disattivati.append(f"{cartella}/ -> {nuova.name}/")
    if disattivati:
        for voce in disattivati:
            print(f"  {voce}")
    else:
        print("  nessun file di istruzioni trovato")

    # 4. Verifica: il cancello lo vede come progetto?
    print("\n  VERIFICA")
    checker = base / "tools" / "contract_scope.py"
    if not checker.is_file():
        print(f"  NO   manca {checker}: non posso verificare il cancello", file=sys.stderr)
        return 1
    prova = f"{nome}/README.md"
    esito = subprocess.run(
        [sys.executable, str(checker), "check", prova],
        cwd=str(base), capture_output=True, text=True, timeout=120,
    )
    if esito.returncode != 0:
        print(f"  ok   il cancello protegge «{nome}»: nessun contract lo copre ancora")
        print("       E' il punto di partenza giusto: il primo lavoro sara' il primo contract")
        return 0
    print(
        f"  NO   il cancello NON protegge «{nome}»: una scrittura passerebbe senza permesso",
        file=sys.stderr,
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    analizzatore = argparse.ArgumentParser(
        description="Importa un progetto da un altro motore, e lo tratta come nuovo."
    )
    analizzatore.add_argument("--da", required=True, help="la cartella del progetto da importare")
    analizzatore.add_argument("--come", help="il nome con cui importarlo (numerato)")
    analizzatore.add_argument("--dry-run", action="store_true", help="dice cosa farebbe")
    args = analizzatore.parse_args(argv)

    return importa(Path(args.da), args.come, asciutto=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
