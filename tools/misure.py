#!/usr/bin/env python3
"""Le misure di una verifica si eseguono, e l'allegato si genera.

    python3 tools/misure.py run    <elenco.yaml> --out <allegato.md>
    python3 tools/misure.py check  <elenco.yaml>
    python3 tools/misure.py elenca <elenco.yaml>
    python3 tools/misure.py confronta <a.md> <b.md>

Perche' esiste. Il report della verifica del 10-11 ottobre ha preso `FAIL` tre
volte sullo stesso criterio — «ogni affermazione porta la sua prova, comando
eseguito ed esito» — mentre i suoi fatti venivano confermati due volte da
verificatori indipendenti. La causa non era la negligenza: i numeri erano
**scritti a mano** in un documento che descrive un mondo in movimento, e ogni
correzione **spostava le righe**, rompendo le citazioni interne (`DEC-0044`).
Il rimedio non e' curare il documento: e' **togliere i numeri scritti a mano**.
Questo strumento li toglie: li esegue, e scrive quello che ha visto.

**Le misure stanno in un elenco dichiarato, non nel codice.** Il formato e' YAML,
e la ragione e' che il progetto lo usa gia' per tutto cio' che e' una
dichiarazione — contract, approvazioni, evidenze, verbali, errori, drift — e
perche' PyYAML e' gia' una dipendenza: un formato nuovo sarebbe una dipendenza
nuova, e il contract la vieta. Rispetto a JSON ha una cosa che qui conta piu'
della moda: i commenti, e le stringhe lunghe senza fughe. Un elenco contiene
`nome`, `comando`, `descrizione` (cosa misura), e facoltativamente `cwd` ed
`esito_atteso`. Nient'altro: **il codice non conosce nessuna misura**, e
aggiungerne una non richiede di toccare questo file.

**Il momento, e come regge la riproducibilita'.** Ogni misura porta il momento in
cui e' stata eseguita, perche' un numero vecchio non deve leggersi come attuale.
Il momento pero' cambia per definizione, quindi due esecuzioni non possono dare
un testo identico *carattere per carattere*: darebbero un testo identico **a
meno delle righe che portano un momento**, e quelle righe sono dichiarate qui
sotto in `PREFISSI_VARIABILI`, sono riconoscibili a occhio, e sono le uniche che
`confronta` ignora. L'allegato porta in testa l'**impronta stabile** — lo
`sha256` del documento con i momenti sostituiti da `<variabile>` — cosi' la
riproducibilita' non e' una promessa: e' un numero che due esecuzioni devono
dare uguale, e `misure.py confronta` lo verifica su due file veri.

**Un comando che fallisce non si nasconde.** Un codice di uscita diverso da
quello atteso viene riportato com'e', col suo codice, e il conteggio in testa lo
dichiara. E' la cosa che rende l'allegato onesto: un allegato che omette i
fallimenti e' peggio di nessun allegato, perche' si legge come una prova.

**Cosa non si esegue, e perche' e' spiegato.** `VIETATI` e' la lista delle forme
rifiutate, raggruppate per **famiglia**. Non e' riscritta da zero: parte da
`ad_scope.MUTATION_PATTERNS`, la stessa lista che il layer di enforcement usa per
la shell, e la **estende** dove una misura ha bisogno di piu'. La lezione di
`ERR-0026` e' che una difesa riscritta in ogni file viene dimenticata nel file
successivo: qui si estende, non si duplica. Il rifiuto e' **spiegato**, non
silenzioso: dice quale comando, quale famiglia lo vieta e come riformulare.

**Cosa il rifiuto NON garantisce — e perche' lo dice l'allegato.** La prima
versione di questo strumento prometteva «nessun comando scrive, sposta, cancella o
riscrive la storia». Era **falso**, e il gate `QA` l'ha dimostrato eseguendo dieci
forme che passavano — fra cui `git -C . commit`, che ha creato un commit vero, e
`sed -i.bak`, `awk 'BEGIN{system(...)}'`, un heredoc, `1> file`, `install`,
`node -e`. Quelle forme ora si rifiutano, ma **la promessa assoluta non si
rimette**: un elenco di cose vietate non finisce mai, e una promessa che nessun
controllo puo' mantenere fa smettere di guardare — che e' la lezione di
`ERR-0026`. Il testo del limite vive in ``LIMITE_RIFIUTO``, in **una definizione
sola**, e finisce **dentro l'allegato**: un limite scritto solo nel codice non e'
dichiarato, perche' l'artefatto che si cita come prova e' l'allegato.

**La validazione viene prima dell'esecuzione, e vale per l'intero elenco.** Se
una sola voce e' vietata, non parte **niente** e non si scrive **niente**. Un
elenco e' un atto unico: eseguirlo a meta' vorrebbe dire consegnare un allegato
che sembra completo e non lo e'. E il rifiuto arriva prima di ogni comando,
quindi un elenco sbagliato non ha effetti collaterali da riparare.

**La guardia di ambito si chiama prima di ogni scrittura.** `ad_scope.guard` e'
la porta riparata da `ADMF-004`: la scrittura fatta da uno script non passa
dall'euristica della shell del plugin, quindi la guardia sta dentro lo strumento
(`DEC-0008`). Qui e' chiamata due volte di proposito: una **prima** di eseguire
— per non lanciare trenta comandi e scoprire poi che l'allegato non si puo'
scrivere — e una dentro `scrivi`, che e' l'unico punto in cui questo file tocca
il disco. E l'**area di misura** sta dentro l'albero di autorita': un `--area`
che puntasse fuori sarebbe lo stesso varco di `ERR-0026`, cioe' «una capacita'
che nessuno deve poter attivare».

**Limiti dichiarati, perche' un limite nascosto e' peggio di un limite.**
Il rifiuto e' un'euristica su forme note, non un sandbox (il testo esteso e' in
``LIMITE_RIFIUTO``, e l'allegato lo porta dentro). Restano falsi positivi — un
comando di sola lettura che *nomina* una forma vietata viene rifiutato lo stesso:
bloccare un falso positivo e' un fastidio, lasciar passare una scrittura e' un
danno — e il gate ne ha trovati due che valevano la pena di togliere:
`printf 'vado su disco'` (la parola italiana «su») e `grep -n 'a>b'` (un `>`
dentro una stringa). L'output si tronca oltre `MAX_RIGHE`, e il troncamento e'
**dichiarato** con quante righe sono state omesse: non e' un taglio silenzioso, e
un test lo difende.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ad_docs  # noqa: E402
import ad_scope  # noqa: E402

#: L'elenco predefinito degli elenchi: dove vivono le misure dichiarate.
CARTELLA_ELENCHI = "misure-liste"

#: Quante righe di output finiscono nell'allegato. Oltre, si dichiara il taglio.
MAX_RIGHE = 40

#: Quanto si aspetta un comando prima di dichiararlo scaduto.
TIMEOUT_SECONDI = 120

#: I verbi che scrivono, presi dalla lista di `ad_scope` — e la stessa lista,
#: ancorata alla **posizione di comando**.
#:
#: Perche' due versioni dello stesso elenco. In `ad_scope` i verbi si cercano con
#: `\b(...)\b`, ed e' largo apposta: li' la domanda e' «questa shell potrebbe
#: scrivere?» e un falso positivo costa un fastidio. Qui la domanda e' la stessa
#: ma il costo e' diverso — il rifiuto **spegne una misura che qualcuno ha
#: dichiarato** — e i falsi positivi si sono visti subito, due volte: `grep -ln`
#: contiene `ln`, e `printf 'su disco: '` contiene `su`. Entrambi sono comandi di
#: sola lettura. Ancorare il verbo all'inizio di un comando, o dopo un separatore
#: o una barra, toglie i falsi positivi senza togliere nessun vero positivo:
#: un comando si scrive in posizione di comando, e `/bin/rm` e' ancora un `rm`.
#:
#: La differenza con `ad_scope` e' **due regole** — i verbi e la redirezione —
#: e un test la fissa: se lassu' cambiano quelle liste, il test lo dice invece di
#: lasciare due liste che divergono in silenzio.
#:
#: Le virgolette e la barra rovesciata sono nella classe di sinistra perche' la
#: shell le toglie: `"rm" -rf x` esegue `rm`, e senza di loro passerebbe. Il
#: prezzo sono falsi positivi in piu' (`grep 'rm' file` viene rifiutato): e' il
#: verso giusto in cui sbagliare, e ``LIMITE_RIFIUTO`` lo dichiara.
VERBI = "rm|mv|cp|tee|truncate|dd|touch|mkdir|rmdir|chmod|chown|ln|patch"
SCHEMA_VERBI_BASE = re.compile(rf"\b({VERBI})\b")
VERBI_IN_POSIZIONE = re.compile(
    rf"(?:^|[|;&(/\s\"'\\])({VERBI})(?=\s|$|[|;&)\"'\\])"
)

#: L'esecuzione che si annida, con `su` in posizione di comando: la parola
#: italiana «su» non e' un cambio di utente, e non deve spegnere una misura.
#: `su` vuole un separatore davanti — non basta uno spazio, o `printf 'vado su
#: disco'` verrebbe rifiutato (falso positivo trovato dal gate `QA`).
ESECUZIONE_ANNIDATA = re.compile(
    r"\b(sh|bash|zsh|dash|ksh|eval|exec|sudo|doas|xargs|nohup|env)\b"
)
CAMBIO_UTENTE = re.compile(r"(?:^|[|;&(]\s*)su(?=\s|$)")

#: Gli strumenti che scrivono file senza essere verbi della shell.
#:
#: Perche' non basta la lista dei verbi: `install` copia e crea file esattamente
#: come `cp`, e `tar`, `unzip`, `vi` scrivono per mestiere. Il gate `QA` ha
#: **eseguito** `install` e ha visto nascere il file.
STRUMENTI_CHE_SCRIVONO = re.compile(
    r"(?:^|[|;&(/\s\"'\\])(install|shred|mkfs|fdisk|tar|zip|unzip|gzip|gunzip"
    r"|vi|vim|nvim|nano|ed)(?=\s|$|[|;&)\"'\\])"
)

#: I linguaggi che eseguono comandi. Un programma dentro una stringa puo' fare
#: qualunque cosa — `awk 'BEGIN{system("touch x")}'` e' stato eseguito dal gate —
#: e da fuori non c'e' modo di leggerlo. Non servono a una misura di lettura:
#: quando servono, si scrive un programma in `tools/` e lo si chiama per nome.
LINGUAGGI_CHE_ESEGUONO = re.compile(
    r"\b(awk|gawk|mawk|perl|ruby|php|lua|tclsh|wish|make|expect|busybox)\b"
)

#: Il testo che diventa codice: un heredoc e' un programma che arriva dallo stdin,
#: e chi legge la riga di comando non lo vede. Il gate ha eseguito
#: `python3 - <<'PY'` e ha visto il programma partire.
TESTO_CHE_DIVENTA_CODICE = re.compile(r"<<")

#: Gli interpreti con codice inline — `-c` **e** `-e`: `node -e` e `ruby -e`
#: scrivono file quanto `python3 -c`, e il gate li ha eseguiti.
INTERPRETE_INLINE = re.compile(
    r"\b(python3?|node|deno|php|lua|perl|ruby)\s+(-{1,2}[\w-]+\s+)*-(c|e)\b"
)

#: La redirezione con un descrittore davanti: `1> f` scrive un file come `> f`, e
#: la regola di `ad_scope` non la vede perche' esclude la cifra prima di `>`.
#: `2>&1` invece **non** scrive niente — duplica un descrittore — e passa; e
#: `2>/dev/null` passa per la deroga dichiarata in ``DEROGA_FUORI``.
#:
#: Questa regola si applica **fuori dalle virgolette**, ed e' l'unica: un `>`
#: dentro una stringa non e' una redirezione, e il gate `QA` ha segnalato
#: `grep -n 'a>b' file` come falso positivo. Alle altre famiglie le virgolette
#: non si tolgono di proposito: `"rm" -rf x` **esegue** `rm`. Una redirezione
#: dentro una stringa, invece, la esegue solo chi ri-analizza la stringa — e
#: quelli (`sh`, `bash`, `eval`, `exec`, `xargs`, `sudo`, `awk`, gli interpreti
#: con `-c`) sono tutte famiglie rifiutate qui sotto.
REDIREZIONE = re.compile(r"\d*\s*>>?\s*(?![&=])(?!/dev/null)")

#: Il pattern della redirezione **come lo cerca `ad_scope`**: qui e' riscritto
#: (fuori dalle virgolette, e con il descrittore davanti), e questo e' il testo
#: che serve a riconoscerlo nella lista per non applicarlo due volte.
SCHEMA_REDIREZIONE_BASE = r"(^|[^=\d])>>?(?!=)"

#: Quali regole si applicano al comando **senza** le parti fra virgolette.
SOLO_FUORI_VIRGOLETTE: tuple[str, ...] = (REDIREZIONE.pattern,)

#: La storia di git, con le **opzioni globali** in mezzo: `git -C . commit` e'
#: un commit, e il gate l'ha creato davvero riscrivendo la storia di un albero di
#: prova. La regola di `ad_scope` vede solo `git` seguito subito dal verbo.
#: `git log --grep 'commit'` non e' un commit, e non viene toccato: dopo `git`
#: ci sono opzioni e poi il verbo, non una parola qualunque.
GIT_CHE_RISCRIVE = re.compile(
    r"\bgit\s+(?:-[A-Za-z][\w-]*(?:=\S+|\s+\S+)?\s+)*"
    r"(commit|add|push|pull|fetch|tag|merge|rebase|rm|mv|config|init|clone"
    r"|switch|update-ref|gc|prune|worktree|filter-branch)"
    r"|"
    r"\bgit\s+(?:-[A-Za-z][\w-]*(?:=\S+|\s+\S+)?\s+)*"
    r"(checkout|reset|clean|restore|apply|stash)\b"
)

#: La sostituzione in loco, in tutte le forme che `sed` accetta: `-i`, `-i.bak`,
#: `--in-place`. `sed -i.bak` e' stato eseguito dal gate, e la regola di
#: `ad_scope` — che pretende `-i` seguito da spazio o fine riga — non lo vedeva.
SED_IN_PLACE = re.compile(r"\bsed\b[^\n]*\s(?:-i\S*|--in-place\S*)")

#: Le famiglie di comandi che non si eseguono, con la ragione da mostrare.
#:
#: La base e' **la stessa** di `ad_scope`: il layer di enforcement e lo strumento
#: di misura devono rifiutare le stesse cose, o il secondo diventa il modo di
#: fare quello che il primo vieta. L'unico schema non ereditato e' quello dei
#: verbi, sostituito dalla versione ancorata; **il resto si aggiunge** — la
#: storia di git con le opzioni in mezzo, l'esecuzione annidata, i linguaggi che
#: eseguono, il testo che diventa codice, la redirezione col descrittore.
#:
#: Le aggiunte non sono un capriccio: sono le forme che il gate `QA` ha
#: **eseguito** su un albero di prova, scrivendo davvero. Vedi
#: ``LIMITE_RIFIUTO``: questa lista non chiude il problema, lo restringe.
VIETATI: tuple[tuple[str, re.Pattern[str]], ...] = (
    tuple(
        ("scrittura sul filesystem", schema)
        for schema in ad_scope.MUTATION_PATTERNS
        if schema.pattern
        not in (SCHEMA_VERBI_BASE.pattern, SCHEMA_REDIREZIONE_BASE)
    )
    + (
        ("scrittura sul filesystem", VERBI_IN_POSIZIONE),
        ("scrittura sul filesystem", STRUMENTI_CHE_SCRIVONO),
        ("scrittura sul filesystem", REDIREZIONE),
        ("scrittura sul filesystem", SED_IN_PLACE),
        ("storia di git", GIT_CHE_RISCRIVE),
        (
            "storia di git",
            re.compile(
                r"\bgit\s+(commit|add|push|pull|fetch|tag|merge|rebase|rm|mv|config"
                r"|init|clone|switch|update-ref|gc|prune|worktree)\b"
            ),
        ),
        ("esecuzione annidata", ESECUZIONE_ANNIDATA),
        ("cambio di utente", CAMBIO_UTENTE),
        ("interprete con codice inline", INTERPRETE_INLINE),
        ("linguaggio che esegue comandi", LINGUAGGI_CHE_ESEGUONO),
        ("testo che diventa codice", TESTO_CHE_DIVENTA_CODICE),
        (
            "scaricamento",
            re.compile(r"\b(curl|wget|rsync|scp|sftp)\b"),
        ),
        (
            "ricerca che esegue o scrive",
            re.compile(r"\bfind\b[^\n]*\s-(exec|execdir|ok|okdir|delete|fprint|fprint0|fls)\b"),
        ),
        (
            "cambio di directory",
            re.compile(r"(^|[|;&]\s*)cd\s"),
        ),
        (
            "processi e servizi",
            re.compile(r"\b(kill|pkill|killall|systemctl|service|reboot|shutdown|crontab)\b"),
        ),
        (
            "installazione di pacchetti",
            re.compile(r"\b(apt|apt-get|brew|snap|pipx|npm|pnpm|yarn)\b"),
        ),
    )
)

#: Il limite del rifiuto, in una definizione sola.
#:
#: Questo testo e' **la** dichiarazione del limite: la usano la docstring, il
#: registro `tools/README.md` e — questa e' la parte che il gate `QA` ha
#: contestato — l'**allegato**, che e' l'artefatto che si cita come prova. Un
#: limite che vive solo nel codice non e' dichiarato: chi legge l'allegato non lo
#: vede, e crede a una promessa che nessuno ha fatto.
#:
#: La frase da non riscrivere e' l'ultima: la difesa vera non e' questa lista.
LIMITE_RIFIUTO = (
    "Il rifiuto e' un'**euristica su forme note**, non un sandbox: rifiuta le "
    "famiglie elencate, non garantisce la sola lettura.\n"
    "Un comando che scrive senza somigliare a nessuna di quelle forme **non viene "
    "visto**. Il caso dichiarato e' `python3 tools/<programma>.py`: quello che fa "
    "lo decide il programma, non la riga di comando — e nessuna lista di forme "
    "vietate lo puo' sapere.\n"
    "Un elenco di cose vietate non finisce mai. La difesa vera non e' questa "
    "lista: e' che le misure stanno in **un file che si legge**, e che qualcuno "
    "risponde di averlo scritto."
)

#: Le sole righe che cambiano fra due esecuzioni dello stesso elenco.
#:
#: Sono tre famiglie, e sono tutte un momento o qualcosa che da un momento
#: dipende: il momento dell'esecuzione, l'impronta stabile (calcolata su questo
#: stesso testo, quindi non puo' contenere se stessa) e il momento di ogni
#: misura. `confronta` le ignora; tutto il resto deve essere identico.
PREFISSI_VARIABILI: tuple[str, ...] = (
    "**Momento.**",
    "| esecuzione |",
    "| **impronta stabile** |",
)

#: Cosa sostituisce i valori variabili quando si calcola l'impronta stabile.
SEGNO_VARIABILE = "<variabile>"

#: La riga con cui una misura dichiara che il **suo output** puo' dipendere dal tempo.
#:
#: Perche' serve, e perche' non si maschera. Un comando puo' **stampare** un
#: valore che dipende dall'ora — `coherence.py` scrive l'ora corrente e un conto
#: alla rovescia nei suoi messaggi. Il gate `QA` l'ha trovato: tre esecuzioni
#: consecutive davano tre impronte stabili diverse, con **due righe** di
#: differenza, tutte dentro l'output di una misura.
#:
#: La strada facile sarebbe togliere anche quelle righe dal calcolo
#: dell'impronta. **Non si fa**: nasconderebbe differenze vere dentro lo stesso
#: output — una divergenza nuova di `coherence.py` sparirebbe insieme all'ora.
#: Si **dichiara** invece: la misura porta questa riga, e `confronta` separa le
#: differenze **dichiarate** da quelle **vere** mostrandole entrambe.
SEGNO_TEMPO = "**Output dipendente dal tempo.**"

#: L'unico percorso fuori dall'area che si accetta: non e' un file, e' il posto
#: dove l'output non va. Senza, l'unico modo di zittire uno strumento sarebbe un
#: file vero — cioe' una scrittura.
DEROGA_FUORI = ("/dev/null",)

#: Avviso in testa a ogni riga di output quando il comando non e' mai partito.
NON_ESEGUITA = "non eseguita"


class ElencoNonValido(RuntimeError):
    """L'elenco delle misure non si puo' leggere o non e' completo."""


class AreaNonValida(RuntimeError):
    """L'area di misura non sta dentro l'albero di autorita'."""


@dataclass(frozen=True)
class Misura:
    """Una misura dichiarata: un nome, un comando, e cosa misura."""

    indice: int
    nome: str
    comando: str
    descrizione: str
    cwd: str = "."
    esito_atteso: tuple[int, ...] = (0,)
    tempo_nell_output: bool = False

    @property
    def identificatore(self) -> str:
        """L'etichetta con cui l'allegato e il rapporto la citano."""
        return f"M{self.indice:02d}"


@dataclass(frozen=True)
class Esclusa:
    """Una misura che l'elenco dichiara di non fare, con la ragione."""

    nome: str
    motivo: str
    comando: str = ""


@dataclass(frozen=True)
class Elenco:
    """Un elenco dichiarato di misure, piu' quelle che si e' scelto di non fare."""

    percorso: Path
    dichiarato: str
    impronta: str
    titolo: str
    descrizione: str
    area: str
    misure: tuple[Misura, ...]
    escluse: tuple[Esclusa, ...]


@dataclass(frozen=True)
class Esito:
    """Cosa e' successo a una misura: il comando, l'esito, il codice, il momento."""

    misura: Misura
    momento: str
    codice: int | None
    output: str
    righe_output: int
    eseguita: bool = True
    errore: str = ""

    @property
    def atteso(self) -> bool:
        """True quando il codice di uscita e' fra quelli dichiarati attesi."""
        return self.codice is not None and self.codice in self.misura.esito_atteso

    @property
    def verdetto(self) -> str:
        """L'etichetta breve dell'esito, per l'indice."""
        if not self.eseguita:
            return NON_ESEGUITA
        if self.atteso:
            return "eseguita"
        return "INATTESA"


def impronta(testo: str | bytes) -> str:
    """Return the first 12 hex digits of the sha256 of ``testo``.

    Dodici e' la lunghezza che il progetto usa gia' per le impronte (il report
    bocciato e' `f580bee8…`, il Blueprint di un progetto `e2474d97cd89`): abbastanza
    per non confondere due documenti, corta abbastanza per stare in una riga di
    una tabella.
    """
    dati = testo.encode("utf-8") if isinstance(testo, str) else testo
    return hashlib.sha256(dati).hexdigest()[:12]


def _testo(valore: Any, dove: str) -> str:
    """Return a non-empty string field, or raise."""
    if not isinstance(valore, str) or not valore.strip():
        raise ElencoNonValido(f"{dove}: campo mancante o vuoto")
    return valore.strip()


def _esiti_attesi(valore: Any, dove: str) -> tuple[int, ...]:
    """Read the declared expected exit codes, defaulting to ``(0,)``."""
    if valore is None:
        return (0,)
    valori = valore if isinstance(valore, list) else [valore]
    codici: list[int] = []
    for voce in valori:
        if isinstance(voce, bool) or not isinstance(voce, int):
            raise ElencoNonValido(f"{dove}: esito_atteso vuole numeri interi, non {voce!r}")
        codici.append(voce)
    if not codici:
        raise ElencoNonValido(f"{dove}: esito_atteso vuoto")
    return tuple(codici)


def carica(percorso: Path | str) -> Elenco:
    """Legge un elenco di misure dichiarato.

    Args:
        percorso: Il file YAML dell'elenco.

    Returns:
        L'elenco, con le misure numerate nell'ordine in cui sono dichiarate.

    Raises:
        ElencoNonValido: Se il file manca, non e' YAML, o una voce e' incompleta.
    """
    via = Path(percorso)
    try:
        grezzo = via.read_text(encoding="utf-8")
    except OSError as errore:
        raise ElencoNonValido(f"elenco illeggibile: {via} ({errore})") from errore
    try:
        dati = yaml.safe_load(grezzo)
    except yaml.YAMLError as errore:
        raise ElencoNonValido(f"elenco non e' YAML valido: {via} ({errore})") from errore
    if not isinstance(dati, dict):
        raise ElencoNonValido(f"elenco vuoto o non e' una mappa: {via}")

    voci = dati.get("misure")
    if not isinstance(voci, list) or not voci:
        raise ElencoNonValido(f"{via}: «misure» manca o e' vuoto")

    misure: list[Misura] = []
    for posizione, voce in enumerate(voci, start=1):
        dove = f"{via.name} misura #{posizione}"
        if not isinstance(voce, dict):
            raise ElencoNonValido(f"{dove}: non e' una mappa")
        nome = _testo(voce.get("nome"), f"{dove} (nome)")
        misura = Misura(
            indice=posizione,
            nome=nome,
            comando=_testo(voce.get("comando"), f"{dove} ({nome}) comando"),
            descrizione=_testo(voce.get("descrizione"), f"{dove} ({nome}) descrizione"),
            cwd=str(voce.get("cwd") or ".").strip() or ".",
            esito_atteso=_esiti_attesi(voce.get("esito_atteso"), f"{dove} ({nome})"),
            tempo_nell_output=bool(voce.get("tempo_nell_output", False)),
        )
        misure.append(misura)

    nomi = [misura.nome for misura in misure]
    ripetuti = sorted({nome for nome in nomi if nomi.count(nome) > 1})
    if ripetuti:
        raise ElencoNonValido(f"{via.name}: nomi ripetuti: {', '.join(ripetuti)}")

    escluse: list[Esclusa] = []
    for posizione, voce in enumerate(dati.get("escluse") or [], start=1):
        dove = f"{via.name} esclusa #{posizione}"
        if not isinstance(voce, dict):
            raise ElencoNonValido(f"{dove}: non e' una mappa")
        escluse.append(
            Esclusa(
                nome=_testo(voce.get("nome"), f"{dove} (nome)"),
                motivo=_testo(voce.get("motivo"), f"{dove} (motivo)"),
                comando=str(voce.get("comando") or "").strip(),
            )
        )

    return Elenco(
        percorso=via,
        dichiarato=percorso_dichiarato(via),
        impronta=impronta(grezzo),
        titolo=str(dati.get("titolo") or via.stem).strip(),
        descrizione=str(dati.get("descrizione") or "").strip(),
        area=str(dati.get("area") or ".").strip() or ".",
        misure=tuple(misure),
        escluse=tuple(escluse),
    )


def percorso_dichiarato(percorso: Path | str) -> str:
    """Return the list path **as it is written in the attachment**.

    Relativo alla root di autorita' quando ci sta dentro. La ragione e' la
    riproducibilita': `misure.py run tools/misure-liste/x.yaml` e
    `misure.py run /home/luka/Scrivania/AD Projects/tools/misure-liste/x.yaml`
    sono la stessa esecuzione, e devono dare lo stesso testo — non due impronte
    stabili diverse perche' la riga di comando era scritta in un altro modo. Il
    gate `QA` l'ha trovato cosi'.
    """
    relativo = ad_scope.relative_to_root(percorso, ad_docs.DOCS_ROOT)
    return relativo if relativo else str(percorso)


def vieta(comando: str) -> str | None:
    """Return why a command must not run, or None when it passes the deny list.

    Il rifiuto e' **spiegato**: dice la famiglia, il motivo e come riformulare.
    Un rifiuto silenzioso si legge come un guasto, e la prossima volta si aggira.

    E dice anche **cosa non e'**: un'euristica. La prima versione di questo
    strumento prometteva la sola lettura, e il gate `QA` ha trovato dieci forme
    che la smentivano. Quelle forme ora si rifiutano, ma la promessa no: chi legge
    il messaggio deve sapere che la lista e' un elenco di forme note, non una
    garanzia — altrimenti si fida di un controllo che non c'e'.
    """
    for famiglia, schema in VIETATI:
        testo = (
            _fuori_dalle_virgolette(comando)
            if schema.pattern in SOLO_FUORI_VIRGOLETTE
            else comando
        )
        trovato = schema.search(testo)
        if trovato is not None:
            return (
                f"comando rifiutato: «{trovato.group(0).strip()}» appartiene alla famiglia "
                f"«{famiglia}».\n"
                "Le misure osservano, non cambiano: un elenco non puo' contenere un comando "
                "che scrive, sposta, cancella o riscrive la storia (lezione di DEC-0044).\n"
                "Rimedio: se il comando e' di sola lettura, riformulalo senza l'operatore "
                "di scrittura; se serve davvero scrivere, non e' una misura.\n"
                "Nota: questo rifiuto e' un'euristica su forme note, non un sandbox — un "
                "comando che scrive senza somigliare a nessuna delle forme elencate non "
                "viene visto (il testo esteso e' in misure.LIMITE_RIFIUTO)."
            )
    return None


def _fuori_dalle_virgolette(comando: str) -> str:
    """Il comando con le parti fra virgolette sostituite da uno spazio.

    Serve a **una** regola — la redirezione — e la ragione sta scritta sopra
    ``REDIREZIONE``: un `>` dentro una stringa non e' una redirezione, e togliere
    le virgolette a tutte le altre famiglie nasconderebbe `"rm" -rf x`, che `rm`
    lo esegue davvero.
    """
    return re.sub(r"'[^']*'|\"[^\"]*\"", " ", comando)


def _parole(comando: str) -> tuple[str, ...]:
    """Divide il comando in parole, togliendo virgolette e separatori. Superficiale.

    Non e' un parser di shell e non vuole esserlo: serve a trovare i percorsi
    scritti dentro un comando. Una difesa *non* si copia da un altro file
    (`ERR-0026`), ma un separatore di parole non e' una difesa: e' un modo di
    guardare, e sta scritto qui perche' si veda come guarda.
    """
    return tuple(parola for parola in re.split(r"[\s|;&()<>'\"`=]+", comando) if parola)


def fuori_area(misura: Misura, area: Path) -> str | None:
    """Return why a measure would read outside the measurement area, or None.

    Il controllo e' sui **percorsi che si vedono**: la cartella di lavoro
    dichiarata, i percorsi assoluti, e le risalite con `..`. Un percorso
    calcolato dentro il comando non si vede, e questo e' il limite dichiarato in
    testa al file: qui si chiude la porta che si vede, non si promette un
    sandbox.
    """
    base = Path(area) / misura.cwd
    risolta = base.resolve()
    dentro = ad_scope.relative_to_root(risolta, area)
    if dentro is None:
        return (
            f"la cartella di lavoro «{misura.cwd}» esce dall'area di misura "
            f"({risolta} non sta sotto {area}).\n"
            "Una misura legge dove e' dichiarata l'area: un percorso che ne esce "
            "sarebbe una misura su un altro albero, fatta passare per questa."
        )
    if not risolta.is_dir():
        return f"la cartella di lavoro «{misura.cwd}» non esiste ({risolta})."

    for parola in _parole(misura.comando):
        if "/" not in parola or parola.startswith("-"):
            continue
        if parola in DEROGA_FUORI:
            continue
        if parola.startswith("~"):
            return (
                f"percorso «{parola}»: la casa dell'utente non e' un'area di misura. "
                "Un elenco che legge li' non e' riproducibile su un'altra macchina."
            )
        candidato = Path(parola) if parola.startswith("/") else risolta / parola
        if ad_scope.relative_to_root(candidato, area) is None:
            return (
                f"il comando nomina «{parola}», che esce dall'area di misura ({area}).\n"
                "Le misure si fanno dentro l'area dichiarata: fuori, un comando di "
                "lettura e' comunque una misura che nessuno puo' rieseguire."
            )
    return None


def valida(misura: Misura, area: Path) -> str | None:
    """Return why a measure must not run, or None when it may.

    Args:
        misura: La voce dichiarata.
        area: La radice dentro cui la misura legge.

    Returns:
        Il motivo del rifiuto — gia' pronto da mostrare — oppure None.
    """
    return vieta(misura.comando) or fuori_area(misura, area)


def valida_elenco(elenco: Elenco, area: Path) -> list[tuple[Misura, str]]:
    """Return every measure of an elenco that would be refused, with the reason.

    Vuota significa che l'elenco puo' partire. Non vuota significa che non parte
    **niente**: la validazione e' un passo separato e viene prima, perche' un
    elenco e' un atto unico e non si esegue a meta'.
    """
    rifiuti: list[tuple[Misura, str]] = []
    for misura in elenco.misure:
        motivo = valida(misura, area)
        if motivo:
            rifiuti.append((misura, motivo))
    return rifiuti


def area_di(elenco: Elenco, richiesta: Path | str | None = None) -> Path:
    """Return the measurement area, refusing anything outside the authority tree.

    L'area sta **dentro** l'albero di autorita', e non e' configurabile altrove:
    `--area /tmp/x` sarebbe lo stesso varco che `ADMF-004` ha chiuso in
    `ad_scope.guard` — una capacita' che nessuno deve poter attivare, non un
    permesso da concedere.

    Raises:
        AreaNonValida: Se l'area risolta esce dall'albero di autorita'.
    """
    base = Path(richiesta) if richiesta is not None else ad_docs.DOCS_ROOT / elenco.area
    risolta = base.resolve()
    if ad_scope.relative_to_root(risolta, ad_docs.DOCS_ROOT) is None:
        raise AreaNonValida(
            f'l\'area di misura "{risolta}" non sta sotto la root di autorita\' '
            f"({ad_docs.DOCS_ROOT}).\n"
            "Le misure si eseguono dentro l'albero di autorita': fuori, nessun "
            "contract copre niente, e un'area scelta dal chiamante sarebbe il "
            "varco di ERR-0026 riaperto da un'altra porta."
        )
    if not risolta.is_dir():
        raise AreaNonValida(f"l'area di misura non esiste: {risolta}")
    return risolta


def esegui(misura: Misura, area: Path) -> Esito:
    """Esegue una misura in sola lettura e ne registra comando, esito, codice, momento.

    Il momento si prende **prima** del comando: e' il momento in cui la misura
    comincia, ed e' quello che un lettore vuole sapere («quando e' stata presa
    questa misura?»), non quello in cui e' finita.

    Un codice di uscita diverso da zero **non** e' un errore dello strumento: e'
    un esito, e viene riportato com'e'. L'unico caso in cui non c'e' un codice e'
    il comando che non parte — tempo scaduto o esecuzione impossibile — e anche
    li' la voce resta nell'allegato, dichiarata.
    """
    momento = datetime.now().astimezone().isoformat(timespec="seconds")
    cwd = (Path(area) / misura.cwd).resolve()
    try:
        completato = subprocess.run(
            misura.comando,
            shell=True,
            cwd=str(cwd),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=TIMEOUT_SECONDI,
            # Bash e non `sh`: la shell di sistema e' `dash`, e le misure vere
            # usano i cicli e le sostituzioni di processo che il report usava.
            # Dichiararlo qui e' meglio che scoprirlo da un esito strano.
            executable="/bin/bash",
        )
    except subprocess.TimeoutExpired:
        return Esito(
            misura=misura,
            momento=momento,
            codice=None,
            output="",
            righe_output=0,
            eseguita=False,
            errore=f"tempo scaduto dopo {TIMEOUT_SECONDI}s",
        )
    except OSError as errore:
        return Esito(
            misura=misura,
            momento=momento,
            codice=None,
            output="",
            righe_output=0,
            eseguita=False,
            errore=f"esecuzione impossibile: {errore}",
        )

    testo = completato.stdout + completato.stderr
    return Esito(
        misura=misura,
        momento=momento,
        codice=completato.returncode,
        output=testo,
        righe_output=len(testo.splitlines()),
    )


def esegui_elenco(elenco: Elenco, area: Path) -> list[Esito]:
    """Esegue le misure di un elenco, nell'ordine in cui sono dichiarate.

    L'ordine e' quello dell'elenco e non si mescola: due esecuzioni consecutive
    devono dare lo stesso testo, e un ordine che dipende dal filesystem non lo
    garantirebbe.
    """
    return [esegui(misura, area) for misura in elenco.misure]


def _blocco_output(esito: Esito) -> str:
    """Render the output of a measure, declaring any truncation."""
    righe = esito.output.splitlines()
    if not righe:
        return "(nessun output)"
    mostrate = righe[:MAX_RIGHE]
    if len(righe) > MAX_RIGHE:
        omesse = len(righe) - MAX_RIGHE
        mostrate = mostrate + [
            f"[... {omesse} righe non mostrate su {len(righe)}: "
            "l'allegato le dichiara invece di nasconderle ...]"
        ]
    return "\n".join(mostrate)


def _campo_esito(esito: Esito) -> str:
    """Render the outcome line of a measure: executed, with which expected code.

    Il numero di righe di output sta **qui** e non solo nel blocco: e' il modo di
    accorgersi a colpo d'occhio che un comando ha detto molto piu' di quanto
    l'allegato ne mostri, senza doverlo dedurre dal segno di troncamento. Uno
    strumento che risponde meno di quanto sa, senza dirlo, e' il difetto che
    questo allegato esiste per non avere.
    """
    if not esito.eseguita:
        return f"{NON_ESEGUITA} — {esito.errore}"
    attesi = ", ".join(f"`{codice}`" for codice in esito.misura.esito_atteso)
    righe = f"righe di output: {esito.righe_output}"
    if esito.atteso:
        return f"eseguita — codice di uscita `{esito.codice}` (atteso: {attesi}) · {righe}"
    return (
        f"eseguita — codice di uscita `{esito.codice}` **non atteso** "
        f"(atteso: {attesi}) · {righe}: la misura e' riportata lo stesso, col suo codice"
    )


def _chi_ha_il_tempo(elenco: Elenco) -> str:
    """Chi, in questo elenco, dichiara un output che dipende dal tempo.

    Una riga sola, generata dai dati: se domani un'altra misura lo dichiara,
    l'allegato lo dice da solo — e se nessuna lo dichiara, lo dice lo stesso,
    perche' «nessuna» e' un'informazione e il silenzio no.
    """
    dichiarate = [
        f"`{misura.identificatore}` (`{misura.comando.strip().splitlines()[0]}`)"
        for misura in elenco.misure
        if misura.tempo_nell_output
    ]
    if not dichiarate:
        return "nessuna misura di questo elenco lo dichiara"
    return "qui " + ", ".join(dichiarate)


def rendi(elenco: Elenco, esiti: list[Esito], area: Path, impronta_stabile: str) -> str:
    """Genera l'allegato in markdown.

    Args:
        elenco: L'elenco dichiarato.
        esiti: Un esito per misura, nello stesso ordine.
        area: L'area di misura.
        impronta_stabile: L'impronta del testo senza le righe variabili.

    Returns:
        Il documento. Le uniche righe che cambiano fra due esecuzioni sono
        quelle elencate in ``PREFISSI_VARIABILI``.
    """
    eseguite = sum(1 for esito in esiti if esito.eseguita)
    attese = sum(1 for esito in esiti if esito.atteso)
    inattese = eseguite - attese
    momento_esecuzione = esiti[0].momento if esiti else ""
    righe: list[str] = [
        "# Allegato — misure eseguite",
        "",
        "<!-- generato da tools/misure.py: non si scrive a mano, si rigenera -->",
        "",
    ]
    if elenco.descrizione:
        righe += [elenco.descrizione, ""]
    righe += [
        f"## {elenco.titolo}",
        "",
        "| campo | valore |",
        "|---|---|",
        f"| elenco delle misure | `{elenco.dichiarato}` |",
        f"| impronta dell'elenco | `sha256:{elenco.impronta}` |",
        f"| area di misura | `{area}` |",
        f"| esecuzione | `{momento_esecuzione}` |",
        f"| conteggio | {len(esiti)} misure · {eseguite} eseguite · {attese} con "
        f"l'esito atteso · {inattese} inattese |",
        f"| **impronta stabile** | `sha256:{impronta_stabile}` |",
        "",
        "> **Come si legge.** Ogni misura ha quattro campi: il **comando**, l'**esito**,",
        "> il **codice di uscita** e il **momento**. Un codice diverso da quello atteso",
        "> non viene nascosto e non viene tolto: e' la cosa che rende questo allegato",
        "> onesto invece che comodo. Un rapporto che ha bisogno di un numero **cita**",
        "> una misura per nome, e cita questo file per impronta — non per numero di",
        "> riga, perche' una correzione sposta le righe e romperebbe il rimando",
        "> (`DEC-0044`).",
        "",
        "> **Cosa cambia fra due esecuzioni, e cosa no.** Le righe che l'allegato",
        "> dichiara variabili sono quelle che portano un momento — il momento",
        "> dell'esecuzione, quello di ogni misura, e la riga dell'impronta stabile,",
        "> che non puo' contenere se stessa. Tutto il resto e' **stabile a parita' di",
        "> mondo**: se un registro, un file o un conteggio si muove, l'impronta",
        "> cambia, ed e' il punto. Non promette che il numero di oggi sia quello di",
        "> domani: promette che due esecuzioni consecutive senza cambiamenti danno lo",
        "> stesso testo, e che la differenza fra due esecuzioni si legge riga per riga.",
        "",
        "> **L'ora dentro un output: il caso che nessuna maschera toglie.** Un comando",
        f"> puo' **stampare** un valore che dipende dal tempo — {_chi_ha_il_tempo(elenco)}.",
        "> Quelle righe restano nel testo e contano nell'impronta, perche' toglierle",
        "> nasconderebbe anche una **differenza vera** che capita nello stesso output.",
        "> La sezione della misura lo dichiara, e `python3 tools/misure.py confronta",
        "> <a.md> <b.md>` separa le differenze **dichiarate** da quelle **vere**, e le",
        "> mostra entrambe invece di sceglierne una.",
        "",
        "> **Cosa non garantisce.** Che le misure siano quelle giuste: l'allegato dice",
        "> cosa e' stato eseguito, non che l'elenco sia completo. Un elenco e' una",
        "> dichiarazione, e come tutte le dichiarazioni si contesta leggendola.",
        "> E non garantisce nemmeno che i comandi fossero di sola lettura: quello e'",
        "> detto nella sezione qui sotto, dove si vede.",
        "",
        "## Cosa lo strumento rifiuta, e cosa non garantisce",
        "",
        "Questa parte riguarda **le misure stesse**, e sta qui perche' e' qui che si",
        "legge: un limite dichiarato solo nel codice dello strumento non e' un limite",
        "dichiarato, perche' l'artefatto che si cita come prova e' questo file.",
        "",
        "| famiglia rifiutata | forme |",
        "|---|---|",
    ]
    for famiglia, quante in sorted(
        Counter(nome for nome, _ in VIETATI).items()
    ):
        righe.append(f"| {famiglia} | {quante} |")
    righe += [
        "",
        LIMITE_RIFIUTO,
        "",
        "Le forme che questo rifiuto ha **gia' sbagliato** — trovate da un gate che le",
        "ha eseguite su un albero di prova, e da allora chiuse — sono elencate e",
        "provate una per una in `tools/tests/test_ad_org.py`, gruppo `test_misure`.",
        "Un controllo che non sa fallire non e' un controllo: quelle prove ci sono",
        "perche' la lista sia costretta a crescere quando qualcuno trova un buco.",
        "",
        "## Indice",
        "",
        "| # | misura | esito | codice |",
        "|---|---|---|---|",
    ]
    for esito in esiti:
        codice = "—" if esito.codice is None else f"`{esito.codice}`"
        righe.append(f"| {esito.misura.identificatore} | {esito.misura.nome} | "
                     f"{esito.verdetto} | {codice} |")
    righe.append("")

    for esito in esiti:
        misura = esito.misura
        righe += [
            "---",
            "",
            f"### {misura.identificatore} · {misura.nome}",
            "",
            f"**Cosa misura.** {misura.descrizione}",
            "",
        ]
        if misura.tempo_nell_output:
            righe += [
                f"{SEGNO_TEMPO} Dichiarato nell'elenco: questo comando puo' stampare "
                "un valore che dipende dall'ora, quindi fra due esecuzioni la sua "
                "sezione puo' differire **senza che il mondo sia cambiato**. "
                "`confronta` le separa dalle differenze vere e le mostra entrambe: "
                "non si nasconde niente, si distingue.",
                "",
            ]
        if misura.cwd not in (".", ""):
            righe += [f"**Dove.** `{misura.cwd}` (relativo all'area di misura)", ""]
        righe += [
            "**Comando.**",
            "",
            "```console",
            f"$ {misura.comando}",
            "```",
            "",
            f"**Esito.** {_campo_esito(esito)}",
            "",
            "```console",
            _blocco_output(esito),
            "```",
            "",
            f"**Momento.** `{esito.momento}`",
            "",
        ]

    if elenco.escluse:
        righe += [
            "---",
            "",
            "## Misure escluse, e perche'",
            "",
            "Un elenco dice anche cosa **non** contiene. Queste misure non sono qui,",
            "e la ragione e' scritta invece che taciuta: una misura che manca senza",
            "dirlo si legge come una misura che non serviva.",
            "",
            "| misura | perche' non e' qui |",
            "|---|---|",
        ]
        for esclusa in elenco.escluse:
            motivo = " ".join(esclusa.motivo.split())
            righe.append(f"| {esclusa.nome} | {motivo} |")
        righe.append("")
        for esclusa in elenco.escluse:
            if not esclusa.comando:
                continue
            righe += [
                f"**{esclusa.nome}** — il comando che la esprimerebbe:",
                "",
                "```console",
                f"$ {esclusa.comando}",
                "```",
                "",
            ]

    return "\n".join(righe).rstrip() + "\n"


def maschera(testo: str) -> str:
    """Sostituisce i valori variabili con un segno fisso.

    E' **l'unica** definizione di «cosa cambia fra due esecuzioni»: la usano sia
    il calcolo dell'impronta stabile sia `confronta`. Due definizioni
    divergerebbero, e la seconda direbbe una cosa diversa dalla prima — che e'
    esattamente il difetto che `ERR-0026` racconta.
    """
    righe: list[str] = []
    for riga in testo.splitlines():
        if any(riga.startswith(prefisso) for prefisso in PREFISSI_VARIABILI):
            inizio = riga.find("`")
            fine = riga.find("`", inizio + 1) if inizio >= 0 else -1
            if inizio >= 0 and fine > inizio:
                riga = riga[: inizio + 1] + SEGNO_VARIABILE + riga[fine:]
        righe.append(riga)
    return "\n".join(righe) + ("\n" if testo.endswith("\n") else "")


def sezioni_col_tempo(testo: str) -> list[tuple[int, int]]:
    """Gli intervalli di riga (1-based, inclusivi) delle misure dichiarate tempo-dipendenti.

    Si leggono **dal testo**, non dall'elenco: `confronta` lavora su due file, e
    un file deve dire da solo cosa contiene. La sezione di una misura comincia
    con la sua intestazione `### Mnn · …` e finisce all'intestazione successiva.
    """
    righe = testo.splitlines()
    intervalli: list[tuple[int, int]] = []
    inizio: int | None = None
    dichiarata = False
    for numero, riga in enumerate(righe, start=1):
        if riga.startswith("### ") or riga.startswith("## "):
            if inizio is not None and dichiarata:
                intervalli.append((inizio, numero - 1))
            inizio, dichiarata = numero, False
        elif inizio is not None and riga.startswith(SEGNO_TEMPO):
            dichiarata = True
    if inizio is not None and dichiarata:
        intervalli.append((inizio, len(righe)))
    return intervalli


def confronta(primo: str, secondo: str) -> tuple[bool, list[str], list[str]]:
    """Confronta due allegati a meno delle righe variabili, e **classifica** il resto.

    Le differenze si dividono in due, e la distinzione e' il punto:

    - **dichiarate** — cadono dentro la sezione di una misura che ha dichiarato
      un output dipendente dal tempo. Non contano come movimento del mondo, e si
      mostrano lo stesso: nasconderle vorrebbe dire nascondere anche una
      differenza vera che capita nello stesso output.
    - **vere** — tutto il resto. Sono quelle che fanno fallire il confronto.

    Returns:
        ``(nessuna_differenza_vera, differenze_vere, differenze_dichiarate)``.
    """
    mascherato_a = maschera(primo)
    mascherato_b = maschera(secondo)
    a = mascherato_a.splitlines()
    b = mascherato_b.splitlines()
    intervalli = sezioni_col_tempo(mascherato_a) + sezioni_col_tempo(mascherato_b)
    vere: list[str] = []
    dichiarate: list[str] = []
    for numero in range(max(len(a), len(b))):
        riga_a = a[numero] if numero < len(a) else "<manca>"
        riga_b = b[numero] if numero < len(b) else "<manca>"
        if riga_a == riga_b:
            continue
        voce = f"riga {numero + 1}:\n  - {riga_a}\n  + {riga_b}"
        dentro = any(inizio <= numero + 1 <= fine for inizio, fine in intervalli)
        (dichiarate if dentro else vere).append(voce)
    return (not vere), vere, dichiarate


def scrivi(testo: str, percorso: Path | str) -> Path:
    """Scrive l'allegato, dopo aver chiesto il permesso all'autorita' di ambito.

    `ad_scope.guard` sta **qui**, all'unico punto in cui questo strumento tocca
    il disco: la scrittura fatta da uno script non passa dall'euristica della
    shell del plugin, quindi la guardia sta dentro lo strumento (`DEC-0008`, e
    `ERR-0026` per quello che succede quando non c'e').

    Raises:
        PermissionError: Se nessun contract approvato copre il percorso.
    """
    via = Path(percorso)
    ad_scope.guard(via)
    via.parent.mkdir(parents=True, exist_ok=True)
    via.write_text(testo, encoding="utf-8")
    return via


def componi(
    elenco: Elenco, area: Path, esiti: list[Esito]
) -> tuple[str, str, str]:
    """Genera l'allegato e la sua impronta stabile.

    L'impronta si calcola su un testo che **contiene gia' se stessa**: la riga
    dell'impronta e' una delle righe variabili, quindi viene mascherata prima del
    calcolo e il documento non dipende da se' stesso. E' un punto fisso, e un
    test lo verifica invece di darlo per buono.

    Returns:
        ``(testo, impronta_stabile, testo_mascherato)``.
    """
    provvisorio = rendi(elenco, esiti, area, "")
    stabile = maschera(provvisorio)
    return rendi(elenco, esiti, area, impronta(stabile)), impronta(stabile), stabile


def _esegui_comando(args: argparse.Namespace) -> int:
    """`misure.py run`: valida l'elenco, esegue, genera l'allegato."""
    try:
        elenco = carica(args.elenco)
        area = area_di(elenco, args.area)
    except (ElencoNonValido, AreaNonValida) as errore:
        print(f"ERRORE  {errore}", file=sys.stderr)
        return 2

    rifiuti = valida_elenco(elenco, area)
    if rifiuti:
        print(
            "RIFIUTATO  l'elenco contiene comandi che non si eseguono: "
            f"{len(rifiuti)} su {len(elenco.misure)}.\n"
            "Non e' partito niente e non e' stato scritto niente: un elenco e' un atto "
            "unico, e a meta' sarebbe un allegato che sembra completo e non lo e'.\n",
            file=sys.stderr,
        )
        for misura, motivo in rifiuti:
            print(f"{misura.identificatore} · {misura.nome}\n  {motivo}\n", file=sys.stderr)
        return 2

    if args.out is not None:
        # La guardia prima dell'esecuzione, non solo prima della scrittura: trenta
        # comandi lanciati per poi scoprire che l'allegato non si puo' scrivere
        # sarebbero trenta misure dichiarate e nessun posto dove metterle.
        try:
            ad_scope.guard(Path(args.out))
        except PermissionError as errore:
            print(f"ERRORE  {errore}", file=sys.stderr)
            return 2

    esiti = esegui_elenco(elenco, area)
    testo, stabile, _ = componi(elenco, area, esiti)

    eseguite = sum(1 for esito in esiti if esito.eseguita)
    attese = sum(1 for esito in esiti if esito.atteso)
    inattese = [esito for esito in esiti if esito.eseguita and not esito.atteso]
    non_eseguite = [esito for esito in esiti if not esito.eseguita]

    if args.json:
        print(json.dumps({
            "elenco": str(elenco.percorso),
            "area": str(area),
            "misure": len(esiti),
            "eseguite": eseguite,
            "con_esito_atteso": attese,
            "inattese": [esito.misura.identificatore for esito in inattese],
            "non_eseguite": [esito.misura.identificatore for esito in non_eseguite],
            "impronta_stabile": stabile,
            "uscita": str(args.out) if args.out else "",
        }, indent=2, ensure_ascii=False))
    else:
        print(
            f"{elenco.titolo}: {len(esiti)} misure, {eseguite} eseguite, "
            f"{attese} con l'esito atteso, {len(inattese)} inattese."
        )
        print(f"impronta stabile: sha256:{stabile}")
        for esito in inattese:
            print(
                f"  INATTESA  {esito.misura.identificatore} · {esito.misura.nome}: "
                f"codice {esito.codice} (atteso {list(esito.misura.esito_atteso)})"
            )
        for esito in non_eseguite:
            print(f"  NON ESEGUITA  {esito.misura.identificatore} · {esito.errore}")

    if args.out is not None:
        try:
            scritto = scrivi(testo, args.out)
        except PermissionError as errore:
            print(f"ERRORE  {errore}", file=sys.stderr)
            return 2
        print(f"scritto: {scritto}")

    # Un esito inatteso e' un fatto da riportare, non un guasto dello strumento:
    # l'allegato c'e' comunque, e il codice di uscita dice che qualcosa non e'
    # andato come l'elenco dichiarava.
    return 1 if (inattese or non_eseguite) else 0


def _comando_check(args: argparse.Namespace) -> int:
    """`misure.py check`: valida l'elenco senza eseguire niente."""
    try:
        elenco = carica(args.elenco)
        area = area_di(elenco, args.area)
    except (ElencoNonValido, AreaNonValida) as errore:
        print(f"ERRORE  {errore}", file=sys.stderr)
        return 2

    rifiuti = valida_elenco(elenco, area)
    if args.json:
        print(json.dumps({
            "elenco": str(elenco.percorso),
            "area": str(area),
            "misure": len(elenco.misure),
            "escluse": len(elenco.escluse),
            "rifiutate": [
                {"misura": misura.identificatore, "nome": misura.nome, "motivo": motivo}
                for misura, motivo in rifiuti
            ],
            "ok": not rifiuti,
        }, indent=2, ensure_ascii=False))
        return 2 if rifiuti else 0

    if rifiuti:
        print(f"RIFIUTATO  {len(rifiuti)} misure su {len(elenco.misure)} non si eseguono.\n")
        for misura, motivo in rifiuti:
            print(f"{misura.identificatore} · {misura.nome}\n  {motivo}\n")
        return 2
    print(
        f"OK   {elenco.percorso.name}: {len(elenco.misure)} misure eseguibili, "
        f"{len(elenco.escluse)} escluse e dichiarate, area {area}"
    )
    return 0


def _comando_elenca(args: argparse.Namespace) -> int:
    """`misure.py elenca`: cosa contiene un elenco, senza toccare niente."""
    try:
        elenco = carica(args.elenco)
    except ElencoNonValido as errore:
        print(f"ERRORE  {errore}", file=sys.stderr)
        return 2
    print(f"{elenco.titolo}  ({elenco.percorso}, impronta sha256:{elenco.impronta})")
    if elenco.descrizione:
        print(f"  {elenco.descrizione}")
    for misura in elenco.misure:
        print(f"  {misura.identificatore} · {misura.nome}")
    for esclusa in elenco.escluse:
        print(f"  (esclusa) · {esclusa.nome}")
    return 0


def _comando_confronta(args: argparse.Namespace) -> int:
    """`misure.py confronta`: due allegati danno lo stesso testo stabile?"""
    try:
        primo = Path(args.primo).read_text(encoding="utf-8")
        secondo = Path(args.secondo).read_text(encoding="utf-8")
    except OSError as errore:
        print(f"ERRORE  {errore}", file=sys.stderr)
        return 2
    nessuna_vera, vere, dichiarate = confronta(primo, secondo)
    variabili = sum(
        1
        for riga in primo.splitlines()
        if any(riga.startswith(prefisso) for prefisso in PREFISSI_VARIABILI)
    )
    if dichiarate:
        print(
            f"     {len(dichiarate)} righe differiscono dentro misure che dichiarano un output\n"
            "     dipendente dal tempo: si mostrano qui sotto e **non contano come\n"
            "     differenze**. Guardale lo stesso: una differenza VERA dentro lo stesso\n"
            "     output sarebbe classificata come dichiarata — e' il prezzo dichiarato di\n"
            "     non mascherarle."
        )
        for differenza in dichiarate:
            print(f"  (dichiarata) {differenza}")
    if nessuna_vera:
        if dichiarate:
            print(
                "OK   nessuna differenza vera. L'impronta stabile dei due file puo'\n"
                f"     differire per le righe qui sopra: {impronta(maschera(primo))} "
                f"contro {impronta(maschera(secondo))}."
            )
        else:
            print(f"OK   stesso testo stabile: sha256:{impronta(maschera(primo))}")
        print(f"     {variabili} righe dichiarate variabili (momenti e impronta) ignorate.")
        return 0
    print(f"DIVERSI  {len(vere)} righe stabili non coincidono:")
    for differenza in vere:
        print(f"  {differenza}")
    return 1


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Esegue le misure di una verifica e genera l'allegato delle prove"
    )
    sotto = parser.add_subparsers(dest="azione", required=True)

    esecuzione = sotto.add_parser("run", help="esegue l'elenco e genera l'allegato")
    esecuzione.add_argument("elenco", help="file YAML delle misure dichiarate")
    esecuzione.add_argument("--out", help="dove scrivere l'allegato in markdown")
    esecuzione.add_argument("--area", help="area di misura (default: quella dell'elenco)")
    esecuzione.add_argument("--json", action="store_true", help="riassunto in JSON")

    controllo = sotto.add_parser("check", help="valida l'elenco senza eseguire niente")
    controllo.add_argument("elenco", help="file YAML delle misure dichiarate")
    controllo.add_argument("--area", help="area di misura (default: quella dell'elenco)")
    controllo.add_argument("--json", action="store_true", help="esito in JSON")

    lettura = sotto.add_parser("elenca", help="mostra le misure di un elenco")
    lettura.add_argument("elenco", help="file YAML delle misure dichiarate")

    confronto = sotto.add_parser("confronta", help="due allegati a meno dei momenti")
    confronto.add_argument("primo", help="primo allegato")
    confronto.add_argument("secondo", help="secondo allegato")

    args = parser.parse_args(argv)
    if args.azione == "run":
        return _esegui_comando(args)
    if args.azione == "check":
        return _comando_check(args)
    if args.azione == "elenca":
        return _comando_elenca(args)
    return _comando_confronta(args)


if __name__ == "__main__":
    raise SystemExit(main())
