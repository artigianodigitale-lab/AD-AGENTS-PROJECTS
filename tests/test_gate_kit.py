#!/usr/bin/env python3
"""Il kit del revisore: difesa dalla dimenticanza, buchi meccanici chiusi (ENG-009).

    python3 tests/test_gate_kit.py

Perche' esiste. Il kit non promette un lucchetto crittografico (DEC-0063): un file
locale non firmato non si rende manomettibile. Promette di **impedire la
dimenticanza** — aprire un gate senza batteria verde, chiudere senza entrambi i
revisori, chiudere con il prodotto mosso — e di rendere **rumorose** le manomissioni.
Qui si prova ogni rifiuto, perche' un controllo che non sa fallire non e' un controllo.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "tools"))

import ad_contract  # noqa: E402
import ad_registry  # noqa: E402
import gate_kit  # noqa: E402
import yaml  # noqa: E402

PASSED = 0


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    """Assert one expectation."""
    global PASSED
    if not condizione:
        raise AssertionError(f"{etichetta}: {dettaglio or 'condizione falsa'}")
    PASSED += 1


def _contratto(radice: Path, task: str = "TEST-001", stato: str = "active") -> Path:
    return radice / "contratti" / "societa" / f"{task}.yaml"


def _macchina(radice: Path, *, stato: str = "active", scope=None, task: str = "TEST-001") -> Path:
    """A scratch machine: one contract, one file, one expected-absent file, a directory."""
    for cartella in ("contratti/societa", "evidenze", "drift", "errori", "cartella"):
        (radice / cartella).mkdir(parents=True, exist_ok=True)
    (radice / "contratto.txt").write_text("contenuto\n", encoding="utf-8")
    (radice / "cartella" / "uno.txt").write_text("uno\n", encoding="utf-8")
    voci = scope if scope is not None else ["contratto.txt", "nuovo.txt", "cartella"]
    righe = ["task_id: " + task, "status: " + stato, "acceptance_criteria:", "  - 'criterio uno'", "write_scope:"]
    if isinstance(voci, str):
        righe.append("  " + voci)
    else:
        righe += [f"  - {voce}" for voce in voci]
    _contratto(radice, task).write_text("\n".join(righe) + "\n", encoding="utf-8")
    return radice


def _stamp(radice: Path, task: str = "TEST-001", *, verde: bool = True, minuti: int = 0,
           task_id: str | None = None, contract_sha: str | None = None) -> None:
    """Write a preflight stamp as the real preflight does."""
    quando = datetime.now(timezone.utc) - timedelta(minutes=minuti)
    dati = {
        "task_id": task_id if task_id is not None else task,
        "contract_sha": contract_sha if contract_sha is not None else gate_kit._sha_contract(task, radice),
        "verde": verde,
        "at": quando.isoformat(timespec="seconds"),
    }
    gate_kit.preflight_path(task, radice).write_text(json.dumps(dati), encoding="utf-8")


def _evidenze(radice: Path, task: str = "TEST-001", *, solo: str | None = None, vecchie: bool = False) -> None:
    """Write the two gate evidences (or only one, to test the refusal)."""
    for suffisso in ("QA", "CodeReview"):
        if solo is not None and suffisso != solo:
            continue
        percorso = radice / "evidenze" / f"{task}-{suffisso}.yaml"
        percorso.write_text(
            "schema: 2\n"
            f"task_id: {task}\n"
            f"gate: {suffisso}\n"
            "outcome: PASS\n"
            f"producer: {suffisso.lower()}\n"
            "confidence: observed\n"
            "authority: execution\n"
            "coverage: {status: complete, examined: 1, total: 1}\n"
            "limitations:\n  - 'nessuna'\n"
            "side_effects: {code: YES, database: NO, schema: NO, deps: NO, env: NO, external_services: NO}\n",
            encoding="utf-8",
        )
        if vecchie:
            vecchio = (datetime.now(timezone.utc) - timedelta(hours=2)).timestamp()
            os.utime(percorso, (vecchio, vecchio))


def _stub_preflight(radice: Path, *, rosso: bool = False) -> None:
    """Fake the three preflight commands in a scratch root (real subprocess path)."""
    (radice / "tools").mkdir(exist_ok=True)
    (radice / "tests").mkdir(exist_ok=True)
    codice = "raise SystemExit(1 if %r else 0)\n" % rosso
    for relativo in ("tools/validate_contract.py", "tests/ci.py", "tools/verdict.py"):
        percorso = radice / relativo
        percorso.write_text(codice, encoding="utf-8")


def test_ciclo_completo() -> None:
    """Preflight -> freeze -> check -> movimenti -> close (con entrambe le evidenze)."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp))
        _stamp(radice)
        dati = gate_kit.freeze("TEST-001", radice)
        check("gate aperto", dati.get("gate") == "open", str(dati.get("gate")))
        check("revisione R1", dati.get("revision") == "R1", str(dati.get("revision")))
        check("marcatore di formato", dati.get("tool") == "gate_kit", str(dati.get("tool")))
        check("il contract e' sorvegliato", any("TEST-001.yaml" in f for f in dati["files"]), str(list(dati["files"])))
        check("file atteso registrato", dati.get("expected") == ["nuovo.txt"], str(dati.get("expected")))
        check("directory registrata", dati.get("dirs") == {"cartella": ["cartella/uno.txt"]}, str(dati.get("dirs")))
        check("check immobile", gate_kit.check("TEST-001", radice) == [], str(gate_kit.check("TEST-001", radice)))

        (radice / "contratto.txt").write_text("manomesso\n", encoding="utf-8")
        check("MOSSO rilevato", any("MOSSO" in p for p in gate_kit.check("TEST-001", radice)), "no")
        (radice / "contratto.txt").write_text("contenuto\n", encoding="utf-8")
        (radice / "nuovo.txt").write_text("x\n", encoding="utf-8")
        check("COMPARSO rilevato", any("COMPARSO" in p for p in gate_kit.check("TEST-001", radice)), "no")
        (radice / "nuovo.txt").unlink()
        (radice / "cartella" / "due.txt").write_text("x\n", encoding="utf-8")
        check("AGGIUNTO in directory", any("AGGIUNTO" in p for p in gate_kit.check("TEST-001", radice)), "no")
        (radice / "cartella" / "due.txt").unlink()

        # senza evidenze il gate non si chiude
        try:
            gate_kit.close("TEST-001", radice)
        except gate_kit.GateError as errore:
            check("close senza evidenze rifiutato", "QA.yaml" in str(errore) and "CodeReview.yaml" in str(errore), str(errore))
        else:
            check("close senza evidenze rifiutato", False, "ha chiuso")

        _evidenze(radice)
        chiusura = gate_kit.close("TEST-001", radice)
        check("close ok", chiusura.get("gate") == "closed", str(chiusura.get("gate")))
        check("sigillo di chiusura", str(chiusura.get("closed_digest", "")).startswith("close_"), str(chiusura.get("closed_digest")))
        check("check dopo la chiusura verifica il sigillo", gate_kit.check("TEST-001", radice) == [], str(gate_kit.check("TEST-001", radice)))
        check("secondo close idempotente", gate_kit.close("TEST-001", radice).get("gate") == "closed")


def test_close_rifiutato_se_mosso() -> None:
    """Con un file mosso e le evidenze presenti, `close` rifiuta e il gate resta aperto."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp))
        _stamp(radice)
        gate_kit.freeze("TEST-001", radice)
        _evidenze(radice)
        (radice / "contratto.txt").write_text("rotto\n", encoding="utf-8")
        try:
            gate_kit.close("TEST-001", radice)
        except gate_kit.GateError as errore:
            check("close rifiutato", "MOSSO" in str(errore) or "mossa" in str(errore), str(errore))
        else:
            check("close rifiutato", False, "ha chiuso")
        check("gate ancora aperto", gate_kit._leggi_yaml(gate_kit.revision_path("TEST-001", radice), "r").get("gate") == "open", "chiuso")


def test_evidenza_di_un_gate_precedente() -> None:
    """Un'evidenza anteriore al congelamento non vale come verdetto di questo gate."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp))
        _stamp(radice)
        gate_kit.freeze("TEST-001", radice)
        _evidenze(radice, vecchie=True)
        try:
            gate_kit.close("TEST-001", radice)
        except gate_kit.GateError as errore:
            check("evidenza vecchia rifiutata", "non e' successiva" in str(errore), str(errore))
        else:
            check("evidenza vecchia rifiutata", False, "ha chiuso")


def test_preflight_obbligatorio() -> None:
    """Senza preflight, con timbro rosso, vecchio, di un altro task o di un altro contract: chiuso."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp))
        try:
            gate_kit.freeze("TEST-001", radice)
        except gate_kit.GateError as errore:
            check("senza preflight: rifiutato", "preflight mancante" in str(errore), str(errore))
        else:
            check("senza preflight: rifiutato", False, "ha aperto")

        _stamp(radice, verde=False)
        try:
            gate_kit.freeze("TEST-001", radice)
        except gate_kit.GateError as errore:
            check("timbro rosso: rifiutato", "ROSSO" in str(errore), str(errore))
        else:
            check("timbro rosso: rifiutato", False, "ha aperto")

        _stamp(radice, minuti=120)
        try:
            gate_kit.freeze("TEST-001", radice)
        except gate_kit.GateError as errore:
            check("timbro vecchio: rifiutato", "vecchio" in str(errore), str(errore))
        else:
            check("timbro vecchio: rifiutato", False, "ha aperto")

        _stamp(radice, task_id="ALTRO-999")
        try:
            gate_kit.freeze("TEST-001", radice)
        except gate_kit.GateError as errore:
            check("timbro di un altro task: rifiutato", "altro task" in str(errore), str(errore))
        else:
            check("timbro di un altro task: rifiutato", False, "ha aperto")

        _stamp(radice, contract_sha="0" * 64)
        try:
            gate_kit.freeze("TEST-001", radice)
        except gate_kit.GateError as errore:
            check("contract cambiato dopo il preflight: rifiutato", "cambiato" in str(errore), str(errore))
        else:
            check("contract cambiato dopo il preflight: rifiutato", False, "ha aperto")


def test_preflight_go_no_go() -> None:
    """Il preflight reale: GO con i comandi verdi, NO-GO con un comando rosso."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp))
        _stub_preflight(radice)
        check("preflight GO esce 0", gate_kit.preflight("TEST-001", root=radice) == 0, "no")
        timbro = json.loads(gate_kit.preflight_path("TEST-001", radice).read_text(encoding="utf-8"))
        check("timbro verde e legato al contract", timbro.get("verde") is True and timbro.get("contract_sha") == gate_kit._sha_contract("TEST-001", radice), str(timbro))
        _stub_preflight(radice, rosso=True)
        check("preflight NO-GO esce 1", gate_kit.preflight("TEST-001", root=radice) == 1, "no")


def test_identita_della_revisione() -> None:
    """La revisione di un altro task, copiata, non chiude questo gate."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp))
        _macchina(radice, task="ALTRO-001")
        _stamp(radice, task="ALTRO-001")
        dati_altro = gate_kit.freeze("ALTRO-001", radice)
        check("l'altro freeze e' andato", dati_altro.get("gate") == "open", str(dati_altro.get("gate")))
        gate_kit.revision_path("TEST-001", radice).write_text(
            gate_kit.revision_path("ALTRO-001", radice).read_text(encoding="utf-8"), encoding="utf-8"
        )
        problemi = gate_kit.check("TEST-001", radice)
        check("identita': check rifiuta", any("IDENTITA" in p for p in problemi), str(problemi))
        try:
            gate_kit.close("TEST-001", radice)
        except gate_kit.GateError as errore:
            check("identita': close rifiuta", "IDENTITA" in str(errore) or "mossa" in str(errore), str(errore))
        else:
            check("identita': close rifiuta", False, "ha chiuso")


def test_write_scope_confinato() -> None:
    """Assoluti, '..', symlink fuori, voce scalare: rifiutati, non letti."""
    casi = [
        (["/etc/hostname"], "assoluto"),
        ([".."], "fuori dalla macchina"),
        ("contratto.txt", "non e' una lista"),
        ([123], "non stringa"),
    ]
    for scope, atteso in casi:
        with tempfile.TemporaryDirectory() as tmp:
            radice = _macchina(Path(tmp), scope=scope)
            _stamp(radice)
            try:
                gate_kit.freeze("TEST-001", radice)
            except gate_kit.GateError as errore:
                check(f"scope {atteso}: rifiutato", atteso in str(errore), str(errore))
            else:
                check(f"scope {atteso}: rifiutato", False, "ha aperto")


def test_symlink_che_esce() -> None:
    """Un symlink nel write_scope che porta fuori dalla macchina e' un rifiuto."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp), scope=["link-esterno"])
        (radice / "link-esterno").symlink_to("/etc/hostname")
        _stamp(radice)
        try:
            gate_kit.freeze("TEST-001", radice)
        except gate_kit.GateError as errore:
            check("symlink esterno: rifiutato", "fuori dalla macchina" in str(errore), str(errore))
        else:
            check("symlink esterno: rifiutato", False, "ha aperto")


def test_registro_delle_revisioni() -> None:
    """Cancellare una revisione chiusa non fa ripartire da R1: il registro lo impedisce."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp))
        _stamp(radice)
        gate_kit.freeze("TEST-001", radice)
        _evidenze(radice)
        gate_kit.close("TEST-001", radice)
        gate_kit.revision_path("TEST-001", radice).unlink()
        _stamp(radice)
        try:
            gate_kit.freeze("TEST-001", radice)
        except gate_kit.GateError as errore:
            check("revisione sparita: rifiutato", "sparita" in str(errore), str(errore))
        else:
            check("revisione sparita: rifiutato", False, "ha ripartito da R1")


def test_chiusura_a_mano_non_regge() -> None:
    """Un `gate: closed` scritto a mano non ha il sigillo di chiusura: il validatore blocca."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp), stato="closed")
        _stamp(radice)
        # congelo con il contract attivo, poi lo chiudo e forzo gate: closed a mano
        originale = _contratto(radice, "TEST-001").read_text(encoding="utf-8")
        _contratto(radice, "TEST-001").write_text(originale.replace("status: closed", "status: active"), encoding="utf-8")
        _stamp(radice)
        gate_kit.freeze("TEST-001", radice)
        percorso = gate_kit.revision_path("TEST-001", radice)
        dati = yaml.safe_load(percorso.read_text(encoding="utf-8"))
        dati["gate"] = "closed"  # a mano, senza close: nessun sigillo di chiusura
        percorso.write_text(yaml.safe_dump(dati, sort_keys=False), encoding="utf-8")
        # e il contract viene chiuso a mano: la chiusura prematura come la vede `scan`
        _contratto(radice, "TEST-001").write_text(originale, encoding="utf-8")
        contratto = {"task_id": "TEST-001", "status": "closed"}
        codici = [f.code for f in ad_contract.validate(contratto, ad_registry.load(), root=radice)]
        check("chiusura a mano: bloccata", "gate-aperto" in codici, str(codici))
        check("scan la vede", bool(gate_kit.scan(radice)), str(gate_kit.scan(radice)))


def test_revisione_malformata() -> None:
    """Campi malformati: GateError con la ragione, non traceback."""
    casi = [
        {"files": ["x"], "expected": [], "dirs": {}, "revision": "R1", "task_id": "TEST-001"},
        {"files": {}, "expected": 5, "dirs": {}, "revision": "R1", "task_id": "TEST-001"},
        {"files": {}, "expected": [], "dirs": "x", "revision": "R1", "task_id": "TEST-001"},
        {"files": {}, "expected": [], "dirs": {}, "revision": "R2x", "task_id": "TEST-001"},
    ]
    for dati in casi:
        with tempfile.TemporaryDirectory() as tmp:
            radice = _macchina(Path(tmp))
            gate_kit.revision_path("TEST-001", radice).write_text(yaml.safe_dump(dati), encoding="utf-8")
            try:
                gate_kit.check("TEST-001", radice)
            except gate_kit.GateError:
                check(f"malformata {list(dati)[0]}: GateError", True)
            except Exception as errore:  # noqa: BLE001
                check(f"malformata {list(dati)[0]}: GateError", False, f"{errore.__class__.__name__}")
            else:
                check(f"malformata {list(dati)[0]}: GateError", False, "nessuna eccezione")


def test_sigillo() -> None:
    """Riscrivere a mano le impronte senza ricalcolare il sigillo si vede."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp))
        _stamp(radice)
        gate_kit.freeze("TEST-001", radice)
        percorso = gate_kit.revision_path("TEST-001", radice)
        dati = yaml.safe_load(percorso.read_text(encoding="utf-8"))
        (radice / "contratto.txt").write_text("alterato\n", encoding="utf-8")
        dati["files"]["contratto.txt"] = "0" * 64
        percorso.write_text(yaml.safe_dump(dati, sort_keys=False), encoding="utf-8")
        check("sigillo non combacia", any("SIGILLO" in p for p in gate_kit.check("TEST-001", radice)), "no")


def test_task_non_e_un_percorso() -> None:
    """Un task_id con percorsi e' rifiutato."""
    for brutto in ("../contratti/societa/T", "a/b", "..", ""):
        try:
            gate_kit.valida_task(brutto)
        except gate_kit.GateError:
            check(f"task {brutto!r} rifiutato", True)
        else:
            check(f"task {brutto!r} rifiutato", False, "accettato")


def test_contract_chiuso_non_si_congela() -> None:
    """Un gate su un contract gia' chiuso non si apre."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp), stato="closed")
        _stamp(radice)
        try:
            gate_kit.freeze("TEST-001", radice)
        except gate_kit.GateError as errore:
            check("gate su contract chiuso rifiutato", "active" in str(errore), str(errore))
        else:
            check("gate su contract chiuso rifiutato", False, "ha aperto")


def test_brief_ermetico() -> None:
    """Il brief legge i registri e non mostra l'evidenza dell'altro ruolo."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp))
        (radice / "drift" / "README.md").write_text(
            "## DRIFT-001 — uno\n| **Stato** | OPEN |\n## DRIFT-002 — due\n| **Stato** | FIXED |\n",
            encoding="utf-8",
        )
        (radice / "errori" / "ERR-0001.yaml").write_text("id: ERR-0001\ndiventa: controllo\n", encoding="utf-8")
        (radice / "evidenze" / "TEST-001-QA.yaml").write_text("outcome: PASS\nproducer: qa\n", encoding="utf-8")
        (radice / "evidenze" / "TEST-001-CodeReview.yaml").write_text("outcome: FAIL\nproducer: review\n", encoding="utf-8")
        qa = gate_kit.brief("TEST-001", "qa", root=radice)
        review = gate_kit.brief("TEST-001", "review", root=radice)
    check("brief QA: scatola nera", "scatola nera" in qa, qa[:200])
    check("brief review: legge il codice", "leggi il codice" in review, review[:200])
    check("brief QA non mostra Code Review", "CodeReview" not in qa, "mostra l'altro")
    check("brief review non mostra QA", "TEST-001-QA.yaml" not in review, "mostra l'altro")
    check("divergenze aperte: solo le OPEN", "divergenze aperte: 1 su 2" in qa, qa[qa.find("Registri"):qa.find("Registri") + 220])
    check("cicatrici con la lezione", "ERR-0001: diventa controllo" in qa, "no")
    try:
        gate_kit.brief("TEST-001", "altro", root=radice)
    except gate_kit.GateError:
        check("ruolo sconosciuto rifiutato", True)
    else:
        check("ruolo sconosciuto rifiutato", False, "accettato")


def test_catalogo() -> None:
    """Almeno 8 classi, ognuna con nome, cerca e prova."""
    check("almeno 8 classi", len(gate_kit.ATTACCHI) >= 8, str(len(gate_kit.ATTACCHI)))
    for attacco in gate_kit.ATTACCHI:
        check(f"{attacco.get('nome')}: campi", {"nome", "cerca", "prova"} <= set(attacco), str(attacco))


def test_cli() -> None:
    """La CLI: rifiuti corretti, nessun crash."""
    def _cli(*argomenti: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(ROOT / "tests" / "gate_kit.py"), *argomenti],
            capture_output=True, text=True, cwd=str(ROOT),
        )

    ignoto = _cli("check", "NON-ESISTE")
    check("check task inesistente: exit 1", ignoto.returncode == 1, str(ignoto.returncode))
    senza_ruolo = _cli("brief", "ENG-009")
    check("brief senza --role: exit 2", senza_ruolo.returncode == 2, str(senza_ruolo.returncode))
    attacchi = _cli("attacks")
    check("attacks esce 0", attacchi.returncode == 0, attacchi.stderr[:150])
    check("attacks mostra la prova", "prova:" in attacchi.stdout, attacchi.stdout[:150])
    scan = _cli("scan")
    check("scan esce 0 su macchina sana", scan.returncode == 0, scan.stdout[:200])


def test_gate_obbligatorio() -> None:
    """Una revisione senza stato valido del gate non si chiude."""
    for valore in (None, "", "boh"):
        with tempfile.TemporaryDirectory() as tmp:
            radice = _macchina(Path(tmp))
            _stamp(radice)
            dati = gate_kit.freeze("TEST-001", radice)
            percorso = gate_kit.revision_path("TEST-001", radice)
            grezza = yaml.safe_load(percorso.read_text(encoding="utf-8"))
            if valore is None:
                grezza.pop("gate")
            else:
                grezza["gate"] = valore
            percorso.write_text(yaml.safe_dump(grezza, sort_keys=False), encoding="utf-8")
            check(f"gate {valore!r}: check lo segnala", any("GATE" in p for p in gate_kit.check("TEST-001", radice)), str(gate_kit.check("TEST-001", radice)))
            _evidenze(radice)
            try:
                gate_kit.close("TEST-001", radice)
            except gate_kit.GateError:
                check(f"gate {valore!r}: close rifiuta", True)
            else:
                check(f"gate {valore!r}: close rifiuta", False, "ha chiuso")


def test_evidenze_identita_e_vuotezza() -> None:
    """Un'evidenza vuota o di un altro task non certifica questo gate."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp))
        _stamp(radice)
        gate_kit.freeze("TEST-001", radice)
        for nome in ("TEST-001-QA.yaml", "TEST-001-CodeReview.yaml"):
            (radice / "evidenze" / nome).write_text("", encoding="utf-8")
        try:
            gate_kit.close("TEST-001", radice)
        except gate_kit.GateError as errore:
            check("evidenze vuote: rifiutate", "vuota" in str(errore), str(errore))
        else:
            check("evidenze vuote: rifiutate", False, "ha chiuso")

        for nome in ("TEST-001-QA.yaml", "TEST-001-CodeReview.yaml"):
            (radice / "evidenze" / nome).write_text(
                "schema: 2\ntask_id: ALTRO-999\noutcome: PASS\n", encoding="utf-8"
            )
        try:
            gate_kit.close("TEST-001", radice)
        except gate_kit.GateError as errore:
            check("evidenze di un altro task: rifiutate", "altro task" in str(errore), str(errore))
        else:
            check("evidenze di un altro task: rifiutate", False, "ha chiuso")


def test_validatore_confinato() -> None:
    """Il validatore rifiuta write_scope assoluti, '..', null, vuoti e non ASCII."""
    casi = [
        (["/etc/passwd"], "write-scope-assoluto"),
        (["../evil.txt"], "write-scope-traversal"),
        (["tests/../../evil.txt"], "write-scope-traversal"),
        ([None], "write-scope-voce-non-stringa"),
        ([""], "write-scope-vuota"),
        (["pròva.txt"], "write-scope-non-ascii"),
        (None, "write-scope-non-lista"),
    ]
    for scope, codice in casi:
        contratto = {"task_id": "TEST-009", "status": "active", "domain": "technical",
                     "agent": "platform", "task_type": "shared_platform", "product": "altro",
                     "write_scope": scope}
        codici = [f.code for f in ad_contract.validate(contratto, ad_registry.load())]
        check(f"validatore scope {scope!r}: {codice}", codice in codici, str(codici))


def test_percorso_lunghissimo_e_non_ascii() -> None:
    """Un percorso da 1000 caratteri o non ASCII e' un rifiuto, non un traceback."""
    for scope, atteso in (([("a" * 1000)], "troppo lungo"), (["pròva.txt"], "non ASCII")):
        with tempfile.TemporaryDirectory() as tmp:
            radice = _macchina(Path(tmp), scope=scope)
            _stamp(radice)
            try:
                gate_kit.freeze("TEST-001", radice)
            except gate_kit.GateError as errore:
                check(f"scope {atteso}: rifiutato", atteso in str(errore), str(errore))
            except Exception as errore:  # noqa: BLE001
                check(f"scope {atteso}: rifiutato", False, f"{errore.__class__.__name__}")
            else:
                check(f"scope {atteso}: rifiutato", False, "ha aperto")


def test_sottodirectory() -> None:
    """Una directory vuota aggiunta dentro una sorvegliata e' un movimento."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp), scope=["cartella"])
        _stamp(radice)
        gate_kit.freeze("TEST-001", radice)
        (radice / "cartella" / "vuota").mkdir()
        check("directory aggiunta rilevata", any("AGGIUNTA la directory" in p for p in gate_kit.check("TEST-001", radice)), str(gate_kit.check("TEST-001", radice)))


def test_evidenza_modificata_dopo_la_chiusura() -> None:
    """Dopo la chiusura, un'evidenza modificata si vede."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp))
        _stamp(radice)
        gate_kit.freeze("TEST-001", radice)
        _evidenze(radice)
        gate_kit.close("TEST-001", radice)
        (radice / "evidenze" / "TEST-001-QA.yaml").write_text(
            "schema: 2\ntask_id: TEST-001\noutcome: FAIL\n", encoding="utf-8"
        )
        problemi = gate_kit.check("TEST-001", radice)
        check("evidenza modificata: rilevata", any("EVIDENZA MODIFICATA" in p for p in problemi), str(problemi))


def test_timbro_rosso() -> None:
    """Un timbro rosso dice ROSSO, non 'contract cambiato'."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp))
        gate_kit.preflight_path("TEST-001", radice).write_text(
            json.dumps({"task_id": "TEST-001", "verde": False, "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}),
            encoding="utf-8",
        )
        try:
            gate_kit.freeze("TEST-001", radice)
        except gate_kit.GateError as errore:
            check("timbro rosso: messaggio giusto", "ROSSO" in str(errore), str(errore))
        else:
            check("timbro rosso: messaggio giusto", False, "ha aperto")


def test_ledger_r2() -> None:
    """Dopo una chiusura, il freeze successivo e' R2 e aggiorna il registro."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp))
        _stamp(radice)
        gate_kit.freeze("TEST-001", radice)
        _evidenze(radice)
        gate_kit.close("TEST-001", radice)
        _stamp(radice)
        dati = gate_kit.freeze("TEST-001", radice)
        check("seconda revisione e' R2", dati.get("revision") == "R2", str(dati.get("revision")))
        ledger = yaml.safe_load((radice / gate_kit.LEDGER_REL).read_text(encoding="utf-8"))
        check("il registro ha due revisioni", len(ledger["tasks"]["TEST-001"]) == 2, str(ledger))


def test_marcatore_sigillato() -> None:
    """Togliere il marcatore 'tool' rompe il sigillo: non c'e' declassamento silenzioso."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp))
        _stamp(radice)
        gate_kit.freeze("TEST-001", radice)
        percorso = gate_kit.revision_path("TEST-001", radice)
        dati = yaml.safe_load(percorso.read_text(encoding="utf-8"))
        dati.pop("tool")
        percorso.write_text(yaml.safe_dump(dati, sort_keys=False), encoding="utf-8")
        check("marcatore rimosso: sigillo rotto", any("SIGILLO" in p for p in gate_kit.check("TEST-001", radice)), str(gate_kit.check("TEST-001", radice)))



def test_coerenza_sigilli() -> None:
    """Una sola formula, e anche il SIGILLO DI CHIUSURA: revisione costruita in scratch.

    E' il test che avrebbe preso ERR-0059: se le due formule divergono, qui si vede.
    Non dipende dal workspace: la revisione e' costruita nel test (ERR-0060).
    """
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp), stato="closed")
        originale = _contratto(radice, "TEST-001").read_text(encoding="utf-8")
        _contratto(radice, "TEST-001").write_text(originale.replace("status: closed", "status: active"), encoding="utf-8")
        _stamp(radice)
        gate_kit.freeze("TEST-001", radice)
        _evidenze(radice)
        gate_kit.close("TEST-001", radice)
        congelata = yaml.safe_load(gate_kit.revision_path("TEST-001", radice).read_text(encoding="utf-8"))
        # revisione: kit == validatore == valore scritto
        check("sigillo revisione: kit == validatore", gate_kit._digest(congelata) == ad_contract.digest_revisione(congelata))
        check("sigillo revisione: scritto == ricalcolato", congelata.get("digest") == ad_contract.digest_revisione(congelata))
        # chiusura: idem, e il validatore la accetta davvero
        check("sigillo chiusura: kit == validatore", gate_kit._closed_digest(congelata) == ad_contract.digest_chiusura(congelata))
        check("sigillo chiusura: scritto == ricalcolato", congelata.get("closed_digest") == ad_contract.digest_chiusura(congelata))
        contratto = {"task_id": "TEST-001", "status": "closed"}
        check("la chiusura e' valida per il validatore", ad_contract.gate_status(contratto, radice) == (None, ""), str(ad_contract.gate_status(contratto, radice)))

def test_chiusura_end_to_end() -> None:
    """freeze -> close -> contract chiuso -> il validatore PASSA e scan e' pulito."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp), stato="closed")
        originale = _contratto(radice, "TEST-001").read_text(encoding="utf-8")
        _contratto(radice, "TEST-001").write_text(originale.replace("status: closed", "status: active"), encoding="utf-8")
        _stamp(radice)
        gate_kit.freeze("TEST-001", radice)
        _evidenze(radice)
        gate_kit.close("TEST-001", radice)
        _contratto(radice, "TEST-001").write_text(originale, encoding="utf-8")
        contratto = {"task_id": "TEST-001", "status": "closed", "domain": "technical",
                     "agent": "platform", "task_type": "shared_platform", "product": "altro"}
        codici = [f.code for f in ad_contract.validate(contratto, ad_registry.load(), root=radice)]
        check("validatore: nessuna violazione di gate", "gate-aperto" not in codici, str(codici))
        check("gate_status pulito dopo la chiusura", ad_contract.gate_status(contratto, radice) == (None, ""), str(ad_contract.gate_status(contratto, radice)))
        check("scan pulito", gate_kit.scan(radice) == [], str(gate_kit.scan(radice)))


def test_utf8_invalido() -> None:
    """UTF-8 invalido in revisione, timbro o contract: GateError, mai traceback."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp))
        gate_kit.revision_path("TEST-001", radice).write_bytes(b"\xff\xfe\x00bad")
        try:
            gate_kit.check("TEST-001", radice)
        except gate_kit.GateError as errore:
            check("revisione non UTF-8: GateError", "UTF-8" in str(errore), str(errore))
        except UnicodeDecodeError as errore:
            check("revisione non UTF-8: GateError", False, f"UnicodeDecodeError: {errore}")
        else:
            check("revisione non UTF-8: GateError", False, "nessuna eccezione")

    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp))
        gate_kit.preflight_path("TEST-001", radice).write_bytes(b"\xff\xfe")
        try:
            gate_kit._controlla_preflight("TEST-001", radice)
        except gate_kit.GateError as errore:
            check("timbro non UTF-8: GateError", "UTF-8" in str(errore), str(errore))
        except UnicodeDecodeError as errore:
            check("timbro non UTF-8: GateError", False, f"UnicodeDecodeError: {errore}")
        else:
            check("timbro non UTF-8: GateError", False, "nessuna eccezione")

    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp))
        _contratto(radice, "TEST-001").write_bytes(b"\xff\xfe")
        try:
            gate_kit.contract_path("TEST-001", radice)
        except gate_kit.GateError as errore:
            check("contract non UTF-8: GateError", "UTF-8" in str(errore), str(errore))
        except UnicodeDecodeError as errore:
            check("contract non UTF-8: GateError", False, f"UnicodeDecodeError: {errore}")
        else:
            check("contract non UTF-8: GateError", False, "nessuna eccezione")


def test_ruolo_dell_evidenza() -> None:
    """L'evidenza del QA copiata sopra quella del Code Review non chiude il gate."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp))
        _stamp(radice)
        gate_kit.freeze("TEST-001", radice)
        _evidenze(radice)
        (radice / "evidenze" / "TEST-001-CodeReview.yaml").write_text(
            (radice / "evidenze" / "TEST-001-QA.yaml").read_text(encoding="utf-8"), encoding="utf-8"
        )
        try:
            gate_kit.close("TEST-001", radice)
        except gate_kit.GateError as errore:
            check("ruolo sbagliato: rifiutato", "ruolo" in str(errore), str(errore))
        else:
            check("ruolo sbagliato: rifiutato", False, "ha chiuso")


def test_pycache() -> None:
    """Il filtro `__pycache__` e' davvero escluso: cancellare un .pyc non e' un movimento.

    Se il filtro sparisse da freeze o da check, questo test diventerebbe rosso.
    """
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp), scope=["cartella"])
        (radice / "cartella" / "__pycache__").mkdir()
        (radice / "cartella" / "__pycache__" / "x.pyc").write_bytes(b"x")
        (radice / "cartella" / "modulo.pyc").write_bytes(b"y")
        _stamp(radice)
        dati = gate_kit.freeze("TEST-001", radice)
        check("pycache: non e' tra i file congelati", not any("__pycache__" in f for f in dati["files"]), str(list(dati["files"])))
        (radice / "cartella" / "__pycache__" / "x.pyc").unlink()
        check("pycache: cancella un .pyc = nessun movimento", gate_kit.check("TEST-001", radice) == [], str(gate_kit.check("TEST-001", radice)))


def test_contract_ombra() -> None:
    """Due contract con lo stesso task: rifiuto, non scelta silenziosa."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp))
        ombra = radice / "contratti" / "aaa"
        ombra.mkdir(parents=True)
        (ombra / "TEST-001.yaml").write_text("task_id: TEST-001\nstatus: active\nwrite_scope:\n  - contratto.txt\n", encoding="utf-8")
        try:
            gate_kit.contract_path("TEST-001", radice)
        except gate_kit.GateError as errore:
            check("contract ombra: rifiutato", "piu' di un contract" in str(errore), str(errore))
        else:
            check("contract ombra: rifiutato", False, "ha scelto un contract")


def test_registro_incoerente() -> None:
    """Se il registro sparisce dopo il freeze, il gate non si chiude in silenzio."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp))
        _stamp(radice)
        gate_kit.freeze("TEST-001", radice)
        _evidenze(radice)
        (radice / gate_kit.LEDGER_REL).unlink()
        try:
            gate_kit.close("TEST-001", radice)
        except gate_kit.GateError as errore:
            check("registro sparito: close rifiutato", "registro" in str(errore).lower(), str(errore))
        else:
            check("registro sparito: close rifiutato", False, "ha chiuso")
        dati = yaml.safe_load(gate_kit.revision_path("TEST-001", radice).read_text(encoding="utf-8"))
        check("il rifiuto non chiude la revisione", dati.get("gate") == "open", str(dati.get("gate")))



def test_timbro_senza_sha() -> None:
    """Un timbro senza l'impronta del contract non apre il gate (fail-closed)."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp))
        gate_kit.preflight_path("TEST-001", radice).write_text(
            json.dumps({"task_id": "TEST-001", "verde": True,
                        "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}),
            encoding="utf-8",
        )
        try:
            gate_kit.freeze("TEST-001", radice)
        except gate_kit.GateError as errore:
            check("timbro senza sha: rifiutato", "impronta" in str(errore) or "cambiato" in str(errore), str(errore))
        else:
            check("timbro senza sha: rifiutato", False, "ha aperto")


def test_evidenze_in_verifica() -> None:
    """La regola delle due evidenze vale anche nella verifica, non solo nel close."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp), stato="closed")
        originale = _contratto(radice, "TEST-001").read_text(encoding="utf-8")
        _contratto(radice, "TEST-001").write_text(originale.replace("status: closed", "status: active"), encoding="utf-8")
        _stamp(radice)
        gate_kit.freeze("TEST-001", radice)
        _evidenze(radice)
        gate_kit.close("TEST-001", radice)
        percorso = gate_kit.revision_path("TEST-001", radice)
        dati = yaml.safe_load(percorso.read_text(encoding="utf-8"))
        dati["evidenze"] = {}
        percorso.write_text(yaml.safe_dump(dati, sort_keys=False), encoding="utf-8")
        contratto = {"task_id": "TEST-001", "status": "closed"}
        codice, messaggio = ad_contract.gate_status(contratto, radice)
        check("evidenze mancanti in verifica: blocco", codice == "block" and "ENTRAMBE" in messaggio, str((codice, messaggio)))


def test_evidenze_malformate_in_verifica() -> None:
    """Una revisione chiusa con 'evidenze' malformata non fa crashare la verifica."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp), stato="closed")
        revisione = {
            "tool": "gate_kit", "task_id": "TEST-001", "revision": "R1",
            "frozen_at": "2026-10-19T10:00:00+00:00", "gate": "closed",
            "closed_at": "2026-10-19T10:00:00+00:00", "files": {}, "expected": [],
            "dirs": {}, "subdirs": {}, "digest": "x", "closed_digest": "y", "evidenze": ["x"],
        }
        gate_kit.revision_path("TEST-001", radice).write_text(yaml.safe_dump(revisione), encoding="utf-8")
        contratto = {"task_id": "TEST-001", "status": "closed"}
        try:
            codice, messaggio = ad_contract.gate_status(contratto, radice)
        except AttributeError as errore:
            check("evidenze malformate: nessun crash", False, f"AttributeError: {errore}")
        else:
            check("evidenze malformate: blocco o avviso, non crash", codice in ("block", "warn", None), str((codice, messaggio)))


def test_perimetro_nel_brief() -> None:
    """Il brief dichiara il perimetro: dentro = FAIL, fuori = backlog (DEC-0064)."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp))
        testo = gate_kit.brief("TEST-001", "qa", root=radice)
    check("brief: sezione perimetro", "Perimetro" in testo, testo[:200])
    check("brief: distingue dentro/fuori", "Fuori perimetro" in testo and "Dentro il perimetro" in testo, "no")
    check("brief: il dolo e' fuori perimetro", "dolo" in testo or "riscrivere deliberatamente" in testo, "no")



def test_registro_fermo_alla_revisione_precedente() -> None:
    """Un registro che conosce solo la revisione precedente non chiude quella in corso."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp))
        _stamp(radice)
        gate_kit.freeze("TEST-001", radice)
        _evidenze(radice)
        gate_kit.close("TEST-001", radice)
        # nuova revisione R2, ma il registro torna indietro a R1
        _stamp(radice)
        gate_kit.freeze("TEST-001", radice)
        ledger = yaml.safe_load((radice / gate_kit.LEDGER_REL).read_text(encoding="utf-8"))
        ledger["tasks"]["TEST-001"] = ledger["tasks"]["TEST-001"][:1]
        (radice / gate_kit.LEDGER_REL).write_text(yaml.safe_dump(ledger), encoding="utf-8")
        (radice / "evidenze" / "TEST-001-QA.yaml").unlink()
        (radice / "evidenze" / "TEST-001-CodeReview.yaml").unlink()
        _evidenze(radice)
        try:
            gate_kit.close("TEST-001", radice)
        except gate_kit.GateError as errore:
            check("registro fermo: rifiutato", "scollegata" in str(errore) or "fermo" in str(errore), str(errore))
        else:
            check("registro fermo: rifiutato", False, "ha chiuso")

def test_brief_registri_malformati() -> None:
    """Un registro malformato non fa crashare il brief."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp))
        (radice / "evidenze" / "incognite.yaml").write_bytes(b"\xff\xfe\x00")
        try:
            testo = gate_kit.brief("TEST-001", "qa", root=radice)
        except Exception as errore:  # noqa: BLE001
            check("brief: incognite non-UTF8 senza traceback", False, errore.__class__.__name__)
        else:
            check("brief: incognite non-UTF8 senza traceback", True)
            check("brief: avvisa il registro rotto", "AVVISO registri" in testo, testo[:200])

def test_timestamp_yaml() -> None:
    """frozen_at letto da YAML come datetime non fa crashare (normalizzato)."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp))
        _stamp(radice)
        gate_kit.freeze("TEST-001", radice)
        percorso = gate_kit.revision_path("TEST-001", radice)
        testo = percorso.read_text(encoding="utf-8").replace("frozen_at: '", "frozen_at: ")
        percorso.write_text(testo, encoding="utf-8")
        try:
            gate_kit.check("TEST-001", radice)
        except TypeError as errore:
            check("timestamp YAML: nessun TypeError", False, str(errore))
        else:
            check("timestamp YAML: nessun TypeError", True)

def test_contract_yml() -> None:
    """Un contract `.yml` e' visto come un `.yaml`."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = Path(tmp)
        (radice / "contratti" / "societa").mkdir(parents=True)
        (radice / "contratti" / "societa" / "TEST-009.yml").write_text(
            "task_id: TEST-009\nstatus: active\nwrite_scope:\n  - x.txt\n", encoding="utf-8")
        trovato = gate_kit.contract_path("TEST-009", radice)
        check("contract .yml trovato", trovato is not None and trovato.suffix == ".yml", str(trovato))

def test_budget_non_mappa() -> None:
    """Un budget scalare e' una violazione del validatore, non un traceback."""
    contratto = {"task_id": "T", "status": "active", "domain": "technical", "agent": "platform",
                 "task_type": "shared_platform", "product": "altro", "write_scope": [],
                 "budget": "due"}
    try:
        codici = [f.code for f in ad_contract.validate(contratto, ad_registry.load())]
    except Exception as errore:  # noqa: BLE001
        check("budget scalare: nessun traceback", False, errore.__class__.__name__)
    else:
        check("budget scalare: violazione", "budget-non-mappa" in codici, str(codici))


def test_brief_errori_malformati() -> None:
    """Anche `errori/*.yaml` malformati o annidati non fanno crashare il brief (ENG-013)."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp))
        (radice / "errori" / "ERR-9001-bad.yaml").write_bytes(b"\xff\xfe")
        (radice / "errori" / "ERR-9002-bad.yaml").write_text("[[[\n", encoding="utf-8")
        try:
            testo = gate_kit.brief("TEST-001", "qa", root=radice)
        except Exception as errore:  # noqa: BLE001
            check("errori malformati: nessun traceback", False, errore.__class__.__name__)
        else:
            check("errori malformati: nessun traceback", True)
            check("errori malformati: avviso nel brief", "AVVISO registri" in testo, testo[:300])

    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp))
        annidato = "a:\n" + "  " * 2000 + "b: 1\n"
        (radice / "evidenze" / "incognite.yaml").write_text(annidato, encoding="utf-8")
        try:
            gate_kit.brief("TEST-001", "qa", root=radice)
        except RecursionError as errore:
            check("incognite annidate: nessun RecursionError", False, str(errore))
        except Exception:  # noqa: BLE001
            check("incognite annidate: nessun RecursionError", True)
        else:
            check("incognite annidate: nessun RecursionError", True)


def test_errori_fuori_dagli_ultimi_cinque() -> None:
    """Un errore malformato fuori dagli ultimi 5 non sparisce in silenzio."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp))
        (radice / "errori" / "ERR-0001-bad.yaml").write_bytes(b"\xff")
        for indice in range(2, 7):
            (radice / "errori" / f"ERR-{indice:04d}-ok.yaml").write_text(
                f"id: ERR-{indice:04d}\ndiventa: nota\n", encoding="utf-8")
        try:
            testo = gate_kit.brief("TEST-001", "qa", root=radice)
        except Exception as errore:  # noqa: BLE001
            check("errore fuori dagli ultimi 5: nessun crash", False, errore.__class__.__name__)
        else:
            check("errore fuori dagli ultimi 5: avviso", "AVVISO registri" in testo, testo[:300])



def test_prompt_senza_percorsi() -> None:
    """La prompt del revisore la genera il codice e non contiene percorsi (ERR-0064)."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp))
        for ruolo, atteso in (("qa", "scatola nera"), ("review", "leggi il codice")):
            prompt = gate_kit.prompt_revisore("TEST-001", ruolo, root=radice)
            brief = gate_kit.brief("TEST-001", ruolo, root=radice)
            check(f"prompt {ruolo}: niente radice", str(gate_kit.ROOT) not in prompt, "contiene la radice")
            check(f"prompt {ruolo}: niente radice scratch", str(radice) not in prompt, "contiene la radice scratch")
            check(f"prompt {ruolo}: niente MACCHINA", "MACCHINA:" not in prompt, "contiene MACCHINA:")
            check(f"prompt {ruolo}: niente radice nel brief", str(gate_kit.ROOT) not in brief, "brief con radice")
            check(f"prompt {ruolo}: perimetro", "Dentro il perimetro" in prompt and "Fuori perimetro" in prompt, "manca il perimetro")
            check(f"prompt {ruolo}: metodo", atteso in prompt, prompt[:200])
            check(f"prompt {ruolo}: nomina il task", "TEST-001" in prompt, prompt[:200])
            check(f"prompt {ruolo}: comando del brief", "gate_kit.py brief TEST-001" in prompt, prompt[:300])
            check(f"prompt {ruolo}: file dell'evidenza", f"evidenze/TEST-001-" in prompt, prompt[:300])
            check(f"prompt {ruolo}: niente 'cd '", "cd " not in prompt, "contiene un cd")
    try:
        gate_kit.prompt_revisore("TEST-001", "altro")
    except gate_kit.GateError:
        check("prompt: ruolo sconosciuto rifiutato", True)
    else:
        check("prompt: ruolo sconosciuto rifiutato", False, "accettato")



def test_criteri_malformati() -> None:
    """Un `acceptance_criteria` non-lista e' un rifiuto, non un traceback (ENG-014)."""
    for valore in ("42", "due", "true"):
        with tempfile.TemporaryDirectory() as tmp:
            radice = _macchina(Path(tmp))
            percorso = _contratto(radice, "TEST-001")
            testo = percorso.read_text(encoding="utf-8").replace(
                "acceptance_criteria:\n  - 'criterio uno'",
                f"acceptance_criteria: {valore}",
            )
            percorso.write_text(testo, encoding="utf-8")
            _stamp(radice)
            try:
                gate_kit.brief("TEST-001", "qa", root=radice)
            except gate_kit.GateError as errore:
                check(f"criteri {valore}: GateError", "acceptance_criteria" in str(errore), str(errore))
            except TypeError as errore:
                check(f"criteri {valore}: GateError", False, f"TypeError: {errore}")
            else:
                check(f"criteri {valore}: GateError", False, "nessun rifiuto")


def test_evidenza_debole_rifiutata() -> None:
    """Un'evidenza senza i campi dello schema 2 non chiude il gate (ENG-014)."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp))
        _stamp(radice)
        gate_kit.freeze("TEST-001", radice)
        for suffisso in ("QA", "CodeReview"):
            (radice / "evidenze" / f"TEST-001-{suffisso}.yaml").write_text(
                f"schema: 2\ntask_id: TEST-001\ngate: {suffisso}\noutcome: PASS\nproducer: {suffisso.lower()}\n",
                encoding="utf-8",
            )
        try:
            gate_kit.close("TEST-001", radice)
        except gate_kit.GateError as errore:
            check("evidenza debole: rifiutata", "schema 2" in str(errore), str(errore))
        else:
            check("evidenza debole: rifiutata", False, "ha chiuso")


def test_prompt_task_inesistente() -> None:
    """La prompt di un task senza contract e' un rifiuto (ENG-014)."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp))
        try:
            gate_kit.prompt_revisore("NON-ESISTE", "qa", root=radice)
        except gate_kit.GateError:
            check("prompt: task inesistente rifiutato", True)
        else:
            check("prompt: task inesistente rifiutato", False, "ha generato la prompt")


def test_brief_termine_come_qa() -> None:
    """Un task_id che contiene 'QA' non nasconde la propria evidenza (ENG-014)."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp), task="QA-001")
        (radice / "evidenze" / "QA-001-CodeReview.yaml").write_text(
            "schema: 2\ntask_id: QA-001\ngate: Code Review\noutcome: FAIL\nproducer: review\n",
            encoding="utf-8",
        )
        testo = gate_kit.brief("QA-001", "review", root=radice)
        check("task con QA: la propria evidenza c'e'", "QA-001-CodeReview.yaml" in testo, testo[-400:])



def main() -> int:
    """Run the suite."""
    print("kit del revisore: difesa dalla dimenticanza, buchi meccanici chiusi")
    test_ciclo_completo()
    test_close_rifiutato_se_mosso()
    test_evidenza_di_un_gate_precedente()
    test_preflight_obbligatorio()
    test_preflight_go_no_go()
    test_identita_della_revisione()
    test_write_scope_confinato()
    test_symlink_che_esce()
    test_registro_delle_revisioni()
    test_chiusura_a_mano_non_regge()
    test_revisione_malformata()
    test_sigillo()
    test_task_non_e_un_percorso()
    test_contract_chiuso_non_si_congela()
    test_brief_ermetico()
    test_catalogo()
    test_cli()
    test_gate_obbligatorio()
    test_evidenze_identita_e_vuotezza()
    test_validatore_confinato()
    test_percorso_lunghissimo_e_non_ascii()
    test_sottodirectory()
    test_evidenza_modificata_dopo_la_chiusura()
    test_timbro_rosso()
    test_ledger_r2()
    test_marcatore_sigillato()
    test_coerenza_sigilli()
    test_chiusura_end_to_end()
    test_utf8_invalido()
    test_ruolo_dell_evidenza()
    test_pycache()
    test_contract_ombra()
    test_registro_incoerente()
    test_timbro_senza_sha()
    test_evidenze_in_verifica()
    test_evidenze_malformate_in_verifica()
    test_perimetro_nel_brief()
    test_registro_fermo_alla_revisione_precedente()
    test_brief_registri_malformati()
    test_timestamp_yaml()
    test_contract_yml()
    test_budget_non_mappa()
    test_brief_errori_malformati()
    test_errori_fuori_dagli_ultimi_cinque()
    test_prompt_senza_percorsi()
    test_criteri_malformati()
    test_evidenza_debole_rifiutata()
    test_prompt_task_inesistente()
    test_brief_termine_come_qa()
    print(f"PASS — {PASSED} controlli sul kit del revisore")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
