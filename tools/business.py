#!/usr/bin/env python3
"""La tela business: sezioni obbligate, fonti datate, assunzioni dichiarate (M7, `DEC-0119`).

Perche' esiste. Le card business sanno produrre analisi, ma un'analisi in testo libero si puo'
solo credere o non credere. Questo strumento non giudica la strategia: verifica che l'analisi
sia **completa e tracciabile**.

Regole dichiarate (e niente di piu'):
  - le 11 sezioni della tela ci sono e non sono vuote;
  - ogni riga che contiene una **cifra** dichiara `fonte: <URL o file>` **e** una data
    `AAAA-MM-GG` (il tool **non verifica la fonte**: la controlla che sia dichiarata, non che
    sia vera; verificarla e' un altro lavoro, umano o di `memoria.py`/`crawler.py`);
  - almeno 2 concorrenti, 2 rischi, 1 assunzione, 1 prossimo passo;
  - niente segnaposto: `TODO` e `<...>` non sono un'analisi;
  - la sezione «Numeri» ha almeno 2 righe con fonte.

Limite dichiarato: il check misura struttura e tracciabilita', **non la qualita' della
strategia** ne' la verita' delle fonti. (La fonte ufficiale del canvas lo dice da sempre:
«a filled-in canvas isn't a decision».)

Uso:
    python3 tools/business.py genera --progetto "<nome>" --out <file.md>
    python3 tools/business.py check <file.md> [--json]

Esiti: 0 la tela e' completa e tracciabile, 1 manca qualcosa, 2 uso sbagliato.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

#: (numero, titolo, chiave). L'ordine e' quello della tela.
SEZIONI: tuple[tuple[int, str, str], ...] = (
    (1, "Richiesta", "richiesta"),
    (2, "Clienti (ICP e segmenti)", "clienti"),
    (3, "Problema", "problema"),
    (4, "Proposta di valore", "proposta"),
    (5, "Offerta e prezzo", "offerta"),
    (6, "Canali", "canali"),
    (7, "Concorrenti", "concorrenti"),
    (8, "Numeri", "numeri"),
    (9, "Rischi", "rischi"),
    (10, "Assunzioni", "assunzioni"),
    (11, "Prossimi passi", "prossimi_passi"),
)
TITOLI = {chiave: titolo for _, titolo, chiave in SEZIONI}
RIGA_SEZIONE = re.compile(r"^##\s+(\d+)\.\s*(.+?)\s*$")
RIGA_TITOLO = re.compile(r"^##\s+(.*)$")
FONTE_COMPLETA = re.compile(r"fonte:\s*(.+?)\s*(?:—|–|\s-\s)\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE)
FONTE_TOKEN = re.compile(r"fonte:\s*(\S+)", re.IGNORECASE)
DATA = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
CIFRA = re.compile(r"\d")
SEGNAPOSTO = re.compile(r"\bTODO\b|<[^>]+>", re.IGNORECASE)
#: Fonti che dichiarano «non lo so»: non sono una fonte verificabile.
FONTI_NULLE = {"ignota", "sconosciuta", "nessuna", "n/a", "na", "-", "?"}


def _fonte_valida(token: str) -> bool:
    """Una fonte e' un URL http(s) o un file con un nome vero (almeno un punto o una barra)."""
    pulito = token.strip().strip(".,;:").strip("'\"«»")
    if not pulito or pulito.lower() in FONTI_NULLE or len(pulito) < 4:
        return False
    if pulito.lower().startswith(("http://", "https://")):
        return True
    return ("/" in pulito or "." in pulito) and not pulito.lower().startswith(("todo", "<"))


def _riga_fonte_valida(riga: str) -> bool:
    """Vero se la riga dichiara una fonte valida E una data, nel formato `<fonte> — <data>`."""
    incontro = FONTE_COMPLETA.search(riga)
    return bool(incontro and _fonte_valida(incontro.group(1)))


class ErroreBusiness(Exception):
    def __init__(self, messaggio: str, rimedio: str) -> None:
        super().__init__(messaggio)
        self.messaggio = messaggio
        self.rimedio = rimedio


def _leggi(percorso: Path) -> list[str]:
    return percorso.read_text(encoding="utf-8").splitlines()


def _sezioni(righe: list[str]) -> tuple[dict[str, list[tuple[int, str]]], list[dict]]:
    """Mappa chiave -> [(numero riga, testo)] e gli errori di struttura.

    Struttura: un `##` senza numero non e' una sezione (e va segnalato), due sezioni con lo
    stesso titolo sono un errore (non si fondono in silenzio), le righe prima della prima
    sezione non possono contenere cifre senza fonte.
    """
    risultato: dict[str, list[tuple[int, str]]] = {}
    errori: list[dict] = []
    corrente: str | None = None
    for numero, riga in enumerate(righe, 1):
        incontro = RIGA_SEZIONE.match(riga)
        if incontro:
            titolo = incontro.group(2).strip().lower()
            corrente = next((chiave for _, titolo_atteso, chiave in SEZIONI
                             if titolo_atteso.lower() == titolo or chiave in titolo), None)
            if corrente:
                if corrente in risultato:
                    errori.append({"codice": "sezione-duplicata", "riga": numero,
                                   "messaggio": f"la sezione «{TITOLI[corrente]}» compare due volte"})
                else:
                    risultato[corrente] = []
            continue
        if RIGA_TITOLO.match(riga):
            errori.append({"codice": "sezione-non-numerata", "riga": numero,
                           "messaggio": "un titolo `## ...` deve essere numerato (`## N. Titolo`)"})
            corrente = None
            continue
        if corrente:
            risultato[corrente].append((numero, riga))
        elif not risultato and riga.strip() and not riga.strip().startswith(("#", "<!--")) and CIFRA.search(riga):
            errori.append({"codice": "fuori-sezione", "riga": numero,
                           "messaggio": "una cifra prima della prima sezione non e' tracciabile"})
    return risultato, errori


def _piene(righe: list[tuple[int, str]]) -> list[tuple[int, str]]:
    return [(n, r) for n, r in righe if r.strip() and not r.strip().startswith("<!--")]


def genera(progetto: str) -> str:
    """Lo scheletro della tela: segnaposto, non un'analisi (e il check lo dira')."""
    righe = [
        f"# Tela business — {progetto}",
        "",
        "<!-- Regola: ogni riga con una cifra dichiara `fonte: <URL o file> — AAAA-MM-GG`. -->",
        "<!-- Il check verifica struttura e tracciabilita', non la qualita' della strategia. -->",
        "",
    ]
    for numero, titolo, chiave in SEZIONI:
        righe.append(f"## {numero}. {titolo}")
        righe.append("")
        if chiave == "concorrenti":
            righe += ["- TODO: concorrente 1", "- TODO: concorrente 2"]
        elif chiave == "rischi":
            righe += ["- TODO: rischio 1", "- TODO: rischio 2"]
        elif chiave == "assunzioni":
            righe += ["- TODO: assunzione da verificare"]
        elif chiave == "prossimi_passi":
            righe += ["- TODO: primo passo, con responsabile e data"]
        elif chiave == "numeri":
            righe += ["- TODO: <numero> — fonte: <URL o file> — AAAA-MM-GG"]
        else:
            righe.append("TODO: da compilare")
        righe.append("")
    return "\n".join(righe)


def check(percorso: Path) -> dict:
    righe = _leggi(percorso)
    sezioni, errori = _sezioni(righe)

    for _, titolo_atteso, chiave in SEZIONI:
        if chiave not in sezioni:
            errori.append({"codice": "sezione-mancante", "messaggio": f"manca la sezione «{titolo_atteso}»"})
            continue
        contenuto = _piene(sezioni[chiave])
        if not contenuto:
            errori.append({"codice": "sezione-vuota", "messaggio": f"«{titolo_atteso}» e' vuota"})
            continue
        if chiave in ("concorrenti", "rischi") and len([r for _, r in contenuto if r.lstrip().startswith("-")]) < 2:
            errori.append({"codice": "troppo-pochi", "messaggio": f"«{titolo_atteso}»: servono almeno 2 voci"})
        if chiave == "assunzioni" and not any(r.lstrip().startswith("-") for _, r in contenuto):
            errori.append({"codice": "troppo-pochi", "messaggio": "«Assunzioni»: almeno 1 voce"})
        if chiave == "prossimi_passi" and not any(r.lstrip().startswith("-") for _, r in contenuto):
            errori.append({"codice": "troppo-pochi", "messaggio": "«Prossimi passi»: almeno 1 voce"})
        if chiave == "numeri":
            con_fonte = [(n, r) for n, r in contenuto if _riga_fonte_valida(r)]
            if len(con_fonte) < 2:
                errori.append({"codice": "numeri-senza-fonte",
                               "messaggio": "«Numeri»: servono almeno 2 righe con fonte e data"})

        for numero_riga, riga in contenuto:
            if SEGNAPOSTO.search(riga):
                errori.append({"codice": "segnaposto", "riga": numero_riga,
                               "messaggio": "c'e' un segnaposto (TODO o <...>): un'analisi va compilata"})
            if not CIFRA.search(riga):
                continue
            if _riga_fonte_valida(riga):
                continue
            incontro = FONTE_TOKEN.search(riga)
            if incontro:
                errori.append({"codice": "fonte-non-valida", "riga": numero_riga,
                               "messaggio": f"la fonte «{incontro.group(1)}» non e' un URL o un file: "
                                            "serve `fonte: <URL o file> — AAAA-MM-GG`"})
            else:
                errori.append({"codice": "riga-senza-fonte", "riga": numero_riga,
                               "messaggio": "una riga con una cifra deve dichiarare «fonte: <URL o file> — AAAA-MM-GG»"})

    return {"file": str(percorso), "ok": not errori, "errori": errori,
            "sezioni_trovate": len(sezioni), "sezioni_attese": len(SEZIONI)}


def main(argv: list[str] | None = None) -> int:
    analizzatore = argparse.ArgumentParser(description="La tela business verificabile")
    sotto = analizzatore.add_subparsers(dest="azione", required=True)
    g = sotto.add_parser("genera", help="crea lo scheletro della tela")
    g.add_argument("--progetto", required=True)
    g.add_argument("--out", required=True)
    c = sotto.add_parser("check", help="verifica una tela")
    c.add_argument("file")
    c.add_argument("--json", action="store_true")

    args = analizzatore.parse_args(argv)
    if args.azione == "genera":
        contenuto = genera(args.progetto)
        percorso = Path(args.out)
        percorso.parent.mkdir(parents=True, exist_ok=True)
        percorso.write_text(contenuto + "\n", encoding="utf-8")
        print(f"  tela scritta: {percorso} (segnaposto: il check dira' cosa manca)")
        return 0

    file = Path(args.file)
    if not file.is_file():
        print(f"  file non trovato: {file}", file=sys.stderr)
        return 2
    esito = check(file)
    if args.json:
        print(json.dumps(esito, indent=2, ensure_ascii=False))
    elif esito["ok"]:
        print(f"  tela completa e tracciabile: {esito['sezioni_trovate']}/{esito['sezioni_attese']} sezioni")
    else:
        print(f"  NO — {len(esito['errori'])} problemi:")
        for errore in esito["errori"][:20]:
            riga = f" (riga {errore['riga']})" if errore.get("riga") else ""
            print(f"    · {errore['messaggio']}{riga}")
    return 0 if esito["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
