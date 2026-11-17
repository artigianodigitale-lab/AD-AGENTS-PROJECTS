#!/usr/bin/env python3
"""Test del verdetto fail-closed (ENG-001, passo 1).

    python3 tools/tests/test_evidenza.py

Non richiede pytest: ogni controllo e' un'asserzione e il file esce 1 al primo
fallimento. Come `test_ad_org.py`, ma su un solo oggetto: **un gate si chiude
solo con un PASS**, e tutto il resto lo tiene aperto.

Perche' esiste. Il verdetto era scritto come elenco di cio' che BLOCCA
(`FAIL`, `MISSING`, `INVALID`): qualunque altro valore — compreso un `UNKNOWN`
che nessuno aveva previsto — sarebbe passato per ACCEPT, perche' non era
nell'elenco dei cattivi. Un elenco di cio' che blocca e' aperto per costruzione.
Questi test provano il RIFIUTO, non il successo: il successo lo prova gia' la
suite esistente.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

import yaml  # noqa: E402

import ad_evidence  # noqa: E402
import misure  # noqa: E402

PASSED = 0

#: I sei side-effect richiesti da `ad_evidence._validity_problem` (DEC-0011).
SIDE_EFFECTS = {
    "code": "YES",
    "database": "NO",
    "schema": "NO",
    "deps": "NO",
    "env": "NO",
    "external_services": "NO",
}


def check(label: str, condition: bool, detail: str = "") -> None:
    """Assert one condition and report it."""
    global PASSED
    if not condition:
        raise AssertionError(f"{label}: {detail or 'condizione falsa'}")
    PASSED += 1


def _contratto(**over: object) -> dict[str, object]:
    """Build a minimal contract that the verdict accepts as valid."""
    base: dict[str, object] = {
        "task_id": "ENG-TEST",
        "agent": "esecutore",
        "required_gates": ["QA"],
        "write_scope": ["tools/"],
        "approval": {"human": False},
    }
    base.update(over)
    return base


def _evidenza(
    cartella: Path,
    nome: str,
    *,
    gate: str = "QA",
    outcome: str = "PASS",
    producer: str = "qa",
    task_id: str = "ENG-TEST",
) -> Path:
    """Write one evidence file inside a temporary directory."""
    data = {
        "task_id": task_id,
        "gate": gate,
        "outcome": outcome,
        "producer": producer,
        "side_effects": dict(SIDE_EFFECTS),
        "references": ["tools/tests/test_evidenza.py"],
    }
    percorso = cartella / f"{nome}.yaml"
    percorso.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return percorso


def _verdetto(contratto: dict[str, object], *percorsi: Path) -> ad_evidence.Verdict:
    """Evaluate a contract against the given evidence files."""
    return ad_evidence.evaluate(
        contratto, ad_evidence.collect([str(percorso) for percorso in percorsi])
    )


def test_pass_chiude_il_gate() -> None:
    """Il caso che deve continuare a funzionare: PASS -> ACCEPT."""
    with tempfile.TemporaryDirectory() as tmp:
        percorso = _evidenza(Path(tmp), "qa")
        verdetto = _verdetto(_contratto(), percorso)
    check("PASS chiude", verdetto.outcome == "ACCEPT", verdetto.outcome)
    check("PASS e' lo stato", verdetto.gates[0].state == "PASS", verdetto.gates[0].state)


def test_fail_tiene_aperto() -> None:
    """FAIL -> REJECT, e lo stato resta FAIL (non viene mascherato)."""
    with tempfile.TemporaryDirectory() as tmp:
        percorso = _evidenza(Path(tmp), "qa", outcome="FAIL")
        verdetto = _verdetto(_contratto(), percorso)
    check("FAIL blocca", verdetto.outcome == "REJECT", verdetto.outcome)
    check("FAIL resta FAIL", verdetto.gates[0].state == "FAIL", verdetto.gates[0].state)


def test_unknown_non_aggrega() -> None:
    """LA REGRESSIONE DI QUESTO PASSO: UNKNOWN non e' ACCEPT.

    Prima della correzione questo caso produceva ACCEPT, perche' `UNKNOWN` non
    era nell'elenco di cio' che blocca.
    """
    with tempfile.TemporaryDirectory() as tmp:
        percorso = _evidenza(Path(tmp), "qa", outcome="UNKNOWN")
        verdetto = _verdetto(_contratto(), percorso)
    check("UNKNOWN non aggrega", verdetto.outcome == "REJECT", verdetto.outcome)
    check(
        "UNKNOWN e' riconosciuto, non INVALID",
        verdetto.gates[0].state == "UNKNOWN",
        verdetto.gates[0].state,
    )
    check(
        "la nota spiega il fail-closed",
        any("fail-closed" in nota for nota in verdetto.notes),
        str(verdetto.notes),
    )


def test_gli_altri_esiti_aperti() -> None:
    """TRUNCATED, SKIPPED, UNSUPPORTED: ammessi, e nessuno chiude il gate."""
    for esito in ("TRUNCATED", "SKIPPED", "UNSUPPORTED"):
        with tempfile.TemporaryDirectory() as tmp:
            percorso = _evidenza(Path(tmp), "qa", outcome=esito)
            verdetto = _verdetto(_contratto(), percorso)
        check(f"{esito} blocca", verdetto.outcome == "REJECT", verdetto.outcome)
        check(
            f"{esito} resta se stesso",
            verdetto.gates[0].state == esito,
            verdetto.gates[0].state,
        )


def test_esito_inventato() -> None:
    """Un esito che non esiste non e' ne' PASS ne' valido: INVALID."""
    with tempfile.TemporaryDirectory() as tmp:
        percorso = _evidenza(Path(tmp), "qa", outcome="MAGARI")
        verdetto = _verdetto(_contratto(), percorso)
    check("esito inventato blocca", verdetto.outcome == "REJECT", verdetto.outcome)
    check(
        "esito inventato e' INVALID",
        verdetto.gates[0].state == "INVALID",
        verdetto.gates[0].state,
    )


def test_evidenza_assente() -> None:
    """Nessuna evidenza per un gate richiesto: MISSING, e REJECT."""
    with tempfile.TemporaryDirectory() as tmp:
        percorso = _evidenza(Path(tmp), "altro", gate="QA", task_id="ALTRO-TASK")
        verdetto = _verdetto(_contratto(), percorso)
    check("assenza blocca", verdetto.outcome == "REJECT", verdetto.outcome)
    check("assenza e' MISSING", verdetto.gates[0].state == "MISSING", verdetto.gates[0].state)


def test_produttore_non_e_l_esecutore() -> None:
    """Chi produce l'artefatto non valida il proprio gate."""
    with tempfile.TemporaryDirectory() as tmp:
        percorso = _evidenza(Path(tmp), "qa", producer="esecutore")
        verdetto = _verdetto(_contratto(), percorso)
    check("auto-validazione bloccata", verdetto.outcome == "REJECT", verdetto.outcome)
    check(
        "auto-validazione e' INVALID",
        verdetto.gates[0].state == "INVALID",
        verdetto.gates[0].state,
    )


def test_un_gate_aperto_blocca_tutto() -> None:
    """Due gate: uno PASS e uno UNKNOWN -> REJECT. Non si media."""
    with tempfile.TemporaryDirectory() as tmp:
        percorso = _evidenza(Path(tmp), "qa", gate="QA", outcome="PASS")
        contratto = _contratto(required_gates=["QA", "Code Review"])
        verdetto = _verdetto(contratto, percorso)
    check("un gate aperto blocca", verdetto.outcome == "REJECT", verdetto.outcome)
    stati = {result.gate: result.state for result in verdetto.gates}
    check(
        "il gate senza evidenza e' MISSING",
        any(state == "MISSING" for state in stati.values()),
        str(stati),
    )



#: Un esempio completo di evidenza di schema 2, valida.
V2 = {
    "schema": 2,
    "confidence": "observed",
    "authority": "execution",
    "coverage": {"status": "complete", "examined": 12, "total": 12},
    "limitations": ["non eseguito su Windows"],
}


def _scrivi(cartella: Path, nome: str, **campi: object) -> Path:
    """Write one evidence file with arbitrary fields (defaults are valid)."""
    data: dict[str, object] = {
        "task_id": "ENG-TEST",
        "gate": "QA",
        "outcome": "PASS",
        "producer": "qa",
        "side_effects": dict(SIDE_EFFECTS),
        "references": ["tools/tests/test_evidenza.py"],
    }
    data.update(campi)
    percorso = cartella / f"{nome}.yaml"
    percorso.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return percorso


def _firma(cartella: Path, percorso: Path) -> Path:
    """Compute the identity of a written record and write it back, as an author would."""
    record = ad_evidence.load_evidence(percorso)
    data = yaml.safe_load(percorso.read_text(encoding="utf-8"))
    data["evidence_id"] = ad_evidence.compute_evidence_id(record)
    percorso.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return percorso



# --- passo 2: schema v2, copertura, identita' ---------------------------------


def test_v2_pass_completo() -> None:
    """Schema 2 con copertura completa: ACCEPT, e l'identita' e' calcolata."""
    with tempfile.TemporaryDirectory() as tmp:
        percorso = _scrivi(Path(tmp), "qa", **V2)
        verdetto = _verdetto(_contratto(), percorso)
    check("v2 completo chiude", verdetto.outcome == "ACCEPT", verdetto.outcome)
    check(
        "l'identita' e' un'impronta",
        bool(verdetto.gates[0].evidence_id) and verdetto.gates[0].evidence_id.startswith("ev_"),
        verdetto.gates[0].evidence_id,
    )


def test_v2_pass_parziale_blocca() -> None:
    """LA REGOLA NUOVA: PASS con copertura parziale e' una contraddizione."""
    with tempfile.TemporaryDirectory() as tmp:
        percorso = _scrivi(
            Path(tmp),
            "qa",
            **{**V2, "coverage": {"status": "partial", "examined": 7, "total": 12}},
        )
        verdetto = _verdetto(_contratto(), percorso)
    check("PASS parziale blocca", verdetto.outcome == "REJECT", verdetto.outcome)
    check("PASS parziale e' INVALID", verdetto.gates[0].state == "INVALID", verdetto.gates[0].state)
    check(
        "la ragione parla di osservazione completa",
        "osservazione completa" in verdetto.gates[0].detail,
        verdetto.gates[0].detail,
    )


def test_v2_pass_unknown_blocca() -> None:
    """PASS con copertura unknown: stessa contraddizione."""
    with tempfile.TemporaryDirectory() as tmp:
        percorso = _scrivi(
            Path(tmp), "qa", **{**V2, "coverage": {"status": "unknown"}}
        )
        verdetto = _verdetto(_contratto(), percorso)
    check("PASS unknown blocca", verdetto.outcome == "REJECT", verdetto.outcome)


def test_v2_senza_copertura() -> None:
    """Schema 2 senza copertura: la dichiarazione e' obbligatoria."""
    dati = dict(V2)
    dati.pop("coverage")
    with tempfile.TemporaryDirectory() as tmp:
        percorso = _scrivi(Path(tmp), "qa", **dati)
        verdetto = _verdetto(_contratto(), percorso)
    check("v2 senza copertura blocca", verdetto.outcome == "REJECT", verdetto.outcome)
    check(
        "la ragione nomina la copertura",
        "coverage" in verdetto.gates[0].detail,
        verdetto.gates[0].detail,
    )


def test_v2_senza_autorita() -> None:
    """Schema 2 senza authority: non si sa che tipo di prova sia."""
    with tempfile.TemporaryDirectory() as tmp:
        percorso = _scrivi(Path(tmp), "qa", schema=2, confidence="observed",
                           coverage={"status": "complete", "examined": 1, "total": 1})
        verdetto = _verdetto(_contratto(), percorso)
    check("v2 senza authority blocca", verdetto.outcome == "REJECT", verdetto.outcome)


def test_copertura_contraddittoria() -> None:
    """'complete' con examined < total e' una contraddizione."""
    with tempfile.TemporaryDirectory() as tmp:
        percorso = _scrivi(
            Path(tmp),
            "qa",
            **{**V2, "coverage": {"status": "complete", "examined": 3, "total": 12}},
        )
        verdetto = _verdetto(_contratto(), percorso)
    check("copertura contraddittoria blocca", verdetto.outcome == "REJECT", verdetto.outcome)


def test_legacy_vale_ma_si_dichiara() -> None:
    """Un'evidenza legacy continua a valere, e il verdetto lo dice."""
    with tempfile.TemporaryDirectory() as tmp:
        percorso = _scrivi(Path(tmp), "qa")
        verdetto = _verdetto(_contratto(), percorso)
    check("legacy vale", verdetto.outcome == "ACCEPT", verdetto.outcome)
    check(
        "legacy dichiarata nella nota",
        any("legacy" in nota for nota in verdetto.notes),
        str(verdetto.notes),
    )


def test_legacy_con_copertura_parziale_blocca() -> None:
    """Se la copertura e' dichiarata, la regola vale anche senza schema 2."""
    with tempfile.TemporaryDirectory() as tmp:
        percorso = _scrivi(
            Path(tmp), "qa", coverage={"status": "partial", "examined": 1, "total": 9}
        )
        verdetto = _verdetto(_contratto(), percorso)
    check("copertura parziale blocca", verdetto.outcome == "REJECT", verdetto.outcome)


def test_identita_manomessa() -> None:
    """Un file modificato dopo la firma: l'identita' non combacia piu'."""
    with tempfile.TemporaryDirectory() as tmp:
        percorso = _firma(Path(tmp), _scrivi(Path(tmp), "qa", **V2))
        pulito = _verdetto(_contratto(), percorso)
        data = yaml.safe_load(percorso.read_text(encoding="utf-8"))
        data["limitations"] = ["una limitazione aggiunta dopo la firma"]
        percorso.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
        manomesso = _verdetto(_contratto(), percorso)
    check("firma valida chiude", pulito.outcome == "ACCEPT", pulito.outcome)
    check("manomesso blocca", manomesso.outcome == "REJECT", manomesso.outcome)
    check(
        "la ragione parla di modifica dopo la firma",
        "modificato dopo la firma" in manomesso.gates[0].detail,
        manomesso.gates[0].detail,
    )


def test_identita_e_proprieta_del_contenuto() -> None:
    """L'identita' non dipende dal percorso, e cambia se cambia il contenuto."""
    with tempfile.TemporaryDirectory() as tmp:
        uno = _scrivi(Path(tmp), "primo", **V2)
        due = _scrivi(Path(tmp), "secondo", **V2)
        id_uno = ad_evidence.compute_evidence_id(ad_evidence.load_evidence(uno))
        id_due = ad_evidence.compute_evidence_id(ad_evidence.load_evidence(due))
        tre = _scrivi(Path(tmp), "terzo", **{**V2, "limitations": ["altra limitazione"]})
        id_tre = ad_evidence.compute_evidence_id(ad_evidence.load_evidence(tre))
    check("stesso contenuto, stesso id", id_uno == id_due, f"{id_uno} vs {id_due}")
    check("contenuto diverso, id diverso", id_uno != id_tre, "id uguale con contenuto diverso")



# --- passo 3: registro delle incognite ----------------------------------------


def _prova(cartella: Path, nome: str, **campi: object) -> dict[str, object]:
    """Write one v2 evidence file and return it keyed for the registry checks."""
    dati = dict(V2)
    dati.update(campi)
    percorso = _scrivi(cartella, nome, **dati)
    record = ad_evidence.load_evidence(percorso)
    return {record.evidence_id: record}


def test_incognita_identita_stabile() -> None:
    """L'id si calcola da domanda+dominio: niente id scelti, niente corse."""
    primo = ad_evidence.unknown_id("Le dipendenze sono coperte?", "sicurezza")
    secondo = ad_evidence.unknown_id("  Le   dipendenze sono coperte?  ", "sicurezza")
    altro = ad_evidence.unknown_id("Le dipendenze sono coperte?", "privacy")
    check("id stabile sugli spazi", primo == secondo, f"{primo} vs {secondo}")
    check("dominio diverso, id diverso", primo != altro, "id uguale su domini diversi")
    check("id con prefisso", primo.startswith("unk_"), primo)


def test_incognita_nuova_e_coerente() -> None:
    """Una voce nuova passa il controllo del registro."""
    record = ad_evidence.new_unknown("X?", "dominio", severity="high")
    check("nuova voce coerente", ad_evidence.check_unknowns([record]) == [], str(ad_evidence.check_unknowns([record])))
    check("stato iniziale aperto", record["status"] == "open", str(record["status"]))


def test_incognita_id_inventato() -> None:
    """Un id che non corrisponde alla domanda e' un errore, non un dettaglio."""
    record = ad_evidence.new_unknown("X?", "dominio")
    record["unknown_id"] = "unk_00000000000000000000000000000000"
    problemi = ad_evidence.check_unknowns([record])
    check("id inventato segnalato", any("id non corrisponde" in p for p in problemi), str(problemi))


def test_incognita_duplicata() -> None:
    """La stessa domanda due volte e' una voce doppia, e si vede."""
    record = ad_evidence.new_unknown("X?", "dominio")
    problemi = ad_evidence.check_unknowns([record, dict(record)])
    check("duplicato segnalato", any("duplicato" in p for p in problemi), str(problemi))


def test_incognita_revisione() -> None:
    """Ogni modifica e' una revisione, e la catena deve tornare."""
    record = ad_evidence.new_unknown("X?", "dominio")
    seconda = ad_evidence.update_unknown(record, status="investigating")
    check("revisione incrementata", seconda["revision"] == 2, str(seconda["revision"]))
    check("catena coerente", seconda["previous_revision"] == 1, str(seconda["previous_revision"]))
    rotta = dict(seconda)
    rotta["previous_revision"] = 7
    problemi = ad_evidence.check_unknowns([rotta])
    check("catena rotta segnalata", any("previous_revision" in p for p in problemi), str(problemi))


def test_incognita_risolta_senza_prova() -> None:
    """Una domanda non si chiude con un'opinione."""
    record = ad_evidence.new_unknown("X?", "dominio")
    chiusa = ad_evidence.update_unknown(
        record,
        status="resolved",
        resolution={"disposition": "verified", "rationale": "fatto", "evidence_ids": []},
    )
    problemi = ad_evidence.check_unknowns([chiusa])
    check("chiusura senza prova segnalata", any("almeno una prova" in p for p in problemi), str(problemi))


def test_incognita_risolta_con_prova_comparabile() -> None:
    """Si chiude con una prova che esiste e ha l'autorita' richiesta."""
    with tempfile.TemporaryDirectory() as tmp:
        prove = _prova(Path(tmp), "esecuzione", authority="execution")
        record = ad_evidence.new_unknown("X?", "dominio", required_authority="execution")
        identificatore = next(iter(prove))
        chiusa = ad_evidence.update_unknown(
            record,
            status="resolved",
            resolution={
                "disposition": "verified",
                "rationale": "eseguito e osservato",
                "evidence_ids": [identificatore],
            },
        )
        problemi = ad_evidence.check_unknowns([chiusa], prove)
    check("chiusura con prova valida", problemi == [], str(problemi))


def test_incognita_autorita_incomparabile() -> None:
    """Una prova di tipo diverso non chiude una domanda che ne chiede un'altra."""
    with tempfile.TemporaryDirectory() as tmp:
        prove = _prova(Path(tmp), "artefatto", authority="artifact")
        record = ad_evidence.new_unknown("X?", "dominio", required_authority="execution")
        identificatore = next(iter(prove))
        chiusa = ad_evidence.update_unknown(
            record,
            status="resolved",
            resolution={
                "disposition": "verified",
                "rationale": "letto un report",
                "evidence_ids": [identificatore],
            },
        )
        problemi = ad_evidence.check_unknowns([chiusa], prove)
    check(
        "autorita' incomparabile segnalata",
        any("autority" in p or "authority" in p for p in problemi),
        str(problemi),
    )


def test_incognita_resolution_su_voce_aperta() -> None:
    """Una resolution su una voce non risolta e' una contraddizione."""
    record = ad_evidence.new_unknown("X?", "dominio")
    record["resolution"] = {"disposition": "verified", "rationale": "x", "evidence_ids": ["ev_x"]}
    problemi = ad_evidence.check_unknowns([record])
    check("resolution su aperta segnalata", any("c'e' una resolution" in p for p in problemi), str(problemi))


def test_incognita_registro_round_trip() -> None:
    """Il registro si salva e si rilegge identico."""
    with tempfile.TemporaryDirectory() as tmp:
        percorso = Path(tmp) / "incognite.yaml"
        record = ad_evidence.new_unknown("X?", "dominio")
        ad_evidence.save_unknowns(percorso, [record])
        riletto = ad_evidence.load_unknowns(percorso)
    check("round-trip del registro", riletto == [record], "registro diverso dopo il salvataggio")



# --- passo 4: bundle sigillato ------------------------------------------------


def _prove_di(cartella: Path, nome: str = "qa", **campi: object) -> list:
    """Write one evidence file and return it as a list, ready for a bundle."""
    dati = dict(V2)
    dati.update(campi)
    percorso = _scrivi(cartella, nome, **dati)
    return [ad_evidence.load_evidence(percorso)]


def test_bundle_esporta_e_verifica() -> None:
    """Un bundle appena creato e' attendibile, e ha un sigillo."""
    with tempfile.TemporaryDirectory() as tmp:
        prove = _prove_di(Path(tmp))
        bundle = ad_evidence.create_bundle(prove)
        problemi = ad_evidence.verify_bundle(bundle)
    check("bundle coerente", problemi == [], str(problemi))
    check("bundle sigillato", str(bundle.get("seal", "")).startswith("seal_"), str(bundle.get("seal")))
    check("un record nel bundle", len(bundle["records"]) == 1, str(len(bundle["records"])))


def test_bundle_manomesso() -> None:
    """Modificare una riga del pacchetto rompe il sigillo."""
    with tempfile.TemporaryDirectory() as tmp:
        bundle = ad_evidence.create_bundle(_prove_di(Path(tmp)))
        bundle["records"][0]["limitations"] = ["cambiata dopo il sigillo"]
        problemi = ad_evidence.verify_bundle(bundle)
    check(
        "manomissione del bundle rilevata",
        any("sigillo" in p for p in problemi),
        str(problemi),
    )


def test_bundle_sigillo_ricalcolato() -> None:
    """Se l'attaccante ricalcola il sigillo, resta la seconda rete: l'identita'."""
    with tempfile.TemporaryDirectory() as tmp:
        bundle = ad_evidence.create_bundle(_prove_di(Path(tmp)))
        bundle["records"][0]["limitations"] = ["cambiata e risigillata"]
        bundle["seal"] = ad_evidence._bundle_seal(bundle)
        problemi = ad_evidence.verify_bundle(bundle)
    check(
        "identita' del record rileva la modifica",
        any("evidence_id dichiarato" in p for p in problemi),
        str(problemi),
    )


def test_bundle_vuoto_rifiutato() -> None:
    """Un bundle senza prove non e' un bundle."""
    try:
        ad_evidence.create_bundle([])
    except ad_evidence.BundleError:
        check("bundle vuoto rifiutato", True)
    else:
        check("bundle vuoto rifiutato", False, "create_bundle([]) non ha sollevato")


def test_bundle_un_solo_task() -> None:
    """Due lavori diversi non stanno nello stesso pacchetto."""
    with tempfile.TemporaryDirectory() as tmp:
        prove = _prove_di(Path(tmp), "uno", task_id="A")
        prove += _prove_di(Path(tmp), "due", task_id="B")
        try:
            ad_evidence.create_bundle(prove)
        except ad_evidence.BundleError:
            check("bundle misto rifiutato", True)
        else:
            check("bundle misto rifiutato", False, "create_bundle non ha sollevato")


def test_bundle_round_trip_ed_estrazione() -> None:
    """Esporta, rileggi, verifica ed estrai: le prove restano le stesse."""
    with tempfile.TemporaryDirectory() as tmp:
        cartella = Path(tmp)
        bundle = ad_evidence.create_bundle(_prove_di(cartella))
        ad_evidence.save_bundle(cartella / "bundle.json", bundle)
        riletto = ad_evidence.load_bundle(cartella / "bundle.json")
        esito = ad_evidence.extract_bundle(riletto, cartella / "fuori")
        lette = ad_evidence.collect([cartella / "fuori"])
    check("round-trip coerente", ad_evidence.verify_bundle(riletto) == [], "bundle riletto non valido")
    check("estrazione completa", esito["records"] == 1, str(esito))
    check("estratto rileggibile", len(lette) == 1, str(len(lette)))
    check(
        "identita' conservata",
        lette[0].evidence_id == ad_evidence._record_from_dict(riletto["records"][0]).evidence_id,
        "identita' diversa dopo il viaggio",
    )


def test_bundle_incognite_coerenti() -> None:
    """Le incognite del bundle devono reggersi sulle prove del bundle."""
    with tempfile.TemporaryDirectory() as tmp:
        prove = _prove_di(Path(tmp), authority="execution")
        identificatore = prove[0].evidence_id
        record = ad_evidence.new_unknown("X?", "dominio", required_authority="execution")
        chiusa = ad_evidence.update_unknown(
            record,
            status="resolved",
            resolution={
                "disposition": "verified",
                "rationale": "eseguito",
                "evidence_ids": [identificatore],
            },
        )
        bundle = ad_evidence.create_bundle(prove, [chiusa])
        problemi = ad_evidence.verify_bundle(bundle)
    check("incognita coerente nel bundle", problemi == [], str(problemi))


def test_bundle_incognita_senza_prova() -> None:
    """Se la prova citata non e' nel bundle, il bundle non e' attendibile."""
    with tempfile.TemporaryDirectory() as tmp:
        prove = _prove_di(Path(tmp))
        record = ad_evidence.new_unknown("X?", "dominio", required_authority="execution")
        chiusa = ad_evidence.update_unknown(
            record,
            status="resolved",
            resolution={
                "disposition": "verified",
                "rationale": "detto io",
                "evidence_ids": ["ev_" + "0" * 64],
            },
        )
        bundle = ad_evidence.create_bundle(prove, [chiusa])
        problemi = ad_evidence.verify_bundle(bundle)
    check(
        "prova assente segnalata",
        any("non esiste nel registro" in p for p in problemi),
        str(problemi),
    )


def test_collect_ignora_il_registro() -> None:
    """Una cartella con prove e registro conta solo le prove."""
    with tempfile.TemporaryDirectory() as tmp:
        cartella = Path(tmp)
        _scrivi(cartella, "qa", **V2)
        ad_evidence.save_unknowns(
            cartella / "incognite.yaml", [ad_evidence.new_unknown("X?", "dominio")]
        )
        lette = ad_evidence.collect([cartella])
    check("il registro non e' una prova", len(lette) == 1, str(len(lette)))



# --- passo 5: limiti obbligatori ---------------------------------------------


def test_schema2_senza_limiti() -> None:
    """Schema 2 senza `limitations` non e' falsificabile: il gate resta aperto."""
    dati = dict(V2)
    dati.pop("limitations")
    with tempfile.TemporaryDirectory() as tmp:
        percorso = _scrivi(Path(tmp), "qa", **dati)
        verdetto = _verdetto(_contratto(), percorso)
    check("senza limiti blocca", verdetto.outcome == "REJECT", verdetto.outcome)
    check(
        "la ragione chiede i limiti",
        "limitations" in verdetto.gates[0].detail,
        verdetto.gates[0].detail,
    )


def test_schema2_limiti_vuoti_ma_dichiarati() -> None:
    """`limitations: []` e' una dichiarazione: nessun limite, ma detto."""
    with tempfile.TemporaryDirectory() as tmp:
        percorso = _scrivi(Path(tmp), "qa", **{**V2, "limitations": []})
        verdetto = _verdetto(_contratto(), percorso)
    check("limiti vuoti dichiarati passano", verdetto.outcome == "ACCEPT", verdetto.outcome)


def test_legacy_senza_limiti_passa() -> None:
    """L'evidenza legacy non ha l'obbligo, e il verdetto lo dice."""
    with tempfile.TemporaryDirectory() as tmp:
        percorso = _scrivi(Path(tmp), "qa")
        verdetto = _verdetto(_contratto(), percorso)
    check("legacy senza limiti passa", verdetto.outcome == "ACCEPT", verdetto.outcome)


def test_limiti_portati_al_chiamante() -> None:
    """I limiti dichiarati arrivano nel risultato del gate, non si perdono."""
    with tempfile.TemporaryDirectory() as tmp:
        percorso = _scrivi(Path(tmp), "qa", **V2)
        verdetto = _verdetto(_contratto(), percorso)
    check(
        "i limiti sono esposti",
        "non eseguito su Windows" in verdetto.gates[0].limitations,
        str(verdetto.gates[0].limitations),
    )


def _elenco(cartella: Path, testo: str) -> Path:
    percorso = cartella / "elenco.yaml"
    percorso.write_text(testo, encoding="utf-8")
    return percorso


def test_misure_schema2_senza_limiti() -> None:
    """Un elenco di misure in schema 2 senza limiti non si carica."""
    with tempfile.TemporaryDirectory() as tmp:
        percorso = _elenco(
            Path(tmp),
            "versione: 2\ntitolo: Prova\nmisure:\n"
            "  - nome: una\n    comando: printf 'ok\\n'\n    descrizione: stampa\n",
        )
        try:
            misure.carica(percorso)
        except misure.ElencoNonValido:
            check("elenco v2 senza limiti rifiutato", True)
        else:
            check("elenco v2 senza limiti rifiutato", False, "carica non ha sollevato")


def test_misure_limiti_nell_allegato() -> None:
    """I limiti dichiarati finiscono DENTRO l'allegato, che e' la prova citata."""
    with tempfile.TemporaryDirectory() as tmp:
        percorso = _elenco(
            Path(tmp),
            "versione: 2\ntitolo: Prova\nlimiti:\n  - solo su Linux x64\nmisure:\n"
            "  - nome: una\n    comando: printf 'ok\\n'\n    descrizione: stampa\n",
        )
        elenco = misure.carica(percorso)
        testo = misure.rendi(elenco, [], Path("."), "0" * 64)
    check("allegato con sezione limiti", "## Limiti dichiarati" in testo, "sezione assente")
    check("allegato cita il limite", "solo su Linux x64" in testo, "limite non citato")


def test_misure_legacy_dichiara_l_assenza() -> None:
    """Un elenco legacy dichiara di non avere limiti invece di tacere."""
    with tempfile.TemporaryDirectory() as tmp:
        percorso = _elenco(
            Path(tmp),
            "titolo: Prova\nmisure:\n"
            "  - nome: una\n    comando: printf 'ok\\n'\n    descrizione: stampa\n",
        )
        elenco = misure.carica(percorso)
        testo = misure.rendi(elenco, [], Path("."), "0" * 64)
    check("legacy dichiara l'assenza", "Nessun limite dichiarato" in testo, "assenza non dichiarata")



# --- passo 6: rilevamento fuori banda ----------------------------------------


def _albero(cartella: Path) -> Path:
    """Prepare a tiny watched tree: a/ with one file."""
    (cartella / "a").mkdir(parents=True, exist_ok=True)
    (cartella / "a" / "uno.txt").write_text("uno\n", encoding="utf-8")
    return cartella


def test_albero_immutato() -> None:
    """Se niente cambia, nessuna contaminazione."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _albero(Path(tmp))
        witness = ad_evidence.create_witness(radice, ("a",))
        corrente = ad_evidence.tree_fingerprint(radice, ("a",))
    check("albero immutato pulito", ad_evidence.compare_tree(witness, corrente) == [], "contaminazioni trovate")


def test_albero_modificato_fuori_banda() -> None:
    """Una modifica che nessuna evidenza nomina e' una contaminazione."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _albero(Path(tmp))
        witness = ad_evidence.create_witness(radice, ("a",))
        (radice / "a" / "uno.txt").write_text("due\n", encoding="utf-8")
        corrente = ad_evidence.tree_fingerprint(radice, ("a",))
        problemi = ad_evidence.compare_tree(witness, corrente)
    check(
        "modifica fuori banda rilevata",
        any("MODIFICATO fuori banda" in p for p in problemi),
        str(problemi),
    )


def test_albero_aggiunto_e_rimosso() -> None:
    """Anche aggiungere e togliere sono modifiche, non solo cambiare."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _albero(Path(tmp))
        witness = ad_evidence.create_witness(radice, ("a",))
        (radice / "a" / "nuovo.txt").write_text("x\n", encoding="utf-8")
        aggiunto = ad_evidence.tree_fingerprint(radice, ("a",))
        problemi_aggiunta = ad_evidence.compare_tree(witness, aggiunto)
        (radice / "a" / "nuovo.txt").unlink()
        (radice / "a" / "uno.txt").unlink()
        rimosso = ad_evidence.tree_fingerprint(radice, ("a",))
        problemi_rimozione = ad_evidence.compare_tree(witness, rimosso)
    check("aggiunta rilevata", any("AGGIUNTO" in p for p in problemi_aggiunta), str(problemi_aggiunta))
    check("rimozione rilevata", any("RIMOSSO" in p for p in problemi_rimozione), str(problemi_rimozione))


def test_albero_coperto_da_evidenza() -> None:
    """Se un'evidenza nomina il percorso, la modifica e' dichiarata, non silenziosa."""
    with tempfile.TemporaryDirectory() as tmp:
        cartella = Path(tmp)
        radice = _albero(cartella)
        witness = ad_evidence.create_witness(radice, ("a",))
        (radice / "a" / "uno.txt").write_text("due\n", encoding="utf-8")
        corrente = ad_evidence.tree_fingerprint(radice, ("a",))
        prova = _scrivi(cartella, "qa", **{**V2, "references": ["a/uno.txt"]})
        copertura = ad_evidence.coverage_map([ad_evidence.load_evidence(prova)])
        problemi = ad_evidence.compare_tree(witness, corrente, copertura)
    check("modifica coperta da evidenza", problemi == [], str(problemi))


def test_albero_coperto_da_cartella() -> None:
    """Una referenza a una cartella copre cio' che ci sta dentro."""
    with tempfile.TemporaryDirectory() as tmp:
        cartella = Path(tmp)
        radice = _albero(cartella)
        witness = ad_evidence.create_witness(radice, ("a",))
        (radice / "a" / "due.txt").write_text("x\n", encoding="utf-8")
        corrente = ad_evidence.tree_fingerprint(radice, ("a",))
        prova = _scrivi(cartella, "qa", **{**V2, "references": ["a"]})
        copertura = ad_evidence.coverage_map([ad_evidence.load_evidence(prova)])
        problemi = ad_evidence.compare_tree(witness, corrente, copertura)
    check("cartella copre i figli", problemi == [], str(problemi))


def test_testimone_manomesso() -> None:
    """Se il testimone viene modificato, il sigillo lo dice."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _albero(Path(tmp))
        witness = ad_evidence.create_witness(radice, ("a",))
        witness["files"]["a/uno.txt"] = "0" * 64
        corrente = ad_evidence.tree_fingerprint(radice, ("a",))
        problemi = ad_evidence.compare_tree(witness, corrente)
    check(
        "testimone manomesso segnalato",
        any("modificato dopo essere stato sigillato" in p for p in problemi),
        str(problemi),
    )


def test_testimone_esclude_se_stesso() -> None:
    """Il testimone vive dentro la cartella sorvegliata: si esclude da solo."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = _albero(Path(tmp))
        witness = ad_evidence.create_witness(radice, ("a",), exclude=("a/uno.txt",))
    check("esclusione dichiarata", witness.get("exclude") == ["a/uno.txt"], str(witness.get("exclude")))
    check("file escluso non contato", "a/uno.txt" not in witness["files"], str(list(witness["files"])))



def test_bundle_con_testimone() -> None:
    """Il pacchetto sigilla anche com'era l'albero quando le prove sono nate."""
    with tempfile.TemporaryDirectory() as tmp:
        cartella = Path(tmp)
        prove = _prove_di(cartella)
        radice = _albero(cartella)
        testimone = ad_evidence.create_witness(radice, ("a",))
        bundle = ad_evidence.create_bundle(prove, witness=testimone)
        problemi = ad_evidence.verify_bundle(bundle)
    check("bundle con testimone coerente", problemi == [], str(problemi))


def test_bundle_testimone_manomesso() -> None:
    """Toccare il testimone dentro il pacchetto lo invalida."""
    with tempfile.TemporaryDirectory() as tmp:
        cartella = Path(tmp)
        prove = _prove_di(cartella)
        testimone = ad_evidence.create_witness(_albero(cartella), ("a",))
        bundle = ad_evidence.create_bundle(prove, witness=testimone)
        bundle["witness"]["files"]["a/uno.txt"] = "0" * 64
        problemi = ad_evidence.verify_bundle(bundle)
    check(
        "testimone manomesso segnalato",
        any("testimone dentro il bundle" in p for p in problemi),
        str(problemi),
    )


def test_bundle_estrae_il_testimone() -> None:
    """L'estrazione porta fuori anche il testimone, per poterlo ricontrollare."""
    with tempfile.TemporaryDirectory() as tmp:
        cartella = Path(tmp)
        prove = _prove_di(cartella)
        testimone = ad_evidence.create_witness(_albero(cartella), ("a",))
        bundle = ad_evidence.create_bundle(prove, witness=testimone)
        esito = ad_evidence.extract_bundle(bundle, cartella / "fuori")
        presente = (cartella / "fuori" / "albero.yaml").is_file()
    check("testimone estratto", esito.get("witness") == 1, str(esito))
    check("file del testimone presente", presente, "assente")



# --- F4 del primo gate: la CLI deve essere provata, non solo la libreria ------


def _cli(*argomenti: str) -> subprocess.CompletedProcess:
    """Run verdict.py as a user would, and capture the result."""
    return subprocess.run(
        [sys.executable, str(TOOLS / "verdict.py"), *argomenti],
        capture_output=True,
        text=True,
        cwd=str(TOOLS.parent),
    )


def _registro_con_chiusura_inventata(cartella: Path) -> Path:
    """Write a ledger where a critical question is 'verified' by a fake proof."""
    identificatore = ad_evidence.unknown_id("X?", "d")
    percorso = cartella / "incognite.yaml"
    percorso.write_text(
        "unknowns:\n"
        f"  - unknown_id: \"{identificatore}\"\n"
        "    revision: 2\n"
        "    previous_revision: 1\n"
        '    question: "X?"\n'
        '    domain: "d"\n'
        "    status: resolved\n"
        "    severity: critical\n"
        "    required_authority: execution\n"
        "    required_confidence: observed\n"
        "    supporting_evidence: []\n"
        "    contradicting_evidence: []\n"
        "    recommended_probes: []\n"
        "    resolution:\n"
        "      disposition: verified\n"
        '      rationale: "detto io"\n'
        '      evidence_ids: ["ev_' + "0" * 64 + '"]\n',
        encoding="utf-8",
    )
    return percorso


def test_cli_incognita_non_e_fail_open() -> None:
    """F1: senza --evidence il registro NON deve dire OK a una chiusura inventata."""
    with tempfile.TemporaryDirectory() as tmp:
        percorso = _registro_con_chiusura_inventata(Path(tmp))
        esito = _cli("--unknown", "check", "--ledger", str(percorso))
    check(
        "CLI: chiusura inventata rifiutata di default",
        esito.returncode == 1,
        f"exit {esito.returncode}: {esito.stdout.strip()[:120]}",
    )


def test_cli_resolve_non_chiude_con_prova_inventata() -> None:
    """F1: anche `resolve` di default deve rifiutare una prova che non esiste."""
    with tempfile.TemporaryDirectory() as tmp:
        cartella = Path(tmp)
        ledger = cartella / "incognite.yaml"
        nuovo = _cli(
            "--unknown", "new", "--ledger", str(ledger),
            "--question", "X?", "--domain", "d", "--severity", "critical",
            "--authority", "execution",
        )
        identificatore = nuovo.stdout.split()[0]
        esito = _cli(
            "--unknown", "resolve", "--ledger", str(ledger), "--id", identificatore,
            "--disposition", "verified", "--rationale", "detto io",
            "--evidence-ids", "ev_" + "0" * 64,
        )
    check(
        "CLI: resolve con prova inventata rifiutato",
        esito.returncode == 1,
        f"exit {esito.returncode}: {esito.stderr.strip()[:120]}",
    )


def test_cli_confidenza_assente_non_chiude() -> None:
    """F2: una prova senza `confidence` non soddisfa una domanda che la chiede."""
    with tempfile.TemporaryDirectory() as tmp:
        cartella = Path(tmp)
        prova = cartella / "prova.yaml"
        prova.write_text(
            "task_id: T\ngate: QA\noutcome: PASS\nproducer: qa\n"
            "authority: execution\nreferences: ['x']\n"
            "side_effects: {code: YES, database: NO, schema: NO, deps: NO, env: NO, "
            "external_services: NO}\n",
            encoding="utf-8",
        )
        identificatore = ad_evidence.compute_evidence_id(ad_evidence.load_evidence(prova))
        ledger = _registro_con_chiusura_inventata(cartella)
        # riscrivo la chiusura con la prova vera: la confidenza resta assente
        testo = ledger.read_text(encoding="utf-8").replace("ev_" + "0" * 64, identificatore)
        ledger.write_text(testo, encoding="utf-8")
        esito = _cli(
            "--unknown", "check", "--ledger", str(ledger),
            "--evidence", str(prova),
        )
    check(
        "CLI: confidenza assente rifiutata",
        esito.returncode == 1,
        f"exit {esito.returncode}: {esito.stdout.strip()[:120]}",
    )


def test_cli_bundle() -> None:
    """La CLI del bundle esporta, verifica e rifiuta un pacchetto manomesso."""
    with tempfile.TemporaryDirectory() as tmp:
        cartella = Path(tmp)
        ev = cartella / "ev"
        ev.mkdir()
        _scrivi(ev, "qa", **V2)
        bundle = cartella / "b.json"
        # Ledger proprio: senza, l'export legge evidenze/incognite.yaml e il test
        # dipende dallo stato del registro reale (ERR-0052, famiglia ERR-0049).
        ledger = cartella / "incognite.yaml"
        ledger.write_text("unknowns: []\n", encoding="utf-8")
        export = _cli(
            "--bundle", "export", "--evidence", str(ev), "--out", str(bundle),
            "--ledger", str(ledger), "--no-witness",
        )
        integro = _cli("--bundle", "check", "--bundle-path", str(bundle))
        dati = json.loads(bundle.read_text(encoding="utf-8"))
        dati["records"][0]["limitations"] = ["toccata dopo il sigillo"]
        bundle.write_text(json.dumps(dati), encoding="utf-8")
        manomesso = _cli("--bundle", "check", "--bundle-path", str(bundle))
    check("CLI: export", export.returncode == 0, export.stderr[:120])
    check("CLI: bundle integro", integro.returncode == 0, integro.stderr[:120])
    check("CLI: bundle manomesso rifiutato", manomesso.returncode == 1, manomesso.stdout[:120])


def test_cli_albero() -> None:
    """La CLI dell'albero registra su una radice sua e rileva un'aggiunta."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = Path(tmp)
        (radice / "a").mkdir()
        (radice / "a" / "uno.txt").write_text("uno\n", encoding="utf-8")
        testimone = radice / "w.yaml"
        record = _cli(
            "--tree", "record", "--tree-root", str(radice), "--paths", "a",
            "--witness", str(testimone),
        )
        pulito = _cli(
            "--tree", "check", "--tree-root", str(radice), "--witness", str(testimone)
        )
        (radice / "a" / "nuovo.txt").write_text("x\n", encoding="utf-8")
        contaminato = _cli(
            "--tree", "check", "--tree-root", str(radice), "--witness", str(testimone)
        )
    check("CLI: tree record", record.returncode == 0, record.stderr[:120])
    check("CLI: tree pulito", pulito.returncode == 0, pulito.stderr[:120])
    check("CLI: tree contamina", contaminato.returncode == 1, contaminato.stdout[:120])


def main() -> int:
    """Run every test."""
    test_pass_chiude_il_gate()
    test_fail_tiene_aperto()
    test_unknown_non_aggrega()
    test_gli_altri_esiti_aperti()
    test_esito_inventato()
    test_evidenza_assente()
    test_produttore_non_e_l_esecutore()
    test_un_gate_aperto_blocca_tutto()
    test_v2_pass_completo()
    test_v2_pass_parziale_blocca()
    test_v2_pass_unknown_blocca()
    test_v2_senza_copertura()
    test_v2_senza_autorita()
    test_copertura_contraddittoria()
    test_legacy_vale_ma_si_dichiara()
    test_legacy_con_copertura_parziale_blocca()
    test_identita_manomessa()
    test_identita_e_proprieta_del_contenuto()
    test_incognita_identita_stabile()
    test_incognita_nuova_e_coerente()
    test_incognita_id_inventato()
    test_incognita_duplicata()
    test_incognita_revisione()
    test_incognita_risolta_senza_prova()
    test_incognita_risolta_con_prova_comparabile()
    test_incognita_autorita_incomparabile()
    test_incognita_resolution_su_voce_aperta()
    test_incognita_registro_round_trip()
    test_bundle_esporta_e_verifica()
    test_bundle_manomesso()
    test_bundle_sigillo_ricalcolato()
    test_bundle_vuoto_rifiutato()
    test_bundle_un_solo_task()
    test_bundle_round_trip_ed_estrazione()
    test_bundle_incognite_coerenti()
    test_bundle_incognita_senza_prova()
    test_collect_ignora_il_registro()
    test_schema2_senza_limiti()
    test_schema2_limiti_vuoti_ma_dichiarati()
    test_legacy_senza_limiti_passa()
    test_limiti_portati_al_chiamante()
    test_misure_schema2_senza_limiti()
    test_misure_limiti_nell_allegato()
    test_misure_legacy_dichiara_l_assenza()
    test_albero_immutato()
    test_albero_modificato_fuori_banda()
    test_albero_aggiunto_e_rimosso()
    test_albero_coperto_da_evidenza()
    test_albero_coperto_da_cartella()
    test_testimone_manomesso()
    test_testimone_esclude_se_stesso()
    test_bundle_con_testimone()
    test_bundle_testimone_manomesso()
    test_bundle_estrae_il_testimone()
    test_cli_incognita_non_e_fail_open()
    test_cli_resolve_non_chiude_con_prova_inventata()
    test_cli_confidenza_assente_non_chiude()
    test_cli_bundle()
    test_cli_albero()
    print(
        f"PASS — {PASSED} controlli su verdetto, evidenza, incognite, bundle, limiti e fuori banda"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
