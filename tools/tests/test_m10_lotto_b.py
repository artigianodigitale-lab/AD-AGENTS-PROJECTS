#!/usr/bin/env python3
"""Lotto B di M10: le cinque guardie finali (`DEC-0124`, `ENG-060`).

  1. `ERR-0068` — un vincolo «non si modifica» che contraddice criteri di correzione.
  2. `ERR-0022` — gli orari nel futuro dentro le evidenze dei progetti.
  3. `DRIFT-013` — un contract attivo su una tappa che dichiara di essere chiusa.
  4. `ERR-0049` — il test dell'ambito shell non legge piu' il mondo.
  5. `ERR-0073` — la regola degli orari UTC e' scritta.

    python3 tools/tests/test_m10_lotto_b.py
"""

from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE / "tools"))

import ad_coherence  # noqa: E402
import ad_contract  # noqa: E402

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


def main() -> int:
    print("ERR-0068 — un vincolo contro i criteri")
    positivo = ad_contract.rilievi_vincoli({
        "task_id": "TST",
        "acceptance_criteria": ["typecheck 0 errori", "le misure sono verdi"],
        "constraints": ["il codice del modulo non si modifica"],
    })
    check("il contract contraddittorio e' segnalato", len(positivo) == 1, str(positivo))
    if positivo:
        check("il codice e' vincolo-contro-criteri", positivo[0][0] == "vincolo-contro-criteri")
    negativo = ad_contract.rilievi_vincoli({
        "task_id": "TST",
        "acceptance_criteria": ["il foglio esiste"],
        "constraints": ["il codice del modulo non si modifica"],
    })
    check("senza criteri di correzione non e' un rilievo", negativo == [], str(negativo))

    print("\nERR-0022 — orari nelle evidenze dei progetti")
    with tempfile.TemporaryDirectory(prefix="ad-lotto-b-") as tmp:
        radice = Path(tmp)
        progetto = radice / "Progetti" / "1. Prova"
        (progetto / "governance" / "evidenze").mkdir(parents=True)
        adesso = datetime(2026, 11, 17, 7, 0, tzinfo=timezone.utc)
        futuro = (adesso + timedelta(days=2)).isoformat(timespec="seconds")
        (progetto / "governance" / "evidenze" / "TST-QA.yaml").write_text(
            f"task_id: TST\ntimestamp: {futuro}\noutcome: PASS\n", encoding="utf-8"
        )
        trovati = ad_coherence.orari_nei_progetti(
            radice, adesso=adesso, progetti=radice / "Progetti"
        )
        check("l'orario nel futuro dentro il progetto e' segnalato", len(trovati) == 1, str(trovati))

        (progetto / "governance" / "evidenze" / "TST-QA.yaml").write_text(
            "task_id: TST\ntimestamp: 2026-11-16T07:00:00+00:00\noutcome: PASS\n",
            encoding="utf-8",
        )
        trovati = ad_coherence.orari_nei_progetti(
            radice, adesso=adesso, progetti=radice / "Progetti"
        )
        check("un orario passato non e' un rilievo", trovati == [], str(trovati))

    print("\nDRIFT-013 — permesso attivo su tappa chiusa")
    with tempfile.TemporaryDirectory(prefix="ad-lotto-b-") as tmp:
        radice = Path(tmp)
        contratti = radice / "contratti" / "societa"
        contratti.mkdir(parents=True)
        progetto = radice / "Progetti" / "1. Prova"
        (progetto / "Analisi-Prompt-Report" / "Milestone 1").mkdir(parents=True)
        (progetto / "Analisi-Prompt-Report" / "Milestone 1" / "REPORT.md").write_text(
            "# Milestone 1\n\n```yaml\nstato: chiusa\n```\n", encoding="utf-8"
        )
        (contratti / "TST-900.yaml").write_text(
            "task_id: TST-900\nstatus: active\nmilestone: 1\nwrite_scope:\n"
            '  - "1. Prova/Analisi-Prompt-Report/Milestone 1/"\n',
            encoding="utf-8",
        )
        trovati = ad_coherence.tappe_chiuse_con_permessi(
            radice, progetti=radice / "Progetti"
        )
        check("il permesso attivo sulla tappa chiusa e' segnalato", len(trovati) == 1, str(trovati))
        check("il messaggio dice di chiuderlo o rinnovarlo", "chiudilo o rinnovalo" in trovati[0])

        # Un'eccezione dichiarata tace; un caso nuovo parla.
        trovati = ad_coherence.tappe_chiuse_con_permessi(
            radice, progetti=radice / "Progetti", eccezioni={"TST-900": "dichiarato"}
        )
        check("l'eccezione dichiarata e' rispettata", trovati == [], str(trovati))

        (progetto / "Analisi-Prompt-Report" / "Milestone 1" / "REPORT.md").write_text(
            "# Milestone 1\n\n```yaml\nstato: aperta\n```\n", encoding="utf-8"
        )
        trovati = ad_coherence.tappe_chiuse_con_permessi(
            radice, progetti=radice / "Progetti"
        )
        check("una tappa aperta non e' un rilievo", trovati == [], str(trovati))

    print("\nERR-0049 — il test dell'ambito shell non legge il mondo")
    sorgente_test = (RADICE / "tools" / "tests" / "test_ad_org.py").read_text(encoding="utf-8")
    inizio = sorgente_test.find("def test_bash_scope")
    fine = sorgente_test.find("def test_milestone", inizio)
    funzione = sorgente_test[inizio:fine]
    check("non legge piu' il progetto reale",
          'Path(root) / "13. Commercialista' not in funzione)
    check("costruisce la sua radice (TemporaryDirectory + progetto finto)",
          "ad-shell-" in sorgente_test and "13. Progetto Di Prova" in sorgente_test)

    print("\nERR-0073 — la regola degli orari UTC e' scritta")
    avvio = (RADICE / "orchestrazione" / "AVVIO-PROGETTO.md").read_text(encoding="utf-8")
    check("la regola UTC e' nel documento", "UTC" in avvio)
    check("dice che l'orario nel futuro e' un errore", "orario nel futuro e' un errore" in avvio)

    print()
    print(f"  {PASSATI} controlli passati")
    if FALLITI:
        print(f"FALLITI: {len(FALLITI)}")
        return 1
    print("PASS — le cinque guardie del lotto B mordono")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
