"""Evidenze e verdetto del Quality Gate (QUALITY-GATES.md).

I documenti dicono **cosa** deve dichiarare un'evidenza ma non in quale
contenitore. Questo modulo fissa il contenitore minimo:

```yaml
schema: 2              # opzionale: senza, l'evidenza e' legacy (vale, ma lo dice il verdetto)
task_id: BIO-142
gate: QA
outcome: PASS          # PASS chiude il gate; FAIL/UNKNOWN/TRUNCATED/SKIPPED/UNSUPPORTED lo tengono aperto
producer: qa           # card che ha prodotto l'evidenza
artifact_producer: backend   # opzionale
timestamp: 2026-10-08T07:20:00+02:00   # opzionale, per il rework
references: [artefatto, comando]
confidence: observed        # observed | derived | inferred  (schema 2)
authority: execution        # execution | artifact | reference | external-service | inference  (schema 2)
coverage:                   # schema 2: quanto ho guardato davvero
  status: complete          # complete | partial | unknown
  examined: 12
  total: 12
limitations: ["non eseguito su Windows"]
evidence_id: ev_<64 hex>    # opzionale: se c'e', deve combaciare con quello calcolato
notes: ""
```

Un'evidenza che non dichiara task_id, gate, esito e produttore non conta.

**Identita'.** `evidence_id` e' il digest SHA-256 del contenuto semantico (JSON canonico):
non si sceglie, si calcola. Se il file ne dichiara uno e non combacia, il record e' INVALID e
il gate resta aperto — e' cosi' che una modifica successiva alla firma si vede. Stessa idea di
REA, `studio/rea-main/src/domain/evidence.ts`.

**Copertura.** Un `PASS` con `coverage.status` diverso da `complete` e' una contraddizione:
chi non ha finito la verifica ha `UNKNOWN`, non `PASS`. La regola sta in
`_coverage_problem`; lo schema 2 la pretende esplicita, la legacy la dichiara assente.

**Fail-closed.** Solo `PASS` chiude un gate. Gli altri esiti sono ammessi — un'evidenza
onesta deve poter dire «non ho potuto» — ma non aggregano mai in ACCEPT: un gate NON
soddisfatto, non osservabile, troncato, saltato o non supportato resta aperto. Un
elenco di esiti «che bloccano» sarebbe aperto per costruzione; qui la regola e' scritta
come elenco di cio' che **apre**, e ha un solo elemento (ENG-001, passo 1).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

import ad_contract
import ad_gates

#: Esiti ammessi in un'evidenza, e cosa dichiara ognuno.
#:
#: **Solo `PASS` chiude un gate.** Gli altri descrivono un lavoro che non e' chiuso:
#: ammetterli e' corretto (un'evidenza onesta deve poter dire «non ho potuto»), ma
#: aggregarli in ACCEPT sarebbe la bugia che questo sistema esiste per impedire.
#: La regola e' quella di REA, `studio/rea-main/docs/reconstruction-readiness.md`:
#: «fail, unknown, unsupported, truncated and skipped never aggregate to pass».
#: ENG-001, passo 1.
OUTCOMES: dict[str, str] = {
    "PASS": "il gate e' soddisfatto",
    "FAIL": "il gate non e' soddisfatto",
    "UNKNOWN": "non e' stato possibile stabilire l'esito",
    "TRUNCATED": "l'osservazione e' incompleta per troncamento",
    "SKIPPED": "la verifica richiesta non e' stata eseguita",
    "UNSUPPORTED": "la verifica non e' supportata in questo ambiente",
}
VALID_OUTCOMES: tuple[str, ...] = tuple(OUTCOMES)

#: L'unico esito che chiude un gate. Tutto il resto tiene il gate aperto.
ADVANCING_OUTCOME = "PASS"

EVIDENCE_SUFFIXES: tuple[str, ...] = (".yaml", ".yml")

#: Versione dello schema dell'evidenza. `schema: 2` dichiara un'evidenza che sa
#: **quanto** ha guardato (`coverage`) e **che tipo di prova** e' (`authority`,
#: `confidence`). Senza `schema`, l'evidenza e' *legacy*: vale come prima, ma non
#: dichiara la copertura — e il verdetto lo dice invece di far finta di niente.
SCHEMA_VERSION = 2

#: Quanto e' solida l'osservazione. Stesse etichette di REA
#: (`studio/rea-main/src/domain/evidence.ts`): un fatto osservato, dedotto o
#: inferito non sono la stessa cosa e non si sostituiscono.
CONFIDENCE_VALUES: tuple[str, ...] = ("observed", "derived", "inferred")

#: Da dove viene il fatto. Serve a impedire che una prova debole chiuda un gate
#: che chiedeva una prova forte (in REA: `docs/reconstruction-coverage.md`).
AUTHORITY_VALUES: tuple[str, ...] = (
    "execution",        # un comando e' stato ESEGUITO e osservato
    "artifact",         # un artefatto e' stato LETTO
    "reference",        # una fonte storica o documentale
    "external-service", # una risposta di un servizio esterno
    "inference",        # ragionamento dell'analista, senza osservazione diretta
)

#: Quanto del perimetro e' stato davvero esaminato. `complete` e' l'unico stato
#: su cui un `PASS` puo' reggersi; `partial` e `unknown` tengono il gate aperto.
COVERAGE_STATUSES: tuple[str, ...] = ("complete", "partial", "unknown")


@dataclass(frozen=True)
class Coverage:
    """Dichiarazione di quanto e' stato esaminato."""

    status: str
    examined: int | None
    total: int | None

    def projection(self) -> dict[str, Any]:
        """Return the semantic projection used for the evidence identity."""
        return {"status": self.status, "examined": self.examined, "total": self.total}

#: C1 — etichette d'evidenza. Ogni affermazione portante ne porta una.
#: Senza etichetta un'affermazione vale NOT_VERIFIED, mai VERIFIED per default.
CLAIM_LABELS: tuple[str, ...] = (
    "VERIFIED",
    "DOCUMENTED",
    "INFERRED",
    "NOT_VERIFIED",
    "NOT_AVAILABLE",
    "DOCUMENTATION_MISMATCH",
)

#: C3 — dichiarazione obbligatoria dei side-effect, complemento del write_scope.
#: "Se non verificabile -> NOT_VERIFIED (mai inventare NO)".
SIDE_EFFECT_KEYS: tuple[str, ...] = (
    "code",
    "database",
    "schema",
    "deps",
    "env",
    "external_services",
)
SIDE_EFFECT_VALUES: tuple[str, ...] = ("YES", "NO", "NOT_VERIFIED")

#: Frammenti di write_scope che toccano dati persistenti.
DATA_HINTS: tuple[str, ...] = (
    "db",
    "database",
    "prisma",
    "migration",
    "migrations",
    "seed",
    "schema",
    "dati",
)


class EvidenceError(Exception):
    """Raised when an evidence file cannot be read or parsed."""


@dataclass(frozen=True)
class Evidence:
    """One evidence record produced for a gate."""

    path: Path
    task_id: str
    gate: str
    outcome: str
    producer: str
    artifact_producer: str
    timestamp: str
    references: tuple[str, ...]
    side_effects: tuple[tuple[str, str], ...] = ()
    claims: tuple[tuple[str, str], ...] = ()
    schema: int | None = None
    confidence: str = ""
    authority: str = ""
    coverage: Coverage | None = None
    limitations: tuple[str, ...] = ()
    #: Identita' dichiarata nel file. Se c'e', deve combaciare con quella calcolata.
    declared_id: str = ""
    #: Identita' calcolata dal contenuto. Sempre presente: e' la proprieta' del record.
    evidence_id: str = ""
    #: Perche' un'identita' dichiarata non combacia, se non combacia.
    id_problem: str = ""
    #: Se il file dichiara `limitations` (anche vuoto). Assente != vuoto.
    limitations_declared: bool = False
    #: Prosa del produttore. Fa parte dell'identita': puo' portare affermazioni.
    notes: str = ""

    def describe(self) -> str:
        """Return a one-line description."""
        return f"{self.path.name}: gate={self.gate} outcome={self.outcome} producer={self.producer}"

    def side_effect(self, key: str) -> str:
        """Return the declared value for one side-effect key, or an empty string."""
        return dict(self.side_effects).get(key, "")

    def semantic_projection(self) -> dict[str, Any]:
        """Return what identifies the record, and only that.

        Fuori restano i campi di **visualizzazione** (il percorso del file) e
        l'identita' stessa: dentro tutto cio' che cambia il significato. E' la
        stessa scelta di REA in `src/domain/evidence.ts`, dove il digest esclude
        il nome del soggetto e include il resto.
        """
        return {
            "schema": self.schema,
            "task_id": self.task_id,
            "gate": self.gate,
            "outcome": self.outcome,
            "producer": self.producer,
            "artifact_producer": self.artifact_producer,
            "timestamp": self.timestamp,
            "references": list(self.references),
            "side_effects": dict(sorted(self.side_effects)),
            "claims": dict(sorted(self.claims)),
            "confidence": self.confidence,
            "authority": self.authority,
            "coverage": None if self.coverage is None else self.coverage.projection(),
            "limitations": list(self.limitations),
            "limitations_declared": self.limitations_declared,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class GateResult:
    """The verdict on a single required gate."""

    gate: str
    state: str  # PASS | FAIL | MISSING | INVALID | UNKNOWN | TRUNCATED | SKIPPED | UNSUPPORTED
    producer: str
    detail: str
    evidence_id: str = ""
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class Verdict:
    """The Quality Gate verdict for a contract."""

    outcome: str  # ACCEPT | REJECT
    human_gate: bool
    gates: tuple[GateResult, ...]
    notes: tuple[str, ...]


def canonical_payload(projection: dict[str, Any]) -> str:
    """Serialise a projection so that two equal records give equal bytes.

    JSON con chiavi ordinate: e' la stessa idea del JSON canonico di REA
    (`canonicalDigest.ts`, RFC 8785), ridotta a cio' che serve qui.
    """
    return json.dumps(projection, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_evidence_id(record: Evidence) -> str:
    """Return the content-derived identity of one evidence record."""
    digest = hashlib.sha256(canonical_payload(record.semantic_projection()).encode("utf-8"))
    return f"ev_{digest.hexdigest()}"


def _effect_value(value: object) -> str:
    """Normalise a side-effect value.

    YAML 1.1 risolve ``NO`` come booleano ``False`` (e ``YES`` come ``True``): il
    cosiddetto "problema della Norvegia". Chi scrive ``database: NO`` senza
    virgolette intende NO, e lo ottiene: qui il booleano viene riportato al testo.
    """
    if isinstance(value, bool):
        return "YES" if value else "NO"
    return str(value).strip().upper()


def load_evidence(path: str | Path) -> Evidence:
    """Load one evidence file.

    Args:
        path: Path to a YAML evidence file.

    Returns:
        The parsed evidence.

    Raises:
        EvidenceError: If the file is missing, unreadable or not a mapping.
    """
    file_path = Path(path)
    try:
        data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise EvidenceError(f"evidenza illeggibile '{file_path}': {exc}") from exc
    except yaml.YAMLError as exc:
        raise EvidenceError(f"YAML non valido in '{file_path}': {exc}") from exc
    if not isinstance(data, dict):
        raise EvidenceError(f"'{file_path}' non contiene una mappatura")

    effects = data.get("side_effects") or {}
    if not isinstance(effects, dict):
        raise EvidenceError(f"'{file_path}': 'side_effects' deve essere una mappatura")
    claims = data.get("claims") or {}
    # `claims` e' una mappatura `chiave: esito` — e resta la forma che si scrive. Ma se
    # arriva una **lista di affermazioni** non si rifiuta il file: si converte, dicendo
    # che non e' verificato.
    #
    # Perche' (2026-11-06). Il QA di `GOV-024` R4 ha scritto `claims` come lista di sei
    # affermazioni vere e ben scritte. `gate_kit` non controllava il tipo, quindi il gate
    # si e' chiuso; poi `ad_unknowns` ha inciampato su quel file e `test-mcp` e' diventato
    # rosso. Un'evidenza che un validatore accetta e un altro non sa leggere e' un
    # contratto rotto — ma la risposta non e' rompere tutto il registro per un file: e'
    # leggere il file. Il gate ora rifiuta la forma sbagliata (vedi `gate_kit`), quindi non
    # se ne produrranno altre; questa resta leggibile perche' esiste.
    #
    # La conversione e' onesta: una lista non dice quale affermazione sia verificata,
    # quindi nessuna lo e'. `non_verificato`, non `VERIFIED`.
    if isinstance(claims, list):
        claims = {str(voce).strip(): "non_verificato" for voce in claims if str(voce).strip()}
    if not isinstance(claims, dict):
        raise EvidenceError(
            f"'{file_path}': 'claims' deve essere una mappatura (chiave: esito) o una lista "
            f"di affermazioni, non {type(data.get('claims')).__name__}"
        )

    record = Evidence(
        path=file_path,
        task_id=str(data.get("task_id", "")).strip(),
        gate=str(data.get("gate", "")).strip(),
        outcome=str(data.get("outcome", "")).strip().upper(),
        producer=str(data.get("producer", "")).strip(),
        artifact_producer=str(data.get("artifact_producer", "")).strip(),
        timestamp=str(data.get("timestamp", "")).strip(),
        references=tuple(str(item) for item in (data.get("references") or [])),
        side_effects=tuple(
            (str(key).strip(), _effect_value(value)) for key, value in effects.items()
        ),
        claims=tuple(
            (str(key).strip(), str(value).strip().upper()) for key, value in claims.items()
        ),
        schema=_parse_schema(data.get("schema"), file_path),
        confidence=str(data.get("confidence", "")).strip().lower(),
        authority=str(data.get("authority", "")).strip().lower(),
        coverage=_parse_coverage(data.get("coverage"), file_path),
        limitations=_parse_string_list(data.get("limitations"), "limitations", file_path),
        limitations_declared="limitations" in data,
        notes=str(data.get("notes", "")),
        declared_id=str(data.get("evidence_id", "")).strip(),
    )

    # L'identita' si CALCOLA dal contenuto, non si sceglie. Se il file ne dichiara
    # una, deve combaciare: e' cosi' che una modifica successiva si vede.
    sealed = replace(record, evidence_id=compute_evidence_id(record))
    if sealed.declared_id and sealed.declared_id != sealed.evidence_id:
        sealed = replace(
            sealed,
            id_problem=(
                f"evidence_id dichiarato '{sealed.declared_id}' diverso da quello calcolato "
                f"'{sealed.evidence_id}': il file e' stato modificato dopo la firma, "
                "oppure l'identita' e' stata copiata da un altro record"
            ),
        )
    return sealed


def _parse_schema(value: object, file_path: Path) -> int | None:
    """Parse the optional schema version."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise EvidenceError(f"'{file_path}': 'schema' deve essere un intero (2)")
    return value


def _parse_string_list(value: object, name: str, file_path: Path) -> tuple[str, ...]:
    """Parse an optional list of strings."""
    if value is None:
        return ()
    if isinstance(value, str):
        return (value.strip(),)
    if not isinstance(value, list):
        raise EvidenceError(f"'{file_path}': '{name}' deve essere una lista di stringhe")
    return tuple(str(item).strip() for item in value)


def _parse_coverage(value: object, file_path: Path) -> Coverage | None:
    """Parse the optional coverage declaration."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise EvidenceError(f"'{file_path}': 'coverage' deve essere una mappatura")
    status = str(value.get("status", "")).strip().lower()
    if not status:
        raise EvidenceError(f"'{file_path}': 'coverage' richiede 'status'")
    counters: dict[str, int | None] = {}
    for chiave in ("examined", "total"):
        grezzo = value.get(chiave)
        if grezzo is None:
            counters[chiave] = None
        elif isinstance(grezzo, bool) or not isinstance(grezzo, int) or grezzo < 0:
            raise EvidenceError(
                f"'{file_path}': 'coverage.{chiave}' deve essere un intero non negativo"
            )
        else:
            counters[chiave] = grezzo
    return Coverage(status=status, examined=counters["examined"], total=counters["total"])


def _is_unknowns_ledger(path: Path) -> bool:
    """True when a YAML file is the unknowns ledger, not an evidence record.

    `evidenze/` tiene le prove e il registro delle incognite nello stesso posto:
    senza questa distinzione il registro entrerebbe nel conto delle prove, e una
    directory di evidenze ne risulterebbe una in piu'. La regola e' stretta: e'
    un registro **solo** se ha `unknowns` e non ha `gate`. Un file malformato non
    viene ignorato: passa di li' e fa l'errore che deve fare.
    """
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return False
    if not isinstance(data, dict) or "gate" in data:
        return False
    # Il registro delle incognite e il testimone dell'albero vivono in `evidenze/`
    # come le prove, ma non sono prove: si riconoscono dalla forma, e solo da quella.
    return "unknowns" in data or "tree_version" in data


def collect(targets: list[str | Path]) -> list[Evidence]:
    """Collect evidence from files and directories.

    Args:
        targets: Files or directories to scan.

    Returns:
        The evidence found, sorted by file name.

    Raises:
        EvidenceError: If a target does not exist.
    """
    paths: list[Path] = []
    for target in targets:
        path = Path(target)
        if path.is_dir():
            paths.extend(
                sorted(
                    p
                    for p in path.iterdir()
                    if p.suffix.lower() in EVIDENCE_SUFFIXES and not _is_unknowns_ledger(p)
                )
            )
        elif path.exists():
            paths.append(path)
        else:
            raise EvidenceError(f"evidenza non trovata: {path}")
    return [load_evidence(path) for path in paths]


def _latest(records: list[Evidence]) -> Evidence:
    """Return the most recent evidence record."""
    stamped = [record for record in records if record.timestamp]
    if len(stamped) == len(records):
        return max(records, key=lambda record: record.timestamp)
    return records[-1]


def evaluate(
    contract: dict[str, Any],
    evidence: list[Evidence],
) -> Verdict:
    """Apply the verdict rule of QUALITY-GATES.md.

    Args:
        contract: The task contract.
        evidence: Every evidence record available for the task.

    Returns:
        The verdict, with one result per required gate.
    """
    task_id = str(contract.get("task_id", "")).strip()
    executor = str(contract.get("agent", "")).strip()
    required = [
        ad_gates.canonical(str(g)) or str(g)
        for g in ad_contract.as_list(contract.get("required_gates"))
    ]
    notes: list[str] = []
    scope_text = " ".join(
        str(item).lower() for item in ad_contract.as_list(contract.get("write_scope"))
    )

    results: list[GateResult] = []
    legacy_validi: list[Evidence] = []
    for gate in required:
        candidates = [
            record for record in evidence if ad_gates.canonical(record.gate) == gate
        ]
        if not candidates:
            results.append(
                GateResult(gate, "MISSING", "", "nessuna evidenza: REJECT (QUALITY-GATES.md)")
            )
            continue

        # ERR-0027 — PRIMA di chi e' l'evidenza, POI quando e' stata scritta.
        #
        # Prima qui si sceglieva fra tutte le evidenze di quel gate e solo dopo si
        # guardava il `task_id`: se l'evidenza di un ALTRO permesso aveva un
        # timestamp piu' recente, quella giusta non veniva nemmeno guardata, e il
        # gate risultava INVALID accusando il permesso sbagliato. Su 7 permessi del
        # progetto, 6 davano un falso REJECT, e l'unico che passava era quello la
        # cui evidenza era l'ultima depositata — cioe' un caso, non la regola.
        #
        # Il criterio del verdetto non cambia: un gate senza evidenza PROPRIA resta
        # un REJECT, e resta un `MISSING` — l'assenza non e' un'accusa.
        proprie = [record for record in candidates if record.task_id == task_id]
        if not proprie:
            estranei = sorted({record.task_id or "(senza task_id)" for record in candidates})
            results.append(
                GateResult(
                    gate,
                    "MISSING",
                    "",
                    f"nessuna evidenza di '{task_id}' per questo gate. Depositate: "
                    f"{len(candidates)}, di altri permessi ({', '.join(estranei)}) — "
                    "REJECT (QUALITY-GATES.md)",
                )
            )
            continue
        if len(proprie) > 1:
            notes.append(
                f"gate '{gate}': {len(proprie)} evidenze di questo permesso; vale la piu' "
                "recente per timestamp, altrimenti l'ultima in ordine di file"
            )
        if len(proprie) < len(candidates):
            notes.append(
                f"gate '{gate}': evidenze di altri permessi escluse dal conto "
                f"({len(candidates) - len(proprie)}): il task_id e' diverso da '{task_id}'"
            )
        record = _latest(proprie)
        problem = _validity_problem(record, task_id, gate, executor, scope_text)
        if problem:
            results.append(
                GateResult(gate, "INVALID", record.producer, problem, record.evidence_id)
            )
            continue
        if record.schema is None and record.coverage is None:
            legacy_validi.append(record)
        if record.producer and record.producer not in ad_gates.owners(gate):
            owners = ad_gates.owners(gate)
            if owners:
                notes.append(
                    f"gate '{gate}': produttore '{record.producer}' diverso dall'owner di "
                    f"default {list(owners)}; ammesso se indipendente dall'esecutore"
                )
        results.append(
            GateResult(
                gate,
                record.outcome,
                record.producer,
                record.path.name,
                record.evidence_id,
                record.limitations,
            )
        )

    # FAIL-CLOSED (ENG-001, passo 1). Un gate si chiude **solo** con un PASS.
    #
    # Prima qui si cercavano soltanto FAIL/MISSING/INVALID: un esito `UNKNOWN`
    # — o qualunque esito nuovo — sarebbe passato per ACCEPT, perche' non era
    # nell'elenco dei cattivi. La regola era scritta come elenco di cio' che
    # blocca, e un elenco di cio' che blocca e' aperto per costruzione: basta un
    # valore che nessuno ha previsto. Ora la regola e' scritta come elenco di
    # cio' che **apre**, che ha un solo elemento.
    aperti = [result for result in results if result.state != ADVANCING_OUTCOME]
    outcome = "REJECT" if aperti else "ACCEPT"
    for result in aperti:
        if result.state not in ("FAIL", "MISSING", "INVALID"):
            notes.append(
                f"gate '{result.gate}': esito {result.state} — un gate si chiude solo con "
                f"PASS; '{result.state}' lo tiene aperto (fail-closed)"
            )

    # Transizione dichiarata (ENG-001, passo 2). Le evidenze scritte prima dello
    # schema 2 non dicono quanto hanno esaminato: continuano a valere, ma il
    # verdetto lo DICE e le elenca, invece di far finta che siano complete.
    # Rifiutarle in blocco cancellerebbe lavoro vero; tacerle lascerebbe in piedi
    # un PASS senza copertura, che e' la cosa che stiamo togliendo.
    if legacy_validi:
        notes.append(
            f"{len(legacy_validi)} evidenze legacy senza copertura dichiarata "
            f"({', '.join(sorted(record.path.name for record in legacy_validi))}): "
            "valgono come prima, ma non dichiarano quanto hanno esaminato. "
            "Migrarle con `schema: 2` + `coverage` + `authority` + `confidence`"
        )

    approval = contract.get("approval") or {}
    human_gate = bool(approval.get("human")) if isinstance(approval, dict) else False
    if outcome == "ACCEPT" and human_gate:
        notes.append(
            "ACCEPT non e' il rilascio: approval.human e' true, decide l'umano "
            "(QUALITY-GATES.md)"
        )

    return Verdict(outcome=outcome, human_gate=human_gate, gates=tuple(results), notes=tuple(notes))


def _coverage_problem(record: Evidence) -> str:
    """Return why the coverage declaration is unusable, or an empty string.

    La regola che conta: **un PASS su un'osservazione incompleta e' una
    contraddizione**, non un PASS. Chi non ha potuto completare la verifica ha un
    esito apposta per dirlo (`UNKNOWN`, `TRUNCATED`, `SKIPPED`, `UNSUPPORTED`); se
    scrive `PASS` con copertura parziale sta chiedendo al verdetto di crederci.
    """
    coverage = record.coverage
    if coverage is None:
        return ""
    if coverage.status not in COVERAGE_STATUSES:
        return (
            f"coverage.status '{coverage.status}' non ammesso: ammessi "
            + ", ".join(COVERAGE_STATUSES)
        )
    if (
        coverage.status == "complete"
        and coverage.examined is not None
        and coverage.total is not None
        and coverage.examined < coverage.total
    ):
        return (
            f"coverage.status 'complete' ma examined {coverage.examined} < total "
            f"{coverage.total}: contraddizione"
        )
    if coverage.status != "complete" and record.outcome == ADVANCING_OUTCOME:
        return (
            f"esito PASS con copertura '{coverage.status}': un gate si chiude solo su "
            "un'osservazione completa. Se la verifica non e' finita, l'esito e' "
            "UNKNOWN/TRUNCATED/SKIPPED; se e' finita, dichiara coverage complete"
        )
    return ""


def _validity_problem(
    record: Evidence, task_id: str, gate: str, executor: str, scope: str = ""
) -> str:
    """Return why the evidence does not count, or an empty string.

    Il controllo del `task_id` resta anche se `evaluate` adesso filtra prima di
    scegliere: questa e' la validita' di UNA evidenza per UN contract, e deve
    restare completa se qualcuno la chiama su un record che non e' il suo.
    """
    if record.id_problem:
        return record.id_problem
    if record.schema is not None and record.schema != SCHEMA_VERSION:
        return (
            f"schema {record.schema} non ammesso: ammesso {SCHEMA_VERSION} "
            "(o nessuno schema, per un'evidenza legacy)"
        )
    if record.confidence and record.confidence not in CONFIDENCE_VALUES:
        return (
            f"confidence '{record.confidence}' non ammessa: ammesse "
            + ", ".join(CONFIDENCE_VALUES)
        )
    if record.authority and record.authority not in AUTHORITY_VALUES:
        return (
            f"authority '{record.authority}' non ammessa: ammesse "
            + ", ".join(AUTHORITY_VALUES)
        )
    if record.coverage is not None:
        problema = _coverage_problem(record)
        if problema:
            return problema
    if record.schema == SCHEMA_VERSION and not record.limitations_declared:
        return (
            "schema 2 richiede `limitations` esplicito: se non ne hai, scrivi "
            "`limitations: []`. Un risultato che non dice cosa non copre non e' "
            "falsificabile — non si sa cosa lo smentirebbe"
        )
    if record.schema == SCHEMA_VERSION:
        mancanti = [
            campo
            for campo, valore in (
                ("confidence", record.confidence),
                ("authority", record.authority),
                ("coverage", record.coverage),
            )
            if not valore
        ]
        if mancanti:
            return (
                "schema 2 richiede una dichiarazione esplicita: manca "
                + ", ".join(mancanti)
                + " — un'evidenza che non dice quanto ha guardato non chiude un gate"
            )
    if record.task_id != task_id:
        return (
            f"task_id '{record.task_id}' diverso dal contract '{task_id}': l'evidenza non conta"
        )
    if record.outcome not in VALID_OUTCOMES:
        return (
            f"esito '{record.outcome or 'assente'}' non ammesso: ammessi "
            + ", ".join(VALID_OUTCOMES)
        )
    if not record.producer:
        return "produttore non dichiarato: l'evidenza non conta"
    if record.producer == executor:
        return (
            f"prodotta da '{record.producer}', che e' l'esecutore del contract: "
            "chi produce l'artefatto non ne valida il gate"
        )
    # Con `executor` vuoto non si sa chi esegue: la regola "chi produce non valida"
    # si applica solo quando l'esecutore e' noto. Senza, un `artifact_producer`
    # dichiarato veniva bocciato contro la stringa vuota (L4 del 2o gate ENG-002).
    if executor and record.artifact_producer and record.artifact_producer != executor:
        return (
            f"artifact_producer '{record.artifact_producer}' incoerente con l'esecutore "
            f"'{executor}' del contract"
        )

    declared = dict(record.side_effects)
    if not declared:
        return (
            "dichiarazione dei side-effect assente: serve 'side_effects' con "
            + ", ".join(SIDE_EFFECT_KEYS)
            + " = YES|NO|NOT_VERIFIED (DEC-0011)"
        )
    for key, value in declared.items():
        if key not in SIDE_EFFECT_KEYS:
            return f"side_effect '{key}' non dichiarabile: ammessi {list(SIDE_EFFECT_KEYS)}"
        if value not in SIDE_EFFECT_VALUES:
            return f"side_effect '{key}' = '{value}': ammessi YES, NO, NOT_VERIFIED"
    missing = [key for key in SIDE_EFFECT_KEYS if key not in declared]
    if missing:
        return f"side_effects incompleta: mancano {missing} (DEC-0011)"
    if declared.get("database") == "NO" and any(hint in scope for hint in DATA_HINTS):
        return (
            "dichiara 'database: NO' ma il write_scope tocca dati persistenti: "
            "contraddizione. Se non hai potuto verificare, usa NOT_VERIFIED"
        )

    for claim, label in record.claims:
        if label not in CLAIM_LABELS:
            return (
                f"etichetta '{label}' non ammessa per '{claim}': ammesse {list(CLAIM_LABELS)}"
            )
    return ""


# ---------------------------------------------------------------------------
# Registro delle incognite (ENG-001, passo 3)
#
# Perche' esiste. Un dubbio, oggi, vive nella prosa di un report: nessuno lo
# conta, nessuno sa se e' ancora aperto, e la risoluzione non e' legata a una
# prova. Il registro lo rende una voce con stato, revisione, prove a favore e
# contro, e **l'autorita' che servirebbe per chiuderlo**. E' lo stesso oggetto
# di REA (`studio/rea-main/src/domain/residualUnknown.ts`): la domanda e' stabile,
# la revisione e' esplicita, e solo un'osservazione qualificata puo' chiuderla.
#
# L'identificatore si CALCOLA da domanda + dominio: due sessioni che scrivono la
# stessa domanda ottengono lo stesso id, e non serve prenotare niente.
# ---------------------------------------------------------------------------

UNKNOWN_STATUSES: tuple[str, ...] = (
    "open",
    "investigating",
    "blocked",
    "contradicted",
    "resolved",
)
SEVERITIES: tuple[str, ...] = ("low", "medium", "high", "critical")
DISPOSITIONS: tuple[str, ...] = ("verified", "withdrawn", "out-of-scope")


class UnknownRegistryError(Exception):
    """Raised when the unknowns ledger cannot be read or written."""


def unknown_id(question: str, domain: str) -> str:
    """Return the stable identity of one question in one domain."""
    normalizzata = " ".join(question.split()).strip()
    dominio = " ".join(domain.split()).strip()
    digest = hashlib.sha256(f"{dominio}\n{normalizzata}".encode("utf-8")).hexdigest()
    return f"unk_{digest[:32]}"


def load_unknowns(path: str | Path) -> list[dict[str, Any]]:
    """Load the unknowns ledger; a missing file is an empty ledger."""
    file_path = Path(path)
    if not file_path.exists():
        return []
    try:
        data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise UnknownRegistryError(f"registro illeggibile '{file_path}': {exc}") from exc
    except yaml.YAMLError as exc:
        raise UnknownRegistryError(f"YAML non valido in '{file_path}': {exc}") from exc
    if data is None:
        return []
    if not isinstance(data, dict) or not isinstance(data.get("unknowns"), list):
        raise UnknownRegistryError(
            f"'{file_path}': il registro deve essere una mappatura con chiave 'unknowns'"
        )
    records: list[dict[str, Any]] = []
    for voce in data["unknowns"]:
        if not isinstance(voce, dict):
            raise UnknownRegistryError(f"'{file_path}': ogni incognita deve essere una mappatura")
        records.append(dict(voce))
    return records


def save_unknowns(path: str | Path, records: list[dict[str, Any]]) -> None:
    """Write the ledger atomically, so a crash cannot truncate it."""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    testo = yaml.safe_dump({"unknowns": records}, allow_unicode=True, sort_keys=False)
    temporaneo = file_path.with_name(f".{file_path.name}.tmp")
    temporaneo.write_text(testo, encoding="utf-8")
    temporaneo.replace(file_path)


def new_unknown(
    question: str,
    domain: str,
    *,
    severity: str = "medium",
    required_authority: str | None = None,
    required_confidence: str = "observed",
    probes: tuple[str, ...] = (),
    supporting: tuple[str, ...] = (),
    contradicting: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Build one registry entry; the identity is derived, never chosen."""
    record: dict[str, Any] = {
        "unknown_id": unknown_id(question, domain),
        "revision": 1,
        "previous_revision": None,
        "question": " ".join(question.split()).strip(),
        "domain": " ".join(domain.split()).strip(),
        "status": "open",
        "severity": severity,
        "required_authority": required_authority,
        "required_confidence": required_confidence,
        "supporting_evidence": list(supporting),
        "contradicting_evidence": list(contradicting),
        "recommended_probes": list(probes),
        "resolution": None,
    }
    return record


def update_unknown(
    record: dict[str, Any],
    *,
    status: str | None = None,
    severity: str | None = None,
    probes: tuple[str, ...] | None = None,
    supporting: tuple[str, ...] | None = None,
    contradicting: tuple[str, ...] | None = None,
    resolution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a new revision of one entry, preserving its identity."""
    nuovo = dict(record)
    if status is not None:
        nuovo["status"] = status
    if severity is not None:
        nuovo["severity"] = severity
    if probes is not None:
        nuovo["recommended_probes"] = list(probes)
    if supporting is not None:
        nuovo["supporting_evidence"] = list(supporting)
    if contradicting is not None:
        nuovo["contradicting_evidence"] = list(contradicting)
    if resolution is not None:
        nuovo["resolution"] = resolution
    precedente = int(record.get("revision") or 1)
    nuovo["previous_revision"] = precedente
    nuovo["revision"] = precedente + 1
    return nuovo


def check_unknowns(
    records: list[dict[str, Any]],
    evidences: dict[str, Evidence] | None = None,
) -> list[str]:
    """Return every problem of the ledger; an empty list means coherent."""
    problemi: list[str] = []
    visti: set[str] = set()
    for indice, record in enumerate(records, start=1):
        etichetta = f"incognita #{indice}"
        domanda = str(record.get("question", "")).strip()
        dominio = str(record.get("domain", "")).strip()
        identificatore = str(record.get("unknown_id", "")).strip()
        if not domanda or not dominio:
            problemi.append(f"{etichetta}: manca 'question' o 'domain'")
        elif identificatore != unknown_id(domanda, dominio):
            problemi.append(
                f"{etichetta} ({identificatore or 'senza id'}): l'id non corrisponde a "
                f"domanda+dominio — quello calcolato e' {unknown_id(domanda, dominio)}"
            )
        if identificatore in visti:
            problemi.append(f"{etichetta}: id duplicato '{identificatore}'")
        visti.add(identificatore)

        stato = str(record.get("status", "")).strip().lower()
        if stato not in UNKNOWN_STATUSES:
            problemi.append(
                f"{etichetta}: status '{stato}' non ammesso: ammessi "
                + ", ".join(UNKNOWN_STATUSES)
            )
        gravita = str(record.get("severity", "")).strip().lower()
        if gravita not in SEVERITIES:
            problemi.append(
                f"{etichetta}: severity '{gravita}' non ammessa: ammesse "
                + ", ".join(SEVERITIES)
            )
        revisione = record.get("revision")
        if isinstance(revisione, bool) or not isinstance(revisione, int) or revisione < 1:
            problemi.append(f"{etichetta}: 'revision' deve essere un intero >= 1")
        else:
            precedente = record.get("previous_revision")
            if revisione > 1 and precedente != revisione - 1:
                problemi.append(
                    f"{etichetta}: revision {revisione} ma previous_revision "
                    f"{precedente!r} (atteso {revisione - 1})"
                )
            if revisione == 1 and precedente not in (None, 0):
                problemi.append(f"{etichetta}: revision 1 non puo' avere previous_revision")

        autorita = record.get("required_authority")
        if autorita is not None and str(autorita).strip() not in AUTHORITY_VALUES:
            problemi.append(
                f"{etichetta}: required_authority '{autorita}' non ammessa: ammesse "
                + ", ".join(AUTHORITY_VALUES)
            )
        confidenza = record.get("required_confidence")
        if confidenza is not None and str(confidenza).strip() not in CONFIDENCE_VALUES:
            problemi.append(
                f"{etichetta}: required_confidence '{confidenza}' non ammessa: ammesse "
                + ", ".join(CONFIDENCE_VALUES)
            )

        problemi.extend(_resolution_problems(record, etichetta, stato, evidences))
        problemi.extend(
            _evidence_reference_problems(record, etichetta, evidences)
        )
    return problemi


def _resolution_problems(
    record: dict[str, Any],
    etichetta: str,
    stato: str,
    evidences: dict[str, Evidence] | None,
) -> list[str]:
    """Check the resolution block, and that only a resolution closes a question."""
    resolution = record.get("resolution")
    if stato != "resolved":
        if resolution not in (None, {}):
            return [f"{etichetta}: status '{stato}' ma c'e' una resolution"]
        return []
    if not isinstance(resolution, dict):
        return [f"{etichetta}: status 'resolved' richiede una 'resolution'"]
    problemi: list[str] = []
    disposizione = str(resolution.get("disposition", "")).strip().lower()
    if disposizione not in DISPOSITIONS:
        problemi.append(
            f"{etichetta}: disposition '{disposizione}' non ammessa: ammesse "
            + ", ".join(DISPOSITIONS)
        )
    if not str(resolution.get("rationale", "")).strip():
        problemi.append(f"{etichetta}: la resolution richiede una 'rationale'")
    ids = [str(item) for item in (resolution.get("evidence_ids") or [])]
    if disposizione == "verified" and not ids:
        problemi.append(
            f"{etichetta}: 'verified' richiede almeno una prova: una domanda non si chiude "
            "con un'opinione"
        )
    if disposizione == "verified" and evidences is not None:
        richiesta = record.get("required_authority")
        richiesta_confidenza = record.get("required_confidence") or "observed"
        for identificatore in ids:
            prova = evidences.get(identificatore)
            if prova is None:
                problemi.append(
                    f"{etichetta}: la prova '{identificatore}' non esiste nel registro "
                    "consultato: passa `--evidence` con le prove vere, oppure non chiudere "
                    "la domanda"
                )
                continue
            if richiesta and prova.authority != str(richiesta):
                problemi.append(
                    f"{etichetta}: la prova '{identificatore}' ha authority "
                    f"'{prova.authority}', ma la domanda chiede '{richiesta}'"
                )
            if not prova.confidence:
                problemi.append(
                    f"{etichetta}: la prova '{identificatore}' non dichiara `confidence`: "
                    f"non puo' chiudere una domanda che chiede '{richiesta_confidenza}'. "
                    "Una confidenza assente non e' una confidenza soddisfatta"
                )
            elif prova.confidence != str(richiesta_confidenza):
                problemi.append(
                    f"{etichetta}: la prova '{identificatore}' ha confidence "
                    f"'{prova.confidence}', ma la domanda chiede '{richiesta_confidenza}'"
                )
    return problemi


def _evidence_reference_problems(
    record: dict[str, Any],
    etichetta: str,
    evidences: dict[str, Evidence] | None,
) -> list[str]:
    """Every evidence id cited by the entry must exist, when a set is supplied."""
    if evidences is None:
        return []
    problemi: list[str] = []
    for campo in ("supporting_evidence", "contradicting_evidence"):
        for identificatore in record.get(campo) or []:
            if str(identificatore) not in evidences:
                problemi.append(
                    f"{etichetta}: {campo} cita '{identificatore}', che non esiste nel registro"
                )
    return problemi


# ---------------------------------------------------------------------------
# Bundle sigillato delle prove (ENG-001, passo 4)
#
# Perche' esiste. L'impronta di UNA prova dice che quel file non e' cambiato; non
# dice niente sull'INSIEME. Un revisore esterno riceve un pacchetto: se una riga
# e' stata toccata, il sigillo del pacchetto non combacia e l'import rifiuta.
# E' la stessa idea del Blueprint di AD (un sigillo sul contenuto, non un
# puntatore) e dell'Evidence bundle di REA, ridotta all'essenziale.
# ---------------------------------------------------------------------------

BUNDLE_VERSION = 1


class BundleError(Exception):
    """Raised when a bundle cannot be read, written or trusted."""


def _record_to_dict(record: Evidence) -> dict[str, Any]:
    """Serialise one evidence record, identity included."""
    dati = record.semantic_projection()
    dati["evidence_id"] = record.evidence_id
    return dati


def _record_from_dict(data: dict[str, Any]) -> Evidence:
    """Rebuild one evidence record from a bundle entry."""
    coverage = data.get("coverage")
    record = Evidence(
        path=Path("<bundle>"),
        task_id=str(data.get("task_id", "")),
        gate=str(data.get("gate", "")),
        outcome=str(data.get("outcome", "")),
        producer=str(data.get("producer", "")),
        artifact_producer=str(data.get("artifact_producer", "")),
        timestamp=str(data.get("timestamp", "")),
        references=tuple(str(item) for item in (data.get("references") or ())),
        side_effects=tuple(
            (str(k), str(v)) for k, v in (data.get("side_effects") or {}).items()
        ),
        claims=tuple((str(k), str(v)) for k, v in (data.get("claims") or {}).items()),
        schema=data.get("schema"),
        confidence=str(data.get("confidence", "")),
        authority=str(data.get("authority", "")),
        coverage=None
        if coverage is None
        else Coverage(
            status=str(coverage.get("status", "")),
            examined=coverage.get("examined"),
            total=coverage.get("total"),
        ),
        limitations=tuple(str(item) for item in (data.get("limitations") or ())),
        declared_id=str(data.get("evidence_id", "")),
        limitations_declared=bool(
            data.get("limitations_declared", "limitations" in data)
        ),
        notes=str(data.get("notes", "")),
    )
    return replace(record, evidence_id=compute_evidence_id(record))


def _bundle_seal(payload: dict[str, Any]) -> str:
    """Return the seal of a bundle payload (everything except the seal)."""
    senza = {chiave: valore for chiave, valore in payload.items() if chiave != "seal"}
    digest = hashlib.sha256(canonical_payload(senza).encode("utf-8"))
    return f"seal_{digest.hexdigest()}"


def create_bundle(
    records: list[Evidence],
    unknowns: list[dict[str, Any]] | None = None,
    *,
    created_at: str | None = None,
    witness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a sealed bundle for one task.

    `witness` e' il testimone dell'albero (passo 6): dentro il pacchetto, il
    sigillo copre **anche** com'era la struttura quando le prove sono state
    prodotte. Senza, chi modificasse file e testimone insieme non verrebbe preso.
    """
    if not records:
        raise BundleError("nessuna evidenza da impacchettare")
    task_ids = sorted({record.task_id for record in records})
    if len(task_ids) != 1:
        raise BundleError(
            f"le evidenze appartengono a piu' task ({', '.join(task_ids)}): "
            "un bundle e' di un lavoro solo"
        )
    payload: dict[str, Any] = {
        "bundle_version": BUNDLE_VERSION,
        "task_id": task_ids[0],
        "created_at": created_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "records": sorted(
            (_record_to_dict(record) for record in records),
            key=lambda voce: str(voce["evidence_id"]),
        ),
        "unknowns": list(unknowns or ()),
    }
    if witness is not None:
        payload["witness"] = witness
    payload["seal"] = _bundle_seal(payload)
    return payload


def save_bundle(path: str | Path, bundle: dict[str, Any]) -> None:
    """Write a bundle atomically, as canonical JSON."""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temporaneo = file_path.with_name(f".{file_path.name}.tmp")
    temporaneo.write_text(canonical_payload(bundle) + "\n", encoding="utf-8")
    temporaneo.replace(file_path)


def load_bundle(path: str | Path) -> dict[str, Any]:
    """Read a bundle file."""
    file_path = Path(path)
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise BundleError(f"bundle illeggibile '{file_path}': {exc}") from exc
    except json.JSONDecodeError as exc:
        raise BundleError(f"bundle non e' JSON valido '{file_path}': {exc}") from exc
    if not isinstance(data, dict):
        raise BundleError(f"'{file_path}': il bundle deve essere un oggetto")
    return data


def verify_bundle(bundle: dict[str, Any]) -> list[str]:
    """Return every problem of a bundle; an empty list means trustworthy."""
    problemi: list[str] = []
    versione = bundle.get("bundle_version")
    if versione != BUNDLE_VERSION:
        return [f"bundle_version {versione!r} non ammessa: ammessa {BUNDLE_VERSION}"]
    sigillo = bundle.get("seal")
    if not isinstance(sigillo, str) or not sigillo:
        return ["il bundle non ha un sigillo: non e' verificabile"]
    if sigillo != _bundle_seal(bundle):
        problemi.append(
            "sigillo del bundle non combacia: il pacchetto e' stato modificato dopo "
            "essere stato sigillato"
        )
    grezzi = bundle.get("records")
    if not isinstance(grezzi, list) or not grezzi:
        problemi.append("il bundle non contiene evidenze")
        return problemi

    ricostruiti: list[Evidence] = []
    visti: set[str] = set()
    for indice, voce in enumerate(grezzi, start=1):
        if not isinstance(voce, dict):
            problemi.append(f"record #{indice}: non e' un oggetto")
            continue
        try:
            record = _record_from_dict(voce)
        except (TypeError, ValueError) as exc:
            problemi.append(f"record #{indice}: non ricostruibile ({exc})")
            continue
        ricostruiti.append(record)
        if str(voce.get("evidence_id", "")) != record.evidence_id:
            problemi.append(
                f"record #{indice}: evidence_id dichiarato diverso da quello calcolato "
                "dal contenuto"
            )
        if record.evidence_id in visti:
            problemi.append(f"record #{indice}: evidence_id duplicato")
        visti.add(record.evidence_id)

    task_ids = {record.task_id for record in ricostruiti}
    if len(task_ids) > 1:
        problemi.append(
            f"il bundle mescola piu' task ({', '.join(sorted(task_ids))}): "
            "un bundle e' di un lavoro solo"
        )

    testimone = bundle.get("witness")
    if testimone is not None:
        if not isinstance(testimone, dict):
            problemi.append("'witness' deve essere una mappatura")
        elif testimone.get("tree_version") != TREE_VERSION:
            problemi.append(
                f"testimone con tree_version {testimone.get('tree_version')!r} non ammessa"
            )
        elif testimone.get("digest") != _tree_digest(testimone):
            problemi.append(
                "il testimone dentro il bundle e' stato modificato dopo essere stato sigillato"
            )

    incognite = bundle.get("unknowns")
    if incognite is not None:
        if not isinstance(incognite, list):
            problemi.append("'unknowns' deve essere una lista")
        else:
            mappa = {record.evidence_id: record for record in ricostruiti}
            problemi.extend(check_unknowns(list(incognite), mappa))
    return problemi


def _safe_slug(value: str, fallback: str = "gate") -> str:
    """Return a filename-safe slug from untrusted text.

    Il `gate` viene da un bundle, e un bundle puo' essere costruito da chiunque: se
    finisse nel nome del file cosi' com'e', un `gate: "../../tmp/x"` scriverebbe
    FUORI dalla cartella di destinazione. Qui si riduce a `[a-z0-9-]`.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", str(value).strip().lower()).strip("-")
    return slug[:32] or fallback


def extract_bundle(bundle: dict[str, Any], destination: str | Path) -> dict[str, int]:
    """Write a verified bundle's records (and unknowns) into a directory.

    Ogni file scritto deve restare DENTRO `destination`: il nome viene da dati non
    fidati, quindi si sanifica e si verifica il contenimento **prima** di scrivere.
    """
    problemi = verify_bundle(bundle)
    if problemi:
        raise BundleError("bundle non attendibile: " + "; ".join(problemi))
    cartella = Path(destination)
    cartella.mkdir(parents=True, exist_ok=True)
    scritti = 0
    for voce in bundle.get("records") or []:
        record = _record_from_dict(voce)
        nome = f"{_safe_slug(record.gate)}-{record.evidence_id[3:15]}.yaml"
        bersaglio = (cartella / nome).resolve()
        if bersaglio.parent != cartella.resolve():
            raise BundleError(
                f"nome di file non contenibile nella destinazione: {nome}"
            )
        bersaglio.write_text(
            yaml.safe_dump(_record_to_dict(record), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        scritti += 1
    incognite = bundle.get("unknowns") or []
    if incognite:
        save_unknowns(cartella / "incognite.yaml", list(incognite))
    testimone = bundle.get("witness")
    if isinstance(testimone, dict):
        save_witness(cartella / "albero.yaml", testimone)
    return {
        "records": scritti,
        "unknowns": len(incognite),
        "witness": 1 if isinstance(testimone, dict) else 0,
    }


# ---------------------------------------------------------------------------
# Rilevamento fuori banda (ENG-001, passo 6)
#
# Perche' esiste. Con piu' superfici di esecuzione (DEC-0057) una scrittura fatta
# **fuori dai tool** non e' impedita da nessuno: la shell di qualunque client la
# fa. Il punto non e' impedirla — e' non poterla nascondere. Qui si fotografa
# l'albero quando si produce una prova, e al controllo si confronta: cio' che e'
# cambiato senza che un'evidenza lo nomini e' una **contaminazione**, coi percorsi
# esatti. E' la traduzione operativa di «non puoi mentire»: la garanzia non e'
# l'impossibilita' dell'azione, e' l'impossibilita' del silenzio.
#
# La regola di copertura e' meccanica e va detta: una modifica e' **coperta** se
# almeno un'evidenza del registro cita quel percorso (o una sua cartella) in
# `references`. Non prova che la modifica sia autorizzata; prova che qualcuno
# l'ha dichiarata osservandola. Il resto e' silenzio, e il silenzio si vede.
# ---------------------------------------------------------------------------

TREE_VERSION = 1

#: I percorsi della macchina che valgono come «struttura». `studio/` e' escluso
#: di proposito: e' materiale di studio, grande e non operativo, e includerlo
#: renderebbe il controllo lento senza aggiungere garanzia.
DEFAULT_TREE_PATHS: tuple[str, ...] = (
    ".brain",
    "tools",
    "tests",
    "evals",
    "DECISIONI",
    "contratti",
    "approvazioni",
    "drift",
    "errori",
    "piani",
    "orchestrazione",
    "milestone",
    "REQUISITI",
    "comunicazioni",
)
# `evidenze/` NON e' sorvegliata, e la ragione va detta: e' il posto dove le prove
# si **depositano**. Sorvegliarla significa che ogni gate, depositando le sue
# evidenze, fa scattare due «aggiunte fuori banda» — e un controllo che suona
# sempre insegna a ignorarlo (F3 del primo gate di ENG-001). L'integrita' delle
# prove non si difende con l'albero: si difende con l'identita' del record (passo
# 2) e col sigillo del bundle (passo 4), che sono fatti apposta.


class TreeError(Exception):
    """Raised when the tree witness cannot be read, written or trusted."""


def tree_fingerprint(
    root: str | Path,
    paths: tuple[str, ...] = DEFAULT_TREE_PATHS,
    exclude: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Return the file-level fingerprint of the watched paths.

    `exclude` esiste per il **testimone stesso**: vive dentro una cartella
    sorvegliata, e senza esclusione si vedrebbe come «aggiunto fuori banda» al
    primo controllo. Si esclude un file dichiarato, non una classe di file.
    """
    radice = Path(root).resolve()
    esclusi = {voce.strip().lstrip("./") for voce in exclude if voce.strip()}
    files: dict[str, str] = {}
    for relativo in paths:
        if not str(relativo).strip():
            # Un percorso vuoto non e' "tutta la radice": e' un input che non dice
            # niente. Il CLI e il server devono rifiutarlo allo stesso modo (4o
            # gate di ENG-002, residuo N5/L1).
            raise TreeError("percorso sorvegliato vuoto: indica almeno una sottocartella")
        if "\x00" in str(relativo):
            raise TreeError("percorso sorvegliato con byte NUL: non e' un percorso valido")
        candidato = Path(relativo)
        base = (candidato if candidato.is_absolute() else radice / candidato).resolve()
        if base != radice and radice not in base.parents:
            # Un percorso che esce dalla radice non si legge e non si legge «un
            # po'»: si rifiuta prima. F-A del gate di ENG-002: il vecchio codice
            # apriva il file e falliva dopo, quindi leggeva byte fuori dalla root.
            raise TreeError(
                f"percorso sorvegliato fuori dalla radice: {relativo}"
            )
        base = radice / base.relative_to(radice) if base != radice else radice
        if base.is_file():
            candidati = [base]
        elif base.is_dir():
            candidati = sorted(p for p in base.rglob("*") if p.is_file())
        else:
            continue
        for percorso in candidati:
            if "__pycache__" in percorso.parts or percorso.suffix == ".pyc":
                continue
            try:
                contenuto = percorso.read_bytes()
            except OSError as exc:
                raise TreeError(f"file illeggibile '{percorso}': {exc}") from exc
            chiave = percorso.relative_to(radice).as_posix()
            if chiave in esclusi:
                continue
            files[chiave] = hashlib.sha256(contenuto).hexdigest()
    return {
        "tree_version": TREE_VERSION,
        "paths": list(paths),
        "exclude": sorted(esclusi),
        "files": dict(sorted(files.items())),
    }


def _tree_digest(report: dict[str, Any]) -> str:
    """Return the seal of a tree witness."""
    senza = {
        chiave: valore
        for chiave, valore in report.items()
        if chiave not in ("digest", "recorded_at")
    }
    return f"tree_{hashlib.sha256(canonical_payload(senza).encode('utf-8')).hexdigest()}"


def create_witness(
    root: str | Path,
    paths: tuple[str, ...] = DEFAULT_TREE_PATHS,
    *,
    recorded_at: str | None = None,
    exclude: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Build a sealed witness of the tree."""
    report = tree_fingerprint(root, paths, exclude)
    report["recorded_at"] = recorded_at or datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )
    report["digest"] = _tree_digest(report)
    return report


def save_witness(path: str | Path, witness: dict[str, Any]) -> None:
    """Write a witness atomically."""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temporaneo = file_path.with_name(f".{file_path.name}.tmp")
    temporaneo.write_text(yaml.safe_dump(witness, allow_unicode=True, sort_keys=True), encoding="utf-8")
    temporaneo.replace(file_path)


def load_witness(path: str | Path) -> dict[str, Any]:
    """Read a witness file."""
    file_path = Path(path)
    try:
        data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise TreeError(f"testimone illeggibile '{file_path}': {exc}") from exc
    except yaml.YAMLError as exc:
        raise TreeError(f"YAML non valido in '{file_path}': {exc}") from exc
    if not isinstance(data, dict):
        raise TreeError(f"'{file_path}': il testimone deve essere una mappatura")
    return data


def compare_tree(
    witness: dict[str, Any],
    current: dict[str, Any],
    cover: dict[str, tuple[str, ...]] | None = None,
) -> list[str]:
    """Return the contaminations: changes no evidence declares.

    `cover` mappa percorso -> evidenze che lo citano. Una modifica senza nessuna
    evidenza che la nomini e' una contaminazione.
    """
    problemi: list[str] = []
    if witness.get("tree_version") != TREE_VERSION:
        return [f"tree_version {witness.get('tree_version')!r} non ammessa"]
    if witness.get("digest") and witness["digest"] != _tree_digest(witness):
        problemi.append(
            "il testimone dell'albero e' stato modificato dopo essere stato sigillato"
        )
    prima = witness.get("files")
    dopo = current.get("files")
    if not isinstance(prima, dict) or not isinstance(dopo, dict):
        return problemi + ["testimone o stato attuale senza 'files'"]
    copertura = cover or {}

    def nominate(percorso: str) -> tuple[str, ...]:
        """Evidenze che citano il percorso, esatto o come cartella che lo contiene."""
        esatte = copertura.get(percorso, ())
        if esatte:
            return esatte
        trovate: list[str] = []
        for riferimento in copertura:
            if percorso.startswith(riferimento.rstrip("/") + "/"):
                trovate.extend(copertura[riferimento])
        return tuple(trovate)

    for percorso in sorted(set(prima) - set(dopo)):
        quali = nominate(percorso)
        if not quali:
            problemi.append(f"RIMOSSO fuori banda: {percorso}")
    for percorso in sorted(set(dopo) - set(prima)):
        quali = nominate(percorso)
        if not quali:
            problemi.append(f"AGGIUNTO fuori banda: {percorso}")
    for percorso in sorted(set(prima) & set(dopo)):
        if prima[percorso] != dopo[percorso] and not nominate(percorso):
            problemi.append(f"MODIFICATO fuori banda: {percorso}")
    return problemi


def coverage_map(records: list[Evidence]) -> dict[str, tuple[str, ...]]:
    """Map every path named by an evidence to the evidences that name it."""
    mappa: dict[str, list[str]] = {}
    for record in records:
        for riferimento in record.references:
            testo = riferimento.strip().replace("\\", "/").lstrip("./")
            if not testo:
                continue
            mappa.setdefault(testo, []).append(record.evidence_id)
    return {chiave: tuple(valori) for chiave, valori in mappa.items()}
