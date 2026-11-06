#!/usr/bin/env python3
"""L'accensione: dire se l'engine e' acceso, e cosa manca se non lo e'.

Perche' esiste. `AGENTS.md` diceva come comportarsi, ma non verificava che la macchina
fosse in grado di farlo. Un agente leggeva il regolamento e cominciava, senza sapere se
il cancello era montato, se le skill erano collegate, se la macchina era verde. Il
2026-11-06 il plugin era nel profilo `web` mentre la sessione girava in `desktop`: ogni
verifica diceva «installato», e il cancello era spento proprio dove serviva. Nessuno se
ne accorgeva, perche' nessuno lo chiedeva.

Questo comando lo chiede. Sei controlli, ognuno con il suo esito e il suo rimedio:

  1. **sede.yaml** — chi e' il CEO, e come si chiama questa macchina
  2. **il cancello montato** — il plugin nel profilo DSH, non in un profilo qualsiasi
  3. **le skill collegate** — quelle del motore, nel catalogo di ogni sessione
  4. **il server MCP** — dichiarato, cosi' gli strumenti sono raggiungibili
  5. **la macchina verde** — la batteria rapida, perche' un motore rotto non e' acceso
  6. **il catalogo dei comandi** — l'elenco esiste, e dice cosa c'e'

Non scrive niente, non avvia niente, non chiede permessi: si puo' eseguire a ogni chat,
tante volte quante si vuole.

Uso:
    python3 tools/accendi.py            # l'accensione, in parole comprensibili
    python3 tools/accendi.py --json     # gli stessi esiti, per un programma

Esito: 0 tutto acceso · 1 qualcosa manca (e il messaggio dice cosa fare).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]
SEDE = RADICE / "sede.yaml"
PROFILI = Path.home() / ".dsh" / "profiles"
SKILL_MOTORE = RADICE / ".brain" / "skills"
SKILL_INSTALLATE = Path.home() / ".agents" / "skills"
#: L'identificatore del plugin nel layer del profilo. Deve combaciare con il `name:`
#: scritto da `tools/setup.py`, che e' l'unico che lo monta.
ID_PLUGIN = "ad-enforce-contract"
ID_MCP = "ad-projects-mcp"


class Esito:
    """Un controllo: se passa, cosa dice, e cosa fare se non passa."""

    def __init__(self, nome: str, ok: bool, detto: str, rimedio: str = "") -> None:
        self.nome = nome
        self.ok = ok
        self.detto = detto
        self.rimedio = rimedio

    def a_dizionario(self) -> dict:
        return {"nome": self.nome, "ok": self.ok, "detto": self.detto, "rimedio": self.rimedio}


def _profili_con_layer() -> list[Path]:
    """I profili DSH che hanno un layer di patch: sono quelli in cui si puo' montare."""
    if not PROFILI.is_dir():
        return []
    return sorted(p / "cordis.patch.yml" for p in PROFILI.iterdir() if (p / "cordis.patch.yml").is_file())


def controlla_sede() -> Esito:
    """1 — chi e' il CEO. Senza, l'engine non sa per chi lavora."""
    if not SEDE.is_file():
        return Esito(
            "sede",
            False,
            "manca `sede.yaml`: l'engine non e' ancora avviato",
            "serve il nome del CEO e il permesso di installare: la skill `ad-avvio` fa il resto",
        )
    try:
        import yaml

        dato = yaml.safe_load(SEDE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - qualunque cosa renda illeggibile la sede
        return Esito("sede", False, "`sede.yaml` non si legge", "controlla che sia YAML valido")
    if not isinstance(dato, dict):
        return Esito("sede", False, "`sede.yaml` non contiene una mappatura", "riscrivilo come YAML")
    # `ceo` puo' essere un testo o una mappatura con `nome`: la forma vera del file e'
    # la seconda, e leggere solo la prima faceva stampare il dizionario grezzo.
    grezzo = dato.get("ceo")
    if isinstance(grezzo, dict):
        ceo = str(grezzo.get("nome", "")).strip()
    else:
        ceo = str(grezzo or "").strip()
    if not ceo:
        return Esito(
            "sede",
            False,
            "`sede.yaml` non dice chi e' il CEO",
            "aggiungi `ceo: nome: <nome>` in `sede.yaml`",
        )
    macchina = ""
    if isinstance(dato.get("macchina"), dict):
        macchina = str(dato["macchina"].get("nome", "")).strip()
    dove = f" su «{macchina}»" if macchina else ""
    return Esito("sede", True, f"il CEO e' {ceo}{dove}")


def controlla_cancello() -> Esito:
    """2 — il plugin, nel profilo attivo.

    Il 2026-11-06 il plugin era in `web` e la sessione in `desktop`: ogni verifica diceva
    «installato» e il cancello era spento dove serviva. Quindi si guardano **tutti** i
    profili, e se anche uno solo non ce l'ha lo si dice.
    """
    layer = _profili_con_layer()
    if not layer:
        return Esito(
            "cancello",
            False,
            "nessun profilo DSH ha un layer di patch",
            "monta il cancello con `python3 tools/setup.py`",
        )
    mancanti = []
    for percorso in layer:
        try:
            testo = percorso.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            mancanti.append(f"{percorso.parent.name} (illeggibile)")
            continue
        if ID_PLUGIN not in testo:
            mancanti.append(percorso.parent.name)
    if mancanti:
        return Esito(
            "cancello",
            False,
            "il cancello non e' montato in: " + ", ".join(mancanti),
            "`python3 tools/setup.py` lo monta su tutti i profili; ha effetto al prossimo avvio di DSH",
        )
    return Esito(
        "cancello",
        True,
        f"montato in {len(layer)} profili DSH ({', '.join(p.parent.name for p in layer)})",
    )


def controlla_skill() -> Esito:
    """3 — le skill del motore, nel catalogo di ogni sessione."""
    if not SKILL_MOTORE.is_dir():
        return Esito("skill", False, "manca `.brain/skills/`", "il motore e' incompleto: verifica il checkout")
    attese = sorted(p.name for p in SKILL_MOTORE.iterdir() if (p / "SKILL.md").is_file())
    if not attese:
        return Esito("skill", False, "`.brain/skills/` non contiene skill", "verifica il checkout del motore")
    if not SKILL_INSTALLATE.is_dir():
        return Esito(
            "skill",
            False,
            f"manca {SKILL_INSTALLATE}",
            "`python3 tools/setup.py` collega le skill al catalogo delle sessioni",
        )
    mancanti = [nome for nome in attese if not (SKILL_INSTALLATE / nome).exists()]
    if mancanti:
        return Esito(
            "skill",
            False,
            f"{len(mancanti)} skill su {len(attese)} non sono collegate: " + ", ".join(mancanti[:4]),
            "`python3 tools/setup.py` rifa' i collegamenti",
        )
    return Esito("skill", True, f"{len(attese)} skill collegate al catalogo")


def controlla_mcp() -> Esito:
    """4 — il server MCP, dichiarato: senza, gli strumenti del motore non sono raggiungibili."""
    layer = _profili_con_layer()
    if not layer:
        return Esito("mcp", False, "nessun profilo DSH", "monta il server con `python3 tools/setup.py`")
    con_mcp = [p.parent.name for p in layer if ID_MCP in _testo(p)]
    if not con_mcp:
        return Esito(
            "mcp",
            False,
            "il server MCP del motore non e' dichiarato in nessun profilo",
            "aggiungilo al layer del profilo; gli strumenti `ad_*` non sarebbero raggiungibili",
        )
    return Esito("mcp", True, f"dichiarato in {', '.join(con_mcp)}")


def _testo(percorso: Path) -> str:
    try:
        return percorso.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def controlla_macchina(timeout: int = 180) -> Esito:
    """5 — la macchina verde: un motore rotto non e' acceso.

    Si esegue la batteria **rapida**, non quella completa: qui serve sapere se qualcosa
    e' rotto, non certificarlo. Se il tempo basta a `ci.py` dire VERDE, bene; se no, lo
    si dice invece di far aspettare due minuti a ogni chat.
    """
    try:
        esito = subprocess.run(
            [sys.executable, str(RADICE / "tests" / "ci.py")],
            cwd=str(RADICE),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return Esito(
            "macchina",
            False,
            f"la verifica non e' finita entro {timeout} secondi",
            "lancia `python3 tests/ci.py` a mano per vedere cosa e' lento",
        )
    except OSError as errore:
        return Esito("macchina", False, f"non riesco a eseguire `tests/ci.py`: {errore}", "verifica il checkout")
    if esito.returncode == 0:
        riga = [r for r in esito.stdout.splitlines() if "verdetto" in r]
        return Esito("macchina", True, riga[-1].strip() if riga else "verifica rapida verde")
    rosse = [r.split()[0] for r in esito.stdout.splitlines() if "fallito" in r]
    return Esito(
        "macchina",
        False,
        "la verifica rapida e' rossa" + (f": {', '.join(rosse)}" if rosse else ""),
        "`python3 tests/ci.py` dice quale controllo fallisce, e come tornare indietro",
    )


def controlla_catalogo() -> Esito:
    """6 — il catalogo dei comandi: un agente che non sa di avere uno strumento lo reinventa."""
    catalogo = RADICE / "tools" / "README.md"
    if not catalogo.is_file():
        return Esito(
            "catalogo",
            False,
            "manca `tools/README.md`: l'elenco dei comandi non esiste",
            "va rigenerato: e' il registro che dice cosa il motore sa fare",
        )
    testo = _testo(catalogo)
    voci = testo.count("\n| `")
    if voci < 10:
        return Esito(
            "catalogo",
            False,
            f"`tools/README.md` elenca solo {voci} comandi",
            "il catalogo e' incompleto: `python3 tools/coherence.py` dice cosa manca",
        )
    return Esito("catalogo", True, f"{voci} comandi elencati in `tools/README.md`")


def accendi(*, rapida: bool = True) -> list[Esito]:
    """I sei controlli, in ordine. ``rapida=False`` salta la batteria della macchina."""
    esiti = [
        controlla_sede(),
        controlla_cancello(),
        controlla_skill(),
        controlla_mcp(),
        controlla_catalogo(),
    ]
    if rapida:
        esiti.append(controlla_macchina())
    return esiti


def main(argv: list[str] | None = None) -> int:
    argomenti = argv if argv is not None else sys.argv[1:]
    esiti = accendi(rapida="--senza-macchina" not in argomenti)
    mancanti = [e for e in esiti if not e.ok]

    if "--json" in argomenti:
        print(
            json.dumps(
                {"acceso": not mancanti, "esiti": [e.a_dizionario() for e in esiti]},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if not mancanti else 1

    for esito in esiti:
        segno = "ok  " if esito.ok else "NO  "
        print(f"  {segno} {esito.nome:10} {esito.detto}")
        if not esito.ok and esito.rimedio:
            print(f"                -> {esito.rimedio}")
    print()
    if mancanti:
        print(f"  L'ENGINE NON E' COMPLETAMENTE ACCESO: {len(mancanti)} cose da sistemare.")
        print("  Il motore funziona anche cosi', ma una di queste mancanze e' la ragione")
        print("  per cui un controllo potrebbe non scattare quando serve.")
        return 1
    print("  L'ENGINE E' ACCESO. Le regole di AGENTS.md valgono, e i controlli girano.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
