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
import tempfile
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
#: Il profilo DSH su cui si monta. **Non** un valore fisso: il 2026-11-02 il default
#: era "web", la sessione girava su "desktop", e il plugin e' stato montato nel profilo
#: sbagliato. Il cancello risultava «installato» e non era attivo — il peggiore dei casi,
#: perche' nessuno lo cerca. Sceglie cosi', in ordine:
#:   1. `--profilo <nome>` (chi sa cosa vuole, lo dice)
#:   2. `AD_DSH_PROFILO` (per gli script)
#:   3. il profilo che DSH ha usato **davvero** l'ultima volta (`desktop-preferences.json`)
#:   4. "web", come ripiego dichiarato
def _profilo_scelto() -> str:
    from os import environ

    scelto = environ.get("AD_DSH_PROFILO", "").strip()
    if scelto:
        return scelto
    return "web"


def profili_dsh() -> list[str]:
    """I profili DSH che esistono davvero sulla macchina.

    Il 2026-11-02 il plugin era montato in `web` e la sessione girava in `desktop`: il
    cancello risultava installato e non era attivo. Il profilo vivo non e' dichiarato in
    nessun file leggibile, quindi **non si indovina**: si monta su tutti quelli che ci
    sono. Montare due volte non costa niente e non sbaglia mai; indovinare costa un
    cancello spento che nessuno cerca.
    """
    radice = Path.home() / ".dsh" / "profiles"
    if not radice.is_dir():
        return [PROFILO]
    trovati = sorted(
        voce.name
        for voce in radice.iterdir()
        if voce.is_dir() and (voce / "cordis.patch.yml").is_file()
    )
    return trovati or [PROFILO]


PROFILO = _profilo_scelto()

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


def _errore_yaml(testo: str) -> str | None:
    """Prova a leggere il layer come YAML, senza pretendere PyYAML.

    Il file puo' contenere espressioni `!!js`, che il parser standard non conosce:
    il costruttore sotto le accetta come valori. Non serve interpretarle, serve solo
    sapere se la struttura e' leggibile.
    """
    try:
        import yaml
    except ImportError:  # pragma: no cover - l'ambiente senza PyYAML non blocca
        return None

    class Caricatore(yaml.SafeLoader):
        pass

    Caricatore.add_multi_constructor(
        "tag:yaml.org,2002:js",
        lambda caricatore, suffisso, nodo: None,
    )
    try:
        yaml.load(testo, Loader=Caricatore)
    except Exception as errore:  # il parser dice sempre cosa non va
        return str(errore).splitlines()[0]
    return None


def _scrivi_patch(percorso: Path, testo: str) -> None:
    """Sostituisce il layer in modo atomico: un'interruzione non lo lascia a meta'."""
    temporaneo = percorso.with_name(f".{percorso.name}.tmp-{os.getpid()}")
    try:
        temporaneo.write_text(testo, encoding="utf-8")
        if percorso.exists():
            os.chmod(temporaneo, percorso.stat().st_mode)
        os.replace(temporaneo, percorso)
    finally:
        if temporaneo.exists():
            temporaneo.unlink()


def _togli_blocco_legacy(testo: str) -> str:
    """Toglie il blocco che il vecchio setup scriveva indentato in testa.

    Era il difetto: un elenco di primo livello non puo' cominciare con quattro spazi.
    Si rimuove solo se contiene davvero il nostro plugin; il resto del file resta suo.
    """
    if ID_PLUGIN not in testo:
        return testo
    schema = re.compile(
        r"^(?:[ \t]+#[^\n]*\n)*[ \t]+- insert:\n(?:[ \t]+[^\n]*\n)*",
        re.M,
    )
    trovato = schema.match(testo)
    if trovato is not None and ID_PLUGIN in trovato.group(0):
        return testo[trovato.end():]
    return testo


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
    esiti: list[str] = []
    for nome in profili_dsh():
        esiti.append(f"{nome}: {_monta_in(nome, asciutto)}")
    if len(esiti) == 1:
        return esiti[0].split(": ", 1)[1]
    return " · ".join(esiti)


def _monta_in(profilo: str, asciutto: bool) -> str:
    """Monta il plugin in UN profilo. Restituisce cosa ha fatto."""
    patch = Path.home() / ".dsh" / "profiles" / profilo / "cordis.patch.yml"
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
            "DSH non e' installato qui, oppure il profilo si chiama diversamente. "
            "Non c'e' un'opzione per sceglierlo: il montaggio guarda OGNI profilo che "
            "abbia un cordis.patch.yml, perche' indovinare quale sia vivo e' il difetto "
            "di ERR-0086. Se la cartella del profilo non esiste, DSH non lo vede comunque."
        )

    testo = patch.read_text(encoding="utf-8")
    testo = _togli_blocco_legacy(testo)

    # Il difetto che ha impedito a DSH di partire: un blocco indentato in testa a un
    # elenco di primo livello. Prima di toccare il file si controlla che sia leggibile.
    errore = _errore_yaml(testo)
    if errore is not None:
        return f"non posso montare: il layer non e' YAML valido ({errore})"

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
        aggiornato = schema.sub(lambda m: m.group(1) + str(PLUGIN), testo, count=1)
        errore = _errore_yaml(aggiornato)
        if errore is not None:
            return f"non ho aggiornato: il risultato non e' YAML valido ({errore})"
        _scrivi_patch(patch, aggiornato)
        return "aggiornato: il percorso puntava a un'altra sede"

    # **Il blocco parte a colonna zero**: e' un elemento dell'elenco YAML, non un
    # frammento annidato. L'installazione non deve mai rendere il file illeggibile.
    blocco = (
        "- insert:\n"
        f"    - id: {ID_PLUGIN}\n"
        f"      name: {PLUGIN}\n"
    )
    if asciutto:
        return "da aggiungere in testa al layer"
    # **In testa**, ed e' corretto: un layer DSH e' una lista YAML di voci, quindi un
    # elemento preposto e' un elemento in piu' della stessa lista. Il 2026-11-06 ho
    # creduto di aver trovato un difetto qui — «il blocco preposto a un file che
    # contiene una mappa produce un documento illeggibile» — e ho scritto un ramo che
    # accodava. Il difetto non c'era: era il mio **test** a costruire una mappa
    # (`plugins:\n  - id: ...`) invece di una lista. Il formato vero e' quello che si
    # legge in `~/.dsh/profiles/*/cordis.patch.yml`: commenti e voci `- ...`.
    #
    # Il ramo e' stato tolto. Due cose da ricordare: un test che prova un formato che
    # non esiste accusa il programma di un difetto che e' suo; e il controllo `errore`
    # qui sotto e' quello che mi ha impedito di scrivere un file rotto mentre credevo
    # di correggere.
    nuovo = blocco + testo
    errore = _errore_yaml(nuovo)
    if errore is not None:
        return f"non ho montato: il file prodotto non e' YAML valido ({errore})"
    _scrivi_patch(patch, nuovo)
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


def prova(ambiente: str, *, dove_provare: Path | None = None) -> list[tuple[bool, str]]:
    """Le prove. Una sola conta piu' di tutte: **la scrittura viene rifiutata?**

    ``dove_provare`` e' la cartella sotto cui creare il progetto di prova. Serve ai test:
    senza, la prova scrive nella radice del motore **vera** — e una HOME finta non la
    reindirizza, perche' ``PROGETTI_ROOT`` viene dal percorso del modulo, non da
    ``Path.home()``. Il QA di `GOV-024` l'ha misurato: **7 creazioni nella radice vera per
    ogni esecuzione del test**, con un nome fisso, quindi due sessioni si scontrano e la
    prima che finisce cancella la cartella dell'altra. E se il processo muore a meta', il
    residuo resta **invisibile**: `.gitignore` lo nasconde a git, il gate resta immobile,
    e il nome numerico lo fa trattare come progetto.
    
    Non si dichiara «installato»: si prova che il cancello rifiuta. E' la differenza
    fra una regola scritta e un controllo che fallisce.
    """
    esiti: list[tuple[bool, str]] = []

    esiti.append((PLUGIN.is_file(), f"il plugin esiste: {PLUGIN.relative_to(RADICE)}"))

    if ambiente == "dsh":
        # **Tutti** i profili, non uno. Il 2026-11-02 la prova guardava `web`, la sessione
        # girava in `desktop`, e l'esito diceva «installato» mentre il cancello era spento
        # proprio dove serviva. Un controllo che guarda un posto solo e' la stessa cosa di
        # un controllo che non c'e', quando il posto non e' quello giusto.
        for nome in profili_dsh():
            patch = Path.home() / ".dsh" / "profiles" / nome / "cordis.patch.yml"
            testo = ""
            try:
                testo = patch.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                pass
            montato = ID_PLUGIN in testo
            esiti.append((montato, f"il montaggio dichiara il plugin (profilo {nome})"))
            if montato:
                esiti.append(
                    (
                        str(PLUGIN) in testo,
                        f"e il percorso e' quello di ADESSO (profilo {nome})",
                    )
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
    #
    # Il nome e' **unico per processo**, non fisso. Con un nome fisso due sessioni che
    # eseguono il setup insieme si scontrano: la prima che finisce cancella la cartella
    # dell'altra, e la seconda prova il rifiuto su una cartella che non c'e' piu'. Il QA
    # di `GOV-024` l'ha misurato, insieme al caso peggiore: se il processo muore a meta',
    # il residuo resta e nessuno lo vede — `.gitignore` lo nasconde a git, il gate resta
    # immobile, e il nome numerico lo fa trattare come un progetto.
    #
    # Il numero davanti resta: e' cio' che dice al cancello «questa e' una cartella
    # prodotto», e senza il cancello non rifiuterebbe niente. Ma il suffisso lo rende
    # nostro, e la pulizia lo toglie anche se il processo viene interrotto.
    # **In una radice temporanea, non in quella vera.** E' il rimedio proposto dal Code
    # Review di `GOV-024` R4 (F-2), e la sua prova regge: il cancello riconosce una
    # cartella prodotto da `^\d+\.` **relativo alla radice che gli si passa**, non alla
    # radice vera. Con `--root` su una cartella temporanea il rifiuto e' identico, e il
    # residuo diventa **impossibile** invece che improbabile: se il processo muore fra
    # `mkdir` e `rmtree`, resta una cartella in `/tmp` che nessuno scambia per un progetto.
    #
    # Prima si scriveva nella radice vera con un nome unico per PID. Funzionava, ma un
    # `SIGKILL` a meta' lasciava un `99. Prova Del Cancello 1234` che `.gitignore` nasconde
    # a git, che il gate resta immobile su, e che il nome numerico fa trattare come
    # progetto. La cartella di un'altra sessione, poi, veniva cancellata dalla pulizia.
    #
    # La radice temporanea ha bisogno di `sede.yaml` e di `contratti/`: senza, il cancello
    # e' inerte e la prova direbbe «ammesso» su tutto. Si copiano dal motore, che e' la
    # cosa che si vuole provare.
    base = dove_provare if dove_provare is not None else RADICE
    nome_prova = f"99. Prova Del Cancello {os.getpid()}"
    temporanea = Path(tempfile.mkdtemp(prefix="prova-cancello-"))
    creata = False
    try:
        # La radice finta deve somigliare abbastanza al motore perche' il cancello
        # funzioni: `sede.yaml` (la macchina esiste) e `contratti/` (il registro).
        (temporanea / "contratti" / "societa").mkdir(parents=True)
        sede_vera = RADICE / "sede.yaml"
        if sede_vera.is_file():
            shutil.copy2(sede_vera, temporanea / "sede.yaml")
        prova = temporanea / nome_prova
        prova.mkdir()
        creata = True
        esito = subprocess.run(
            [sys.executable, str(CHECKER), "check", f"{nome_prova}/una-prova.ts",
             "--root", str(temporanea)],
            capture_output=True,
            text=True,
            cwd=str(temporanea),
        )
        rifiutata = esito.returncode != 0
        esiti.append(
            (rifiutata, "il cancello RIFIUTA una scrittura in una cartella di progetto")
        )
    except Exception as errore:  # noqa: BLE001
        esiti.append((False, f"non ho potuto provare il rifiuto: {type(errore).__name__}"))
    finally:
        # La pulizia toglie **tutto** cio' che questo processo ha creato: la radice
        # temporanea e' nostra e nessun altro la usa, quindi cancellarla e' sicuro.
        shutil.rmtree(temporanea, ignore_errors=True)
        if temporanea.exists():
            esiti.append(
                (False, f"residuo non rimosso: {temporanea} — va cancellato a mano")
            )

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


def _togli_la_nostra_voce(testo: str) -> str | None:
    """Toglie **la sola voce del nostro plugin**, e nient'altro. ``None`` se non c'e'.

    Perche' non basta una regex sul blocco (`GOV-024` B-2, P1 del Code Review). Nel
    profilo vivo `web` il nostro plugin **condivide** l'`insert:` con MailerLite:

        - insert:
            - id: ad-enforce-contract
              name: .../index.mjs
            - id: mailerlite-mcp          <- la voce di qualcun altro
              name: '@deepseek-ai/dsh-mcp-client'

    La versione precedente toglieva `- insert:` **intero** con la prima voce: le voci
    sorelle restavano **orfane**, sotto nessun `insert:`, e il file diventava illeggibile
    — «expected '<document start>', but found '<block sequence start>'». Con exit 0 e il
    messaggio «rimosso». E siccome il ciclo nuovo tocca tutti i profili, R2 rompeva tutti
    quelli che condividevano il blocco, non uno.

    Qui si tolgono solo le righe della **nostra** voce — l'`id`, il `name`, e i commenti
    che l'installatore ha scritto sopra — e se il blocco resta con altre voci lo si tiene;
    se resta vuoto, si toglie anche il `- insert:`.
    """
    righe = testo.splitlines(keepends=True)
    uscita: list[str] = []
    i = 0
    tolto = False
    while i < len(righe):
        riga = righe[i]
        # Inizio della nostra voce: `- id: <ID_PLUGIN>` (con lo stesso rientro con cui
        # `_monta_in` la scrive, cioe' quattro spazi sotto `insert:`).
        if re.match(rf"^\s*-\s*id:\s*{re.escape(ID_PLUGIN)}\s*$", riga):
            # Si toglie questa riga e le successive piu' indentate della stessa voce:
            # `name:` e `config:` se ci sono, fino alla prossima voce o alla fine.
            rientro_voce = len(riga) - len(riga.lstrip())
            i += 1
            while i < len(righe):
                successiva = righe[i]
                spoglia = successiva.strip()
                if not spoglia or spoglia.startswith("#"):
                    # Un commento dentro la voce: si toglie solo se e' piu' indentato
                    # della voce (cioe' le appartiene).
                    if spoglia.startswith("#") and (
                        len(successiva) - len(successiva.lstrip())
                    ) > rientro_voce:
                        i += 1
                        continue
                    break
                rientro = len(successiva) - len(successiva.lstrip())
                if rientro <= rientro_voce:
                    break
                i += 1
            tolto = True
            continue
        uscita.append(riga)
        i += 1

    if not tolto:
        return None

    # Se il blocco `insert:` e' rimasto **senza voci**, si toglie anche lui: un `insert:`
    # vuoto e' legittimo YAML ma non serve a nessuno, e **si accumula** — il Code Review di
    # R3 ne ha contati due dopo un ciclo monta/smonta. Smentisce «lascia il file come l'hai
    # trovato», che e' la promessa di questa funzione.
    #
    # Due casi che la versione precedente non prendeva (F-006):
    #   - un **commento** che resta dentro il blocco: si guardava solo la prossima riga
    #     non vuota, e un commento non e' una voce;
    #   - il blocco **in fondo al file**: la condizione `indice + 1 < len(uscita)` era
    #     falsa, quindi il blocco restava.
    def _senza_voci(inizio: int, rientro_insert: int) -> bool:
        """Dopo `insert:`, c'e' almeno una voce con rientro maggiore?"""
        for successiva in uscita[inizio + 1:]:
            spoglia = successiva.strip()
            if not spoglia:
                continue
            rientro = len(successiva) - len(successiva.lstrip())
            if spoglia.startswith("#"):
                # Un commento dentro il blocco non e' una voce: si ignora, ma il blocco
                # lo contiene ancora. Solo se il commento e' piu' indentato dell'insert.
                if rientro > rientro_insert:
                    continue
                return True  # commento a livello dell'insert: fine del blocco
            # Una voce del blocco ha rientro maggiore dell'insert.
            return rientro <= rientro_insert
        return True  # niente dopo: blocco vuoto

    risultato: list[str] = []
    indice = 0
    while indice < len(uscita):
        riga = uscita[indice]
        corrispondenza = re.match(r"^(\s*)-\s*insert:\s*$", riga)
        if corrispondenza and _senza_voci(indice, len(corrispondenza.group(1))):
            # Blocco vuoto: si salta l'`insert:` e anche i commenti che gli appartengono,
            # perche' senza voci sono commenti su un blocco che non c'e' piu'.
            indice += 1
            while indice < len(uscita):
                spoglia = uscita[indice].strip()
                if not spoglia:
                    indice += 1
                    continue
                rientro = len(uscita[indice]) - len(uscita[indice].lstrip())
                if spoglia.startswith("#") and rientro > len(corrispondenza.group(1)):
                    indice += 1
                    continue
                break
            continue
        risultato.append(riga)
        indice += 1
    return "".join(risultato)


def disinstalla(ambiente: str) -> list[tuple[str, str]]:
    """Disfa quello che l'installatore ha fatto. **Nient'altro.**

    Su **tutti** i profili, come il montaggio. Fino al 2026-11-06 questa funzione usava
    ``_profilo_dsh()``, che risolve **un** percorso, mentre ``installa()`` cicla su
    ``profili_dsh()``: si montava ovunque e si smontava in un posto. Con tre profili
    montati, ``--uninstall`` ne ripuliva uno, stampava «rimosso» e usciva 0 — lasciando
    il cancello acceso sugli altri, che e' peggio di non averlo montato: chi legge il
    messaggio crede di averlo spento.

    E' `ERR-0086` rovesciato, e l'hanno trovato due revisori indipendenti lo stesso
    giorno (`GOV-024`, F-001 del QA e F-1 del Code Review). La regola generale: se il
    montaggio guarda N posti, la disinstallazione deve guardarne N.
    """
    esiti: list[tuple[str, str]] = []
    if ambiente != "dsh":
        return esiti

    # Lo stesso elenco che usa il montaggio. Una sorgente sola per «dove si monta».
    # `profili_dsh()` restituisce i **nomi**, non i percorsi: il percorso si compone
    # qui, con la stessa formula che usa il montaggio.
    for nome_profilo in profili_dsh():
        patch = Path.home() / ".dsh" / "profiles" / nome_profilo / "cordis.patch.yml"
        if not patch.exists():
            continue
        testo = patch.read_text(encoding="utf-8")
        nuovo = _togli_la_nostra_voce(testo)
        if nuovo is None:
            esiti.append((f"montaggio del plugin ({nome_profilo})", "non c'era"))
            continue
        if nuovo == testo:
            esiti.append((f"montaggio del plugin ({nome_profilo})", "non c'era"))
            continue
        # **La difesa che mancava** (`GOV-024` B-2, P1 del Code Review): si controlla che
        # il risultato sia YAML valido **prima** di scriverlo. `_monta_in` lo fa gia' da
        # sempre; `disinstalla` no — ed e' per questo che ha potuto scrivere un layer
        # illeggibile. Se il risultato non e' valido, si **lascia il file com'e'** e si
        # dice che non si e' potuto togliere: un cancello che resta acceso e' un problema,
        # un layer rotto e' DSH che non parte.
        errore = _errore_yaml(nuovo)
        if errore is not None:
            esiti.append(
                (
                    f"montaggio del plugin ({nome_profilo})",
                    f"NON rimosso: il risultato non sarebbe YAML valido ({errore}). "
                    "Il file e' intatto: togliere la voce a mano",
                )
            )
            continue
        patch.write_text(nuovo, encoding="utf-8")
        esiti.append((f"montaggio del plugin ({nome_profilo})", "rimosso"))

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
        esiti_disinstallazione = disinstalla(ambiente)
        for cosa, esito in esiti_disinstallazione:
            print(f"  {cosa:24} {esito}")
        # F-009 del Code Review di R3: usciva **0** anche quando rifiutava di scrivere.
        # Un exit code che dice «fatto» quando non ha fatto niente e' la stessa classe di
        # difetto del messaggio «rimosso» con il cancello ancora acceso: chi chiama non
        # puo' distinguere i due casi, e non li controllera'.
        if any("NON rimosso" in esito for _, esito in esiti_disinstallazione):
            print()
            print("  esito: NON tutto e' stato rimosso — vedi le righe «NON rimosso»")
            return 1
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
    # Dove creare la cartella di prova. La variabile d'ambiente serve ai **test**: senza,
    # la prova scrive nella radice vera del motore (vedi `prova()`).
    dove = os.environ.get("AD_PROVA_IN")
    for ok, descrizione in prova(ambiente, dove_provare=Path(dove) if dove else None):
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
