#!/usr/bin/env python3
"""Server MCP di AD Projects — il cancello che viaggia (DEC-0057, ENG-002).

    python3 tools/ad_mcp/server.py

Parla MCP su stdio: un messaggio JSON-RPC 2.0 per riga. Nessuna dipendenza oltre
la standard library (piu' PyYAML, che AD usa gia'): un server che richiede un
pacchetto non e' portabile, e la portabilita' e' tutto il motivo per cui esiste.

Perche' esiste. La regola di AD viveva nei comandi Python: un agente la usava solo
se sapeva quale comando lanciare, e ogni client la raggiungeva in modo diverso — o
non la raggiungeva. Qui la regola ha un **confine**: un server locale che ogni
client che parla MCP puo' interrogare allo stesso modo. Il server non riscrive le
regole: chiama le librerie di `tools/`, che restano l'autorita' (come il plugin DSH
interroga `contract_scope.py` invece di duplicarlo).

Sicurezza. Il server non legge e non scrive fuori dalla macchina: ogni percorso che
arriva da fuori viene risolto e, se esce dalla root, **rifiutato** con la ragione.
Non e' una sandbox: e' un confine di autorita', e un confine che non si applica non
e' un confine.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import yaml  # noqa: E402

import ad_contract  # noqa: E402
import ad_evidence  # noqa: E402
import ad_registry  # noqa: E402
import ad_scope  # noqa: E402

SERVER_NAME = "ad-projects"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2025-06-18"


class RpcError(Exception):
    """A protocol error with a remediation: an error without one is a dead end."""

    def __init__(self, code: int, message: str, remediation: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.remediation = remediation

    def data(self) -> dict[str, Any]:
        """Return the JSON-RPC error data."""
        return {"remediation": self.remediation} if self.remediation else {}


def _resolve(
    value: str,
    *,
    must_exist: bool = False,
    must_be_file: bool = False,
    must_be_dir: bool = False,
) -> Path:
    """Resolve a caller path inside the machine, or refuse it.

    `must_be_file`/`must_be_dir` esistono per L1/N5/N6 del 2o gate di ENG-002: la
    stringa vuota veniva coercita a ROOT, e una cartella dove serve un file
    produceva un errore interno invece di un rifiuto con la ragione.
    """
    if not value.strip():
        raise RpcError(
            -32602,
            "percorso vuoto",
            "un percorso vuoto non significa 'la macchina': indica un file o una cartella",
        )
    grezzo = Path(value)
    try:
        percorso = (grezzo if grezzo.is_absolute() else ROOT / grezzo).resolve()
    except (OSError, ValueError) as exc:
        # `Path.resolve()` su un percorso con byte NUL solleva **ValueError**, non
        # OSError: senza catturarlo, il confine rispondeva -32603 «errore interno»
        # con un rimedio falso («riprova»). Un input invalido e' un rifiuto, non un
        # difetto del server (4o gate di ENG-002).
        raise RpcError(
            -32602,
            f"percorso non valido: {exc.__class__.__name__}",
            "il percorso contiene caratteri non ammessi (per esempio un byte NUL) o e' troppo lungo: correggilo",
        ) from exc
    if percorso != ROOT and ROOT not in percorso.parents:
        raise RpcError(
            -32602,
            f"percorso fuori dalla macchina: {value}",
            f"il server ha autorita' solo sotto {ROOT}; usa un percorso relativo alla macchina",
        )
    try:
        esiste = percorso.exists()
        e_file = percorso.is_file()
        e_cartella = percorso.is_dir()
    except (OSError, ValueError) as exc:
        raise RpcError(
            -32602,
            f"percorso inaccessibile: {exc.__class__.__name__}",
            "il percorso non e' valido su questo filesystem: correggilo o accorcialo",
        ) from exc
    if must_exist and not esiste:
        raise RpcError(
            -32602,
            f"percorso inesistente: {value}",
            "controlla il percorso: il file o la cartella non ci sono",
        )
    if must_be_file and esiste and not e_file:
        raise RpcError(
            -32602,
            f"serve un file, non una cartella: {value}",
            "indica un file (per esempio un .yaml o un .json)",
        )
    if must_be_dir and esiste and not e_cartella:
        raise RpcError(
            -32602,
            f"serve una cartella, non un file: {value}",
            "indica una cartella dove scrivere le prove estratte",
        )
    return percorso


def _guard_write(percorso: Path, cosa: str) -> None:
    """Refuse a write destination the gate would refuse.

    Il server non deve concedere piu' di quanto conceda il cancello: se `ad_scope`
    dice no, un client MCP non deve poter scrivere li' passando da un tool. Non e'
    una sandbox: e' la stessa autorita', applicata anche a questa porta.
    """
    verdetto = ad_scope.evaluate(str(percorso))
    if not verdetto.allowed:
        raise RpcError(
            -32602,
            f"{cosa}: {verdetto.reason}",
            "scegli una destinazione coperta da un contract attivo (ad_contract_check sa quale)",
        )


def _evidence_paths(values: Any) -> list[str]:
    """Resolve a list of evidence paths."""
    if not isinstance(values, list) or not values:
        raise RpcError(
            -32602,
            "'evidence' deve essere una lista non vuota di percorsi",
            "passa i file o le cartelle delle prove, relativi alla macchina",
        )
    risolti = []
    for valore in values:
        testo = str(valore).strip()
        if not testo:
            raise RpcError(
                -32602,
                "'evidence' contiene un percorso vuoto",
                "un percorso vuoto non significa 'tutte le prove': elenca i file",
            )
        risolti.append(str(_resolve(testo, must_exist=True)))
    return risolti


def _evidence_map(values: Any, ledger: str) -> dict[str, ad_evidence.Evidence]:
    """Load the evidence set, or the ledger's neighbours: never None."""
    if values:
        return {record.evidence_id: record for record in ad_evidence.collect(_evidence_paths(values))}
    cartella = Path(ledger).resolve().parent
    if cartella.is_dir() and (cartella == ROOT or ROOT in cartella.parents):
        return {record.evidence_id: record for record in ad_evidence.collect([cartella])}
    return {}


def _ledger_path(value: str | None) -> Path:
    """Resolve the unknowns ledger, defaulting to evidenze/incognite.yaml.

    `None` significa "non passato": si usa il default. `""` invece e' un valore
    passato, ed e' vuoto: si rifiuta (N5 del 2o gate di ENG-002).
    """
    percorso = _resolve("evidenze/incognite.yaml") if value is None else _resolve(value)
    if percorso.exists() and not percorso.is_file():
        raise RpcError(
            -32602,
            f"il registro delle incognite deve essere un file: {percorso.relative_to(ROOT)}",
            "indica il file del registro (per esempio evidenze/incognite.yaml)",
        )
    return percorso


def _yaml_block(text: str) -> dict[str, Any]:
    """Return the first fenced YAML block of a markdown document."""
    dentro = False
    righe: list[str] = []
    for riga in text.splitlines():
        if riga.strip().startswith("```yaml"):
            dentro = True
            continue
        if dentro and riga.strip() == "```":
            break
        if dentro:
            righe.append(riga)
    if not righe:
        return {}
    try:
        data = yaml.safe_load("\n".join(righe))
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def _drift_entries() -> list[dict[str, Any]]:
    """Parse the drift registry (one file, one section per entry)."""
    testo = (ROOT / "drift" / "README.md").read_text(encoding="utf-8")
    voci: list[dict[str, Any]] = []
    corrente: dict[str, Any] | None = None
    for riga in testo.splitlines():
        if riga.startswith("## DRIFT-"):
            if corrente:
                voci.append(corrente)
            identificatore, _, titolo = riga[3:].partition(" — ")
            corrente = {"id": identificatore.strip(), "title": titolo.strip()}
            continue
        if corrente is None:
            continue
        for campo, chiave in (
            ("Severita'", "severity"),
            ("Stato", "status"),
            ("Decisione", "decision"),
            ("Rischio", "risk"),
        ):
            if riga.startswith(f"| **{campo}** |"):
                valore = riga.split("|")[2].strip() if riga.count("|") >= 3 else ""
                corrente[chiave] = valore
    if corrente:
        voci.append(corrente)
    return voci


def _decisions() -> list[dict[str, Any]]:
    """Parse the decision records (header block of each file)."""
    voci = []
    for percorso in sorted((ROOT / "DECISIONI").glob("DEC-*.md")):
        dati = _yaml_block(percorso.read_text(encoding="utf-8"))
        voci.append(
            {
                "id": dati.get("id") or percorso.stem,
                "stato": dati.get("stato"),
                "livello": dati.get("livello"),
                "data": dati.get("data"),
                "file": percorso.name,
            }
        )
    return voci


def _plans() -> list[dict[str, Any]]:
    """Parse the plans waiting for a decision."""
    voci = []
    for percorso in sorted((ROOT / "piani").glob("*.md")):
        if percorso.name in ("README.md", "_TEMPLATE.md"):
            continue
        dati = _yaml_block(percorso.read_text(encoding="utf-8"))
        voci.append(
            {
                "id": dati.get("id") or percorso.stem,
                "stato": dati.get("stato"),
                "data": dati.get("data"),
                "file": percorso.name,
            }
        )
    return voci


def _errors() -> list[dict[str, Any]]:
    """Parse the error registry (one file per scar)."""
    voci = []
    for percorso in sorted((ROOT / "errori").glob("ERR-*.yaml")):
        try:
            dati = yaml.safe_load(percorso.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if not isinstance(dati, dict):
            continue
        voci.append(
            {
                "id": dati.get("id") or percorso.stem,
                "stato": dati.get("stato"),
                "diventa": dati.get("diventa"),
                "trovato_da": dati.get("trovato_da"),
                "file": percorso.name,
            }
        )
    return voci


# ---------------------------------------------------------------------------
# I tool. Ognuno dichiara i propri effetti: le annotazioni NON si scrivono a mano,
# si derivano, come nei contratti dei tool di REA (`src/contracts/toolEffects.ts`).
# ---------------------------------------------------------------------------

READ_ONLY = {"readOnlyHint": True, "destructiveHint": False}
WRITES = {"readOnlyHint": False, "destructiveHint": False}


def tool_session(argomenti: dict[str, Any]) -> dict[str, Any]:
    """Inventario: cosa esiste, cosa e' coperto, cosa aspetta una decisione."""
    contratti = []
    for percorso in sorted((ROOT / "contratti").rglob("*.yaml")):
        if percorso.name.startswith("_"):
            continue  # i modelli non sono contratti: `_TEMPLATE.yaml` non si esegue
        try:
            dati = yaml.safe_load(percorso.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if not isinstance(dati, dict) or dati.get("task_id") in (None, "PROD-000"):
            continue
        contratti.append(
            {
                "task_id": dati.get("task_id"),
                "status": dati.get("status"),
                "agent": dati.get("agent"),
                "write_scope": dati.get("write_scope") or [],
                "expires": dati.get("expires"),
            }
        )
    sede = {}
    if (ROOT / "sede.yaml").is_file():
        try:
            sede = yaml.safe_load((ROOT / "sede.yaml").read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            sede = {}
    attivi = [c for c in contratti if str(c["status"]).lower() in ("active", "attivo", "approvato")]
    return {
        "machine": str(ROOT),
        "ceo": (sede.get("ceo") or {}).get("nome"),
        "contracts": {
            "total": len(contratti),
            "active": attivi,
        },
        "registers": {
            "errori": len(_errors()),
            "drift_open": len([v for v in _drift_entries() if str(v.get("status", "")).upper() == "OPEN"]),
            "decisions": len(_decisions()),
            "plans": len(_plans()),
            "unknowns": len(ad_evidence.load_unknowns(ROOT / "evidenze" / "incognite.yaml")),
        },
        "tools": [voce["name"] for voce in TOOLS],
    }


def tool_contract_check(argomenti: dict[str, Any]) -> dict[str, Any]:
    """Say whether one path can be written, and by which contract."""
    percorso = str(argomenti.get("path") or "").strip()
    if not percorso:
        raise RpcError(-32602, "'path' mancante", "passa il percorso da verificare, relativo alla macchina")
    risolto = _resolve(percorso)
    verdetto = ad_scope.evaluate(str(risolto))
    return {
        "path": verdetto.relative,
        "protected": verdetto.protected,
        "covered": verdetto.covered,
        "contract": verdetto.task_id or "",
        "allowed": verdetto.allowed,
        "reason": verdetto.reason,
    }


def tool_contract_validate(argomenti: dict[str, Any]) -> dict[str, Any]:
    """Validate one contract against the card registry."""
    percorso = _resolve(str(argomenti.get("contract") or ""), must_exist=True, must_be_file=True)
    try:
        contract = ad_contract.load(percorso)
    except ad_contract.ContractError as exc:
        return {"ok": False, "contract": str(percorso.relative_to(ROOT)), "findings": [str(exc)]}
    findings = ad_contract.validate(contract, ad_registry.load())
    violazioni = [f for f in findings if f.level != "WARNING"]
    avvisi = [f for f in findings if f.level == "WARNING"]
    return {
        "ok": not violazioni,
        "contract": str(percorso.relative_to(ROOT)),
        "violations": [f"{f.code}: {f.message}" for f in violazioni],
        "warnings": [f"{f.code}: {f.message}" for f in avvisi],
    }


def tool_cards_match(argomenti: dict[str, Any]) -> dict[str, Any]:
    """Match a task type against the authorized cards."""
    tipo = str(argomenti.get("task_type") or "").strip()
    if not tipo:
        raise RpcError(-32602, "'task_type' mancante", "passa il tipo di task, per esempio engine_tooling")
    registro = ad_registry.load()
    trovate = [
        {"id": card.id, "domain": card.domain, "type": card.type}
        for card in registro.values()
        if tipo in (card.authorized_task_types or ()) and card.assignable
    ]
    if not trovate:
        return {
            "matched": False,
            "task_type": tipo,
            "cards": [],
            "reason": "nessuna card autorizza questo tipo: STOP, non si assegna alla card piu' vicina",
        }
    return {"matched": True, "task_type": tipo, "cards": trovate}


def tool_verdict(argomenti: dict[str, Any]) -> dict[str, Any]:
    """The Quality Gate verdict: the same rule as tools/verdict.py."""
    contratto = _resolve(str(argomenti.get("contract") or ""), must_exist=True)
    prove = _evidence_paths(argomenti.get("evidence"))
    try:
        contract = ad_contract.load(contratto)
    except ad_contract.ContractError as exc:
        raise RpcError(-32602, str(exc), "controlla il contract: non e' leggibile o non e' valido") from exc
    evidence = ad_evidence.collect(prove)
    verdetto = ad_evidence.evaluate(contract, evidence)
    return {
        "task_id": contract.get("task_id"),
        "outcome": verdetto.outcome,
        "human_gate": verdetto.human_gate,
        "gates": [
            {
                "gate": r.gate,
                "state": r.state,
                "producer": r.producer,
                "evidence_id": r.evidence_id,
                "limitations": list(r.limitations),
                "detail": r.detail,
            }
            for r in verdetto.gates
        ],
        "notes": list(verdetto.notes),
    }


def tool_evidence_check(argomenti: dict[str, Any]) -> dict[str, Any]:
    """Check identity, schema and coverage of one or more evidence records."""
    record = ad_evidence.collect(_evidence_paths(argomenti.get("evidence")))
    esiti = []
    for prova in record:
        # `executor` vuoto: senza un contract non si sa chi esegue, e la regola
        # "chi produce non valida" si applica solo quando l'esecutore e' noto.
        problemi = ad_evidence._validity_problem(prova, prova.task_id, prova.gate, "")
        esiti.append(
            {
                "file": prova.path.name,
                "gate": prova.gate,
                "outcome": prova.outcome,
                "evidence_id": prova.evidence_id,
                "ok": not problemi,
                "problems": [problemi] if problemi else [],
            }
        )
    return {"checked": len(esiti), "records": esiti, "ok": all(e["ok"] for e in esiti)}


def tool_unknowns(argomenti: dict[str, Any]) -> dict[str, Any]:
    """Manage the unknowns registry: list, show, new, update, resolve, check."""
    azione = str(argomenti.get("action") or "")
    if azione not in ("list", "check", "new", "update", "resolve"):
        raise RpcError(
            -32602,
            f"azione '{azione}' non ammessa per ad_unknowns",
            "ammesse: list, check, new, update, resolve",
        )
    ledger = _ledger_path(argomenti.get("ledger"))
    if ledger.exists() and not ledger.is_file():
        raise RpcError(
            -32602,
            f"il registro deve essere un file: {argomenti.get('ledger') or ledger.relative_to(ROOT)}",
            "indica il file del registro (per esempio evidenze/incognite.yaml)",
        )
    records = ad_evidence.load_unknowns(ledger)
    if azione == "list":
        return {"ledger": str(ledger.relative_to(ROOT)), "unknowns": records}
    if azione == "check":
        problemi = ad_evidence.check_unknowns(records, _evidence_map(argomenti.get("evidence"), str(ledger)))
        return {"ok": not problemi, "unknowns": len(records), "problems": problemi}
    if azione == "new":
        domanda = str(argomenti.get("question") or "")
        dominio = str(argomenti.get("domain") or "")
        if not domanda or not dominio:
            raise RpcError(-32602, "'question' e 'domain' obbligatori", "una domanda senza dominio non e' una voce")
        nuovo = ad_evidence.new_unknown(
            domanda, dominio,
            severity=str(argomenti.get("severity") or "medium"),
            required_authority=argomenti.get("required_authority"),
            supporting=tuple(argomenti.get("evidence_ids") or ()),
        )
        candidati = records + [nuovo]
        problemi = ad_evidence.check_unknowns(candidati, _evidence_map(argomenti.get("evidence"), str(ledger)))
        if problemi:
            raise RpcError(
                -32602,
                "la voce non e' valida: " + "; ".join(problemi),
                "una voce che cita prove inesistenti non si scrive: passa --evidence o togli i riferimenti",
            )
        _guard_write(ledger, "registro delle incognite")
        ad_evidence.save_unknowns(ledger, candidati)
        return {"written": nuovo["unknown_id"], "revision": nuovo["revision"]}
    identificatore = str(argomenti.get("id") or "")
    trovata = next((r for r in records if str(r.get("unknown_id")) == identificatore), None)
    if trovata is None:
        raise RpcError(-32602, f"incognita '{identificatore}' non trovata", "usa action=list per gli id esistenti")
    if azione == "resolve":
        risoluzione = {
            "disposition": str(argomenti.get("disposition") or ""),
            "rationale": str(argomenti.get("rationale") or ""),
            "evidence_ids": list(argomenti.get("evidence_ids") or ()),
        }
        aggiornata = ad_evidence.update_unknown(trovata, status="resolved", resolution=risoluzione)
    elif azione == "update":
        aggiornata = ad_evidence.update_unknown(
            trovata,
            status=argomenti.get("status"),
            severity=argomenti.get("severity"),
        )
    else:
        raise RpcError(-32602, f"azione '{azione}' non ammessa", "ammesse: list, check, new, update, resolve")
    nuove = [aggiornata if r is trovata else r for r in records]
    problemi = ad_evidence.check_unknowns(nuove, _evidence_map(argomenti.get("evidence"), str(ledger)))
    if problemi:
        raise RpcError(-32602, "la modifica non e' valida: " + "; ".join(problemi), "una domanda si chiude solo con una prova che esiste")
    _guard_write(ledger, "registro delle incognite")
    ad_evidence.save_unknowns(ledger, nuove)
    return {"written": aggiornata["unknown_id"], "status": aggiornata["status"], "revision": aggiornata["revision"]}


def tool_bundle(argomenti: dict[str, Any]) -> dict[str, Any]:
    """Export, check or import a sealed bundle of evidence."""
    azione = str(argomenti.get("action") or "")
    if azione not in ("export", "check", "import"):
        raise RpcError(
            -32602, f"azione '{azione}' non ammessa per ad_bundle", "ammesse: export, check, import"
        )
    if azione == "export" and not argomenti.get("out"):
        raise RpcError(-32602, "'out' obbligatorio per export", "passa il file dove scrivere il bundle")
    if azione in ("check", "import") and not argomenti.get("bundle_path"):
        raise RpcError(
            -32602, f"'bundle_path' obbligatorio per {azione}", "passa il file del bundle da leggere"
        )
    if azione == "import" and not argomenti.get("into"):
        raise RpcError(-32602, "'into' obbligatorio per import", "passa la cartella dove estrarre")
    if azione == "export":
        prove = ad_evidence.collect(_evidence_paths(argomenti.get("evidence")))
        ledger = _ledger_path(argomenti.get("ledger"))
        incognite = ad_evidence.load_unknowns(ledger)
        testimone = None
        if not argomenti.get("no_witness"):
            if argomenti.get("witness") is None:
                percorso_testimone = _resolve("evidenze/albero.yaml")
            else:
                percorso_testimone = _resolve(
                    argomenti["witness"], must_exist=True, must_be_file=True
                )
            if percorso_testimone.is_file():
                testimone = ad_evidence.load_witness(percorso_testimone)
        bundle = ad_evidence.create_bundle(prove, incognite, witness=testimone)
        problemi = ad_evidence.verify_bundle(bundle)
        if problemi:
            raise RpcError(-32603, "bundle non verificabile: " + "; ".join(problemi), "controlla i record")
        destinazione = _resolve(str(argomenti.get("out") or ""))
        if destinazione.is_dir():
            raise RpcError(
                -32602,
                f"out e' una cartella: {destinazione.relative_to(ROOT)}",
                "indica un file, per esempio evidenze/mio-bundle.json",
            )
        _guard_write(destinazione, "bundle")
        ad_evidence.save_bundle(destinazione, bundle)
        return {
            "written": str(destinazione.relative_to(ROOT)),
            "task_id": bundle["task_id"],
            "records": len(bundle["records"]),
            "unknowns": len(bundle["unknowns"]),
            "witness": bool(testimone),
            "seal": bundle["seal"],
        }
    percorso = _resolve(str(argomenti.get("bundle_path") or ""), must_exist=True, must_be_file=True)
    bundle = ad_evidence.load_bundle(percorso)
    problemi = ad_evidence.verify_bundle(bundle)
    if problemi:
        raise RpcError(-32602, "bundle non attendibile: " + "; ".join(problemi), "il pacchetto e' stato modificato: non usarlo")
    if azione == "check":
        return {"ok": True, "task_id": bundle["task_id"], "records": len(bundle["records"]), "unknowns": len(bundle["unknowns"])}
    if azione == "import":
        destinazione = _resolve(str(argomenti.get("into") or ""), must_be_dir=True)
        _guard_write(destinazione, "import")
        esito = ad_evidence.extract_bundle(bundle, destinazione)
        return {"imported": str(destinazione.relative_to(ROOT)), **esito}
    raise RpcError(-32602, f"azione '{azione}' non ammessa", "ammesse: export, check, import")


def tool_tree(argomenti: dict[str, Any]) -> dict[str, Any]:
    """Record or check the out-of-band witness of a tree."""
    azione = str(argomenti.get("action") or "")
    if azione not in ("record", "check"):
        raise RpcError(
            -32602,
            f"azione '{azione}' non ammessa per ad_tree",
            "ammesse: record, check",
        )
    if azione == "check" and "paths" in argomenti:
        # Ambiguita' segnalata dal gate di ENG-003: su `check` i `paths` venivano
        # validati e poi ignorati (il perimetro e' quello del testimone), quindi un
        # client che chiedeva di verificare un perimetro ne riceveva un altro.
        raise RpcError(
            -32602,
            "ad_tree: 'paths' vale solo per action=record",
            "il controllo usa il perimetro registrato nel testimone: per sorvegliare "
            "un altro perimetro, registra un nuovo testimone con action=record",
        )
    radice = _resolve(
        argomenti["root"] if "root" in argomenti else ".",
        must_exist=True,
        must_be_dir=True,
    )
    elenco = argomenti.get("paths")
    if elenco is not None and not elenco:
        raise RpcError(
            -32602,
            "ad_tree: 'paths' vuoto non e' 'usa i default'",
            "o ometti 'paths' (si usano le radici della macchina) o passane almeno una",
        )
    percorsi = []
    for voce in elenco if elenco is not None else ad_evidence.DEFAULT_TREE_PATHS:
        if not str(voce).strip():
            raise RpcError(
                -32602,
                "ad_tree: 'paths' contiene un elemento vuoto",
                "un elemento vuoto non significa 'la radice': indica una sottocartella o togli l'elemento",
            )
        candidato = Path(str(voce))
        try:
            risolto = (candidato if candidato.is_absolute() else radice / candidato).resolve()
        except (OSError, ValueError) as exc:
            # `Path.resolve()` su un byte NUL solleva ValueError: questa copia del
            # controllo (fuori da `_resolve`) non lo catturava, e il gate di ENG-003
            # l'ha trovata. Un input invalido e' un rifiuto, non un errore interno.
            raise RpcError(
                -32602,
                f"ad_tree: percorso non valido in 'paths': {exc.__class__.__name__}",
                "un elemento di 'paths' contiene caratteri non ammessi (per esempio un byte NUL): correggilo",
            ) from exc
        if risolto != radice and radice not in risolto.parents:
            raise RpcError(
                -32602,
                f"percorso sorvegliato fuori dalla radice: {voce}",
                f"le radici da sorvegliare devono stare sotto {radice}",
            )
        percorsi.append(str(voce))
    percorsi = tuple(percorsi)
    testimone = _resolve(
        argomenti["witness"] if "witness" in argomenti else "evidenze/albero.yaml",
        must_be_file=True,
    )
    esclusi: tuple[str, ...] = ()
    if testimone == radice or radice in testimone.parents:
        esclusi = (testimone.relative_to(radice).as_posix(),)
    if azione == "record":
        _guard_write(testimone, "testimone")
        witness = ad_evidence.create_witness(radice, percorsi, exclude=esclusi)
        ad_evidence.save_witness(testimone, witness)
        return {
            "written": str(testimone.relative_to(ROOT)),
            "files": len(witness["files"]),
            "roots": len(percorsi),
            "seal": witness["digest"],
        }
    if not testimone.is_file():
        raise RpcError(
            -32602,
            f"ad_tree: testimone inesistente: {testimone.relative_to(ROOT) if ROOT in testimone.parents else testimone}",
            "registra prima un testimone con action=record, oppure indica un witness esistente",
        )
    witness = ad_evidence.load_witness(testimone)
    guardati = tuple(witness.get("paths") or percorsi)
    corrente = ad_evidence.tree_fingerprint(radice, guardati, tuple(witness.get("exclude") or ()))
    copertura = _evidence_map(argomenti.get("evidence"), str(testimone))
    problemi = ad_evidence.compare_tree(witness, corrente, copertura or None)
    return {
        "ok": not problemi,
        "files": len(corrente["files"]),
        "contaminations": problemi,
        "recorded_at": witness.get("recorded_at"),
    }


def tool_registry(argomenti: dict[str, Any]) -> dict[str, Any]:
    """Read a register: summary by default, complete with paging."""
    tipo = str(argomenti.get("kind") or "")
    lettori = {
        "errori": _errors,
        "drift": _drift_entries,
        "decisions": _decisions,
        "plans": _plans,
    }
    if tipo not in lettori:
        raise RpcError(-32602, f"registro '{tipo}' non ammesso", "ammessi: errori, drift, decisions, plans")
    voci = lettori[tipo]()
    dettaglio = str(argomenti.get("detail") or "summary")
    if dettaglio == "complete":
        offset = max(0, int(argomenti.get("offset") or 0))
        limite = min(200, max(1, int(argomenti.get("limit") or 50)))
        pagina = voci[offset : offset + limite]
        return {
            "kind": tipo,
            "total": len(voci),
            "offset": offset,
            "returned": len(pagina),
            "next_offset": offset + len(pagina) if offset + len(pagina) < len(voci) else None,
            "items": pagina,
        }
    stati: dict[str, int] = {}
    for voce in voci:
        stato = str(voce.get("stato") or voce.get("status") or "?").lower()
        stati[stato] = stati.get(stato, 0) + 1
    return {"kind": tipo, "total": len(voci), "by_state": stati, "detail": "summary"}


TOOLS: list[dict[str, Any]] = [
    {
        "name": "ad_session",
        "description": "Inventario della macchina: contratti attivi, registri, tool disponibili. E' la prima cosa da chiedere quando non sai cosa puoi fare.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "annotations": READ_ONLY,
        "handler": tool_session,
    },
    {
        "name": "ad_contract_check",
        "description": "Dice se un percorso della macchina si puo' scrivere, e quale contract lo copre. E' il confine di autorizzazione.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "percorso relativo alla macchina"}},
            "required": ["path"],
            "additionalProperties": False,
        },
        "annotations": READ_ONLY,
        "handler": tool_contract_check,
    },
    {
        "name": "ad_contract_validate",
        "description": "Valida un task contract contro il registry delle card: dice se il lavoro puo' partire.",
        "inputSchema": {
            "type": "object",
            "properties": {"contract": {"type": "string", "description": "file del contract"}},
            "required": ["contract"],
            "additionalProperties": False,
        },
        "annotations": READ_ONLY,
        "handler": tool_contract_validate,
    },
    {
        "name": "ad_cards_match",
        "description": "Cerca la card autorizzata per un tipo di task. Nessun match significa STOP, non 'la card piu' vicina'.",
        "inputSchema": {
            "type": "object",
            "properties": {"task_type": {"type": "string", "description": "tipo di task dichiarato nel contract"}},
            "required": ["task_type"],
            "additionalProperties": False,
        },
        "annotations": READ_ONLY,
        "handler": tool_cards_match,
    },
    {
        "name": "ad_verdict",
        "description": "Il verdetto del Quality Gate: ACCEPT o REJECT leggendo le evidenze. Solo PASS con copertura completa chiude un gate.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "contract": {"type": "string", "description": "file del contract"},
                "evidence": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            },
            "required": ["contract", "evidence"],
            "additionalProperties": False,
        },
        "annotations": READ_ONLY,
        "handler": tool_verdict,
    },
    {
        "name": "ad_evidence_check",
        "description": "Controlla identita', schema e copertura di una o piu' prove, senza emettere un verdetto.",
        "inputSchema": {
            "type": "object",
            "properties": {"evidence": {"type": "array", "items": {"type": "string"}, "minItems": 1}},
            "required": ["evidence"],
            "additionalProperties": False,
        },
        "annotations": READ_ONLY,
        "handler": tool_evidence_check,
    },
    {
        "name": "ad_unknowns",
        "description": "Il registro delle incognite: elenca, crea, aggiorna, risolve o controlla le domande aperte. Una domanda si chiude solo con una prova che esiste.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list", "check", "new", "update", "resolve"]},
                "ledger": {"type": "string"},
                "id": {"type": "string"},
                "question": {"type": "string"},
                "domain": {"type": "string"},
                "severity": {"type": "string", "enum": list(ad_evidence.SEVERITIES)},
                "status": {"type": "string", "enum": list(ad_evidence.UNKNOWN_STATUSES)},
                "disposition": {"type": "string", "enum": list(ad_evidence.DISPOSITIONS)},
                "rationale": {"type": "string"},
                "evidence_ids": {"type": "array", "items": {"type": "string"}},
                "required_authority": {"type": "string", "enum": list(ad_evidence.AUTHORITY_VALUES)},
                "evidence": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["action"],
            "additionalProperties": False,
        },
        "annotations": WRITES,
        "handler": tool_unknowns,
    },
    {
        "name": "ad_bundle",
        "description": "Esporta, verifica o importa un pacchetto sigillato di prove (con le incognite e il testimone). Un pacchetto manomesso viene rifiutato.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["export", "check", "import"]},
                "evidence": {"type": "array", "items": {"type": "string"}},
                "ledger": {"type": "string"},
                "witness": {"type": "string"},
                "no_witness": {"type": "boolean"},
                "out": {"type": "string"},
                "bundle_path": {"type": "string"},
                "into": {"type": "string"},
            },
            "required": ["action"],
            "additionalProperties": False,
        },
        "annotations": WRITES,
        "handler": tool_bundle,
    },
    {
        "name": "ad_tree",
        "description": "Registra o verifica l'impronta dell'albero: le modifiche che nessuna evidenza nomina sono contaminazioni.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["record", "check"]},
                "root": {"type": "string"},
                # `minItems` non c'e' di proposito: la lista vuota deve arrivare al
                # gestore, che sa spiegare *perche'* e' sbagliata (paths vale solo per
                # record; su record, o lo ometti o ne passi almeno una). Rilievo 2 di
                # ENG-003: lo schema rispondeva con un messaggio generico.
                "paths": {"type": "array", "items": {"type": "string"}},
                "witness": {"type": "string"},
                "evidence": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["action"],
            "additionalProperties": False,
        },
        "annotations": WRITES,
        "handler": tool_tree,
    },
    {
        "name": "ad_registry",
        "description": "Legge un registro (errori, drift, decisioni, piani): riassunto per stato, oppure voci complete con paginazione.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["errori", "drift", "decisions", "plans"]},
                "detail": {"type": "string", "enum": ["summary", "complete"]},
                "offset": {"type": "integer", "minimum": 0},
                "limit": {"type": "integer", "minimum": 1, "maximum": 200},
            },
            "required": ["kind"],
            "additionalProperties": False,
        },
        "annotations": READ_ONLY,
        "handler": tool_registry,
    },
]

_BY_NAME = {voce["name"]: voce for voce in TOOLS}


def _catalog() -> list[dict[str, Any]]:
    """Return the wire form of the tool catalog."""
    return [
        {
            "name": voce["name"],
            "description": voce["description"],
            "inputSchema": voce["inputSchema"],
            "annotations": voce["annotations"],
        }
        for voce in TOOLS
    ]


_TIPI = {
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
}


def _validate_arguments(voce: dict[str, Any], argomenti: dict[str, Any]) -> None:
    """Enforce the declared input schema.

    M3 del gate di ENG-002: gli schemi c'erano ma non si applicavano — un argomento
    in piu' veniva ignorato, `path: 123` diventava una stringa, un tipo sbagliato
    arrivava al gestore e usciva come errore interno. Uno schema che non si applica
    e' documentazione, non un contratto: qui si applica.
    """
    nome = voce["name"]
    schema = voce["inputSchema"]
    proprieta = schema.get("properties") or {}
    if schema.get("additionalProperties") is False:
        estranei = sorted(set(argomenti) - set(proprieta))
        if estranei:
            raise RpcError(
                -32602,
                f"{nome}: argomenti non previsti: {', '.join(estranei)}",
                f"ammessi: {', '.join(sorted(proprieta)) or 'nessuno'}",
            )
    for richiesto in schema.get("required") or []:
        if richiesto not in argomenti:
            raise RpcError(
                -32602,
                f"{nome}: argomento obbligatorio mancante: {richiesto}",
                f"passa '{richiesto}'",
            )
    for chiave, valore in argomenti.items():
        sotto = proprieta.get(chiave)
        if not isinstance(sotto, dict):
            continue
        tipo = sotto.get("type")
        controllo = _TIPI.get(str(tipo))
        if controllo is not None and not controllo(valore):
            raise RpcError(
                -32602,
                f"{nome}: '{chiave}' deve essere di tipo {tipo}",
                f"passa '{chiave}' come {tipo}",
            )
        minimo_valore = sotto.get("minimum")
        massimo_valore = sotto.get("maximum")
        if isinstance(valore, (int, float)) and not isinstance(valore, bool):
            if isinstance(minimo_valore, (int, float)) and valore < minimo_valore:
                raise RpcError(
                    -32602,
                    f"{nome}: '{chiave}' deve essere >= {minimo_valore}",
                    f"passa '{chiave}' almeno {minimo_valore}",
                )
            if isinstance(massimo_valore, (int, float)) and valore > massimo_valore:
                raise RpcError(
                    -32602,
                    f"{nome}: '{chiave}' deve essere <= {massimo_valore}",
                    f"passa '{chiave}' al massimo {massimo_valore}",
                )
        if "enum" in sotto and valore not in sotto["enum"]:
            raise RpcError(
                -32602,
                f"{nome}: '{chiave}' non ammesso: {valore!r}",
                "ammessi: " + ", ".join(str(voce_enum) for voce_enum in sotto["enum"]),
            )
        if tipo == "array" and isinstance(valore, list):
            minimo = sotto.get("minItems")
            if isinstance(minimo, int) and len(valore) < minimo:
                raise RpcError(
                    -32602,
                    f"{nome}: '{chiave}' richiede almeno {minimo} elementi",
                    f"passa almeno {minimo} elementi in '{chiave}'",
                )
            tipo_elemento = (sotto.get("items") or {}).get("type")
            controllo_elemento = _TIPI.get(str(tipo_elemento))
            if controllo_elemento is not None:
                for indice, elemento in enumerate(valore):
                    if not controllo_elemento(elemento):
                        raise RpcError(
                            -32602,
                            f"{nome}: '{chiave}[{indice}]' deve essere di tipo {tipo_elemento}",
                            f"passa solo {tipo_elemento} in '{chiave}'",
                        )


def _call_tool(params: dict[str, Any]) -> dict[str, Any]:
    """Dispatch one tools/call."""
    nome = str(params.get("name") or "")
    voce = _BY_NAME.get(nome)
    if voce is None:
        raise RpcError(-32602, f"tool '{nome}' non esiste", "usa tools/list per i tool disponibili")
    argomenti = params.get("arguments") if params.get("arguments") is not None else {}
    if not isinstance(argomenti, dict):
        raise RpcError(-32602, "'arguments' deve essere un oggetto", "passa un oggetto JSON")
    _validate_arguments(voce, argomenti)
    try:
        risultato = voce["handler"](argomenti)
    except RpcError:
        raise
    except (ad_evidence.EvidenceError, ad_evidence.UnknownRegistryError, ad_evidence.BundleError, ad_evidence.TreeError) as exc:
        raise RpcError(-32603, str(exc), "controlla gli input: il registro o il file non e' leggibile") from exc
    testo = json.dumps(risultato, ensure_ascii=False, indent=2)
    return {
        "content": [{"type": "text", "text": testo}],
        "structuredContent": risultato,
        "isError": False,
    }


def _handle(method: str, params: dict[str, Any]) -> dict[str, Any]:
    """Handle one JSON-RPC request."""
    if method == "initialize":
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
        }
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": _catalog()}
    if method == "tools/call":
        return _call_tool(params)
    raise RpcError(
        -32601,
        f"metodo '{method}' non supportato",
        "il server supporta initialize, ping, tools/list, tools/call",
    )


def serve(stdin: Any = None, stdout: Any = None) -> None:
    """Serve MCP over stdio, one JSON-RPC message per line."""
    ingresso = stdin or sys.stdin
    uscita = stdout or sys.stdout
    # Si legge in BYTE: un client che manda UTF-8 non valido non deve uccidere il
    # server con un UnicodeDecodeError. Il confine risponde -32700 e resta vivo.
    flusso = getattr(ingresso, "buffer", ingresso)
    for grezza in flusso:
        if isinstance(grezza, bytes):
            try:
                riga = grezza.decode("utf-8").strip()
            except UnicodeDecodeError:
                _scrivi(
                    uscita,
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {
                            "code": -32700,
                            "message": "byte non validi in UTF-8",
                            "data": {"remediation": "invia JSON UTF-8: controlla l'encoding del client"},
                        },
                    },
                )
                continue
        else:
            riga = grezza.strip()
        if not riga:
            continue
        try:
            messaggio = json.loads(riga)
        except RecursionError:
            _scrivi(
                uscita,
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32700,
                        "message": "JSON troppo annidato",
                        "data": {"remediation": "riduci l'annidamento del messaggio: il server non lo interpreta"},
                    },
                },
            )
            continue
        except json.JSONDecodeError:
            _scrivi(
                uscita,
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32700,
                        "message": "JSON non valido",
                        "data": {"remediation": "un messaggio per riga, JSON-RPC 2.0: controlla le virgolette e le graffe"},
                    },
                },
            )
            continue
        if not isinstance(messaggio, dict):
            _scrivi(
                uscita,
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32600,
                        "message": "richiesta non valida: serve un oggetto",
                        "data": {"remediation": "invia un oggetto JSON-RPC con jsonrpc, id, method"},
                    },
                },
            )
            continue
        identificatore = messaggio.get("id")
        metodo = messaggio.get("method")
        if messaggio.get("jsonrpc") != "2.0":
            _scrivi(
                uscita,
                {
                    "jsonrpc": "2.0",
                    "id": identificatore,
                    "error": {
                        "code": -32600,
                        "message": "manca jsonrpc: \"2.0\"",
                        "data": {"remediation": "ogni messaggio deve dichiarare jsonrpc: \"2.0\""},
                    },
                },
            )
            continue
        if identificatore is None:
            # notifica (per esempio notifications/initialized): nessuna risposta
            continue
        if not isinstance(metodo, str):
            _scrivi(
                uscita,
                {
                    "jsonrpc": "2.0",
                    "id": identificatore,
                    "error": {
                        "code": -32600,
                        "message": "manca 'method'",
                        "data": {"remediation": "una richiesta con id deve avere un metodo: per esempio tools/list"},
                    },
                },
            )
            continue
        parametri = messaggio.get("params") if messaggio.get("params") is not None else {}
        if not isinstance(parametri, dict):
            _scrivi(
                uscita,
                {
                    "jsonrpc": "2.0",
                    "id": identificatore,
                    "error": {
                        "code": -32602,
                        "message": "'params' deve essere un oggetto",
                        "data": {"remediation": "passa un oggetto JSON in 'params', o ometti il campo"},
                    },
                },
            )
            continue
        try:
            risultato = _handle(metodo, parametri)
            _scrivi(uscita, {"jsonrpc": "2.0", "id": identificatore, "result": risultato})
        except RpcError as exc:
            _scrivi(
                uscita,
                {
                    "jsonrpc": "2.0",
                    "id": identificatore,
                    "error": {"code": exc.code, "message": exc.message, "data": exc.data()},
                },
            )
        except Exception as exc:  # noqa: BLE001 - il confine non deve morire su un errore inatteso
            _scrivi(
                uscita,
                {
                    "jsonrpc": "2.0",
                    "id": identificatore,
                    "error": {
                        "code": -32603,
                        "message": f"errore interno: {exc.__class__.__name__}",
                        "data": {"remediation": "riprova; se persiste, e' un difetto del server"},
                    },
                },
            )


def _scrivi(uscita: Any, messaggio: dict[str, Any]) -> None:
    """Write one JSON-RPC message and flush."""
    uscita.write(json.dumps(messaggio, ensure_ascii=False) + "\n")
    uscita.flush()


def main() -> int:
    """Entry point."""
    try:
        serve()
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
