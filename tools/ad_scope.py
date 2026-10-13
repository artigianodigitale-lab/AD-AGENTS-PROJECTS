"""Ambito di scrittura: quale percorso e' coperto da quale task contract.

Il layer di enforcement di runtime (`DEC-0003`) non decide da solo: chiede a
questo modulo. La regola e' quella della governance — un lavoro su un prodotto
parte da un task contract, e il contract dichiara dove si puo' scrivere.

I contract operativi vivono in ``AD Projects/contratti/``: un file YAML per
task, con gli stessi campi di ``TASK-CONTRACTS.md`` piu' ``write_scope``.
"""

from __future__ import annotations

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

#: Una cartella prodotto e' numerata: ``5.APP-Artigiano-Digitale``, ``11. Modelbel``.
#: Solo queste sono protette: gli strumenti e i documenti restano scrivibili.
PROTECTED_DIR = re.compile(r"^\d+\.")

#: Stati che rendono un contract operativo. Qualsiasi altro valore non copre.
ACTIVE_STATES: tuple[str, ...] = ("active", "attivo", "approvato")

#: Comandi che possono modificare il filesystem. Conservativo di proposito:
#: bloccare un comando di sola lettura e' un fastidio, lasciar passare una
#: scrittura su un progetto e' un danno.
MUTATION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(^|[^=\d])>>?(?!=)"),  # redirezione, esclusi >= e =>
    re.compile(r"\b(rm|mv|cp|tee|truncate|dd|touch|mkdir|rmdir|chmod|chown|ln|patch)\b"),
    re.compile(r"\bsed\b[^\n]*\s-i(\s|$)"),
    re.compile(r"\bgit\s+(checkout|reset|clean|restore|apply|stash)\b"),
    re.compile(
        r"\b(npm|pnpm|yarn|pip|pip3|poetry|uv)\s+(install|add|remove|ci|sync|uninstall)\b"
    ),
)

#: Mutazioni senza percorso esplicito: per queste conta la directory di lavoro.
#: Non serve un elenco: la regola e' "nessun argomento con '/' -> vale la cwd".


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


def _expired(value: Any) -> bool:
    """Return True when an ISO ``expires`` value is in the past."""
    if not isinstance(value, str) or not value.strip():
        return False
    text = value.strip().replace("Z", "+00:00")
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return False
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment < datetime.now(UTC)


def load_write_scopes(root: Path | str) -> list[WriteScope]:
    """Load every operational contract that declares a ``write_scope``.

    Args:
        root: Root of AD Projects.

    Returns:
        The contracts, sorted by file name. Files without ``write_scope``,
        with an unknown state or expired are skipped: non coprono nulla.
    """
    directory = contracts_dir(Path(root))
    if not directory.is_dir():
        return []
    found: list[WriteScope] = []
    for path in sorted(set(directory.rglob("*.yaml")) | set(directory.rglob("*.yml"))):
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


def approvals_dir(root: Path | str) -> Path:
    """Return the approvals directory for ``root``."""
    return Path(root) / APPROVALS_DIR


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
    for path in sorted(set(directory.rglob("*.yaml")) | set(directory.rglob("*.yml"))):
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
        found[task_id] = Approval(
            task_id=task_id,
            approvato_da=approver,
            data=moment,
            piano=str(data.get("piano", "")).strip(),
            source=path,
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
            # L'ORDINE E' consenso (7) -> permesso (8): il permesso si scrive DOPO il
            # consenso e PRIMA della tappa. La condizione era invertita — bloccava
            # il caso giusto e lasciava passare il retrodatato — e il 2026-10-13 l'ha
            # trovata la dimostrazione del cancello, non un controllo. Vedi ERR-0052.
            if scope.aperto and str(scope.aperto)[:10] < str(approval.data)[:10]:
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
    # un contract e' scritto **relativo ai progetti** (`11. Modelbel/...`) mentre qui lo si
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
    # niente. il CEO ha chiesto che l'AI *ricordi* che i progetti si numerano: non lo
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


def bash_target(
    command: str, root: Path | str | None = None, cwd: Path | str | None = None
) -> str | None:
    """Return the protected path a shell command appears to modify, or None.

    E' un'euristica, non un confine affidabile: il runtime non considera
    l'analisi della shell un seam sicuro. Un comando che cambia directory con
    ``cd`` e poi scrive in modo relativo non viene visto.
    """
    root_path = Path(root) if root is not None else ad_docs.DOCS_ROOT
    if not isinstance(command, str) or not command.strip():
        return None
    if not any(pattern.search(command) for pattern in MUTATION_PATTERNS):
        return None

    folder = _mentions_protected_path(command, protected_entries(root_path))
    if folder:
        return f"{folder}/"

    base = Path(cwd) if cwd is not None else root_path
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
