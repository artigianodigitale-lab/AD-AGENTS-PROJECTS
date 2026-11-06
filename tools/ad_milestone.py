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
#: Il biglietto di consegna: cosa deve sapere la chat che apre lo sprint dopo
#: (DEC-0089). Sta accanto a PROMPT.md e REPORT.md, e lo genera il motore.
SPRINT_CONSEGNA = "CONSEGNA.md"

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
    def has_consegna(self) -> bool:
        """Il biglietto di consegna esiste?"""
        return (self.path / SPRINT_CONSEGNA).is_file()

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


# --------------------------------------------------------------------------- #
# La consegna fra sprint (DEC-0089)                                            #
# --------------------------------------------------------------------------- #

#: Quanto puo' essere lungo il biglietto. Non e' un limite tecnico: e' la ragione
#: per cui esiste. Se sfonda, il taglio non serve piu'.
LIMITE_CONSEGNA = 6000


def _sezione(testo: str, titolo: str) -> str:
    """Il testo di una sezione ``## titolo`` di un Markdown, senza il titolo."""
    righe: list[str] = []
    dentro = False
    for riga in testo.splitlines():
        if riga.strip().lower().startswith("## "):
            if dentro:
                break
            dentro = riga.strip().lower() == f"## {titolo.strip().lower()}"
            continue
        if dentro:
            righe.append(riga)
    return "\n".join(righe).strip()


def _meta_prompt(testo: str) -> dict[str, str]:
    """I campi del blocco YAML in testa a un ``PROMPT.md``."""
    import yaml

    trovato = False
    righe: list[str] = []
    for riga in testo.splitlines():
        if riga.strip() == "```yaml":
            trovato = True
            continue
        if trovato:
            if riga.strip() == "```":
                break
            righe.append(riga)
    if not trovato:
        return {}
    try:
        dati = yaml.safe_load("\n".join(righe))
    except yaml.YAMLError:
        return {}
    if not isinstance(dati, dict):
        return {}
    return {str(chiave): str(valore) for chiave, valore in dati.items() if valore is not None}


def _primi_caratteri(testo: str, limite: int) -> str:
    """Un estratto che non taglia a meta' parola."""
    testo = " ".join(testo.split())
    if len(testo) <= limite:
        return testo
    tagliato = testo[:limite].rsplit(" ", 1)[0]
    return tagliato + "…"


def genera_consegna(project: Path | str, milestone: int, sprint: int) -> str:
    """Il testo del biglietto: cosa deve sapere la chat che apre lo sprint dopo.

    Si costruisce **solo** dai file che esistono: il ``PROMPT.md`` e il
    ``REPORT.md`` dello sprint che si chiude, il ``REPORT.md`` della milestone e il
    ``BLUEPRINT.md`` del progetto. Nessun riassunto inventato: se un pezzo manca, il
    biglietto lo dice invece di riempirlo.
    """
    root = docs_dir(project)
    cartella = root / f"Milestone {milestone}" / f"Sprint {sprint}"
    nome_progetto = Path(project).name
    righe: list[str] = [
        f"# Consegna — {nome_progetto} · Tappa {milestone} · Passo {sprint}",
        "",
        "> Generato dal motore (`python3 tools/milestone.py consegna`) dai registri del",
        "> progetto. Non si scrive a mano: si rigenera. Contiene tutto quello che serve",
        "> per riprendere il lavoro in una chat nuova, senza rileggere la precedente.",
        "",
    ]

    prompt_path = cartella / SPRINT_PROMPT
    report_path = cartella / SPRINT_REPORT
    if not report_path.is_file():
        righe += [
            "## Stato",
            "",
            f"**Questo passo NON e' chiuso**: manca `{SPRINT_REPORT}` in questa cartella.",
            "Non si consegna un lavoro che non ha il suo rapporto: senza rapporto non",
            "c'e' la prova che sia stato fatto. Scrivilo, poi rilancia la consegna.",
            "",
        ]
        return "\n".join(righe)

    meta = _meta_prompt(prompt_path.read_text(encoding="utf-8")) if prompt_path.is_file() else {}
    obiettivo = meta.get("obiettivo", "")
    rapporto = report_path.read_text(encoding="utf-8")

    righe += ["## Cosa e' stato fatto", ""]
    for titolo in ("Cosa e' stato fatto", "Cosa e' stato prodotto", "Risultato"):
        pezzo = _sezione(rapporto, titolo)
        if pezzo:
            righe += [_primi_caratteri(pezzo, 1200), ""]
            break
    else:
        righe += ["_Il rapporto non ha una sezione «Cosa e' stato fatto»: leggilo per intero._", ""]

    if obiettivo:
        righe += ["## L'obiettivo del passo chiuso", "", obiettivo, ""]

    resti = ""
    for titolo in ("Cosa non e' stato fatto", "Cosa resta", "Aperto"):
        resti = _sezione(rapporto, titolo)
        if resti:
            break
    if resti:
        righe += ["## Cosa resta aperto", "", _primi_caratteri(resti, 1000), ""]

    # Il prossimo passo, se esiste gia' aperto.
    prossimo = cartella.parent / f"Sprint {sprint + 1}" / SPRINT_PROMPT
    if prossimo.is_file():
        meta_prossimo = _meta_prompt(prossimo.read_text(encoding="utf-8"))
        righe += [
            "## Il prossimo passo",
            "",
            f"**Tappa {milestone} · Passo {sprint + 1}** — `{prossimo.relative_to(root).as_posix()}`",
        ]
        if meta_prossimo.get("obiettivo"):
            righe += ["", f"Obiettivo: {meta_prossimo['obiettivo']}"]
        righe += [""]
    else:
        righe += [
            "## Il prossimo passo",
            "",
            "Non ancora aperto. Aprilo prima di cominciare:",
            "",
            "```sh",
            f'python3 tools/milestone.py new-sprint "{nome_progetto}" {milestone} --objective "…"',
            "```",
            "",
        ]

    blueprint = root / "BLUEPRINT.md"
    if blueprint.is_file():
        testo = blueprint.read_text(encoding="utf-8")
        stato = _sezione(testo, "A che punto e'")
        if stato:
            righe += ["## A che punto e' il progetto", "", _primi_caratteri(stato, 500), ""]

    righe += [
        "## Da leggere in questa chat nuova",
        "",
        f"1. questo biglietto ({SPRINT_CONSEGNA});",
        f"2. `{prompt_path.relative_to(root).as_posix()}` — il foglio del passo;",
        f"3. `{report_path.relative_to(root).as_posix()}` — cosa e' stato chiuso.",
        "",
        "Il resto (tappe vecchie, rapporti precedenti) **non serve leggerlo**: se serve",
        "un dettaglio, si apre il file preciso invece di rileggere tutta la storia.",
        "",
        "## Cosa fare in questa chat",
        "",
        "1. Leggi i tre file qui sopra, non altri.",
        "2. Verifica lo stato reale prima di toccare qualcosa (`python3 tests/ci.py` per",
        "   la macchina, il comando di prova del progetto per il prodotto).",
        "3. Apri un contract per il passo nuovo: senza permesso non si scrive.",
        "",
        "---",
        "",
        "_Perche' questa chat e' nuova: una conversazione lunga rallenta e peggiora il",
        "lavoro, perche' il modello rilegge tutto a ogni giro. Il taglio e' al confine",
        "del passo, dove il lavoro e' verificato e documentato (DEC-0089)._",
        "",
    ]
    testo = "\n".join(righe)
    if len(testo) > LIMITE_CONSEGNA:
        testo = testo[:LIMITE_CONSEGNA] + "\n\n_(Biglietto troncato: il limite e' una scelta.)_\n"
    return testo


def scrivi_consegna(project: Path | str, milestone: int, sprint: int) -> Path:
    """Scrive il biglietto accanto al ``PROMPT.md`` dello sprint. Restituisce il percorso.

    Raises:
        FileNotFoundError: Se lo sprint non esiste.
        PermissionError: Se nessun contract approvato copre il percorso.
    """
    cartella = docs_dir(project) / f"Milestone {milestone}" / f"Sprint {sprint}"
    if not cartella.is_dir():
        raise FileNotFoundError(
            f"sprint inesistente: {cartella} — aprilo con "
            f'python3 tools/milestone.py new-sprint "{Path(project).name}" {milestone}'
        )
    destinazione = cartella / SPRINT_CONSEGNA
    ad_scope.guard(destinazione)
    destinazione.write_text(genera_consegna(project, milestone, sprint), encoding="utf-8")
    return destinazione
