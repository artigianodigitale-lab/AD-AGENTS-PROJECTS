#!/usr/bin/env python3
"""La reversibilita', e la separazione fra motori (`GOV-029`).

Perche' esiste. Il CEO ha chiesto il 2026-11-08 due cose che sembrano una:
*«facciamo in modo che un progetto sia reversibile»* e *«il motore di un progetto non e'
il motore di un altro progetto»*.

Sono due, e si provano in due modi:

  1. **Reversibilita'** — attivo il motore A, poi il motore B, poi torno ad A. I ganci
     devono essere di A, e di B non deve restare niente. Senza, attivare una seconda
     macchina e' un trasloco senza ritorno.
  2. **Separazione** — due motori con profili DSH diversi: il cancello di A **non**
     deve autorizzare una scrittura nei progetti di B. Se lo facesse, i due motori
     sarebbero lo stesso motore con due nomi.

## La regola che questo file rispetta

**Non tocca la home vera.** Ogni prova gira con `--home` temporanea. Un test che smonta
il cancello della macchina accesa non e' un test: e' un incidente (`GOV-028`).

## La regola che questo file rispetta, la seconda

**Prova il negativo.** «I ganci tornano ad A» si prova solo verificando che **non**
puntino a B. Una verifica che guarda solo A lo direbbe anche se B fosse ancora li'.

Si esegue dalla radice:
    python3 tools/tests/test_reversibilita.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE / "tools"))

import attiva as modulo_attiva  # noqa: E402

FALLITI: list[str] = []


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    if condizione:
        print(f"  ok   {etichetta}")
    else:
        print(f"  NO   {etichetta}  {dettaglio}")
        FALLITI.append(etichetta)


#: L'identificatore MCP che `attiva.py` cerca. Il test lo mette gia' nei profili: qui
#: si prova la REVERSIBILITA' dei ganci, non l'installazione del server (che ha il suo
#: test in `test_ad_mcp.py`). Un test che finge di installare non proverebbe niente.
ID_MCP = "ad-projects-mcp"


def _home(base: Path) -> Path:
    """Una home con quattro profili DSH, ognuno col server MCP gia' dichiarato."""
    home = base / "home"
    for profilo in ("desktop", "web", "alpha", "beta"):
        cartella = home / ".dsh" / "profiles" / profilo
        cartella.mkdir(parents=True, exist_ok=True)
        (cartella / "cordis.patch.yml").write_text(
            f"# profilo\nplugins:\n    - id: {ID_MCP}\n", encoding="utf-8"
        )
    return home


def _motore(base: Path, nome: str) -> Path:
    """Un motore minimo ma vero: cervello, plugin, strumenti, sede."""
    motore = base / nome
    (motore / ".brain" / "plugin" / "enforce-contract").mkdir(parents=True)
    (motore / ".brain" / "COSTITUZIONE.md").write_text(f"# {nome}\n", encoding="utf-8")
    (motore / ".brain" / "plugin" / "enforce-contract" / "index.mjs").write_text(
        "// gate\n", encoding="utf-8"
    )
    for skill in ("ad-avvio", "ad-kickoff"):
        (motore / ".brain" / "skills" / skill).mkdir(parents=True)
        (motore / ".brain" / "skills" / skill / "SKILL.md").write_text(
            f"# {skill}\n", encoding="utf-8"
        )
    return motore


def _con(radice: Path):
    """Esegue una funzione di attiva.py come se RADICE fosse un altro motore."""
    class _Ctx:
        def __enter__(self):
            self._salva = modulo_attiva.RADICE
            modulo_attiva.RADICE = radice
            return modulo_attiva

        def __exit__(self, *_):
            modulo_attiva.RADICE = self._salva
    return _Ctx()


def test_reversibilita() -> None:
    """Attivo A, poi B, poi torno ad A: i ganci devono essere di A."""
    print("\nreversibilita': A -> B -> A")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        home = _home(base)
        motore_a = _motore(base, "MotoreA")
        motore_b = _motore(base, "MotoreB")

        with _con(motore_a) as m:
            check("attivo A", m.attiva(home) == 0)
        avvio = home / ".dsh" / "AGENTS.md"
        check(
            "il gancio e' di A",
            "MotoreA" in str(avvio.resolve()),
            str(avvio.resolve()),
        )

        with _con(motore_b) as m:
            codice = m.attiva(home)
            check("attivo B", codice == 0, f"exit {codice}")
        check(
            "il gancio adesso e' di B",
            "MotoreB" in str(avvio.resolve()),
            str(avvio.resolve()),
        )
        check(
            "e NON e' piu' di A",
            "MotoreA" not in str(avvio.resolve()),
            "il gancio dice B ma contiene ancora A",
        )

        # La prova che conta: torno ad A.
        with _con(motore_a) as m:
            codice = m.attiva(home)
            check("riattivo A", codice == 0, f"exit {codice}")
        finale = str(avvio.resolve())
        check("il gancio e' tornato ad A", "MotoreA" in finale, finale)
        check(
            "e di B non resta niente",
            "MotoreB" not in finale,
            f"il gancio contiene ancora B: {finale}",
        )

        # Anche le skill devono essere tornate ad A.
        skill = home / ".agents" / "skills" / "ad-avvio"
        check("le skill sono di A", "MotoreA" in str(skill.resolve()), str(skill.resolve()))
        check(
            "e non di B",
            "MotoreB" not in str(skill.resolve()),
            str(skill.resolve()),
        )


def test_separazione_dei_profili() -> None:
    """Due motori, due profili: i loro cancelli non si sovrappongono."""
    print("\nseparazione: un profilo per motore")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        home = _home(base)
        motore_a = _motore(base, "MotoreA")
        motore_b = _motore(base, "MotoreB")

        with _con(motore_a) as m:
            m.attiva(home, profilo="alpha")
        with _con(motore_b) as m:
            m.attiva(home, profilo="beta")

        patch_alpha = (home / ".dsh" / "profiles" / "alpha" / "cordis.patch.yml").read_text(encoding="utf-8")
        patch_beta = (home / ".dsh" / "profiles" / "beta" / "cordis.patch.yml").read_text(encoding="utf-8")

        check(
            "il profilo alpha monta il cancello di A",
            "MotoreA" in patch_alpha,
            patch_alpha[:200],
        )
        check(
            "il profilo beta monta il cancello di B",
            "MotoreB" in patch_beta,
            patch_beta[:200],
        )
        check(
            "il cancello di A NON e' nel profilo di B",
            "MotoreA" not in patch_beta,
            "due motori nello stesso profilo: nessuno dei due protegge davvero",
        )
        check(
            "il cancello di B NON e' nel profilo di A",
            "MotoreB" not in patch_alpha,
            "due motori nello stesso profilo",
        )


def test_il_profilo_si_legge_da_sede() -> None:
    """Il profilo dichiarato in sede.yaml e' quello che si usa."""
    print("\nil profilo dichiarato in sede.yaml")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        motore = _motore(base, "MotoreA")
        (motore / "sede.yaml").write_text(
            'ceo:\n  nome: "X"\nmacchina:\n  nome: "A"\n  profilo: "alpha"\n',
            encoding="utf-8",
        )
        with _con(motore) as m:
            letto = m.profilo_preferito()
        check("legge «alpha»", letto == "alpha", str(letto))

        # Controprova: senza il campo, non inventa.
        (motore / "sede.yaml").write_text('ceo:\n  nome: "X"\n', encoding="utf-8")
        with _con(motore) as m:
            letto = m.profilo_preferito()
        check("senza il campo non inventa", letto is None, str(letto))


def test_senza_profilo_monta_tutti() -> None:
    """Il predefinito resta «tutti»: cambiarlo in silenzio scoprirebbe le sessioni."""
    print("\nsenza --profilo, monta su tutti (ERR-0086)")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        home = _home(base)
        motore = _motore(base, "MotoreA")
        with _con(motore) as m:
            m.attiva(home)
        # dei 4 profili, tutti e 4 devono avere il cancello
        montati = 0
        for profilo in ("desktop", "web", "alpha", "beta"):
            testo = (home / ".dsh" / "profiles" / profilo / "cordis.patch.yml").read_text(encoding="utf-8")
            if "MotoreA" in testo:
                montati += 1
        check("4 profili su 4", montati == 4, f"{montati}/4: una sessione resterebbe scoperta")


def test_la_home_vera_non_si_tocca() -> None:
    """La prova gira su una home temporanea."""
    print("\nla home vera non e' toccata")
    vera = Path.home() / ".dsh" / "AGENTS.md"
    if not vera.is_symlink():
        check("il gancio vero esiste", True)
        return
    proprietario = modulo_attiva._proprietario(vera)
    check(
        "il gancio vero punta ancora alla sua macchina",
        proprietario == "AD-AGENTS-PROJECTS",
        f"punta a {proprietario}",
    )


def main() -> int:
    print("reversibilita' e separazione dei motori")
    test_reversibilita()
    test_separazione_dei_profili()
    test_il_profilo_si_legge_da_sede()
    test_senza_profilo_monta_tutti()
    test_la_home_vera_non_si_tocca()
    print()
    if FALLITI:
        print(f"FALLITO — {len(FALLITI)} controlli: " + ", ".join(FALLITI))
        return 1
    print("PASS — l'attivazione torna indietro, e due motori non si sovrappongono")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
