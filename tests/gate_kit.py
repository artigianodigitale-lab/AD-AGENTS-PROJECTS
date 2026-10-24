#!/usr/bin/env python3
"""Il revisore come strumento: congelamento imposto, preflight, brief (ENG-008).

    python3 tests/gate_kit.py preflight <task> [--print]
    python3 tests/gate_kit.py freeze <task>
    python3 tests/gate_kit.py check <task>
    python3 tests/gate_kit.py close <task>
    python3 tests/gate_kit.py scan
    python3 tests/gate_kit.py brief <task> --role qa|review
    python3 tests/gate_kit.py prompt <task> --role qa|review
    python3 tests/gate_kit.py attacks

Perche' esiste. Il revisore indipendente ha trovato quasi tutti i difetti veri del
progetto, ma il suo congelamento era una regola **scritta in un prompt**: violata tre
volte in un giorno (`ERR-0057`). Qui il congelamento e' un atto del codice:

  preflight  batteria deterministica + contract valido; se e' rosso, il gate NON si apre
  freeze     apre il gate SOLO con un preflight verde e fresco; registra le impronte di
             tutto il write_scope (file esistenti, file attesi, contenuto delle directory)
  check      verifica sigillo e impronte: distingue SPARITO, MOSSO, COMPARSO, AGGIUNTO
  close      chiude il gate solo a revisione immobile
  scan       cerca contract chiusi con il gate ancora aperto (la chiusura prematura)

Il lucchetto e' nel codice, non nella disciplina: `tools/ad_contract.py` rifiuta un
contract chiuso con il gate aperto, e `tests/ci.py` lo controlla a ogni verifica.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

# Le librerie della macchina (ad_contract, ...) stanno in tools/: il kit le usa per
# `scan`, che deve vedere la stessa regola del validatore, non riscriverla.
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

import ad_contract  # noqa: E402  (le formule dei sigilli vivono in tools/ad_contract.py)
import yaml  # noqa: E402

#: Un task_id e' un identificatore, non un percorso: niente '/', niente '..'.
TASK_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,60}$")

#: Quanto vale un preflight: oltre, si rifa'. Un preflight vecchio non prova nulla.
PREFLIGHT_TTL_SECONDI = 3600

#: Marcatore del formato nuovo della revisione: con questo, `digest` e `gate` sono
#: obbligatori. Senza, la revisione e' legacy (avviso dichiarato, non blocco).
TOOL_MARKER = "gate_kit"

#: Il registro delle revisioni: cancellare un file non fa ripartire da R1.
LEDGER_REL = "evidenze/.gate-ledger.yaml"

#: Le due evidenze che un gate deve avere per potersi chiudere (DEC-0063, ENG-009).
RUOLI_EVIDENZA = {"QA": "QA", "Code Review": "CodeReview"}

#: Cosa il kit copre e cosa non copre (DEC-0064). I revisori giudicano DENTRO il
#: perimetro: un difetto fuori perimetro non e' un FAIL, e' backlog.
PERIMETRO = {
    "dentro": [
        "aprire un gate senza preflight verde e fresco",
        "chiudere un gate con un revisore ancora in corso o con evidenze mancanti",
        "chiudere con il prodotto mosso dopo il congelamento",
        "bloccare una chiusura onesta (falso positivo del lucchetto)",
        "crash o traceback su input malformato (UTF-8, tipi, campi annidati)",
        "una dichiarazione del README piu' larga del comportamento",
        "dipendenza dei test dallo stato del workspace",
        "un contratto o una revisione di un altro task accettati come se fossero di questo",
    ],
    "fuori": [
        "riscrivere deliberatamente la revisione o il registro con accesso in scrittura",
        "ricalcolare i sigilli (le formule sono pubbliche: nessuna chiave)",
        "cancellare il registro delle revisioni per far ripartire il contatore",
        "qualunque difesa contro chi ha accesso in scrittura alla macchina",
    ],
}

#: Le classi d'attacco: cosa cerca il revisore, e come si prova. Cresce con le
#: lezioni: ogni difetto trovato che non era in questa lista aggiunge una classe.
ATTACCHI: list[dict[str, str]] = [
    {"nome": "percorsi derivati",
     "cerca": "un valore non-path (nome di file, etichetta, campo di un documento) che diventa un percorso",
     "prova": "iniettare '../../tmp/x' in ogni campo che finisce in un percorso, non solo nei parametri che sembrano percorsi"},
    {"nome": "caratteri invisibili",
     "cerca": "byte NUL, Unicode che sembra ASCII, surrogate, percorsi lunghissimi",
     "prova": "passare '\\x00', 'pròva', un percorso da 100.000 caratteri: deve essere un rifiuto con la ragione, non un errore interno"},
    {"nome": "forme malformate",
     "cerca": "un validatore che si rompe (eccezione) invece di rifiutare",
     "prova": "iniettare liste dove serve una mappa, stringhe dove serve un elenco, null, TOML/JSON/YAML invalidi"},
    {"nome": "stati di default",
     "cerca": "assenza e vuoto trattati come uguali, o come 'va bene'",
     "prova": "omettere il campo, passare '', passare [] e {}: i tre casi devono avere esiti distinti e dichiarati"},
    {"nome": "fail-open sul parametro assente",
     "cerca": "un controllo che si applica solo se il chiamante passa un flag o un file",
     "prova": "eseguire la forma piu' povera possibile (nessun flag) e verificare che il controllo ci sia lo stesso"},
    {"nome": "promozione di cio' che non funziona",
     "cerca": "un validatore o un check piu' debole del formato che controlla",
     "prova": "dare al validatore un artefatto rotto (comando sbagliato, tabella commentata, TOML invalido) e pretendere il rifiuto"},
    {"nome": "deriva documentale",
     "cerca": "una dichiarazione (README, registro, contract) piu' larga del comportamento",
     "prova": "per ogni frase 'tollerato', 'escluso', 'provato', cercare il codice o il test che la sostiene"},
    {"nome": "risorse e protocollo",
     "cerca": "input che uccidono il processo o lo lasciano appeso",
     "prova": "JSON annidato 30.000 volte, UTF-8 invalido, stdin chiuso, richiesta senza metodo, messaggi enormi"},
    {"nome": "confine e autorita'",
     "cerca": "scritture o letture fuori dal perimetro dichiarato",
     "prova": "percorsi assoluti, '..', symlink che escono, destinazioni coperte da un altro titolare"},
    {"nome": "identita' e manomissione",
     "cerca": "dati che si possono cambiare senza che l'impronta se ne accorga",
     "prova": "cambiare un campo, risigillare, cambiare solo un campo non hashato, ripristinare un file da una copia"},
    {"nome": "dipendenza dallo stato",
     "cerca": "test che passano solo perche' oggi il workspace e' in un certo modo",
     "prova": "eseguire la suite in una copia con i registri vuoti o chiusi (famiglia ERR-0049)"},
    {"nome": "copertura incompleta",
     "cerca": "un perimetro che dichiara piu' di quanto controlli: file saltati, aggiunte non viste, directory ignorate",
     "prova": "cancellare un file del perimetro, crearne uno nuovo, aggiungerne uno dentro una directory: il check deve vederli"},
]


class GateError(Exception):
    """Raised when the kit cannot honour the request."""


def valida_task(task: str) -> str:
    """Refuse a task id that is not an identifier (no paths, no traversal)."""
    testo = str(task or "").strip()
    if not TASK_RE.fullmatch(testo):
        raise GateError(
            f"task_id non valido: {task!r}. Ammessi lettere, cifre, '_' e '-', senza percorsi"
        )
    return testo


def revision_path(task: str, root: Path = ROOT) -> Path:
    """Return the revision file of a task (after validating the id)."""
    return root / "evidenze" / f"{valida_task(task)}-revisione.yaml"


def preflight_path(task: str, root: Path = ROOT) -> Path:
    """Return the preflight stamp file of a task."""
    return root / "evidenze" / f".preflight-{valida_task(task)}.json"


def contract_path(task: str, root: Path = ROOT) -> Path | None:
    """Return the contract of a task: same task_id, and refuse an ambiguity.

    Cercare per nome file e' una porta: `contratti/aaa/ENG-009.yaml` vinceva su
    `contratti/societa/ENG-009.yaml` e il freeze sigillava il contract sbagliato.
    Qui si cerca per `task_id`, e se due contract lo dichiarano si rifiuta.
    """
    identificatore = valida_task(task)
    candidati: list[Path] = []
    for percorso in sorted((root / "contratti").rglob("*.y*ml")):
        if percorso.name.startswith("_"):
            continue
        try:
            dati = yaml.safe_load(percorso.read_text(encoding="utf-8")) or {}
        except RecursionError as errore:
            raise GateError(
                f"contract troppo annidato: {percorso.relative_to(root)}"
            ) from errore
        except UnicodeDecodeError as errore:
            raise GateError(
                f"contract non e' UTF-8 valido: {percorso.relative_to(root)} ({errore.reason})"
            ) from errore
        except (OSError, yaml.YAMLError):
            continue
        if isinstance(dati, dict) and str(dati.get("task_id") or "").strip() == identificatore:
            candidati.append(percorso)
    if len(candidati) > 1:
        raise GateError(
            "piu' di un contract dichiara il task " + identificatore + ": "
            + ", ".join(str(c.relative_to(root)) for c in candidati)
            + " — un task, un contract"
        )
    return candidati[0] if candidati else None


def _ignora(percorso: Path) -> bool:
    """True per i percorsi che non fanno parte del perimetro (un solo posto)."""
    return "__pycache__" in percorso.parts


def _confina(relativo: str, root: Path) -> Path:
    """Return the path if it stays inside the machine, else refuse.

    Il `write_scope` non e' un suggerimento: un percorso assoluto, un `..` o un
    symlink che risolve fuori dalla radice leggerebbero (e hasherebbero) file che non
    sono della macchina. Rifiuto con la ragione, non silenzio.
    """
    testo = str(relativo).strip()
    if not testo:
        raise GateError("write_scope contiene una voce vuota")
    if "\x00" in testo:
        raise GateError("write_scope: la voce contiene un byte NUL")
    if len(testo) > 255:
        raise GateError(f"write_scope: percorso troppo lungo ({len(testo)} caratteri)")
    if any(ord(carattere) > 127 for carattere in testo):
        raise GateError(f"write_scope: percorso non ASCII: {testo!r}")
    percorso = Path(testo)
    if percorso.is_absolute():
        raise GateError(f"write_scope: percorso assoluto non ammesso: {testo}")
    base = root.resolve()
    try:
        risolto = (root / percorso).resolve()
    except (OSError, ValueError) as errore:
        raise GateError(f"write_scope: percorso non risolvibile {testo!r}: {errore}") from errore
    if risolto != base and base not in risolto.parents:
        raise GateError(f"write_scope: percorso fuori dalla macchina: {testo}")
    return root / percorso


def _leggi_yaml(percorso: Path, cosa: str) -> dict:
    import yaml

    try:
        grezza = percorso.read_text(encoding="utf-8")
    except UnicodeDecodeError as errore:
        raise GateError(f"{cosa} non e' testo UTF-8 valido '{percorso}': {errore.reason}") from errore
    except OSError as errore:
        raise GateError(f"{cosa} illeggibile '{percorso}': {errore}") from errore
    try:
        dati = yaml.safe_load(grezza)
    except RecursionError as errore:
        raise GateError(f"{cosa} troppo annidato (RecursionError): {percorso}") from errore
    except yaml.YAMLError as errore:
        raise GateError(f"{cosa} non e' YAML valido '{percorso}': {errore}") from errore
    if not isinstance(dati, dict):
        raise GateError(f"{cosa} non e' una mappatura: '{percorso}'")
    return dati


def _scrivi_yaml(percorso: Path, dati: dict) -> None:
    import yaml

    percorso.parent.mkdir(parents=True, exist_ok=True)
    temporaneo = percorso.with_name(f".{percorso.name}.tmp")
    temporaneo.write_text(yaml.safe_dump(dati, allow_unicode=True, sort_keys=False), encoding="utf-8")
    temporaneo.replace(percorso)


def _sha(percorso: Path) -> str:
    return hashlib.sha256(percorso.read_bytes()).hexdigest()


def _digest(dati: dict) -> str:
    """Seal of the revision: UNA formula, in tools/ad_contract.py (ENG-010, ERR-0059)."""
    return ad_contract.digest_revisione(dati)


def _closed_digest(dati: dict, _evidenze: dict[str, str] | None = None) -> str:
    """Closure seal: UNA formula, in tools/ad_contract.py (ENG-010, ERR-0059)."""
    return ad_contract.digest_chiusura(dati)


def _stato_gate(dati: dict) -> str:
    """Return the normalised gate state: open, closed, or 'invalid'."""
    valore = dati.get("gate")
    if not isinstance(valore, str):
        return "invalid"
    normalizzato = valore.strip().lower()
    return normalizzato if normalizzato in ("open", "closed") else "invalid"


def file_da_verificare(task: str, root: Path = ROOT) -> tuple[dict[str, str], list[str], dict[str, list[str]]]:
    """Return (files with hashes, expected-but-absent paths, directories with contents)."""
    import yaml

    contratto = contract_path(task, root)
    if contratto is None:
        raise GateError(f"contract di {task} non trovato in contratti/")
    try:
        dati = yaml.safe_load(contratto.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as errore:
        raise GateError(f"contract di {task} illeggibile: {errore}") from errore
    if not isinstance(dati, dict):
        raise GateError(f"contract di {task} non e' una mappatura")

    scope = dati.get("write_scope")
    if not isinstance(scope, list):
        raise GateError(
            f"write_scope di {task} non e' una lista: un elenco di percorsi relativi "
            "e' l'unico formato che il kit sa sorvegliare"
        )
    if not scope:
        raise GateError(f"write_scope di {task} e' vuoto: un gate senza perimetro non ha senso")
    files: dict[str, str] = {str(contratto.relative_to(root)): _sha(contratto)}
    attendibili: list[str] = []
    attesi: list[str] = []
    directories: dict[str, list[str]] = {}
    sottocartelle: dict[str, list[str]] = {}
    for voce in scope:
        if not isinstance(voce, str):
            raise GateError(f"write_scope di {task}: voce non stringa: {voce!r}")
        relativo = voce.strip()
        percorso = _confina(relativo, root)  # una voce vuota e' un rifiuto, non un salto
        if percorso.is_file():
            attendibili.append(relativo)
            files[relativo] = _sha(percorso)
        elif percorso.is_dir():
            dentro = [
                str(figlio.relative_to(root))
                for figlio in sorted(percorso.rglob("*"))
                if figlio.is_file() and not _ignora(figlio)
            ]
            directories[relativo] = dentro
            sottocartelle[relativo] = [
                str(figlio.relative_to(root))
                for figlio in sorted(percorso.rglob("*"))
                if figlio.is_dir() and not _ignora(figlio)
            ]
            for figlio_rel in dentro:
                files[figlio_rel] = _sha(root / figlio_rel)
        else:
            # Un file dichiarato e non ancora esistente NON si salta in silenzio:
            # si registra come «atteso assente». Se compare, e' un movimento.
            attesi.append(relativo)
    return (
        dict(sorted(files.items())),
        sorted(attesi),
        dict(sorted(directories.items())),
        dict(sorted(sottocartelle.items())),
    )


def _sha_contract(task: str, root: Path = ROOT) -> str:
    """Return the hash of the task's contract (the stamp must be bound to it)."""
    contratto = contract_path(task, root)
    if contratto is None:
        raise GateError(f"contract di {task} non trovato in contratti/")
    return _sha(contratto)


def _controlla_preflight(task: str, root: Path = ROOT) -> None:
    """Refuse to open the gate without a fresh, green preflight of THIS contract."""
    percorso = preflight_path(task, root)
    if not percorso.is_file():
        raise GateError(
            f"preflight mancante per {task}: il gate non si apre senza. "
            f"Esegui: python3 tests/gate_kit.py preflight {task}"
        )
    try:
        grezza = percorso.read_text(encoding="utf-8")
    except UnicodeDecodeError as errore:
        raise GateError(f"preflight di {task} non e' UTF-8 valido: {errore.reason}") from errore
    except OSError as errore:
        raise GateError(f"preflight di {task} illeggibile: {errore}") from errore
    try:
        dati = json.loads(grezza)
    except json.JSONDecodeError as errore:
        raise GateError(f"preflight di {task} illeggibile: {errore}") from errore
    if not isinstance(dati, dict):
        raise GateError(f"preflight di {task}: il timbro non e' una mappatura")
    if dati.get("task_id") != task:
        raise GateError(
            f"il timbro di preflight e' di un altro task ({dati.get('task_id')!r}): "
            "un timbro copiato non apre il gate"
        )
    if "verde" in dati and dati.get("verde") is not True:
        raise GateError(f"l'ultimo preflight di {task} era ROSSO: il gate non si apre")
    if "contract_sha" not in dati:
        raise GateError(
            "il timbro di preflight non porta l'impronta del contract: un timbro senza "
            "legame non prova niente (rifallo con 'preflight')"
        )
    atteso = _sha_contract(task, root)
    if dati.get("contract_sha") != atteso:
        raise GateError(
            "il contract e' cambiato dopo il preflight: rifai il preflight "
            "(un timbro legato a un altro contenuto non prova niente)"
        )
    if dati.get("verde") is not True:
        raise GateError(f"preflight di {task} non dichiara di essere verde: rifallo")
    quando = str(dati.get("at") or "")
    try:
        from datetime import datetime as _dt

        momento = _dt.fromisoformat(quando)
    except ValueError:
        raise GateError(f"preflight di {task} senza data valida: rifallo") from None
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    eta = (datetime.now(timezone.utc) - momento).total_seconds()
    if eta < -60:
        raise GateError(f"il timbro di preflight di {task} e' nel futuro ({int(-eta)}s): rifallo")
    if eta > PREFLIGHT_TTL_SECONDI:
        raise GateError(
            f"preflight di {task} vecchio ({int(eta)}s): rifallo prima di congelare"
        )


def _ledger(root: Path = ROOT) -> dict:
    """Read the revision ledger."""
    percorso = root / LEDGER_REL
    if not percorso.is_file():
        return {"tasks": {}}
    try:
        import yaml

        dati = yaml.safe_load(percorso.read_text(encoding="utf-8")) or {}
    except (OSError, Exception) as errore:  # noqa: BLE001
        raise GateError(f"registro delle revisioni illeggibile: {errore}") from errore
    if not isinstance(dati, dict) or not isinstance(dati.get("tasks"), dict):
        raise GateError("registro delle revisioni in formato inatteso")
    return dati


def _salva_ledger(ledger: dict, root: Path = ROOT) -> None:
    import yaml

    percorso = root / LEDGER_REL
    percorso.parent.mkdir(parents=True, exist_ok=True)
    temporaneo = percorso.with_name(f".{percorso.name}.tmp")
    temporaneo.write_text(yaml.safe_dump(ledger, allow_unicode=True, sort_keys=True), encoding="utf-8")
    temporaneo.replace(percorso)


def freeze(task: str, root: Path = ROOT) -> dict:
    """Open the gate: requires a green preflight, records every declared path."""
    identificatore = valida_task(task)
    contratto = contract_path(identificatore, root)
    if contratto is None:
        raise GateError(f"contract di {identificatore} non trovato in contratti/")
    dati_contratto = _leggi_yaml(contratto, "contract")
    if str(dati_contratto.get("status") or "").strip().lower() != "active":
        raise GateError(
            f"il contract di {identificatore} non e' active: non si apre un gate su un contract chiuso"
        )
    _controlla_preflight(identificatore, root)

    ledger = _ledger(root)
    storia = ledger["tasks"].get(identificatore) or []
    if not isinstance(storia, list):
        raise GateError(f"registro delle revisioni: voce di {identificatore} non e' una lista")
    percorso = revision_path(identificatore, root)
    if not percorso.is_file() and storia:
        raise GateError(
            f"la revisione di {identificatore} e' sparita ma il registro dice che esiste "
            f"({len(storia)} revisioni): ripristinala da git. Cancellare il file non fa "
            "ripartire da R1"
        )
    if percorso.is_file():
        precedente = _leggi_yaml(percorso, "revisione")
        stato = _stato_gate(precedente)
        if stato != "closed":
            raise GateError(
                f"gate di {identificatore} gia' aperto (o illeggibile): chiudilo con 'close' dopo il verdetto"
            )
    numero = len(storia)
    prossima = f"R{numero + 1}"

    files, attesi, directories, sottocartelle = file_da_verificare(identificatore, root)
    dati = {
        "tool": TOOL_MARKER,
        "task_id": identificatore,
        "revision": prossima,
        "gate": "open",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "note": "Sigillata da tests/gate_kit.py. Si modifica solo con un nuovo freeze (R successiva).",
        "files": files,
        "expected": attesi,
        "dirs": directories,
        "subdirs": sottocartelle,
    }
    dati["digest"] = _digest(dati)
    _scrivi_yaml(percorso, dati)
    storia.append(
        {"revision": prossima, "frozen_at": dati["frozen_at"], "digest": dati["digest"], "gate": "open"}
    )
    ledger["tasks"][identificatore] = storia
    _salva_ledger(ledger, root)
    return dati


def _leggi_revisione(task: str, root: Path = ROOT) -> dict:
    """Read and type-check a revision; a malformed file is a refusal, not a crash."""
    percorso = revision_path(task, root)
    dati = _leggi_yaml(percorso, "revisione")
    files = dati.get("files")
    if not isinstance(files, dict):
        raise GateError("revisione malformata: 'files' deve essere una mappatura")
    for chiave, valore in files.items():
        if not isinstance(chiave, str) or not isinstance(valore, str):
            raise GateError("revisione malformata: 'files' deve mappare stringhe a impronte")
    expected = dati.get("expected")
    if not isinstance(expected, list) or any(not isinstance(voce, str) for voce in expected):
        raise GateError("revisione malformata: 'expected' deve essere una lista di stringhe")
    dirs = dati.get("dirs")
    if not isinstance(dirs, dict):
        raise GateError("revisione malformata: 'dirs' deve essere una mappatura")
    for chiave, valore in dirs.items():
        if not isinstance(chiave, str) or not isinstance(valore, list) or any(not isinstance(v, str) for v in valore):
            raise GateError("revisione malformata: 'dirs' deve mappare stringhe a liste di stringhe")
    evidenze = dati.get("evidenze", {})
    if evidenze and not isinstance(evidenze, dict):
        raise GateError("revisione malformata: 'evidenze' deve essere una mappatura")
    if isinstance(evidenze, dict) and any(not isinstance(v, str) for v in evidenze.values()):
        raise GateError("revisione malformata: 'evidenze' deve mappare ruoli a impronte")
    subdirs = dati.get("subdirs", {})
    if not isinstance(subdirs, dict):
        raise GateError("revisione malformata: 'subdirs' deve essere una mappatura")
    for chiave, valore in subdirs.items():
        if not isinstance(chiave, str) or not isinstance(valore, list) or any(not isinstance(v, str) for v in valore):
            raise GateError("revisione malformata: 'subdirs' deve mappare stringhe a liste di stringhe")
    revisione = str(dati.get("revision") or "")
    if not re.fullmatch(r"R[0-9]+", revisione):
        raise GateError(f"revisione malformata: 'revision' non valida ({revisione!r})")
    for campo in ("frozen_at", "closed_at"):
        valore = dati.get(campo)
        if isinstance(valore, datetime):
            dati[campo] = valore.isoformat()
        elif valore is not None and not isinstance(valore, str):
            raise GateError(f"revisione malformata: '{campo}' non e' una data")
    return dati


def check(task: str, root: Path = ROOT) -> list[str]:
    """Return the problems of the frozen revision (empty = immobile)."""
    identificatore = valida_task(task)
    percorso = revision_path(identificatore, root)
    if not percorso.is_file():
        return [f"nessuna revisione congelata per {identificatore}: esegui 'freeze' prima del gate"]
    dati = _leggi_revisione(identificatore, root)
    problemi: list[str] = []
    if _stato_gate(dati) == "invalid":
        problemi.append(
            "GATE ASSENTE O NON VALIDO: il campo 'gate' deve essere 'open' o 'closed'"
        )
    if str(dati.get("task_id")) != identificatore:
        problemi.append(
            f"IDENTITA': la revisione e' del task {dati.get('task_id')!r}, non di {identificatore!r}"
        )
    if _stato_gate(dati) == "closed":
        atteso_chiusura = _closed_digest(dati, dati.get("evidenze") or {})
        if dati.get("closed_digest") != atteso_chiusura:
            problemi.append(
                "SIGILLO DI CHIUSURA non combacia: la chiusura e' stata modificata a mano"
            )
        for ruolo, impronta in (dati.get("evidenze") or {}).items():
            percorso_evidenza = evidenze_del_gate(identificatore, root).get(ruolo)
            if percorso_evidenza is None or not percorso_evidenza.is_file():
                problemi.append(f"EVIDENZA SPARITA dopo la chiusura: {ruolo}")
            elif _sha(percorso_evidenza) != impronta:
                problemi.append(f"EVIDENZA MODIFICATA dopo la chiusura: {ruolo}")
        return problemi
    if dati.get("digest") != _digest(dati):
        problemi.append(
            "SIGILLO della revisione non combacia: il file di congelamento e' stato modificato a mano"
        )
    files = dati.get("files")
    if not isinstance(files, dict) or not files:
        return problemi + [f"revisione di {identificatore} senza impronte"]
    for relativo, atteso in files.items():
        percorso_file = root / relativo
        if not percorso_file.is_file():
            problemi.append(f"SPARITO {relativo}")
            continue
        if _sha(percorso_file) != atteso:
            problemi.append(f"MOSSO {relativo}")
    for relativo in dati.get("expected") or []:
        if (root / relativo).exists():
            problemi.append(f"COMPARSO {relativo} (atteso assente al congelamento)")
    for relativo, elenco in (dati.get("dirs") or {}).items():
        cartella = root / relativo
        if not cartella.is_dir():
            problemi.append(f"SPARITA la directory {relativo}")
            continue
        attuale = {
            str(figlio.relative_to(root))
            for figlio in cartella.rglob("*")
            if figlio.is_file() and not _ignora(figlio)
        }
        for nuovo in sorted(attuale - set(elenco)):
            problemi.append(f"AGGIUNTO nella directory {relativo}: {nuovo}")
        for sparito in sorted(set(elenco) - attuale):
            problemi.append(f"SPARITO dalla directory {relativo}: {sparito}")
    for relativo, elenco in (dati.get("subdirs") or {}).items():
        cartella = root / relativo
        if not cartella.is_dir():
            problemi.append(f"SPARITA la directory {relativo}")
            continue
        attuale_dir = {
            str(figlio.relative_to(root))
            for figlio in cartella.rglob("*")
            if figlio.is_dir() and not _ignora(figlio)
        }
        for nuova in sorted(attuale_dir - set(elenco)):
            problemi.append(f"AGGIUNTA la directory {relativo}: {nuova}")
        for sparita in sorted(set(elenco) - attuale_dir):
            problemi.append(f"SPARITA la directory {relativo}: {sparita}")
    return problemi


def evidenze_del_gate(task: str, root: Path = ROOT) -> dict[str, Path]:
    """Return the two evidence files a gate must have to be closed."""
    return {
        ruolo: root / "evidenze" / f"{task}-{suffisso}.yaml"
        for ruolo, suffisso in RUOLI_EVIDENZA.items()
    }


def _evidenze_mancanti(task: str, frozen_at: str, root: Path = ROOT) -> list[str]:
    """Return the evidence files missing or written before the freeze.

    DEC-0063 / ENG-009: il gate non si chiude "perche' il verdetto e' ovvio". Si
    chiude quando ENTRAMBI i revisori hanno finito, e le loro evidenze sono posteriori
    al congelamento. E' la correzione meccanica della quarta ricorrenza di ERR-0057.
    """
    from datetime import datetime as _dt

    try:
        congelata = _dt.fromisoformat(frozen_at)
    except ValueError:
        raise GateError(f"revisione con frozen_at non valido: {frozen_at!r}") from None
    if congelata.tzinfo is None:
        congelata = congelata.replace(tzinfo=timezone.utc)
    mancanti: list[str] = []
    for ruolo, percorso in evidenze_del_gate(task, root).items():
        if not percorso.is_file():
            mancanti.append(f"{percorso.name} (assente: il revisore {ruolo} non ha ancora scritto)")
            continue
        problemi_contenuto = _evidenza_problemi(percorso, task, ruolo)
        if problemi_contenuto:
            mancanti.append(f"{percorso.name} ({problemi_contenuto})")
            continue
        scritta = datetime.fromtimestamp(percorso.stat().st_mtime, tz=timezone.utc)
        if scritta <= congelata:
            mancanti.append(
                f"{percorso.name} (non e' successiva al congelamento: e' di un gate precedente)"
            )
    return mancanti


#: Come si riconosce il ruolo dentro un'evidenza (campo `gate` o `producer`).
RUOLI_ATTESI: dict[str, tuple[set[str], set[str]]] = {
    "QA": ({"qa"}, {"qa"}),
    "Code Review": ({"code review", "codereview", "review"}, {"review", "codereview", "code review"}),
}


def _evidenza_problemi(percorso: Path, task: str, ruolo: str = "") -> str:
    """Return why an evidence file cannot certify a gate (empty string if it can)."""
    try:
        grezza = percorso.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as errore:
        return f"illeggibile: {errore.__class__.__name__}"
    if not grezza.strip():
        return "vuota"
    import yaml

    try:
        dati = yaml.safe_load(grezza)
    except yaml.YAMLError:
        return "non e' YAML valido"
    if not isinstance(dati, dict):
        return "non e' una mappatura"
    if str(dati.get("task_id")) != task:
        return f"di un altro task ({dati.get('task_id')!r})"
    if str(dati.get("outcome") or "").upper() not in ("PASS", "FAIL"):
        return "senza esito (outcome assente o non valido)"
    if str(dati.get("schema")) != "2":
        return "schema diverso da 2"
    for campo in ("coverage", "side_effects"):
        if not isinstance(dati.get(campo), dict):
            return f"schema 2: campo '{campo}' assente o non mappa"
    for campo in ("confidence", "authority"):
        if campo not in dati:
            return f"schema 2: campo '{campo}' assente"
    if not isinstance(dati.get("limitations"), list):
        return "schema 2: 'limitations' assente o non lista"
    if ruolo:
        gate_attesi, produttori_attesi = RUOLI_ATTESI[ruolo]
        gate_scritto = str(dati.get("gate") or "").strip().lower()
        produttore = str(dati.get("producer") or "").strip().lower()
        if gate_scritto not in gate_attesi and produttore not in produttori_attesi:
            return f"non e' del ruolo {ruolo} (gate={dati.get('gate')!r}, producer={dati.get('producer')!r})"
    return ""


def close(task: str, root: Path = ROOT) -> dict:
    """Close the gate: only with both evidences and an immobile revision."""
    identificatore = valida_task(task)
    problemi = check(identificatore, root)
    if problemi:
        raise GateError("revisione mossa: il gate non si chiude. " + "; ".join(problemi))
    percorso = revision_path(identificatore, root)
    dati = _leggi_revisione(identificatore, root)
    stato_gate = _stato_gate(dati)
    if stato_gate == "closed":
        return dati
    if stato_gate != "open":
        raise GateError(
            "il campo 'gate' della revisione e' assente o non valido: un gate senza stato "
            "non si chiude (rifai il freeze)"
        )
    mancanti = _evidenze_mancanti(identificatore, str(dati.get("frozen_at") or ""), root)
    if mancanti:
        raise GateError(
            "il gate non si chiude senza entrambe le evidenze del gate in corso: "
            + "; ".join(mancanti)
        )
    # Il registro si legge e si verifica PRIMA di toccare la revisione: un rifiuto
    # non deve lasciare il gate gia' chiuso (un retry lo ratificherebbe).
    ledger = _ledger(root)
    storia = ledger["tasks"].get(identificatore) or []
    if not isinstance(storia, list) or not storia:
        raise GateError(
            "registro delle revisioni incoerente: il freeze non ha registrato "
            f"{identificatore}. Il gate non si chiude con un registro che non sa della revisione"
        )
    ultima = storia[-1] if isinstance(storia[-1], dict) else {}
    if str(ultima.get("revision") or "") != str(dati.get("revision") or ""):
        raise GateError(
            f"registro delle revisioni fermo a {ultima.get('revision')!r}: la revisione in "
            f"corso e' {dati.get('revision')!r}. Il gate non si chiude su una revisione "
            "scollegata dal registro (rifai il freeze)"
        )
    evidenze = {
        ruolo: _sha(percorso_ev)
        for ruolo, percorso_ev in evidenze_del_gate(identificatore, root).items()
    }
    dati["gate"] = "closed"
    dati["closed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    dati["evidenze"] = evidenze
    dati["closed_digest"] = _closed_digest(dati, evidenze)
    storia[-1]["gate"] = "closed"
    storia[-1]["closed_at"] = dati["closed_at"]
    ledger["tasks"][identificatore] = storia
    _salva_ledger(ledger, root)
    _scrivi_yaml(percorso, dati)
    return dati


def scan(root: Path = ROOT) -> list[str]:
    """Return the contracts closed while their gate is still open (premature closure)."""
    import ad_contract

    problemi: list[str] = []
    for percorso in sorted((root / "contratti").rglob("*.y*ml")):
        if percorso.name.startswith("_"):
            continue
        try:
            dati = _leggi_yaml(percorso, "contract")
        except GateError as errore:
            print(f"ATTENZIONE  {percorso.name}: {errore}", file=sys.stderr)
            continue
        codice, messaggio = ad_contract.gate_status(dati, root)
        if codice == "block":
            problemi.append(messaggio)
    return problemi


def _registri(root: Path = ROOT) -> dict[str, object]:
    """Read the registers the brief needs: open drift, recent lessons, open unknowns."""
    import yaml

    info: dict[str, object] = {"drift_aperti": 0, "drift_totali": 0, "errori": [], "incognite": [], "problemi": []}
    drift = root / "drift" / "README.md"
    if drift.is_file():
        try:
            testo = drift.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            testo = ""
        voci = [riga for riga in testo.splitlines() if riga.startswith("## DRIFT-")]
        aperti = sum(1 for riga in testo.splitlines() if riga.strip() == "| **Stato** | OPEN |")
        info["drift_totali"] = len(voci)
        info["drift_aperti"] = aperti
    errori_tutti = sorted((root / "errori").glob("ERR-*.yaml"))
    for percorso in errori_tutti:
        try:
            dati = yaml.safe_load(percorso.read_text(encoding="utf-8")) or {}
        except (OSError, UnicodeDecodeError, yaml.YAMLError, RecursionError):
            info["problemi"].append(f"{percorso.name} illeggibile: la cicatrice non e' nel brief")
            continue
        if not isinstance(dati, dict):
            info["problemi"].append(f"{percorso.name} non e' una mappatura")
            continue
        info["errori"].append(f"{dati.get('id')}: diventa {dati.get('diventa')}")
    info["errori"] = info["errori"][-5:]

    incognite = root / "evidenze" / "incognite.yaml"
    if incognite.is_file():
        try:
            dati = yaml.safe_load(incognite.read_text(encoding="utf-8")) or {}
        except UnicodeDecodeError:
            info["problemi"].append("incognite.yaml non e' UTF-8")
            dati = {}
        except RecursionError:
            info["problemi"].append("incognite.yaml troppo annidato")
            dati = {}
        except (OSError, yaml.YAMLError):
            info["problemi"].append("incognite.yaml illeggibile")
            dati = {}
        if not isinstance(dati, dict):
            info["problemi"].append("incognite.yaml non e' una mappatura")
            dati = {}
        voci = dati.get("unknowns")
        if voci is not None and not isinstance(voci, list):
            info["problemi"].append("incognite.yaml: 'unknowns' non e' una lista")
            voci = []
        for voce in voci or []:
            if isinstance(voce, dict) and str(voce.get("status")) == "open":
                info["incognite"].append(str(voce.get("unknown_id")))
    if (root / "drift" / "README.md").is_file() and not info["drift_totali"]:
        try:
            testo_drift = (root / "drift" / "README.md").read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            info["problemi"].append("drift/README.md illeggibile: le divergenze non sono nel brief")
        else:
            _ = testo_drift  # leggibile: nessun allarme (anche se non ha voci)
    return info


def brief(task: str, role: str, root: Path = ROOT) -> str:
    """Generate the reviewer's brief from the registers."""
    import yaml

    identificatore = valida_task(task)
    if role not in ("qa", "review"):
        raise GateError("role ammesso: qa (obbligatorio esplicito) oppure review")
    contratto = contract_path(identificatore, root)
    if contratto is None:
        raise GateError(f"contract di {identificatore} non trovato")
    dati = _leggi_yaml(contratto, "contract")
    criteri = dati.get("acceptance_criteria") or []
    if isinstance(criteri, str) or not isinstance(criteri, list) or any(
        not isinstance(voce, str) for voce in criteri
    ):
        raise GateError(
            f"acceptance_criteria di {identificatore} deve essere una lista di stringhe "
            f"(trovato: {type(criteri).__name__}); un contract cosi' non apre il gate"
        )
    registro = _registri(root)
    righe = [
        f"# Brief del revisore — {identificatore} · ruolo {role}",
        "",
        "Sei un REVISORE INDIPENDENTE: non hai scritto il codice e non lo modificherai.",
        "",
    ]
    if role == "qa":
        righe += [
            "**Il tuo metodo: scatola nera.** Non leggere il codice (o leggilo il meno possibile).",
            "Esegui, prova, misura: quello che conta e' cio' che il programma fa, non cio' che dice.",
        ]
    else:
        righe += [
            "**Il tuo metodo: leggi il codice.** Cerca il difetto che i test non vedono:",
            "le regole scritte e non applicate, i rami mai eseguiti, i default, i confini.",
        ]
    righe += [
        "",
        "Non fidarti delle affermazioni del contract ne' dei suoi test: riprova.",
        "Dichiara sempre cosa NON hai potuto verificare.",
        "Non chiudere il gate: lo chiude il Lead dopo il verdetto.",
        "",
        "## Contract",
        f"- file: {contratto.relative_to(root)}",
        f"- obiettivo: {str(dati.get('objective') or '').strip()[:300]}",
        "",
        "## Perimetro: cosa giudicare (DEC-0064)",
        "Il kit difende dalla DIMENTICANZA e dagli incidenti, non dal dolo.",
        "**Dentro il perimetro** (un difetto qui e' un FAIL):",
    ] + [f"- {voce}" for voce in PERIMETRO["dentro"]] + [
        "**Fuori perimetro** (un difetto qui e' una NOTA da backlog, non un FAIL):",
    ] + [f"- {voce}" for voce in PERIMETRO["fuori"]] + [
        "",
        "## Criteri di accettazione (uno per uno)",
    ]
    for indice, criterio in enumerate(criteri, start=1):
        righe.append(f"{indice}. {criterio}")
    # Le evidenze dell'ALTRO ruolo dello stesso gate non si mostrano: i due revisori
    # non devono vedersi (difetto D8 del primo gate).
    altro = "CodeReview" if role == "qa" else "QA"
    proprie = sorted((root / "evidenze").glob(f"{identificatore}-*.yaml"))
    precedenti = [
        percorso
        for percorso in proprie
        if "revisione" not in percorso.name
        and not percorso.name.endswith(f"-{altro}.yaml")
    ]
    righe += ["", "## Evidenze precedenti di questo task (non quelle dell'altro revisore)"]
    if precedenti:
        for percorso in precedenti:
            dati_ev = _leggi_yaml(percorso, "evidenza")
            righe.append(f"- {percorso.name}: {dati_ev.get('outcome')} (produttore {dati_ev.get('producer')})")
    else:
        righe.append("- nessuna: e' il primo gate di questo task")
    righe += [
        "",
        "## Registri",
        f"- divergenze aperte: {registro['drift_aperti']} su {registro['drift_totali']}",
        f"- ultime cicatrici (id: cosa e' diventato): {'; '.join(registro['errori']) or 'nessuna'}",
        f"- incognite aperte: {', '.join(registro['incognite']) or 'nessuna'}",
    ] + ([f"- AVVISO registri: {'; '.join(registro['problemi'])}"] if registro.get("problemi") else []) + [
        "",
        "## Catalogo delle classi d'attacco",
    ]
    for attacco in ATTACCHI:
        righe += [f"### {attacco['nome']}", f"- cerca: {attacco['cerca']}", f"- prova: {attacco['prova']}", ""]
    percorso_revisione = revision_path(identificatore, root)
    if percorso_revisione.is_file():
        dati_rev = _leggi_revisione(identificatore, root)
        if str(dati_rev.get("task_id")) != identificatore:
            righe += [
                "## Revisione congelata",
                f"- ATTENZIONE: la revisione e' del task {dati_rev.get('task_id')!r}, non di "
                f"{identificatore!r}: STOP, non e' il gate di questo task",
            ]
            return "\n".join(righe) + "\n"
        righe += ["## Revisione congelata", f"- revisione {dati_rev.get('revision')} del {dati_rev.get('frozen_at')}", "- impronte:"]
        for relativo, impronta in (dati_rev.get("files") or {}).items():
            righe.append(f"  - {relativo}: {impronta}")
        for relativo in dati_rev.get("expected") or []:
            righe.append(f"  - {relativo}: ATTESO ASSENTE (se compare, e' un movimento)")
        for relativo, elenco in (dati_rev.get("dirs") or {}).items():
            righe.append(f"  - directory {relativo}: {len(elenco)} file sorvegliati")
        for relativo, elenco in (dati_rev.get("subdirs") or {}).items():
            righe.append(f"  - directory {relativo}: {len(elenco)} sottodirectory sorvegliate")
        righe += [
            "",
            "Verifica le impronte all'inizio, a meta' e alla fine. Se una cambia: STOP e FAIL.",
            "Il contract deve restare `status: active` per tutta la durata.",
        ]
    else:
        righe += ["", "## Revisione congelata", "- NON ancora congelata: l'autore deve eseguire `freeze`."]
    righe += [
        "",
        "## Comandi",
        f"python3 tests/gate_kit.py check {identificatore}",
        f"python3 tests/gate_kit.py close {identificatore}   # solo dopo il verdetto, lo fa il Lead",
    ]
    return "\n".join(righe) + "\n"


def prompt_revisore(task: str, role: str, root: Path = ROOT) -> str:
    """Generate the reviewer's PROMPT from the code, without any absolute path.

    La cartella si decide al lancio (workspace) e gli strumenti trovano la radice da
    soli: un percorso nella prompt e' inutile, fragile e contro la costituzione
    (ERR-0064). Se la prompt la scrive il codice, non c'e' spazio per un percorso
    scritto a mano.
    """
    identificatore = valida_task(task)
    if role not in ("qa", "review"):
        raise GateError("role ammesso: qa oppure review")
    if contract_path(identificatore, root) is None:
        raise GateError(f"contract di {identificatore} non trovato: nessuna prompt da generare")
    suffisso = "QA" if role == "qa" else "CodeReview"
    if role == "qa":
        metodo = (
            "**Il tuo metodo: scatola nera.** Non leggere il codice: esegui, prova, misura. "
            "Quello che conta e' cio' che il programma fa, non cio' che dice."
        )
    else:
        metodo = (
            "**Il tuo metodo: leggi il codice.** Cerca il difetto che i test non vedono: "
            "regole scritte e non applicate, rami mai eseguiti, default, confini."
        )
    righe = [
        f"# Prompt del revisore — {identificatore} · ruolo {role}",
        "",
        "Sei un REVISORE INDIPENDENTE: non hai scritto il codice che giudichi e non lo",
        "modificherai. Lavori in parallelo con l'altro revisore (stesso gate, ruolo diverso),",
        "che non vedi.",
        "",
        metodo,
        "",
        "Sei dentro la macchina: non ti serve sapere dove sta. Sei stato lanciato nella",
        "cartella giusta, e gli strumenti trovano la radice da soli. Non chiedere e non",
        "scrivere percorsi.",
        "",
        "## Perimetro: cosa giudicare (DEC-0064)",
        "Il kit difende dalla DIMENTICANZA e dagli incidenti, non dal dolo.",
        "**Dentro il perimetro** (un difetto qui e' un FAIL):",
    ] + [f"- {voce}" for voce in PERIMETRO["dentro"]] + [
        "**Fuori perimetro** (un difetto qui e' una NOTA da backlog, non un FAIL):",
    ] + [f"- {voce}" for voce in PERIMETRO["fuori"]] + [
        "",
        "## Cosa fare",
        f"1. Leggi il brief: `python3 tests/gate_kit.py brief {identificatore} --role {role}`",
        "   Seguilo: contiene criteri, perimetro, catalogo delle classi d'attacco, impronte.",
        "2. Non modificare nulla nella macchina: le prove distruttive solo in una copia",
        "   scratch fuori dalla macchina, dichiarata nei limiti.",
        "3. Non chiudere il gate: lo chiude il Lead dopo il verdetto.",
        f"4. Scrivi l'evidenza in `evidenze/{identificatore}-{suffisso}.yaml` (schema 2).",
        "5. Esegui il verdetto: `python3 tools/verdict.py --contract <contract> --evidence ...`",
        "   (il file del contract e' nel brief).",
        "",
        "Dichiara sempre cosa NON hai potuto verificare. Sii severo: un revisore che",
        "promuove tutto non serve.",
    ]
    return "\n".join(righe) + "\n"


def _piano_preflight(contratto: Path, root: Path) -> list[tuple[str, list[str]]]:
    return [
        ("contract valido", [PY, str(root / "tools" / "validate_contract.py"), str(contratto)]),
        ("batteria deterministica", [PY, str(root / "tests" / "ci.py"), "--full"]),
        ("albero (informativo)", [PY, str(root / "tools" / "verdict.py"), "--tree", "check"]),
    ]


def _esegui_comando(comando: list[str], root: Path) -> tuple[int, str]:
    """Run one preflight command (private: nessun punto di iniezione pubblico)."""
    esito = subprocess.run(comando, cwd=str(root), capture_output=True, text=True)
    return esito.returncode, (esito.stdout + esito.stderr).strip()


def preflight(
    task: str,
    print_only: bool = False,
    root: Path = ROOT,
) -> int:
    """Check that the gate can be opened; on success write the stamp freeze requires."""
    identificatore = valida_task(task)
    contratto = contract_path(identificatore, root)
    if contratto is None:
        print(f"ERRORE  contract di {identificatore} non trovato", file=sys.stderr)
        return 2
    piano = _piano_preflight(contratto, root)
    if print_only:
        for nome, comando in piano:
            print(f"{nome}: {' '.join(comando)}")
        return 0
    esiti = [(nome, *_esegui_comando(comando, root)) for nome, comando in piano]
    # Il codice di uscita e' l'indice 1 della tupla: confrontare l'output (indice 2)
    # rendeva bloccante ogni controllo (bug trovato provando il preflight).
    bloccanti = [voce for voce in esiti if voce[1] != 0 and "informativo" not in voce[0]]
    for nome, codice, output in esiti:
        if codice != 0 and "informativo" not in nome:
            print(f"{nome:26} ROSSO")
            print("\n".join(output.splitlines()[-6:]))
        else:
            print(f"{nome:26} {'OK' if codice == 0 else 'INFORMATIVO'}")
    if bloccanti:
        stamp = preflight_path(identificatore, root)
        stamp.write_text(
            json.dumps({"task_id": identificatore, "verde": False,
                        "at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
                       indent=2),
            encoding="utf-8",
        )
        print(f"\npreflight: NO-GO ({len(bloccanti)} controlli rossi) — il gate non si apre")
        return 1
    stamp = preflight_path(identificatore, root)
    stamp.write_text(
        json.dumps(
            {
                "task_id": identificatore,
                "contract_sha": _sha_contract(identificatore, root),
                "verde": True,
                "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print("\npreflight: GO — il gate puo' aprirsi (freeze)")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Il revisore come strumento (ENG-008)")
    sotto = parser.add_subparsers(dest="azione", required=True)
    for nome in ("preflight", "freeze", "check", "close", "brief", "prompt"):
        comando = sotto.add_parser(nome)
        comando.add_argument("task")
        if nome == "preflight":
            comando.add_argument("--print", action="store_true", dest="stampa")
        if nome in ("brief", "prompt"):
            comando.add_argument("--role", required=True, choices=("qa", "review"))
    sotto.add_parser("scan")
    sotto.add_parser("attacks")
    args = parser.parse_args(argv)
    try:
        if args.azione == "attacks":
            for attacco in ATTACCHI:
                print(f"- {attacco['nome']}: {attacco['cerca']}\n  prova: {attacco['prova']}")
            return 0
        if args.azione == "preflight":
            return preflight(args.task, print_only=getattr(args, "stampa", False))
        if args.azione == "freeze":
            dati = freeze(args.task)
            print(f"gate APERTO · {args.task} · {dati['revision']} · {len(dati['files'])} file, {len(dati['expected'])} attesi, {len(dati['dirs'])} directory")
            return 0
        if args.azione == "check":
            problemi = check(args.task)
            for problema in problemi:
                print(f"CONTAMINAZIONE  {problema}", file=sys.stderr)
            if problemi:
                print(f"revisione MOSSA: {len(problemi)} problemi")
                return 1
            print(f"OK   revisione immobile ({args.task})")
            return 0
        if args.azione == "close":
            dati = close(args.task)
            print(f"gate CHIUSO · {args.task} · {dati.get('revision')}")
            return 0
        if args.azione == "scan":
            problemi = scan()
            for problema in problemi:
                print(f"CHIUSURA PREMATURA  {problema}", file=sys.stderr)
            if problemi:
                print(f"gate aperti su contract chiusi: {len(problemi)}")
                return 1
            print("OK   nessun contract chiuso con il gate aperto")
            return 0
        if args.azione == "brief":
            sys.stdout.write(brief(args.task, args.role))
            return 0
        if args.azione == "prompt":
            sys.stdout.write(prompt_revisore(args.task, args.role))
            return 0
        print("ERRORE  azione sconosciuta", file=sys.stderr)
        return 2
    except GateError as errore:
        print(f"ERRORE  {errore}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
