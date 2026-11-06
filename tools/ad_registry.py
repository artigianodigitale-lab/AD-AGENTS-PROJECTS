"""Registry delle Agent Card letto dai documenti normativi.

Due cataloghi, due formati:

* ``AGENT-CARDS-V2.md`` — una card per intestazione ``### <id>`` con un blocco
  YAML completo.
* ``AGENT-CARDS-BUSINESS.md`` — la card di governance in un blocco YAML, gli
  specialisti in una **tabella Markdown** i cui campi comuni vivono in un
  blocco separato e vanno espansi per eredita'.

Il parser non inventa nulla: un campo che il documento non dichiara resta
assente e finisce in ``Card.missing_fields``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import yaml

import ad_docs

#: Livelli di permesso ordinabili. Un valore non noto vale -1 (illeggibile).
PERMISSION_LEVELS: dict[str, int] = {"none": 0, "read": 1, "write": 2}

#: Campi senza i quali un contract non e' verificabile (AGENT-CARDS-V2.md).
REQUIRED_REGISTRY_FIELDS: tuple[str, ...] = (
    "capabilities",
    "authorized_task_types",
    "excluded_task_types",
    "permissions",
    "tools",
    "accessible_memory",
    "autonomy",
    "escalation",
    "definition_of_done",
)

#: Campi che ``AGENTI-V2.md`` pretende su ogni card del registry. Sono piu' di
#: quelli che i validatori usano: servono a misurare la completezza del
#: catalogo, non a decidere un match.
GOVERNANCE_REGISTRY_FIELDS: tuple[str, ...] = (
    "id",
    "version",
    "mission",
    *REQUIRED_REGISTRY_FIELDS,
)

_YAML_BLOCK = re.compile(r"```ya?ml\s*\n(.*?)```", re.DOTALL)
_H2 = re.compile(r"^## (?P<title>.+?)\s*$", re.MULTILINE)
_H3 = re.compile(r"^### (?P<id>[a-z0-9-]+)\s*$", re.MULTILINE)
_BUSINESS_ROW = re.compile(
    r"^\|\s*`(?P<id>[a-z0-9-]+)`\s*\|(?P<mission>[^|]*)\|(?P<excluded>[^|]*)\|(?P<models>[^|]*)\|\s*$",
    re.MULTILINE,
)


@dataclass(frozen=True)
class Card:
    """Una Agent Card del registry."""

    id: str
    name: str
    domain: str  # technical | business
    type: str
    version: str
    status: str
    mission: str
    capabilities: tuple[str, ...]
    authorized_task_types: tuple[str, ...] | None
    excluded_task_types: tuple[str, ...] | None
    permissions: dict[str, str]
    tools: tuple[str, ...]
    accessible_memory: tuple[str, ...]
    autonomy: dict[str, str]
    escalation: tuple[str, ...]
    definition_of_done: tuple[str, ...]
    formation: dict[str, Any]
    source: str
    missing_fields: tuple[str, ...] = ()
    governance_missing_fields: tuple[str, ...] = ()

    @property
    def inactive(self) -> bool:
        """True when the card is in the only state a contract may activate."""
        return self.status == "inactive"

    @property
    def assignable(self) -> bool:
        """True when an explicit match is verifiable (SPECIALIZATION.md).

        Una card senza ``authorized_task_types`` non e' assegnabile: la
        governance impone STOP, non l'assegnazione all'agente piu' vicino.
        """
        return bool(self.authorized_task_types) and self.inactive

    @property
    def is_governance(self) -> bool:
        """True for the governing roles, which never execute production work."""
        return self.type == "governance"

    def allows_task_type(self, task_type: str) -> bool:
        """Return True when ``task_type`` is explicitly authorised."""
        return task_type in (self.authorized_task_types or ())

    def excludes_task_type(self, task_type: str) -> bool:
        """Return True when ``task_type`` is explicitly excluded."""
        return task_type in (self.excluded_task_types or ())

    def permission_level(self, scope: str) -> int:
        """Return the numeric level the card grants on ``scope``."""
        return PERMISSION_LEVELS.get(str(self.permissions.get(scope, "none")).lower(), -1)

    def summary(self) -> str:
        """Return a one-line human description."""
        return f"{self.id} [{self.domain}/{self.type}] stato={self.status}"


def _as_tuple(value: Any) -> tuple[str, ...]:
    """Normalise a YAML scalar or list into a tuple of strings."""
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    return (str(value),)


def _as_mapping(value: Any) -> dict[str, str]:
    """Normalise a YAML mapping into ``dict[str, str]``."""
    if isinstance(value, dict):
        return {str(k): str(v) for k, v in value.items()}
    return {}


def _first_yaml_block(text: str) -> dict[str, Any]:
    """Return the first YAML mapping of ``text``, or an empty mapping."""
    match = _YAML_BLOCK.search(text)
    if match is None:
        return {}
    data = yaml.safe_load(match.group(1))
    return data if isinstance(data, dict) else {}


def _clean_cell(value: str) -> str:
    """Return a table cell without backticks and surrounding whitespace."""
    return value.replace("`", "").strip()


def _missing(merged: dict[str, Any], fields: tuple[str, ...]) -> tuple[str, ...]:
    """Return the fields of ``fields`` the document does not declare."""
    return tuple(name for name in fields if merged.get(name) in (None, "", [], {}))


def _card_from_mapping(
    data: dict[str, Any],
    *,
    domain: str,
    source: str,
    inherited: dict[str, Any] | None = None,
) -> Card:
    """Build a Card merging declared fields over inherited common fields."""
    merged: dict[str, Any] = {**(inherited or {}), **data}
    card_id = str(merged.get("id", "")).strip()
    authorized = merged.get("authorized_task_types")
    excluded = merged.get("excluded_task_types")
    return Card(
        id=card_id,
        name=str(merged.get("name") or card_id),
        domain=domain,
        type=str(merged.get("type", "")),
        version=str(merged.get("version", "")),
        status=str(merged.get("status", "")),
        mission=str(merged.get("mission", "")).strip(),
        capabilities=_as_tuple(merged.get("capabilities")),
        authorized_task_types=None if authorized is None else _as_tuple(authorized),
        excluded_task_types=None if excluded is None else _as_tuple(excluded),
        permissions=_as_mapping(merged.get("permissions")),
        tools=_as_tuple(merged.get("tools")),
        accessible_memory=_as_tuple(merged.get("accessible_memory")),
        autonomy=_as_mapping(merged.get("autonomy")),
        escalation=_as_tuple(merged.get("escalation")),
        definition_of_done=_as_tuple(merged.get("definition_of_done")),
        formation=merged.get("formation") if isinstance(merged.get("formation"), dict) else {},
        source=source,
        missing_fields=_missing(merged, REQUIRED_REGISTRY_FIELDS),
        governance_missing_fields=_missing(merged, GOVERNANCE_REGISTRY_FIELDS),
    )


def _sections(text: str) -> dict[str, str]:
    """Split a document into ``## `` sections, keyed by heading."""
    parts = _H2.split(text)
    return {parts[i].strip(): parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def parse_technical(text: str) -> list[Card]:
    """Parse every card of ``AGENT-CARDS-V2.md``.

    Args:
        text: Full text of the technical catalog.

    Returns:
        The cards in document order.
    """
    parts = _H3.split(text)
    cards: list[Card] = []
    for index in range(1, len(parts) - 1, 2):
        heading_id = parts[index].strip()
        body = parts[index + 1]
        data = _first_yaml_block(body)
        if not data:
            continue
        data.setdefault("id", heading_id)
        cards.append(_card_from_mapping(data, domain="technical", source=ad_docs.TECH_CARDS))
    return cards


def parse_business(text: str) -> list[Card]:
    """Parse every card of ``AGENT-CARDS-BUSINESS.md``.

    Expands the inherited common fields onto the specialists declared in the
    Markdown table, and records what the table does not declare.

    Args:
        text: Full text of the business catalog.

    Returns:
        The cards in document order: governance first, then the specialists.
    """
    sections = _sections(text)
    common: dict[str, Any] = {}
    for title, body in sections.items():
        if title.lower().startswith("campi ereditati"):
            common = _first_yaml_block(body)

    cards: list[Card] = []

    governance = sections.get("Governance", "")
    for match in _YAML_BLOCK.finditer(governance):
        data = yaml.safe_load(match.group(1))
        if isinstance(data, dict) and "id" in data:
            # ``mission`` non si eredita: quella comune descrive uno specialista,
            # non l'orchestratore.
            inherited = {k: v for k, v in common.items() if k != "mission"}
            cards.append(
                _card_from_mapping(
                    data, domain="business", source=ad_docs.BUSINESS_CARDS, inherited=inherited
                )
            )

    registry = sections.get("Specialisti business", "")

    # Formato corrente: una card per blocco YAML.
    blocks: list[dict[str, Any]] = []
    for match in _YAML_BLOCK.finditer(registry):
        data = yaml.safe_load(match.group(1))
        if isinstance(data, dict) and "id" in data:
            blocks.append(data)
    if blocks:
        for data in blocks:
            cards.append(
                _card_from_mapping(
                    data, domain="business", source=ad_docs.BUSINESS_CARDS, inherited=common
                )
            )
        return cards

    # Fallback: formato a tabella, per i cataloghi non ancora normalizzati.
    # Le esclusioni restano prosa: senza campi strutturati la card non e'
    # assegnabile, ed e' giusto che il registry lo dica.
    for match in _BUSINESS_ROW.finditer(registry):
        row = {
            "id": match.group("id"),
            "type": "business",
            "mission": _clean_cell(match.group("mission")),
            "formation": {
                "models": [
                    item.strip()
                    for item in _clean_cell(match.group("models")).split(",")
                    if item.strip()
                ],
                "review": (common.get("formation") or {}).get("review", "quarterly")
                if isinstance(common.get("formation"), dict)
                else "quarterly",
            },
            "_exclusions_prose": _clean_cell(match.group("excluded")),
        }
        cards.append(
            _card_from_mapping(
                row, domain="business", source=ad_docs.BUSINESS_CARDS, inherited=common
            )
        )
    return cards


def load() -> dict[str, Card]:
    """Load and merge both catalogs, keyed by card id.

    Returns:
        Every card of the registry.

    Raises:
        ValueError: If the two catalogs declare the same id.
    """
    cards = parse_technical(ad_docs.read(ad_docs.TECH_CARDS))
    cards += parse_business(ad_docs.read(ad_docs.BUSINESS_CARDS))
    registry: dict[str, Card] = {}
    for card in cards:
        if card.id in registry:
            raise ValueError(f"id duplicato nel registry: {card.id}")
        registry[card.id] = card
    return registry


def by_domain(registry: dict[str, Card], domain: str) -> dict[str, Card]:
    """Return the subset of ``registry`` belonging to ``domain``."""
    return {cid: card for cid, card in registry.items() if card.domain == domain}


def task_type_index(registry: dict[str, Card], domain: str | None = None) -> dict[str, list[str]]:
    """Map every authorised task type to the cards that authorise it."""
    index: dict[str, list[str]] = {}
    for card in registry.values():
        if domain and card.domain != domain:
            continue
        for task_type in card.authorized_task_types or ():
            index.setdefault(task_type, []).append(card.id)
    return index
