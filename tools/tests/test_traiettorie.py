#!/usr/bin/env python3
"""Il flight recorder misura l'apprendimento, e una regressione fa rosso (M6, `DEC-0118`).

Si prova il comportamento su una **fixture sintetica** con numeri attesi, non sul repo reale:
  - uno standard chiuso con un gate al secondo tentativo (non primo colpo) e uno al primo;
  - un contract attivo con un gate al primo colpo (ma il contract resta aperto);
  - tre errori: due diventati controllo e con la terza domanda, uno no.
Attesi: primo colpo 2/3 = 66,7%; lezioni→controlli 66,7%; terza domanda 66,7%;
gate aperti 1; errori collegati 2; per task chiuso 1,0 (due task chiusi, uno con la grafia
storica `chiuso`).

Poi: baseline mancante → rosso; `--aggiorna` → verde; baseline peggiorata → rosso;
e il repo reale produce metriche coerenti con la baseline committata.

Si esegue dalla radice:
    python3 tools/tests/test_traiettorie.py
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE / "tools"))

import traiettorie  # noqa: E402

FALLITI: list[str] = []
PASSATI = 0


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    global PASSATI
    if condizione:
        print(f"  ok   {etichetta}")
        PASSATI += 1
    else:
        print(f"  NO   {etichetta}  {dettaglio}")
        FALLITI.append(etichetta)


def _scrivi(percorso: Path, testo: str) -> None:
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_text(testo, encoding="utf-8")


def _fixture(base: Path) -> None:
    _scrivi(base / "contratti" / "societa" / "ENG-1.yaml", """
task_id: ENG-1
status: closed
aperto: "2026-11-01"
chiuso: "2026-11-02"
required_gates: [QA, CodeReview]
""")
    _scrivi(base / "contratti" / "societa" / "ENG-2.yaml", """
task_id: ENG-2
status: active
aperto: "2026-11-03"
required_gates: [QA]
""")
    # Un contratto storico che dice `status: chiuso` (non `closed`): e' chiuso lo stesso.
    _scrivi(base / "contratti" / "societa" / "ENG-3.yaml", """
task_id: ENG-3
status: chiuso
aperto: "2026-10-01"
chiuso: "2026-10-02"
required_gates: []
""")
    _scrivi(base / "evidenze" / "ENG-1-QA-1.yaml", """
task_id: ENG-1
gate: QA
outcome: FAIL
timestamp: "2026-11-01T10:00:00+01:00"
""")
    _scrivi(base / "evidenze" / "ENG-1-QA-2.yaml", """
task_id: ENG-1
gate: QA
outcome: PASS
timestamp: "2026-11-01T11:00:00+01:00"
""")
    _scrivi(base / "evidenze" / "ENG-1-CR-1.yaml", """
task_id: ENG-1
gate: CodeReview
outcome: PASS
timestamp: "2026-11-01T11:30:00+01:00"
""")
    _scrivi(base / "evidenze" / "ENG-2-QA-1.yaml", """
task_id: ENG-2
gate: QA
outcome: PASS
timestamp: "2026-11-03T09:00:00+01:00"
""")
    _scrivi(base / "errori" / "ERR-1.yaml", """
id: ERR-1
diventa: controllo
cosa_l_avrebbe_preso: "un test che prova il caso"
riferimenti: ["ENG-1", "tools/x.py"]
""")
    _scrivi(base / "errori" / "ERR-2.yaml", """
id: ERR-2
diventa: controllo
cosa_l_avrebbe_preso: "un controllo in sicurezza.py"
riferimenti: ["ENG-1"]
""")
    _scrivi(base / "errori" / "ERR-3.yaml", """
id: ERR-3
diventa: nota
cosa_l_avrebbe_preso: ""
riferimenti: ["piani/x.md"]
""")


def test_fixture() -> None:
    print("\nla fixture: i numeri attesi")
    with tempfile.TemporaryDirectory(prefix="ad-traiettorie-") as tmp:
        base = Path(tmp)
        _fixture(base)
        esito = traiettorie.analizza(base)
        m = esito["metriche"]
        check("task chiusi 2/3 (uno dice chiuso)", m["task_chiusi"] == 2 and m["contratti_totali"] == 3, str(m))
        check("gate richiesti 3", m["gate_richiesti"] == 3, str(m))
        check("gate aperti 1", m["gate_aperti"] == 1, str(m))
        check("gate valutati 3", m["gate_valutati"] == 3, str(m))
        check("primo colpo 66.7%", m["primo_colpo_percento"] == 66.7, str(m))
        check("errori 3", m["errori_registrati"] == 3, str(m))
        check("lezioni->controlli 66.7%", m["lezioni_controllo_percento"] == 66.7, str(m))
        check("terza domanda 66.7%", m["terza_domanda_percento"] == 66.7, str(m))
        check("errori collegati 2", m["errori_collegati"] == 2, str(m))
        check("errori per task chiuso 1.0", m["errori_per_task_chiuso"] == 1.0, str(m))
        traiettorie_voci = {t["task_id"]: t for t in esito["traiettorie"]}
        check("la traiettoria di ENG-1 ha due tentativi su QA",
              traiettorie_voci["ENG-1"]["gate"][0]["tentativi"] == 2, str(traiettorie_voci["ENG-1"]))
        check("ENG-2 e' aperto", traiettorie_voci["ENG-2"]["status"] == "active", str(traiettorie_voci["ENG-2"]))
        check("le definizioni sono dichiarate", "primo_colpo" in esito["definizioni"], str(esito["definizioni"]))

        print("\nil confronto con la baseline")
        mancante = traiettorie.confronta(base)
        check("baseline mancante e' ROSSO, non verde", mancante["ok"] is False and "mancante" in mancante["motivo"],
              str(mancante))
        creata = traiettorie.confronta(base, aggiorna=True)
        check("--aggiorna crea la baseline", creata["aggiornata"] is True and (base / "evals" / "traiettorie" / "baseline.json").is_file())
        verde = traiettorie.confronta(base)
        check("con la baseline attuale e' verde", verde["ok"] is True, str(verde))
        baseline_path = base / "evals" / "traiettorie" / "baseline.json"
        dati = json.loads(baseline_path.read_text(encoding="utf-8"))
        dati["metriche"]["primo_colpo_percento"] = 90.0
        baseline_path.write_text(json.dumps(dati), encoding="utf-8")
        peggiore = traiettorie.confronta(base)
        check("una metrica peggiorata fa ROSSO", peggiore["ok"] is False and peggiore["regressioni"], str(peggiore))
        cattura = io.StringIO()
        with contextlib.redirect_stdout(cattura):
            codice = traiettorie.main(["confronta"], radice=base)
        testo_cli = cattura.getvalue()
        check("la CLI della regressione esce 1 e non va in crash",
              codice == 1 and "regressione" in testo_cli, f"exit={codice} out={testo_cli!r}")
        dati["metriche"]["primo_colpo_percento"] = 66.7
        baseline_path.write_text(json.dumps(dati), encoding="utf-8")
        check("la stessa metrica non e' una regressione", traiettorie.confronta(base)["ok"] is True)


def test_reale() -> None:
    print("\nil repo reale: numeri coerenti e baseline committata")
    esito = traiettorie.analizza(RADICE)
    m = esito["metriche"]
    if m["task_chiusi"] == 0:
        print("  skip  nessun task chiuso (kit nuovo): il confronto con la baseline richiede storia")
        return
    check("ci sono task chiusi", m["task_chiusi"] > 0, str(m))
    check("gate richiesti > 0", m["gate_richiesti"] > 0, str(m))
    for nome in ("primo_colpo_percento", "lezioni_controllo_percento", "terza_domanda_percento"):
        check(f"{nome} fra 0 e 100", 0 <= m[nome] <= 100, str(m[nome]))
    check("errori registrati > 0", m["errori_registrati"] > 0, str(m))
    check("la baseline esiste", (RADICE / "evals" / "traiettorie" / "baseline.json").is_file())
    confronto = traiettorie.confronta(RADICE)
    check("il confronto con la baseline e' verde", confronto["ok"] is True, str(confronto)[:300])


def main() -> int:
    test_fixture()
    test_reale()
    print()
    print(f"  {PASSATI} controlli passati")
    if FALLITI:
        print(f"FALLITI: {len(FALLITI)}")
        return 1
    print("PASS — il flight recorder misura, e una regressione fa rosso")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
