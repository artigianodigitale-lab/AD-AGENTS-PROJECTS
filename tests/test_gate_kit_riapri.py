#!/usr/bin/env python3
"""Il gate si riapre dopo un REJECT (DEC-0090, `ERR-0082`).

    python3 tests/test_gate_kit_riapri.py

Perche' esiste. Il 2026-11-02 il gate di ENG-017 e' finito in un vicolo cieco: il revisore ha
detto NO trovando un difetto vero, la correzione ha mosso l'albero, `close` ha rifiutato la
revisione mossa e `freeze` ha rifiutato perche' il gate era aperto. Un revisore che fa bene il
suo lavoro bloccava il lavoro.

Qui si prova il ciclo completo in una radice temporanea — nessun contract vero, nessuna
evidenza vera della macchina:

  R1 con evidenza FAIL  ->  freeze --riapri  ->  R2  ->  due evidenze PASS  ->  close

e i casi negativi: riapertura senza FAIL, riapertura su un gate chiuso, riapertura senza
preflight verde.
"""

from __future__ import annotations

import json
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "tools"))

import gate_kit  # noqa: E402

PASSED = 0


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    """Assert one expectation."""
    global PASSED
    if not condizione:
        raise AssertionError(f"{etichetta}: {dettaglio or 'condizione falsa'}")
    PASSED += 1
    print(f"  ok  {etichetta}")


#: Un contract minimo ma valido: il kit legge `status` e il write_scope.
CONTRACT = """
task_id: TST-001
title: "Prova del ciclo di riapertura"
domain: technical
agent: platform
task_type: shared_platform
product: altro
decision_record: "DEC-0000"
objective: "Provare che il gate si riapre dopo un REJECT."
inputs: [requirements]
acceptance_criteria:
  - "il ciclo si chiude"
outputs: [code]
required_gates: [QA, Code Review]
approval:
  human: false
budget:
  max_retries: 2
priority: P0
impact_forecast:
  data: NONE
  schema: NONE
  auth: NONE
  security: NONE
  shared_platform: HIGH
  product: NONE
status: active
write_scope:
  - "uno.txt"
"""

EVIDENZA = """
schema: 2
task_id: TST-001
gate: {gate}
outcome: {outcome}
producer: revisore-di-prova
artifact_producer: platform
timestamp: "{momento}"
coverage:
  status: complete
side_effects:
  code: "NO"
confidence: observed
authority: artifact
references:
  - "prova"
claims:
  "la prova esiste": "VERIFIED"
limitations:
  - "prova"
"""


@contextmanager
def radice_di_prova():
    """Una macchina finta: contract, preflight verde e un file da sorvegliare."""
    with tempfile.TemporaryDirectory() as temporanea:
        radice = Path(temporanea)
        (radice / "contratti" / "societa").mkdir(parents=True)
        (radice / "evidenze").mkdir()
        (radice / "contratti" / "societa" / "TST-001.yaml").write_text(CONTRACT, encoding="utf-8")
        (radice / "uno.txt").write_text("versione uno\n", encoding="utf-8")
        _preflight_verde(radice)
        yield radice


def _preflight_verde(radice: Path) -> None:
    """Un preflight verde e fresco, col legame al contract — come quello vero."""
    (radice / "evidenze" / ".preflight-TST-001.json").write_text(
        json.dumps(
            {
                "task_id": "TST-001",
                "verde": True,
                "contract_sha": gate_kit._sha_contract("TST-001", radice),
                "at": gate_kit.datetime.now(gate_kit.timezone.utc).isoformat(),
            }
        ),
        encoding="utf-8",
    )


def _evidenza(radice: Path, ruolo: str, esito: str, momento: gate_kit.datetime) -> None:
    """Scrive un'evidenza con un `timestamp` esplicito (la freschezza si misura sui file)."""
    nome = gate_kit.evidenze_del_gate("TST-001", radice)[ruolo]
    gate = "QA" if ruolo == "QA" else "Code Review"
    nome.write_text(
        EVIDENZA.format(gate=gate, outcome=esito, momento=momento.isoformat()),
        encoding="utf-8",
    )


def test_ciclo_completo() -> None:
    """R1 FAIL -> --riapri -> R2 -> due PASS -> close."""
    print("\nil ciclo: REJECT, riapertura, chiusura")
    with radice_di_prova() as radice:
        primo = gate_kit.freeze("TST-001", radice)
        check("il gate si apre una volta", primo["revision"] == "R1", primo["revision"])

        # Il revisore dice NO. Poi il fix muove l'albero.
        dopo = gate_kit.datetime.now(gate_kit.timezone.utc) + gate_kit.timedelta(seconds=1)
        _evidenza(radice, "Code Review", "FAIL", dopo)
        (radice / "uno.txt").write_text("versione due, corretta\n", encoding="utf-8")

        problemi = gate_kit.check("TST-001", radice)
        check(
            "con l'albero mosso il gate non si chiude",
            any("uno.txt" in p for p in problemi),
            str(problemi),
        )

        # Senza il flag, freeze rifiuta ancora (la riapertura e' una decisione).
        try:
            gate_kit.freeze("TST-001", radice)
            check("senza --riapri il gate resta chiuso in apertura", False, "nessun rifiuto")
        except gate_kit.GateError as errore:
            check("senza --riapri il gate resta chiuso in apertura", "gia' aperto" in str(errore), str(errore))

        # Con il flag, si riapre: R2, e la R1 resta nel registro.
        secondo = gate_kit.freeze("TST-001", radice, riapri=True)
        check("la riapertura apre R2", secondo["revision"] == "R2", secondo["revision"])
        check("la nota dice che e' una riapertura", "Riaperta dopo un REJECT" in secondo["note"], secondo["note"])
        check("le impronte sono quelle nuove", secondo["files"]["uno.txt"] != primo["files"]["uno.txt"])
        check(
            "la revisione vecchia non e' stata sovrascritta",
            gate_kit._leggi_revisione("TST-001", radice)["revision"] == "R2",
        )
        storia = gate_kit._ledger(radice)["tasks"]["TST-001"]
        check("il registro ha due revisioni", len(storia) == 2, str(storia))
        check("la prima e' R1", storia[0]["revision"] == "R1", str(storia))
        check("la seconda dice di essere stata riaperta", storia[1].get("riaperta_dopo_reject") is True, str(storia[1]))

        # Ora le due evidenze PASS, posteriori al congelamento.
        adesso = gate_kit.datetime.now(gate_kit.timezone.utc) + gate_kit.timedelta(seconds=2)
        _evidenza(radice, "QA", "PASS", adesso)
        _evidenza(radice, "Code Review", "PASS", adesso)
        chiuso = gate_kit.close("TST-001", radice)
        check("il gate si chiude", chiuso.get("gate") == "closed", str(chiuso.get("gate")))


def test_riapertura_senza_fail() -> None:
    """Non si riapre un gate che nessuno ha respinto."""
    print("\nnon si riapre senza un FAIL")
    with radice_di_prova() as radice:
        gate_kit.freeze("TST-001", radice)
        adesso = gate_kit.datetime.now(gate_kit.timezone.utc) + gate_kit.timedelta(seconds=1)
        _evidenza(radice, "QA", "PASS", adesso)
        try:
            gate_kit.freeze("TST-001", radice, riapri=True)
            check("un gate senza FAIL non si riapre", False, "nessun rifiuto")
        except gate_kit.GateError as errore:
            check("un gate senza FAIL non si riapre", "FAIL" in str(errore), str(errore))
            check("il rifiuto dice come rimediare o perche'", len(str(errore)) > 40, str(errore))


def test_riapertura_su_gate_chiuso() -> None:
    """Un gate chiuso non si riapre: un lavoro nuovo vuole un task nuovo."""
    print("\nnon si riapre un gate chiuso")
    with radice_di_prova() as radice:
        gate_kit.freeze("TST-001", radice)
        adesso = gate_kit.datetime.now(gate_kit.timezone.utc) + gate_kit.timedelta(seconds=1)
        _evidenza(radice, "QA", "PASS", adesso)
        _evidenza(radice, "Code Review", "PASS", adesso)
        gate_kit.close("TST-001", radice)
        try:
            gate_kit.freeze("TST-001", radice, riapri=True)
            check("un gate chiuso non si riapre", False, "nessun rifiuto")
        except gate_kit.GateError as errore:
            check("un gate chiuso non si riapre", "gia' chiuso" in str(errore), str(errore))


def test_riapertura_senza_preflight() -> None:
    """Senza un preflight verde, nemmeno la riapertura passa."""
    print("\nsenza preflight verde non si riapre")
    with radice_di_prova() as radice:
        gate_kit.freeze("TST-001", radice)
        adesso = gate_kit.datetime.now(gate_kit.timezone.utc) + gate_kit.timedelta(seconds=1)
        _evidenza(radice, "Code Review", "FAIL", adesso)
        (radice / "evidenze" / ".preflight-TST-001.json").unlink()
        try:
            gate_kit.freeze("TST-001", radice, riapri=True)
            check("senza preflight la riapertura e' rifiutata", False, "nessun rifiuto")
        except gate_kit.GateError as errore:
            check("senza preflight la riapertura e' rifiutata", "preflight" in str(errore), str(errore))


def main() -> int:
    """Run the suite."""
    print("gate kit: la riapertura dopo un REJECT (DEC-0090)")
    test_ciclo_completo()
    test_riapertura_senza_fail()
    test_riapertura_su_gate_chiuso()
    test_riapertura_senza_preflight()
    print(f"PASS — {PASSED} controlli sulla riapertura")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
