#!/usr/bin/env python3
"""L'accensione deve saper dire di no (GOV-020).

Un'accensione che dice sempre «acceso» e' peggiore di nessuna accensione: convince che
la macchina funzioni mentre un controllo non gira. Il 2026-11-06 il plugin era nel
profilo `web` e la sessione in `desktop`: ogni verifica diceva «installato», e il cancello
era spento proprio dove serviva.

Questo file prova i sei controlli **in negativo**, ognuno sulla sua mancanza:

  1. sede senza CEO          -> non acceso, e dice di aggiungere il nome
  2. cancello in un profilo solo -> non acceso, e nomina il profilo scoperto
  3. una skill non collegata -> non acceso, e la nomina
  4. MCP assente             -> non acceso
  5. catalogo vuoto          -> non acceso
  6. macchina rossa          -> non acceso (provato con un `ci.py` finto che esce 1)

Si esegue dalla radice:
    python3 tools/tests/test_accendi.py
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE / "tools"))

import accendi  # noqa: E402

FALLITI: list[str] = []


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    if condizione:
        print(f"  ok   {etichetta}")
    else:
        print(f"  NO   {etichetta}  {dettaglio}")
        FALLITI.append(etichetta)


class Finta:
    """Una macchina finta: sede, profili, skill, catalogo. Il motore vero non si tocca."""

    def __init__(self) -> None:
        self.base = Path(tempfile.mkdtemp())
        self.casa = self.base / "casa"
        (self.casa / ".dsh" / "profiles" / "desktop").mkdir(parents=True)
        (self.casa / ".agents" / "skills").mkdir(parents=True)
        (self.base / "tools").mkdir(parents=True)
        (self.base / ".brain" / "skills" / "ad-prova").mkdir(parents=True)
        (self.base / ".brain" / "skills" / "ad-prova" / "SKILL.md").write_text("---\n", encoding="utf-8")
        (self.base / "tools" / "README.md").write_text(
            "\n".join(f"| `c{n}.py` | x | y |" for n in range(12)), encoding="utf-8"
        )
        self.scrivi_sede("Luca")
        self.scrivi_layer("desktop", plugin=True, mcp=True)
        (self.casa / ".agents" / "skills" / "ad-prova").mkdir()
        self._prima = (
            accendi.SEDE,
            accendi.PROFILI,
            accendi.SKILL_MOTORE,
            accendi.SKILL_INSTALLATE,
            accendi.ID_PLUGIN,
            accendi.ID_MCP,
            accendi.RADICE,
        )
        accendi.SEDE = self.base / "sede.yaml"
        accendi.PROFILI = self.casa / ".dsh" / "profiles"
        accendi.SKILL_MOTORE = self.base / ".brain" / "skills"
        accendi.SKILL_INSTALLATE = self.casa / ".agents" / "skills"
        accendi.RADICE = self.base

    def scrivi_sede(self, nome: str | None) -> None:
        contenuto = "ceo:\n" + (f'  nome: "{nome}"\n' if nome else "  ruolo: CEO\n")
        (self.base / "sede.yaml").write_text(contenuto + "macchina:\n  nome: prova\n", encoding="utf-8")

    def scrivi_layer(self, profilo: str, *, plugin: bool, mcp: bool) -> None:
        cartella = self.casa / ".dsh" / "profiles" / profilo
        cartella.mkdir(parents=True, exist_ok=True)
        righe = []
        if plugin:
            righe.append(f"- id: {accendi.ID_PLUGIN}\n  name: /x/index.mjs")
        if mcp:
            righe.append(f"- id: {accendi.ID_MCP}\n  name: server")
        (cartella / "cordis.patch.yml").write_text("\n".join(righe) + "\n", encoding="utf-8")

    def chiudi(self) -> None:
        (
            accendi.SEDE,
            accendi.PROFILI,
            accendi.SKILL_MOTORE,
            accendi.SKILL_INSTALLATE,
            accendi.ID_PLUGIN,
            accendi.ID_MCP,
            accendi.RADICE,
        ) = self._prima
        shutil.rmtree(self.base, ignore_errors=True)


def test_tutto_acceso() -> None:
    """Il caso felice: i cinque controlli locali passano (la macchina si salta)."""
    print("\ntutto acceso")
    finta = Finta()
    try:
        esiti = accendi.accendi(rapida=False)
        mancanti = [e for e in esiti if not e.ok]
        check("nessuna mancanza", not mancanti, str([e.detto for e in mancanti]))
    finally:
        finta.chiudi()


def test_sede_senza_ceo() -> None:
    """1 — senza il nome del CEO l'engine non sa per chi lavora."""
    print("\n1 — sede senza CEO")
    finta = Finta()
    try:
        finta.scrivi_sede(None)
        esito = accendi.controlla_sede()
        check("non e' acceso", not esito.ok, esito.detto)
        check("dice cosa fare", "ceo" in esito.rimedio.lower(), esito.rimedio)
    finally:
        finta.chiudi()


def test_cancello_in_un_profilo_solo() -> None:
    """2 — il caso del 2026-11-06: il plugin in un profilo, non nell'altro."""
    print("\n2 — il cancello in un profilo solo")
    finta = Finta()
    try:
        finta.scrivi_layer("web", plugin=False, mcp=True)
        esito = accendi.controlla_cancello()
        check("non e' acceso", not esito.ok, esito.detto)
        check("nomina il profilo scoperto", "web" in esito.detto, esito.detto)
        check("dice cosa fare", "setup" in esito.rimedio, esito.rimedio)
    finally:
        finta.chiudi()


def test_skill_non_collegata() -> None:
    """3 — una skill del motore che il catalogo non vede."""
    print("\n3 — una skill non collegata")
    finta = Finta()
    try:
        (finta.base / ".brain" / "skills" / "ad-nuova").mkdir()
        (finta.base / ".brain" / "skills" / "ad-nuova" / "SKILL.md").write_text("---\n", encoding="utf-8")
        esito = accendi.controlla_skill()
        check("non e' acceso", not esito.ok, esito.detto)
        check("nomina la skill", "ad-nuova" in esito.detto, esito.detto)
    finally:
        finta.chiudi()


def test_mcp_assente() -> None:
    """4 — senza il server MCP gli strumenti del motore non sono raggiungibili."""
    print("\n4 — MCP assente")
    finta = Finta()
    try:
        finta.scrivi_layer("desktop", plugin=True, mcp=False)
        esito = accendi.controlla_mcp()
        check("non e' acceso", not esito.ok, esito.detto)
        check("dice cosa fare", "raggiungibili" in esito.rimedio, esito.rimedio)
    finally:
        finta.chiudi()


def test_catalogo_vuoto() -> None:
    """5 — un catalogo senza voci non dice all'agente cosa sa fare il motore."""
    print("\n5 — catalogo vuoto")
    finta = Finta()
    try:
        (finta.base / "tools" / "README.md").write_text("nessun comando\n", encoding="utf-8")
        esito = accendi.controlla_catalogo()
        check("non e' acceso", not esito.ok, esito.detto)
    finally:
        finta.chiudi()


def test_macchina_rossa() -> None:
    """6 — un motore rotto non e' acceso: `ci.py` rosso deve dire di no."""
    print("\n6 — macchina rossa")
    finta = Finta()
    try:
        (finta.base / "tests").mkdir()
        (finta.base / "tests" / "ci.py").write_text(
            "import sys\nprint('  coerenza  fallito')\nprint('verdetto: ROSSO (1 falliti)')\nsys.exit(1)\n",
            encoding="utf-8",
        )
        esito = accendi.controlla_macchina(timeout=30)
        check("non e' acceso", not esito.ok, esito.detto)
        check("nomina il controllo rosso", "coerenza" in esito.detto, esito.detto)
    finally:
        finta.chiudi()


def test_macchina_verde() -> None:
    """6 — e con `ci.py` verde deve dire di si."""
    print("\n6 — macchina verde")
    finta = Finta()
    try:
        (finta.base / "tests").mkdir()
        (finta.base / "tests" / "ci.py").write_text(
            "print('verdetto: VERDE (38 controlli, 0 falliti)')\n", encoding="utf-8"
        )
        esito = accendi.controlla_macchina(timeout=30)
        check("e' acceso", esito.ok, esito.detto)
    finally:
        finta.chiudi()


def test_motore_vero_acceso() -> None:
    """Il motore vero, adesso: e' acceso davvero? (senza la batteria, che e' lenta)."""
    print("\nil motore vero")
    esiti = accendi.accendi(rapida=False)
    mancanti = [e for e in esiti if not e.ok]
    check("il motore vero e' acceso", not mancanti, str([e.detto for e in mancanti]))


def main() -> int:
    print("l'accensione sa dire di no")
    test_tutto_acceso()
    test_sede_senza_ceo()
    test_cancello_in_un_profilo_solo()
    test_skill_non_collegata()
    test_mcp_assente()
    test_catalogo_vuoto()
    test_macchina_rossa()
    test_macchina_verde()
    test_motore_vero_acceso()
    print()
    if FALLITI:
        print(f"FALLITO — {len(FALLITI)} controlli: " + ", ".join(FALLITI))
        return 1
    print("PASS — ogni mancanza produce un esito distinto e un rimedio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
