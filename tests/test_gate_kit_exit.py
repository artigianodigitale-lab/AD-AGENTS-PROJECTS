#!/usr/bin/env python3
"""Gli exit code normativi di `gate_kit check` (`DEC-0105`).

Perche' esiste. `piani/2026-11-02-review-governance-v2.md` §5.2 dichiara quattro codici:

    0  revisione valida e immobile
    1  errore o violazione del gate (contract, preflight, ledger)
    2  snapshot modificato — revisione invalidata
    3  evidenze mancanti o non verificabili

E dice che sono **normativi**: `ci.py` e il pre-commit li trattano come errori, non come
avvisi. Ma il CLI restituiva `1` per qualunque problema: la distinzione era scritta e non
esisteva. `ENG-021` prometteva `tests/test_gate_kit_exit.py` — questo file — e non c'era.

La differenza conta per chi chiama: con `1` non sa se rifare il congelamento (`2`) o
recuperare un'evidenza (`3`). Sono due lavori diversi.

Si esegue dalla radice:
    python3 tests/test_gate_kit_exit.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RADICE / "tests"))

import gate_kit  # noqa: E402

FALLITI: list[str] = []


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    if condizione:
        print(f"  ok   {etichetta}")
    else:
        print(f"  NO   {etichetta}  {dettaglio}")
        FALLITI.append(etichetta)


def _macchina(radice: Path) -> Path:
    """Una macchina minima: un contract attivo con un file da congelare."""
    for cartella in ("contratti/societa", "evidenze", "drift", "errori"):
        (radice / cartella).mkdir(parents=True, exist_ok=True)
    (radice / "contratto.txt").write_text("contenuto\n", encoding="utf-8")
    (radice / "contratti" / "societa" / "TEST-001.yaml").write_text(
        "task_id: TEST-001\nstatus: active\nacceptance_criteria:\n  - 'criterio'\n"
        "write_scope:\n  - contratto.txt\n",
        encoding="utf-8",
    )
    return radice


def _stamp(radice: Path) -> None:
    """Il timbro del preflight, nel formato che il preflight vero scrive.

    I campi sono quattro e vanno tutti: `task_id`, `contract_sha` (l'impronta del
    contract **al momento** del preflight), `verde`, `at`. Un timbro senza
    `contract_sha` non e' un timbro — e' un file che dice «ok».
    """
    import json
    from datetime import datetime, timezone

    dati = {
        "task_id": "TEST-001",
        "contract_sha": gate_kit._sha_contract("TEST-001", radice),
        "verde": True,
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    gate_kit.preflight_path("TEST-001", radice).write_text(json.dumps(dati), encoding="utf-8")


def _evidenze(radice: Path) -> None:
    """Le due evidenze complete: schema 2, con tutti i campi che il kit pretende."""
    for ruolo in ("QA", "CodeReview"):
        (radice / "evidenze" / f"TEST-001-{ruolo}.yaml").write_text(
            "schema: 2\n"
            "task_id: TEST-001\n"
            f"gate: {ruolo}\n"
            "outcome: PASS\n"
            f"producer: {ruolo.lower()}\n"
            "confidence: observed\n"
            "authority: execution\n"
            "coverage: {status: complete, examined: 1, total: 1}\n"
            "limitations:\n  - 'nessuna'\n"
            "side_effects: {code: YES, database: NO, schema: NO, deps: NO, env: NO, external_services: NO}\n",
            encoding="utf-8",
        )


def test_esito_zero_revisione_immobile() -> None:
    """0 — la revisione e' valida e non si e' mossa."""
    print("\n0 — revisione immobile")
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp))
        _stamp(radice)
        gate_kit.freeze("TEST-001", radice)
        problemi = gate_kit.check("TEST-001", radice)
        check("nessun problema", not problemi, str(problemi))
        check("esito 0", gate_kit.esito_dei_problemi(problemi) == 0, str(problemi))


def test_esito_due_snapshot_modificato() -> None:
    """2 — un file del write_scope e' cambiato: la revisione e' invalidata."""
    print("\n2 — snapshot modificato")
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp))
        _stamp(radice)
        gate_kit.freeze("TEST-001", radice)
        (radice / "contratto.txt").write_text("cambiato\n", encoding="utf-8")
        problemi = gate_kit.check("TEST-001", radice)
        esito = gate_kit.esito_dei_problemi(problemi)
        check("il problema e' rilevato", bool(problemi), str(problemi))
        check("esito 2, non 1", esito == 2, f"esito {esito}: {problemi}")


def test_esito_tre_evidenze_mancanti() -> None:
    """3 — manca un'evidenza: non si puo' giudicare."""
    print("\n3 — evidenze mancanti")
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp))
        _stamp(radice)
        gate_kit.freeze("TEST-001", radice)
        _evidenze(radice)
        gate_kit.close("TEST-001", radice)
        (radice / "evidenze" / "TEST-001-QA.yaml").unlink()
        problemi = gate_kit.check("TEST-001", radice)
        esito = gate_kit.esito_dei_problemi(problemi)
        check("il problema e' rilevato", bool(problemi), str(problemi))
        check("esito 3", esito == 3, f"esito {esito}: {problemi}")


def test_esito_uno_guasto_del_gate() -> None:
    """1 — un guasto del gate: contract assente, revisione non congelata."""
    print("\n1 — guasto del gate")
    with tempfile.TemporaryDirectory() as tmp:
        radice = _macchina(Path(tmp))
        problemi = gate_kit.check("TEST-001", radice)
        esito = gate_kit.esito_dei_problemi(problemi)
        check("il problema e' rilevato", bool(problemi), str(problemi))
        check("esito 1, non 2", esito == 1, f"esito {esito}: {problemi}")


def test_tre_vince_su_due() -> None:
    """Con due famiglie diverse si dice quella che chiede piu' lavoro: l'evidenza.

    Un'evidenza mancante impedisce di giudicare; un file mosso lascia la revisione
    leggibile. Chiedere l'evidenza e' il primo passo, quindi l'ordine e' 3 poi 2.
    """
    print("\nle due famiglie insieme")
    esito = gate_kit.esito_dei_problemi(["MOSSO contratto.txt", "EVIDENZA SPARITA dopo la chiusura: QA"])
    check("esito 3, non 2", esito == 3, str(esito))


def test_il_cli_restituisce_il_codice() -> None:
    """Il CLI esce davvero con quel codice, non solo la funzione.

    Una funzione giusta che il `main` non usa e' esattamente la promessa non mantenuta
    che questo file esiste per chiudere: `ENG-021` dichiarava i quattro codici, e il
    CLI ne restituiva uno.

    La prova e' deterministica perche' si esegue su un gate **reale** di cui conosciamo
    l'esito: `ENG-022` e' chiuso e immobile, quindi deve uscire `0`. Accettare «0 o 1»
    non proverebbe niente — sarebbe la soglia sotto il valore vero, il difetto che ho
    gia' commesso tre volte.
    """
    print("\nil CLI esce col codice")
    esito = subprocess.run(
        [sys.executable, str(RADICE / "tests" / "gate_kit.py"), "check", "ENG-022"],
        cwd=str(RADICE),
        capture_output=True,
        text=True,
        timeout=120,
    )
    check(
        "un gate chiuso e immobile -> 0",
        esito.returncode == 0,
        f"uscita {esito.returncode}: {(esito.stdout + esito.stderr)[:200]}",
    )

    # E un task che non esiste: la revisione non c'e', quindi e' un guasto del gate (1),
    # non un albero mosso (2).
    esito_mancante = subprocess.run(
        [sys.executable, str(RADICE / "tests" / "gate_kit.py"), "check", "NON-ESISTE-999"],
        cwd=str(RADICE),
        capture_output=True,
        text=True,
        timeout=120,
    )
    check(
        "un task senza revisione -> 1, non 2",
        esito_mancante.returncode == 1,
        f"uscita {esito_mancante.returncode}: {(esito_mancante.stdout + esito_mancante.stderr)[:200]}",
    )


def test_i_codici_sono_distinti() -> None:
    """I quattro codici devono essere quattro valori diversi."""
    print("\ni quattro codici")
    codici = {
        gate_kit.ESITO_IMMOBILE,
        gate_kit.ESITO_ERRORE,
        gate_kit.ESITO_MOSSO,
        gate_kit.ESITO_EVIDENZE,
    }
    check("sono quattro", len(codici) == 4, str(sorted(codici)))
    check(
        "sono 0, 1, 2, 3",
        codici == {0, 1, 2, 3},
        str(sorted(codici)),
    )


def main() -> int:
    print("gli exit code normativi di gate_kit")
    test_esito_zero_revisione_immobile()
    test_esito_due_snapshot_modificato()
    test_esito_tre_evidenze_mancanti()
    test_esito_uno_guasto_del_gate()
    test_tre_vince_su_due()
    test_il_cli_restituisce_il_codice()
    test_i_codici_sono_distinti()
    print()
    if FALLITI:
        print(f"FALLITO — {len(FALLITI)} controlli: " + ", ".join(FALLITI))
        return 1
    print("PASS — i quattro codici sono distinti, e il CLI li restituisce")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
