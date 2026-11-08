#!/usr/bin/env python3
"""Attiva QUESTA macchina: i tre ganci che la rendono viva, e la prova che lo sono.

Perche' esiste. Il 2026-11-08 l'analisi di `100.AAP` ha trovato che il codice e'
portabile — nessun percorso assoluto, `RADICE = Path(__file__).parents[1]` in tutti gli
strumenti, il cancello scopre la radice da se' — ma **l'accensione no**:

    ~/.dsh/AGENTS.md      -> il cervello della PRIMA macchina
    ~/.agents/skills/     10 symlink, tutti verso la prima macchina, 0 verso questa

Quindi scrivere `AGENTS.md` accendeva la macchina sbagliata. Il codice era indipendente;
l'interruttore no.

## I tre ganci

  1. **`~/.dsh/AGENTS.md`** — il symlink che DSH legge a ogni sessione. Deve puntare al
     cervello di questa macchina, non a quello di un'altra.
  2. **`~/.agents/skills/`** — i symlink delle dieci procedure. Devono venire da questa
     macchina.
  3. **`~/.dsh/profiles/<p>/cordis.patch.yml`** — il plugin del cancello, montato in
     **ogni** profilo DSH. Su uno solo e' la storia di `ERR-0086`: il cancello era in
     `web`, la sessione girava in `desktop`, e ogni verifica diceva «installato».

## La regola che questo comando rispetta: una macchina accesa, non due

I ganci stanno nella **home dell'utente**, non nella cartella del motore. Due macchine
sullo stesso utente non possono essere accese insieme dallo stesso interruttore. Percio'
`attiva.py` non aggiunge soltanto: **elenca quello che smonta**, e lo fa in chiaro. Una
macchina accesa e una mezza accesa e' peggio di una spenta, perche' nessuno sa piu' dove
sta il cancello.

## La regola che questo comando rispetta: non tocca niente senza dirlo

`--check` dice cosa manca e **non scrive niente**. Senza `--check` scrive solo i tre
ganci e li elenca, uno per uno. `--disattiva` li toglie e riporta com'erano.

`--home` esiste per una ragione sola, e non e' una comodita': **una prova di portabilita'
non deve smontare la macchina vera**. Il test passa un `HOME` temporaneo, e il motore
vero del CEO non se ne accorge.

Uso:
    python3 tools/attiva.py                 # attiva questa macchina
    python3 tools/attiva.py --check         # dice cosa manca, senza scrivere
    python3 tools/attiva.py --disattiva     # toglie i ganci di questa macchina
    python3 tools/attiva.py --home /tmp/x   # su una home diversa (per le prove)

Esito: 0 fatto o gia' a posto · 1 qualcosa non ha funzionato · 2 uso sbagliato.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]

#: Il nome che identifica le skill di questa macchina: sono le cartelle dentro
#: `.brain/skills/`. Il collegamento si fa per nome, non per contenuto.
CARTELLA_SKILL = Path(".brain") / "skills"

#: Il file che DSH legge come regolamento a ogni sessione, nella home dell'utente.
GANCIO_AVVIO = Path(".dsh") / "AGENTS.md"

#: Dove vivono i collegamenti delle skill.
GANCIO_SKILL = Path(".agents") / "skills"

#: I profili DSH, ognuno col suo `cordis.patch.yml`.
CARTELLA_PROFILI = Path(".dsh") / "profiles"

#: L'identificatore del server MCP nel `cordis.patch.yml`. Il quarto gancio, e quello
#: che si dimentica: senza, gli strumenti `ad_*` non sono raggiungibili e `accendi.py`
#: dice «non e' dichiarato in nessun profilo». Il 2026-11-08 la prova di portabilita' lo
#: ha trovato perche' provava l'ESITO e non la presenza dei file.
ID_MCP = "ad-projects-mcp"


def _home(esplicita: Path | None) -> Path:
    """La home su cui lavorare.

    Senza `--home` e' quella vera dell'utente. Con `--home` e' quella indicata: serve
    alle prove di portabilita', che devono poter simulare un altro PC senza smontare
    la macchina di chi lavora.
    """
    if esplicita is not None:
        return Path(esplicita).expanduser().resolve()
    return Path.home()


def _skill_di_questa_macchina() -> list[Path]:
    """Le procedure che questa macchina ha davvero."""
    cartella = RADICE / CARTELLA_SKILL
    if not cartella.is_dir():
        return []
    return sorted(p for p in cartella.iterdir() if p.is_dir())


def _punto_a(percorso: Path, bersaglio: Path) -> bool:
    """Il collegamento punta gia' esattamente li'?"""
    if not percorso.is_symlink():
        return False
    try:
        return percorso.resolve() == bersaglio.resolve()
    except OSError:
        return False


def _proprietario(percorso: Path) -> str:
    """A quale macchina appartiene oggi questo gancio, se a una."""
    if not percorso.is_symlink():
        return "nessuno (non e' un collegamento)"
    try:
        vera = percorso.resolve()
    except OSError:
        return "rotto"
    # Il proprietario e' la cartella che contiene `.brain/`: due livelli sopra
    # `.brain/skills/<nome>` o `.brain/COSTITUZIONE.md`.
    for genitore in [vera] + list(vera.parents):
        if (genitore / ".brain").is_dir():
            return genitore.name
    return f"altrove ({vera})"


def controlla(home: Path, profilo: str | None = None) -> list[tuple[str, bool, str]]:
    """Cosa manca perche' questa macchina sia accesa. Non scrive niente.

    Restituisce (descrizione, a_posto, dettaglio) per ogni gancio.
    """
    esiti: list[tuple[str, bool, str]] = []

    # 1. Il gancio di avvio
    avvio = home / GANCIO_AVVIO
    costituzione = RADICE / ".brain" / "COSTITUZIONE.md"
    if not costituzione.is_file():
        esiti.append(("avvio", False, f"manca il cervello: {costituzione}"))
    elif _punto_a(avvio, costituzione):
        esiti.append(("avvio", True, f"punta a questa macchina ({RADICE.name})"))
    else:
        esiti.append(
            ("avvio", False, f"punta a {_proprietario(avvio)}, non a {RADICE.name}")
        )

    # 2. Le skill
    skill = _skill_di_questa_macchina()
    if not skill:
        esiti.append(("skill", False, f"questa macchina non ha {CARTELLA_SKILL}/"))
    else:
        cartella = home / GANCIO_SKILL
        a_posto = 0
        for una in skill:
            collegamento = cartella / una.name
            if _punto_a(collegamento, una):
                a_posto += 1
        esiti.append(
            (
                "skill",
                a_posto == len(skill),
                f"{a_posto}/{len(skill)} collegate a questa macchina",
            )
        )

    # 3. Il server MCP: il quarto gancio, quello che si dimentica.
    profili_mcp = _scegli_profili(_profili(home), profilo)
    if not profili_mcp:
        esiti.append(("mcp", False, "nessun profilo DSH trovato"))
    else:
        con_mcp = [p for p in profili_mcp if ID_MCP in _leggi_patch(home, p)]
        esiti.append(
            (
                "mcp",
                bool(con_mcp),
                f"dichiarato in {len(con_mcp)}/{len(profili_mcp)}"
                + ("" if con_mcp else " — gli strumenti ad_* non sarebbero raggiungibili"),
            )
        )

    # 4. Il cancello, in ogni profilo
    profili = _scegli_profili(_profili(home), profilo)
    if not profili:
        esiti.append(("cancello", False, "nessun profilo DSH trovato"))
    else:
        montati = [p for p in profili if _montato_in(home, p)]
        esiti.append(
            (
                "cancello",
                len(montati) == len(profili),
                f"{len(montati)}/{len(profili)} profili ({', '.join(profili)})",
            )
        )

    return esiti


def profilo_preferito() -> str | None:
    """Il profilo DSH dichiarato in `sede.yaml`, se c'e'.

    Perche' sta nella sede: la sede e' gia' la carta d'identita' della macchina — chi e'
    il CEO, come si chiama. Il profilo su cui vive il suo cancello e' la stessa domanda,
    e una seconda risposta scritta altrove sarebbe un secondo posto da tenere allineato.
    """
    sede = RADICE / "sede.yaml"
    if not sede.is_file():
        return None
    try:
        import yaml
        dati = yaml.safe_load(sede.read_text(encoding="utf-8")) or {}
    except Exception:
        return None
    macchina = dati.get("macchina") or {}
    valore = macchina.get("profilo")
    return str(valore).strip() if valore else None


def _profili(home: Path) -> list[str]:
    """I profili DSH che esistono davvero, su quella home."""
    radice = home / CARTELLA_PROFILI
    if not radice.is_dir():
        return []
    return sorted(
        voce.name
        for voce in radice.iterdir()
        if voce.is_dir() and (voce / "cordis.patch.yml").is_file()
    )


def _scegli_profili(tutti: list[str], scelto: str | None) -> list[str]:
    """Quali profili montare.

    Senza scelta, tutti: e' il comportamento che evita `ERR-0086` (il cancello in `web`
    mentre la sessione girava in `desktop`). Con `--profilo`, uno solo: e' il meccanismo
    che separa i motori. La differenza e' voluta, e va scelta — non indovinata.
    """
    if not scelto:
        return tutti
    return [scelto] if scelto in tutti else tutti


def _plugin_di_questa_macchina() -> Path:
    """Il plugin del cancello che vive in questa macchina."""
    return RADICE / ".brain" / "plugin" / "enforce-contract"


def _leggi_patch(home: Path, profilo: str) -> str:
    patch = home / CARTELLA_PROFILI / profilo / "cordis.patch.yml"
    try:
        return patch.read_text(encoding="utf-8")
    except OSError:
        return ""


def _montato_in(home: Path, profilo: str) -> bool:
    """Il plugin DI QUESTA macchina e' montato in quel profilo?

    Non basta che una riga `enforce-contract` esista: deve puntare al plugin di questa
    macchina. Un profilo montato col plugin di un'altra macchina e' peggio di uno
    smontato, perche' sembra a posto e non lo e'.
    """
    testo = _leggi_patch(home, profilo)
    if not testo:
        return False
    # Il cancello di QUESTA macchina: il percorso del suo plugin. L'id da solo non
    # basta — ogni macchina usa `ad-enforce-contract`, e un profilo montato col plugin
    # di un'altra sembrerebbe a posto.
    return str(_plugin_di_questa_macchina() / "index.mjs") in testo


def attiva(home: Path, asciutto: bool = False, profilo: str | None = None) -> int:
    """Punta i tre ganci su questa macchina. Restituisce l'exit code."""
    print(f"  macchina: {RADICE}")
    print(f"  home:     {home}")
    print()

    if asciutto:
        print("  CONTROLLO (non scrive niente)")
    else:
        print("  ATTIVAZIONE")

    fallimenti = 0
    smontati: list[str] = []

    # --- 1. Il gancio di avvio ---------------------------------------------
    avvio = home / GANCIO_AVVIO
    costituzione = RADICE / ".brain" / "COSTITUZIONE.md"
    if not costituzione.is_file():
        print(f"  NO   avvio: manca il cervello di questa macchina ({costituzione})")
        fallimenti += 1
    elif _punto_a(avvio, costituzione):
        print(f"  ok   avvio: gia' su questa macchina")
    else:
        prima = _proprietario(avvio)
        if prima != "nessuno (non e' un collegamento)":
            smontati.append(f"avvio: era di {prima}")
        if asciutto:
            print(f"  ..   avvio: punterebbe a {RADICE.name} (ora: {prima})")
        else:
            avvio.parent.mkdir(parents=True, exist_ok=True)
            if avvio.is_symlink() or avvio.exists():
                avvio.unlink()
            avvio.symlink_to(costituzione)
            print(f"  ok   avvio: {avvio} -> {costituzione}")

    # --- 2. Le skill --------------------------------------------------------
    skill = _skill_di_questa_macchina()
    if not skill:
        print(f"  NO   skill: questa macchina non ha {CARTELLA_SKILL}/")
        fallimenti += 1
    else:
        cartella = home / GANCIO_SKILL
        collegate = 0
        for una in skill:
            collegamento = cartella / una.name
            if _punto_a(collegamento, una):
                collegate += 1
                continue
            prima = _proprietario(collegamento)
            if collegamento.exists() or collegamento.is_symlink():
                smontati.append(f"skill {una.name}: era di {prima}")
            if asciutto:
                continue
            cartella.mkdir(parents=True, exist_ok=True)
            if collegamento.is_symlink() or collegamento.exists():
                collegamento.unlink()
            collegamento.symlink_to(una)
        if asciutto:
            print(f"  ..   skill: {collegate}/{len(skill)} gia' su questa macchina")
        else:
            print(f"  ok   skill: {len(skill)} collegate a questa macchina")

    # --- 3. Il server MCP ---------------------------------------------------
    # Il quarto gancio. Senza, gli strumenti `ad_*` non sono raggiungibili e la
    # macchina e' accesa a meta': `accendi.py` lo dice, ma solo se lo si esegue.
    # La voce la sa scrivere `tools/ad_mcp/install.py`; qui si chiama quello, perche'
    # due modi di scrivere lo stesso blocco sarebbero due posti da tenere allineati.
    profili_mcp = _scegli_profili(_profili(home), profilo)
    if not profili_mcp:
        print("  NO   mcp: nessun profilo DSH trovato")
        fallimenti += 1
    elif any(ID_MCP in _leggi_patch(home, p) for p in profili_mcp):
        print(f"  ok   mcp: dichiarato")
    else:
        installatore = RADICE / "tools" / "ad_mcp" / "install.py"
        if asciutto:
            print(f"  ..   mcp: da dichiarare (con {installatore.name})")
        elif not installatore.is_file():
            print(f"  NO   mcp: manca {installatore}")
            fallimenti += 1
        else:
            esito = subprocess.run(
                [sys.executable, str(installatore), "--apply", "auto"],
                cwd=str(RADICE), capture_output=True, text=True, timeout=180,
                env={**os.environ, "HOME": str(home)},
            )
            fatto = any(ID_MCP in _leggi_patch(home, p) for p in profili_mcp)
            print(f"  {'ok  ' if fatto else 'NO  '} mcp: dichiarato")
            if not fatto:
                fallimenti += 1

    # --- 4. Il cancello, su ogni profilo ------------------------------------
    profili = _scegli_profili(_profili(home), profilo)
    if not profili:
        print("  NO   cancello: nessun profilo DSH trovato su questa home")
        fallimenti += 1
    else:
        for profilo in profili:
            if _montato_in(home, profilo):
                print(f"  ok   cancello: montato in «{profilo}»")
                continue
            if asciutto:
                print(f"  ..   cancello: da montare in «{profilo}»")
                continue
            esito = _monta(home, profilo)
            print(f"  {'ok  ' if esito else 'NO  '} cancello: «{profilo}»")
            if not esito:
                fallimenti += 1

    # --- Cosa abbiamo smontato ---------------------------------------------
    if smontati:
        print()
        print("  SMONTATI (appartenevano a un'altra macchina):")
        for voce in smontati:
            print(f"    {voce}")
        print("  Una macchina accesa, non due. I ganci sono uno per utente.")

    print()
    if fallimenti:
        print(f"  {fallimenti} ganci non a posto: la macchina NON e' completamente accesa.")
        return 1
    print(f"  QUESTA MACCHINA E' ATTIVA: {RADICE.name}")
    return 0


def _monta(home: Path, profilo: str) -> bool:
    """Monta il plugin del cancello di questa macchina in un profilo.

    Il `cordis.patch.yml` e' YAML con commenti: si aggiunge una voce senza riscrivere
    il resto. La stessa forma che usa `setup.py`, perche' il file e' lo stesso e due
    modi di scriverlo sarebbero due posti da tenere allineati.
    """
    patch = home / CARTELLA_PROFILI / profilo / "cordis.patch.yml"
    plugin = _plugin_di_questa_macchina()
    if not plugin.is_dir():
        return False
    try:
        testo = patch.read_text(encoding="utf-8")
    except OSError:
        return False
    if str(plugin) in testo:
        return True

    # Il formato vero, preso dal profilo che funziona (`~/.dsh/profiles/desktop`):
    #
    #     - id: ad-enforce-contract
    #       name: /percorso/al/plugin/index.mjs
    #
    # `name` e' il percorso, `id` e' l'identita'. Servono entrambi: il controllo
    # dell'accensione cerca l'id, e la radice del cancello viene da `name`.
    # Il 2026-11-08 ho scritto prima `- path:` e il montaggio non veniva visto: la
    # forma sbagliata e' invisibile, che e' peggio di un errore.
    voce = (
        f"    - id: ad-enforce-contract\n"
        f"      name: {plugin / 'index.mjs'}\n"
    )
    if "plugins:" in testo:
        # C'e' gia' la sezione: si aggiunge la voce in coda, senza riscrivere il resto.
        patch.write_text(testo.rstrip() + "\n" + voce, encoding="utf-8")
    else:
        patch.write_text(
            testo.rstrip() + "\n\nplugins:\n" + voce, encoding="utf-8"
        )
    return True


def disattiva(home: Path) -> int:
    """Toglie i ganci di questa macchina, e solo quelli."""
    print(f"  macchina: {RADICE.name}")
    print(f"  home:     {home}")
    print()
    tolti = 0

    avvio = home / GANCIO_AVVIO
    if _punto_a(avvio, RADICE / ".brain" / "COSTITUZIONE.md"):
        avvio.unlink()
        print(f"  tolto  avvio")
        tolti += 1

    cartella = home / GANCIO_SKILL
    for una in _skill_di_questa_macchina():
        collegamento = cartella / una.name
        if _punto_a(collegamento, una):
            collegamento.unlink()
            tolti += 1
    if tolti:
        print(f"  tolte  skill di questa macchina")

    for profilo in _profili(home):
        if _montato_in(home, profilo):
            print(f"  NOTA   cancello ancora montato in «{profilo}»: si toglie con tools/setup.py --uninstall")

    print()
    print(f"  {tolti} ganci tolti. Questa macchina non e' piu' attiva.")
    return 0


def main(argv: list[str] | None = None) -> int:
    analizzatore = argparse.ArgumentParser(
        description="Attiva questa macchina: i tre ganci, e la prova che lo sono."
    )
    analizzatore.add_argument("--check", action="store_true", help="dice cosa manca, senza scrivere")
    analizzatore.add_argument("--disattiva", action="store_true", help="toglie i ganci di questa macchina")
    analizzatore.add_argument(
        "--home",
        help="la home su cui lavorare (default: quella dell'utente). Serve alle prove di portabilita'.",
    )
    analizzatore.add_argument(
        "--profilo",
        help="monta il cancello in UN profilo DSH soltanto. E' il meccanismo che separa "
             "i motori: ogni motore ha il suo profilo, e il suo cancello non copre i "
             "progetti di un altro. Senza, si monta su tutti (ERR-0086).",
    )
    analizzatore.add_argument("--json", action="store_true", help="esito in JSON")
    args = analizzatore.parse_args(argv)

    home = _home(Path(args.home) if args.home else None)

    if args.disattiva:
        return disattiva(home)

    if args.check:
        esiti = controlla(home, args.profilo)
        if args.json:
            print(json.dumps(
                [{"gancio": g, "ok": ok, "dettaglio": d} for g, ok, d in esiti],
                ensure_ascii=False, indent=2,
            ))
            return 0 if all(ok for _, ok, _ in esiti) else 1
        print(f"  macchina: {RADICE.name}")
        print(f"  home:     {home}")
        print()
        for gancio, ok, dettaglio in esiti:
            print(f"  {'ok  ' if ok else 'NO  '} {gancio:10} {dettaglio}")
        print()
        if all(ok for _, ok, _ in esiti):
            print(f"  QUESTA MACCHINA E' ATTIVA: {RADICE.name}")
            return 0
        print("  La macchina NON e' completamente attiva. Rilancia senza --check per attivarla.")
        return 1

    return attiva(home, profilo=args.profilo)


if __name__ == "__main__":
    raise SystemExit(main())
