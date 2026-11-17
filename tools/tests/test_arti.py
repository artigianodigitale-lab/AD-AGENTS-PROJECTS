#!/usr/bin/env python3
"""Un cervello, molti arti (`GOV-023`, parte GOV-030).

Il CEO ha fissato il modello il 2026-11-08: *«AD-AGENTS-PROJECTS e' il cervello, il
motore e la memoria. Ogni cartella del workspace e' un arto.»* E alla domanda se un arto
possa scrivere in un altro: *«No. Resta il cervello che deve capire se cio' che e'
accaduto a un braccio puo' essere utile all'altro.»*

Questo file prova le tre cose che il modello richiede:

  1. **L'arto lavora nella sua cartella.** Una chat aperta in `8. Epsilon/` che scrive
     `note.md` deve essere valutata su `8. Epsilon/note.md`, non su un file inesistente
     nella radice del cervello.
  2. **Il cervello resta uno.** I contratti, gli errori, le decisioni si leggono da
     `AD-AGENTS-PROJECTS/`, sempre.
  3. **Un arto non scrive nell'arto dell'altro.** `../1. Alfa/x.md` da una chat in
     `8. Epsilon/` viene negato.

## Le due regole che questo file rispetta

**Non tocca il `~/.dsh` vero.** Prova le funzioni del plugin, non il montaggio.

**Non scrive nessun file.** Le scritture sono **simulate**: si chiede il verdetto al
verificatore vero, senza eseguire niente.

Si esegue dalla radice:
    python3 tools/tests/test_arti.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
VERIFICATORE = RADICE / "tools" / "contract_scope.py"
PLUGIN = RADICE / ".brain" / "plugin" / "enforce-contract" / "index.mjs"

sys.path.insert(0, str(RADICE / "tools"))
import ad_docs  # noqa: E402

#: I progetti possono stare fuori dal motore (M1, `DEC-0111`): `sede.yaml` lo dichiara.
PROGETTI = ad_docs.PROGETTI_ROOT

FALLITI: list[str] = []


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    if condizione:
        print(f"  ok   {etichetta}")
    else:
        print(f"  NO   {etichetta}  {dettaglio}")
        FALLITI.append(etichetta)


def verdetto(percorso: str) -> tuple[int, str]:
    """Chiede al verificatore vero, senza scrivere niente."""
    esito = subprocess.run(
        [sys.executable, str(VERIFICATORE), "check", percorso],
        cwd=str(RADICE), capture_output=True, text=True, timeout=120,
    )
    testo = (esito.stdout + esito.stderr).strip().splitlines()
    return esito.returncode, (testo[0][:110] if testo else "")


def test_il_plugin_ha_la_funzione() -> None:
    """La correzione e' nel codice, non solo nel contract."""
    print("\nla correzione e' nel codice")
    check("l'index.mjs esiste", PLUGIN.is_file())
    if not PLUGIN.is_file():
        return
    testo = PLUGIN.read_text(encoding="utf-8")
    check(
        "esiste cwdDellaSessione()",
        "function cwdDellaSessione(" in testo,
        "la funzione che legge la cartella della sessione non c'e'",
    )
    check(
        "targetOf usa una base parametrica",
        "function targetOf(exec, base)" in testo,
        "targetOf usa ancora la radice fissa",
    )
    check(
        "nessuna chiamata risolve piu' contro la radice",
        "targetOf(exec, settings.root)" not in testo,
        "una chiamata usa ancora la radice del cervello per i relativi",
    )


def test_larto_lavora_nella_sua_cartella() -> None:
    """Il file che l'arto scrive e' quello che il cancello valuta."""
    print("\nl'arto lavora nella sua cartella")
    progetto = PROGETTI / "8. Epsilon"
    if not progetto.is_dir():
        check("il progetto 8. Epsilon esiste", False)
        return

    # Come lo risolve il plugin DOPO: relativo alla cwd della sessione.
    codice, prima = verdetto(str(progetto / "note.md"))
    # Come lo risolveva PRIMA: nella radice del cervello.
    codice_prima, prima_prima = verdetto(str(RADICE / "note.md"))

    check(
        "il percorso sbagliato era «fuori dalle cartelle prodotto»",
        codice_prima == 0,
        f"exit {codice_prima}: {prima_prima}",
    )
    check(
        "il file vero del progetto produce un verdetto diverso",
        codice != codice_prima or prima != prima_prima,
        f"stesso esito ({codice}): la correzione non cambia il bersaglio",
    )


def test_il_cervello_resta_uno() -> None:
    """I registri si leggono dalla radice, per tutti gli arti."""
    print("\nil cervello resta uno")
    for registro in ("contratti", "approvazioni", "DECISIONI", "errori"):
        check(f"{registro}/ e' nella radice", (RADICE / registro).is_dir())
    for progetto in ("8. Epsilon", "1. Alfa"):
        cartella = PROGETTI / progetto
        if not cartella.is_dir():
            continue
        propri = [c for c in ("contratti", "DECISIONI", "errori") if (cartella / c).is_dir()]
        check(
            f"{progetto}/ non ha registri propri",
            not propri,
            f"ha {propri}: la memoria si e' divisa",
        )


def test_un_arto_non_scrive_nell_arto_dell_altro() -> None:
    """Il confine: `../1. Alfa/x.md` da Epsilon viene negato."""
    print("\nun arto non scrive nell'arto dell'altro")
    epsilon = PROGETTI / "8. Epsilon"
    if not epsilon.is_dir() or not (PROGETTI / "1. Alfa").is_dir():
        check("i due progetti esistono", False, "servono 8. Epsilon e 1. Alfa")
        return

    uscita = str((epsilon / ".." / "1. Alfa" / "intruso.md").resolve())
    codice, prima = verdetto(uscita)
    check(
        "scrivere nell'altro progetto e' negato",
        codice != 0,
        f"exit {codice}: {prima} — un arto scrive nell'altro",
    )


def test_la_radice_non_cambia() -> None:
    """Con cwd = radice, il comportamento resta quello di oggi."""
    print("\ncon cwd = radice, niente cambia")
    codice, prima = verdetto("nuovo-file-di-prova.md")
    check(
        "nella radice il verdetto e' quello di oggi",
        codice == 0,
        f"exit {codice}: {prima}",
    )


def test_il_test_del_plugin_passa() -> None:
    """Il test del plugin non e' stato rotto dalla correzione."""
    print("\nil test del plugin")
    esito = subprocess.run(
        ["node", str(RADICE / ".brain" / "plugin" / "enforce-contract" / "test.mjs")],
        cwd=str(RADICE), capture_output=True, text=True, timeout=180,
    )
    ultime = (esito.stdout + esito.stderr).strip().splitlines()
    check(
        "il test del plugin passa",
        esito.returncode == 0,
        ultime[-1][:150] if ultime else "nessun output",
    )


def main() -> int:
    print("un cervello, molti arti")
    test_il_plugin_ha_la_funzione()
    test_larto_lavora_nella_sua_cartella()
    test_il_cervello_resta_uno()
    test_un_arto_non_scrive_nell_arto_dell_altro()
    test_la_radice_non_cambia()
    test_il_test_del_plugin_passa()
    print()
    if FALLITI:
        print(f"FALLITO — {len(FALLITI)} controlli: " + ", ".join(FALLITI))
        return 1
    print("PASS — ogni arto lavora nella sua cartella, il cervello resta uno")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
