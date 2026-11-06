"""Validazione deterministica di un Task Contract (TASK-CONTRACTS.md, RUNTIME.md).

Il validatore applica le regole scritte nei documenti normativi e nient'altro.
Distingue due livelli:

* ``VIOLATION`` — una regola scritta e' violata: il task non parte.
* ``WARNING`` — il documento non permette di verificare la condizione: la
  decisione resta all'orchestratore, ma il buco va visto.

Ogni messaggio dice quale documento impone la regola.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

import ad_docs
import ad_gates
import ad_milestone
import ad_registry
import ad_scope

VIOLATION = "VIOLATION"
WARNING = "WARNING"

#: Campi senza i quali il contract non e' un contract (TASK-CONTRACTS.md).
REQUIRED_FIELDS: tuple[str, ...] = (
    "task_id",
    "domain",
    "agent",
    "objective",
    "inputs",
    "acceptance_criteria",
    "constraints",
    "outputs",
    "required_gates",
    "approval",
    "priority",
    "impact_forecast",
)

#: Priorita' del contract (DEC-0012). Se una modifica tocca piu' livelli vale il massimo.
PRIORITIES: tuple[str, ...] = ("P0", "P1", "P2", "P3", "P4")

#: Livelli di impatto ammessi nella previsione obbligatoria prima del diff.
IMPACT_LEVELS: tuple[str, ...] = ("NONE", "LOW", "MED", "HIGH", "UNKNOWN")

#: Aree su cui la previsione di impatto deve pronunciarsi.
IMPACT_AREAS: tuple[str, ...] = (
    "data",
    "schema",
    "auth",
    "security",
    "shared_platform",
    "product",
)

#: Obbligatori quando il contract scrive in una cartella prodotto (invariante 13).
MILESTONE_FIELD = "milestone"
SPRINT_FIELD = "sprint"

#: Prodotti ammessi dallo schema del contract.
KNOWN_PRODUCTS: tuple[str, ...] = (
    "artigiano-digitale",
    "ad-stock-tracker",
    "biocimatica",
    "altro",
)

#: Soglia oltre la quale MODEL-ROUTING.md parla di escalation e non di rework.
MAX_RETRIES_HINT = 2

_DECISION_ID = re.compile(r"^DEC-\d+", re.IGNORECASE)


@dataclass(frozen=True)
class Finding:
    """Un esito della validazione."""

    level: str
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.level} [{self.code}] {self.message}"


class ContractError(Exception):
    """Raised when the contract file cannot be read or parsed."""


def load(path: str | Path) -> dict[str, Any]:
    """Load a contract from a YAML file.

    Args:
        path: Path to the contract.

    Returns:
        The contract mapping.

    Raises:
        ContractError: If the file is missing, unreadable or not a mapping.
    """
    file_path = Path(path)
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ContractError(
            f"contract non e' testo UTF-8 valido '{file_path}': {exc.reason}"
        ) from exc
    except OSError as exc:
        raise ContractError(f"contract illeggibile '{file_path}': {exc}") from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ContractError(f"YAML non valido in '{file_path}': {exc}") from exc
    if not isinstance(data, dict):
        raise ContractError(f"'{file_path}' non contiene una mappatura")
    return data


def _as_list(value: Any) -> list[Any]:
    """Return ``value`` as a list, wrapping scalars."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def as_list(value: Any) -> list[Any]:
    """Public form of the scalar/list normaliser, for sibling modules."""
    return _as_list(value)


def _non_empty_text(value: Any) -> bool:
    """Return True when ``value`` is a non-blank string."""
    return isinstance(value, str) and bool(value.strip())


def resolve_decision_record(value: str) -> Path | None:
    """Resolve a Decision Record reference to a file.

    Args:
        value: A record id such as ``DEC-0001`` or a path.

    Returns:
        The resolved path, or None when nothing matches.
    """
    decisions = ad_docs.DOCS_ROOT / "DECISIONI"
    candidate = Path(value)
    if candidate.suffix == ".md":
        resolved = candidate if candidate.is_absolute() else ad_docs.DOCS_ROOT / candidate
        return resolved if resolved.exists() else None
    if _DECISION_ID.match(value.strip()):
        matches = sorted(decisions.glob(f"{value.strip()}*.md"))
        if matches:
            return matches[0]
    return None


def _record_state(path: Path) -> str:
    """Return the ``stato`` declared by a Decision Record, or an empty string."""
    try:
        testo = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    blocks = re.findall(r"```ya?ml\s*\n(.*?)```", testo, re.DOTALL)
    for block in blocks:
        data = yaml.safe_load(block)
        if isinstance(data, dict) and "stato" in data:
            return str(data["stato"]).strip().lower()
    return ""


def _project_of(contract: dict[str, Any]) -> str | None:
    """Return the product folder this contract writes into, or None."""
    for prefix in as_list(contract.get("write_scope")):
        head = str(prefix).strip().strip('"').split("/", 1)[0]
        if ad_scope.PROTECTED_DIR.match(head):
            return head
    return None


# ---------------------------------------------------------------------------
# Il verdetto di proporzione
#
# Da dove viene: il 2026-10-10, per **una riga** di `.gitignore` su un progetto
# (che non era nemmeno un repository Git), il sistema ha chiesto un permesso, una
# milestone, un passo aperto, un rapporto — **6 file e 8 passaggi**.
#
# Il sistema sa dire «per questo serve una tappa». **Non sa dire «per questo non
# serve»** — e la differenza e' tutta li': un sistema che tratta allo stesso modo
# una riga di `.gitignore` e un refactor **insegna a bypassarlo**, e un bypass rende
# inutile qualunque cancello, compreso quello che stiamo costruendo.
#
# L'idea viene da Graphify (`studio/graphify-8`): il suo report comincia con un
# **verdetto di utilita'** — «corpus is large enough that graph structure adds value».
# Uno strumento che dice quando **non** vale la pena usarlo.
#
# ATTENZIONE — questo NON cambia l'invariante 13: **misura e consiglia**.
# Nulla e' esentato. La decisione e' del CEO (DEC-0040).
# ---------------------------------------------------------------------------

#: I file che NON sono prodotto: igiene del repository, non funzionalita'.
#: Cambiarli non cambia cosa fa il prodotto.
PERCORSI_IGIENE = (
    ".gitignore", ".gitattributes", ".editorconfig", ".env.example",
    "license", "licence", "security.md", "contributing.md", "code_of_conduct.md",
)

#: Quanti percorsi restano "piccoli".
PERCORSI_POCHI = 5

#: I documenti che la catena completa chiede DENTRO il progetto.
DOCUMENTI_CATENA = ("Milestone N/REPORT.md", "Milestone N/Sprint M/PROMPT.md",
                    "Milestone N/Sprint M/REPORT.md", "BLUEPRINT.md")


def classe_della_scrittura(contract: dict, root: Path | str | None = None) -> dict:
    """Quanto costa, in proporzione a cosa cambia. **Misura, non esenta.**

    Restituisce `{"classe", "perche", "percorsi", "costo"}` dove `classe` e':
      - `igiene`  — tocca solo file di igiene del repository
      - `piena`   — tocca il prodotto, o e' grande, o non si sa
    """
    scopes = _as_list(contract.get("write_scope"))
    progetto = _project_of(contract)

    if progetto is None or not scopes:
        return {"classe": "piena", "perche": "non e' una scrittura dentro un progetto", "percorsi": scopes, "costo": []}

    # Il percorso DENTRO il progetto, senza il nome della cartella.
    dentro, cerimonia = [], []
    for voce in scopes:
        testo = str(voce).strip().strip('"')
        rel = testo[len(progetto):].lstrip("/") if testo.startswith(progetto) else testo
        # La cartella delle tappe NON e' parte della modifica: e' la **cerimonia**.
        # Il permesso deve contenerla perche' lo impone l'invariante 13 — ma se la
        # contassi come "cosa tocca", il verdetto direbbe sempre `piena` e non
        # direbbe mai niente. Il verdetto misura la **modifica**, non il permesso.
        if ad_milestone.PROJECT_DOCS in rel:
            cerimonia.append(rel)
        else:
            dentro.append(rel)

    if not dentro:
        return {"classe": "piena", "perche": "il permesso non nomina nessuna modifica", "percorsi": dentro, "costo": []}

    if len(dentro) > PERCORSI_POCHI:
        return {"classe": "piena", "perche": f"{len(dentro)} percorsi (piu' di {PERCORSI_POCHI})", "percorsi": dentro, "costo": []}

    di_igiene = [d for d in dentro if Path(d).name.lower() in PERCORSI_IGIENE]
    if len(di_igiene) != len(dentro):
        altro = sorted(set(d for d in dentro if d not in di_igiene))
        return {"classe": "piena", "perche": f"tocca anche {', '.join(altro[:3])}", "percorsi": dentro, "costo": []}

    return {
        "classe": "igiene",
        "perche": f"tocca solo {', '.join(sorted(set(Path(d).name for d in dentro)))}: igiene del repository, non il prodotto",
        "percorsi": dentro,
        "cerimonia": cerimonia,
        "costo": list(DOCUMENTI_CATENA),
    }


# ---------------------------------------------------------------------------
# Un percorso, un titolare
#
# Da dove viene: il 2026-10-13 ho misurato e trovato **cinque permessi attivi su
# `tools/`**, quattro su `.brain/`, cinque sulla stessa tappa di Marketing Factory.
# Il cancello lasciava passare tutti, **perche' tutti erano validi** — e un percorso
# con due titolari **non ha un titolare**: se qualcosa si rompe nessuno sa di chi era.
#
# Tre cause, e qui si cura la prima: due permessi che dichiarano **lo stesso** percorso
# sono un conflitto vero. Due che si **contengono** (una cartella e un file dentro)
# non lo sono per forza — possono toccare file diversi — ma vanno guardati.
#
# La causa profonda resta un'altra, e non si cura qui: **un permesso non finisce
# quando il lavoro finisce.** Lo dice DEC-0054: chi esegue chiude il proprio contract.
# ---------------------------------------------------------------------------


#: I contract che erano ATTIVI **prima** che la regola esistesse (2026-10-13).
#:
#: Perche' esistono: la regola nasce il 2026-10-13, e il giorno prima c'erano gia'
#: **cinque titolari su `tools/`** e **cinque sulla stessa tappa** di Marketing
#: Factory. Quei permessi sono di **un'altra sessione**, sono stati dati in buona
#: fede, e **non si rendono invalidi da un giorno all'altro**: saremmo noi a rompere
#: qualcosa che funzionava. E' lo stesso criterio dei rapporti di passo e di
#: `DEC-0037` per i verbali — si dichiara il passato, si impone il presente.
#:
#: **La clausola vale per QUESTI contract, non per gli altri**: un contract NUOVO che
#: si sovrappone a uno di questi e' una violazione, perche' aggiungerebbe al mucchio.
#: E i conflitti restano **visibili**: `contract_scope.py titolari` li mostra sempre.
#:
#: **Questa lista deve SVUOTARSI.** Ogni voce e' un lavoro che il CEO deve chiudere o
#: restringere. Una clausola di nonno che resta piena e' un permesso permanente.
ESENTI_DALLA_REGOLA = (
    "ADMF-007",  # tools/ + la tappa di Marketing Factory
    "ADMF-008",  # tools/ + .brain/
    "ADMF-009",  # la tappa di Marketing Factory, con altri quattro
    "ADMF-010",
    "ADMF-012",
    "ADMF-013",
)


def conflitti_di_raggio(contract: dict, root: Path | str | None = None) -> tuple[list[str], list[str]]:
    """(violazioni, avvisi) fra il raggio di questo contract e i permessi gia' attivi.

    Il contract **non** e' in conflitto con se stesso: si esclude il proprio `task_id`,
    altrimenti un contract gia' scritto non si potrebbe piu' validare.
    """
    import ad_scope

    base = Path(root) if root is not None else ad_docs.DOCS_ROOT
    mio = str(contract.get("task_id", ""))
    miei = [str(v).strip() for v in _as_list(contract.get("write_scope"))]
    if not miei:
        return [], []

    violazioni: list[str] = []
    avvisi: list[str] = []
    try:
        try:
            attivi = ad_scope.load_write_scopes(base)
        except UnicodeDecodeError as errore:
            return [
                "impossibile leggere i write_scope: un contract in contratti/ non e' UTF-8 "
                f"({errore.reason}): il controllo 'un percorso un titolare' e' spento finche' "
                "quel file non torna leggibile"
            ], []
    except Exception:  # noqa: BLE001
        return [], []  # senza il registro non si accusa nessuno

    for scope in attivi:
        if scope.task_id == mio:
            continue
        altrui = [str(v).strip() for v in scope.scopes]
        for percorso in miei:
            if percorso in altrui:
                violazioni.append(
                    f'"{percorso}" e\' gia\' di {scope.task_id}, che e\' ATTIVO. '
                    "Un percorso con due titolari non ha un titolare: chiudi quello, "
                    "oppure restringi il tuo raggio ai FILE (DEC-0054)"
                )
                continue
            for altro in altrui:
                if percorso.startswith(altro) or altro.startswith(percorso):
                    avvisi.append(
                        f'"{percorso}" e "{altro}" ({scope.task_id}) si contengono: '
                        "possono toccare file diversi, ma guarda se e' voluto"
                    )
    return violazioni, avvisi


def digest_revisione(dati: dict[str, Any]) -> str:
    """The ONLY formula of the revision seal (ENG-010, ERR-0059).

    La formula stava anche in `tests/gate_kit.py` e i due posti sono divergiti: il
    lucchetto accusa di manomissione le revisioni autentiche. Da qui in avanti la
    formula vive qui; il kit la importa.
    """
    import hashlib
    import json

    immutabile = {
        "tool": dati.get("tool"),
        "task_id": dati.get("task_id"),
        "revision": dati.get("revision"),
        "frozen_at": dati.get("frozen_at"),
        "files": dati.get("files"),
        "expected": dati.get("expected"),
        "dirs": dati.get("dirs"),
        "subdirs": dati.get("subdirs"),
    }
    testo = json.dumps(immutabile, sort_keys=True, ensure_ascii=False)
    return "rev_" + hashlib.sha256(testo.encode("utf-8")).hexdigest()


def digest_revisione_legacy(dati: dict[str, Any]) -> str:
    """La formula pre-marcatore (ENG-008 R2), riconosciuta per leggere i sigilli vecchi."""
    import hashlib
    import json

    immutabile = {
        "task_id": dati.get("task_id"),
        "revision": dati.get("revision"),
        "frozen_at": dati.get("frozen_at"),
        "files": dati.get("files"),
        "expected": dati.get("expected"),
        "dirs": dati.get("dirs"),
    }
    testo = json.dumps(immutabile, sort_keys=True, ensure_ascii=False)
    return "rev_" + hashlib.sha256(testo.encode("utf-8")).hexdigest()


def digest_chiusura_legacy(dati: dict[str, Any]) -> str:
    """La formula di chiusura pre-marcatore (ENG-008 R2)."""
    import hashlib
    import json

    immutabile = {
        "task_id": dati.get("task_id"),
        "revision": dati.get("revision"),
        "frozen_at": dati.get("frozen_at"),
        "files": dati.get("files"),
        "expected": dati.get("expected"),
        "dirs": dati.get("dirs"),
        "gate": "closed",
        "closed_at": dati.get("closed_at"),
        "evidenze": dati.get("evidenze"),
    }
    testo = json.dumps(immutabile, sort_keys=True, ensure_ascii=False)
    return "close_" + hashlib.sha256(testo.encode("utf-8")).hexdigest()


def digest_chiusura(dati: dict[str, Any]) -> str:
    """The ONLY formula of the closure seal (ENG-010, ERR-0059)."""
    import hashlib
    import json

    immutabile = {
        "tool": dati.get("tool"),
        "task_id": dati.get("task_id"),
        "revision": dati.get("revision"),
        "frozen_at": dati.get("frozen_at"),
        "files": dati.get("files"),
        "expected": dati.get("expected"),
        "dirs": dati.get("dirs"),
        "subdirs": dati.get("subdirs"),
        "gate": "closed",
        "closed_at": dati.get("closed_at"),
        "evidenze": dati.get("evidenze"),
    }
    testo = json.dumps(immutabile, sort_keys=True, ensure_ascii=False)
    return "close_" + hashlib.sha256(testo.encode("utf-8")).hexdigest()


def gate_status(
    contract: dict[str, Any], root: Path | str | None = None
) -> tuple[str | None, str]:
    """Return (codice, messaggio) sullo stato del gate di un contract chiuso.

    ENG-008 / DEC-0062. Il congelamento non e' piu' una nota di disciplina:

        block  il contract e' chiuso e il gate NON risulta chiuso (o la revisione e'
               illeggibile, o il sigillo non combacia): chiusura prematura o manomessa
        warn   la revisione manca, o e' in formato legacy senza stato del gate: la
               chiusura non e' verificabile (compatibilita' con i contract storici,
               dichiarata, non nascosta)
        None   nessun problema
    """
    import yaml

    task = str(contract.get("task_id") or "").strip()
    stato = str(contract.get("status") or "").strip().lower()
    if not task or stato not in ("closed", "chiuso"):
        return None, ""
    base = Path(root) if root is not None else ad_docs.DOCS_ROOT
    cartella = base / "evidenze"
    candidati = [
        percorso
        for percorso in cartella.glob("*-revisione.yaml")
        if percorso.stem.lower() == f"{task}-revisione".lower()
    ]
    if not candidati:
        return "warn", (
            f"{task}: nessuna revisione congelata per questo contract: la chiusura non e' "
            "verificabile dal gate (contract storico, o il file di congelamento e' stato "
            "cancellato). I contract nuovi hanno sempre la revisione"
        )
    percorso = candidati[0]
    try:
        dati = yaml.safe_load(percorso.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as errore:
        return "block", (
            f"{task}: revisione di congelamento illeggibile ({errore.__class__.__name__}): "
            "la chiusura NON e' verificabile. Ripristina il file o rifai il gate"
        )
    if not isinstance(dati, dict):
        return "block", f"{task}: la revisione di congelamento non e' una mappatura"
    if str(dati.get("task_id")) != task:
        return "block", (
            f"{task}: la revisione di congelamento e' del task {dati.get('task_id')!r}: "
            "una revisione copiata da un altro task non chiude questo gate"
        )

    sigillo = dati.get("digest")
    formato_nuovo = dati.get("tool") == "gate_kit"
    if formato_nuovo and not (isinstance(sigillo, str) and sigillo):
        return "block", (
            f"{task}: revisione di formato nuovo SENZA sigillo: non e' verificabile"
        )
    if isinstance(sigillo, str) and sigillo:
        if formato_nuovo:
            sigillo_valido = sigillo == digest_revisione(dati)
        else:
            sigillo_valido = sigillo in (digest_revisione(dati), digest_revisione_legacy(dati))
        if not sigillo_valido:
            return "block", (
                f"{task}: il sigillo della revisione non combacia: il file di congelamento "
                "e' stato modificato a mano"
            )

    if "gate" not in dati:
        if formato_nuovo:
            return "block", f"{task}: revisione di formato nuovo senza stato del gate"
        return "warn", (
            f"{task}: revisione legacy senza stato del gate: chiusura non verificabile "
            "(accettata per i contract storici)"
        )
    valore = dati.get("gate")
    if not isinstance(valore, str) or valore.strip().lower() != "closed":
        return "block", (
            f"{task}: il contract e' chiuso ma il gate e' ancora aperto (o non valido). "
            f"La chiusura e' prematura: chiudere il gate dopo il verdetto "
            f"(python3 tests/gate_kit.py close {task})"
        )
    # --- stato del gate: vale per entrambi i formati -------------------------
    valore = dati.get("gate")
    gate_chiuso = isinstance(valore, str) and valore.strip().lower() == "closed"
    if not gate_chiuso:
        return "block", (
            f"{task}: il contract e' chiuso ma il gate e' ancora aperto (o non valido: "
            f"{valore!r}). La chiusura e' prematura: chiudere il gate dopo il verdetto "
            f"(python3 tests/gate_kit.py close {task})"
        )

    if not formato_nuovo:
        # Legacy: la chiusura e' registrata ma il suo sigillo appartiene a un formato
        # storico; il kit la legge con la formula del suo tempo. Avviso dichiarato.
        if "closed_digest" in dati:
            chiusure_valide = {
                digest_chiusura_legacy(dati),
                digest_chiusura(dati),
            }
            if dati.get("closed_digest") not in chiusure_valide:
                return "block", (
                    f"{task}: sigillo di chiusura legacy non combacia: chiusura manomessa"
                )
        return "warn", (
            f"{task}: revisione in formato legacy (senza marcatore 'tool: gate_kit'): "
            "chiusura registrata ma non verificabile dal kit (contract storico). "
            "DEC-0063: un file locale non firmato non distingue legacy da manomesso"
        )

    # --- formato nuovo: sigillo di chiusura, entrambe le evidenze, file presenti ---
    import hashlib

    evidenze = dati.get("evidenze")
    if not isinstance(evidenze, dict):
        return "block", f"{task}: campo 'evidenze' malformato nella revisione"
    if set(evidenze) != {"QA", "Code Review"}:
        return "block", (
            f"{task}: la chiusura non registra ENTRAMBE le evidenze del gate "
            f"(trovate: {sorted(evidenze)}): la regola vale anche in verifica"
        )
    for ruolo, impronta in evidenze.items():
        suffisso = "QA" if ruolo == "QA" else "CodeReview"
        percorso_ev = cartella / f"{task}-{suffisso}.yaml"
        if not percorso_ev.is_file():
            return "block", f"{task}: evidenza sparita dopo la chiusura: {percorso_ev.name}"
        if hashlib.sha256(percorso_ev.read_bytes()).hexdigest() != impronta:
            return "block", f"{task}: evidenza modificata dopo la chiusura: {percorso_ev.name}"
    if dati.get("closed_digest") != digest_chiusura(dati):
        return "block", (
            f"{task}: il gate risulta chiuso ma il SIGILLO DI CHIUSURA non combacia "
            f"(o manca): la chiusura non e' quella registrata dal kit"
        )
    return None, ""


def validate(
    contract: dict[str, Any],
    registry: dict[str, ad_registry.Card],
    root: Path | str | None = None,
) -> list[Finding]:
    """Validate a contract against the normative documents.

    Args:
        contract: The contract mapping.
        registry: The card registry.

    Returns:
        Every finding, violations first.
    """
    findings: list[Finding] = []

    def violation(code: str, message: str) -> None:
        findings.append(Finding(VIOLATION, code, message))

    def warning(code: str, message: str) -> None:
        findings.append(Finding(WARNING, code, message))

    # --- il gate non e' ancora chiuso (ENG-008) ------------------------------
    codice_gate, messaggio_gate = gate_status(contract, root)
    if codice_gate == "block":
        violation("gate-aperto", messaggio_gate)
    elif codice_gate == "warn":
        warning("gate-non-verificabile", messaggio_gate)

    # --- forma del contract ------------------------------------------------
    for field_name in REQUIRED_FIELDS:
        if field_name not in contract:
            violation(
                f"missing-field:{field_name}",
                f"campo obbligatorio assente '{field_name}' (TASK-CONTRACTS.md, Schema)",
            )
    budget = contract.get("budget")
    if "budget" in contract and not isinstance(budget, dict):
        violation(
            "budget-non-mappa",
            "'budget' deve essere una mappatura (es. max_retries: 2): un valore scalare "
            "non e' interpretabile e farebbe crashare la validazione (ERR-0060)",
        )
    timestamps = contract.get("timestamps")
    if isinstance(timestamps, dict):
        for chiave, valore in timestamps.items():
            if not isinstance(valore, str):
                violation("timestamp-non-testo", f"timestamps.{chiave} non e' testo")

    scope = contract.get("write_scope")
    if "write_scope" in contract and not isinstance(scope, list):
        violation(
            "write-scope-non-lista",
            "'write_scope' deve essere una LISTA di percorsi relativi: un valore scalare "
            "viene iterato carattere per carattere e legge fuori dalla macchina (ENG-009)",
        )
    elif isinstance(scope, list):
        for voce in scope:
            if not isinstance(voce, str):
                violation(
                    "write-scope-voce-non-stringa",
                    f"'write_scope' contiene una voce non stringa: {voce!r} (ENG-009)",
                )
                continue
            testo = voce.strip()
            if not testo:
                violation("write-scope-vuota", "'write_scope' contiene una voce vuota (ENG-009)")
            elif "\x00" in testo:
                violation("write-scope-nul", f"'write_scope' contiene un byte NUL: {testo!r} (ENG-009)")
            elif len(testo) > 255:
                violation("write-scope-troppo-lunga", f"'write_scope': percorso troppo lungo ({len(testo)} caratteri) (ENG-009)")
            elif any(ord(carattere) > 127 for carattere in testo):
                violation("write-scope-non-ascii", f"'write_scope': percorso non ASCII: {testo!r} (ENG-009)")
            elif Path(testo).is_absolute():
                violation(
                    "write-scope-assoluto",
                    f"'write_scope': percorso assoluto non ammesso: {testo} — "
                    "un perimetro che esce dalla macchina non e' un perimetro (ENG-009)",
                )
            elif ".." in Path(testo).parts:
                violation(
                    "write-scope-traversal",
                    f"'write_scope': percorso con '..' non ammesso: {testo} (ENG-009)",
                )

    for field_name in ("title", "product"):
        if field_name not in contract:
            warning(
                f"field-undeclared:{field_name}",
                f"campo '{field_name}' non dichiarato: lo schema di TASK-CONTRACTS.md lo prevede",
            )
    for field_name in ("task_id", "objective"):
        if field_name in contract and not _non_empty_text(contract[field_name]):
            violation(f"empty-field:{field_name}", f"campo '{field_name}' vuoto")

    if "budget" not in contract:
        warning(
            "budget-undeclared",
            "'budget.max_retries' non dichiarato: RUNTIME.md limita i tentativi entro quel valore",
        )
    else:
        budget_mappa = contract.get("budget") if isinstance(contract.get("budget"), dict) else {}
        retries = budget_mappa.get("max_retries")
        if retries is None:
            warning("budget-undeclared", "'budget.max_retries' non dichiarato")
        elif not isinstance(retries, int) or retries < 0:
            violation("budget-invalid", f"'budget.max_retries' non valido: {retries!r}")
        elif retries > MAX_RETRIES_HINT:
            warning(
                "retries-above-two",
                f"'budget.max_retries={retries}': MODEL-ROUTING.md ammette due tentativi "
                "locali, poi escalation. Verifica che non sia un loop.",
            )

    # --- DEC-0012: priorita' e previsione di impatto -----------------------
    priority = str(contract.get("priority", "")).strip().upper()
    if priority and priority not in PRIORITIES:
        violation(
            "priority-invalid",
            f"'priority' = '{priority}': ammesse {list(PRIORITIES)}",
        )

    forecast = contract.get("impact_forecast")
    if forecast is not None:
        if not isinstance(forecast, dict) or not forecast:
            violation(
                "impact-forecast-invalid",
                "'impact_forecast' deve essere una mappatura non vuota: e' il dovere di "
                "previsione prima del diff (DEC-0012)",
            )
        else:
            peggiore = ""
            for area, level in forecast.items():
                normalised = str(level).strip().upper()
                if area not in IMPACT_AREAS:
                    violation(
                        "impact-area-unknown",
                        f"area '{area}' non dichiarabile: ammesse {list(IMPACT_AREAS)}",
                    )
                if normalised not in IMPACT_LEVELS:
                    violation(
                        "impact-level-invalid",
                        f"impact_forecast.{area} = '{normalised}': ammessi {list(IMPACT_LEVELS)}",
                    )
                if normalised == "HIGH" and not peggiore:
                    peggiore = area
            if peggiore and priority and priority != "P0":
                violation(
                    "impact-priority-mismatch",
                    f"impact_forecast.{peggiore} = HIGH ma priority = {priority}: "
                    "se una modifica tocca piu' livelli vale il massimo, e HIGH impone P0 "
                    "(DEC-0012)",
                )

    # --- un percorso, un titolare ------------------------------------------
    # Due permessi attivi sullo STESSO percorso sono un conflitto vero: un percorso
    # con due titolari non ha un titolare. Due che si CONTENGONO (una cartella e un
    # file dentro) possono toccare file diversi, e allora e' un avviso da guardare.
    # DEC-0054; il 2026-10-13 c'erano cinque titolari su `tools/`.
    doppi, contenuti = conflitti_di_raggio(contract, root)
    # DRIFT-027: un contract CHIUSO non possiede piu' i percorsi. Se il successore li
    # ha presi, non e' un conflitto: e' la storia. Il contratto chiuso si rivalida
    # (serve per verificare la sua chiusura, non per assegnargli un raggio).
    if str(contract.get("status", "")).strip().lower() in ("closed", "chiuso"):
        for messaggio in doppi:
            warning(
                "percorso-pasato-al-successore",
                messaggio + " — il contract e' chiuso: il percorso vive nel successore (DRIFT-027)",
            )
        doppi = []
    if str(contract.get("task_id", "")) in ESENTI_DALLA_REGOLA:
        # Clausola di nonno: questo contract c'era prima della regola. I conflitti si
        # dicono **come avvisi**, con scritto che vanno chiusi — non si tacciono.
        for messaggio in doppi:
            warning(
                "percorso-gia-di-un-altro (esente: precedente alla regola)",
                messaggio + " — va chiuso o ristretto: la clausola deve svuotarsi (DEC-0054)",
            )
        doppi = []
    for messaggio in doppi:
        violation("percorso-gia-di-un-altro", messaggio)
    for messaggio in contenuti:
        warning("raggi-che-si-contengono", messaggio)

    # --- invariante 13: milestone e sprint per i contract di progetto -------
    progetto = _project_of(contract)
    if progetto is not None:
        tappa = contract.get(MILESTONE_FIELD)
        passo = contract.get(SPRINT_FIELD)
        for nome, valore in ((MILESTONE_FIELD, tappa), (SPRINT_FIELD, passo)):
            if valore is None:
                violation(
                    f"missing-field:{nome}",
                    f'il contract scrive in "{progetto}/": \'{nome}\' e\' obbligatorio '
                    "(invariante 13, TASK-CONTRACTS.md)",
                )
            elif isinstance(valore, bool) or not isinstance(valore, int) or valore < 1:
                violation(
                    f"invalid-{nome}",
                    f"'{nome}' deve essere un intero >= 1: {valore!r}",
                )
        # --- il verdetto di proporzione ---------------------------------
        # Non esenta niente: **misura e consiglia**. La decisione e' del CEO.
        classe = classe_della_scrittura(contract, root)
        if classe["classe"] == "igiene":
            warning(
                "catena-sproporzionata",
                f'questo contract tocca solo igiene ({classe["perche"]}): '
                f'{len(classe["percorsi"])} percorso/i, nessun file di prodotto. '
                f'La catena completa chiede {len(classe["costo"])} documenti dentro il '
                "progetto (" + ", ".join(classe["costo"]) + "). "
                "E' sproporzionata — e la scelta se il consenso debba stare sulla "
                "TAPPA o sul PERMESSO e' del CEO: invariante 13 dice la tappa (DEC-0040)",
            )

        aperto = (
            isinstance(tappa, int) and not isinstance(tappa, bool)
            and isinstance(passo, int) and not isinstance(passo, bool)
            and tappa >= 1 and passo >= 1
        )
        if aperto:
            base = Path(root) if root is not None else ad_docs.DOCS_ROOT
            prompt = ad_milestone.sprint_prompt(base / progetto, tappa, passo)
            if not prompt.is_file():
                # DRIFT-010 — non e' una violazione: e' lo stato di un contract che
                # sta per aprire il suo passo. Se fosse una violazione, il primo
                # contract di un progetto non potrebbe mai essere valido, perche'
                # per aprire il passo serve il contract e per avere il contract
                # serve il passo. Il confine vero e' **dove si scrive**, e lo
                # impone ad_scope: finche' il passo non e' aperto, il contract
                # copre soltanto la cartella di quel passo.
                warning(
                    "sprint-not-open",
                    f"lo sprint {tappa}/{passo} non e' ancora aperto: manca "
                    f"{prompt.relative_to(base)}. Il contract vale per APRIRLO — "
                    "finche' non lo apri, copre solo la cartella di quel passo. "
                    f'Aprilo con python3 tools/milestone.py new-sprint "{progetto}" {tappa}',
                )

    approval = contract.get("approval")
    if approval is not None:
        if not isinstance(approval, dict) or "human" not in approval:
            violation("approval-invalid", "'approval.human' assente o non mappatura")
        elif not isinstance(approval["human"], bool):
            violation("approval-invalid", "'approval.human' deve essere booleano")

    for field_name in ("inputs", "acceptance_criteria", "constraints", "outputs", "required_gates"):
        if field_name in contract and not _as_list(contract[field_name]):
            violation(f"empty-list:{field_name}", f"'{field_name}' vuoto")
    if isinstance(contract.get("outputs"), list) and "evidence" not in contract.get("outputs", []):
        warning(
            "outputs-without-evidence",
            "'outputs' non elenca 'evidence': senza evidenze il lavoro non e' DONE (AGENTI-V2.md)",
        )

    constraints = [str(item) for item in _as_list(contract.get("constraints"))]
    lowered = " ".join(constraints).lower()
    for needed, label in (
        ("do not edit this contract", "non modificare il contract"),
        ("do not change own permissions", "non modificare i propri permessi"),
    ):
        if needed not in lowered:
            warning(
                "constraint-missing-prohibition",
                f"il contract non vieta esplicitamente di {label} (TASK-CONTRACTS.md, Regole)",
            )

    # --- dominio, card e match --------------------------------------------
    domain = str(contract.get("domain", "")).strip().lower()
    agent_id = str(contract.get("agent", "")).strip()

    if domain not in ("technical", "business"):
        violation("domain-invalid", f"'domain' deve essere technical o business, trovato {domain!r}")

    card = registry.get(agent_id)
    if card is None:
        violation(
            "agent-unknown",
            f"'{agent_id}' non esiste nel registry: nessun match, STOP "
            "(SPECIALIZATION.md, TASK-CONTRACTS.md)",
        )
        return _sorted(findings)

    if domain in ("technical", "business") and card.domain != domain:
        violation(
            "agent-domain-mismatch",
            f"la card '{agent_id}' appartiene al dominio '{card.domain}', il contract dichiara "
            f"'{domain}': un orchestratore non assegna card dell'altro dominio "
            "(GOVERNANCE-AZIENDALE.md)",
        )

    if not card.inactive:
        violation(
            "agent-status",
            f"la card '{agent_id}' non e' inactive (stato={card.status!r}): nessuna istanza "
            "(RUNTIME.md, Avvio)",
        )

    if not card.assignable:
        missing = ", ".join(card.missing_fields) or "authorized_task_types"
        violation(
            "agent-not-assignable",
            f"la card '{agent_id}' non dichiara un match esplicito ({missing}): STOP, "
            "serve una card nuova o un Transient Worker autorizzato (SPECIALIZATION.md)",
        )

    task_type = contract.get("task_type")
    if task_type is None:
        warning(
            "task-type-undeclared",
            "il contract non dichiara 'task_type': il match con authorized_task_types di "
            f"'{agent_id}' non e' verificabile, resta una dichiarazione "
            "(RUNTIME.md, Avvio)",
        )
    else:
        task_type = str(task_type).strip()
        if card.excludes_task_type(task_type):
            violation(
                "task-type-excluded",
                f"'{task_type}' e' in excluded_task_types di '{agent_id}' "
                "(RUNTIME.md, Avvio)",
            )
        elif not card.allows_task_type(task_type):
            violation(
                "task-type-no-match",
                f"'{task_type}' non e' in authorized_task_types di '{agent_id}' "
                f"{list(card.authorized_task_types or ())}: nessun match, STOP",
            )

    product = contract.get("product")
    if _non_empty_text(product) and str(product).strip() not in KNOWN_PRODUCTS:
        warning(
            "product-unknown",
            f"prodotto '{product}' fuori dall'elenco dello schema {list(KNOWN_PRODUCTS)}",
        )

    # --- permessi ----------------------------------------------------------
    requested = contract.get("permissions")
    if requested is not None:
        if not isinstance(requested, dict):
            violation("permissions-invalid", "'permissions' deve essere una mappatura")
        else:
            for scope, level in requested.items():
                granted = card.permission_level(str(scope))
                wanted = ad_registry.PERMISSION_LEVELS.get(str(level).lower(), -1)
                if wanted < 0:
                    violation(
                        "permissions-invalid",
                        f"livello '{level}' non noto per lo scope '{scope}'",
                    )
                elif wanted > granted:
                    violation(
                        "permission-escalation",
                        f"il contract chiede '{scope}: {level}' ma la card '{agent_id}' concede "
                        f"'{scope}: {card.permissions.get(str(scope), 'none')}'. Il contract puo' "
                        "togliere permessi, non aggiungerne (RUNTIME.md, Permessi)",
                    )

    if card.is_governance:
        outputs = [str(item).lower() for item in _as_list(contract.get("outputs"))]
        if "code" in outputs:
            warning(
                "governance-card-producing-code",
                f"'{agent_id}' e' una card di governance e il contract le chiede 'code': "
                "il ruolo decompone e assegna, non sviluppa (AGENTI-V2.md)",
            )

    # --- gate --------------------------------------------------------------
    gates = [str(item).strip() for item in _as_list(contract.get("required_gates"))]
    if not gates:
        violation(
            "gates-empty",
            "nessun gate richiesto: senza Quality Gate il lavoro non e' ACCEPT "
            "(AGENTI-V2.md, Governance aziendale)",
        )
    seen: set[str] = set()
    for gate in gates:
        canonical_name = ad_gates.canonical(gate)
        if canonical_name is None:
            violation(
                "gate-unknown",
                f"'{gate}' non e' nel catalogo dei gate (QUALITY-GATES.md)",
            )
            continue
        if canonical_name in seen:
            warning("gate-duplicated", f"gate '{canonical_name}' richiesto piu' di una volta")
        seen.add(canonical_name)
        owners = ad_gates.owners(canonical_name)
        if owner_id := next((o for o in owners if o == agent_id), None):
            violation(
                "gate-owner-conflict",
                f"la card '{owner_id}' e' l'esecutore del contract ed e' anche l'owner di "
                f"default del gate '{canonical_name}': chi produce un artefatto non ne valida "
                "il gate (GOVERNANCE-AZIENDALE.md, Principi non negoziabili)",
            )

    # --- decision record ---------------------------------------------------
    record = contract.get("decision_record")
    if record in (None, ""):
        warning(
            "decision-record-absent",
            "nessun 'decision_record': se il task e' una decisione di Livello 2 o 3 il record "
            "e' obbligatorio (TASK-CONTRACTS.md, Schema)",
        )
    else:
        path = resolve_decision_record(str(record))
        if path is None:
            violation(
                "decision-record-missing",
                f"Decision Record '{record}' non trovato in DECISIONI/",
            )
        else:
            state = _record_state(path)
            if state != "approvato":
                violation(
                    "decision-record-not-approved",
                    f"Decision Record '{record}' ha stato {state or 'non dichiarato'!r}: "
                    "senza approvazione la decisione non e' presa (GOVERNANCE-AZIENDALE.md)",
                )

    return _sorted(findings)


def _sorted(findings: list[Finding]) -> list[Finding]:
    """Return findings with violations first, then by code."""
    return sorted(findings, key=lambda f: (f.level != VIOLATION, f.code, f.message))


def violations(findings: list[Finding]) -> list[Finding]:
    """Return only the violations."""
    return [f for f in findings if f.level == VIOLATION]


def warnings(findings: list[Finding]) -> list[Finding]:
    """Return only the warnings."""
    return [f for f in findings if f.level == WARNING]
