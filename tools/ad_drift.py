"""Registro drift: divergenze fra documenti e realta'.

Il registro vive in ``drift/README.md``: una voce per divergenza trovata e non
ancora sanata. La regola che lo governa e' **si registra, non si corregge in
silenzio**: la correzione richiede un Decision Record, la registrazione no.

Questo modulo verifica che il registro sia leggibile e coerente. Una chiusura
senza Decision Record esistente non e' una chiusura: e' una modifica silenziosa
con un'etichetta.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import ad_docs

REGISTER = "drift/README.md"
DECISIONS_DIR = "DECISIONI"

ID_RE = re.compile(r"^(DRIFT-\d{3})\s+—\s+(.+)$", re.M)
FIELD_RE = re.compile(r"^\|\s+\*\*(.+?)\*\*\s+\|\s*(.*?)\s*\|\s*$", re.M)
DECISION_RE = re.compile(r"^DEC-\d{4}$")
DATA_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")

REQUIRED_FIELDS: tuple[str, ...] = (
    "Severita'",
    "Documento dice",
    "Realta' dice",
    "Rischio",
    "Stato",
    "Evidenza",
)
CLOSING_FIELDS: tuple[str, ...] = ("Chiuso", "Decisione")

SEVERITIES: tuple[str, ...] = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL")
STATES: tuple[str, ...] = ("OPEN", "FIXED", "CLOSED", "ACCEPTED")


@dataclass(frozen=True)
class Drift:
    """Una divergenza registrata."""

    id: str
    title: str
    fields: dict[str, str]

    def field(self, name: str) -> str:
        """Return the raw value of a field, or an empty string."""
        return self.fields.get(name, "").strip()

    @property
    def severity(self) -> str:
        """Return the severity, normalised."""
        return self.field("Severita'").upper()

    @property
    def state(self) -> str:
        """Return the state, taking the first token of the field."""
        raw = self.field("Stato").upper()
        return raw.split()[0] if raw else ""

    @property
    def closed(self) -> bool:
        """True when the entry claims to be resolved."""
        return self.state in ("FIXED", "CLOSED")


def register_path(root: Path | str | None = None) -> Path:
    """Return the path of the drift register."""
    base = Path(root) if root is not None else ad_docs.DOCS_ROOT
    return base / REGISTER


def load(root: Path | str | None = None) -> list[Drift]:
    """Read every entry of the drift register.

    Args:
        root: Root of AD Projects (default: the root of this checkout).

    Returns:
        The entries, in file order.
    """
    path = register_path(root)
    if not path.is_file():
        return []
    text = path.read_text(encoding="utf-8")
    entries: list[Drift] = []
    for block in re.split(r"^##\s+(?=DRIFT-\d{3})", text, flags=re.M)[1:]:
        head = ID_RE.match(block)
        if head is None:
            continue
        fields = {key.strip(): value.strip() for key, value in FIELD_RE.findall(block)}
        entries.append(Drift(head.group(1), head.group(2).strip(), fields))
    return entries


def problems(root: Path | str | None = None) -> list[str]:
    """Return what makes the register incoherent.

    Args:
        root: Root of AD Projects (default: the root of this checkout).

    Returns:
        One message per problem. An empty list means the register is coherent.
    """
    base = Path(root) if root is not None else ad_docs.DOCS_ROOT
    entries = load(base)
    if not entries:
        return [f"nessuna voce in {REGISTER}"]

    issues: list[str] = []
    ids = [entry.id for entry in entries]
    # Gli id non si rinumerano: una voce tolta **lascia il suo numero**, come gli id
    # atomici non si riusano (2026-10-13). Quindi si pretende che **crescano**, non che
    # siano contigui — altrimenti togliere una voce obbligherebbe a riscrivere i numeri,
    # e ogni citazione a un id diventerebbe falsa. Il 2026-10-13 ho tolto da questa
    # versione le voci che riguardavano mondi che non esistono qui, e due di quelle
    # citazioni (`DRIFT-010`) restano valide proprio grazie a questa regola.
    if ids != sorted(ids) or len(set(ids)) != len(ids):
        issues.append(f"ID fuori ordine o duplicati: trovati {ids}")

    for entry in entries:
        for name in REQUIRED_FIELDS:
            if not entry.field(name):
                issues.append(f"{entry.id}: manca il campo '{name}'")
        if entry.severity and entry.severity not in SEVERITIES:
            issues.append(
                f"{entry.id}: severita' '{entry.severity}' non ammessa: {list(SEVERITIES)}"
            )
        if entry.state and entry.state not in STATES:
            issues.append(f"{entry.id}: stato '{entry.state}' non ammesso: {list(STATES)}")
        if not entry.closed:
            continue
        for name in CLOSING_FIELDS:
            if not entry.field(name):
                issues.append(f"{entry.id}: chiuso ma manca '{name}' (DEC-0012)")
        if entry.field("Chiuso") and not DATA_RE.match(entry.field("Chiuso")):
            issues.append(f"{entry.id}: 'Chiuso' non e' una data ISO: {entry.field('Chiuso')}")
        decision = entry.field("Decisione")
        if decision:
            if not DECISION_RE.match(decision):
                issues.append(f"{entry.id}: '{decision}' non ha la forma DEC-nnnn")
            elif not list((base / DECISIONS_DIR).glob(f"{decision}-*.md")):
                issues.append(f"{entry.id}: Decision Record '{decision}' inesistente in {DECISIONS_DIR}/")
    return issues
