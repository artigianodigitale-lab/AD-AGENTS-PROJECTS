#!/usr/bin/env python3
"""Il costo del prefisso: le due guardie devono mordere (GOV-018, punto A/B).

Un controllo che non e' mai stato visto fallire non e' un controllo. Questo prova le due
guardie di `tools/prefisso.py` sui casi che devono farle scattare, su una cartella
temporanea: non tocca il motore vero.

  A — oltre la soglia di byte, il controllo fallisce e dice quanto costa
  B — una data con l'ora in testa fallisce; la stessa data in fondo passa

Si esegue dalla radice:
    python3 tools/tests/test_prefisso.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE / "tools"))

import prefisso  # noqa: E402

FALLITI: list[str] = []


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    if condizione:
        print(f"  ok   {etichetta}")
    else:
        print(f"  NO   {etichetta}  {dettaglio}")
        FALLITI.append(etichetta)


class Finta:
    """Un `.brain/` finto in una cartella temporanea: il motore vero non si tocca."""

    def __init__(self, testo: str, skill_kb: int = 0) -> None:
        self.base = Path(tempfile.mkdtemp())
        (self.base / ".brain" / "skills").mkdir(parents=True)
        (self.base / ".brain" / "COSTITUZIONE.md").write_text(testo, encoding="utf-8")
        if skill_kb:
            for numero in range(skill_kb):
                cartella = self.base / ".brain" / "skills" / f"s{numero}"
                cartella.mkdir()
                (cartella / "SKILL.md").write_text("x" * 1024, encoding="utf-8")
        self._prima_c = prefisso.COSTITUZIONE
        self._prima_s = prefisso.SKILLS
        prefisso.COSTITUZIONE = self.base / ".brain" / "COSTITUZIONE.md"
        prefisso.SKILLS = self.base / ".brain" / "skills"

    def chiudi(self) -> None:
        prefisso.COSTITUZIONE = self._prima_c
        prefisso.SKILLS = self._prima_s
        shutil.rmtree(self.base, ignore_errors=True)


def test_sotto_le_guardie() -> None:
    """Un prefisso piccolo e pulito passa: la guardia non accusa chi sta bene."""
    print("\nun prefisso piccolo e pulito")
    finta = Finta("# Costituzione\n\nRegole brevi.\n")
    try:
        problemi, numeri = prefisso.controlli()
        check("nessun problema", not problemi, str(problemi))
        check("i byte si misurano", numeri["costituzione"] > 0, str(numeri))
    finally:
        finta.chiudi()


def test_oltre_la_soglia() -> None:
    """A — oltre la soglia di byte, la guardia scatta e dice quanto costa."""
    print("\nA — un prefisso troppo grande")
    finta = Finta("# Costituzione\n\n" + ("parola " * 20000) + "\n")
    try:
        problemi, numeri = prefisso.controlli()
        check("la guardia scatta", bool(problemi), "nessun problema: la soglia non morde")
        check(
            "il messaggio dice quanto costa",
            any("token" in p for p in problemi),
            str(problemi)[:120],
        )
        check("e cita AGENTS.md", any("AGENTS.md" in p for p in problemi), str(problemi)[:120])
    finally:
        finta.chiudi()


def test_skill_troppe() -> None:
    """A — anche il totale delle skill ha una guardia."""
    print("\nA — troppe skill nel livello sempre caricato")
    finta = Finta("# Costituzione\n\nRegole.\n", skill_kb=110)
    try:
        problemi, numeri = prefisso.controlli()
        check("la guardia sul totale scatta", bool(problemi), str(numeri))
    finally:
        finta.chiudi()


def test_dinamico_in_testa() -> None:
    """B — una data con l'ora in testa rompe il prefisso cachabile."""
    print("\nB — testo dinamico in testa")
    testo = "# Costituzione\n\nSessione avviata 2026-11-06T08:30:00, tutto pronto.\n"
    finta = Finta(testo)
    try:
        problemi, _ = prefisso.controlli()
        check("la guardia scatta", bool(problemi), "nessun problema: la guardia non morde")
        check(
            "il messaggio spiega perche'",
            any("cach" in p.lower() or "prefisso" in p for p in problemi),
            str(problemi)[:120],
        )
    finally:
        finta.chiudi()


def test_dinamico_in_fondo_passa() -> None:
    """B — la stessa data in fondo NON rompe il prefisso: e' la posizione che conta."""
    print("\nB — la stessa data in fondo passa")
    righe = ["# Costituzione", "", "Regole."] + [f"riga {n}" for n in range(500)]
    righe.append("Sessione avviata 2026-11-06T08:30:00.")
    finta = Finta("\n".join(righe) + "\n")
    try:
        problemi, _ = prefisso.controlli()
        check("in fondo non accusa", not problemi, str(problemi)[:150])
    finally:
        finta.chiudi()


def test_citazione_storica_ammessa() -> None:
    """Una data raccontata in testa e' storia, non stato corrente: non deve accusare."""
    print("\nuna citazione storica in testa")
    testo = "# Costituzione\n\nIl 2026-10-11 ho verificato che una cartella senza numero passava.\n"
    finta = Finta(testo)
    try:
        problemi, _ = prefisso.controlli()
        check("la storia non accusa", not problemi, str(problemi)[:150])
    finally:
        finta.chiudi()


def test_il_motore_vero_e_pulito() -> None:
    """Il motore vero, adesso, sta sotto le guardie."""
    print("\nil motore vero")
    problemi, numeri = prefisso.controlli()
    check("il motore e' sotto le guardie", not problemi, str(problemi)[:200])
    check("e i byte si leggono", numeri["totale"] > 1000, str(numeri))


def main() -> int:
    print("il costo del prefisso (GOV-018, punti A e B)")
    test_sotto_le_guardie()
    test_oltre_la_soglia()
    test_skill_troppe()
    test_dinamico_in_testa()
    test_dinamico_in_fondo_passa()
    test_citazione_storica_ammessa()
    test_il_motore_vero_e_pulito()
    print()
    if FALLITI:
        print(f"FALLITO — {len(FALLITI)} controlli: " + ", ".join(FALLITI))
        return 1
    print("PASS — le due guardie mordono, e non accusano chi sta bene")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
