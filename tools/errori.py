#!/usr/bin/env python3
"""Il registro degli errori: validazione, elenco e statistica.

Perche' esiste questo strumento, in una riga: il 2026-10-08 ho scritto in un
verbale che le date inventate erano un errore, e **l'ho rifatto altre due volte**.
Una regola scritta non cambia il comportamento. Un controllo che fallisce si'.

Questo strumento non impedisce di sbagliare: verifica che ogni voce del registro
sia **completa** e che la difesa che dichiara **esista davvero**. Una voce che
promette un controllo inesistente e' peggio di una voce assente, perche' sembra
una difesa.

Uso:
    python3 tools/errori.py check     # tutte le voci sono complete e oneste?
    python3 tools/errori.py list      # l'elenco, con la statistica
    python3 tools/errori.py stats     # solo il numero che conta

Esito: 0 tutto a posto, 1 altrimenti, 2 scrittura rifiutata perche' nessun
contract approvato copre il percorso.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

import ad_docs

try:
    import yaml
except ImportError:  # pragma: no cover - yaml e' una dipendenza di fatto
    print("serve PyYAML", file=sys.stderr)
    raise SystemExit(2)

RADICE = Path(__file__).resolve().parents[1]
CARTELLA = "errori"

#: Le tre domande. Senza la terza una voce e' incompleta: non e' apprendimento,
#: e' memoria di un dispiacere.
CAMPI = (
    "id",
    "data",
    "cosa_e_fallito",
    "cosa_l_ha_risolto",
    "cosa_l_avrebbe_preso",
    "diventa",
    "trovato_da",
    "stato",
)

DIVENTA = ("controllo", "nota", "verbale")
TROVATO_DA = ("controllo", "revisore", "altro-agente", "io")
STATI = ("chiuso", "aperto")

#: Come e' stato trovato l'errore. `controllo` e' l'unico che significa che il
#: sistema sta imparando: gli altri tre sono gradi diversi di fortuna.
FORTUNA = ("io", "altro-agente")


def carica(base: Path | None = None) -> list[dict]:
    """Legge tutte le voci del registro, in ordine di nome file."""
    radice = (base or RADICE) / CARTELLA
    voci: list[dict] = []
    if not radice.is_dir():
        return voci
    for percorso in sorted(radice.glob("ERR-*.yaml")):
        try:
            dati = yaml.safe_load(percorso.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            dati = None
        voci.append({"percorso": percorso, "dati": dati if isinstance(dati, dict) else {}})
    return voci


def problemi(base: Path | None = None) -> list[str]:
    """Cosa non va nel registro. Elenco vuoto = tutto a posto."""
    radice = base or RADICE
    fuori: list[str] = []
    viste: dict[str, str] = {}

    for voce in carica(radice):
        percorso: Path = voce["percorso"]
        dati: dict = voce["dati"]
        nome = percorso.name

        if not dati:
            fuori.append(f"{nome}: non si legge, o non e' un oggetto YAML")
            continue

        for campo in CAMPI:
            valore = dati.get(campo)
            if valore is None or (isinstance(valore, str) and not valore.strip()):
                fuori.append(f"{nome}: manca il campo '{campo}'")

        for campo, ammessi in (
            ("diventa", DIVENTA),
            ("trovato_da", TROVATO_DA),
            ("stato", STATI),
        ):
            valore = dati.get(campo)
            if valore is not None and valore not in ammessi:
                fuori.append(
                    f"{nome}: '{campo}' vale '{valore}', ammessi {', '.join(ammessi)}"
                )

        # La terza domanda: se la risposta e' vuota la voce non insegna niente.
        preso = str(dati.get("cosa_l_avrebbe_preso", "")).strip()
        if preso and preso.lower() in ("niente", "niente.", "nessuno", "-"):
            fuori.append(
                f"{nome}: 'cosa_l_avrebbe_preso' dice che non c'e' difesa. "
                "Va bene dirlo, ma allora 'stato' deve restare 'aperto': l'errore puo' ripetersi"
            )

        # Una difesa che non esiste e' peggio di nessuna difesa: sembra una difesa.
        dove = str(dati.get("dove", "")).strip()
        if dati.get("diventa") == "controllo":
            if not dove:
                fuori.append(f"{nome}: 'diventa: controllo' ma 'dove' e' vuoto")
            elif not (radice / dove.split("#")[0]).exists():
                fuori.append(f"{nome}: la difesa dichiarata non esiste: {dove}")

        ident = str(dati.get("id", nome))
        if ident in viste:
            fuori.append(f"{nome}: id '{ident}' gia' usato da {viste[ident]}")
        viste[ident] = nome

    return fuori


def statistiche(base: Path | None = None) -> dict:
    """Il numero che conta: quanto stiamo imparando e quanto stiamo avendo fortuna.

    E la **metrica della maturita'**: quante cicatrici sono diventate un controllo,
    su quante ne sono nate. Sale quando il sistema impara, **scende quando si sbaglia
    di nuovo** — cioe' si comporta come una misura, non come un trofeo.

    E non si puo' gonfiare: ogni voce `diventa: controllo` dichiara il **file** che
    la attua, e quel file deve esistere (`check` lo pretende).
    """
    voci = [v["dati"] for v in carica(base) if v["dati"]]
    per_trovato: dict[str, int] = {}
    for voce in voci:
        chiave = str(voce.get("trovato_da", "?"))
        per_trovato[chiave] = per_trovato.get(chiave, 0) + 1

    dal_controllo = per_trovato.get("controllo", 0)
    per_fortuna = sum(per_trovato.get(chiave, 0) for chiave in FORTUNA)
    totale = len(voci)
    aperti = sum(1 for v in voci if v.get("stato") == "aperto")

    # La metrica: quante cicatrici sono diventate **codice**.
    per_diventa: dict[str, int] = {}
    for voce in voci:
        chiave = str(voce.get("diventa", "?"))
        per_diventa[chiave] = per_diventa.get(chiave, 0) + 1
    diventate_controllo = per_diventa.get("controllo", 0)
    maturita = (diventate_controllo / totale) if totale else 0.0

    if totale == 0:
        giudizio = "registro vuoto: non sappiamo niente di come impariamo"
    elif dal_controllo > totale / 2:
        giudizio = "il sistema sta imparando: la maggioranza degli errori la trova un controllo"
    elif per_fortuna > totale / 2:
        giudizio = "stiamo avendo FORTUNA: la maggioranza degli errori l'ha trovata una persona"
    else:
        giudizio = "equilibrio: meta' controlli, meta' fortuna"

    return {
        "totale": totale,
        "per_trovato_da": per_trovato,
        "dal_controllo": dal_controllo,
        "per_fortuna": per_fortuna,
        "aperti": aperti,
        "per_diventa": per_diventa,
        "diventate_controllo": diventate_controllo,
        "maturita": round(maturita, 4),
        "maturita_percento": round(maturita * 100),
        "giudizio": giudizio,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Registro degli errori")
    parser.add_argument("comando", choices=("check", "list", "stats", "nuovo"))
    parser.add_argument("--slug", default="nuovo")
    parser.add_argument("--root", default=str(RADICE))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    base = Path(args.root).resolve()

    if args.comando == "nuovo":
        # **Gli id non si scelgono, si chiedono.** La prenotazione e' atomica: due
        # sessioni che provano lo stesso numero, una vince e l'altra passa al
        # successivo. E' la difesa contro la collisione del 2026-10-11.
        cartella = base / "errori"
        try:
            identificatore, percorso = ad_docs.prenota_id(
                cartella, "ERR", slug=args.slug, estensione=".yaml"
            )
        except PermissionError as errore:
            print(str(errore), file=sys.stderr)
            return 2
        modello = cartella / "_TEMPLATE.yaml"
        testo = modello.read_text(encoding="utf-8") if modello.is_file() else ""
        testo = testo.replace("<numero>", identificatore.split("-")[1]).replace("<slug>", args.slug)
        # Il modello dichiara un id di comodo e una data di comodo: si mettono
        # quelli veri, altrimenti il file nasce con l'identita' di un altro.
        testo = re.sub(r"^id: ERR-\d+", f"id: {identificatore}", testo, count=1, flags=re.M)
        testo = re.sub(
            r'^data: "AAAA-MM-GG"',
            f'data: "{datetime.date.today().isoformat()}"',
            testo, count=1, flags=re.M,
        )
        if not testo.strip():
            testo = (
                f"# {identificatore}\n\n"
                f"id: {identificatore}\ndata: \"\"\n\n"
                "cosa_e_fallito: >\n\ncosa_l_ha_risolto: >\n\ncosa_l_avrebbe_preso: >\n\n"
                'diventa: nota\ndove: ""\n\ntrovato_da: io\nstato: aperto\n'
            )
        percorso.write_text(testo, encoding="utf-8")
        print(percorso.relative_to(base))
        return 0

    if args.comando == "check":
        guai = problemi(base)
        if args.json:
            print(json.dumps({"ok": not guai, "problemi": guai}, ensure_ascii=False))
            return 0 if not guai else 1
        if guai:
            for guaio in guai:
                print(f"  {guaio}")
            print(f"\nesito: {len(guai)} problemi — il registro non e' coerente")
            return 1
        print("OK   ogni voce e' completa, e ogni difesa dichiarata esiste")
        return 0

    if args.comando == "stats":
        dati = statistiche(base)
        if args.json:
            print(json.dumps(dati, ensure_ascii=False, indent=2))
            return 0
        print(f"  voci:            {dati['totale']}")
        print(f"  trovate da un controllo: {dati['dal_controllo']}")
        print(f"  trovate per fortuna:     {dati['per_fortuna']}")
        for chiave, quante in sorted(dati["per_trovato_da"].items()):
            print(f"    {chiave:14} {quante}")
        print(f"  ancora aperte:   {dati['aperti']}")
        print()
        print("  ── maturita': quante cicatrici sono diventate CODICE")
        print(f"  diventate controllo: {dati['diventate_controllo']} su {dati['totale']}"
              f"   ->  {dati['maturita_percento']}%")
        print("  (sale quando il sistema impara, scende quando si sbaglia di nuovo)")
        print(f"\n  {dati['giudizio']}")
        return 0

    # list
    voci = carica(base)
    if args.json:
        print(json.dumps([v["dati"] for v in voci], ensure_ascii=False))
        return 0
    if not voci:
        print("  registro vuoto")
        return 0
    for voce in voci:
        dati = voce["dati"]
        print(
            f"  {str(dati.get('id', '?')):9} {str(dati.get('stato', '?')):7} "
            f"{str(dati.get('diventa', '?')):10} {str(dati.get('trovato_da', '?')):12} "
            f"{str(dati.get('cosa_e_fallito', ''))[:58]}"
        )
    dati = statistiche(base)
    print(f"\n  {dati['totale']} voci · {dati['giudizio']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
