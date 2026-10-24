#!/usr/bin/env python3
"""Verifica automatica della macchina (ENG-006).

    python3 tests/ci.py            # profilo veloce: quello che gira prima di un commit
    python3 tests/ci.py --full     # profilo completo: anche la suite storica e l'albero
    python3 tests/ci.py --json     # esito strutturato, per i ganci e per un remoto

Perche' esiste. I controlli deterministici della macchina — registri, coerenza,
contract, suite — esistevano gia' (~490 controlli) ma nessuno li eseguiva
automaticamente: dipendevano dalla disciplina di chi lavora, e la disciplina e'
fallita tre volte in un giorno (`ERR-0057`). Questo comando li mette in fila, con un
solo esito: **se e' rosso, il commit non parte**.

Cosa NON e'. Non e' un Quality Gate: prova i programmi, non giudica il lavoro. Il
giudizio su un artefatto resta a un revisore indipendente, con la sua evidenza. E
non e' una garanzia sul comportamento dell'agente: quella e' `tools/comportamento.py`.

Esito: 0 tutto verde · 1 un controllo obbligatorio e' fallito · 2 uso sbagliato.

Eccezioni dichiarate (non nascoste):
  - la suite storica `tools/tests/test_ad_org.py` si ferma su '13. Progetto Eta
    Digitale' in questa copia (`DRIFT-023`): e' riconosciuta e riportata, non fa
    fallire la CI; qualunque ALTRO guasto si';
  - il controllo dell'albero e' INFORMATIVO: il testimone e' una fotografia e
    invecchia per progetto fra un gate e l'altro, quindi non blocca un commit.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
PY = sys.executable


@dataclass
class Controllo:
    """Un controllo dichiarato: un nome, un comando, e che tipo di esito e'."""

    nome: str
    comando: list[str]
    tipo: str = "obbligatorio"  # obbligatorio | informativo | eccezione
    nota: str = ""



@dataclass
class Esito:
    """Cosa e' successo a un controllo."""

    controllo: Controllo
    codice: int
    testo: str
    secondi: float
    stato: str = ""  # ok | fallito | noto | informativo
    dettaglio: str = field(default="")


def contratti_attivi() -> list[Path]:
    """Return the active contracts (closed ones are history, see DRIFT-027)."""
    import yaml

    attivi: list[Path] = []
    for percorso in sorted((ROOT / "contratti").rglob("*.yaml")):
        if percorso.name.startswith("_"):
            continue
        try:
            dati = yaml.safe_load(percorso.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - un contract illeggibile lo dira' il validatore
            attivi.append(percorso)
            continue
        if isinstance(dati, dict) and str(dati.get("status")) == "active":
            attivi.append(percorso)
    return attivi


def _esegui(comando: list[str]) -> tuple[int, str]:
    """Run one command and return (exit code, combined output)."""
    try:
        esito = subprocess.run(
            comando, cwd=str(ROOT), capture_output=True, text=True, timeout=900
        )
        return esito.returncode, (esito.stdout + esito.stderr)
    except subprocess.TimeoutExpired:
        return 124, f"tempo scaduto: {' '.join(comando)}"
    except OSError as errore:
        return 127, f"non eseguibile: {errore}"


def controlli_fast() -> list[Controllo]:
    """The checks that run before every commit."""
    elenco = [
        Controllo(
            "gate-aperto",
            [PY, str(ROOT / "tests" / "gate_kit.py"), "scan"],
            nota="nessun contract chiuso con il gate ancora aperto",
        ),
        Controllo("coerenza", [PY, str(TOOLS / "coherence.py")]),
        Controllo("drift", [PY, str(TOOLS / "drift.py"), "check"]),
        Controllo("verbali", [PY, str(TOOLS / "verbali.py"), "check"]),
        Controllo("errori", [PY, str(TOOLS / "errori.py"), "check"]),
        Controllo("test-evidenza", [PY, str(TOOLS / "tests" / "test_evidenza.py")]),
        Controllo("test-mcp", [PY, str(TOOLS / "tests" / "test_ad_mcp.py")]),
        Controllo("test-install", [PY, str(TOOLS / "tests" / "test_ad_install.py")]),
    ]
    for contratto in contratti_attivi():
        elenco.append(
            Controllo(
                f"contract {contratto.stem}",
                [PY, str(TOOLS / "validate_contract.py"), str(contratto)],
            )
        )
    return elenco


def controlli_full() -> list[Controllo]:
    """The checks that run before a push: the fast ones plus the heavy profiles."""
    elenco = controlli_fast()
    elenco += [
        # Impronte dei documenti normativi: OBBLIGATORIO, senza eccezioni.
        # DRIFT-028 e' stata chiusa con DEC-0061 e lo snapshot e' riallineato: una
        # modifica a un documento normativo ora e' un guasto vero, non una
        # tolleranza da configurare.
        Controllo(
            "test-memoria",
            [PY, str(ROOT / "tests" / "test_strategic_memory.py")],
            nota="impronte dei documenti normativi",
        ),
        Controllo("test-ci", [PY, str(ROOT / "tests" / "test_ci.py")]),
        Controllo("test-gate-kit", [PY, str(ROOT / "tests" / "test_gate_kit.py")]),
        Controllo(
            "suite-storica",
            [PY, str(TOOLS / "tests" / "test_ad_org.py")],
            tipo="eccezione",
            nota="si ferma su '13. Progetto Eta' (DRIFT-023)",
        ),
        Controllo(
            "albero",
            [PY, str(TOOLS / "verdict.py"), "--tree", "check"],
            tipo="informativo",
            nota="il testimone e' una fotografia: invecchia per progetto",
        ),
    ]
    return elenco


def documenti_divergenti_dal_snapshot() -> set[str]:
    """Return the normative documents that differ from the approved snapshot.

    Si **calcola** confrontando lo snapshot con i file veri, non si legge
    l'output del test: quel test si ferma al PRIMO documento divergente, quindi
    `AGENTS.md` (che viene prima) mascherava ogni altro documento — un difetto
    grave trovato dal gate di ENG-006: la CI restava verde con un documento
    normativo modificato. Qui non c'e' nessun primo: si confrontano tutti.
    """
    sys.path.insert(0, str(ROOT / "tests"))
    import test_strategic_memory as memoria  # noqa: PLC0415 - import locale, serve solo qui

    approvati = memoria.load_documents()
    divergenti: set[str] = set()
    for percorso in memoria.canonical_documents():
        atteso = approvati.get(percorso.name)
        if atteso is None or not percorso.is_file() or memoria.digest(percorso) != atteso:
            divergenti.add(percorso.name)
    return divergenti


def _classifica(controllo: Controllo, codice: int, testo: str) -> Esito:
    """Decide se un controllo e' verde, noto, informativo o fallito."""
    esito = Esito(controllo, codice, testo, 0.0)
    if controllo.tipo == "informativo":
        esito.stato = "informativo"
        esito.dettaglio = "non blocca"
        return esito
    if codice == 0:
        esito.stato = "ok"
        return esito
    if controllo.tipo == "eccezione" and (
        "13. Progetto Eta" in testo and "FileNotFoundError" in testo
    ):
        # Eccezione DICHIARATA: nella copia distributiva i progetti non ci sono.
        esito.stato = "noto"
        esito.dettaglio = "DRIFT-023: la copia non ha i progetti numerati"
        return esito
    esito.stato = "fallito"
    return esito


def verifica(
    profilo: str = "fast", runner=_esegui
) -> list[Esito]:
    """Run the declared battery and return one outcome per check."""
    controlli = controlli_full() if profilo == "full" else controlli_fast()
    esiti: list[Esito] = []
    for controllo in controlli:
        inizio = time.monotonic()
        codice, testo = runner(controllo.comando)
        esito = _classifica(controllo, codice, testo)
        esito.secondi = time.monotonic() - inizio
        esiti.append(esito)
    return esiti


def fallimenti(esiti: list[Esito]) -> list[Esito]:
    """Return the checks that must block a commit."""
    return [esito for esito in esiti if esito.stato == "fallito"]


def _stampa(esiti: list[Esito], profilo: str) -> None:
    """Print the human summary."""
    print(f"verifica della macchina · profilo {profilo}")
    print()
    print(f"{'controllo':28} {'esito':12} {'tempo':>7}  note")
    for esito in esiti:
        nome = esito.controllo.nome
        tempo = f"{esito.secondi:.1f}s"
        nota = esito.dettaglio or esito.controllo.nota
        print(f"{nome:28} {esito.stato:12} {tempo:>7}  {nota}")
    falliti = fallimenti(esiti)
    print()
    if falliti:
        for esito in falliti:
            print(f"FALLITO  {esito.controllo.nome}")
            coda = "\n".join(esito.testo.strip().splitlines()[-6:])
            print(coda)
            print()
        print(f"verdetto: ROSSO ({len(falliti)} controlli falliti)")
        print()
        # Il modo per tornare indietro, detto subito: `git checkout -- file` non
        # basta se la versione rotta e' gia' nell'index (scoperto provando il
        # rifiuto: il commit non parte, ma la modifica resta staged).
        print("per tornare indietro: git restore --source=HEAD --staged --worktree <file>")
        print("  (git checkout -- <file> non basta: l'index conserva la versione rotta)")
        return
    print(f"verdetto: VERDE ({len(esiti)} controlli, 0 falliti)")


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Verifica automatica della macchina")
    parser.add_argument("--fast", action="store_true", help="profilo veloce (default)")
    parser.add_argument("--full", action="store_true", help="profilo completo")
    parser.add_argument("--json", action="store_true", help="esito strutturato")
    args = parser.parse_args(argv)
    if args.fast and args.full:
        print("ERRORE  scegli --fast oppure --full, non entrambi", file=sys.stderr)
        return 2
    profilo = "full" if args.full else "fast"
    esiti = verifica(profilo)
    falliti = fallimenti(esiti)
    if args.json:
        print(
            json.dumps(
                {
                    "profilo": profilo,
                    "verde": not falliti,
                    "controlli": [
                        {
                            "nome": esito.controllo.nome,
                            "comando": list(esito.controllo.comando),
                            "stato": esito.stato,
                            "codice": esito.codice,
                            "secondi": round(esito.secondi, 2),
                            "dettaglio": esito.dettaglio or esito.controllo.nota,
                        }
                        for esito in esiti
                    ],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        _stampa(esiti, profilo)
    return 0 if not falliti else 1


if __name__ == "__main__":
    raise SystemExit(main())
