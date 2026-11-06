#!/usr/bin/env python3
"""Il cancello che distingue leggere da scrivere (GOV-018, 2026-11-06).

Perche' esiste. Il 2026-11-06 il cancello ha bloccato **tre comandi di sola lettura in
un'ora**: un `python3 -c` che apriva file per leggerli, un `grep` su un elenco di file, e
un comando con la redirezione dei messaggi d'errore. Ogni blocco era falso, e ognuno
costava un giro di lavoro.

La regola che avevo gia' imparato e non avevo applicato qui (ERR-0088): **un controllo che
accusa comandi legittimi insegna a disattivarlo, che e' peggio di non averlo.**

Il caso centrale e' la redirezione. Il segno di maggiore non vuol dire sempre «scrive un
file»:

  scrive:     `> file`   `>> file`   `2> file`   `&> file`   `>file`
  non scrive: `2>&1`     `>&2`       verso il pozzo nero dei messaggi

La prima versione del pattern trattava ogni `>` come scrittura: cosi' un comando che
mandava i messaggi d'errore nel pozzo nero veniva rifiutato come «scrittura su tools/», e
il rifiuto era falso — il comando non scriveva nessun file.

Si esegue dalla radice:
    python3 tools/tests/test_cancello_preciso.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE / "tools"))

import ad_scope  # noqa: E402

FALLITI: list[str] = []

#: Il pozzo nero dei messaggi, scritto in un pezzo per non finire nel comando stesso.
POZZO = "/dev/" + "null"


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    if condizione:
        print(f"  ok   {etichetta}")
    else:
        print(f"  NO   {etichetta}  {dettaglio}")
        FALLITI.append(etichetta)


def scrittura(comando: str) -> bool:
    """Il comando sembra modificare il filesystem?"""
    return any(p.search(comando) for p in ad_scope.MUTATION_PATTERNS)


def test_redirezioni_che_scrivono() -> None:
    """Le redirezioni con una destinazione vera restano scritture: qui non si allarga niente."""
    print("\nle redirezioni che scrivono")
    for comando in (
        "python3 x.py > fuori.txt",
        "python3 x.py >> fuori.txt",
        "python3 x.py 2> errori.txt",
        "python3 x.py &> tutto.txt",
        "python3 x.py >fuori.txt",
        "echo x > tools/ad_scope.py",
    ):
        check(f"scrive: {comando}", scrittura(comando))


def test_redirezioni_che_non_scrivono() -> None:
    """I messaggi nel pozzo nero non scrivono file: erano il falso positivo."""
    print("\nle redirezioni che non scrivono")
    for comando in (
        "python3 tools/stato.py render 2>&1",
        f"python3 tools/stato.py render >{POZZO}",
        f"python3 tools/stato.py render 2>{POZZO}",
        f"python3 tools/stato.py render > {POZZO}",
        "python3 tools/stato.py render >&2",
        "timeout 400 python3 tests/ci.py 2>&1 | tail -3",
    ):
        check(f"non scrive: {comando}", not scrittura(comando))


def test_confronti_non_sono_redirezioni() -> None:
    """I confronti non sono redirezioni: erano gia' esclusi, e restano esclusi."""
    print("\nconfronti e frecce")
    for comando in ("test a >= b", "echo a->b", "echo a ==> b"):
        check(f"non scrive: {comando}", not scrittura(comando))


def test_i_comandi_veri_che_mi_hanno_bloccato() -> None:
    """I comandi di sola lettura che il cancello ha fermato: misurati, non immaginati."""
    print("\ni comandi che mi hanno bloccato")
    casi = (
        "grep -l pattern contratti/societa/GOV-018.yaml",
        f"python3 tools/stato.py render >{POZZO} 2>&1; python3 tests/ci.py 2>&1 | grep prefisso",
        "cat tools/README.md | head -3",
    )
    for comando in casi:
        check(f"ora passa: {comando[:58]}", not scrittura(comando))


def test_le_scritture_vere_restano_bloccate() -> None:
    """La correzione non allarga il permesso: le scritture vere restano scritture."""
    print("\nle scritture vere")
    for comando in (
        "rm -rf tools/",
        "cp file tools/",
        "sed -i 's/a/b/' tools/x.py",
        "git checkout -- tools/",
        "pip install qualcosa",
        "echo x >> tools/README.md",
        "mkdir tools/nuova",
    ):
        check(f"scrive: {comando}", scrittura(comando))


def test_il_verificatore_concorda() -> None:
    """`check-command` del verificatore vero: un composto con i messaggi nel pozzo non e' scrittura."""
    print("\nil verificatore vero")
    comando = f"python3 tools/stato.py render >{POZZO} 2>&1; echo fatto"
    esito = subprocess.run(
        [
            sys.executable,
            str(RADICE / "tools" / "contract_scope.py"),
            "check-command",
            comando,
            "--cwd",
            str(RADICE),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    check(
        "il composto con i messaggi nel pozzo e' ammesso",
        esito.returncode == 0,
        (esito.stdout + esito.stderr)[:160],
    )


def main() -> int:
    print("il cancello che distingue leggere da scrivere")
    test_redirezioni_che_scrivono()
    test_redirezioni_che_non_scrivono()
    test_confronti_non_sono_redirezioni()
    test_i_comandi_veri_che_mi_hanno_bloccato()
    test_le_scritture_vere_restano_bloccate()
    test_il_verificatore_concorda()
    print()
    if FALLITI:
        print(f"FALLITO — {len(FALLITI)} controlli: " + ", ".join(FALLITI))
        return 1
    print("PASS — legge e scrive si distinguono, e le scritture vere restano negate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
