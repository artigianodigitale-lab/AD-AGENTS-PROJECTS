"""Milestone e sprint: la storia documentata di un progetto.

Struttura attesa dentro la cartella di un progetto:

```text
<progetto>/
  Milestone 1/
    REPORT.md              report della milestone, step by step
    Sprint 1/
      PROMPT.md            il prompt dello sprint, scritto prima di eseguirlo
      REPORT.md            cosa e' stato fatto e come, rilasciato alla chiusura
    Sprint 2/
      PROMPT.md
      REPORT.md
  Milestone 2/
    ...
```

Una milestone senza `REPORT.md` non e' chiusa. Uno sprint senza `PROMPT.md` non e'
stato aperto; senza `REPORT.md` non e' stato chiuso e non si passa al successivo.

Questo modulo non inventa la storia: la **verifica** e la **avvia** dai modelli in
`milestone/`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import ad_docs
import ad_scope

MILESTONE_DIR = re.compile(r"^Milestone\s+(\d+)$", re.IGNORECASE)
SPRINT_DIR = re.compile(r"^Sprint\s+(\d+)$", re.IGNORECASE)

MILESTONE_REPORT = "REPORT.md"
SPRINT_PROMPT = "PROMPT.md"
SPRINT_REPORT = "REPORT.md"

#: La cartella che raccoglie i documenti di un progetto, dentro il progetto.
#: Regola del CEO, 2026-10-08: «tutte le cartelle e i file che crei devono andare a
#: finire dentro al progetto di cui stiamo parlando». La root di AD Projects tiene
#: la macchina, non le carte dei progetti.
PROJECT_DOCS = "Analisi-Prompt-Report"

TEMPLATE_ROOT = "milestone"
TEMPLATE_MILESTONE = "_TEMPLATE-MILESTONE.md"
TEMPLATE_SPRINT_PROMPT = "_TEMPLATE-SPRINT-PROMPT.md"
TEMPLATE_SPRINT_REPORT = "_TEMPLATE-SPRINT-REPORT.md"


@dataclass(frozen=True)
class Sprint:
    """Uno sprint di una milestone."""

    number: int
    path: Path

    @property
    def has_prompt(self) -> bool:
        """True when the sprint prompt exists: the sprint was opened."""
        return (self.path / SPRINT_PROMPT).is_file()

    @property
    def has_report(self) -> bool:
        """True when the sprint report exists: the sprint was closed."""
        return (self.path / SPRINT_REPORT).is_file()


@dataclass(frozen=True)
class Milestone:
    """Una milestone di un progetto."""

    number: int
    path: Path
    sprints: tuple[Sprint, ...]

    @property
    def has_report(self) -> bool:
        """True when the milestone report exists: the milestone is documented."""
        return (self.path / MILESTONE_REPORT).is_file()


def template(name: str) -> str:
    """Return the text of a milestone template.

    Args:
        name: Template file name inside ``milestone/``.

    Returns:
        The template text.
    """
    return (ad_docs.DOCS_ROOT / TEMPLATE_ROOT / name).read_text(encoding="utf-8")


def scan(project: Path | str) -> list[Milestone]:
    """Read the milestone structure of a project.

    Args:
        project: Path of the project folder.

    Returns:
        The milestones found, ordered by number.
    """
    root = milestone_root(project)
    if not root.is_dir():
        return []
    found: list[Milestone] = []
    for entry in sorted(root.iterdir()):
        match = MILESTONE_DIR.match(entry.name)
        if not entry.is_dir() or match is None:
            continue
        sprints: list[Sprint] = []
        for child in sorted(entry.iterdir()):
            sprint_match = SPRINT_DIR.match(child.name)
            if child.is_dir() and sprint_match is not None:
                sprints.append(Sprint(int(sprint_match.group(1)), child))
        sprints.sort(key=lambda sprint: sprint.number)
        found.append(Milestone(int(match.group(1)), entry, tuple(sprints)))
    found.sort(key=lambda milestone: milestone.number)
    return found


def docs_dir(project: Path | str) -> Path:
    """Return the folder that holds a project's documents."""
    return Path(project) / PROJECT_DOCS


def milestone_root(project: Path | str) -> Path:
    """Return where the milestones of a project live.

    Dentro la cartella dei documenti, se esiste. Altrimenti nella radice del
    progetto: cosi' i progetti aperti prima di questa regola continuano a
    funzionare senza essere spostati.
    """
    docs = docs_dir(project)
    radice = Path(project)
    for candidata in (docs, radice):
        if not candidata.is_dir():
            continue
        try:
            if any(MILESTONE_DIR.match(voce.name) for voce in candidata.iterdir()):
                return candidata
        except OSError:
            continue
    return docs if docs.is_dir() else radice


def problems(project: Path | str) -> list[str]:
    """Return what is missing or out of order in a project's history.

    Args:
        project: Path of the project folder.

    Returns:
        One message per problem. An empty list means the history is complete.
    """
    milestones = scan(project)
    if not milestones:
        return ["nessuna Milestone: il progetto non ha una storia documentata"]

    issues: list[str] = []
    expected = list(range(1, len(milestones) + 1))
    actual = [milestone.number for milestone in milestones]
    if actual != expected:
        issues.append(f"milestone non contigue: trovate {actual}, attese {expected}")

    for milestone in milestones:
        if not milestone.has_report:
            issues.append(f"{milestone.path.name}: manca {MILESTONE_REPORT}")
        if not milestone.sprints:
            issues.append(f"{milestone.path.name}: nessuno sprint")
            continue
        expected_sprints = list(range(1, len(milestone.sprints) + 1))
        actual_sprints = [sprint.number for sprint in milestone.sprints]
        if actual_sprints != expected_sprints:
            issues.append(
                f"{milestone.path.name}: sprint non contigui: "
                f"trovati {actual_sprints}, attesi {expected_sprints}"
            )
        for sprint in milestone.sprints:
            label = f"{milestone.path.name}/{sprint.path.name}"
            if not sprint.has_prompt:
                issues.append(f"{label}: manca {SPRINT_PROMPT} (sprint mai aperto)")
            if not sprint.has_report:
                issues.append(f"{label}: manca {SPRINT_REPORT} (sprint mai chiuso)")
    return issues


def next_milestone(project: Path | str) -> int:
    """Return the number of the next milestone to open."""
    milestones = scan(project)
    return (milestones[-1].number + 1) if milestones else 1


def next_sprint(project: Path | str, milestone: int) -> int:
    """Return the number of the next sprint to open in a milestone."""
    for found in scan(project):
        if found.number == milestone:
            return (found.sprints[-1].number + 1) if found.sprints else 1
    return 1


def sprint_prompt(project: Path | str, milestone: int, sprint: int) -> Path:
    """Return the expected path of a sprint prompt.

    E' la convenzione che il validatore dei contract usa per verificare che uno
    sprint sia stato **aperto** prima di autorizzare scritture nel progetto
    (invariante 13).
    """
    return milestone_root(project) / f"Milestone {milestone}" / f"Sprint {sprint}" / SPRINT_PROMPT


def _fill(template_text: str, values: dict[str, str]) -> str:
    """Replace ``{{chiave}}`` placeholders in a template."""
    text = template_text
    for key, value in values.items():
        text = text.replace(f"{{{{{key}}}}}", value)
    return text


def scaffold_milestone(project: Path | str, goal: str = "") -> Path:
    """Create the next milestone folder with its report stub.

    Args:
        project: Path of the project folder.
        goal: One-line goal of the milestone.

    Returns:
        The path of the created ``REPORT.md``.

    Raises:
        PermissionError: If no approved contract covers the path.
    """
    root = docs_dir(project)
    number = next_milestone(project)
    folder = root / f"Milestone {number}"
    target = folder / MILESTONE_REPORT
    # La guardia e' UNA, in `ad_scope.guard`: qui c'era `_guard`, e gli altri
    # strumenti che scrivono non la chiamavano (ERR-0026). Prima di creare la
    # cartella, cosi' un rifiuto non lascia tracce.
    ad_scope.guard(target)
    folder.mkdir(parents=True, exist_ok=True)
    target.write_text(
        _fill(
            template(TEMPLATE_MILESTONE),
            {"MILESTONE": str(number), "PROGETTO": Path(project).name, "OBIETTIVO": goal},
        ),
        encoding="utf-8",
    )
    return target


def scaffold_sprint(project: Path | str, milestone: int, objective: str = "") -> Path:
    """Create the next sprint folder with its prompt stub.

    Args:
        project: Path of the project folder.
        milestone: The milestone number.
        objective: One-line objective of the sprint.

    Returns:
        The path of the created ``PROMPT.md``.

    Raises:
        FileNotFoundError: If the milestone does not exist.
        PermissionError: If no approved contract covers the path.
    """
    root = docs_dir(project)
    folder = root / f"Milestone {milestone}"
    if not folder.is_dir():
        raise FileNotFoundError(
            f"milestone inesistente: {folder} — aprila con "
            f'python3 tools/milestone.py new-milestone "{Path(project).name}"'
        )
    number = next_sprint(project, milestone)
    sprint = folder / f"Sprint {number}"
    target = sprint / SPRINT_PROMPT
    ad_scope.guard(target)
    sprint.mkdir(parents=True, exist_ok=True)
    target.write_text(
        _fill(
            template(TEMPLATE_SPRINT_PROMPT),
            {"MILESTONE": str(milestone), "SPRINT": str(number),
             "PROGETTO": Path(project).name,
             "OBIETTIVO": objective},
        ),
        encoding="utf-8",
    )
    return target
