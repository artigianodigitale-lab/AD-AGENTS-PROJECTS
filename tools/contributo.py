#!/usr/bin/env python3
"""Contributi: il documento che si CHIEDE al sistema, per raccontare un problema.

    python3 tools/contributo.py nuovo            # crea il tuo documento
    python3 tools/contributo.py elenca           # quelli aperti
    python3 tools/contributo.py check <file>     # e' completo?

Perche' esiste, in una riga: un progetto aperto al mondo ha bisogno di una **porta**,
e la porta non puo' essere un modulo da compilare a mano in un posto che non conosci.
Questo comando **genera** il documento con le domande dentro, lo numera, e ti dice dove
mandarlo. Chi arriva non deve sapere niente di questo sistema per contribuire: esegue
un comando, risponde, e spedisce.

Il documento e' **bilingue**: le domande ci sono in italiano e in inglese, cosi' chi
scrive usa la lingua che vuole. Il resto del sistema e' in italiano; la porta e' per
tutti.

Perche' non e' un issue tracker: perche' un problema raccontato bene vale piu' di cento
raccontati male, e perche' il documento **resta** — si allega, si cita, e un giorno si
puo' rileggere per capire se quel problema e' stato davvero risolto. Vedi CONTRIBUTING.md.

Uscita:
    0  fatto
    1  il documento non e' completo (check)
    2  argomento mancante, o scrittura non permessa
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

import ad_docs  # noqa: E402

#: Dove finiscono i contributi. Non e' una cartella di progetto: e' la porta.
CONTRIBUTI = "contributi"

#: Dove si manda il documento. **Chi mantiene il progetto lo cambia qui**, in una riga.
INDIRIZZO = "artigianodigitale.me@gmail.com"

INTESTAZIONE = """# Contributo {id}

<!--
  QUESTO DOCUMENTO TE LO HA DATO IL SISTEMA, non l'hai scritto a mano.
  Rispondi sotto ogni domanda. Non serve essere ordinati: serve essere precisi.
  Quando hai finito, controlla con:
      python3 tools/contributo.py check {percorso}
  e poi mandalo a: {indirizzo}
  Oggetto consigliato: [CONTRIBUTO] <due o tre parole>

  Se una domanda non ha risposta per te, scrivi "non lo so": e' un'informazione utile,
  e molto meglio di una risposta inventata per riempire lo spazio.

  ---------------------------------------------------------------------------
  THIS DOCUMENT WAS GIVEN TO YOU BY THE SYSTEM, not written by hand.
  Answer under each question. You do not need to be tidy: you need to be precise.
  When finished, check it with:
      python3 tools/contributo.py check {percorso}
  then send it to: {indirizzo}
  Suggested subject: [CONTRIBUTO] <two or three words>

  If a question has no answer for you, write "I don't know": that is useful
  information, and far better than an answer invented to fill the space.
-->

**Data / Date:** {data}
**Chi scrive / Who writes:** (facoltativo / optional)

"""

CORPO = """## {n}. {domanda}

*{domanda_en}*

{risposta}

"""


def _domande_bilingui() -> list[tuple[str, str, str]]:
    """Le domande, con la versione inglese accanto. In ordine, senza buchi."""
    return [
        ("cosa_e_successo",
         "Cosa e' successo, e cosa ti aspettavi che succedesse?",
         "What happened, and what did you expect to happen?"),
        ("come_si_riproduce",
         "Come si riproduce? I passi esatti, e i comandi che hai dato",
         "How can it be reproduced? The exact steps, and the commands you ran"),
        ("cosa_dice_il_sistema",
         "Cosa ti ha risposto il sistema? Incolla il messaggio intero",
         "What did the system answer? Paste the whole message"),
        ("cosa_hai_provato",
         "Cosa hai provato prima di scrivere?",
         "What did you try before writing?"),
        ("cosa_proponi",
         "Se hai un'idea di cosa dovrebbe succedere, scrivila",
         "If you have an idea of what should happen instead, write it"),
        ("credito",
         "Vuoi essere ringraziato col tuo nome? Scrivilo qui, e comparira' nel registro "
         "delle cicatrici se dal tuo contributo nasce un controllo. Se preferisci restare "
         "anonimo, scrivi \"anonimo\".",
         "Do you want to be credited by name? Write it here, and it will appear in the scar "
         "register if your contribution becomes a check. If you prefer to stay anonymous, "
         "write \"anonymous\"."),
    ]


def _data() -> str:
    from datetime import date
    return date.today().isoformat()


def nuovo(root: Path) -> int:
    """Crea il documento, con un id prenotato in modo atomico."""
    cartella = Path(root) / CONTRIBUTI
    cartella.mkdir(parents=True, exist_ok=True)
    try:
        ident, percorso = ad_docs.prenota_id(
            cartella, "CONTRIBUTO", cifre=3, slug="problema", estensione=".md"
        )
    except ad_docs.IdNonPrenotabile as errore:
        print(f"Non ho potuto prenotare un id: {errore}", file=sys.stderr)
        return 2

    domande = _domande_bilingui()
    pezzi = [
        INTESTAZIONE.format(
            id=ident, percorso=percorso.relative_to(Path(root)),
            indirizzo=INDIRIZZO, data=_data(),
        )
    ]
    for numero, (_chiave, domanda, domanda_en) in enumerate(domande, 1):
        pezzi.append(
            CORPO.format(n=numero, domanda=domanda, domanda_en=domanda_en,
                         risposta="<!-- la tua risposta / your answer -->")
        )
    pezzi.append(
        "\n---\n\n"
        f"Grazie. Mandalo a **{INDIRIZZO}**.\n"
        f"Thank you. Send it to **{INDIRIZZO}**.\n"
    )
    percorso.write_text("".join(pezzi), encoding="utf-8")

    print(f"  scritto: {percorso.relative_to(Path(root))}")
    print(f"  id:      {ident}  (prenotato, non scelto)")
    print()
    print(f"  Rispondi alle {len(domande)} domande, poi:")
    print(f"      python3 tools/contributo.py check {percorso.relative_to(Path(root))}")
    print(f"  e mandalo a {INDIRIZZO}")
    return 0


def elenca(root: Path) -> int:
    """I contributi aperti, in ordine di id."""
    cartella = Path(root) / CONTRIBUTI
    if not cartella.is_dir():
        print("  nessun contributo: la cartella non esiste ancora")
        return 0
    file = sorted(p for p in cartella.glob("CONTRIBUTO-*.md"))
    if not file:
        print("  nessun contributo")
        return 0
    for percorso in file:
        testo = percorso.read_text(encoding="utf-8")
        stato = "COMPLETO" if not incompleto(testo) else "da completare"
        print(f"  {percorso.name}  [{stato}]")
    return 0


def incompleto(testo: str) -> list[str]:
    """Cosa manca. Vuoto significa completo."""
    mancanti = []
    for _chiave, domanda, domanda_en in _domande_bilingui():
        # La risposta sta fra il titolo della domanda e quello successivo (o la fine).
        inizio = testo.find(domanda)
        if inizio < 0:
            mancanti.append(domanda)
            continue
        resto = testo[inizio + len(domanda):]
        fine = resto.find("\n## ")
        risposta = (resto[:fine] if fine >= 0 else resto).strip()
        risposta = risposta.replace("*" + domanda_en + "*", "").strip()
        if not risposta or risposta.startswith("<!--"):
            mancanti.append(domanda)
    return mancanti


def check(percorso: str) -> int:
    """Il documento e' completo? Un documento con i buchi non aiuta nessuno."""
    file = Path(percorso)
    if not file.is_file():
        print(f"  non esiste: {percorso}", file=sys.stderr)
        return 2
    testo = file.read_text(encoding="utf-8")
    mancanti = incompleto(testo)
    if mancanti:
        print(f"  MANCANO {len(mancanti)} risposte:")
        for domanda in mancanti:
            print(f"    - {domanda}")
        print()
        print("  «Non lo so» va bene: e' un'informazione. Una risposta inventata no.")
        return 1
    print("  completo.")
    print()
    # Il sistema NON manda niente: prepara, e l'ultimo clic lo fa una persona.
    # (Invariante 3: nessun invio esterno senza che qualcuno lo veda e lo voglia.)
    from urllib.parse import quote
    oggetto = quote(f"[CONTRIBUTO] {file.stem}")
    corpo = quote("In allegato il documento compilato.\nAttached: the completed document.")
    print(f"  Apri la mail:   mailto:{INDIRIZZO}?subject={oggetto}&body={corpo}")
    print(f"  ...e ALLEGA il file: {file}")
    print()
    print("  Perche' a mano: il sistema non spedisce nulla da solo. Un invio esterno")
    print("  senza che tu lo veda sarebbe la prima regola che questo motore tradisce.")
    return 0


def _risposte(testo: str) -> dict[str, str]:
    """Le risposte, per chiave. Serve a importare un contributo nel registro."""
    fuori: dict[str, str] = {}
    for chiave, domanda, domanda_en in _domande_bilingui():
        inizio = testo.find(domanda)
        if inizio < 0:
            fuori[chiave] = ""
            continue
        resto = testo[inizio + len(domanda):]
        fine = resto.find("\n## ")
        risposta = resto[:fine] if fine >= 0 else resto
        # L'ULTIMA domanda arriva fino in fondo al documento, e si porterebbe dietro la
        # coda ("Grazie. Mandalo a..."). Il 2026-10-13 e' successo, e ha prodotto una
        # stringa YAML non chiusa che il registro ha rifiutato: ERR-0046 insegna che chi
        # scrive un registro lo RILEGGE. Quindi qui si taglia, e sotto si valida.
        for taglio in ("\n---", "\nGrazie.", "\nThank you."):
            i = risposta.find(taglio)
            if i >= 0:
                risposta = risposta[:i]
        fuori[chiave] = risposta.replace("*" + domanda_en + "*", "").strip()
    return fuori


def importa(root: Path, percorso: str) -> int:
    """Da un contributo RICEVUTO a una cicatrice nel registro.

    Questa e' la promessa di CONTRIBUTING.md, mantenuta dal codice: se dal contributo
    nasce un lavoro, **il nome di chi l'ha proposto resta scritto**, col numero e la data.

    Il sistema prepara la scheda; **cosa l'ha risolto e cosa lo avrebbe preso le scrive
    una persona**, perche' quelle due cose non si possono dedurre da un racconto.
    """
    file = Path(percorso)
    if not file.is_file():
        print(f"  non esiste: {percorso}", file=sys.stderr)
        return 2
    testo = file.read_text(encoding="utf-8")
    risposte = _risposte(testo)
    # Il credito e' UNA RIGA, e non puo' portare caratteri che rompono lo YAML.
    # (Il 2026-10-13 il credito si e' portato dietro la coda del documento e ha prodotto
    # una stringa non chiusa: il registro l'ha rifiutata. Da qui la regola: chi scrive
    # un registro lo RILEGGE, e piu' sotto infatti si rilegge.)
    _grezzo = risposte.get("credito", "").strip()
    credito = _grezzo.splitlines()[0].strip() if _grezzo else ""
    credito = credito.replace('"', "'").replace("\\", "")
    anonimo = (not credito) or credito.lower() in {"anonimo", "anonymous", "non lo so", "i don't know"}

    cartella = Path(root) / "errori"
    cartella.mkdir(parents=True, exist_ok=True)
    try:
        ident, destinazione = ad_docs.prenota_id(
            cartella, "ERR", cifre=4, slug="da-contributo", estensione=".yaml"
        )
    except ad_docs.IdNonPrenotabile as errore:
        print(f"Non ho potuto prenotare un id: {errore}", file=sys.stderr)
        return 2

    def blocco(testo_: str) -> str:
        return "  " + "\n  ".join(testo_.splitlines()) + "\n"

    corpo = [
        f"# {ident} — Da un contributo: {file.stem}\n",
        f"id: {ident}",
        f'data: "{_data()}"',
        "",
        "cosa_e_fallito: >",
        blocco(f"[{risposte.get('cosa_e_successo', '')}] "
               f"Come si riproduce: {risposte.get('come_si_riproduce', '')} "
               f"Il sistema ha risposto: {risposte.get('cosa_dice_il_sistema', '')}"),
        "cosa_l_ha_risolto: >",
        "  DA COMPLETARE. Nessuno puo' dedurre da un racconto cosa ha risolto il problema:\n"
        "  lo scrive chi lo risolve. Finche' e' vuoto, la voce resta aperta — ed e' giusto.",
        "cosa_l_avrebbe_preso: >",
        blocco("DA COMPLETARE. " + (risposte.get("cosa_proponi", "").strip() or
                                    "Chi l'ha proposto non ha indicato una difesa.")),
        "diventa: nota",
        "dove: \"\"",
        "trovato_da: contributo",
        f'proposto_da: "{"" if anonimo else credito}"',
        "stato: aperto",
        "",
        "riferimenti:",
        f'  - "{file}"',
        "",
        "# La scheda l'ha preparata il sistema da un contributo ricevuto.",
        "# I due campi 'DA COMPLETARE' li scrive una persona: un racconto dice cosa e'",
        "# successo, non cosa l'ha risolto ne' cosa lo avrebbe preso.",
        "" if anonimo else f"# Credito: {credito} — se dal contributo nasce un controllo,",
        "" if anonimo else "# il nome resta qui, col numero e la data. E' la promessa di CONTRIBUTING.md.",
        "",
    ]
    testo_finale = "\n".join(corpo)
    # Chi scrive un registro lo rilegge (ERR-0046). Se non si legge, non si lascia.
    try:
        ad_controllo = __import__("yaml").safe_load(testo_finale)
        assert isinstance(ad_controllo, dict), "non e' un oggetto YAML"
    except Exception as errore:
        print(f"  NON ho scritto niente: la scheda non sarebbe leggibile ({errore}).",
              file=sys.stderr)
        print("  E' un difetto di questo comando: segnalalo.", file=sys.stderr)
        return 2
    destinazione.write_text(testo_finale, encoding="utf-8")
    print(f"  scritto: {destinazione}")
    print(f"  id:      {ident}  (prenotato)")
    print(f"  credito: {'anonimo' if anonimo else credito}")
    print()
    print("  Adesso completalo: i due 'DA COMPLETARE', e metti `diventa: controllo`")
    print("  con il file in `dove` quando la difesa esiste davvero.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Contributi al progetto")
    parser.add_argument("comando", choices=("nuovo", "elenca", "check", "importa"))
    parser.add_argument("percorso", nargs="?")
    parser.add_argument("--root", default=str(TOOLS.parent))
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if args.comando == "nuovo":
        return nuovo(root)
    if args.comando == "elenca":
        return elenca(root)
    if args.comando == "importa":
        if not args.percorso:
            print("  serve il percorso del contributo ricevuto", file=sys.stderr)
            return 2
        return importa(root, args.percorso)
    if not args.percorso:
        print("  serve il percorso del documento", file=sys.stderr)
        return 2
    return check(args.percorso)


if __name__ == "__main__":
    raise SystemExit(main())
