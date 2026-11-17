#!/usr/bin/env python3
"""Gli ID non si scontrano, nemmeno con dieci sessioni insieme (`GOV-031`).

Perche' esiste. Il 2026-11-08 ho trovato che `prenota_id` **non era atomico**, e l'ho
scoperto perche' ho provato: dieci processi paralleli hanno prodotto dieci file chiamati
`ERR-0096`.

Due correzioni sbagliate prima di quella giusta, ed entrambe mie:

  1. `ERR-0096-<slug>.yaml` — `O_EXCL` protegge il percorso, e lo slug lo cambia: dieci
     file diversi, **stesso numero**. Lo slug nel nome rende unico cio' che doveva
     restare condiviso.
  2. sentinella `.prenotato` poi `os.replace` — il sentinella e' il lucchetto ma
     **sparisce quando lo usi**: dopo il rename il numero sembra di nuovo libero.

La forma che regge: **il file definitivo e' il lucchetto**. Si chiama col numero e
nient'altro; lo slug va dentro il file.

## La regola che questo file rispetta

**Non lascia residui.** I file prenotati si cancellano alla fine, e la pulizia e'
verificata: un test che sporca il registro degli errori creerebbe un difetto mentre ne
prova un altro.

Si esegue dalla radice:
    python3 tools/tests/test_id_atomici.py
"""

from __future__ import annotations

import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE / "tools"))

FALLITI: list[str] = []


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    if condizione:
        print(f"  ok   {etichetta}")
    else:
        print(f"  NO   {etichetta}  {dettaglio}")
        FALLITI.append(etichetta)


def _prenota(args):
    """Un processo che prenota. Import locale: ogni processo ha il suo modulo."""
    cartella, indice = args
    import sys as _s
    _s.path.insert(0, str(RADICE / "tools"))
    import ad_docs

    try:
        ident, percorso = ad_docs.prenota_id(
            Path(cartella), "ERR", slug=f"prova-{indice}", estensione=".yaml"
        )
        return ("ok", ident, str(percorso))
    except Exception as errore:  # noqa: BLE001 — il test vuole vedere tutto
        return ("errore", type(errore).__name__, str(errore)[:90])


def test_il_nome_e_il_numero() -> None:
    """Il codice prenota sul numero, non sul percorso con lo slug."""
    print("\nil nome del file e' il numero")
    sorgente = (RADICE / "tools" / "ad_docs.py").read_text(encoding="utf-8")
    check(
        "il nome del file non contiene lo slug",
        "{identificatore}{estensione}" in sorgente,
        "il percorso usa ancora lo slug nel nome",
    )
    # La parola «sentinella» nel sorgente NON e' un difetto: c'e' il commento che
    # spiega perche' quella forma era sbagliata, ed e' la lezione (GOV-031).
    # Quello che conta e' l'EFFETTO: la funzione rinomina ancora qualcosa? Se chiama
    # `os.replace`, il lucchetto sparisce quando lo usi e il difetto e' tornato.
    corpo = sorgente[sorgente.find("def prenota_id"):]
    corpo = corpo[:corpo.find("\ndef ", 10)] if "\ndef " in corpo[10:] else corpo
    check(
        "la prenotazione non rinomina un lucchetto temporaneo",
        "os.replace(" not in corpo,
        "il codice chiama ancora os.replace: il sentinella sparisce quando lo usi",
    )


def test_dieci_processi_insieme() -> None:
    """Dieci processi paralleli: dieci numeri distinti, nessun duplicato."""
    print("\ndieci processi paralleli")
    registro = RADICE / "errori"
    prima = {p.name for p in registro.glob("*.yaml")}

    with ProcessPoolExecutor(max_workers=10) as pool:
        esiti = list(pool.map(_prenota, [(str(registro), i) for i in range(10)]))

    riusciti = [e for e in esiti if e[0] == "ok"]
    falliti = [e for e in esiti if e[0] != "ok"]
    check(
        "tutti hanno proceduto",
        len(riusciti) == 10,
        f"{len(riusciti)}/10 · {[f[2] for f in falliti[:2]]}",
    )

    numeri = [e[1] for e in riusciti]
    ripetuti = sorted({n for n in numeri if numeri.count(n) > 1})
    check(
        "dieci numeri distinti",
        not ripetuti,
        f"duplicati: {ripetuti} — il numero non e' protetto",
    )

    for e in riusciti:
        percorso = Path(e[2])
        if percorso.is_file():
            percorso.unlink()

    dopo = {p.name for p in registro.glob("*.yaml")}
    check("nessun residuo", dopo == prima, f"aggiunti: {sorted(dopo - prima)}")


def test_il_file_dice_a_cosa_serve() -> None:
    """Lo slug non si perde: sta dentro il file, non nel nome."""
    print("\nil file appena prenotato dice a cosa serve")
    registro = RADICE / "errori"
    import ad_docs

    ident, percorso = ad_docs.prenota_id(
        registro, "ERR", slug="prova-descrittiva", estensione=".yaml"
    )
    try:
        testo = percorso.read_text(encoding="utf-8")
        check("contiene l'id", ident in testo, testo[:80])
        check("contiene lo slug", "prova-descrittiva" in testo, testo[:80])
        check(
            "il nome NON contiene lo slug",
            "prova-descrittiva" not in percorso.name,
            f"il nome e' {percorso.name}: lo slug e' tornato nel nome",
        )
    finally:
        percorso.unlink(missing_ok=True)


def test_i_chiamanti_reali() -> None:
    """I quattro chiamanti esistono e usano ancora la prenotazione."""
    print("\ni chiamanti reali")
    for comando, minimo in (("errori.py", 1), ("verbali.py", 1), ("contributo.py", 2)):
        percorso = RADICE / "tools" / comando
        if not percorso.is_file():
            check(f"{comando} esiste", False)
            continue
        testo = percorso.read_text(encoding="utf-8")
        quante = testo.count("prenota_id")
        check(
            f"{comando} prenota {minimo}+ volte",
            quante >= minimo,
            f"trovato {quante}: potrebbe scegliere l'id da solo",
        )


def test_nessun_duplicato_nel_registro() -> None:
    """Il registro degli errori non ha id ripetuti."""
    print("\nil registro vero")
    registro = RADICE / "errori"
    esito = subprocess.run(
        ["ls", str(registro)], capture_output=True, text=True, timeout=60,
    )
    nomi = [r for r in esito.stdout.splitlines() if r.startswith("ERR-")]
    identita = [n.split("-")[1] for n in nomi if n.endswith(".yaml")]
    duplicati = sorted({i for i in identita if identita.count(i) > 1})
    check("nessun id ripetuto", not duplicati, f"duplicati: {duplicati}")


def main() -> int:
    print("gli ID non si scontrano")
    test_il_nome_e_il_numero()
    test_dieci_processi_insieme()
    test_il_file_dice_a_cosa_serve()
    test_i_chiamanti_reali()
    test_nessun_duplicato_nel_registro()
    print()
    if FALLITI:
        print(f"FALLITO — {len(FALLITI)} controlli: " + ", ".join(FALLITI))
        return 1
    print("PASS — dieci sessioni insieme, dieci numeri diversi, nessun residuo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
