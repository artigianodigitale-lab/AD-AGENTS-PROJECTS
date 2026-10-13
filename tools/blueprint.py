#!/usr/bin/env python3
"""Il Blueprint di un progetto: il documento d'ingresso, generato dai registri.

Perche' esiste, in una riga: oggi per capire a che punto e' un progetto servono
cinque o sei file, e un riassunto **scritto a mano** diventerebbe la seconda
verita' del progetto — la cosa che si allontana piu' in fretta, perche' nessuno
la rilegge.

Quindi il Blueprint ha **due parti**:

  - una **scritta a mano** (cos'e' il progetto, per chi, perche'): sta in cima,
    si scrive una volta, e nessuno la rigenera;
  - una **generata** dai registri, fra due marcatori. Il controllo la rigenera e
    confronta: se qualcuno la modifica a mano, o se non e' aggiornata dopo una
    chiusura, **e' un errore**.

Cosi' il Blueprint **non puo' mentire**. Non per disciplina: perche' e'
impossibile.

Uso:
    python3 tools/blueprint.py render "<progetto>"   # scrive (serve il permesso)
    python3 tools/blueprint.py check ["<progetto>"]  # verifica, senza scrivere
    python3 tools/blueprint.py show "<progetto>"     # stampa, senza scrivere

Esito: 0 tutto a posto, 1 altrimenti, 2 scrittura rifiutata perche' nessun
contract approvato copre il percorso.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re

import yaml
import sys
from pathlib import Path

import ad_drift
import ad_docs
import ad_milestone
import ad_scope

RADICE = Path(__file__).resolve().parents[1]
NOME = "BLUEPRINT.md"

INIZIO = "<!-- generato:inizio -->"
FINE = "<!-- generato:fine -->"

#: Cosa si scrive a mano quando il Blueprint nasce. Due righe, non due pagine:
#: la parte lunga la generano i registri.
TESTA = """# BLUEPRINT — {progetto}

> La parte sopra il marcatore la scrive una persona, una volta sola: **cos'e' questo progetto,
> per chi, perche' esiste.** La parte sotto la generano i registri, e il controllo la
> rigenera e confronta: se la modifichi a mano, o se non e' aggiornata, e' un errore.
> Vedi `tools/blueprint.py`.

## Cos'e' questo progetto

<Due righe: cosa fa, per chi, e perche' vale la pena farlo. Se non le sai scrivere,
il progetto non e' ancora chiaro abbastanza per lavorarci.>

## Per chi

<Chi paga, chi usa, chi decide. Se sono tre persone diverse, dillo.>

"""


def _stato_dichiarato(percorso: Path) -> str:
    """Lo stato che un record dichiara di se', letto dal suo blocco YAML.

    Perche' non basta che il file esista: `new-milestone` crea il rapporto come
    **modello**, con `stato: aperta`. Guardare solo l'esistenza faceva dire al
    Blueprint «chiusa» a una tappa appena aperta — cioe' lo faceva mentire, che
    e' esattamente quello che questo strumento esiste per impedire.
    """
    try:
        testo = percorso.read_text(encoding="utf-8")
    except OSError:
        return ""
    trovato = re.search(r"^stato:\s*([a-zA-Z]+)", testo, re.M)
    return trovato.group(1).lower() if trovato else ""


def percorso(progetto: str | Path, root: Path | str | None = None) -> Path:
    """Dove vive il Blueprint di un progetto."""
    base = Path(root) if root else RADICE
    return base / str(progetto) / ad_milestone.PROJECT_DOCS / NOME


def _contratti_del_progetto(progetto: str, root: Path) -> list[ad_scope.WriteScope]:
    """I permessi che scrivono in questo progetto, attivi o no."""
    trovati = []
    for scope in ad_scope.load_write_scopes(root):
        if ad_scope._primo_progetto(scope.scopes) == progetto:
            trovati.append(scope)
    return trovati


def _prove(progetto: str, root: Path) -> list[Path]:
    """Le prove depositate per questo progetto."""
    cartella = root / progetto / ad_milestone.PROJECT_DOCS / "Evidenze"
    if not cartella.is_dir():
        return []
    return sorted(cartella.glob("*.yaml"))


def _discrepanze(progetto: str, root: Path, contratti: list[str]) -> list[ad_drift.Drift]:
    """Le discrepanze aperte che riguardano questo progetto."""
    fuori = []
    for voce in ad_drift.load(root):
        if voce.closed:
            continue
        testo = " ".join([voce.title, *voce.fields.values()])
        if progetto in testo or any(task in testo for task in contratti):
            fuori.append(voce)
    return fuori


def _tutti_i_permessi(progetto: str, root: Path) -> list[str]:
    """Tutti i permessi che scrivono in questo progetto, **anche quelli chiusi**.

    `ad_scope.load_write_scopes` restituisce solo gli attivi: per l'autorizzazione va
    bene, per riconoscere un errore no. Un errore puo' nominare un permesso che nel
    frattempo e' stato chiuso, ed e' comunque un errore di questo progetto.
    """
    trovati = []
    for percorso in (root / "contratti").rglob("*.yaml"):
        if percorso.name.startswith("_"):
            continue
        try:
            dati = yaml.safe_load(percorso.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        scope = dati.get("write_scope") or []
        if isinstance(scope, str):
            scope = [scope]
        if _primo_progetto_di(scope) == progetto:
            trovati.append(str(dati.get("task_id", percorso.stem)))
    return sorted(set(trovati))


def _primo_progetto_di(scope) -> str | None:
    """Il primo segmento di un write_scope, se e' una cartella numerata."""
    for voce in scope:
        testa = str(voce).strip().strip('"').split("/", 1)[0]
        if re.match(r"^\d+\.", testa):
            return testa
    return None


def _nomi_del_progetto(progetto: str) -> list[str]:
    """Come un errore puo' nominare questo progetto.

    Il nome intero funziona raramente: gli errori si scrivono a mano, e chi li scrive
    dice «Marketing Factory», non «3. AD-Marketing-Factory». Quindi si guarda anche
    **la coda del nome** — le ultime due parole — che e' come lo si nomina davvero.

    E' un'euristica, e va detta: puo' sbagliare in entrambi i versi.
    """
    intero = progetto.lower()
    parole = re.split(r"[\s.\-_]+", progetto)
    parole = [p for p in parole if p and not p.isdigit()]
    coda = " ".join(parole[-2:]).lower() if len(parole) >= 2 else ""
    return [n for n in (intero, coda) if n]


def _errori(progetto: str, root: Path, contratti: list[str]) -> list[dict]:
    """Gli errori registrati che riguardano questo progetto.

    Un errore riguarda un progetto se lo nomina, o se nomina uno dei suoi permessi.
    NON si mostrano gli errori della societa': quelli stanno in `errori/`, e chi li
    vuole li legge la'.
    """
    import errori  # noqa: PLC0415

    nomi = _nomi_del_progetto(progetto)
    fuori = []
    for voce in errori.carica(root):
        dati = voce["dati"]
        if not dati:
            continue
        testo = " ".join(
            [
                str(dati.get("cosa_e_fallito", "")),
                str(dati.get("cosa_l_ha_risolto", "")),
                str(dati.get("cosa_l_avrebbe_preso", "")),
                " ".join(str(r) for r in (dati.get("riferimenti") or [])),
            ]
        ).lower()
        if any(nome in testo for nome in nomi) or any(
            task.lower() in testo for task in contratti
        ):
            fuori.append(dati)
    return fuori

def _verbali(progetto: str, root: Path, contratti: list[str]) -> list[Path]:
    """I verbali che nominano questo progetto o i suoi permessi."""
    cartella = root / "DECISIONI"
    if not cartella.is_dir():
        return []
    fuori = []
    for percorso_verbale in sorted(cartella.glob("DEC-*.md")):
        try:
            testo = percorso_verbale.read_text(encoding="utf-8")
        except OSError:
            continue
        if progetto in testo or any(task in testo for task in contratti):
            fuori.append(percorso_verbale)
    return fuori


# ---------------------------------------------------------------------------
# Le dichiarazioni, da cui la prosa e' COSTRUITA
#
# Perche' stanno qui e non dentro le frasi: il 2026-10-10 ho misurato **30
# affermazioni scritte a mano** in questo generatore, **zero derivate**. E tre
# righe di prosa erano gia' sbagliate o lo sarebbero diventate:
#
#   - «Letto dai registri: ...»  -> mancava `errori`
#   - «se il blocco e' cambiato e' un errore» -> falso da DEC-0033
#   - «distingue tre casi» -> i verdetti erano diventati quattro
#
# **Un letterale non ha nessuna dipendenza dalla cosa che descrive.** Quando la
# cosa cambia, il letterale resta: compila, si stampa, e nessuno se ne accorge.
# Quindi: quello che ha una fonte si DERIVA da qui, e quello che non ne ha lo
# dice dentro la frase.
# ---------------------------------------------------------------------------

#: Cosa il generatore legge davvero, e per fare quale sezione.
FONTI: tuple[tuple[str, str], ...] = (
    ("tappe e passi", "A che punto e', La storia"),
    ("permessi", "Chi puo' scrivere qui"),
    ("prove", "Le prove"),
    ("discrepanze", "Cosa non torna"),
    ("errori", "Errori che hanno toccato questo progetto"),
    ("verbali", "Cosa e' stato deciso"),
)

#: I registri che esistono e NON si leggono, con la ragione. Dichiararli e' il
#: modo di non lasciare che l'assenza passi per completezza.
NON_LETTE: tuple[tuple[str, str], ...] = (
    ("requisiti", "non ancora collegati"),
    ("piani", "non ancora collegati"),
    ("comunicazioni", "non ancora collegati"),
    ("proposte di metodo", "non ancora collegate"),
)

#: Le sezioni che NON vengono da un registro, e perche'. Senza questa lista, una
#: sezione nuova potrebbe affermare fatti senza che nessuno lo dichiari — ed e'
#: esattamente cosi' che sono nate le tre righe sbagliate.
SEZIONI_NON_DA_REGISTRI: tuple[tuple[str, str], ...] = (
    ("Dove sta cosa", "legge la cartella del progetto, non un registro"),
    ("Fine", "la chiusura parla del meccanismo, non dei dati"),
)

#: I verdetti di `check`, e cosa significano. La prosa e' costruita da qui, e
#: `_verdetto()` rifiuta un verdetto non dichiarato: cosi' aggiungerne uno senza
#: scriverlo e' **impossibile**, non «da ricordare».
VERDETTI: tuple[tuple[str, str], ...] = (
    ("aggiornato", "e' dei registri di adesso"),
    ("indietro", "autentico ma di registri piu' vecchi"),
    ("manomesso", "il testo non corrisponde al proprio sigillo"),
    ("senza-impronta", "il sigillo manca o non e' in cima: versione vecchia, o qualcuno ci ha scritto sopra"),
    ("senza-marcatori", "i marcatori del blocco generato non ci sono"),
    ("assente", "il Blueprint non esiste"),
)


def _verdetto(nome: str, dettaglio: str) -> tuple[str, str]:
    """Un verdetto, rifiutando quelli non dichiarati in VERDETTI."""
    if nome not in {n for n, _ in VERDETTI}:
        raise ValueError(
            f"verdetto '{nome}' non dichiarato in VERDETTI: la prosa del Blueprint lo "
            "ignorerebbe, e direbbe una cosa incompleta senza accorgersene"
        )
    return nome, dettaglio


def _corpo(progetto: str, root: Path | None = None) -> str:
    """Il corpo del blocco generato. Deterministico: nessuna data, nessun ordine casuale."""
    base = root or RADICE
    righe: list[str] = []

    righe.append("## A che punto e'")
    righe.append("")

    tappe = ad_milestone.scan(base / progetto)
    aperti: list[tuple[int, int]] = []
    for tappa in tappe:
        for passo in tappa.sprints:
            if passo.has_prompt and _stato_dichiarato(
                passo.path / ad_milestone.SPRINT_REPORT
            ) not in ("chiuso", "chiusa"):
                aperti.append((tappa.number, passo.number))

    if not tappe:
        righe.append("**Fermo.** Il progetto non ha una storia documentata: nessuna tappa aperta.")
    elif aperti:
        tappa, passo = aperti[0]
        righe.append(f"**Tappa {tappa} · Passo {passo}** — aperto, senza rapporto.")
        if len(aperti) > 1:
            altri = ", ".join(f"{t}/{p}" for t, p in aperti[1:])
            righe.append(f"")
            righe.append(f"Altri passi aperti senza rapporto: {altri}.")
    else:
        ultima = tappe[-1]
        righe.append(f"**Fermo.** L'ultima tappa e' la {ultima.number}, e non ha passi aperti.")

    guai = ad_milestone.problems(base / progetto)
    if guai:
        righe.append("")
        righe.append("Il controllo della storia segnala:")
        righe.append("")
        for guaio in guai:
            righe.append(f"- {guaio}")

    righe.append("")
    righe.append("## La storia")
    righe.append("")
    if not tappe:
        righe.append("Nessuna tappa.")
    else:
        righe.append("| Tappa | Obiettivo | Passi | Stato |")
        righe.append("|---|---|---|---|")
        for tappa in tappe:
            elenco = []
            for passo in tappa.sprints:
                if not passo.has_prompt:
                    segno = "vuoto"
                elif _stato_dichiarato(passo.path / ad_milestone.SPRINT_REPORT) in ("chiuso", "chiusa"):
                    segno = "chiuso"
                else:
                    segno = "aperto"
                elenco.append(f"{passo.number}·{segno}")
            passi = ", ".join(elenco) or "—"
            dichiarato = _stato_dichiarato(tappa.path / ad_milestone.MILESTONE_REPORT)
            stato = "chiusa" if dichiarato in ("chiusa", "chiuso") else "aperta"
            righe.append(f"| {tappa.number} | vedi `Milestone {tappa.number}/REPORT.md` | {passi} | {stato} |")
        righe.append("")
        righe.append(
            "Legenda dei passi: `N·chiuso` ha il rapporto, `N·aperto` ha il foglio ma non il "
            "rapporto, `N·vuoto` non ha nemmeno il foglio."
        )

    # --- chi puo' scrivere ---------------------------------------------------
    contratti = _contratti_del_progetto(progetto, base)
    righe.append("")
    righe.append("## Chi puo' scrivere qui")
    righe.append("")
    if not contratti:
        righe.append("**Nessun permesso.** Il progetto e' chiuso: va aperto un passo prima di toccarlo.")
    else:
        righe.append("| Permesso | Chi | Tappa·Passo | Stato |")
        righe.append("|---|---|---|---|")
        for scope in sorted(contratti, key=lambda s: s.task_id):
            tappa = "-" if scope.milestone is None else str(scope.milestone)
            passo = "-" if scope.sprint is None else str(scope.sprint)
            righe.append(
                f"| `{scope.task_id}` | `{scope.agent}` | {tappa}·{passo} | {scope.status} |"
            )

    # --- le prove ------------------------------------------------------------
    prove = _prove(progetto, base)
    righe.append("")
    righe.append("## Le prove")
    righe.append("")
    if not prove:
        righe.append("Nessuna prova depositata.")
    else:
        for prova in prove:
            righe.append(f"- `{prova.name}`")
    righe.append("")
    righe.append(f"Totale: **{len(prove)}**.")

    # --- cosa non torna ------------------------------------------------------
    nomi = [scope.task_id for scope in contratti]
    discrepanze = _discrepanze(progetto, base, nomi)
    righe.append("")
    righe.append("## Cosa non torna")
    righe.append("")
    if not discrepanze:
        righe.append("Nessuna discrepanza aperta che riguardi questo progetto.")
    else:
        for voce in discrepanze:
            righe.append(f"- **{voce.id}** ({voce.severity or '—'}) — {voce.title}")

    # --- gli errori ----------------------------------------------------------
    errori_del_progetto = _errori(progetto, base, _tutti_i_permessi(progetto, base))
    righe.append("")
    righe.append("## Errori che hanno toccato questo progetto")
    righe.append("")
    if not errori_del_progetto:
        righe.append("Nessun errore registrato riguarda questo progetto.")
    else:
        for voce in errori_del_progetto:
            stato = str(voce.get("stato", "?"))
            segno = "" if stato == "chiuso" else f" **({stato})**"
            righe.append(f"- `{voce.get('id', '?')}`{segno} — {str(voce.get('cosa_e_fallito', ''))[:160]}")
        aperti = [v for v in errori_del_progetto if v.get("stato") != "chiuso"]
        righe.append("")
        righe.append(
            f"Totale: **{len(errori_del_progetto)}**, di cui **{len(aperti)}** ancora aperti."
        )

    # --- i verbali -----------------------------------------------------------
    verbali = _verbali(progetto, base, nomi)
    righe.append("")
    righe.append("## Cosa e' stato deciso")
    righe.append("")
    if not verbali:
        righe.append("Nessun verbale riguarda questo progetto.")
    else:
        for verbale in verbali:
            nome = verbale.stem
            righe.append(f"- `{nome}`")

    # --- dove sta cosa -------------------------------------------------------
    docs = base / progetto / ad_milestone.PROJECT_DOCS
    righe.append("")
    righe.append("## Dove sta cosa")
    righe.append("")
    righe.append("```text")
    righe.append(f"{progetto}/")
    righe.append(f"  {ad_milestone.PROJECT_DOCS}/")
    if docs.is_dir():
        for voce in sorted(docs.iterdir()):
            if voce.is_dir():
                quante = len(list(voce.glob("*.md"))) + len(list(voce.glob("*.yaml")))
                righe.append(f"    {voce.name}/   ({quante} file)")
            elif voce.name != NOME:
                righe.append(f"    {voce.name}")
        righe.append(f"    {NOME}   <- questo documento")
    righe.append("```")

    righe.append("")
    righe.append("---")
    righe.append("")
    righe.append(
        "**Letto dai registri**: " + ", ".join(nome for nome, _ in FONTI) + ". "
        "**Non letto**: "
        + ", ".join(f"{nome} ({perche})" for nome, perche in NON_LETTE)
        + ". Un registro che non e' qui non e' entrato in questa fotografia."
    )
    righe.append("")
    righe.append(
        "**Cos'e' garantito, e cosa no.** L'impronta in cima garantisce che questo testo non e' "
        "stato toccato dopo essere stato generato. **Non garantisce che sia giusto**: se il "
        "generatore legge il campo sbagliato, il sigillo sigilla un errore. *Autentico* non vuol "
        "dire *corretto* — e chi legge non deve smettere di guardare perche' c'e' un sigillo."
    )
    righe.append("")
    righe.append(
        "`python3 tools/blueprint.py check` distingue "
        + str(len(VERDETTI))
        + " casi: "
        + "; ".join(f"**{nome}** ({spiega})" for nome, spiega in VERDETTI)
        + "."
    )
    return "\n".join(righe)


def _impronta(corpo: str) -> str:
    """L'impronta dei registri: quel che basta a dire se sono cambiati."""
    return hashlib.sha256(corpo.encode("utf-8")).hexdigest()[:12]


def _ultima_tappa_chiusa(progetto: str, root: Path | None = None) -> int | None:
    """L'ultima tappa chiusa: e' il momento che questa fotografia descrive."""
    base = root or RADICE
    chiusa = None
    for tappa in ad_milestone.scan(base / progetto):
        if _stato_dichiarato(tappa.path / ad_milestone.MILESTONE_REPORT) in ("chiusa", "chiuso"):
            chiusa = tappa.number
    return chiusa


def genera(progetto: str, root: Path | None = None, impronta: str | None = None) -> str:
    """Il blocco generato, con l'impronta dei registri da cui viene.

    L'impronta e' il pezzo che rende possibile distinguere **vecchio** da **falso**.
    Senza, un Blueprint che non corrisponde ai registri puo' essere due cose molto
    diverse — una fotografia invecchiata, o una manomissione — e dal file le due si
    assomigliano. Con, si distinguono:

      - i registri non si sono mossi e il contenuto non corrisponde  -> manomesso
      - i registri si sono mossi, e il contenuto e' esattamente quello
        che il generatore avrebbe prodotto da quelli vecchi           -> indietro
    """
    corpo = _corpo(progetto, root)
    fp = impronta if impronta is not None else _impronta(corpo)
    tappa = _ultima_tappa_chiusa(progetto, root)
    dove = (
        f"alla chiusura della tappa {tappa}"
        if tappa is not None
        else "a progetto ancora senza tappe chiuse"
    )
    return (
        f"> **Fotografia dei registri, scattata {dove}.** impronta: `{fp}`\n"
        "> Non e' un documento da tenere aggiornato: e' una fotografia. Fra una tappa e "
        "l'altra puo' essere **indietro**, ed e' normale.\n\n" + corpo
    )


IMPRONTA_RE = re.compile(r"impronta: `([0-9a-f]+)`")


def impronta_dichiarata(testo: str) -> str | None:
    """L'impronta che il Blueprint dichiara di aver fotografato."""
    trovato = IMPRONTA_RE.search(testo)
    return trovato.group(1) if trovato else None


def separa_fotografia(blocco: str) -> tuple[str | None, str]:
    """Divide il blocco in (impronta dichiarata, corpo).

    L'impronta NON e' un puntatore ai registri: e' un **sigillo sul contenuto**.
    E' la differenza che fa funzionare tutto — un puntatore non si puo' verificare
    dopo che i registri sono cambiati, un sigillo si', sempre.
    """
    # Il riconoscimento non e' legato alla parola «Fotografia»: anche la vista
    # operativa usa lo stesso meccanismo, e la sua intestazione comincia con
    # «> **Vista». Quello che conta e' che la PRIMA riga porti un'impronta.
    righe = blocco.split("\n")
    if len(righe) >= 3 and righe[0].startswith("> **") and IMPRONTA_RE.search(righe[0]):
        trovato = IMPRONTA_RE.search(righe[0])
        corpo = "\n".join(righe[2:]).lstrip("\n")
        return (trovato.group(1) if trovato else None), corpo
    return None, blocco


def blocco_generato(testo: str) -> str | None:
    """Estrae la parte generata fra i marcatori, o None se mancano."""
    inizio = testo.find(INIZIO)
    fine = testo.find(FINE)
    if inizio < 0 or fine < 0 or fine < inizio:
        return None
    return testo[inizio + len(INIZIO):fine].strip("\n")


def controlla(progetto: str, root: Path | None = None) -> tuple[str, str]:
    """Stato del Blueprint. I verdetti possibili sono quelli di VERDETTI, e solo quelli."""
    base = root or RADICE
    percorso_file = base / progetto / ad_milestone.PROJECT_DOCS / NOME
    if not percorso_file.is_file():
        return _verdetto("assente", f"{progetto}: nessun {NOME}")
    try:
        testo = percorso_file.read_text(encoding="utf-8")
    except OSError as errore:
        return _verdetto("assente", f"{progetto}: non si legge ({errore})")

    attuale = blocco_generato(testo)
    if attuale is None:
        return _verdetto("senza-marcatori", f"{progetto}: mancano i marcatori {INIZIO} / {FINE}")
    attuale = attuale.strip("\n")

    dichiarata, corpo = separa_fotografia(attuale)
    if dichiarata is None:
        # Il blocco non comincia con l'intestazione della fotografia. Due possibilita',
        # e non si distinguono: e' stato generato da una versione vecchia, oppure
        # qualcuno ci ha aggiunto qualcosa PRIMA del sigillo — che e' un modo di
        # scavalcare il controllo. In entrambi i casi il rimedio e' lo stesso, e
        # chiamarlo «indietro» (non un errore) lascerebbe aperto un buco.
        return _verdetto(
            "senza-impronta",
            f"{progetto}: il blocco generato non comincia con l'intestazione della fotografia — "
            "o e' stato generato da una versione vecchia, o qualcuno ci ha scritto sopra. "
            "Rigeneralo e guarda cosa cambia",
        )

    # 1. IL SIGILLO REGGE? Se il corpo non corrisponde alla sua stessa impronta,
    #    qualcuno l'ha cambiato dopo la generazione. Vale sempre, anche se i
    #    registri nel frattempo si sono mossi.
    if _impronta(corpo) != dichiarata:
        return _verdetto(
            "manomesso",
            f"{progetto}: il contenuto non corrisponde alla sua impronta — e' stato cambiato "
            "dopo la generazione",
        )

    # 2. Autentico. Ora: e' una fotografia dei registri di adesso?
    if dichiarata == _impronta(_corpo(progetto, base)):
        return _verdetto("aggiornato", f"{progetto}: aggiornato")

    # 3. Autentico ma di registri piu' vecchi. Non e' falso: e' indietro.
    return _verdetto(
        "indietro",
        f"{progetto}: fotografia autentica di registri piu' vecchi (impronta {dichiarata}). "
        "Fra una tappa e l'altra e' normale",
    )


def scrivi(progetto: str, root: Path | None = None) -> Path:
    """Genera e scrive il Blueprint, conservando la parte scritta a mano.

    Raises:
        PermissionError: Se nessun contract approvato copre il percorso. Il
            Blueprint vive DENTRO il progetto, quindi scriverlo e' una scrittura
            in un percorso protetto: fino al 2026-10-11 questo strumento importava
            `ad_scope` e non lo interrogava, ed e' passato dove non doveva
            (ERR-0026).
    """
    base = root or RADICE
    percorso_file = base / progetto / ad_milestone.PROJECT_DOCS / NOME
    # La guardia PRIMA di creare la cartella: un rifiuto non deve lasciare tracce.
    ad_scope.guard(percorso_file)
    percorso_file.parent.mkdir(parents=True, exist_ok=True)

    testa = TESTA.format(progetto=progetto)
    if percorso_file.is_file():
        attuale = percorso_file.read_text(encoding="utf-8")
        taglio = attuale.find(INIZIO)
        if taglio > 0:
            testa = attuale[:taglio].rstrip("\n") + "\n\n"

    percorso_file.write_text(
        testa + INIZIO + "\n" + genera(progetto, base).strip("\n") + "\n" + FINE + "\n",
        encoding="utf-8",
    )
    return percorso_file


def _progetti(base: Path) -> list[str]:
    """I progetti numerati presenti nella super cartella."""
    return sorted(
        voce.name for voce in base.iterdir() if voce.is_dir() and ad_scope.PROTECTED_DIR.match(voce.name)
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Blueprint di un progetto")
    parser.add_argument("comando", choices=("render", "check", "show"))
    parser.add_argument("progetto", nargs="?", default="")
    parser.add_argument("--root", default=str(RADICE))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    base = Path(args.root).resolve()

    if args.comando == "render":
        if not args.progetto:
            print("serve il nome del progetto", file=sys.stderr)
            return 2
        try:
            percorso_file = scrivi(args.progetto, base)
        except PermissionError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(f"scritto {percorso_file.relative_to(base)}")
        return 0

    if args.comando == "show":
        if not args.progetto:
            print("serve il nome del progetto", file=sys.stderr)
            return 2
        print(genera(args.progetto, base))
        return 0

    # check
    progetti = [args.progetto] if args.progetto else _progetti(base)
    esiti = [(p, *controlla(p, base)) for p in progetti]

    if args.json:
        print(json.dumps([{"progetto": p, "stato": s, "dettaglio": d} for p, s, d in esiti], ensure_ascii=False))
        return 1 if any(s in ("manomesso", "senza-marcatori", "senza-impronta") for _, s, _ in esiti) else 0

    senza = [p for p, s, _ in esiti if s == "assente"]
    manomessi = [(p, d) for p, s, d in esiti if s in ("manomesso", "senza-marcatori", "senza-impronta")]
    indietro = [(p, d) for p, s, d in esiti if s == "indietro"]
    aggiornati = [p for p, s, _ in esiti if s == "aggiornato"]

    for _, dettaglio in manomessi:
        print(f"  MANOMESSO  {dettaglio}")
    for _, dettaglio in indietro:
        print(f"  indietro   {dettaglio}")
    print(
        f"  aggiornati: {len(aggiornati)}   indietro: {len(indietro)}   "
        f"manomessi: {len(manomessi)}   senza Blueprint: {len(senza)}"
    )
    if senza:
        print(f"  senza Blueprint: {', '.join(senza[:6])}{' ...' if len(senza) > 6 else ''}")

    # Tre esiti diversi, e solo uno e' un errore:
    #   - senza Blueprint: una cosa da fare
    #   - indietro: una fotografia autentica di registri piu' vecchi — normale
    #   - manomesso: il contenuto non corrisponde al proprio sigillo. E' una bugia.
    if manomessi:
        print(f"\nesito: {len(manomessi)} Blueprint manomessi")
        return 1
    if indietro:
        print(f"\nesito: nessun Blueprint mente, ma {len(indietro)} sono indietro")
        return 0
    print("\nesito: nessun Blueprint mente, e nessuno e' indietro")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
