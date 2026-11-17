"""Catalogo dei gate e owner di default delle evidenze.

Il catalogo canonico e' ``QUALITY-GATES.md``. ``GOVERNANCE-AZIENDALE.md``
rimanda a quel documento in caso di divergenza. Questo modulo legge **entrambi**
i testi e segnala lo scostamento invece di fidarsi di una costante.
"""

from __future__ import annotations

import re

import ad_docs

#: Catalogo atteso. Se i documenti divergono da questa tupla, ``drift()`` lo dice.
GATE_CATALOG: tuple[str, ...] = (
    "QA",
    "Code Review",
    "Security",
    "Architecture",
    "UX",
    "Accessibility",
    "Performance",
    "Documentation",
    "Strategy",
    "Brand",
    "Legal",
    "GDPR",
    "Finance",
    "SEO",
    "Platform",
)

#: Owner di default delle evidenze (QUALITY-GATES.md, "Owner delle evidenze").
#: Il contract puo' nominare un owner diverso purche' indipendente.
GATE_OWNER_HINTS: dict[str, tuple[str, ...]] = {
    "QA": ("qa",),
    "Code Review": ("review",),
    "Security": ("security",),
    "Architecture": ("architect",),
    "UX": ("ux",),
    "Accessibility": ("accessibility",),
    "Performance": ("performance",),
    "Documentation": ("technical-writer",),
    "Strategy": ("lb-business-coach",),
    "Brand": ("lb-brand-identity", "lb-archetypal-branding"),
    "Legal": ("lb-legal",),
    "GDPR": ("gdpr",),
    "Finance": ("lb-finance",),
    "SEO": ("seo",),
    "Platform": ("platform",),
}

_GOVERNANCE_MARKER = "I gate possibili sono:"
_QUALITY_MARKER = "I gate disponibili sono:"


def _parse_gate_sentence(text: str, marker: str) -> tuple[str, ...]:
    """Extract the gate names from the sentence introduced by ``marker``."""
    index = text.find(marker)
    if index < 0:
        return ()
    tail = text[index + len(marker) :]
    stop = tail.find(".")
    sentence = tail if stop < 0 else tail[:stop]
    names: list[str] = []
    for chunk in sentence.split(","):
        for piece in re.split(r"\s+e\s+", chunk):
            piece = piece.strip().strip(".")
            if piece:
                names.append(piece)
    return tuple(names)


def governance_catalog() -> tuple[str, ...]:
    """Return the gate names declared by ``GOVERNANCE-AZIENDALE.md``."""
    return _parse_gate_sentence(ad_docs.read(ad_docs.GOVERNANCE), _GOVERNANCE_MARKER)


def quality_catalog() -> tuple[str, ...]:
    """Return the gate names declared by ``QUALITY-GATES.md``."""
    return _parse_gate_sentence(ad_docs.read(ad_docs.QUALITY_GATES), _QUALITY_MARKER)


def is_gate(name: str) -> bool:
    """Return True when ``name`` is a catalog gate, case-insensitively."""
    lowered = name.strip().lower()
    return any(lowered == gate.lower() for gate in GATE_CATALOG)


def canonical(name: str) -> str | None:
    """Return the catalog spelling of ``name``, or None when unknown."""
    lowered = name.strip().lower()
    for gate in GATE_CATALOG:
        if lowered == gate.lower():
            return gate
    return None


def owners(gate: str) -> tuple[str, ...]:
    """Return the default evidence owners for ``gate``."""
    canonical_name = canonical(gate) or gate
    return GATE_OWNER_HINTS.get(canonical_name, ())


def drift() -> list[str]:
    """Return the divergences between the documents and the expected catalog.

    Returns:
        One message per divergence; an empty list means the two normative
        documents agree with :data:`GATE_CATALOG`.
    """
    problems: list[str] = []
    expected = set(GATE_CATALOG)

    for label, names in (
        (ad_docs.QUALITY_GATES, quality_catalog()),
        (ad_docs.GOVERNANCE, governance_catalog()),
    ):
        if not names:
            problems.append(f"{label}: frase del catalogo gate non trovata")
            continue
        missing = sorted(expected - set(names))
        extra = sorted(set(names) - expected)
        if missing:
            problems.append(f"{label}: gate mancanti {missing}")
        if extra:
            problems.append(f"{label}: gate non previsti {extra}")
    return problems
