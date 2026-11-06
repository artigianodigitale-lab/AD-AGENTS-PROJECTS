#!/usr/bin/env python3
"""Il consenso verificabile: una firma, il legame col piano, la provenienza (DEC-0096).

Perche' esiste. Un'approvazione, oggi, vale se il file contiene tre campi: `task_id`,
`approvato_da`, `data`. Chiunque possa scrivere in `approvazioni/` crea un marcatore che
dice «approvato da Luca» e il cancello lo accetta. **Il sistema non distingue un consenso
da un file che afferma un consenso.**

Tre cose mancavano, e sono le tre che questo strumento aggiunge:

  1. **la firma** — un HMAC-SHA256 del contenuto, calcolato con una chiave che **non sta nel
     repository**: chi non ha la chiave non puo' firmare, e non puo' nemmeno rifare una
     firma dopo aver manomesso il file. Un hash da solo non basta: chi scrive ricalcola
     l'hash. Una firma richiede il segreto.
  2. **il legame col piano** — `piano_sha256` e' l'impronta del piano nel momento in cui il
     CEO ha approvato. Un piano modificato dopo non e' piu' quello approvato, e si vede.
  3. **la provenienza** — `superficie` dice da dove e' arrivato il consenso (chat, terminale,
     sessione), e `firmato_il` distingue il momento della firma da quello del consenso.

Limite dichiarato: la chiave sta sulla stessa macchina. Non difende da chi ha accesso root —
difende da chi ha accesso al **repository**, che e' il perimetro reale del sistema.

Uso:
    python3 tools/ad_consenso.py chiave-nuova      # crea la chiave (se manca), 0600
    python3 tools/ad_consenso.py stato             # dice se la chiave c'e'
    python3 tools/ad_consenso.py firma <TASK> --superficie chat
    python3 tools/ad_consenso.py verifica          # controlla tutti i marcatori
    python3 tools/ad_consenso.py verifica <TASK>

Esito: 0 tutto a posto · 1 c'e' almeno un problema · 2 uso sbagliato.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import secrets
import stat
import sys
import time
from pathlib import Path

import yaml

RADICE = Path(__file__).resolve().parents[1]
#: La chiave vive FUORI dal repository. E' il punto di tutta la difesa: se stesse qui,
#: chi scrive il repository la leggerebbe e la firma non varrebbe niente.
CARTELLA_CHIAVE = Path.home() / ".dsh"
NOME_CHIAVE = "ad-consenso.key"

#: I campi che entrano nella firma. Tutti tranne `firma`: un campo escluso e' un campo
#: che si puo' cambiare senza invalidare la firma, e quindi non si esclude niente.
CAMPO_FIRMA = "firma"

#: Le superfici ammesse: un consenso senza provenienza non e' tracciabile.
SUPERFICI = ("chat", "terminale", "sessione", "api")


class Rifiuto(Exception):
    """L'operazione non si puo' fare, e il messaggio dice perche'. Esito 1."""


# --------------------------------------------------------------------------- #
# La chiave                                                                    #
# --------------------------------------------------------------------------- #


def percorso_chiave() -> Path:
    return CARTELLA_CHIAVE / NOME_CHIAVE


def chiave_esiste() -> bool:
    return percorso_chiave().is_file()


def leggi_chiave() -> bytes:
    """La chiave HMAC, o un rifiuto. Non si genera da sola: un segreto implicito non e' un segreto."""
    percorso = percorso_chiave()
    try:
        modo = stat.S_IMODE(percorso.stat().st_mode)
    except OSError:
        raise Rifiuto(
            f"manca la chiave {percorso}. Creala con: python3 tools/ad_consenso.py chiave-nuova\n"
            "  (senza la chiave le approvazioni non si possono firmare, e quelle firmate non "
            "si possono verificare)"
        ) from None
    if modo & 0o077:
        raise Rifiuto(
            f"la chiave {percorso} e' leggibile da altri (modo {oct(modo)}): deve essere 600. "
            f"Correggi con: chmod 600 {percorso}"
        )
    try:
        dati = percorso.read_bytes().strip()
    except OSError as errore:
        raise Rifiuto(f"la chiave {percorso} non si legge: {errore}") from None
    if len(dati) < 32:
        raise Rifiuto(f"la chiave {percorso} e' troppo corta ({len(dati)} byte): rifalla")
    return dati


def chiave_nuova(forza: bool = False) -> Path:
    """Crea la chiave, con permessi 600. Se esiste gia', non la tocca (a meno di --forza)."""
    percorso = percorso_chiave()
    if percorso.exists() and not forza:
        raise Rifiuto(
            f"la chiave esiste gia': {percorso}. Non la sovrascrivo: rifarla invaliderebbe "
            "tutte le firme esistenti. Usa --forza solo se sai cosa stai facendo."
        )
    CARTELLA_CHIAVE.mkdir(parents=True, exist_ok=True)
    # `O_EXCL`: due sessioni non possono creare due chiavi diverse contemporaneamente.
    try:
        descrittore = os.open(percorso, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise Rifiuto(f"la chiave e' comparsa mentre la creavo: {percorso}") from None
    except OSError as errore:
        raise Rifiuto(f"non posso creare la chiave in {percorso}: {errore}") from None
    with os.fdopen(descrittore, "wb") as uscita:
        uscita.write(secrets.token_bytes(64))
    os.chmod(percorso, 0o600)
    return percorso


# --------------------------------------------------------------------------- #
# La firma                                                                     #
# --------------------------------------------------------------------------- #


def _canonico(dati: dict) -> bytes:
    """Il contenuto da firmare: tutto tranne la firma, in ordine stabile.

    L'ordine e' stabile perche' il JSON ordinato e' deterministico: se due macchine
    calcolano la stessa firma, devono partire dagli stessi byte.
    """
    senza = {chiave: valore for chiave, valore in dati.items() if chiave != CAMPO_FIRMA}
    return json.dumps(senza, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode(
        "utf-8"
    )


def calcola_firma(dati: dict, chiave: bytes) -> str:
    return hmac.new(chiave, _canonico(dati), hashlib.sha256).hexdigest()


def impronta_piano(percorso: Path) -> str | None:
    """L'impronta del piano approvato, o ``None`` se il piano non c'e'.

    Un marcatore che nomina un piano inesistente e' un consenso a un piano che non
    esiste: si firma lo stesso (il consenso c'e' stato) ma lo si dice.
    """
    try:
        return hashlib.sha256(percorso.read_bytes()).hexdigest()
    except OSError:
        return None


# --------------------------------------------------------------------------- #
# Trovare i marcatori                                                           #
# --------------------------------------------------------------------------- #


def cartella_approvazioni(root: Path) -> Path:
    return root / "approvazioni"


def trova_marcatore(task: str, root: Path = RADICE) -> Path:
    """Il file del marcatore per quel task, cercando in ogni gruppo."""
    cercato = task.strip().upper()
    base = cartella_approvazioni(root)
    if not base.is_dir():
        raise Rifiuto(f"non esiste {base}")
    for percorso in sorted(base.glob("*/*.yaml")):
        if percorso.name.startswith("_"):
            continue
        if percorso.stem.upper() == cercato:
            return percorso
    raise Rifiuto(f"nessun marcatore «{task}» in {base}/<gruppo>/")


def tutti_i_marcatori(root: Path = RADICE) -> list[Path]:
    base = cartella_approvazioni(root)
    if not base.is_dir():
        return []
    return [p for p in sorted(base.glob("*/*.yaml")) if not p.name.startswith("_")]


def _leggi(percorso: Path) -> dict:
    try:
        dato = yaml.safe_load(percorso.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as errore:
        raise Rifiuto(f"«{percorso}» non si legge: {errore}") from None
    except yaml.YAMLError as errore:
        raise Rifiuto(f"«{percorso}» non e' YAML valido: {errore}") from None
    if not isinstance(dato, dict):
        raise Rifiuto(f"«{percorso}» non contiene una mappatura")
    return dato


# --------------------------------------------------------------------------- #
# Firmare e verificare                                                         #
# --------------------------------------------------------------------------- #


def firma(task: str, superficie: str, root: Path = RADICE, *, adesso: str | None = None) -> dict:
    """Firma il marcatore di quel task. Restituisce il marcatore firmato."""
    if superficie not in SUPERFICI:
        raise Rifiuto(f"superficie «{superficie}» non ammessa: {', '.join(SUPERFICI)}")
    percorso = trova_marcatore(task, root)
    dati = _leggi(percorso)

    # I tre campi senza i quali il marcatore non vale nemmeno oggi.
    for campo in ("task_id", "approvato_da", "data"):
        if not str(dati.get(campo, "")).strip():
            raise Rifiuto(
                f"«{percorso.name}» non ha «{campo}»: un marcatore incompleto non si firma "
                "(firmarlo gli darebbe un'autorita' che non ha)"
            )

    chiave = leggi_chiave()
    piano = str(dati.get("piano", "")).strip()
    if piano:
        impronta = impronta_piano(root / piano)
        if impronta is None:
            print(f"  AVVISO: il piano «{piano}» non esiste: il consenso non e' legato a un testo")
        else:
            dati["piano_sha256"] = impronta
    dati["superficie"] = superficie
    dati["firmato_il"] = adesso or time.strftime("%Y-%m-%dT%H:%M:%S%z")
    dati[CAMPO_FIRMA] = calcola_firma(dati, chiave)

    percorso.write_text(
        yaml.safe_dump(dati, allow_unicode=True, sort_keys=False, width=100), encoding="utf-8"
    )
    return dati


def verifica_uno(percorso: Path, chiave: bytes | None, root: Path = RADICE) -> tuple[str, str]:
    """``(stato, messaggio)`` per un marcatore. Gli stati sono i quattro che contano."""
    try:
        dati = _leggi(percorso)
    except Rifiuto as rifiuto:
        return "illeggibile", str(rifiuto)
    if CAMPO_FIRMA not in dati:
        return "non firmata (legacy)", "nessuna firma: vale solo per i contract precedenti a DEC-0096"
    if chiave is None:
        return "verificabile solo con la chiave", "la chiave non c'e': non posso ricalcolare la firma"
    attesa = calcola_firma(dati, chiave)
    if not hmac.compare_digest(str(dati[CAMPO_FIRMA]), attesa):
        return "manomessa", "la firma non combacia: il contenuto e' cambiato dopo la firma"
    piano = str(dati.get("piano", "")).strip()
    registrata = dati.get("piano_sha256")
    if piano and registrata:
        attuale = impronta_piano(root / piano)
        if attuale is None:
            return "piano sparito", f"il piano «{piano}» non esiste piu'"
        if attuale != registrata:
            return "piano cambiato", (
                f"«{piano}» e' cambiato dopo l'approvazione: il consenso era a un altro testo"
            )
    return "firmata", f"da {dati.get('approvato_da')} il {dati.get('data')} via {dati.get('superficie', '?')}"


def verifica_tutti(root: Path = RADICE) -> list[tuple[str, str, str]]:
    """``[(stato, task, messaggio)]`` per ogni marcatore."""
    chiave: bytes | None
    try:
        chiave = leggi_chiave()
    except Rifiuto:
        chiave = None
    esiti: list[tuple[str, str, str]] = []
    for percorso in tutti_i_marcatori(root):
        stato, messaggio = verifica_uno(percorso, chiave, root)
        esiti.append((stato, percorso.stem, messaggio))
    return esiti


# --------------------------------------------------------------------------- #
# Comandi                                                                      #
# --------------------------------------------------------------------------- #


def cmd_chiave_nuova(forza: bool) -> int:
    percorso = chiave_nuova(forza)
    print(f"  chiave creata: {percorso} (modo 600)")
    print("  Non sta nel repository: e' quello che rende una firma una firma.")
    print("  Fanne una copia in un posto sicuro: se la perdi, rifarla invalida le firme esistenti.")
    return 0


def cmd_stato() -> int:
    percorso = percorso_chiave()
    if not percorso.is_file():
        print(f"  chiave: MANCA ({percorso})")
        print("  Creala: python3 tools/ad_consenso.py chiave-nuova")
        return 1
    modo = stat.S_IMODE(percorso.stat().st_mode)
    print(f"  chiave: {percorso}")
    print(f"  permessi: {oct(modo)}" + ("  (corretto: solo il proprietario)" if not modo & 0o077 else "  ATTENZIONE: leggibile da altri"))
    print(f"  dimensione: {percorso.stat().st_size} byte")
    return 0 if not modo & 0o077 else 1


def cmd_firma(task: str, superficie: str) -> int:
    dati = firma(task, superficie)
    print(f"  firmato: {dati.get('task_id')}")
    print(f"  da:      {dati.get('approvato_da')} il {dati.get('data')}")
    print(f"  via:     {dati.get('superficie')} alle {dati.get('firmato_il')}")
    if dati.get("piano_sha256"):
        print(f"  piano:   {dati.get('piano')} ({dati['piano_sha256'][:16]}…)")
    return 0


def cmd_verifica(task: str | None) -> int:
    if task:
        percorso = trova_marcatore(task)
        try:
            chiave = leggi_chiave()
        except Rifiuto:
            chiave = None
        stato, messaggio = verifica_uno(percorso, chiave)
        print(f"  {percorso.stem}: {stato}")
        print(f"    {messaggio}")
        return 0 if stato == "firmata" else 1

    esiti = verifica_tutti()
    if not esiti:
        print("  nessun marcatore da verificare")
        return 0
    conteggio: dict[str, int] = {}
    for stato, _, _ in esiti:
        conteggio[stato] = conteggio.get(stato, 0) + 1
    for stato, task, messaggio in esiti:
        if stato != "firmata":
            print(f"  {task}: {stato} — {messaggio}")
    print()
    for stato in sorted(conteggio):
        print(f"  {stato}: {conteggio[stato]}")
    print(f"  totale: {len(esiti)}")
    # Le «non firmate» sono la storia: non sono un errore. Gli altri stati lo sono.
    gravi = sum(n for s, n in conteggio.items() if s not in ("firmata", "non firmata (legacy)"))
    return 1 if gravi else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ad_consenso.py",
        description="Il consenso verificabile: firma, legame col piano, provenienza (DEC-0096).",
    )
    sotto = parser.add_subparsers(dest="comando", required=True)

    p_chiave = sotto.add_parser("chiave-nuova", help="crea la chiave HMAC in ~/.dsh (modo 600)")
    p_chiave.add_argument("--forza", action="store_true", help="sovrascrive una chiave esistente")

    sotto.add_parser("stato", help="dice se la chiave c'e' e se i permessi sono giusti")

    p_firma = sotto.add_parser("firma", help="firma il marcatore di un task")
    p_firma.add_argument("task")
    p_firma.add_argument(
        "--superficie", default="chat", choices=SUPERFICI, help="da dove arriva il consenso"
    )

    p_ver = sotto.add_parser("verifica", help="verifica uno o tutti i marcatori")
    p_ver.add_argument("task", nargs="?")

    argomenti = parser.parse_args(argv)
    try:
        if argomenti.comando == "chiave-nuova":
            return cmd_chiave_nuova(argomenti.forza)
        if argomenti.comando == "stato":
            return cmd_stato()
        if argomenti.comando == "firma":
            return cmd_firma(argomenti.task, argomenti.superficie)
        return cmd_verifica(argomenti.task)
    except Rifiuto as errore:
        print(f"ad_consenso: {errore}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
