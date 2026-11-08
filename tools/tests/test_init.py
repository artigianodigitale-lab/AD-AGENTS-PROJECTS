#!/usr/bin/env python3
"""L'inizializzatore deve costruire un motore che funziona (`GOV-020`).

Il criterio che questo file difende: chi scarica il repository pubblico riceve la vetrina
e gli strumenti, ma **non i registri**. Deve poter costruire la propria memoria.

    python3 tools/init.py --nome "X" --ceo "Y"

E soprattutto: **dopo aver creato, verifica**. Non dichiara «fatto» e va via — che è la
lezione di `ERR-0091`, dove un lavoro era stato dichiarato completo senza prova.

Si esegue dalla radice:
    python3 tools/tests/test_init.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]


def _git_init(base: Path) -> None:
    """Un repository di prova, per provare il confine con git vero."""
    import subprocess as _sp

    _sp.run(["git", "init", "-q"], cwd=base, capture_output=True)
    _sp.run(["git", "add", "-A", "-n"], cwd=base, capture_output=True)


def _git_ignora(base: Path, percorso: str) -> bool:
    """git ignora davvero quel percorso?"""
    import subprocess as _sp

    esito = _sp.run(["git", "check-ignore", "-q", percorso], cwd=base, capture_output=True)
    return esito.returncode == 0
sys.path.insert(0, str(RADICE / "tools"))

import init  # noqa: E402

FALLITI: list[str] = []


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    if condizione:
        print(f"  ok   {etichetta}")
    else:
        print(f"  NO   {etichetta}  {dettaglio}")
        FALLITI.append(etichetta)


def test_crea_tutto() -> None:
    """Su una cartella vuota crea sede, sette registri e il confine."""
    print("\ncrea tutto su una cartella vuota")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        esiti = init.crea("Macchina Di Prova", "Prova CEO", radice=base)

        check("sede.yaml esiste", (base / "sede.yaml").is_file())
        check("il CEO è scritto", "Prova CEO" in (base / "sede.yaml").read_text(encoding="utf-8"))
        check("il nome della macchina è scritto",
              "Macchina Di Prova" in (base / "sede.yaml").read_text(encoding="utf-8"))
        for cartella in init.CARTELLE:
            check(f"{cartella}/ esiste", (base / cartella).is_dir())
            check(
                f"{cartella}/README.md dice a cosa serve",
                (base / cartella / "README.md").is_file(),
            )
        check(".gitignore esiste", (base / ".gitignore").is_file())
        # Il pattern deve coprire UNA cifra, non solo due. La versione precedente
        # (`/[0-9][0-9]*/`) lasciava passare "1. Cliente", "8. Progetto" e ogni altra
        # cartella a cifra singola — e questo test le dichiarava corrette, quindi il
        # difetto si propagava in ogni motore nuovo. Ora si prova l'**effetto**: git
        # ignora davvero le cartelle numerate?
        check(
            "il .gitignore tiene fuori i progetti",
            "/[0-9]*/" in (base / ".gitignore").read_text(encoding="utf-8"),
        )
        for nome_cartella in ("1. Cliente", "8. Progetto", "11. Altro", "123. Grande"):
            percorso = base / nome_cartella / "segreto.md"
            percorso.parent.mkdir(parents=True, exist_ok=True)
            percorso.write_text("dato\n", encoding="utf-8")
        _git_init(base)
        for nome_cartella in ("1. Cliente", "8. Progetto", "11. Altro", "123. Grande"):
            check(
                f"git ignora «{nome_cartella}»",
                _git_ignora(base, f"{nome_cartella}/segreto.md"),
                f"{nome_cartella} entra nel repository: il confine ha un buco",
            )
        check(
            "ma i tools restano tracciati",
            not _git_ignora(base, "tools/init.py"),
            "il confine tiene fuori anche il motore",
        )
        check("tutti i passi hanno un esito", len(esiti) >= 9, str(len(esiti)))


def test_non_sovrascrive_la_sede() -> None:
    """Un sede.yaml esistente è la carta d'identità della casa: non si tocca."""
    print("\nnon sovrascrive una sede esistente")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        sede = base / "sede.yaml"
        sede.write_text('ceo:\n  nome: "Il Primo"\n', encoding="utf-8")
        init.crea("Nuova", "Il Secondo", radice=base)
        testo = sede.read_text(encoding="utf-8")
        check("il CEO originale resta", "Il Primo" in testo, testo)
        check("il nuovo CEO non entra", "Il Secondo" not in testo, testo)


def test_idempotente() -> None:
    """Eseguito due volte non duplica e non rompe niente."""
    print("\nidempotente")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        init.crea("X", "Y", radice=base)
        prima = {p.name: p.stat().st_mtime for p in base.iterdir()}
        esiti = init.crea("X", "Y", radice=base)
        dopo = {p.name: p.stat().st_mtime for p in base.iterdir()}
        check("la seconda esecuzione non cambia niente", prima == dopo)
        check("e dice che c'era già", all("gia" in e or "c'e" in e for _, e in esiti), str(esiti))


def test_dry_run_non_scrive() -> None:
    """`--dry-run` dice cosa farebbe, e non scrive niente."""
    print("\n--dry-run non scrive")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        esiti = init.crea("X", "Y", asciutto=True, radice=base)
        check("la cartella resta vuota", not list(base.iterdir()), str(list(base.iterdir())))
        check("ma dice cosa farebbe", any("da creare" in e for _, e in esiti), str(esiti))


def test_senza_ceo_esce_2() -> None:
    """Un motore senza CEO non sa per chi lavora."""
    print("\nargomenti mancanti")
    for argomenti in ([], ["--nome", "X"], ["--ceo", "Y"]):
        esito = subprocess.run(
            [sys.executable, str(RADICE / "tools" / "init.py"), *argomenti],
            capture_output=True, text=True, timeout=60, cwd=str(RADICE),
        )
        check(f"senza {argomenti or 'niente'}: esce 2", esito.returncode == 2, str(esito.returncode))


def test_verifica_dopo_creare() -> None:
    """Dopo aver creato, verifica. Non dichiara «fatto» e va via."""
    print("\nverifica dopo aver creato")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        # Una macchina finta, senza tools/: la verifica deve dire che manca.
        esito = init.verifica(radice=base)
        check(
            "senza tools/accendi.py la verifica fallisce",
            esito == 1,
            f"esito {esito}: ha dichiarato acceso un motore senza strumenti",
        )


def test_il_motore_vero_ha_gli_strumenti() -> None:
    """Il motore vero ha init.py e accendi.py: la catena è completa."""
    print("\nil motore vero")
    check("tools/init.py esiste", (RADICE / "tools" / "init.py").is_file())
    check("tools/accendi.py esiste", (RADICE / "tools" / "accendi.py").is_file())
    check(
        "init.py sa eseguire la verifica",
        "accendi.py" in (RADICE / "tools" / "init.py").read_text(encoding="utf-8"),
    )


def main() -> int:
    print("l'inizializzatore")
    test_crea_tutto()
    test_non_sovrascrive_la_sede()
    test_idempotente()
    test_dry_run_non_scrive()
    test_senza_ceo_esce_2()
    test_verifica_dopo_creare()
    test_il_motore_vero_ha_gli_strumenti()
    print()
    if FALLITI:
        print(f"FALLITO — {len(FALLITI)} controlli: " + ", ".join(FALLITI))
        return 1
    print("PASS — l'inizializzatore costruisce, non sovrascrive, e verifica")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
