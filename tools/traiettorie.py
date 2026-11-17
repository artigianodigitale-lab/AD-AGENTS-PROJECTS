#!/usr/bin/env python3
"""Il flight recorder del motore: le traiettorie diventano numeri (M6, `DEC-0118`).

Perche' esiste. Il motore scrive gia' tutto: contratti (cosa era autorizzato), evidenze
(tentativi e gate), errori (le cicatrici con «cosa lo avrebbe preso»), chiusure. Ma nessuno
ricompone questa storia ne' misura se il sistema **sta imparando**. Senza numeri,
«autoapprendimento» e' una parola.

Cosa misura, con definizioni dichiarate:
  - **primo colpo %**: gate la cui ultima evidenza e' PASS e che non ha nessun FAIL/REJECT
    prima. Un gate senza evidenze non e' ne' primo colpo ne' successo: non conta.
  - **lezioni -> controlli %**: errori con `diventa: controllo` sul totale degli errori.
  - **terza domanda %**: errori con `cosa_l_avrebbe_preso` compilato.
  - **errori collegati** e **per task chiuso**: errori i cui riferimenti nominano un task.
  - **gate aperti** e **task chiusi**: lo stato del lavoro.

Il confronto con `evals/traiettorie/baseline.json` dice se una metrica e' **peggiorata** oltre
la tolleranza dichiarata: allora il confronto e' rosso. `--aggiorna` e' una firma esplicita,
non un tasto: aggiornare la baseline senza guardare cancella la regressione.

Uso:
    python3 tools/traiettorie.py analizza [--json]
    python3 tools/traiettorie.py confronta [--aggiorna] [--json]

Esiti: 0 ok, 1 regressione o baseline mancante, 2 uso sbagliato.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

RADICE = Path(__file__).resolve().parents[1]
BASELINE = RADICE / "evals" / "traiettorie" / "baseline.json"
TOLLERANZA_PUNTI = 5.0  # punti percentuali: sotto questa soglia non e' una regressione
#: Metriche in cui «piu' alto e' meglio» (le altre si leggono e basta nel report).
METRICHE_CRESCENTI = ("primo_colpo_percento", "lezioni_controllo_percento", "terza_domanda_percento")


def _leggi_yaml(percorso: Path) -> dict[str, Any]:
    try:
        dati = yaml.safe_load(percorso.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    return dati if isinstance(dati, dict) else {}


def _contratti(radice: Path) -> list[dict[str, Any]]:
    contratti = []
    cartella = radice / "contratti"
    if not cartella.is_dir():
        return contratti
    for percorso in sorted(cartella.rglob("*.yaml")):
        dati = _leggi_yaml(percorso)
        if not dati.get("task_id"):
            continue
        contratti.append({
            "task_id": str(dati["task_id"]),
            "gates": [str(g) for g in (dati.get("required_gates") or [])],
            "status": str(dati.get("status") or ""),
            "aperto": str(dati.get("aperto") or ""),
            "chiuso": str(dati.get("chiuso") or ""),
            "file": str(percorso.relative_to(radice)),
        })
    return contratti


def _evidenze(radice: Path) -> list[dict[str, Any]]:
    evidenze = []
    cartella = radice / "evidenze"
    if not cartella.is_dir():
        return evidenze
    for percorso in sorted(cartella.glob("*.yaml")):
        dati = _leggi_yaml(percorso)
        if not dati.get("task_id") or not dati.get("gate"):
            continue
        evidenze.append({
            "task_id": str(dati["task_id"]),
            "gate": str(dati["gate"]),
            "outcome": str(dati.get("outcome") or "").upper(),
            "timestamp": str(dati.get("timestamp") or ""),
            "file": str(percorso.relative_to(radice)),
        })
    return evidenze


def _errori(radice: Path) -> list[dict[str, Any]]:
    errori = []
    cartella = radice / "errori"
    if not cartella.is_dir():
        return errori
    for percorso in sorted(cartella.glob("*.yaml")):
        dati = _leggi_yaml(percorso)
        if not dati.get("id"):
            continue
        terza = str(dati.get("cosa_l_avrebbe_preso") or "").strip()
        errori.append({
            "id": str(dati["id"]),
            "diventa": str(dati.get("diventa") or "").strip(),
            "trovato_da": str(dati.get("trovato_da") or "").strip(),
            "terza_domanda": bool(terza),
            "riferimenti": [str(r) for r in (dati.get("riferimenti") or [])],
            "file": str(percorso.relative_to(radice)),
        })
    return errori


def _chiuso(contratto: dict[str, Any]) -> bool:
    """Alcuni contract storici dicono `status: chiuso`, i nuovi `closed`: sono la stessa cosa."""
    return contratto["status"].strip().lower() in ("closed", "chiuso")


def analizza(radice: Path = RADICE) -> dict[str, Any]:
    contratti = _contratti(radice)
    evidenze = _evidenze(radice)
    errori = _errori(radice)

    task_chiusi = sum(1 for c in contratti if _chiuso(c))
    gate_richiesti = sum(len(c["gates"]) for c in contratti)
    gate_aperti = sum(len(c["gates"]) for c in contratti if not _chiuso(c))

    # Tentativi per (task, gate), in ordine di timestamp.
    tentativi: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for voce in evidenze:
        tentativi.setdefault((voce["task_id"], voce["gate"]), []).append(voce)
    for lista in tentativi.values():
        lista.sort(key=lambda v: v["timestamp"] or v["file"])

    primo_colpo = 0
    gate_valutati = 0
    for chiave, lista in tentativi.items():
        if not lista:
            continue
        gate_valutati += 1
        finali = lista[-1]["outcome"]
        precedenti_negativi = any(v["outcome"] in ("FAIL", "REJECT") for v in lista[:-1])
        if finali == "PASS" and not precedenti_negativi:
            primo_colpo += 1

    # Errori collegati: un riferimento nomina un task id di un contract.
    task_ids = {c["task_id"] for c in contratti}
    collegati = 0
    for errore in errori:
        if any(any(task in riferimento for task in task_ids) for riferimento in errore["riferimenti"]):
            collegati += 1

    def percentuale(numeratore: int, denominatore: int) -> float:
        return round(100.0 * numeratore / denominatore, 1) if denominatore else 0.0

    metriche = {
        "task_chiusi": task_chiusi,
        "contratti_totali": len(contratti),
        "gate_richiesti": gate_richiesti,
        "gate_aperti": gate_aperti,
        "gate_valutati": gate_valutati,
        "primo_colpo_percento": percentuale(primo_colpo, gate_valutati),
        "errori_registrati": len(errori),
        "lezioni_controllo_percento": percentuale(sum(1 for e in errori if e["diventa"] == "controllo"), len(errori)),
        "terza_domanda_percento": percentuale(sum(1 for e in errori if e["terza_domanda"]), len(errori)),
        "errori_collegati": collegati,
        "errori_per_task_chiuso": round(collegati / task_chiusi, 2) if task_chiusi else 0.0,
    }
    traiettorie = []
    for contratto in contratti:
        gate_voci = []
        for gate in contratto["gates"]:
            lista = tentativi.get((contratto["task_id"], gate), [])
            gate_voci.append({
                "gate": gate,
                "tentativi": len(lista),
                "esito_finale": lista[-1]["outcome"] if lista else "SENZA PROVA",
            })
        traiettorie.append({
            "task_id": contratto["task_id"],
            "status": contratto["status"],
            "aperto": contratto["aperto"],
            "chiuso": contratto["chiuso"],
            "gate": gate_voci,
        })
    return {
        "metriche": metriche,
        "traiettorie": traiettorie,
        "definizioni": {
            "primo_colpo": "ultima evidenza PASS e nessun FAIL/REJECT prima; gate senza evidenze esclusi",
            "lezioni_controllo": "errori con diventa: controllo / errori totali",
            "terza_domanda": "errori con cosa_l_avrebbe_preso non vuoto / errori totali",
            "errori_per_task_chiuso": "errori i cui riferimenti nominano un task / task chiusi",
        },
        "fonte": "contratti/, evidenze/, errori/ — sola lettura",
    }


def confronta(radice: Path = RADICE, *, aggiorna: bool = False) -> dict[str, Any]:
    attuale = analizza(radice)
    percorso = radice / "evals" / "traiettorie" / "baseline.json"
    if aggiorna:
        percorso.parent.mkdir(parents=True, exist_ok=True)
        percorso.write_text(json.dumps({
            "schema": 1,
            "nota": "fotografia delle metriche di apprendimento; --aggiorna e' una firma, non un tasto",
            "tolleranza_punti": TOLLERANZA_PUNTI,
            "metriche": attuale["metriche"],
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return {"aggiornata": True, "baseline": str(percorso), "metriche": attuale["metriche"]}

    if not percorso.is_file():
        return {"ok": False, "motivo": "baseline mancante",
                "rimedio": "crea la baseline con `confronta --aggiorna` dopo aver guardato le metriche",
                "metriche": attuale["metriche"]}
    try:
        baseline = json.loads(percorso.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as errore:
        return {"ok": False, "motivo": f"baseline illeggibile: {errore}",
                "rimedio": "rigenera con `confronta --aggiorna`", "metriche": attuale["metriche"]}
    attese = baseline.get("metriche") or {}
    tolleranza = float(baseline.get("tolleranza_punti", TOLLERANZA_PUNTI))
    regressioni = []
    for nome in METRICHE_CRESCENTI:
        prima = attese.get(nome)
        ora = attuale["metriche"].get(nome)
        if prima is None or ora is None:
            continue
        if float(ora) < float(prima) - tolleranza:
            regressioni.append({"metrica": nome, "prima": prima, "ora": ora, "tolleranza": tolleranza})
    return {
        "ok": not regressioni,
        "regressioni": regressioni,
        "metriche": attuale["metriche"],
        "baseline": str(percorso),
    }


def main(argv: list[str] | None = None, *, radice: Path = RADICE) -> int:
    analizzatore = argparse.ArgumentParser(description="Flight recorder e metriche di apprendimento")
    sotto = analizzatore.add_subparsers(dest="azione", required=True)
    a = sotto.add_parser("analizza", help="ricompone le traiettorie e calcola le metriche")
    a.add_argument("--json", action="store_true")
    c = sotto.add_parser("confronta", help="confronta con la baseline")
    c.add_argument("--aggiorna", action="store_true", help="scrive la baseline con i numeri di oggi")
    c.add_argument("--json", action="store_true")

    args = analizzatore.parse_args(argv)
    if args.azione == "analizza":
        esito = analizza(radice)
        if args.json:
            print(json.dumps(esito, indent=2, ensure_ascii=False))
        else:
            m = esito["metriche"]
            print(f"  task chiusi: {m['task_chiusi']}/{m['contratti_totali']} · gate richiesti: {m['gate_richiesti']} · gate aperti: {m['gate_aperti']}")
            print(f"  primo colpo: {m['primo_colpo_percento']}% ({m['gate_valutati']} gate con prove)")
            print(f"  lezioni -> controlli: {m['lezioni_controllo_percento']}% · terza domanda: {m['terza_domanda_percento']}%")
            print(f"  errori collegati: {m['errori_collegati']} · per task chiuso: {m['errori_per_task_chiuso']}")
        return 0
    esito = confronta(radice, aggiorna=args.aggiorna)
    if args.json:
        print(json.dumps(esito, indent=2, ensure_ascii=False))
    elif esito.get("aggiornata"):
        print(f"  baseline aggiornata: {esito['baseline']}")
    elif esito.get("ok") is False:
        if esito.get("motivo"):
            print(f"  NO: {esito['motivo']}")
            if esito.get("rimedio"):
                print(f"  rimedio: {esito['rimedio']}")
        for regressione in esito.get("regressioni", []):
            print(f"  NO: regressione su {regressione['metrica']}: "
                  f"{regressione['prima']} -> {regressione['ora']} (tolleranza {regressione['tolleranza']})")
    else:
        print(f"  verde: nessuna metrica e' peggiorata oltre {TOLLERANZA_PUNTI} punti")
    return 0 if esito.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
