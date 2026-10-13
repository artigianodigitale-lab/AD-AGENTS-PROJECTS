#!/usr/bin/env python3
"""I verbali: la struttura che il modello chiede, e l'esito che nessuno scrive.

Perche' esiste, in una riga: il modello di `DECISIONI/_TEMPLATE.md` **chiedeva gia'**
le cose giuste — le opzioni compreso il non fare nulla, la metrica, la data di
revisione — e per 36 verbali **non l'ho seguito**: ho scritto sezioni mie, ogni
volta diverse.

La conseguenza, misurata il 2026-10-10 su 36 verbali:

    alternative scartate .......... 20 su 36
    cosa succede se non si fa nulla  10 su 36
    esito misurato ................  3 su 36

Il modello non era sbagliato. **Mancava il controllo.** Un modello che nessuno
verifica e' un buon proposito, e i buoni propositi non cambiano il comportamento.

Uso:
    python3 tools/verbali.py check     # i verbali seguono il modello?
    python3 tools/verbali.py list      # l'indice, con l'esito
    python3 tools/verbali.py show <id>

Esito: 0 tutto a posto, 1 almeno un verbale fuori modello, 2 scrittura rifiutata
perche' nessun contract approvato copre il percorso.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

import ad_docs
import yaml

RADICE = Path(__file__).resolve().parents[1]
CARTELLA = "DECISIONI"

#: Il primo verbale scritto **seguendo il modello**. Quelli prima sono esenti, e il
#: perche' e' scritto qui: sono 36 record scritti a mano libera, e sono immutabili —
#: riscriverli per farli entrare in una regola nata dopo sarebbe falsificare la storia.
PRIMO_CON_MODELLO = 37

#: I campi del blocco YAML.
CAMPI = {
    "id": "l'identificatore, uguale al nome del file",
    "stato": "proposto | approvato | respinto | superato",
    "livello": "2 = orchestratore competente | 3 = il CEO",
    "data": "quando e' stato scritto",
    "approver": "chi decide",
}

#: Le sezioni del modello, e la domanda a cui rispondono.
SEZIONI = {
    "## Problema": "cosa va deciso, perche' ora, e cosa succede se non si decide",
    "## Opzioni": "le alternative CON LA FONTE, compreso il non fare nulla",
    "## Evidenze": "dato, test, misura o documento verificabile",
    "## Scelta": "opzione scelta e ragione; se respinto, dirlo qui",
    "## Conseguenze": "effetto su prodotti, agenti, tempi, costi, permessi",
    "## Metrica": "come si misura che la decisione ha funzionato",
    "## Data di revisione": "quando si va a vedere",
    "## Esito misurato": "cosa e' cambiato davvero, con quale evidenza",
}

URL_RE = re.compile(r"https?://\S+")
#: La VOCE «Non fare nulla», non la frase: `3. **Non fare nulla** — ...`
#: L'opzione di riferimento. **Il punto puo' stare dentro o fuori il grassetto**: chi
#: scrive `1. **Non fare nulla.**` sta scrivendo italiano corretto, e il 2026-10-13 il
#: controllo l'ha respinto. Un controllo che pretende una punteggiatura sbagliata
#: obbliga a sbagliare.
NON_FARE_NULLA_RE = re.compile(r"^\s*\d+\.\s*\*\*Non fare nulla\.?\*\*", re.M | re.I)
NUMERO_RE = re.compile(r"DEC-(\d+)")


def carica(base: Path | None = None) -> list[dict]:
    """Tutti i verbali, in ordine di numero."""
    radice = base or RADICE
    fuori = []
    for percorso in sorted((radice / CARTELLA).glob("DEC-[0-9]*.md")):
        numero = int(NUMERO_RE.search(percorso.name).group(1))
        testo = percorso.read_text(encoding="utf-8")
        fuori.append(
            {"percorso": percorso, "numero": numero, "testo": testo, "dati": _dati(testo)}
        )
    return sorted(fuori, key=lambda v: v["numero"])


def _dati(testo: str) -> dict:
    pezzi = re.findall(r"```yaml\n(.*?)```", testo, re.S)
    if not pezzi:
        return {}
    try:
        return yaml.safe_load(pezzi[0]) or {}
    except yaml.YAMLError:
        return {}


def _sezione(testo: str, titolo: str) -> str:
    i = testo.find(titolo)
    if i < 0:
        return ""
    i += len(titolo)
    resto = testo[i:]
    prossimo = re.search(r"^## ", resto, re.M)
    return resto[: prossimo.start()] if prossimo else resto


def problemi(base: Path | None = None) -> tuple[list[str], list[str]]:
    """(errori, da rivedere). Vuoto il primo = i verbali seguono il modello."""
    radice = base or RADICE
    errori: list[str] = []
    da_rivedere: list[str] = []
    oggi = datetime.date.today()

    for voce in carica(radice):
        rel = voce["percorso"].name
        dati = voce["dati"]
        testo = voce["testo"]
        numero = voce["numero"]

        if not dati:
            errori.append(f"{rel}: manca il blocco YAML in cima")
            continue

        identificatore = str(dati.get("id", ""))
        if identificatore and not rel.startswith(f"{identificatore}-"):
            errori.append(f"{rel}: l'id dichiarato e' `{identificatore}`, il nome del file no")

        # la data di revisione, se dichiarata: serve a entrambe le regole
        revisione = _data_revisione(testo, dati)
        esito = _sezione(testo, "## Esito misurato")
        esito_scritto = len(esito.strip()) > 20 and not esito.strip().startswith("<")

        if numero < PRIMO_CON_MODELLO:
            # Esente dalla struttura: e' un record scritto a mano libera, ed e'
            # immutabile. Ma se dichiara una revisione e quella data e' passata,
            # l'esito mancante si **vede** — non e' un errore, e' una cosa da fare.
            if revisione and revisione <= oggi and not esito_scritto:
                da_rivedere.append(
                    f"{rel}: la revisione era il {revisione.isoformat()} e l'esito non c'e'"
                )
            continue

        for campo, perche in CAMPI.items():
            if not str(dati.get(campo, "")).strip():
                errori.append(f"{rel}: manca `{campo}` ({perche})")

        stato = str(dati.get("stato", ""))
        if stato and stato not in ("proposto", "approvato", "respinto", "superato"):
            errori.append(f"{rel}: stato `{stato}` non ammesso")

        for sezione, domanda in SEZIONI.items():
            if sezione not in testo:
                errori.append(f"{rel}: manca «{sezione}» ({domanda})")

        # le opzioni devono citare una fonte: una decisione senza fonti verificabili
        # e' un'opinione con la data sopra
        opzioni = _sezione(testo, "## Opzioni")
        if opzioni and not URL_RE.search(opzioni):
            errori.append(
                f"{rel}: «Opzioni» non cita nessuna fonte — le evidenze devono essere "
                "verificabili (vedi le regole del registro)"
            )
        # NON si cerca la frase «non fare nulla» dentro la sezione: compare anche
        # di passaggio nel testo di un'altra opzione, e il controllo passerebbe su
        # una sezione che l'opzione non ce l'ha. Si cerca **la voce numerata**, che
        # e' la struttura. E' la quinta volta in tre giorni che confondo una
        # somiglianza con una struttura: vedi ERR-0002, 0009, 0010, 0013.
        if opzioni and not NON_FARE_NULLA_RE.search(opzioni):
            errori.append(
                f"{rel}: «Opzioni» non contiene una voce **Non fare nulla**. E' l'opzione di "
                "riferimento: senza, non si sa con cosa si sta confrontando la scelta"
            )

        # l'esito si scrive DOPO, e alla data dichiarata dev'esserci
        if revisione and revisione <= oggi and not esito_scritto:
            errori.append(
                f"{rel}: la revisione era il {revisione.isoformat()} e «Esito misurato» "
                "e' vuoto — la decisione dice come si misura, ma nessuno l'ha misurata"
            )

    return errori, da_rivedere


def _data_revisione(testo: str, dati: dict):
    """La data di revisione: dal campo YAML, o dalla sezione del modello."""
    valore = str(dati.get("data_revisione", "")).strip()
    if not valore:
        sezione = _sezione(testo, "## Data di revisione").strip()
        trovato = re.search(r"\d{4}-\d{2}-\d{2}", sezione)
        valore = trovato.group(0) if trovato else ""
    if not valore:
        return None
    try:
        return datetime.date.fromisoformat(valore[:10])
    except ValueError:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Registro delle decisioni")
    parser.add_argument("comando", choices=("check", "list", "show", "nuovo"))
    parser.add_argument("id", nargs="?")
    parser.add_argument("--slug", default="nuovo")
    parser.add_argument("--root", default=str(RADICE))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    base = Path(args.root).resolve()
    voci = carica(base)

    if args.comando == "nuovo":
        # **Gli id non si scelgono, si chiedono.** Vedi ad_docs.prenota_id.
        cartella = base / CARTELLA
        try:
            identificatore, percorso = ad_docs.prenota_id(cartella, "DEC", slug=args.slug)
        except PermissionError as errore:
            print(str(errore), file=sys.stderr)
            return 2
        modello = cartella / "_TEMPLATE.md"
        testo = modello.read_text(encoding="utf-8") if modello.is_file() else ""
        testo = testo.replace("<numero>", identificatore.split("-")[1]).replace("<slug>", args.slug)
        percorso.write_text(testo, encoding="utf-8")
        print(percorso.relative_to(base))
        return 0

    if args.comando == "show":
        for voce in voci:
            if str(voce["dati"].get("id")) == args.id or args.id in voce["percorso"].name:
                print(voce["testo"])
                return 0
        print(f"nessun verbale {args.id}")
        return 1

    if args.comando == "list":
        if args.json:
            print(json.dumps([{"id": v["dati"].get("id"), "stato": v["dati"].get("stato")} for v in voci], ensure_ascii=False))
            return 0
        print(f"  {len(voci)} verbali, dal {voci[0]['dati'].get('id')} al {voci[-1]['dati'].get('id')}")
        for voce in voci:
            print(f"  {str(voce['dati'].get('id', '?')):10} {str(voce['dati'].get('stato', '?'))}")
        return 0

    errori, da_rivedere = problemi(base)
    if args.json:
        print(json.dumps({"errori": errori, "da_rivedere": da_rivedere}, ensure_ascii=False))
        return 1 if errori else 0

    for errore in errori:
        print(f"  ERRORE      {errore}")
    for voce in da_rivedere:
        print(f"  da rivedere {voce}")
    print(
        f"\n  {len(voci)} verbali · {len(errori)} fuori modello"
        f" · {len(da_rivedere)} con l'esito da scrivere"
    )
    if not errori:
        print("  esito: i verbali seguono il modello")
    else:
        print(f"  esito: {len(errori)} problemi")
    return 1 if errori else 0


if __name__ == "__main__":
    raise SystemExit(main())
