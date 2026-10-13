"""Evidenze e verdetto del Quality Gate (QUALITY-GATES.md).

I documenti dicono **cosa** deve dichiarare un'evidenza ma non in quale
contenitore. Questo modulo fissa il contenitore minimo:

```yaml
task_id: BIO-142
gate: QA
outcome: PASS          # PASS | FAIL
producer: qa           # card che ha prodotto l'evidenza
artifact_producer: backend   # opzionale
timestamp: 2026-10-08T07:20:00+02:00   # opzionale, per il rework
references: [artefatto, comando]
notes: ""
```

Un'evidenza che non dichiara task_id, gate, esito e produttore non conta.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

import ad_contract
import ad_gates

VALID_OUTCOMES: tuple[str, ...] = ("PASS", "FAIL")
EVIDENCE_SUFFIXES: tuple[str, ...] = (".yaml", ".yml")

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

    def describe(self) -> str:
        """Return a one-line description."""
        return f"{self.path.name}: gate={self.gate} outcome={self.outcome} producer={self.producer}"

    def side_effect(self, key: str) -> str:
        """Return the declared value for one side-effect key, or an empty string."""
        return dict(self.side_effects).get(key, "")


@dataclass(frozen=True)
class GateResult:
    """The verdict on a single required gate."""

    gate: str
    state: str  # PASS | FAIL | MISSING | INVALID
    producer: str
    detail: str


@dataclass(frozen=True)
class Verdict:
    """The Quality Gate verdict for a contract."""

    outcome: str  # ACCEPT | REJECT
    human_gate: bool
    gates: tuple[GateResult, ...]
    notes: tuple[str, ...]


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
    if not isinstance(claims, dict):
        raise EvidenceError(f"'{file_path}': 'claims' deve essere una mappatura")

    return Evidence(
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
    )


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
                sorted(p for p in path.iterdir() if p.suffix.lower() in EVIDENCE_SUFFIXES)
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
            results.append(GateResult(gate, "INVALID", record.producer, problem))
            continue
        if record.producer and record.producer not in ad_gates.owners(gate):
            owners = ad_gates.owners(gate)
            if owners:
                notes.append(
                    f"gate '{gate}': produttore '{record.producer}' diverso dall'owner di "
                    f"default {list(owners)}; ammesso se indipendente dall'esecutore"
                )
        results.append(
            GateResult(gate, record.outcome, record.producer, record.path.name)
        )

    if any(result.state in ("FAIL", "MISSING", "INVALID") for result in results):
        outcome = "REJECT"
    else:
        outcome = "ACCEPT"

    approval = contract.get("approval") or {}
    human_gate = bool(approval.get("human")) if isinstance(approval, dict) else False
    if outcome == "ACCEPT" and human_gate:
        notes.append(
            "ACCEPT non e' il rilascio: approval.human e' true, decide l'umano "
            "(QUALITY-GATES.md)"
        )

    return Verdict(outcome=outcome, human_gate=human_gate, gates=tuple(results), notes=tuple(notes))


def _validity_problem(
    record: Evidence, task_id: str, gate: str, executor: str, scope: str = ""
) -> str:
    """Return why the evidence does not count, or an empty string.

    Il controllo del `task_id` resta anche se `evaluate` adesso filtra prima di
    scegliere: questa e' la validita' di UNA evidenza per UN contract, e deve
    restare completa se qualcuno la chiama su un record che non e' il suo.
    """
    if record.task_id != task_id:
        return (
            f"task_id '{record.task_id}' diverso dal contract '{task_id}': l'evidenza non conta"
        )
    if record.outcome not in VALID_OUTCOMES:
        return f"esito '{record.outcome or 'assente'}' non ammesso: serve PASS o FAIL"
    if not record.producer:
        return "produttore non dichiarato: l'evidenza non conta"
    if record.producer == executor:
        return (
            f"prodotta da '{record.producer}', che e' l'esecutore del contract: "
            "chi produce l'artefatto non ne valida il gate"
        )
    if record.artifact_producer and record.artifact_producer != executor:
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
