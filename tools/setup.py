#!/usr/bin/env python3
"""L'installazione: la macchina si collega da sola, dove sta.

    python3 tools/setup.py                  installa per DSH
    python3 tools/setup.py --ide claude-code
    python3 tools/setup.py --check          verifica senza scrivere
    python3 tools/setup.py --uninstall      disfa

Perche' esiste, in una riga: **il 2026-10-13 ho copiato la macchina altrove e ha
funzionato** — la radice si scopre, il cancello blocca — **tranne il collegamento**,
che era stato fatto a mano l'8 ottobre con i percorsi assoluti dentro. Il CEO ha chiesto
che «ovunque la metta» funzioni: l'unico pezzo che manca e' questo.

## Cosa collega

Tre cose, e sono tre perche' servono a tre cose diverse:

| Cosa | Dove | A cosa serve |
|---|---|---|
| il **plugin** | `~/.dsh/profiles/<profilo>/cordis.patch.yml` | il cancello che blocca le scritture |
| la **costituzione** | `~/.dsh/AGENTS.md` | le regole che ogni agente legge |
| le **skill** | `~/.agents/skills/ad-*` | le procedure operative |

## L'onesta' che serve

Non tutti gli ambienti hanno un **gancio**: un punto in cui il programma chiede il
permesso *prima* di scrivere. DSH ce l'ha, e li' il cancello **blocca davvero**. Dove
il gancio non c'e', si installano **le regole** — e si **dichiara** che sono regole,
non un cancello. La differenza fra «sconsigliato» e «impossibile» e' tutto quello che
questo sistema ha imparato, e non si cancella per far contenta una tabella.

## Il file di montaggio non si riscrive

`cordis.patch.yml` contiene espressioni `!!js` che nessun parser YAML standard legge.
Quindi **non si parsa e non si rigenera**: si sostituisce la sola riga del percorso del
plugin, e se il blocco non c'e' si aggiunge in testa. Un file di configurazione di
un altro programma non e' nostro, e si tocca il minimo.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ad_docs  # noqa: E402

#: La macchina: la cartella che contiene `.brain/` e `tools/`.
RADICE = ad_docs.DOCS_ROOT
COSTITUZIONE = RADICE / ".brain" / "COSTITUZIONE.md"
SKILLS = RADICE / ".brain" / "skills"
PLUGIN = RADICE / ".brain" / "plugin" / "enforce-contract" / "index.mjs"
CHECKER = RADICE / "tools" / "contract_scope.py"

#: L'identificatore del plugin nel file di montaggio. Deve combaciare con `name`
#: esportato da `index.mjs`: e' quello che DSH cerca.
ID_PLUGIN = "ad-enforce-contract"

#: Il nome del profilo DSH. Sovrascrivibile con --profilo.
PROFILO = os.environ.get("AD_DSH_PROFILO", "web")

#: Gli ambienti e cosa si puo' davvero fare in ciascuno.
#:
#: `gancio` e' la differenza che conta: **True** significa che esiste un punto in cui
#: il programma chiede il permesso prima di scrivere, e li' il cancello blocca.
#: **False** significa che si installano le regole, e basta — e va detto.
AMBIENTI = {
    "dsh": {
        "gancio": True,
        "regole": "~/.dsh/AGENTS.md",
        "skill": "~/.agents/skills",
        "perche": "monta il plugin nel layer del profilo: il cancello e' attivo",
    },
    "claude-code": {
        "gancio": True,
        "regole": "CLAUDE.md",
        "skill": ".claude/skills",
        "perche": (
            "il gancio PreToolUse esiste e puo' rispondere `permissionDecision: deny`; "
            "l'adattatore si scrive a parte e va provato dentro Claude Code"
        ),
    },
    "codex": {
        "gancio": True,
        "regole": "AGENTS.md",
        "skill": ".codex/skills",
        "perche": "legge AGENTS.md; i ganci vanno dichiarati nella sua configurazione",
    },
    "cursor": {
        "gancio": False,
        "regole": ".cursor/rules/ad-projects.mdc",
        "skill": "",
        "perche": (
            "riceve le REGOLE, non il cancello: un file di regole orienta, non impedisce. "
            "DEC-0039 ha gia' deciso di non trattare Cursor come una superficie da bloccare"
        ),
    },
    "antigravity": {
        "gancio": True,
        "regole": "AGENTS.md",
        "skill": "",
        "perche": "i ganci sono documentati; l'adattatore va scritto e provato li'",
    },
}


def _profilo_dsh() -> Path:
    """Il layer di patch del profilo DSH attivo."""
    return Path.home() / ".dsh" / "profiles" / PROFILO / "cordis.patch.yml"


def _collega(percorso: Path, destinazione: Path, asciutto: bool) -> str:
    """Un collegamento simbolico, rifatto se punta altrove. Idempotente."""
    if destinazione.is_symlink():
        if destinazione.resolve() == percorso.resolve():
            return "gia' a posto"
        if not asciutto:
            destinazione.unlink()
    elif destinazione.exists():
        return "esiste ed e' un file vero: NON toccato"
    if asciutto:
        return "da creare"
    destinazione.parent.mkdir(parents=True, exist_ok=True)
    destinazione.symlink_to(percorso)
    return "collegato"


def installa_montaggio(asciutto: bool = False) -> str:
    """Mette il plugin nel layer del profilo DSH, con il percorso **vero**.

    Si tocca **una riga**: il percorso. Il resto del file non e' nostro.
    """
    patch = _profilo_dsh()
    if patch.exists():
        pass
    elif patch.parent.is_dir():
        # La cartella del profilo c'e' ma il file no: si crea. Un'installazione
        # nuova di DSH puo' non averlo ancora, e non sapere il percorso del plugin.
        if asciutto:
            return f"da creare: {patch}"
        patch.write_text("", encoding="utf-8")
    else:
        return (
            f"non posso montare: {patch.parent} non esiste. "
            "DSH non e' installato qui, oppure il profilo si chiama diversamente — "
            "in quel caso: --profilo <nome>"
        )

    testo = patch.read_text(encoding="utf-8")
    riga = f"          name: {PLUGIN}"

    # gia' montato, con il percorso giusto?
    if re.search(rf"^\s*name:\s*{re.escape(str(PLUGIN))}\s*$", testo, re.M):
        return "gia' a posto"

    # montato, ma con un ALTRO percorso: e' il caso della macchina spostata.
    schema = re.compile(
        rf"(^\s*-?\s*insert:\s*\n\s*-\s*id:\s*{re.escape(ID_PLUGIN)}\s*\n\s*name:\s*)(\S.*)$",
        re.M,
    )
    if schema.search(testo):
        if asciutto:
            return "da aggiornare: il percorso nel montaggio e' quello vecchio"
        testo = schema.sub(lambda m: m.group(1) + str(PLUGIN), testo, count=1)
        patch.write_text(testo, encoding="utf-8")
        return "aggiornato: il percorso puntava a un'altra sede"

    blocco = (
        f"    # Enforcement di runtime del cervello di AD Projects.\n"
        f"    # Scritto da tools/setup.py: il percorso e' quello dove la macchina sta ORA.\n"
        f"    - insert:\n"
        f"        - id: {ID_PLUGIN}\n"
        f"          name: {PLUGIN}\n"
    )
    if asciutto:
        return "da aggiungere in testa al layer"
    patch.write_text(blocco + testo, encoding="utf-8")
    return "montato"


def installa_dsh(asciutto: bool = False) -> list[tuple[str, str]]:
    """I tre collegamenti di DSH. Restituisce (cosa, esito)."""
    esiti: list[tuple[str, str]] = []
    esiti.append(("montaggio del plugin", installa_montaggio(asciutto)))

    if not COSTITUZIONE.is_file():
        esiti.append(("costituzione", f"NON TROVATA: {COSTITUZIONE}"))
    else:
        esiti.append(
            ("costituzione", _collega(COSTITUZIONE, Path.home() / ".dsh" / "AGENTS.md", asciutto))
        )

    if not SKILLS.is_dir():
        esiti.append(("skill", f"NON TROVATE: {SKILLS}"))
    else:
        quante = 0
        for skill in sorted(SKILLS.iterdir()):
            if not skill.is_dir():
                continue
            destinazione = Path.home() / ".agents" / "skills" / skill.name
            if _collega(skill, destinazione, asciutto) != "esiste ed e' un file vero: NON toccato":
                quante += 1
        esiti.append(("skill", f"{quante} collegate su {len(list(SKILLS.iterdir()))}"))
    return esiti


def installa_regole(ambiente: str, asciutto: bool = False) -> str:
    """Il file delle regole, per gli ambienti che non sono DSH.

    Punta alla costituzione invece di copiarla: **una sola fonte**. Una copia
    invecchierebbe in silenzio, e sarebbe il difetto che questo sistema combatte.
    """
    fuori = ["~/.dsh/AGENTS.md", "~/.dsh"]
    percorso_rel = AMBIENTI[ambiente]["regole"]
    if any(percorso_rel.startswith(f) for f in fuori):
        return "lo installa il montaggio DSH"
    if not percorso_rel:
        return "questo ambiente non ha un file di regole dichiarato"

    destinazione = RADICE / percorso_rel
    if destinazione.exists():
        return f"gia' presente: {percorso_rel} (non toccato)"
    if asciutto:
        return f"da creare: {percorso_rel}"

    destinazione.parent.mkdir(parents=True, exist_ok=True)
    if destinazione.suffix == ".mdc":
        contenuto = (
            "---\ndescription: AD Projects — regole operative\nglobs: \nalwaysApply: true\n---\n\n"
            f"# AD Projects\n\nLe regole stanno in **una sola fonte**: `{COSTITUZIONE.relative_to(RADICE)}`.\n"
            "Leggile da li': non sono copiate qui, perche' una copia invecchia in silenzio.\n\n"
            f"Radice della macchina: `{RADICE}`\n"
        )
    else:
        contenuto = (
            "# AD Projects\n\n"
            f"Le regole operative stanno in **una sola fonte**: `{COSTITUZIONE.relative_to(RADICE)}`.\n"
            "Leggile da li'. Questo file esiste perche' l'ambiente cerca le regole qui.\n\n"
            f"Radice della macchina: `{RADICE}`\n"
        )
    destinazione.write_text(contenuto, encoding="utf-8")
    return f"creato: {percorso_rel}"


def installa_skill(ambiente: str, asciutto: bool = False) -> str:
    """Le skill, dove l'ambiente le cerca. Collegamenti, non copie."""
    dove = AMBIENTI[ambiente].get("skill") or ""
    if not dove or dove.startswith("~/.agents"):
        return "le collega il montaggio DSH" if dove else "questo ambiente non ha una cartella dichiarata"
    destinazione = RADICE / dove
    if asciutto:
        return f"da collegare in {dove}"
    destinazione.mkdir(parents=True, exist_ok=True)
    quante = 0
    for skill in sorted(SKILLS.iterdir()):
        if not skill.is_dir():
            continue
        _collega(skill, destinazione / skill.name, asciutto)
        quante += 1
    return f"{quante} skill in {dove}"


# ---------------------------------------------------------------------------
# La prova
# ---------------------------------------------------------------------------


def prova(ambiente: str) -> list[tuple[bool, str]]:
    """Le prove. Una sola conta piu' di tutte: **la scrittura viene rifiutata?**

    Non si dichiara «installato»: si prova che il cancello rifiuta. E' la differenza
    fra una regola scritta e un controllo che fallisce.
    """
    esiti: list[tuple[bool, str]] = []

    esiti.append((PLUGIN.is_file(), f"il plugin esiste: {PLUGIN.relative_to(RADICE)}"))

    montato = _profilo_dsh().exists() and ID_PLUGIN in _profilo_dsh().read_text(encoding="utf-8")
    if ambiente == "dsh":
        esiti.append((montato, "il montaggio dichiara il plugin"))
        if montato:
            testo = _profilo_dsh().read_text(encoding="utf-8")
            esiti.append(
                (str(PLUGIN) in testo, "e il percorso e' quello di ADESSO, non di un'altra sede")
            )
        esiti.append(
            (
                (Path.home() / ".dsh" / "AGENTS.md").is_symlink()
                and (Path.home() / ".dsh" / "AGENTS.md").resolve() == COSTITUZIONE.resolve(),
                "la costituzione e' collegata alla macchina",
            )
        )

    # La prova che conta: una scrittura dentro un progetto DEVE essere rifiutata.
    #
    # **Si crea il progetto di prova, non si spera che ce ne sia uno.** Il 2026-10-13,
    # provando AAP come motore vergine, questa prova diceva «nessuna cartella numerata:
    # non posso provare il rifiuto» — e un motore appena scaricato **non ha progetti**.
    # Una prova che dipende da un progetto esistente non prova niente su un motore
    # nuovo: e' il momento in cui serve di piu'.
    #
    # La cartella si crea, si prova, e **si toglie** — anche se qualcosa va storto.
    base = ad_docs.PROGETTI_ROOT
    prova = base / "99. Prova Del Cancello"
    creata = False
    try:
        if not prova.exists():
            prova.mkdir(parents=True)
            creata = True
        esito = subprocess.run(
            [sys.executable, str(CHECKER), "check", "99. Prova Del Cancello/una-prova.ts",
             "--root", str(RADICE)],
            capture_output=True,
            text=True,
            cwd=str(base),
        )
        rifiutata = esito.returncode != 0
        esiti.append(
            (rifiutata, "il cancello RIFIUTA una scrittura in una cartella di progetto")
        )
    except Exception as errore:  # noqa: BLE001
        esiti.append((False, f"non ho potuto provare il rifiuto: {type(errore).__name__}"))
    finally:
        if creata:
            shutil.rmtree(prova, ignore_errors=True)

    # E il plugin, se e' li', deve passare le sue prove.
    if ambiente == "dsh" and PLUGIN.is_file():
        node = shutil.which("node")
        test = PLUGIN.parent / "test.mjs"
        if node and test.is_file():
            esito = subprocess.run(
                [node, str(test)], capture_output=True, text=True, cwd=str(RADICE)
            )
            esiti.append((esito.returncode == 0, "le prove del plugin passano"))
    return esiti


def disinstalla(ambiente: str) -> list[tuple[str, str]]:
    """Disfa quello che l'installatore ha fatto. **Nient'altro.**"""
    esiti: list[tuple[str, str]] = []
    patch = _profilo_dsh()
    if ambiente == "dsh" and patch.exists():
        testo = patch.read_text(encoding="utf-8")
        # Si tolgono anche le righe di commento che ha scritto l'installatore:
        # disfare deve lasciare il file come l'ha trovato, non "quasi" come l'ha
        # trovato. Un residuo e' una bugia che resta.
        blocco = re.compile(
            rf"(?:^\s*#[^\n]*\n)*^\s*-?\s*insert:\s*\n\s*-\s*id:\s*"
            rf"{re.escape(ID_PLUGIN)}\s*\n\s*name:.*\n?",
            re.M,
        )
        nuovo = blocco.sub("", testo, count=1)
        if nuovo != testo:
            patch.write_text(nuovo, encoding="utf-8")
            esiti.append(("montaggio del plugin", "rimosso"))
        else:
            esiti.append(("montaggio del plugin", "non c'era"))

        for percorso in (Path.home() / ".dsh" / "AGENTS.md",):
            if percorso.is_symlink():
                percorso.unlink()
                esiti.append((str(percorso), "scollegato"))
        for skill in sorted((Path.home() / ".agents" / "skills").glob("ad-*")):
            if skill.is_symlink():
                skill.unlink()
        esiti.append(("skill", "scollegate"))
    return esiti


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Installazione della macchina AD Projects")
    parser.add_argument(
        "--ide",
        default="dsh",
        choices=sorted(AMBIENTI),
        help="per quale ambiente (default: dsh)",
    )
    parser.add_argument("--check", action="store_true", help="verifica senza scrivere")
    parser.add_argument("--uninstall", action="store_true", help="disfa")
    args = parser.parse_args(argv)

    asciutto = args.check
    ambiente = args.ide
    info = AMBIENTI[ambiente]

    print(f"  macchina: {RADICE}")
    print(f"  ambiente: {ambiente} — {'CANCELLO' if info['gancio'] else 'solo REGOLE'}")
    print(f"            {info['perche']}")
    print()

    if args.uninstall:
        for cosa, esito in disinstalla(ambiente):
            print(f"  {cosa:24} {esito}")
        return 0

    if asciutto:
        print("  VERIFICA (non scrive niente)")
        for cosa, esito in installa_dsh(asciutto=True) if ambiente == "dsh" else []:
            print(f"  {cosa:24} {esito}")
    else:
        print("  INSTALLAZIONE")
        if ambiente == "dsh":
            for cosa, esito in installa_dsh():
                print(f"  {cosa:24} {esito}")
        else:
            print(f"  {AMBIENTI[ambiente]['regole']:24} {installa_regole(ambiente)}")
            if info.get("skill"):
                print(f"  {'skill':24} {installa_skill(ambiente)}")

    print()
    print("  PROVE")
    falliti = 0
    for ok, descrizione in prova(ambiente):
        print(f"  {'ok  ' if ok else 'NO  '} {descrizione}")
        falliti += 0 if ok else 1

    print()
    if falliti:
        print(f"  esito: {falliti} prove fallite — l'installazione NON e' completa")
        return 1
    print("  esito: installato e provato")
    if ambiente == "dsh":
        print("        (il montaggio del plugin ha effetto al prossimo avvio di DSH)")
    elif not info["gancio"]:
        print("        (in questo ambiente valgono le REGOLE, non un cancello che blocca)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
