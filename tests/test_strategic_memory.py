#!/usr/bin/env python3
"""Gate di integrità della catena documentale di AD Projects.

Due garanzie, entrambe deterministiche e a costo zero token (fascia 1 di
MODEL-ROUTING.md):

1. **Snapshot** — i documenti canonici della root non sono cambiati rispetto
   allo snapshot approvato in ``strategic_memory/_frozen_before.json``.
   Accettare una modifica richiede un Decision Record in ``DECISIONI/`` e la
   rigenerazione esplicita:

       python3 tests/test_strategic_memory.py --update

2. **Invarianti strutturali** — ciò che i documenti dichiarano è ancora
   presente nel testo: campi di registry su ogni card, campi del layer di
   comunicazione, regole di runtime, retrieval della memoria strategica.

Uso:
    python3 tests/test_strategic_memory.py            # verifica
    python3 tests/test_strategic_memory.py --update   # accetta lo stato corrente
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "strategic_memory" / "_frozen_before.json"
DOC_GLOB = "*.md"

#: Campi che AGENT-CARDS-V2.md dichiara presenti su ogni card.
REQUIRED_CARD_FIELDS = (
    "authorized_task_types",
    "excluded_task_types",
    "permissions",
    "autonomy",
    "escalation",
    "definition_of_done",
)

#: Messaggi ammessi dal layer di comunicazione.
MESSAGE_TYPES = ("request", "evidence", "proposal", "dependency", "blocker", "result")

SNAPSHOT_NOTE = (
    "Snapshot di integrità dei documenti canonici della root di AD Projects. "
    "Rigenerare solo con un Decision Record approvato: "
    "python3 tests/test_strategic_memory.py --update"
)


def digest(path: Path) -> str:
    """Return the SHA-256 of ``path``."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_documents() -> list[Path]:
    """Return the root Markdown documents, sorted by name."""
    return sorted(ROOT.glob(DOC_GLOB), key=lambda p: p.name)


def load_documents() -> dict[str, str]:
    """Return the ``documents`` map of the approved snapshot."""
    if not SNAPSHOT.exists():
        raise AssertionError(
            f"snapshot assente: {SNAPSHOT.relative_to(ROOT)}. "
            "Rigeneralo con: python3 tests/test_strategic_memory.py --update"
        )
    data = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    documents = data.get("documents")
    if not isinstance(documents, dict) or not documents:
        raise AssertionError(
            f"{SNAPSHOT.relative_to(ROOT)}: chiave 'documents' assente o vuota"
        )
    return documents


def write_snapshot() -> int:
    """Rewrite the snapshot from the current documents. Explicit acceptance only."""
    documents = {path.name: digest(path) for path in canonical_documents()}
    SNAPSHOT.write_text(
        json.dumps(
            {"note": SNAPSHOT_NOTE, "documents": documents},
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"snapshot aggiornato: {len(documents)} documenti canonici")
    for name in documents:
        print(f"  {name}")
    return 0


def check_snapshot(documents: dict[str, str]) -> None:
    """Assert every tracked document is unchanged and every document is tracked."""
    for name, expected in documents.items():
        path = ROOT / name
        if not path.exists():
            raise AssertionError(
                f"{name}: documento canonico tracciato ma assente. "
                "Se è stato eliminato, registra un Decision Record e rigenera lo snapshot."
            )
        current = digest(path)
        if current != expected:
            raise AssertionError(
                f"{name}: modificato rispetto allo snapshot approvato. "
                "Se la modifica è voluta, registra un Decision Record in DECISIONI/ "
                "e rigenera lo snapshot con --update."
            )

    untracked = sorted({p.name for p in canonical_documents()} - set(documents))
    if untracked:
        raise AssertionError(
            "documenti canonici non tracciati nello snapshot: "
            + ", ".join(untracked)
            + ". Rigenera lo snapshot con --update dopo il Decision Record."
        )


def check_card_registry(cards: str) -> int:
    """Assert every card carries the registry fields the document declares."""
    blocks = cards.split("\n### ")[1:]
    assert blocks, "AGENT-CARDS-V2.md: nessuna card trovata"
    for block in blocks:
        card_id = block.splitlines()[0].strip()
        for field in REQUIRED_CARD_FIELDS:
            assert f"{field}:" in block, f"card '{card_id}': campo di registry mancante '{field}'"

    master = cards.split("### lb-master-orchestrator", 1)[1].split("### ", 1)[0]
    assert "ui_implementation" not in master, (
        "lb-master-orchestrator non può autorizzare ui_implementation"
    )
    assert "ui_implementation" in cards, "nessuna card autorizza ui_implementation"
    return len(blocks)


def check_communication(comm: str) -> None:
    """Assert the communication layer still declares its schema and boundaries."""
    for field in ("sender", "recipient", "task_id", "message_type", "evidence_reference"):
        assert field in comm, f"COMMUNICATION.md: campo mancante '{field}'"
    for message_type in MESSAGE_TYPES:
        assert message_type in comm, f"COMMUNICATION.md: message_type mancante '{message_type}'"
    assert "strategic memory" in comm.lower(), (
        "COMMUNICATION.md non dichiara che la strategic memory non è condivisa per default"
    )


def check_runtime(runtime: str) -> None:
    """Assert the runtime still defines permissions as an intersection."""
    assert "intersezione" in runtime, (
        "RUNTIME.md: i permessi dell'istanza non sono più definiti come intersezione"
    )


def check_strategic_memory() -> None:
    """Assert retrieval works and the synthesis keeps its output labels."""
    out = subprocess.check_output(
        [
            sys.executable,
            str(ROOT / "strategic_memory" / "retrieve.py"),
            "posizionamento nuovo SaaS B2B",
        ],
        text=True,
    )
    low = out.lower()
    for needle in ("kotler", "ries", "rackham", "cialdini"):
        assert needle in low, f"retrieve.py non recupera '{needle}' per la query di prova"

    synthesis = (ROOT / "strategic_memory" / "cross_framework" / "synthesis.md").read_text(
        encoding="utf-8"
    )
    for label in ("INSIGHT", "DECISIONE", "AZIONE", "METRICA", "FACT", "ASSUMPTION"):
        assert label in synthesis, f"synthesis.md: etichetta mancante '{label}'"


def check_required_documents() -> None:
    """Assert the canonical chain is present as files."""
    for name in ("GOVERNANCE-AZIENDALE.md", "AGENTI-V2.md", "AGENT-CARDS-V2.md"):
        assert (ROOT / name).exists(), f"documento della catena assente: {name}"


def verify() -> int:
    """Run every check and report."""
    documents = load_documents()
    check_snapshot(documents)
    check_required_documents()

    cards = (ROOT / "AGENT-CARDS-V2.md").read_text(encoding="utf-8")
    card_count = check_card_registry(cards)
    check_communication((ROOT / "COMMUNICATION.md").read_text(encoding="utf-8"))
    check_runtime((ROOT / "RUNTIME.md").read_text(encoding="utf-8"))
    check_strategic_memory()

    print(
        f"PASS — {len(documents)} documenti canonici invariati, "
        f"{card_count} card con registry completo, retrieval e layer verificati"
    )
    return 0


def main(argv: list[str]) -> int:
    """Dispatch between verification and explicit snapshot acceptance."""
    if "--update" in argv:
        return write_snapshot()
    return verify()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
