#!/usr/bin/env python3
"""La memoria del motore: provenienza, verifica, costo, eval (M4, `DEC-0116`).

Tre cose, e ognuna ha il suo fallimento:
 1. **Eval**: 9 domande con la fonte canonica; la memoria deve trovarne >= 7 nei primi 3.
    Sotto la soglia il test e' rosso: e' la misura del valore, non un'etichetta.
 2. **Provenienza**: ogni risultato porta `file`, `riga`, `sha256`; `verifica` conferma che
    la fonte esiste ancora con quell'impronta, e dice «cambiata» se non e' cosi'.
 3. **Costo e onesta'**: la query dichiara byte letti e token stimati; una domanda senza
    termini utili non inventa risultati.

Si esegue dalla radice:
    python3 tools/tests/test_memoria.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE / "tools"))

import memoria  # noqa: E402

FALLITI: list[str] = []
PASSATI = 0
SOGLIA = 7


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    global PASSATI
    if condizione:
        print(f"  ok   {etichetta}")
        PASSATI += 1
    else:
        print(f"  NO   {etichetta}  {dettaglio}")
        FALLITI.append(etichetta)


def test_eval() -> None:
    print(f"\nl'eval: >= {SOGLIA}/9 fonti canoniche nei primi 3 risultati")
    storico = [p for p in (RADICE / "errori").glob("ERR-*.yaml")]
    storico += [p for p in (RADICE / "DECISIONI").glob("DEC-*.md")]
    if not storico:
        print("  skip  registri vuoti (kit nuovo): l'eval richiede la memoria di un lavoro vero")
        return
    eval_file = RADICE / "evals" / "memoria" / "domande.yaml"
    domande = yaml.safe_load(eval_file.read_text(encoding="utf-8"))["domande"]
    check("l'eval ha 9 domande", len(domande) == 9, str(len(domande)))
    trovate = 0
    for voce in domande:
        esito = memoria.cerca(voce["domanda"], k=3)
        file_trovati = [r["file"] for r in esito["risultati"]]
        buona = voce["fonte"] in file_trovati
        check(f"«{voce['domanda']}» -> {voce['fonte']}", buona, str(file_trovati))
        if buona:
            trovate += 1
    check(f"risultato {trovate}/9 (soglia {SOGLIA})", trovate >= SOGLIA, str(trovate))


def test_provenienza() -> None:
    print("\nla provenienza: file, riga, impronta, e la verifica che regge")
    esito = memoria.cerca("drift 037 rapporti progetto 4 fuori modello", k=3)
    check("ci sono risultati", bool(esito["risultati"]), str(esito))
    primo = esito["risultati"][0]
    check("il risultato ha file e riga", primo["file"] and primo["riga"] >= 1, str(primo))
    check("il risultato ha l'impronta della fonte", len(primo["sha256"]) == 64, primo["sha256"][:16])
    conferma = memoria.verifica(primo["file"], primo["sha256"])
    check("la fonte citata e' verificata", conferma["ok"] is True, str(conferma))
    sbagliata = memoria.verifica(primo["file"], "0" * 64)
    check("una fonte cambiata NON e' verificata", sbagliata["ok"] is False, str(sbagliata))
    inesistente = memoria.verifica("piani/non-esiste.md", "0" * 64)
    check("una fonte inesistente NON e' verificata", inesistente["ok"] is False, str(inesistente))


def test_costo_e_onesta() -> None:
    print("\nil costo e' dichiarato, e la memoria non inventa")
    esito = memoria.cerca("perche il crawler rifiuta la rete interna", k=3)
    costo = esito["costo"]
    check("dichiara i file letti", costo["file_letti"] > 0, str(costo))
    check("dichiara i byte letti", costo["byte_letti"] > 0, str(costo))
    check("dichiara i token stimati (e non zero)", costo["token_stimati"] > 0, str(costo))
    check("la nota dice che il recupero e' lessicale", "lessicale" in esito["nota"], esito["nota"])

    vuoto = memoria.cerca("qzx qzy qzz", k=3)
    check("una domanda senza riscontri non inventa", vuoto["risultati"] == [], str(vuoto["risultati"]))
    senza_termini = memoria.cerca("il di a", k=3)
    check("una domanda senza termini utili non inventa", senza_termini["risultati"] == [], str(senza_termini))

    elenco = memoria.fonti()
    check("le fonti sono dichiarate", len(elenco) > 0 and all(isinstance(f, str) for f in elenco), str(len(elenco)))


def main() -> int:
    test_eval()
    test_provenienza()
    test_costo_e_onesta()
    print()
    print(f"  {PASSATI} controlli passati")
    if FALLITI:
        print(f"FALLITI: {len(FALLITI)}")
        return 1
    print("PASS — la memoria trova, cita e si puo' verificare")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
