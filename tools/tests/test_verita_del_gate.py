#!/usr/bin/env python3
"""Il contract non si muove a gate aperto (`ERR-0083`, `ERR-0084`, `DEC-0121`).

Prima: il kit rilevava il movimento, il validatore lo accettava. Un agente poteva cambiare i
criteri di accettazione a gate aperto e il gate chiudeva su un documento diverso da quello che
il revisore aveva in mano. Ora `ad_contract.validate` rifiuta.

Si prova su una radice finta: contract + revisione di congelamento, con le impronte dei file.

    python3 tools/tests/test_verita_del_gate.py
"""

from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path

import yaml

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE / "tools"))

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


def _scrivi_contract(base: Path, criterio: str = "la prova esiste") -> Path:
    cartella = base / "contratti" / "societa"
    cartella.mkdir(parents=True)
    percorso = cartella / "TST-001.yaml"
    percorso.write_text(
        yaml.safe_dump(
            {
                "task_id": "TST-001",
                "status": "active",
                "agent": "platform",
                "acceptance_criteria": [criterio],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return percorso


def _congela(base: Path, percorso: Path) -> Path:
    evidenze = base / "evidenze"
    evidenze.mkdir(parents=True)
    revisione = evidenze / "TST-001-revisione.yaml"
    revisione.write_text(
        yaml.safe_dump(
            {
                "tool": "gate_kit",
                "task_id": "TST-001",
                "gate": "open",
                "files": {
                    "contratti/societa/TST-001.yaml": hashlib.sha256(
                        percorso.read_bytes()
                    ).hexdigest()
                },
            }
        ),
        encoding="utf-8",
    )
    return revisione


def main() -> int:
    print("il contract fermo al congelamento")
    with tempfile.TemporaryDirectory(prefix="ad-gate-verita-") as tmp:
        base = Path(tmp)
        percorso = _scrivi_contract(base)
        _congela(base, percorso)
        dati = ad_contract.load(percorso)
        codice, messaggio = ad_contract.contract_mosso(dati, root=base)
        check("contract identico: nessun blocco", codice is None and not messaggio, str(messaggio))

    print("\nil contract modificato a gate aperto")
    with tempfile.TemporaryDirectory(prefix="ad-gate-verita-") as tmp:
        base = Path(tmp)
        percorso = _scrivi_contract(base)
        _congela(base, percorso)
        # Il contract cambia: i criteri non sono piu' quelli che il revisore ha letto.
        testo = percorso.read_text(encoding="utf-8").replace(
            "la prova esiste", "la prova e' bella"
        )
        percorso.write_text(testo, encoding="utf-8")
        dati = ad_contract.load(percorso)
        codice, messaggio = ad_contract.contract_mosso(dati, root=base)
        check("contract cambiato: BLOCCO", codice == "block", str(codice))
        check("il messaggio dice che e' cambiato dopo il congelamento",
              "cambiato DOPO il congelamento" in messaggio, messaggio[:160])
        check("il messaggio dice come uscirne (freeze --riapri)",
              "freeze TST-001 --riapri" in messaggio, messaggio[-160:])

        # La guardia deve stare nel PERCORSO DI PRODUZIONE, non solo nella funzione:
        # fino a qui il test chiamava `contract_mosso` direttamente e togliere la
        # chiamata da `validate()` non faceva fallire niente (trovato dalla revisione
        # indipendente di ENG-057). Ora si prova `validate()`.
        codici = {f.code for f in ad_contract.validate(dati, {}, root=base)}
        check("validate() di produzione produce la violazione contract-mosso",
              "contract-mosso" in codici, str(sorted(codici))[:300])

        # --- e non si aggira col nome del file -------------------------------
        # Rinominare il contract a gate aperto non deve spegnere la guardia.
    print("\nla guardia non si aggira rinominando il file")
    with tempfile.TemporaryDirectory(prefix="ad-gate-verita-") as tmp:
        base = Path(tmp)
        percorso = _scrivi_contract(base)
        _congela(base, percorso)
        rinominato = percorso.with_name("TST-001-bis.yaml")
        percorso.rename(rinominato)
        codice, messaggio = ad_contract.contract_mosso(
            ad_contract.load(rinominato), root=base
        )
        check("contract rinominato a gate aperto: BLOCCO", codice == "block", str(codice))
        check("il messaggio nomina il percorso apparso dopo",
              "non era fra i file congelati" in messaggio, messaggio[:160])

    print("\ndue contract con lo stesso task_id")
    with tempfile.TemporaryDirectory(prefix="ad-gate-verita-") as tmp:
        base = Path(tmp)
        percorso = _scrivi_contract(base)
        _congela(base, percorso)
        copia = base / "contratti" / "societa" / "TST-001-copia.yaml"
        copia.write_text(percorso.read_text(encoding="utf-8"), encoding="utf-8")
        codice, messaggio = ad_contract.contract_mosso(ad_contract.load(percorso), root=base)
        check("due titolari: BLOCCO (registro ambiguo)", codice == "block", str(codice))
        check("il messaggio dice che la guardia non sa quale sia il congelato",
              "stesso task_id" in messaggio, messaggio[:160])

    print("\nle eccezioni sono dichiarate, non silenziose")
    with tempfile.TemporaryDirectory(prefix="ad-gate-verita-") as tmp:
        base = Path(tmp)
        percorso = _scrivi_contract(base)
        _congela(base, percorso)
        # Un contract nuovo (senza revisione) non e' "mosso": il gate non e' mai stato aperto.
        altro = base / "contratti" / "societa" / "TST-002.yaml"
        altro.write_text(
            yaml.safe_dump({"task_id": "TST-002", "status": "active"}), encoding="utf-8"
        )
        codice, _ = ad_contract.contract_mosso(ad_contract.load(altro), root=base)
        check("contract senza revisione: nessun blocco (gate mai aperto)", codice is None)
        # A gate chiuso non si applica: la chiusura e' il mestiere di `gate_status`.
        revisione = base / "evidenze" / "TST-001-revisione.yaml"
        dati_rev = yaml.safe_load(revisione.read_text(encoding="utf-8"))
        dati_rev["gate"] = "closed"
        revisione.write_text(yaml.safe_dump(dati_rev), encoding="utf-8")
        percorso.write_text(percorso.read_text(encoding="utf-8") + "\n# cambiato\n", encoding="utf-8")
        codice, _ = ad_contract.contract_mosso(ad_contract.load(percorso), root=base)
        check("gate chiuso: la guardia sul movimento non si applica", codice is None)

    print()
    print(f"  {PASSATI} controlli passati")
    if FALLITI:
        print(f"FALLITI: {len(FALLITI)}")
        return 1
    print("PASS — il contract non si cambia sotto il gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
