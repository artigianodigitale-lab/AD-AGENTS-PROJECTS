"""Coerenza del livello sempre caricato.

Il livello che ogni agente legge all'avvio e' `.brain/COSTITUZIONE.md`
(symlinkato da `~/.dsh/AGENTS.md`). Descrive il sistema: quali skill esistono,
quali comandi, quali cartelle, quale sequenza seguire. **Se la descrizione
diverge dal sistema, l'agente segue la descrizione.**

Non e' un rischio teorico. Il 2026-10-08 la costituzione elencava 10 passi e la
skill `ad-kickoff` ne elencava 12: il sistema milestone e' rimasto inutilizzato
per una giornata intera. E `ad-milestone` non era nominata fra le skill, quindi
per un agente nuovo non esisteva.

L'elenco dei comandi **non** sta nella costituzione: sta in `tools/README.md`, che
e' il registro. La costituzione lo cita, e nomina solo i comandi che sono un passo
della sequenza. Elenco e procedura sono due cose diverse, e distinguerle e' il
senso di ADMF-008:

* l'**elenco** e' «tutti i comandi che esistono». Cresce a ogni strumento nuovo, e
  per questo vive accanto al codice che descrive — un file che si tocca quando si
  tocca quel codice, non il documento che ogni agente legge a ogni avvio;
* la **procedura** e' «i pochi comandi che sono un passo obbligato». Cambia solo
  quando cambia la sequenza, ed e' l'unica parte che ha senso nella costituzione.

Finche' le due cose stavano insieme, aggiungere uno strumento voleva dire due
scritture a mano in un documento di governance (costituzione e vocabolario), e
nessun controllo se ne accorgeva: una riga sbagliata nella costituzione non la
prendeva nessuno.

Questo modulo confronta la descrizione con la realta'. Non giudica la qualita'
di nessuna delle due: trova solo le divergenze.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import ad_docs

COSTITUZIONE = ".brain/COSTITUZIONE.md"
KICKOFF = ".brain/skills/ad-kickoff/SKILL.md"
SKILLS_DIR = ".brain/skills"
TOOLS_DIR = "tools"
#: Il registro dei comandi: l'unico posto in cui un comando e' **dichiarato**, con
#: il suo nome, cosa fa in parole comprensibili e la forma d'uso.
#:
#: Sta fuori da `.brain/` di proposito. La costituzione e' il livello che ogni
#: agente legge a ogni avvio: qualunque riga ci finisca la pagano tutti, a ogni
#: sessione, e un elenco che cresce a ogni strumento e' il candidato peggiore per
#: quel posto. Qui invece l'elenco vive con il codice che descrive.
REGISTRO = "tools/README.md"
PLUGIN = ".brain/plugin/enforce-contract/index.mjs"
GLOSSARIO = ".brain/GLOSSARIO.md"

#: I due registri della societa': contract e marcatori di approvazione.
REGISTRI: tuple[str, ...] = ("contratti", "approvazioni")

#: Dove stanno i record che dichiarano un orario, e che quindi si controllano.
RECORD_ORARIO: tuple[str, ...] = ("approvazioni", "contratti", "evidenze")

#: I campi che registrano **quando e' successo qualcosa**, non quando scadra'.
#:
#: `expires` e' escluso di proposito: una scadenza **deve** essere nel futuro.
#: La prima versione di questo controllo non lo escludeva e segnalava tutti i
#: permessi attivi come se fossero falsi.
CAMPI_ORARIO: tuple[str, ...] = ("data", "timestamp", "aperta", "chiusa", "chiuso")

ORARIO_RE = re.compile(
    r"^(?:" + "|".join(CAMPI_ORARIO) + r"):\s*\"?(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})",
    re.M,
)
SOCIETA = "societa"

GANCIO_ISTRUZIONI = Path.home() / ".dsh" / "AGENTS.md"
GANCIO_SKILL = Path.home() / ".agents" / "skills"
PATCH_PROFILO = Path.home() / ".dsh" / "profiles" / "web" / "cordis.patch.yml"

#: Una skill: `ad-` seguito da lettere minuscole e trattini.
SKILL_RE = re.compile(r"\bad-[a-z][a-z-]*[a-z]\b")
#: Il nome di un comando: lettere, cifre e underscore. Le **cifre** servono: la
#: prima versione di questo schema le escludeva, e `tools/prova_p0.py` — il comando
#: di prova di ADMF-008 — risultava non dichiarato anche con la sua riga nel
#: registro. L'ha preso la prova che rimette il difetto, non il ragionamento.
COMANDO_RE = re.compile(r"\btools/([a-z0-9_]+\.py)\b")
CARTELLA_RE = re.compile(r"`([A-Za-z][A-Za-z0-9._-]*)/`")
#: Un passo della sequenza: numero, etichetta in maiuscolo, descrizione.
#:
#: L'etichetta finisce dove comincia la descrizione — due o piu' spazi, oppure un
#: solo spazio seguito da minuscola. Pretendere **sempre** due spazi faceva
#: sparire il passo ``6 ANALISI DI AVVIO cosa serve``, che ne ha uno solo, e con
#: esso spariva la possibilita' di accorgersi di una divergenza su quel passo:
#: il confronto passava a vuoto. Vedi anche ``sequenza()``, che ora verifica la
#: contiguita' della numerazione.
PASSO_RE = re.compile(
    r"^\s*(\d{1,2})\s+([A-ZÀ-Ù][A-ZÀ-Ù ]*?)(?=\s{2,}|\s+[a-z])", re.M
)
DOC_RE = re.compile(r"`([A-Z][A-Z0-9-]*\.md)`")

#: L'idioma che rende un file un comando. Si cerca la riga, non la sottostringa:
#: cercare ``"__main__" in testo`` fa rilevare come comando anche *questo* file,
#: che quella stringa la contiene nel proprio codice di rilevamento. E' successo
#: alla prima esecuzione.
MAIN_RE = re.compile(r'^if __name__ == "__main__":', re.M)

#: Una riga del registro: ``| `nome.py` | cosa fa | come si usa |``.
#:
#: Si legge la **riga** e non la sottostringa. Un comando e' dichiarato quando ha
#: una riga di tabella che comincia col suo nome fra backtick; cercare il nome
#: ovunque nel file farebbe passare per dichiarazione una semplice citazione — ed e'
#: il modo in cui un elenco si riempie di voci che nessuno mantiene.
REGISTRO_RIGA_RE = re.compile(r"^\|\s*`([a-z0-9_]+\.py)`\s*\|([^|]*)\|([^|]*)\|\s*$", re.M)

#: Una riga che **dichiara** un comando: la prima cella e' il nome fra backtick.
#:
#: Piu' larga di `REGISTRO_RIGA_RE`, di proposito: serve a riconoscere una
#: dichiarazione anche quando la tabella ha un'altra forma — il vocabolario ne usava
#: una a due colonne. Il difetto da prendere e' l'elenco in **due** posti, non la
#: forma della tabella: se una skill si inventasse un terzo formato, la riga
#: resterebbe una dichiarazione e va vista lo stesso.
DICHIARAZIONE_RE = re.compile(r"^\|\s*`([a-z0-9_]+\.py)`\s*\|", re.M)

#: Quanto deve essere lunga, come minimo, la descrizione di un comando.
#:
#: Non e' un giudizio sulla chiarezza — quella non si misura. E' il minimo perche'
#: una descrizione **esista**: senza, la tabella si riempie di nomi, la colonna
#: resta vuota e il registro torna a essere illeggibile proprio per chi non legge
#: il codice (invariante 14).
DESCRIZIONE_MINIMA = 25


def _testo(percorso: Path) -> str:
    """Return the text of a file, or an empty string if unreadable."""
    try:
        return percorso.read_text(encoding="utf-8")
    except OSError:
        return ""


def skills_nel_cervello(root: Path | str | None = None) -> set[str]:
    """Return the skill directories that exist."""
    base = Path(root) if root is not None else ad_docs.DOCS_ROOT
    cartella = base / SKILLS_DIR
    if not cartella.is_dir():
        return set()
    return {voce.name for voce in cartella.iterdir() if voce.is_dir() and voce.name.startswith("ad-")}


def skills_nominate(testo: str) -> set[str]:
    """Return the skill names mentioned in a text."""
    return set(SKILL_RE.findall(testo))


def comandi_nel_progetto(root: Path | str | None = None) -> set[str]:
    """Return the command-line tools that exist, ignoring the libraries.

    Le librerie (`ad_*.py`) non vanno documentate: sono moduli che altri
    importano. I comandi (`*_*.py` con un `if __name__`) si'. Confondere le due
    categorie produce un conteggio che sembra un problema e non lo e'.
    """
    base = Path(root) if root is not None else ad_docs.DOCS_ROOT
    cartella = base / TOOLS_DIR
    if not cartella.is_dir():
        return set()
    return {
        voce.name
        for voce in cartella.glob("*.py")
        if MAIN_RE.search(_testo(voce))
    }


def comandi_nominati(testo: str) -> set[str]:
    """Return the tool file names mentioned in a text."""
    return set(COMANDO_RE.findall(testo))


def comandi_nel_registro(testo: str) -> dict[str, tuple[str, str]]:
    """Return the commands declared in the registry: name -> (description, usage)."""
    dichiarati: dict[str, tuple[str, str]] = {}
    for nome, descrizione, uso in REGISTRO_RIGA_RE.findall(testo):
        dichiarati[nome] = (" ".join(descrizione.split()), " ".join(uso.split()))
    return dichiarati


def problemi_del_registro(base: Path, registro: str) -> list[str]:
    """Il registro e i comandi che esistono devono dire la stessa cosa.

    Quattro divergenze, e ognuna e' un modo in cui un elenco puo' mentire:

    * un comando che esiste e **non e' dichiarato** — per chi legge il registro non
      esiste. E' il caso da cui e' nato ADMF-008: `tools/misure.py` c'era, e
      l'elenco no;
    * una riga che **nomina un comando che non c'e' piu'** — quando un comando
      cambia nome il registro resta indietro, ed e' lo stesso difetto nel verso
      opposto;
    * una **descrizione vuota** o piu' corta di un segnaposto: la colonna si riempie
      di nomi e il registro smette di servire a chi non legge il codice
      (invariante 14);
    * una **forma d'uso che non nomina il comando** — copiata dalla riga sopra,
      insegna a lanciare la cosa sbagliata.

    Il limite, dichiarato: **la chiarezza di una descrizione non si misura.** Qui si
    controlla che ci sia e che non sia un segnaposto; che sia in parole
    comprensibili lo giudica chi legge, non questo modulo. Un controllo che
    pretendesse di giudicare la chiarezza sarebbe un controllo che non puo'
    fallire — e quindi nessun controllo.
    """
    fuori: list[str] = []
    dichiarati = comandi_nel_registro(registro)

    for comando in sorted(comandi_nel_progetto(base) - set(dichiarati)):
        fuori.append(
            f"il comando tools/{comando} esiste ma non e' dichiarato in {REGISTRO}: "
            "per chi legge il registro non esiste"
        )
    for comando in sorted(comandi_nominati(registro)):
        if not (base / TOOLS_DIR / comando).is_file():
            fuori.append(f"il registro {REGISTRO} nomina tools/{comando}, che non esiste")
    for comando, (descrizione, uso) in sorted(dichiarati.items()):
        if len(descrizione) < DESCRIZIONE_MINIMA or len(descrizione.split()) < 3:
            fuori.append(
                f"{REGISTRO}: la riga di {comando} non dice cosa fa, in parole "
                f"comprensibili (invariante 14): «{descrizione}»"
            )
        if f"{TOOLS_DIR}/{comando}" not in uso:
            fuori.append(
                f"{REGISTRO}: la forma d'uso di {comando} non lo nomina: «{uso}»"
            )
    return fuori


def elenchi_duplicati(base: Path) -> list[str]:
    """Nessun documento del cervello deve ridichiarare l'elenco dei comandi.

    L'elenco vive in `tools/README.md`, e in un posto solo: se il vocabolario — o la
    costituzione, o una skill — tiene la sua copia, le due copie divergono, ed e'
    esattamente il difetto che ADMF-008 toglie. Il vocabolario resta il posto delle
    **parole** (cosa significa «gate», come si dice «sprint» al CEO); il registro e'
    il posto dei **comandi**.

    La forma della dichiarazione e' la riga di tabella: citare un comando dentro una
    frase non e' ridichiararlo, e resta permesso — la costituzione *deve* poter
    nominare i comandi che sono un passo della sequenza.
    """
    fuori: list[str] = []
    percorsi = sorted(base.glob(".brain/**/*.md"))
    costituzione = base / COSTITUZIONE
    if costituzione.is_file() and costituzione not in percorsi:
        percorsi.append(costituzione)
    for percorso in percorsi:
        for nome in DICHIARAZIONE_RE.findall(_testo(percorso)):
            if (base / TOOLS_DIR / nome).is_file():
                fuori.append(
                    f"{percorso.relative_to(base)} ridichiara il comando {nome}: "
                    f"l'elenco dei comandi sta in {REGISTRO}, e in un posto solo"
                )
    return fuori


def cartelle_nominate(testo: str) -> set[str]:
    """Return the folder names written as ``nome/`` in backticks."""
    return set(CARTELLA_RE.findall(testo))


def documenti_nella_root(root: Path | str | None = None) -> set[str]:
    """Return the normative documents of the root."""
    base = Path(root) if root is not None else ad_docs.DOCS_ROOT
    return {voce.name for voce in base.glob("*.md")}


def documenti_nominati(testo: str) -> set[str]:
    """Return the document names mentioned in a text."""
    return set(DOC_RE.findall(testo))


def sequenza(testo: str) -> dict[int, str]:
    """Return the numbered steps of the first ``text`` block, as number -> label."""
    blocco = re.search(r"```text\n(.*?)```", testo, re.S)
    if blocco is None:
        return {}
    passi: dict[int, str] = {}
    for numero, etichetta in PASSO_RE.findall(blocco.group(1)):
        passi[int(numero)] = " ".join(etichetta.split()).upper()
    return passi


def ganci() -> list[str]:
    """Return the problems of the global hooks that point into the brain."""
    problemi: list[str] = []
    if not GANCIO_ISTRUZIONI.exists():
        problemi.append(f"manca il gancio delle istruzioni: {GANCIO_ISTRUZIONI}")
    elif GANCIO_ISTRUZIONI.resolve().name != Path(COSTITUZIONE).name:
        problemi.append(
            f"{GANCIO_ISTRUZIONI} punta a {GANCIO_ISTRUZIONI.resolve()}, "
            f"non a {COSTITUZIONE}"
        )
    if not GANCIO_SKILL.is_dir():
        problemi.append(f"manca la cartella delle skill globali: {GANCIO_SKILL}")
        return problemi
    for voce in sorted(GANCIO_SKILL.glob("ad-*")):
        if voce.is_symlink() and not voce.resolve().is_dir():
            problemi.append(f"{voce} punta a una destinazione inesistente")
    return problemi


def _slug(nome: str) -> str:
    """Il nome breve con cui si raggruppa un progetto nel registro."""
    return re.sub(r"[^a-z0-9]+", "-", nome.lower()).strip("-")


def _gruppo_atteso(prefissi) -> str:
    """In quale cartella del registro va questo contract."""
    for prefisso in prefissi or []:
        testa = str(prefisso).strip().strip('"').split("/", 1)[0]
        if re.match(r"^\d+\.", testa):
            return _slug(testa)
    return SOCIETA


def registro_problemi(base: Path) -> list[str]:
    """Ogni contract e ogni marcatore nel gruppo giusto?

    Il registro e' raggruppato per progetto: mescolare le lavorazioni di progetti
    diversi nella stessa cartella e' cio' che il CEO ha chiesto di evitare. Il
    caricatore e' ricorsivo e funziona comunque — questo controllo rende visibile
    cio' che altrimenti sarebbe solo disordine.
    """
    import yaml

    attesi: dict[str, str] = {}
    for percorso in (base / "contratti").rglob("*.yaml"):
        if percorso.name.startswith("_"):
            continue
        try:
            dati = yaml.safe_load(percorso.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        attesi[str(dati.get("task_id", percorso.stem))] = _gruppo_atteso(dati.get("write_scope"))

    fuori: list[str] = []
    for registro in REGISTRI:
        cartella = base / registro
        if not cartella.is_dir():
            continue
        for percorso in sorted(cartella.rglob("*.yaml")):
            if percorso.name.startswith("_"):
                continue
            atteso = attesi.get(percorso.stem, SOCIETA)
            if percorso.parent != cartella / atteso:
                fuori.append(
                    f"{registro}/{percorso.relative_to(cartella)} non e' raggruppato: "
                    f"va in {registro}/{atteso}/"
                )
        for sciolto in sorted(cartella.glob("*.yaml")):
            if not sciolto.name.startswith("_"):
                fuori.append(
                    f"{registro}/{sciolto.name} e' fuori da ogni gruppo: "
                    f"va in {registro}/<progetto>/ o {registro}/{SOCIETA}/"
                )
    return fuori

def orari_nel_futuro(base: Path, adesso: "datetime | None" = None) -> list[str]:
    """Un record non puo' dichiarare un orario che non e' ancora arrivato.

    Perche' e' un controllo e non una raccomandazione: il 2026-10-08 **ogni**
    prova e **ogni** marcatore scritti quel giorno dichiaravano un orario nel
    futuro rispetto al momento in cui il file era stato scritto — da 20 minuti
    a un'ora e mezza. Nessuno se n'era accorto, perche' nessuno confrontava le
    date dichiarate con l'orologio.

    Un registro di governo in cui le date sono inventate non ordina piu' niente:
    serve a ricostruire chi ha deciso cosa, e quando. L'orario dichiarato non e'
    verificabile contro l'evento, ma **non puo' essere nel futuro** — e questo si
    controlla sempre.
    """
    quando = adesso or datetime.now().astimezone()
    fuori: list[str] = []
    for cartella in RECORD_ORARIO:
        radice = base / cartella
        if not radice.is_dir():
            continue
        for percorso in sorted(radice.rglob("*.yaml")):
            if percorso.name.startswith("_"):
                continue
            try:
                testo = percorso.read_text(encoding="utf-8")
            except OSError:
                continue
            for a, m, g, o, mi, s in ORARIO_RE.findall(testo):
                dichiarato = datetime(
                    int(a), int(m), int(g), int(o), int(mi), int(s),
                    tzinfo=quando.tzinfo,
                )
                if dichiarato > quando:
                    fuori.append(
                        f"{percorso.relative_to(base)} dichiara "
                        f"{dichiarato.isoformat(timespec='seconds')}, che non e' "
                        f"ancora arrivato (adesso e' {quando.isoformat(timespec='seconds')})"
                    )
                    break
    return fuori

#: I conteggi delle card dichiarati nei documenti, e come riconoscerli.
#:
#: Perche' e' un controllo: il 2026-10-10 ho aggiunto due schede e il numero e' rimasto
#: vecchio in SEI posti — costituzione, tre skill, il vocabolario. Nessun controllo lo
#: leggeva. Un conteggio vecchio non fa male da solo, ma e' una bugia in un documento che
#: serve a orientarsi, ed e' esattamente la classe di errore che ci costa di piu'.
CONTEGGI_RE = (
    (re.compile(r"(\d+)\s+card tecniche"), "tecniche"),
    (re.compile(r"(\d+)\s+card business"), "business"),
    (re.compile(r"Business\s*\((\d+)\)"), "business"),
    (re.compile(r"(\d+)\s+specialisti"), "specialisti"),
    (re.compile(r"Tutte le \*\*(\d+) card"), "totale"),
)


def conteggi_delle_card(base: Path) -> list[str]:
    """I numeri dichiarati nei documenti corrispondono al registry?"""
    import ad_registry  # noqa: PLC0415

    # NON si inghiotte l'errore. La prima versione di questo controllo faceva
    # `except Exception: return []` — e `ad_registry.load()` non accetta argomenti,
    # quindi sollevava, e il controllo **non controllava niente in silenzio**.
    # Un controllo che non puo' fallire e' peggio di nessun controllo: sembra una
    # difesa. Se il registry non si legge, e' un problema da dire, non da nascondere.
    try:
        # `load()` restituisce un DIZIONARIO id -> card, non una lista. La prima
        # versione iterava le chiavi e contava zero di tutto: un altro modo di non
        # controllare niente senza dirlo.
        registro = ad_registry.load()
    except Exception as errore:
        return [f"il registry delle card non si legge: {type(errore).__name__}: {errore}"]
    # Le stesse funzioni che usa `cards.py check`: il conteggio dev'essere UNO solo,
    # altrimenti il documento e lo strumento possono dire due numeri diversi.
    vere = {
        "tecniche": len(ad_registry.by_domain(registro, "technical")),
        "business": len(ad_registry.by_domain(registro, "business")),
        "totale": len(registro),
    }
    vere["specialisti"] = vere["business"] - 1  # l'orchestratore non e' uno specialista

    fuori: list[str] = []
    for percorso in sorted(base.glob(".brain/**/*.md")) + [base / ".brain" / "COSTITUZIONE.md"]:
        if not percorso.is_file():
            continue
        try:
            testo = percorso.read_text(encoding="utf-8")
        except OSError:
            continue
        for schema, chiave in CONTEGGI_RE:
            for trovato in schema.finditer(testo):
                dichiarato = int(trovato.group(1))
                if chiave in vere and dichiarato != vere[chiave]:
                    fuori.append(
                        f"{percorso.relative_to(base)}: dichiara {dichiarato} card "
                        f"{chiave}, il registry ne ha {vere[chiave]}"
                    )
    return fuori

#: I documenti di root che **non sono normativi**: porte e spiegazioni.
#:
#: Perche' esistono: il 2026-10-13 la versione vergine ha aggiunto `README.md` (una
#: distribuzione senza README non si sa usare) e `GRAFO.md` (come funziona il motore).
#: Il controllo li trattava come documenti normativi e pretendeva che la costituzione li
#: nominasse — ma **non sono regole**: sono la porta e la spiegazione. Il problema
#: cresceva a ogni documento nuovo, il che e' il segno che la domanda era sbagliata.
#:
#: **Elenco dichiarato**, non dedotto: dedurlo («quelli che non sembrano regole»)
#: vorrebbe dire accettare come non-normativo qualunque cosa qualcuno aggiunga.
#:
#: **Il prezzo, dichiarato**: ogni documento non normativo nuovo vuole una riga qui.
#: E' attrito, ed e' voluto — il controllo ha preso `DOCUMENTAZIONE-TECNICA.md`
#: un minuto dopo che l'ho creato. Un elenco che cresce a mano e' meglio di una
#: regola che accetta tutto, ma e' un attrito che va visto, non subito in silenzio.
DOCUMENTI_NON_NORMATIVI = frozenset({"README.md", "GRAFO.md", "DOCUMENTAZIONE-TECNICA.md", "FORMATO.md", "CONTRIBUTING.md", "README.it.md"})


def problemi(root: Path | str | None = None) -> list[str]:
    """Return every divergence between the always-loaded layer and reality.

    Args:
        root: Root of AD Projects (default: the root of this checkout).

    Returns:
        One message per divergence. An empty list means the layer is coherent.
    """
    base = Path(root) if root is not None else ad_docs.DOCS_ROOT
    testo = _testo(base / COSTITUZIONE)
    if not testo:
        return [f"costituzione illeggibile: {COSTITUZIONE}"]

    fuori: list[str] = []

    # --- skill -------------------------------------------------------------
    nel_cervello = skills_nel_cervello(base)
    nominate = skills_nominate(testo)
    for skill in sorted(nel_cervello - nominate):
        fuori.append(
            f"skill '{skill}' esiste in {SKILLS_DIR}/ ma non e' nominata nella costituzione: "
            "per un agente nuovo non esiste"
        )
    for skill in sorted(nominate - nel_cervello):
        fuori.append(f"la costituzione nomina la skill '{skill}', che non esiste")

    # --- comandi: l'elenco nel registro, la procedura nella costituzione ---
    #
    # Prima si pretendeva che ogni comando fosse nominato *qui*. Per aggiungere
    # `tools/misure.py` bisognava scrivere in due documenti di governance —
    # costituzione e vocabolario — e il controllo tornava verde solo perche' quelle
    # due righe erano state scritte a mano: l'elenco non era verificato, era
    # ricopiato. Ora la pretesa e' girata al registro.
    #
    # La costituzione **cita** il registro e puo' nominare i comandi che sono un
    # passo della sequenza (passi 4, 6, 9, 10, 12: `cards.py match`,
    # `blueprint.py render`, `milestone.py new-milestone` e `new-sprint`,
    # `stato.py render`). Quelli sono **procedura**: chi apre un lavoro deve
    # trovarli li', non in un file che deve sapere di aprire.
    if REGISTRO not in testo:
        fuori.append(
            f"la costituzione non cita il registro {REGISTRO}: l'elenco dei comandi "
            "resterebbe senza un posto dichiarato"
        )
    for comando in sorted(comandi_nominati(testo)):
        if not (base / TOOLS_DIR / comando).is_file():
            fuori.append(f"la costituzione cita tools/{comando}, che non esiste")
    registro = _testo(base / REGISTRO)
    if not registro:
        fuori.append(f"manca il registro dei comandi: {REGISTRO}")
    fuori.extend(problemi_del_registro(base, registro))
    fuori.extend(elenchi_duplicati(base))

    # --- cartelle ----------------------------------------------------------
    # Solo quelle della mappa della root: altrove la costituzione nomina cartelle
    # che vivono DENTRO i progetti (`Analisi-Prompt-Report/`), e pretendere di
    # trovarle qui sarebbe un falso allarme. Il controllo guarda la mappa, che e'
    # per definizione l'elenco di cosa sta nella root.
    mappa = ""
    if "## Dove sta cosa" in testo:
        mappa = testo.split("## Dove sta cosa", 1)[1].split("\n## ", 1)[0]
    for cartella in sorted(cartelle_nominate(mappa)):
        if not (base / cartella).exists():
            fuori.append(f"la costituzione nomina la cartella '{cartella}/', che non esiste")

    # --- documenti normativi ----------------------------------------------
    documenti = documenti_nella_root(base)
    elencati = documenti_nominati(testo)
    for documento in sorted(documenti - elencati - DOCUMENTI_NON_NORMATIVI):
        fuori.append(f"il documento di root '{documento}' non e' nominato nella costituzione")

    # --- sequenza: la costituzione contro la skill d'ingresso -------------
    costituzione = sequenza(testo)
    skill = sequenza(_testo(base / KICKOFF))
    if costituzione and skill:
        # La numerazione deve essere contigua: un buco significa che il documento
        # salta un passo, oppure che il parser non lo riconosce. In entrambi i casi
        # il confronto non e' affidabile, e va detto invece di passare a vuoto.
        for nome, passi in (("costituzione", costituzione), ("ad-kickoff", skill)):
            attesi = set(range(1, len(passi) + 1))
            if set(passi) != attesi:
                fuori.append(
                    f"la sequenza di {nome} non e' contigua: trovati {sorted(passi)}, "
                    f"attesi {sorted(attesi)} — o manca un passo, o il parser non lo vede"
                )
        if set(costituzione) != set(skill):
            fuori.append(
                "la sequenza della costituzione e quella di ad-kickoff hanno passi diversi: "
                f"{sorted(costituzione)} contro {sorted(skill)}"
            )
        else:
            for numero in sorted(costituzione):
                if costituzione[numero] != skill[numero]:
                    fuori.append(
                        f"passo {numero} incoerente: la costituzione dice "
                        f"'{costituzione[numero]}', ad-kickoff dice '{skill[numero]}'"
                    )

    # --- glossario: si sa spiegare tutto al CEO? (invariante 14) ----------
    #
    # I **comandi** non si controllano piu' qui. La loro descrizione in parole
    # comprensibili vive nel registro, accanto al comando, ed e' li' che viene
    # verificata: pretendere il nome anche nel vocabolario rimetterebbe l'elenco in
    # due posti, che e' il difetto tolto da ADMF-008. Che il vocabolario non tenga
    # una copia lo controlla `elenchi_duplicati()`.
    #
    # Le **cartelle** restano: il vocabolario spiega anche dove stanno le cose, e
    # una cartella che compare nella costituzione senza una traduzione per il CEO e'
    # una parola che lui non puo' leggere.
    glossario = _testo(base / GLOSSARIO)
    if not glossario:
        fuori.append(
            f"manca il vocabolario in parole semplici: {GLOSSARIO} (invariante 14)"
        )
    else:
        for cartella in sorted(cartelle_nominate(testo)):
            if cartella not in glossario:
                fuori.append(
                    f"'{cartella}/' e' nominata nella costituzione ma non compare in "
                    f"{GLOSSARIO}: non c'e' modo di spiegarla al CEO in parole semplici"
                )

    # --- registro raggruppato per progetto ---------------------------------
    fuori.extend(registro_problemi(base))

    # --- nessun orario nel futuro ------------------------------------------
    fuori.extend(orari_nel_futuro(base))

    # --- i conteggi delle card --------------------------------------------
    fuori.extend(conteggi_delle_card(base))

    # --- ganci e plugin ----------------------------------------------------
    fuori.extend(ganci())
    if not (base / PLUGIN).is_file():
        fuori.append(f"il plugin di enforcement non esiste: {PLUGIN}")
    else:
        patch = _testo(PATCH_PROFILO)
        if patch and str(base / PLUGIN) not in patch:
            fuori.append(f"il plugin non risulta montato in {PATCH_PROFILO}")

    return fuori
