#!/usr/bin/env python3
"""La cache dei registri deve essere invisibile e onesta (GOV-018).

Una cache che sbaglia e' peggio di nessuna cache: il cancello autorizzerebbe con dati
vecchi. Questo file prova le tre cose che rendono la cache usabile, tutte in negativo:

  1. **riusa** quando niente e' cambiato (e si vede dal tempo);
  2. **si rifa'** quando il contenuto cambia — anche se l'mtime non cambia;
  3. **non rompe** quando e' corrotta, vecchia o su una cartella non scrivibile.

Il caso 2 e' il piu' importante, ed e' quello in cui una cache basata sull'mtime
fallirebbe: `shutil.copy2` conserva l'mtime, quindi un file copiato sopra sembra
identico. Il contenuto invece cambia, e la firma lo vede.

Si esegue dalla radice:
    python3 tools/tests/test_cache_registri.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE / "tools"))

import cache_registri  # noqa: E402

FALLITI: list[str] = []


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    if condizione:
        print(f"  ok   {etichetta}")
    else:
        print(f"  NO   {etichetta}  {dettaglio}")
        FALLITI.append(etichetta)


class Finta:
    """Una radice finta con due file YAML: il motore vero non si tocca."""

    def __init__(self) -> None:
        self.base = Path(tempfile.mkdtemp())
        (self.base / "contratti").mkdir()
        (self.base / "contratti" / "A.yaml").write_text("task_id: A\n", encoding="utf-8")
        (self.base / "contratti" / "B.yaml").write_text("task_id: B\n", encoding="utf-8")
        self.chiamate = 0

    def file(self) -> list[Path]:
        return sorted((self.base / "contratti").glob("*.yaml"))

    def calcola(self) -> dict:
        self.chiamate += 1
        return {"chiamata": self.chiamate, "file": [f.name for f in self.file()]}

    def chiudi(self) -> None:
        shutil.rmtree(self.base, ignore_errors=True)


def test_riusa_quando_nulla_cambia() -> None:
    """1 — la seconda lettura non ricalcola."""
    print("\n1 — riusa quando niente e' cambiato")
    finta = Finta()
    try:
        primo = cache_registri.con_cache("scopes", finta.calcola, finta.file, finta.base)
        secondo = cache_registri.con_cache("scopes", finta.calcola, finta.file, finta.base)
        check("la prima volta calcola", primo.get("chiamata") == 1, str(primo))
        check("la seconda riusa", secondo == primo, f"{primo} vs {secondo}")
        check("e non ha ricalcolato", finta.chiamate == 1, str(finta.chiamate))
    finally:
        finta.chiudi()


def test_si_rifa_quando_il_contenuto_cambia() -> None:
    """2 — il contenuto cambia con lo stesso mtime: la cache deve accorgersene."""
    print("\n2 — si rifa' quando il contenuto cambia")
    finta = Finta()
    try:
        cache_registri.con_cache("scopes", finta.calcola, finta.file, finta.base)
        bersaglio = finta.base / "contratti" / "A.yaml"
        orario = bersaglio.stat().st_mtime
        time.sleep(0.01)
        bersaglio.write_text("task_id: A\nstatus: closed\n", encoding="utf-8")
        # Rimetto l'mtime di prima: e' esattamente cio' che fa `cp -p` o `shutil.copy2`.
        # Una cache basata sull'mtime ora direbbe «niente e' cambiato». Il contenuto no.
        os.utime(bersaglio, (orario, orario))
        check(
            "l'mtime e' identico (la trappola e' armata)",
            bersaglio.stat().st_mtime == orario,
        )
        dopo = cache_registri.con_cache("scopes", finta.calcola, finta.file, finta.base)
        check("la cache si rifa'", dopo.get("chiamata") == 2, str(dopo))
        check("e ha ricalcolato", finta.chiamate == 2, str(finta.chiamate))
    finally:
        finta.chiudi()


def test_si_rifa_quando_un_file_si_aggiunge() -> None:
    """2 — un file nuovo cambia la firma."""
    print("\n2 — si rifa' quando un file si aggiunge")
    finta = Finta()
    try:
        cache_registri.con_cache("scopes", finta.calcola, finta.file, finta.base)
        (finta.base / "contratti" / "C.yaml").write_text("task_id: C\n", encoding="utf-8")
        dopo = cache_registri.con_cache("scopes", finta.calcola, finta.file, finta.base)
        check("la cache si rifa'", dopo.get("chiamata") == 2, str(dopo))
        check("il nuovo file c'e'", "C.yaml" in dopo.get("file", []), str(dopo))
    finally:
        finta.chiudi()


def test_si_rifa_quando_un_file_sparisce() -> None:
    """2 — un file tolto cambia la firma: non si serve un risultato che lo nomina."""
    print("\n2 — si rifa' quando un file sparisce")
    finta = Finta()
    try:
        cache_registri.con_cache("scopes", finta.calcola, finta.file, finta.base)
        (finta.base / "contratti" / "B.yaml").unlink()
        dopo = cache_registri.con_cache("scopes", finta.calcola, finta.file, finta.base)
        check("la cache si rifa'", dopo.get("chiamata") == 2, str(dopo))
        check("B non c'e' piu'", "B.yaml" not in dopo.get("file", []), str(dopo))
    finally:
        finta.chiudi()


def test_cache_corrotta_non_rompe() -> None:
    """3 — una cache illeggibile si rifa' invece di far cadere il lavoro."""
    print("\n3 — una cache corrotta non rompe")
    finta = Finta()
    try:
        percorso = cache_registri.percorso_cache(finta.base)
        percorso.parent.mkdir(parents=True, exist_ok=True)
        percorso.write_text("non sono json {{{", encoding="utf-8")
        risultato = cache_registri.con_cache("scopes", finta.calcola, finta.file, finta.base)
        check("il lavoro continua", risultato.get("chiamata") == 1, str(risultato))
        check("e la cache si e' rifatta", percorso.is_file())
    finally:
        finta.chiudi()


def test_cache_vecchia_non_si_usa() -> None:
    """3 — oltre l'eta' massima si ricalcola, anche se la firma combacia."""
    print("\n3 — una cache vecchia non si usa")
    finta = Finta()
    try:
        cache_registri.con_cache("scopes", finta.calcola, finta.file, finta.base)
        percorso = cache_registri.percorso_cache(finta.base)
        dati = json.loads(percorso.read_text(encoding="utf-8"))
        # Invecchio la voce: firma giusta, eta' oltre il limite.
        dati["scopes"]["quando"] = time.time() - (cache_registri.ETA_MASSIMA + 60)
        percorso.write_text(json.dumps(dati), encoding="utf-8")
        dopo = cache_registri.con_cache("scopes", finta.calcola, finta.file, finta.base)
        check("ha ricalcolato", dopo.get("chiamata") == 2, str(dopo))
    finally:
        finta.chiudi()


def test_cache_in_scrittura_impossibile_non_rompe() -> None:
    """3 — se la cache non si puo' scrivere, il lavoro continua comunque."""
    print("\n3 — una cache non scrivibile non rompe")
    finta = Finta()
    try:
        # `.cache` come FILE, non come cartella: la scrittura fallira'.
        (finta.base / ".cache").write_text("sono un file", encoding="utf-8")
        risultato = cache_registri.con_cache("scopes", finta.calcola, finta.file, finta.base)
        check("il lavoro continua", risultato.get("chiamata") == 1, str(risultato))
    finally:
        finta.chiudi()


def test_chiavi_diverse_non_si_mescolano() -> None:
    """Due cache diverse sullo stesso registro non si sovrascrivono."""
    print("\ndue chiavi diverse")
    finta = Finta()
    try:
        primo = cache_registri.con_cache("scopes", lambda: {"tipo": "scopes"}, finta.file, finta.base)
        secondo = cache_registri.con_cache("approvals", lambda: {"tipo": "approvals"}, finta.file, finta.base)
        check("il primo valore e' suo", primo.get("tipo") == "scopes", str(primo))
        check("il secondo e' un altro", secondo.get("tipo") == "approvals", str(secondo))
        dati = cache_registri.stato(finta.base)
        check("stanno in due voci", len(dati["voci"]) == 2, str(dati["voci"]))
    finally:
        finta.chiudi()


def test_il_guadagno_e_reale() -> None:
    """La cache deve valere: il secondo giro sui registri veri deve essere piu' veloce."""
    print("\nil guadagno sui registri veri")
    import ad_scope

    import cache_registri as cr

    cartella = RADICE / "contratti"
    cache_registri.svuota(RADICE)
    inizio = time.perf_counter()
    cr.con_cache(
        "scopes",
        lambda: [s.task_id for s in ad_scope.load_write_scopes(RADICE)],
        lambda: list(ad_scope.iter_registro(cartella)),
        RADICE,
    )
    prima = time.perf_counter() - inizio
    inizio = time.perf_counter()
    riusato = cr.con_cache(
        "scopes",
        lambda: [],
        lambda: list(ad_scope.iter_registro(cartella)),
        RADICE,
    )
    dopo = time.perf_counter() - inizio
    check("il secondo giro riusa la cache", bool(riusato), str(riusato))
    check(
        f"ed e' piu' veloce ({prima * 1000:.0f} ms -> {dopo * 1000:.0f} ms)",
        dopo < prima / 2,
        f"{prima:.3f} vs {dopo:.3f}",
    )
    cache_registri.svuota(RADICE)


def main() -> int:
    print("la cache dei registri")
    test_riusa_quando_nulla_cambia()
    test_si_rifa_quando_il_contenuto_cambia()
    test_si_rifa_quando_un_file_si_aggiunge()
    test_si_rifa_quando_un_file_sparisce()
    test_cache_corrotta_non_rompe()
    test_cache_vecchia_non_si_usa()
    test_cache_in_scrittura_impossibile_non_rompe()
    test_chiavi_diverse_non_si_mescolano()
    test_il_guadagno_e_reale()
    print()
    if FALLITI:
        print(f"FALLITO — {len(FALLITI)} controlli: " + ", ".join(FALLITI))
        return 1
    print("PASS — la cache riusa quando puo', si rifa' quando deve, non rompe mai")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
