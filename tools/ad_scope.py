"""Ambito di scrittura: quale percorso e' coperto da quale task contract.

Il layer di enforcement di runtime (`DEC-0003`) non decide da solo: chiede a
questo modulo. La regola e' quella della governance — un lavoro su un prodotto
parte da un task contract, e il contract dichiara dove si puo' scrivere.

I contract operativi vivono in ``AD Projects/contratti/``: un file YAML per
task, con gli stessi campi di ``TASK-CONTRACTS.md`` piu' ``write_scope``.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

import ad_contract
import ad_docs
import ad_milestone

#: Cartella dei contract operativi, relativa alla root.
CONTRACTS_DIR = "contratti"

#: Cartella dei marcatori di approvazione del CEO, relativa alla root.
#: Il consenso e' un atto esplicito: senza marcatore il contract non copre.
APPROVALS_DIR = "approvazioni"

#: Artefatti di governance: la macchina che definisce ed esegue le regole.
#:
#: `.brain/` e' symlinkato in `~/.dsh/AGENTS.md` e `~/.agents/skills/`, e il plugin
#: di enforcement e' montato nel profilo DSH: chi scrive qui cambia cosa fanno TUTTI
#: gli agenti, in OGNI sessione. `tools/` e' l'autorita' che il plugin interroga.
#: Non sono cartelle prodotto, ma il loro raggio d'azione e' piu' ampio.
GOVERNANCE_PATHS: tuple[str, ...] = (".brain", "tools")

#: Una cartella prodotto e' numerata: ``5. Example Project``, ``11. Example Project``.
#: Solo queste sono protette: gli strumenti e i documenti restano scrivibili.
PROTECTED_DIR = re.compile(r"^\d+\.")

#: Stati che rendono un contract operativo. Qualsiasi altro valore non copre.
ACTIVE_STATES: tuple[str, ...] = ("active", "attivo", "approvato")

#: Comandi che possono modificare il filesystem. Conservativo di proposito:
#: bloccare un comando di sola lettura e' un fastidio, lasciar passare una
#: scrittura su un progetto e' un danno.
#:
#: MA «CONSERVATIVO» NON VUOL DIRE «SBAGLIATO» (2026-11-06). La prima versione
#: trattava ogni `>` come una redirezione, comprese `2>&1` e `>/dev/null`, che non
#: scrivono nessun file: cosi' un `x.py render 2>/dev/null` veniva rifiutato come
#: scrittura su `tools/`, e il rifiuto era falso. Un controllo che accusa comandi
#: legittimi insegna a disattivarlo — la lezione di ERR-0088, che avevo gia' imparato
#: e non avevo applicato qui.
#:
#: La distinzione:
#:   scrive:    `> file`, `>> file`, `2> file`, `&> file`, `>file`
#:   non scrive: `2>&1`, `>&2`, `>/dev/null`, `2>/dev/null`, `> /dev/null`
MUTATION_PATTERNS: tuple[re.Pattern[str], ...] = (
    # Una redirezione scrive un file solo se ha una destinazione che non e' un
    # descrittore (`&N`) e non e' il pozzo nero. Quattro esclusioni, ognuna per un
    # falso positivo misurato:
    #   `(?<![=<>-])`  `a >= b`, `a -> b`, `a ==> b` non sono redirezioni
    #   `(?![&\d])`    `2>&1` e `>&2` mandano i messaggi a un descrittore
    #   `(?!/dev/null)` il pozzo nero non e' un file
    #   `(?!=)`        `>=` non e' una redirezione (resta per chiarezza)
    re.compile(r"(?<![=<>-])>>?\s*(?![&\d])(?!/dev/null)(?!=)[^\s<>|;&]+"),
    re.compile(r"\b(rm|mv|cp|tee|truncate|dd|touch|mkdir|rmdir|chmod|chown|ln|patch)\b"),
    re.compile(r"\bsed\b[^\n]*\s-i(\s|$)"),
    re.compile(r"\bgit\s+(checkout|reset|clean|restore|apply|stash)\b"),
    re.compile(
        r"\b(npm|pnpm|yarn|pip|pip3|poetry|uv)\s+(install|add|remove|ci|sync|uninstall)\b"
    ),
)

#: Mutazioni senza percorso esplicito: per queste conta la directory di lavoro.
#: Non serve un elenco: la regola e' "nessun argomento con '/' -> vale la cwd".


def _senza_stringhe(comando: str) -> str:
    """Il comando con il contenuto delle stringhe quotate rimosso.

    Perche' serve (2026-11-06). `grep -n 'a>b' file.txt` cerca il testo `a>b`: il
    maggiore e' dentro una stringa, non e' una redirezione, e il comando non scrive
    niente. La prima versione lo rifiutava come scrittura, ed era un falso positivo —
    lo stesso difetto di `2>&1`, in un'altra forma.

    Si toglie il contenuto, non le virgolette: cosi' `"file con spazi.txt"` resta un
    argomento unico e il resto dell'analisi continua a funzionare. Un apice non chiuso
    non si tocca: un comando malformato e' piu' prudente trattarlo com'e'.
    """
    risultato: list[str] = []
    apice = ""
    for carattere in comando:
        if apice:
            if carattere == apice:
                apice = ""
                risultato.append(carattere)
            # dentro la stringa: il contenuto non conta per la struttura
            continue
        if carattere in "\"'":
            apice = carattere
        risultato.append(carattere)
    # Se un apice e' rimasto aperto, il comando era malformato: si torna all'originale
    # invece di restituire una versione a meta', che nasconderebbe una scrittura vera.
    return comando if apice else "".join(risultato)


@dataclass(frozen=True)
class WriteScope:
    """Un contract operativo e il suo ambito di scrittura."""

    task_id: str
    agent: str
    status: str
    scopes: tuple[str, ...]
    source: Path
    milestone: int | None = None
    sprint: int | None = None
    #: La data che il permesso **dichiara** di essere stato aperto. Viaggia col
    #: documento; l'mtime no, e una copia o un `git clone` lo azzera (2026-10-13).
    aperto: str = ""

    def covers(self, relative: str) -> bool:
        """Return True when ``relative`` (posix, senza slash iniziale) e' coperto."""
        target = relative.replace("\\", "/").strip("/")
        for scope in self.scopes:
            candidate = scope.replace("\\", "/").strip().strip("/")
            if not candidate:
                continue
            if target == candidate or target.startswith(candidate + "/"):
                return True
        return False


@dataclass(frozen=True)
class ScopeVerdict:
    """L'esito del controllo su un percorso."""

    target: str
    relative: str
    protected: bool
    covered: bool
    task_id: str
    reason: str

    @property
    def allowed(self) -> bool:
        """True when nothing in the enforcement layer objects."""
        return self.covered or not self.protected


def contracts_dir(root: Path) -> Path:
    """Return the contracts directory for ``root``."""
    return Path(root) / CONTRACTS_DIR


def momento_scadenza(value: Any) -> "datetime | None":
    """Il momento in cui un `expires` scade, o None se non e' una data.

    Una **data sola** (`2026-10-26`) scade alla **fine di quella giornata**, nel fuso
    locale: trattarla come mezzanotte UTC la faceva scadere ~22 ore prima (`ADMF-094`,
    segnalato dal gate di GOV-018). Una data con ora si usa come scritta.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    solo_data = len(text) == 10
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    if moment.tzinfo is None:
        if solo_data:
            locale = datetime.now().astimezone().tzinfo
            moment = moment.replace(hour=23, minute=59, second=59, tzinfo=locale)
        else:
            moment = moment.replace(tzinfo=UTC)
    return moment


def _expired(value: Any) -> bool:
    """Return True when an ISO ``expires`` value is in the past."""
    moment = momento_scadenza(value)
    if moment is None:
        return False
    return moment < datetime.now(UTC)


def iter_registro(
    directory: Path | str, problemi: list[str] | None = None
) -> list[Path]:
    """I file YAML del registro, **seguendo i collegamenti**, senza entrare in ciclo.

    Il registro delle autorizzazioni vive con il progetto
    (``<progetto>/governance/contratti|approvazioni/<gruppo>/``) e nella root restano
    i **collegamenti**. ``Path.rglob`` **non** attraversa una cartella collegata: senza
    questa funzione il cancello non vede i contract — il caso ``NLT-064``, rimasto
    attivo e invisibile, che bloccava a project (``ERR-0076``, ``DEC-0080``).

    Si segue il collegamento e si tiene traccia di ``(st_dev, st_ino)`` delle cartelle
    gia' viste, cosi' un ciclo di collegamenti non fa girare a vuoto.

    Un collegamento **rotto** non entra nell'elenco, e — se il chiamante passa
    ``problemi`` — viene **detto**: saltarlo in silenzio vorrebbe dire rendere
    invisibile un contract senza accorgersene, che e' lo stesso difetto di partenza.
    """
    base = Path(directory)
    if not base.is_dir():
        return []
    visti: set[tuple[int, int]] = set()
    trovati: list[Path] = []
    for radice, cartelle, files in os.walk(base, followlinks=True):
        corrente = Path(radice)
        try:
            stato = corrente.stat()
        except OSError:
            cartelle[:] = []
            continue
        chiave = (stato.st_dev, stato.st_ino)
        if chiave in visti:
            cartelle[:] = []
            continue
        visti.add(chiave)
        for nome in files:
            percorso = corrente / nome
            if not percorso.is_file():
                # Un nome che non e' un file: tipicamente un collegamento rotto
                # (a un file o a una cartella sparita). Non si usa, ma si dice.
                if problemi is not None and percorso.is_symlink():
                    problemi.append(f"collegamento rotto: {percorso}")
                continue
            if nome.endswith((".yaml", ".yml")):
                trovati.append(percorso)
    return sorted(trovati)


def _scope_a_dizionario(scope: WriteScope) -> dict:
    """Un ``WriteScope`` in forma serializzabile: la cache vive su disco."""
    return {
        "task_id": scope.task_id,
        "agent": scope.agent,
        "status": scope.status,
        "scopes": list(scope.scopes),
        "source": str(scope.source),
        "milestone": scope.milestone,
        "sprint": scope.sprint,
        "aperto": scope.aperto,
    }


def _dizionario_a_scope(dato: object) -> WriteScope | None:
    """Il contrario. Un dizionario malformato non diventa uno scope: torna ``None``.

    Una cache che restituisce un oggetto a meta' e' peggio di una cache fredda: chi
    chiama si fiderebbe di un permesso che non e' quello del file.
    """
    if not isinstance(dato, dict):
        return None
    try:
        return WriteScope(
            task_id=str(dato["task_id"]),
            agent=str(dato.get("agent", "")),
            status=str(dato["status"]),
            scopes=tuple(str(x) for x in dato["scopes"]),
            source=Path(str(dato["source"])),
            milestone=dato.get("milestone"),
            sprint=dato.get("sprint"),
            aperto=str(dato.get("aperto", "")),
        )
    except (KeyError, TypeError, ValueError):
        return None


def load_write_scopes(root: Path | str) -> list[WriteScope]:
    """Load every operational contract that declares a ``write_scope``.

    Args:
        root: Root of AD Projects.

    Returns:
        The contracts, sorted by file name. Files without ``write_scope``,
        with an unknown state or expired are skipped: non coprono nulla.

    La lettura passa dalla **cache dei registri** (``tools/cache_registri.py``): il
    parsing di 439 file YAML costa 750 ms, e quattordici punti di chiamata lo pagano a
    ogni comando. La firma e' il **contenuto** dei file, non l'mtime — cosi' una copia
    che conserva gli orari non inganna la cache (la falsa accusa che `ad_scope` conosce
    gia'). Se la cache non si puo' usare, si legge come prima: la cache e' un guadagno,
    non un requisito.
    """
    directory = contracts_dir(Path(root))
    if not directory.is_dir():
        return []

    def _calcola() -> list[dict]:
        return [
            _scope_a_dizionario(scope) for scope in _load_write_scopes_senza_cache(directory)
        ]

    try:
        import cache_registri

        grezzi = cache_registri.con_cache(
            f"scopes:{directory}",
            _calcola,
            lambda: list(iter_registro(directory)),
            Path(root),
        )
        scopes = [s for s in (_dizionario_a_scope(d) for d in grezzi) if s is not None]
        if len(scopes) == len(grezzi):
            return scopes
        # Una voce non si e' potuta ricostruire: si rilegge. Non si serve un elenco a
        # meta' — sarebbe un permesso mancante, e il cancello direbbe di no a una
        # scrittura legittima.
    except (ImportError, OSError, ValueError, TypeError):
        pass
    return _load_write_scopes_senza_cache(directory)


def _load_write_scopes_senza_cache(directory: Path) -> list[WriteScope]:
    """La lettura vera, senza cache. E' il percorso di sempre."""
    found: list[WriteScope] = []
    for path in iter_registro(directory):
        if path.name.startswith("_"):
            continue  # modelli e file di servizio non sono contract
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(data, dict):
            continue
        raw = data.get("write_scope")
        if isinstance(raw, str):
            raw = [raw]
        if not isinstance(raw, list) or not raw:
            continue
        status = str(data.get("status", "active")).strip().lower()
        if status not in ACTIVE_STATES or _expired(data.get("expires")):
            continue
        tappa = data.get("milestone")
        passo = data.get("sprint")
        tappa = tappa if isinstance(tappa, int) and not isinstance(tappa, bool) else None
        passo = passo if isinstance(passo, int) and not isinstance(passo, bool) else None
        found.append(
            WriteScope(
                task_id=str(data.get("task_id", path.stem)),
                agent=str(data.get("agent", "")),
                status=status,
                scopes=tuple(str(item) for item in raw if str(item).strip()),
                source=path,
                milestone=tappa,
                sprint=passo,
                # La data che il permesso dichiara. Viaggia col documento, a
                # differenza dell'mtime, che una copia azzera (2026-10-13).
                aperto=str(data.get("aperto", ""))[:10],
            )
        )
    return found


def _primo_progetto(scopes: tuple[str, ...]) -> str | None:
    """Return the product folder a contract writes into, or None."""
    for prefisso in scopes:
        testa = str(prefisso).strip().strip('"').split("/", 1)[0]
        if PROTECTED_DIR.match(testa):
            return testa
    return None


def relative_to_root(target: Path | str, root: Path | str) -> str | None:
    """Return ``target`` relative to ``root`` as a posix string, or None."""
    try:
        return Path(target).resolve().relative_to(Path(root).resolve()).as_posix()
    except (ValueError, OSError):
        return None


def protected_segment(relative: str | None) -> str | None:
    """Return the numbered product folder of a relative path, or None."""
    if not relative:
        return None
    head = relative.split("/", 1)[0]
    return head if PROTECTED_DIR.match(head) else None


def governance_segment(relative: str | None) -> str | None:
    """Return the governance artifact a relative path belongs to, or None.

    Un artefatto di governance non e' una cartella prodotto: e' la macchina che
    definisce ed esegue le regole. Il suo raggio d'azione non e' un progetto, e'
    ogni agente in ogni sessione.
    """
    if not relative:
        return None
    head = relative.split("/", 1)[0]
    return head if head in GOVERNANCE_PATHS else None


def protected_entries(root: Path | str | None = None) -> tuple[str, ...]:
    """Return every path class the write authority guards.

    Cartelle prodotto **piu'** artefatti di governance. Serve all'analisi della
    shell, che cerca i percorsi per nome invece che per posizione.
    """
    return tuple(protected_folders(root)) + GOVERNANCE_PATHS


def _any_segment(relative: str | None) -> str | None:
    """Return the guarded path class of a relative path, product or governance."""
    return protected_segment(relative) or governance_segment(relative)


@dataclass(frozen=True)
class Approval:
    """Il marcatore con cui il CEO approva un piano."""

    task_id: str
    approvato_da: str
    data: str
    piano: str
    source: Path
    #: DEC-0096: la firma dice **chi** ha approvato, non solo cosa dice il file.
    firmata: bool = False
    superficie: str = ""
    stato_firma: str = "legacy"


def approvals_dir(root: Path | str) -> Path:
    """Return the approvals directory for ``root``."""
    return Path(root) / APPROVALS_DIR


def _stato_della_firma(dati: dict, root: Path) -> str:
    """Lo stato della firma di un marcatore (DEC-0096).

    La distinzione che conta: ``legacy`` **non** e' un errore. Le 413 approvazioni
    scritte prima di DEC-0096 non si riscrivono — la storia non si tocca — ma non provano
    chi ha approvato. ``manomessa`` invece e' un errore: la firma c'e' e non combacia,
    quindi il contenuto e' cambiato dopo l'atto.

    Se la chiave non c'e', una firma presente **non si puo' ricalcolare**: si risponde
    ``non verificabile``, che non e' ``firmata``. Mai dichiarare verificato cio' che non
    si e' potuto verificare.
    """
    import hashlib
    import hmac
    import json

    grezza = str(dati.get("firma", "")).strip()
    if not grezza:
        return "legacy"
    try:
        chiave = (Path.home() / ".dsh" / "ad-consenso.key").read_bytes().strip()
    except OSError:
        return "non verificabile (chiave assente)"
    if len(chiave) < 32:
        return "non verificabile (chiave corta)"
    senza = {chiave_nome: valore for chiave_nome, valore in dati.items() if chiave_nome != "firma"}
    canonico = json.dumps(
        senza, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    attesa = hmac.new(chiave, canonico, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(grezza, attesa):
        return "manomessa"
    piano = str(dati.get("piano", "")).strip()
    registrata = dati.get("piano_sha256")
    if piano and registrata:
        try:
            attuale = hashlib.sha256((root / piano).read_bytes()).hexdigest()
        except OSError:
            return "piano sparito"
        if attuale != registrata:
            return "piano cambiato"
    return "firmata"


def load_approvals(root: Path | str) -> dict[str, Approval]:
    """Load the CEO approval markers, keyed by task id.

    Un marcatore senza `task_id`, `approvato_da` o `data` non vale: l'approvazione
    deve dire chi e quando.

    Args:
        root: Root of AD Projects.

    Returns:
        The valid approvals, keyed by ``task_id``.
    """
    directory = approvals_dir(Path(root))
    if not directory.is_dir():
        return {}
    found: dict[str, Approval] = {}
    for path in iter_registro(directory):
        if path.name.startswith("_"):
            continue
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(data, dict):
            continue
        task_id = str(data.get("task_id", "")).strip()
        approver = str(data.get("approvato_da", "")).strip()
        moment = str(data.get("data", "")).strip()
        if not task_id or not approver or not moment:
            continue
        stato_firma = _stato_della_firma(data, Path(root))
        found[task_id] = Approval(
            task_id=task_id,
            approvato_da=approver,
            data=moment,
            piano=str(data.get("piano", "")).strip(),
            source=path,
            firmata=stato_firma == "firmata",
            superficie=str(data.get("superficie", "")).strip(),
            stato_firma=stato_firma,
        )
    return found


def coverage(relative: str, root: Path | str | None = None) -> tuple[WriteScope | None, str]:
    """Return the contract covering ``relative`` and why it does or does not.

    Un contract copre solo se e' attivo, ha un ``write_scope`` che include il
    percorso, **e** esiste il marcatore di approvazione del CEO per quel task.
    L'approvazione deve precedere il contract: un contract scritto prima del
    consenso non copre.

    Args:
        relative: Target path relative to the root, posix style.
        root: Root of AD Projects (default: the root of this checkout).

    Returns:
        ``(scope, reason)``. ``scope`` is None when nothing covers the path;
        ``reason`` explains the outcome either way.
    """
    root_path = Path(root) if root is not None else ad_docs.DOCS_ROOT
    approvals = load_approvals(root_path)

    for scope in load_write_scopes(root_path):
        if not scope.covers(relative):
            continue
        approval = approvals.get(scope.task_id)
        if approval is None:
            return None, (
                f'Il contract {scope.task_id} copre "{relative}" ma manca '
                "l'approvazione del CEO.\nSenza consenso non si lavora: serve "
                f"{approvals_dir(root_path)}/{scope.task_id}.yaml con task_id, "
                "approvato_da e data (GOVERNANCE-AZIENDALE.md)."
            )
        # DEC-0096: la firma dice chi, non solo cosa. Un marcatore **manomesso** non
        # autorizza: la firma c'e' e non combacia, quindi il contenuto e' cambiato dopo
        # l'atto. Un **legacy** passa — e' la storia — ma il motivo lo dichiara.
        stato = approval.stato_firma
        if stato in ("manomessa", "piano cambiato", "piano sparito"):
            return None, (
                f'Il contract {scope.task_id} copre "{relative}" ma l\'approvazione del CEO '
                f"e' **{stato}**: la firma non combacia col contenuto (DEC-0096). "
                "Il consenso era a un altro testo: serve un'approvazione nuova, firmata con "
                f"`python3 tools/ad_consenso.py firma {scope.task_id}`."
            )
        if stato not in ("firmata", "legacy"):
            return None, (
                f'Il contract {scope.task_id} copre "{relative}" ma la firma non e\' '
                f"verificabile ({stato}). Non dichiaro verificato cio' che non ho potuto "
                "verificare: crea la chiave con `python3 tools/ad_consenso.py chiave-nuova`."
            )
        try:
            # L'ORDINE SI LEGGE DALLE DATE DICHIARATE, NON DAGLI ORARI DEI FILE.
            #
            # Il 2026-10-13 ho copiato la macchina altrove per provare la portabilita':
            # una copia azzera gli mtime, e l'ordine fra permesso e approvazione si
            # perdeva. Ma una copia non e' un caso limite — **e' quello che succede a
            # chiunque cloni il repository**. Un controllo che funziona solo nella
            # cartella dove e' nato non e' un controllo.
            #
            # Le date scritte nei documenti viaggiano con i documenti. L'mtime resta
            # come ripiego quando una data manca, ed e' un ripiego dichiarato.
            # **L'mtime non e' un ripiego: e' una falsa accusa.**
            #
            # Ripiegare sull'mtime sembra prudente, e non lo e'. Su una copia gli
            # orari si azzerano e il controllo **accusa un contract di essere stato
            # retrodatato quando e' solo copiato** — un verdetto sbagliato su una
            # persona che non ha fatto niente. Un controllo che sbaglia cosi' insegna
            # a ignorarlo, che e' peggio di non averlo.
            #
            # Quindi: se le date dichiarate ci sono, si confrontano. Se mancano, **non
            # si accusa e non si tace**: si dichiara che quel permesso non e'
            # verificabile, e va messo in regola. Il permesso nuovo dichiara `aperto:`.
            # Un dato che MANCA non e' una colpa: si **non verifica**, non si nega.
            # Negare bloccherebbe ogni permesso scritto prima di questa regola, e il
            # rimedio sarebbe peggio del male. Chi non dichiara la data viene elencato
            # da `contract_scope.py titolari` e messo in regola quando lo si tocca.
            if scope.aperto and str(scope.aperto)[:10] > str(approval.data)[:10]:
                return None, (
                    f'Il contract {scope.task_id} e\' stato scritto PRIMA '
                    f"dell'approvazione ({approval.data}).\nL'ordine e' "
                    "ricerca -> risposta -> consenso -> contract: un contract "
                    "retrodatato non copre."
                )
        except OSError:
            return None, f"Impossibile verificare l'ordine per {scope.task_id}."

        # DRIFT-010 — il cane che si morde la coda.
        #
        # La regola (invariante 13) dice: non si lavora in un progetto senza il
        # passo aperto. Ma il foglio del passo va *scritto*, e scriverlo richiede
        # un contract: se il contract pretendesse il passo gia' aperto, non si
        # partirebbe mai.
        #
        # Quindi il confine non e' "avere il contract", e' **dove si scrive**:
        # se il passo dichiarato non e' ancora aperto, il contract copre soltanto
        # la cartella di quel passo — il foglio che lo apre e il suo rapporto.
        # Fuori di li' serve il passo aperto.
        if scope.milestone is not None and scope.sprint is not None:
            radice_progetto = Path(root_path) / _primo_progetto(scope.scopes) if _primo_progetto(scope.scopes) else None
            if radice_progetto is not None:
                prompt = ad_milestone.sprint_prompt(
                    radice_progetto, scope.milestone, scope.sprint
                )
                if not prompt.is_file():
                    # La deroga copre l'intera cartella della tappa, non solo quella
                    # del passo: per aprire un passo bisogna **prima** creare la
                    # tappa, e il suo rapporto sta in `Milestone N/`. Coprire solo
                    # `Milestone N/Sprint M/` rendeva impossibile il primo passo.
                    cartella = f"Milestone {scope.milestone}/"
                    if cartella not in (relative or ""):
                        return None, (
                            f'Il contract {scope.task_id} dichiara la tappa '
                            f"{scope.milestone} passo {scope.sprint}, ma quel passo non e' "
                            f"aperto: manca {prompt.relative_to(Path(root_path))}.\n"
                            "Finche' non e' aperto, il contract copre solo le carte di "
                            f'quella tappa ("{cartella}"). Aprilo con\n'
                            f'  python3 tools/milestone.py new-sprint '
                            f'"{_primo_progetto(scope.scopes)}" {scope.milestone}'
                        )
        return scope, (
            f"coperto dal contract {scope.task_id} ({scope.source.name}), "
            f"approvato da {approval.approvato_da} il {approval.data}"
        )

    return None, ""


# ---------------------------------------------------------------------------
# I progetti si numerano
#
# Il numero davanti non e' un'abitudine estetica: e' **cio' che dice al sistema che
# quella cartella e' un prodotto**. `PROTECTED_DIR = ^\d+\.` e' il riconoscimento, e
# da li' discendono il permesso, l'approvazione e il cancello.
#
# Il 2026-10-13 ho verificato cosa succede senza: **la scrittura passa**, senza
# permesso e senza che nessuno se ne accorga. Un buco di protezione, non una svista.
# ---------------------------------------------------------------------------

#: Le cartelle della MACCHINA: vivono nella radice e **non sono progetti**.
#: Elenco dichiarato, non dedotto: dedurlo da cosa esiste vorrebbe dire accettare
#: come "macchina" qualunque cartella qualcuno crei — che e' il buco da chiudere.
CARTELLE_MACCHINA = frozenset(
    {
        ".brain",
        ".git",
        "tools",
        "tests",
        "DECISIONI",
        "approvazioni",
        "comunicazioni",
        "contratti",
        "drift",
        "errori",
        "evals",
        "evidenze",
        "milestone",
        "orchestrazione",
        "piani",
        "REQUISITI",
        "strategic_memory",
        "studio",
        "AD-AGENTS-PROJECTS",
    }
)


def primo_numero_libero(root: Path | str | None = None) -> int:
    """Il primo numero di progetto non usato. Serve a dire **quale** numero usare."""
    # Fra i PROGETTI, non nella cartella del motore: possono essere due posti
    # diversi (`macchina.progetti` in sede.yaml).
    base = Path(root) if root is not None else ad_docs.PROGETTI_ROOT
    usati = set()
    try:
        for voce in base.iterdir():
            trovato = PROTECTED_DIR.match(voce.name)
            if trovato:
                usati.add(int(voce.name.split(".", 1)[0]))
    except OSError:
        return 1
    numero = 1
    while numero in usati:
        numero += 1
    return numero


def evaluate(target: Path | str, root: Path | str | None = None) -> ScopeVerdict:
    """Decide whether a write to ``target`` is covered.

    Args:
        target: The path about to be written.
        root: Root of AD Projects (default: the root of this checkout).

    Returns:
        The verdict, with a reason ready to be shown to the model or the user.
    """
    root_path = Path(root) if root is not None else ad_docs.DOCS_ROOT
    resolved = str(Path(target))

    # **Il motore e i progetti possono essere due cartelle diverse.**
    #
    # Il 2026-10-13, copiando il motore in AD-AGENTS-PROJECTS, e' emerso che il raggio di
    # un contract e' scritto **relativo ai progetti** (`11. Example Project/...`) mentre qui lo si
    # risolveva **rispetto al motore**: finche' i due stanno nella stessa cartella non si
    # vede, ma appena si separano **il permesso non copre piu' niente** e le scritture nei
    # progetti passano senza che nessuno le fermi.
    #
    # Quindi: se il percorso sta nella cartella dei progetti, i permessi si risolvono **li'**;
    # altrimenti rispetto al motore, che e' dove stanno le carte della macchina.
    # I registri (contratti, approvazioni) restano nella cartella del motore: e' li' che il
    # controllore li legge a ogni scrittura.
    # **Solo quando la cornice e' il motore.** Se chi chiama passa una radice sua —
    # una cartella di prova, un progetto singolo — QUELLA e' la cornice, e non si
    # scavalca: il 2026-10-13 la prima versione lo faceva, e le prove dei test
    # (che girano dentro la cartella dei progetti) smettevano di essere coperte.
    progetti = ad_docs.PROGETTI_ROOT
    relative = relative_to_root(target, root_path)
    if root_path == ad_docs.DOCS_ROOT and progetti != root_path:
        fuori = relative_to_root(target, progetti)
        if fuori and not str(fuori).startswith(".."):
            relative = fuori
    folder = protected_segment(relative)
    governance = governance_segment(relative)

    # --- i progetti si numerano --------------------------------------------
    #
    # Il 2026-10-13 ho misurato: **un progetto senza numero PASSA il cancello.** Non
    # e' numerato, quindi `protected_segment` non lo riconosce, quindi nessun permesso
    # serve e nessuna approvazione — e chi ci scrive dentro non viene fermato da
    # niente. Il CEO ha chiesto che l'AI *ricordi* che i progetti si numerano: non lo
    # ricordava perche' **non era scritto da nessuna parte, e nessun controllo lo
    # pretendeva**. Ora lo pretende.
    #
    # La scelta e' la (a) del CEO: **si blocca e si spiega**, e il rifiuto dice quale
    # numero usare. Un divieto senza il rimedio e' un vicolo cieco.
    if relative:
        testa = relative.split("/", 1)[0]
        if (
            folder is None
            and governance is None
            and testa not in CARTELLE_MACCHINA
            and not PROTECTED_DIR.match(testa)
            and (root_path / testa).is_dir()
        ):
            num = primo_numero_libero(root_path)
            return ScopeVerdict(
                resolved,
                relative,
                True,
                False,
                "",
                (
                    f'"{testa}" non e\' una cartella di macchina, e non e\' numerata.\n'
                    "**I progetti si numerano**: il numero e' cio' che dice al sistema "
                    "che quella cartella e' un prodotto — e quindi che va protetta con "
                    "un permesso e un'approvazione.\n"
                    f"Senza numero, chiunque puo\' scriverci dentro senza che nessuno "
                    f"se ne accorga.\n"
                    f"Rimedio: rinominala in **{num}. {testa}**. "
                    f"Il prossimo numero libero e' {num}."
                ),
            )

    if folder is None and governance is None:
        return ScopeVerdict(resolved, relative or "", False, True, "", "")

    scope, reason = coverage(relative or "", root_path)
    if scope is not None:
        return ScopeVerdict(resolved, relative or "", True, True, scope.task_id, reason)
    if reason:
        return ScopeVerdict(resolved, relative or "", True, False, "", reason)

    if governance is not None:
        reason = (
            f'"{relative}" e\' un artefatto di GOVERNANCE ({governance}/), non una '
            "cartella prodotto.\n"
            "`.brain/` e' symlinkato in ~/.dsh/AGENTS.md e ~/.agents/skills/, e il "
            "plugin e' montato nel profilo: una scrittura qui cambia cosa fanno TUTTI "
            "gli agenti, in OGNI sessione. `tools/` e' l'autorita' che il plugin "
            "interroga.\n"
            "Rimedio: un contract con write_scope che includa "
            f'"{governance}/" e il marcatore '
            f"{approvals_dir(root_path)}/<task_id>.yaml approvato dal CEO."
        )
        return ScopeVerdict(resolved, relative or "", True, False, "", reason)

    scopes = load_write_scopes(root_path)
    # Il verdetto di proporzione, **dove il dolore si sente**: il cancello ha appena
    # detto che serve un permesso, e questo e' il momento in cui conta sapere se la
    # catena e' proporzionata a cosa si sta cambiando. Il 2026-10-10 una riga di
    # `.gitignore` e' costata 6 file e 8 passaggi. Misura e consiglia: non esenta
    # niente (DEC-0040).
    sproporzione = ""
    nome = Path(relative).name.lower()
    if nome in ad_contract.PERCORSI_IGIENE:
        sproporzione = (
            f'\n"{relative}" e\' **igiene del repository**, non prodotto: cambiarlo non '
            "cambia cosa fa il prodotto.\n"
            "Con l'invariante 13 la catena completa chiede 4 documenti DENTRO il progetto "
            "(tappa, passo, rapporto, Blueprint). Per una riga reversibile e' "
            "**sproporzionata** — e se il consenso debba stare sulla tappa o sul permesso "
            "e' una decisione del CEO (DEC-0040).\n"
        )
    reason = (
        f'Nessun task contract copre "{relative}".\n'
        "Ogni lavoro su un prodotto parte da un task contract con write_scope "
        "(GOVERNANCE-AZIENDALE.md, TASK-CONTRACTS.md).\n"
        + sproporzione
        + "Rimedio: crea "
        f"{contracts_dir(root_path)}/<task_id>.yaml con\n"
        "  task_id: <id>\n"
        "  agent: <card-id>\n"
        "  write_scope:\n"
        f"    - {folder}/\n"
        f"e il marcatore {approvals_dir(root_path)}/<task_id>.yaml con approvato_da e data.\n"
        "Nessun contract attivo: "
        + (", ".join(sorted(s.task_id for s in scopes)) if scopes else "nessuno")
    )
    return ScopeVerdict(resolved, relative or "", True, False, "", reason)


def guard(target: Path | str, root: Path | str | None = None) -> None:
    """Rifiuta una scrittura che nessun contract approvato copre.

    Perche' la guardia sta **qui** e non dentro lo strumento: il plugin di
    enforcement intercetta i tool di scrittura, non le scritture fatte da uno
    script — l'euristica della shell non vede `python3 tools/blueprint.py render`.
    Quindi il controllo sta dentro lo strumento, e sta **una volta sola**: finche'
    viveva in `ad_milestone._guard`, gli altri strumenti che scrivono non lo
    chiamavano, e il 2026-10-11 `blueprint.py` ha scritto in un percorso che
    nessun contract copriva (ERR-0026). Un varco negli strumenti sarebbe un varco
    nell'enforcement (DEC-0008).

    `root` e' l'**autorita'**, non la cartella su cui lo strumento sta lavorando:
    il default e' la root di AD Projects. Uno strumento che passasse la propria
    `--root` sceglierebbe l'albero in cui cercare i permessi *e* la classe di
    percorso da proteggere: avrebbe in mano il modo di aggirare la guardia. Il
    parametro esiste per i test, che costruiscono una root finta in una cartella
    temporanea; gli strumenti chiamano `guard(percorso)` e basta.

    Questa frase era **scritta e non eseguita**: `evaluate` risponde `allowed` ai
    percorsi fuori dall'albero — e' la risposta giusta alla domanda «questo
    percorso e' protetto?», che e' un'altra domanda — e la guardia ereditava
    quell'uscita, quindi `verbali.py nuovo --root /tmp/x` scriveva fuori senza
    incontrare nessun contract (ERR-0026, provato dal gate). E' la stessa lezione
    del primo ERR-0026: una difesa promessa e non implementata fa smettere di
    guardare. Fuori dall'albero l'autorita' **non ha** giurisdizione: non si
    concede un'eccezione, si rifiuta — e la richiesta e' un errore di chi invoca.

    Args:
        target: Il file o la cartella che sta per essere scritta.
        root: La root dell'autorita' (default: la root di AD Projects).

    Raises:
        PermissionError: Se il percorso sta fuori dall'albero di autorita', o se
            nessun contract approvato lo copre. Il messaggio dice cosa manca e
            come rimediare.
    """
    root_path = Path(root) if root is not None else ad_docs.DOCS_ROOT
    if relative_to_root(target, root_path) is None:
        raise PermissionError(
            f'"{Path(target)}" non sta sotto la root di autorita\' ({root_path}).\n'
            "Fuori da quell'albero nessun contract puo' coprire il percorso: i "
            "permessi si cercano in `contratti/`, e li' non ce ne sono. Non e' "
            "quindi un permesso da concedere, ma un errore di chi invoca: `--root` "
            "sceglie dove uno strumento legge e scrive, non dove cerca "
            "l'autorizzazione.\n"
            "Rimedio: scrivi dentro l'albero di autorita' — di norma si omette "
            f"`--root` e vale {root_path}."
        )
    verdict = evaluate(target, root_path)
    if not verdict.allowed:
        raise PermissionError(verdict.reason)


def protected_folders(root: Path | str | None = None) -> tuple[str, ...]:
    """Return the names of the numbered product folders of ``root``."""
    root_path = Path(root) if root is not None else ad_docs.DOCS_ROOT
    if not root_path.is_dir():
        return ()
    return tuple(
        sorted(
            entry.name
            for entry in root_path.iterdir()
            if entry.is_dir() and PROTECTED_DIR.match(entry.name)
        )
    )


def _mentions_protected_path(command: str, folders: tuple[str, ...]) -> str | None:
    """Return the product folder a command addresses as a path, or None.

    Cerca ``<cartella>/`` nel comando, cosi' ``rm -rf "13. Commercialista
    Digitale/src"`` viene riconosciuto anche se il nome contiene spazi. Un
    semplice accenno al nome senza percorso non basta.
    """
    normalized = command.replace("\\ ", " ")
    for folder in folders:
        if f"{folder}/" in normalized:
            return folder
    return None


def _shell_tokens(command: str) -> tuple[str, ...]:
    """Split a shell command into raw tokens. Shallow on purpose."""
    return tuple(token for token in re.split(r"[\s|;&()<>'\"`=]+", command) if token)


#: Un cambio di directory dentro il comando: ``cd <destinazione>``.
_CD = re.compile(r"(?:^|[;&|]\s*)cd\s+([^;&|]+)")

#: Scritture dentro una stringa: ``python3 -c "open(...,'w')"``, ``node -e "..."``.
_SCRITTURA_OPACA = re.compile(
    r"(?:^|[;&|]\s*)(?:python3?|node|perl|ruby|php)\s+(?:-c|-e)\s"
)

#: Un `.md` o un documento normativo modificato a mano nella radice.
_ESTENSIONI_TESTUALI = (".md", ".txt", ".yaml", ".yml")


def _destinazioni_cd(command: str, base: Path) -> list[Path]:
    """Le directory in cui il comando si sposta, risolte rispetto a ``base``.

    Un ``cd`` che non si riesce a risolvere (variabile, backtick, vuoto) produce una
    lista con ``base`` — cioe' «non lo so» — che il chiamante tratta come incertezza.
    """
    trovate: list[Path] = []
    for corrispondenza in _CD.finditer(command):
        pezzo = corrispondenza.group(1).strip().strip("\"'")
        if not pezzo or pezzo.startswith("-") or "$" in pezzo or "`" in pezzo:
            trovate.append(base)  # incomprensibile: si resta sulla base, e si dira' cosi'
            continue
        trovate.append(Path(pezzo) if pezzo.startswith("/") else base / pezzo)
    return trovate


def bash_target(
    command: str, root: Path | str | None = None, cwd: Path | str | None = None
) -> str | None:
    """Return the protected path a shell command appears to modify, or None.

    E' un'euristica, e resta un'euristica: il confine affidabile e' il ``write_scope``.
    Ma un'euristica che ignora il ``cd`` e' un permesso generale, non un'euristica
    (``ERR-0085``): ``cd "<progetto>" && echo x > file`` passava perche' il percorso
    relativo veniva risolto sulla cwd sbagliata. Qui il ``cd`` **cambia la base**, e si
    controllano tutte le basi che il comando attraversa — non solo la prima.
    """
    root_path = Path(root) if root is not None else ad_docs.DOCS_ROOT
    if not isinstance(command, str) or not command.strip():
        return None

    # Scritture opache: il percorso e' dentro una stringa, e non si puo' dire dove.
    # Non si indovina: si dichiara che il comando non e' verificabile, e chi decide
    # (il chiamante) nega — l'incertezza non e' un permesso.
    if _SCRITTURA_OPACA.search(command) and any(
        segnale in command for segnale in ("open(", "writeFile", "write_text", ">", "io.open")
    ):
        return "<scrittura-opaca>"

    # Si analizza la STRUTTURA del comando, non il testo dentro le stringhe: un `>`
    # fra apici e' un pattern di ricerca (`grep -n 'a>b' file`), non una redirezione.
    # I percorsi si cercano ancora sul comando intero, piu' sotto: un percorso dentro
    # una stringa resta un percorso.
    struttura = _senza_stringhe(command)

    if not any(pattern.search(struttura) for pattern in MUTATION_PATTERNS):
        return None

    folder = _mentions_protected_path(command, protected_entries(root_path))
    if folder:
        return f"{folder}/"

    base = Path(cwd) if cwd is not None else root_path
    for destinazione in _destinazioni_cd(command, base):
        trovato = _percorso_del_comando(command, destinazione, root_path)
        if trovato is not None:
            return trovato
    return _percorso_del_comando(command, base, root_path)


def _percorso_del_comando(command: str, base: Path, root_path: Path) -> str | None:
    """Il percorso protetto che il comando tocca, con quella base."""
    explicit = [token for token in _shell_tokens(command) if "/" in token]
    if explicit:
        for token in explicit:
            if token.startswith("/"):
                candidate = Path(token)
            elif token.startswith("~"):
                candidate = Path(token).expanduser()
            else:
                candidate = base / token
            segment = _any_segment(relative_to_root(candidate, root_path))
            if segment:
                return f"{segment}/"
        return None  # il comando nomina un percorso, ed e' fuori dai progetti

    # Nessun percorso esplicito: la mutazione agisce sulla directory di lavoro.
    return _any_segment(relative_to_root(base, root_path))


def evaluate_command(
    command: str, root: Path | str | None = None, cwd: Path | str | None = None
) -> ScopeVerdict:
    """Decide whether a shell command may run.

    Args:
        command: The shell command about to execute.
        root: Root of AD Projects (default: the root of this checkout).
        cwd: Working directory of the command, when known.

    Returns:
        The verdict, with a reason ready to be shown to the model or the user.
    """
    root_path = Path(root) if root is not None else ad_docs.DOCS_ROOT
    target = bash_target(command, root_path, cwd)
    if target is None:
        return ScopeVerdict(command, "", False, True, "", "")

    scope, covered_reason = coverage(target, root_path)
    if scope is not None:
        return ScopeVerdict(command, target, True, True, scope.task_id, covered_reason)
    if covered_reason:
        return ScopeVerdict(command, target, True, False, "", covered_reason)

    radice = target.split("/", 1)[0]
    if governance_segment(target) is not None and radice:
        reason = (
            f'Il comando sembra modificare "{target}", che e\' un artefatto di GOVERNANCE.\n'
            "`.brain/` e' symlinkato in ~/.dsh/AGENTS.md e ~/.agents/skills/, e il plugin "
            "e' montato nel profilo: una scrittura qui cambia cosa fanno TUTTI gli agenti, "
            "in OGNI sessione. `tools/` e' l'autorita' che il plugin interroga.\n"
            f'Serve un contract con write_scope che includa "{radice}/" e il marcatore '
            "di approvazione del CEO in approvazioni/.\n"
            "Se il comando e' di sola lettura, riformulalo senza operatori di scrittura."
        )
        return ScopeVerdict(command, target, True, False, "", reason)

    reason = (
        f'Il comando sembra modificare "{target}", dentro una cartella prodotto.\n'
        "Gli agenti non toccano un progetto se non e' chiamato: serve un task contract "
        f"in {contracts_dir(root_path)}/ con write_scope che includa \"{target}\" "
        "(GOVERNANCE-AZIENDALE.md, TASK-CONTRACTS.md).\n"
        "Se il comando e' di sola lettura, riformulalo senza operatori di scrittura."
    )
    return ScopeVerdict(command, target, True, False, "", reason)


def policy(root: Path | str | None = None) -> dict[str, Any]:
    """Return the enforcement view of the current state.

    Args:
        root: Root of AD Projects (default: the root of this checkout).

    Returns:
        A JSON-serialisable snapshot: root, protected folders, contracts and approvals.
    """
    root_path = Path(root) if root is not None else ad_docs.DOCS_ROOT
    scopes = load_write_scopes(root_path)
    approvals = load_approvals(root_path)
    folders = list(protected_folders(root_path))
    return {
        "root": str(root_path),
        "contracts_dir": str(contracts_dir(root_path)),
        "approvals_dir": str(approvals_dir(root_path)),
        "protected_folders": folders,
        "governance_paths": list(GOVERNANCE_PATHS),
        "contracts": [
            {
                "task_id": scope.task_id,
                "agent": scope.agent,
                "status": scope.status,
                "write_scope": list(scope.scopes),
                "source": str(scope.source),
                "approved": scope.task_id in approvals,
            }
            for scope in scopes
        ],
        "approvals": [
            {
                "task_id": approval.task_id,
                "approvato_da": approval.approvato_da,
                "data": approval.data,
                "piano": approval.piano,
                "source": str(approval.source),
            }
            for approval in approvals.values()
        ],
    }
