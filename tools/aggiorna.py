#!/usr/bin/env python3
"""Aggiornamenti: c'e' una versione nuova? e cosa cambia dei MIEI dati?

    python3 tools/aggiorna.py check          # confronta la versione locale con quella remota
    python3 tools/aggiorna.py mostra         # cosa cambierebbe, file per file
    python3 tools/aggiorna.py applica        # aggiorna il MOTORE, senza toccare i tuoi dati

Perche' esiste, in una riga: **chi ha clonato il motore ha i suoi dati dentro la stessa
cartella** — contratti, approvazioni, cicatrici, verbali — e un aggiornamento ingenuo glieli
cancella. Questo comando e' la linea fra **il motore**, che si sostituisce, e **i dati**, che
non si toccano **mai**.

La differenza, in una frase:

    Il motore e' codice: si aggiorna. I dati sono tuoi: si tengono.
    Un permesso che hai scritto ieri non deve sparire perche' oggi e' uscita una versione.

E tre regole che il comando rispetta, e che valgono piu' della comodita':

1. **Non cancella niente senza prima mostrarlo.** `applica` chiede conferma e scrive un
   backup in `.aggiornamento/backup-<data>/` prima di toccare il primo file.
2. **Non tocca mai i dati** (`DATI`): ne' per aggiornarli, ne' per "sistemarli".
3. **Non fa il merge al posto tuo.** Se hai **modificato** un file del motore, `applica` **non
   lo sovrascrive**: te lo dice, e quel file resta tuo finche' non decidi. Il vecchio che legge
   il nuovo e' **un agente**, non questo programma: questo gli prepara il lavoro.

Uscita:
    0  fatto (o nessun aggiornamento disponibile)
    1  c'e' un aggiornamento, o qualcosa da decidere (check/mostra)
    2  argomenti sbagliati, o niente git e niente versione remota
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]

#: **Il motore.** Cio' che si sostituisce aggiornando. Se un file qui dentro non e' stato
#: modificato da chi usa il motore, si prende la versione nuova senza discutere.
#:
#: Elenco **dichiarato**, non dedotto: dedurlo («tutto tranne i dati») vorrebbe dire che una
#: cartella nuova e sconosciuta finisce nel motore, e viene sovrascritta. Il contrario di
#: quello che serve.
MOTORE = (
    ".brain",
    "tools",
    "VERSION",
    "AGENTS.md",
    "README.md",
    "README.it.md",
    "GLOSSARY.md",
    "COMMUNITY.md",
    "CONTRIBUTING.md",
    "FORMATO.md",
    "GRAFO.md",
    "DOCUMENTAZIONE-TECNICA.md",
    "GOVERNANCE-AZIENDALE.md",
    "AGENTI-V2.md",
    "AGENT-CARDS-V2.md",
    "AGENT-CARDS-BUSINESS.md",
    "TASK-CONTRACTS.md",
    "RUNTIME.md",
    "QUALITY-GATES.md",
    "SPECIALIZATION.md",
    "COMMUNICATION.md",
    "STRATEGIC-MEMORY.md",
    "MODEL-ROUTING.md",
    "AGENT-PROMPT-TEMPLATE.md",
    "LICENSE",
    "NOTICE",
    "sede.example.yaml",
    ".env.example",
)

#: **I dati di chi usa il motore.** Non si toccano **mai**, in nessun caso, per nessun motivo.
#: Qui dentro c'e' il suo lavoro: i permessi che ha scritto, i sì che ha dato, gli errori che ha
#: incontrato, le decisioni che ha preso.
DATI = (
    "sede.yaml",
    "contratti",
    "approvazioni",
    "errori",
    "DECISIONI",
    "piani",
    "drift",
    "evidenze",
    "REQUISITI",
    "comunicazioni",
    "contributi",
    "evals",
    "orchestrazione",
    "studio",
)


def _git(*args: str, cwd: Path | None = None) -> tuple[int, str]:
    """Esegue git e restituisce (esito, output). Non solleva: git assente e' un caso."""
    try:
        esito = subprocess.run(
            ["git", *args], cwd=str(cwd or RADICE), capture_output=True, text=True, timeout=120
        )
        return esito.returncode, (esito.stdout + esito.stderr).strip()
    except (FileNotFoundError, subprocess.TimeoutExpired) as errore:
        return 2, str(errore)


def versione_locale() -> tuple[str, str]:
    """(versione, data) da `VERSION`. Se manca, lo dice invece di inventare."""
    f = RADICE / "VERSION"
    if not f.is_file():
        return "", ""
    righe = [r.strip() for r in f.read_text(encoding="utf-8").splitlines() if r.strip()]
    return (righe[0] if righe else ""), (righe[1] if len(righe) > 1 else "")


def _remoto() -> str:
    """L'indirizzo del repository da cui si e' clonato, se c'e'."""
    esito, fuori = _git("remote", "get-url", "origin")
    return fuori if esito == 0 else ""


def controlla(quiete: bool = False) -> int:
    """C'e' un aggiornamento? Se non si puo' sapere, lo dice: non finge di saperlo."""
    locale, data_locale = versione_locale()
    if not locale:
        print("  Non c'e' un file VERSION: non so che versione hai. Aggiorna a mano.")
        return 2

    remoto = _remoto()
    if not remoto:
        print(f"  La tua versione: {locale} ({data_locale})")
        print()
        print("  Questa cartella non viene da un `git clone`: non c'e' un repository")
        print("  remoto da interrogare. Per sapere se c'e' una versione nuova, guarda:")
        print("    https://github.com/artigianodigitale-lab/AD-AGENTS-PROJECTS")
        return 2

    esito, _ = _git("fetch", "--quiet", "origin")
    if esito != 0:
        print("  Non ho potuto interrogare il repository remoto (rete assente?).")
        print(f"  La tua versione: {locale} ({data_locale})")
        return 2

    # **Cosa e' stato APPLICATO, non dove sta il ramo.** Un aggiornamento copia i file:
    # `HEAD` resta indietro, e guardare il grafo direbbe "3 aggiornamenti disponibili"
    # per sempre. Il 2026-10-14 e' successo, e un avviso che non si spegne mai e' peggio
    # di nessun avviso: insegna a ignorarlo.
    applicato = _ultimo_applicato()
    if applicato:
        _, dietro = _git("rev-list", "--count", f"{applicato}..origin/main")
    else:
        _, dietro = _git("rev-list", "--count", "HEAD..origin/main")
    _, avanti = _git("rev-list", "--count", "origin/main..HEAD")
    n_dietro = int(dietro or 0)
    n_avanti = int(avanti or 0)

    print(f"  La tua versione:   {locale} ({data_locale})")
    print(f"  Repository:        {remoto}")

    if n_avanti and not n_dietro:
        print("  Stato:             sei AVANTI — hai modifiche tue non ancora pubblicate")
    if n_dietro == 0:
        print("  Stato:             aggiornato")
        if not quiete:
            print()
            print("  Non c'e' niente da scaricare. Il motore e' all'ultima versione.")
        return 0

    print(f"  Stato:             {n_dietro} aggiornamenti disponibili"
          + (f", e {n_avanti} modifiche tue" if n_avanti else ""))
    print()
    print("  **Si consiglia di aggiornare.** Prima guarda cosa cambia:")
    print("      python3 tools/aggiorna.py mostra")
    print("  e poi, quando sei convinto:")
    print("      python3 tools/aggiorna.py applica")
    print()
    print("  I TUOI DATI non vengono toccati: contratti, approvazioni, errori,")
    print("  decisioni, piani, drift. Il motore si aggiorna, il tuo lavoro resta.")
    return 1


def _ultimo_applicato() -> str:
    """Il commit a cui l'ultimo aggiornamento e' arrivato. Vuoto se non si e' mai aggiornato."""
    f = RADICE / ".aggiornamento" / "ultimo.json"
    if not f.is_file():
        return ""
    try:
        return str(json.loads(f.read_text(encoding="utf-8")).get("commit", ""))
    except (ValueError, OSError):
        return ""


def _file_del_motore() -> set[str]:
    """I file del motore presenti nella versione remota, come percorsi relativi."""
    _, fuori = _git("ls-tree", "-r", "--name-only", "origin/main")
    if not fuori:
        return set()
    scelti = set()
    for percorso in fuori.splitlines():
        testa = percorso.split("/", 1)[0]
        if testa in MOTORE or percorso in MOTORE:
            scelti.add(percorso)
    return scelti


def _diversi(percorsi: set[str]) -> tuple[list[str], list[str]]:
    """(da aggiornare, modificati da te). Un file che hai toccato non si sovrascrive."""
    da_aggiornare, tuoi = [], []
    for percorso in sorted(percorsi):
        _, locale = _git("show", f"HEAD:{percorso}")
        _, nuovo = _git("show", f"origin/main:{percorso}")
        if locale == nuovo:
            continue
        esito, _ = _git("diff", "--quiet", "HEAD", "--", percorso)
        (tuoi if esito != 0 else da_aggiornare).append(percorso)
    return da_aggiornare, tuoi


def mostra() -> int:
    """Cosa cambierebbe, e cosa NON cambierebbe. Si guarda prima di applicare."""
    esito = controlla(quiete=True)
    if esito == 2:
        return 2
    if esito == 0:
        return 0

    percorsi = _file_del_motore()
    da_aggiornare, tuoi = _diversi(percorsi)

    print()
    print(f"  ── IL MOTORE: {len(da_aggiornare)} file da aggiornare")
    for percorso in da_aggiornare[:40]:
        print(f"     {percorso}")
    if len(da_aggiornare) > 40:
        print(f"     ...e altri {len(da_aggiornare) - 40}")

    if tuoi:
        print()
        print(f"  ── MODIFICATI DA TE: {len(tuoi)} file del motore che hai toccato")
        for percorso in tuoi[:20]:
            print(f"     {percorso}")
        print()
        print("     **Questi NON vengono sovrascritti.** Sono tuoi: se li aggiornassi")
        print("     perderesti una modifica che hai fatto per una ragione. Il vecchio che")
        print("     legge il nuovo e' un lavoro da agente: guarda `AGGIORNAMENTO.md`.")

    print()
    print(f"  ── I TUOI DATI: {len(DATI)} cartelle e file che NON vengono toccati")
    print(f"     {', '.join(DATI[:8])}...")
    print()
    print("  Se va bene:  python3 tools/aggiorna.py applica")
    return 1


def applica(si: bool = False) -> int:
    """Aggiorna il motore. Backup prima, dati mai, e niente merge al posto tuo."""
    esito = controlla(quiete=True)
    if esito == 2:
        return 2
    if esito == 0:
        print()
        print("  Niente da fare: sei gia' all'ultima versione.")
        return 0

    percorsi = _file_del_motore()
    da_aggiornare, tuoi = _diversi(percorsi)

    if not si:
        print()
        print(f"  Aggiornerei {len(da_aggiornare)} file del motore, e non toccherei i tuoi dati.")
        if tuoi:
            print(f"  Lascierei stare {len(tuoi)} file che hai modificato tu: {', '.join(tuoi[:5])}")
        print()
        print("  Ripeti con `--si` se va bene. Prima viene fatto un backup in")
        print("  `.aggiornamento/backup-<data>/`, cosi' si torna indietro.")
        return 1

    quando = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    backup = RADICE / ".aggiornamento" / f"backup-{quando}"
    scritti = 0
    for percorso in da_aggiornare:
        origine = RADICE / percorso
        if origine.is_file():
            copia = backup / percorso
            copia.parent.mkdir(parents=True, exist_ok=True)
            copia.write_bytes(origine.read_bytes())
        esito_show, contenuto = _git("show", f"origin/main:{percorso}")
        if esito_show != 0:
            continue
        origine.parent.mkdir(parents=True, exist_ok=True)
        origine.write_text(contenuto + "\n", encoding="utf-8")
        scritti += 1

    (RADICE / ".aggiornamento" / "ultimo.json").parent.mkdir(parents=True, exist_ok=True)
    _, commit = _git("rev-parse", "origin/main")
    (RADICE / ".aggiornamento" / "ultimo.json").write_text(
        json.dumps(
            {"quando": quando, "file": scritti, "backup": str(backup), "tuoi": tuoi,
             "commit": commit.strip(), "versione": versione_locale()[0]},
            ensure_ascii=False, indent=2,
        ) + "\n", encoding="utf-8",
    )
    # E il VERSION prende quello nuovo: cosi' `check` sa cosa hai davvero.
    _, nuovo_version = _git("show", "origin/main:VERSION")
    if nuovo_version:
        (RADICE / "VERSION").write_text(nuovo_version.strip() + "\n", encoding="utf-8")

    print()
    print(f"  Aggiornati {scritti} file del motore.")
    print(f"  Backup in:  {backup.relative_to(RADICE)}/")
    if tuoi:
        print()
        print(f"  **{len(tuoi)} file che avevi modificato sono rimasti come li avevi lasciati:**")
        for percorso in tuoi[:10]:
            print(f"     {percorso}")
        print()
        print("  Per allinearli alla versione nuova serve un agente, non una sovrascrittura:")
        print("  vedi `AGGIORNAMENTO.md`.")
    print()
    print("  **I tuoi dati non sono stati toccati.** Contratti, approvazioni, errori,")
    print("  decisioni, piani: come li avevi lasciati.")
    print()
    print("  La cartella da cui hai copiato la versione nuova si puo' cancellare.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aggiornamenti del motore")
    parser.add_argument("comando", choices=("check", "mostra", "applica"))
    parser.add_argument("--si", action="store_true", help="conferma l'aggiornamento")
    args = parser.parse_args(argv)

    if args.comando == "check":
        return controlla()
    if args.comando == "mostra":
        return mostra()
    return applica(si=args.si)


if __name__ == "__main__":
    raise SystemExit(main())
