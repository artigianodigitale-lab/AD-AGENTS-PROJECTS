#!/usr/bin/env python3
"""Il Decision Engine deve saper dire di no (`DEC-0107`, Fase 3).

I **sette casi di §13** della specifica, tutti negativi. Se il sistema non sa fallire,
non e' un sistema — e nove revisioni con nove FAIL su `ENG-020` sono la prova di cosa
succede quando non sa smettere.

    1  un finding P3 su un lavoro altrimenti conforme   -> ACCEPT, il P3 nel backlog
    2  un finding P1 aperto                             -> REJECT
    3  un finding cancellato senza evidenza              -> rifiutato dal validatore
    4  un revisore che modifica lo snapshot              -> exit 2, revisione invalidata
    5  budget superato                                   -> ESCALATE, mai ACCEPT
    6  un waiver senza i sette campi, o P1 non-CEO       -> REJECT
    7  due revisori con finding diversi e legittimi      -> un solo ciclo

Piu' i casi che il documento non elenca ma che decidono se il motore e' onesto: un FAIL
senza finding bloccanti, un'evidenza assente, e la regola che il budget **non** cancella
un P1.

Si esegue dalla radice:
    python3 tests/test_gate_policy.py
"""

from __future__ import annotations

import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RADICE / "tools"))

import policy  # noqa: E402

FALLITI: list[str] = []

EVIDENZE_OK = {"QA": "outcome: PASS\n", "CodeReview": "outcome: PASS\n"}


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    if condizione:
        print(f"  ok   {etichetta}")
    else:
        print(f"  NO   {etichetta}  {dettaglio}")
        FALLITI.append(etichetta)


def finding(severita: str = "P1", disposizione: str = "BLOCKING", nome: str = "F-001") -> dict:
    """Un finding gia' validato dal validatore della Fase 2."""
    return {
        "finding_id": nome,
        "reviewer": "CODE_REVIEW",
        "commit_sha": "abc1234",
        "category": "CORRECTNESS",
        "severity": severita,
        "title": "un difetto",
        "evidence": "evidenze/f.log",
        "reproducible": True,
        "impact": "impatto",
        "trigger": "trigger",
        "surface": "filesystem",
        "compensating_controls": "nessuno",
        "recommendation": "correggere",
        "disposition": disposizione,
    }


def waiver(**extra) -> dict:
    """Un waiver completo dei sette campi: il caso base da guastare."""
    base = {
        "finding_id": "F-001",
        "motivation": "costo alto, impatto basso",
        "residual_impact": "nessuno sfruttabile oggi",
        "mitigations": "il cancello blocca la scrittura",
        "risk_owner": "Luca",
        "review_date": "2026-12-06",
        "decision_ref": "DEC-0001",
        "severity": "P2",
        "autorita": "CEO",
    }
    base.update(extra)
    return base


# ---------------------------------------------------------------- i sette di §13


def test_caso_1_p3_su_lavoro_conforme() -> None:
    """1 — un P3 su un lavoro altrimenti conforme: ACCEPT, e il P3 va in backlog."""
    print("\ncaso 1 — un P3 su un lavoro conforme")
    verdetto = policy.decidi(findings=[finding("P3", "BACKLOG")], evidenze=EVIDENZE_OK)
    check("esito ACCEPT", verdetto["esito"] == policy.ACCEPT, str(verdetto))
    check("il P3 e' nel backlog", len(verdetto["backlog"]) == 1, str(verdetto))
    check("nessun bloccante", not verdetto["bloccanti"], str(verdetto))


def test_caso_2_p1_aperto() -> None:
    """2 — un P1 aperto: REJECT. Il lavoro non e' conforme, punto."""
    print("\ncaso 2 — un P1 aperto")
    verdetto = policy.decidi(findings=[finding("P1", "BLOCKING")], evidenze=EVIDENZE_OK)
    check("esito REJECT", verdetto["esito"] == policy.REJECT, str(verdetto))
    check("il bloccante e' nominato", len(verdetto["bloccanti"]) == 1, str(verdetto))


def test_caso_3_finding_senza_evidenza() -> None:
    """3 — un finding cancellato senza evidenza: rifiutato dal validatore della Fase 2."""
    print("\ncaso 3 — un finding senza evidenza")
    import finding as validatore

    voce = {
        "finding_id": "F-001", "reviewer": "QA", "commit_sha": "a", "category": "UX",
        "severity": "P3", "title": "t", "reproducible": True, "impact": "i",
        "trigger": "t", "surface": "s", "compensating_controls": "n",
        "recommendation": "r", "disposition": "BACKLOG",
    }
    check("senza evidence: rifiutato", bool(validatore.valida(voce)), str(validatore.valida(voce)))
    voce["evidence"] = "evidenze/f.log"
    check("con evidence: accettato", not validatore.valida(voce), str(validatore.valida(voce)))


def test_caso_4_snapshot_modificato() -> None:
    """4 — un revisore che modifica lo snapshot: exit 2. Lo decide `gate_kit`."""
    print("\ncaso 4 — lo snapshot modificato (exit 2)")
    check(
        "gate_kit ha ESITO_MOSSO = 2",
        getattr(__import__("gate_kit"), "ESITO_MOSSO", None) == 2,
        "il codice 2 non esiste",
    )
    import gate_kit

    esito = gate_kit.esito_dei_problemi(["MOSSO tools/banco.py"])
    check("un file mosso produce 2", esito == 2, str(esito))


def test_caso_5_budget_superato() -> None:
    """5 — budget superato: ESCALATE, e **mai** ACCEPT."""
    print("\ncaso 5 — budget superato")
    verdetto = policy.decidi(findings=[], evidenze=EVIDENZE_OK, review_round=4, budget=3)
    check("esito ESCALATE", verdetto["esito"] == policy.ESCALATE, str(verdetto))
    check(
        "NON e' ACCEPT",
        verdetto["esito"] != policy.ACCEPT,
        "il superamento del budget ha prodotto ACCEPT: un budget che migliora l'esito",
    )
    # E il confine: al terzo round si decide ancora.
    verdetto = policy.decidi(findings=[], evidenze=EVIDENZE_OK, review_round=3, budget=3)
    check("al terzo round: ACCEPT", verdetto["esito"] == policy.ACCEPT, str(verdetto))


def test_caso_6_waiver() -> None:
    """6 — un waiver incompleto, o un P1 firmato da un non-CEO: REJECT."""
    print("\ncaso 6 — il waiver")
    # Completo su P2: e' un waiver legittimo, e non blocca.
    verdetto = policy.decidi(findings=[], evidenze=EVIDENZE_OK, waiver=waiver())
    check("waiver completo su P2: ACCEPT", verdetto["esito"] == policy.ACCEPT, str(verdetto))

    # Incompleto: manca `risk_owner`.
    parziale = waiver()
    parziale.pop("risk_owner")
    verdetto = policy.decidi(findings=[], evidenze=EVIDENZE_OK, waiver=parziale)
    check("waiver senza risk_owner: REJECT", verdetto["esito"] == policy.REJECT, str(verdetto))
    check(
        "il motivo nomina il campo",
        "risk_owner" in verdetto["motivo"],
        verdetto["motivo"],
    )

    # Ogni campo deve mordere.
    non_mordono = []
    for campo in policy.CAMPI_WAIVER:
        parziale = waiver()
        parziale.pop(campo)
        if policy.decidi(findings=[], evidenze=EVIDENZE_OK, waiver=parziale)["esito"] != policy.REJECT:
            non_mordono.append(campo)
    check("tutti i sette campi mordono", not non_mordono, "non mordono: " + ", ".join(non_mordono))

    # P1 firmato da un non-CEO: REJECT. Firmato dal CEO: ESCALATE, non ACCEPT.
    verdetto = policy.decidi(
        findings=[], evidenze=EVIDENZE_OK, waiver=waiver(severity="P1", autorita="orchestratore")
    )
    check("P1 firmato da un non-CEO: REJECT", verdetto["esito"] == policy.REJECT, str(verdetto))

    verdetto = policy.decidi(
        findings=[], evidenze=EVIDENZE_OK, waiver=waiver(severity="P1", autorita="CEO")
    )
    check("P1 firmato dal CEO: ESCALATE", verdetto["esito"] == policy.ESCALATE, str(verdetto))
    check(
        "e non chiude il gate",
        verdetto["esito"] != policy.ACCEPT,
        "un waiver P1 ha chiuso il gate",
    )


def test_caso_7_due_revisori_finding_diversi() -> None:
    """7 — la ragione di tutto il documento: due finding diversi, **un solo ciclo**.

    Il difetto che questo chiude: con due revisori che trovano difetti diversi e legittimi,
    il ciclo non finisce mai — ognuno trova il difetto successivo. Il Decision Engine li
    classifica: uno bloccante, uno no, e la decisione e' una.
    """
    print("\ncaso 7 — due revisori, finding diversi")
    uno_bloccante = [finding("P1", "BLOCKING", "F-001"), finding("P3", "BACKLOG", "F-002")]
    verdetto = policy.decidi(findings=uno_bloccante, evidenze=EVIDENZE_OK)
    check("esito REJECT (c'e' un P1)", verdetto["esito"] == policy.REJECT, str(verdetto))
    check("un solo bloccante", len(verdetto["bloccanti"]) == 1, str(verdetto))
    check("il P3 non blocca", len(verdetto["backlog"]) == 1, str(verdetto))

    # Il caso che conta: quando il P1 e' corretto, il P3 **non** tiene aperto il gate.
    corretto = [finding("P1", "REMEDIATED", "F-001"), finding("P3", "BACKLOG", "F-002")]
    verdetto = policy.decidi(findings=corretto, evidenze=EVIDENZE_OK)
    check(
        "corretto il P1: ACCEPT, il P3 va in backlog",
        verdetto["esito"] == policy.ACCEPT,
        str(verdetto),
    )


# ---------------------------------------------------------------- oltre i sette


def test_evidenza_assente_e_inconclusive() -> None:
    """Senza prove non si decide: INCONCLUSIVE, e non accusa nessuno."""
    print("\nun'evidenza assente")
    verdetto = policy.decidi(findings=[], evidenze={})
    check("esito INCONCLUSIVE", verdetto["esito"] == policy.INCONCLUSIVE, str(verdetto))
    verdetto = policy.decidi(findings=[], evidenze={"QA": "outcome: PASS\n"})
    check("manca CodeReview: INCONCLUSIVE", verdetto["esito"] == policy.INCONCLUSIVE, str(verdetto))
    verdetto = policy.decidi(findings=[], evidenze={"QA": "", "CodeReview": ""})
    check("evidenze vuote: INCONCLUSIVE", verdetto["esito"] == policy.INCONCLUSIVE, str(verdetto))


def test_fail_senza_bloccanti_e_backlog() -> None:
    """Un FAIL con soli P2/P3 non tiene aperto il gate: va in backlog."""
    print("\nun FAIL con soli P2/P3")
    verdetto = policy.decidi(
        findings=[finding("P2", "BACKLOG")],
        evidenze={"QA": "outcome: FAIL\n", "CodeReview": "outcome: PASS\n"},
    )
    check("esito ACCEPT", verdetto["esito"] == policy.ACCEPT, str(verdetto))
    check("il P2 e' in backlog", len(verdetto["backlog"]) == 1, str(verdetto))


def test_il_budget_non_cancella_un_p1() -> None:
    """Il budget viene DOPO i finding: superarlo non assolve un P1 aperto."""
    print("\nil budget non cancella un P1")
    verdetto = policy.decidi(
        findings=[finding("P1", "BLOCKING")], evidenze=EVIDENZE_OK, review_round=9, budget=3
    )
    check(
        "esito REJECT, non ESCALATE",
        verdetto["esito"] == policy.REJECT,
        "il budget ha coperto un P1 aperto: " + str(verdetto),
    )


def test_remediated_chiude() -> None:
    """Un finding REMEDIATED non blocca; ACCEPTED_RISK invece non chiude un P0/P1."""
    print("\ncosa chiude un finding")
    verdetto = policy.decidi(findings=[finding("P1", "REMEDIATED")], evidenze=EVIDENZE_OK)
    check("REMEDIATED: ACCEPT", verdetto["esito"] == policy.ACCEPT, str(verdetto))
    verdetto = policy.decidi(findings=[finding("P1", "ACCEPTED_RISK")], evidenze=EVIDENZE_OK)
    check("ACCEPTED_RISK su P1: REJECT", verdetto["esito"] == policy.REJECT, str(verdetto))


def test_e_deterministico() -> None:
    """Stesso input, stesso esito. Sempre: non c'e' nessun modello da interrogare."""
    print("\ne' deterministico")
    esiti = set()
    for _ in range(5):
        esiti.add(policy.decidi(findings=[finding("P1")], evidenze=EVIDENZE_OK)["esito"])
    check("cinque chiamate, un solo esito", len(esiti) == 1, str(esiti))


def test_i_quattro_esiti_esistono() -> None:
    """I quattro esiti sono quattro, e distinti."""
    print("\ni quattro esiti")
    check("sono quattro", len(set(policy.ESITI)) == 4, str(policy.ESITI))
    check(
        "sono quelli della specifica",
        set(policy.ESITI) == {"ACCEPT", "REJECT", "ESCALATE", "INCONCLUSIVE"},
        str(policy.ESITI),
    )


def main() -> int:
    print("il Decision Engine")
    test_caso_1_p3_su_lavoro_conforme()
    test_caso_2_p1_aperto()
    test_caso_3_finding_senza_evidenza()
    test_caso_4_snapshot_modificato()
    test_caso_5_budget_superato()
    test_caso_6_waiver()
    test_caso_7_due_revisori_finding_diversi()
    test_evidenza_assente_e_inconclusive()
    test_fail_senza_bloccanti_e_backlog()
    test_il_budget_non_cancella_un_p1()
    test_remediated_chiude()
    test_e_deterministico()
    test_i_quattro_esiti_esistono()
    print()
    if FALLITI:
        print(f"FALLITO — {len(FALLITI)} controlli: " + ", ".join(FALLITI))
        return 1
    print("PASS — i sette casi di §13, e i quattro esiti")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
