#!/usr/bin/env python3
"""Inizializza un motore nuovo: la struttura minima, e la prova che è accesa.

Perche' esiste. Il repository pubblico contiene la vetrina e gli strumenti, ma **non i
registri**: contratti, approvazioni, decisioni, errori. Quelli sono la memoria di una
casa, e ogni casa ha la sua. Chi scarica il motore non deve ricevere la memoria di
qualcun altro — deve poter costruire la propria.

Questo comando fa quello: prende una cartella e la trasforma in una macchina funzionante.

    python3 tools/init.py --nome "My Studio" --ceo "Mario Rossi"

Cosa crea:

    sede.yaml              chi e' il CEO, e come si chiama questa macchina
    contratti/             il registro delle autorizzazioni
    approvazioni/          i marcatori firmati del CEO
    DECISIONI/             i verbali immutabili
    errori/                le cicatrici, con «cosa lo avrebbe preso»
    evidenze/              le prove dei gate
    drift/                 le divergenze fra documenti e realta'
    piani/                 le proposte in attesa
    .gitignore             il confine: progetti, segreti, cache

E poi **verifica**: esegue `accendi.py` e dice se il motore e' davvero acceso. Se non lo
e', dice cosa manca — non dichiara «fatto» e va via.

## Perche' non copia `.brain/`

Il cervello — la costituzione, le dieci procedure, il plugin — viaggia con il repository:
e' la ragione per cui il repository esiste. Ma il cervello **non contiene la memoria**:
contiene le regole. La memoria la crea chi lavora.

## Perche' non sovrascrive

Un `sede.yaml` esistente e' la carta d'identita' della casa. Riscriverlo cambierebbe chi
comanda, e chi comanda non si cambia con un comando: si cambia con una decisione.

Uso:
    python3 tools/init.py --nome "Nome" --ceo "Nome CEO"
    python3 tools/init.py --nome "Nome" --ceo "Nome" --dry-run    # dice cosa farebbe
    python3 tools/init.py --verifica                              # solo il controllo

Esito: 0 motore pronto · 1 qualcosa manca · 2 uso sbagliato.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]

#: Le cartelle che ogni motore deve avere. Sono **vuote** quando nasce: le riempie il
#: lavoro, non l'installazione. Un registro precompilato sarebbe la memoria di qualcun
#: altro, ed e' la cosa che questo comando esiste per non fare.
CARTELLE = (
    "contratti",
    "approvazioni",
    "DECISIONI",
    "errori",
    "evidenze",
    "drift",
    "piani",
)

#: Cosa mette in ogni cartella: un file che dice a cosa serve. Non un registro vuoto —
#: una spiegazione, che tiene la cartella in git senza fingere di essere contenuto.
SENSO = {
    "contratti": "Le autorizzazioni: chi puo' scrivere dove. Vuoto = nessun permesso concesso.",
    "approvazioni": "I marcatori firmati del CEO. Vuoto = nessuna proposta approvata.",
    "DECISIONI": "I verbali immutabili: cosa si e' scelto, e perche'.",
    "errori": "Le cicatrici: cosa e' fallito, cosa l'ha risolto, cosa lo avrebbe preso.",
    "evidenze": "Le prove dei gate: cosa e' stato verificato, e da chi.",
    "drift": "Le divergenze fra i documenti e la realta'.",
    "piani": "Le proposte in attesa di una decisione.",
}

#: Il `.gitignore` di un motore nuovo. Lo stesso confine del repository pubblico, perche'
#: la lezione e' la stessa: i progetti e i segreti non entrano nel repository.
GITIGNORE = """\
# -- Progetti ----------------------------------------------------------------
# Una cartella progetto ha un numero davanti: "01. Nome Del Progetto". Quel numero e'
# cio' che dice al motore che la cartella va protetta. Non deve finire nel repository.
/[0-9][0-9]*/
/[0-9][0-9]*.*/

# -- Segreti -----------------------------------------------------------------
*.key
*.pem
.env
.env.*
.ad-consenso.key

# -- Stato locale ------------------------------------------------------------
/.cache/
/backup/
*.log
__pycache__/
*.pyc
.DS_Store
"""


def _sede(nome: str, ceo: str) -> str:
    """Il file che dice chi comanda, e come si chiama questa macchina."""
    from datetime import date

    oggi = date.today().isoformat()
    return (
        "# Chi e' il CEO e dove stanno i progetti.\n"
        "# Creato da `tools/init.py`. Non si versiona: e' tuo.\n"
        "\n"
        "ceo:\n"
        f'  nome: "{ceo}"\n'
        '  ruolo: "CEO"\n'
        f'  dal: "{oggi}"\n'
        "\n"
        "macchina:\n"
        f'  nome: "{nome}"\n'
        "  # Dove stanno i progetti, se non accanto al motore. Vuoto = accanto.\n"
        '  progetti: ""\n'
        f'  avviata: "{oggi}"\n'
    )


def crea(nome: str, ceo: str, asciutto: bool = False, radice: Path | None = None) -> list[tuple[str, str]]:
    """Crea la struttura del motore. Restituisce (cosa, esito) per ogni passo."""
    base = Path(radice) if radice is not None else RADICE
    esiti: list[tuple[str, str]] = []

    # 1. La sede. Se c'e' gia', non si sovrascrive: e' la carta d'identita' della casa.
    sede = base / "sede.yaml"
    if sede.exists():
        esiti.append(("sede.yaml", "c'e' gia': non tocco chi e' il CEO"))
    elif asciutto:
        esiti.append(("sede.yaml", f"da creare (CEO: {ceo}, macchina: {nome})"))
    else:
        sede.write_text(_sede(nome, ceo), encoding="utf-8")
        esiti.append(("sede.yaml", f"creato (CEO: {ceo})"))

    # 2. Le cartelle dei registri, ognuna col suo senso.
    for cartella in CARTELLE:
        percorso = base / cartella
        if percorso.is_dir():
            esiti.append((f"{cartella}/", "c'e' gia'"))
            continue
        if asciutto:
            esiti.append((f"{cartella}/", "da creare"))
            continue
        percorso.mkdir(parents=True, exist_ok=True)
        (percorso / "README.md").write_text(
            f"# {cartella}\n\n{SENSO[cartella]}\n",
            encoding="utf-8",
        )
        esiti.append((f"{cartella}/", "creata con il suo README"))

    # 3. Il confine.
    gitignore = base / ".gitignore"
    if gitignore.exists():
        esiti.append((".gitignore", "c'e' gia': non lo tocco"))
    elif asciutto:
        esiti.append((".gitignore", "da creare"))
    else:
        gitignore.write_text(GITIGNORE, encoding="utf-8")
        esiti.append((".gitignore", "creato"))

    return esiti


def verifica(radice: Path | None = None) -> int:
    """Esegue `accendi.py` e riporta. 0 se l'engine e' acceso, 1 se no."""
    base = Path(radice) if radice is not None else RADICE
    accendi = base / "tools" / "accendi.py"
    if not accendi.is_file():
        print(f"  NO   manca {accendi}: il motore e' incompleto", file=sys.stderr)
        return 1
    esito = subprocess.run(
        [sys.executable, str(accendi), "--senza-macchina"],
        cwd=str(base),
        capture_output=True,
        text=True,
        timeout=180,
    )
    print((esito.stdout + esito.stderr).rstrip())
    return esito.returncode


def main(argv: list[str] | None = None) -> int:
    analizzatore = argparse.ArgumentParser(
        description="Crea la struttura di un motore nuovo, e prova che sia accesa."
    )
    analizzatore.add_argument("--nome", help="il nome di questa macchina")
    analizzatore.add_argument("--ceo", help="il nome del CEO")
    analizzatore.add_argument(
        "--dry-run", action="store_true", help="dice cosa farebbe, senza scrivere"
    )
    analizzatore.add_argument(
        "--verifica", action="store_true", help="controlla soltanto, senza creare niente"
    )
    args = analizzatore.parse_args(argv)

    if args.verifica:
        return verifica()

    if not args.nome or not args.ceo:
        print(
            "  servono --nome e --ceo: un motore senza un CEO non sa per chi lavora",
            file=sys.stderr,
        )
        return 2

    print(f"  macchina: {RADICE}")
    print(f"  nome:     {args.nome}")
    print(f"  CEO:      {args.ceo}")
    print()
    if args.dry_run:
        print("  PROVA (non scrive niente)")
    else:
        print("  CREAZIONE")
    for cosa, esito in crea(args.nome, args.ceo, asciutto=args.dry_run):
        print(f"  {cosa:20} {esito}")

    if args.dry_run:
        print()
        print("  Per creare davvero: rilancia senza --dry-run")
        return 0

    print()
    print("  VERIFICA")
    return verifica()


if __name__ == "__main__":
    raise SystemExit(main())
