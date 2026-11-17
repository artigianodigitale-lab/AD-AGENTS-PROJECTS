#!/usr/bin/env python3
"""Il modello dei finding deve saper rifiutare (`DEC-0106`, Fase 2).

Il criterio di chiusura della Fase 2 e' uno solo, e sta nella specifica:
**un finding senza `evidence` e' rifiutato.** Ma un validatore che accetta tutto passa
quello stesso test per caso, quindi qui si prova ogni campo, e soprattutto i casi che
devono **mordere**:

  manca `evidence`                  -> rifiutato (e' il criterio di chiusura)
  `severity: P9`                    -> rifiutato, e dice quali sono ammesse
  `reproducible: false` + severita' -> rifiutato: non e' classificabile
  `disposition` inventata           -> rifiutato
  un finding completo               -> accettato

Perche' conta. Su `ENG-020` i finding erano in prosa: sette revisioni, e un criterio
scritto come requisito e' stato declassato a finding P2 senza che nessuno potesse
contarlo (`ERR-0091`). Un finding senza forma non si conta, e un finding che non si conta
non si vede quando sparisce.

Si esegue dalla radice:
    python3 tools/tests/test_finding.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE / "tools"))

import finding  # noqa: E402

FALLITI: list[str] = []

#: Un finding completo: tutti e quattordici i campi, con valori ammessi.
COMPLETO = {
    "finding_id": "F-001",
    "reviewer": "CODE_REVIEW",
    "commit_sha": "abc1234",
    "category": "SECURITY",
    "severity": "P1",
    "title": "Scrittura fuori dalla cartella del progetto",
    "evidence": "evidenze/F-001.log",
    "reproducible": True,
    "impact": "Un percorso con symlink fa scrivere il banco fuori dal progetto",
    "trigger": "Il campo foto contiene un collegamento che esce dalla cartella",
    "surface": "filesystem",
    "compensating_controls": "nessuno",
    "recommendation": "Verificare il percorso risolto, non quello dichiarato",
    "disposition": "BLOCKING",
}


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    if condizione:
        print(f"  ok   {etichetta}")
    else:
        print(f"  NO   {etichetta}  {dettaglio}")
        FALLITI.append(etichetta)


def test_completo_e_valido() -> None:
    """Il caso felice: un finding completo passa."""
    print("\nun finding completo")
    problemi = finding.valida(COMPLETO)
    check("nessun problema", not problemi, str(problemi))


def test_manca_evidenza() -> None:
    """IL criterio di chiusura della Fase 2: senza `evidence` non e' un fatto."""
    print("\nsenza evidence — il criterio di chiusura")
    for variante in ("assente", "vuota", "solo spazi"):
        voce = dict(COMPLETO)
        if variante == "assente":
            voce.pop("evidence")
        elif variante == "vuota":
            voce["evidence"] = ""
        else:
            voce["evidence"] = "   "
        problemi = finding.valida(voce)
        check(f"evidence {variante}: rifiutato", bool(problemi), str(problemi))
        check(
            f"evidence {variante}: il messaggio la nomina",
            any("evidence" in p for p in problemi),
            str(problemi),
        )


def test_ogni_campo_obbligatorio() -> None:
    """Tutti e quattordici i campi devono mordere, uno per uno."""
    print("\nogni campo obbligatorio")
    mancanti = []
    for campo, _ in finding.CAMPI:
        voce = dict(COMPLETO)
        voce.pop(campo, None)
        if not finding.valida(voce):
            mancanti.append(campo)
    check(
        "tutti i campi mancanti sono rifiutati",
        not mancanti,
        "questi campi non mordono: " + ", ".join(mancanti),
    )


def test_severita_fuori_elenco() -> None:
    """`P9` non e' «quasi giusto»: il Decision Engine decide su questi valori."""
    print("\nseverita' fuori elenco")
    # Lo spazio attorno a `P0` e' tollerato di proposito: e' un errore di battitura,
    # non un valore diverso. Gli altri sono valori che significano un'altra cosa.
    for valore in ("P9", "high", "1", "P0-P1", "p1"):
        voce = dict(COMPLETO)
        voce["severity"] = valore
        problemi = finding.valida(voce)
        check(f"severity {valore!r}: rifiutato", bool(problemi), str(problemi))
    voce = dict(COMPLETO)
    voce["severity"] = "P9"
    problemi = finding.valida(voce)
    check(
        "il messaggio elenca le severita' ammesse",
        any("P0, P1, P2, P3" in p for p in problemi),
        str(problemi),
    )
    # E la controprova: lo spazio non e' un errore.
    voce = dict(COMPLETO)
    voce["severity"] = "P0 "
    check("«P0 » con lo spazio e' tollerato", not finding.valida(voce), str(finding.valida(voce)))


def test_reproducible_false_non_e_classificabile() -> None:
    """La regola della specifica: non riproducibile -> NOT_VERIFIED, senza severita'."""
    print("\nreproducible: false non e' classificabile")
    voce = dict(COMPLETO)
    voce["reproducible"] = False
    problemi = finding.valida(voce)
    check("rifiutato con una severita'", bool(problemi), str(problemi))

    voce["severity"] = ""
    voce["disposition"] = "NOT_VERIFIED"
    problemi = finding.valida(voce)
    check(
        "senza severita' e con NOT_VERIFIED: accettato",
        not problemi,
        str(problemi),
    )

    voce["disposition"] = "BLOCKING"
    problemi = finding.valida(voce)
    check(
        "con NOT_VERIFIED obbligatorio: BLOCKING rifiutato",
        bool(problemi),
        str(problemi),
    )


def test_valori_fuori_elenco() -> None:
    """Revisore, categoria e disposizione hanno elenchi chiusi."""
    print("\nvalori fuori elenco")
    casi = (
        ("reviewer", "BOSS"),
        ("category", "ALTRO"),
        ("disposition", "BOCCIATO"),
    )
    for campo, valore in casi:
        voce = dict(COMPLETO)
        voce[campo] = valore
        problemi = finding.valida(voce)
        check(f"{campo} {valore!r}: rifiutato", bool(problemi), str(problemi))


def test_tutti_i_valori_ammessi_passano() -> None:
    """La controprova: l'elenco non e' troppo stretto."""
    print("\ntutti i valori ammessi")
    for severita in finding.SEVERITA:
        voce = dict(COMPLETO)
        voce["severity"] = severita
        check(f"severity {severita} accettata", not finding.valida(voce), str(voce))
    for revisore in finding.REVISORI:
        voce = dict(COMPLETO)
        voce["reviewer"] = revisore
        check(f"reviewer {revisore} accettato", not finding.valida(voce), str(voce))
    for categoria in finding.CATEGORIE:
        voce = dict(COMPLETO)
        voce["category"] = categoria
        check(f"category {categoria} accettata", not finding.valida(voce), str(voce))


def test_file_con_lista() -> None:
    """Un file puo' contenere piu' finding: ognuno si valida da solo."""
    print("\nun file con piu' finding")
    with tempfile.TemporaryDirectory() as tmp:
        percorso = Path(tmp) / "findings.yaml"
        import yaml

        percorso.write_text(
            yaml.safe_dump({"findings": [COMPLETO, {**COMPLETO, "finding_id": "F-002"}]}),
            encoding="utf-8",
        )
        problemi, validi = finding.valida_file(percorso)
        check("nessun problema", not problemi, str(problemi))
        check("due validi", validi == 2, str(validi))


def test_un_file_vuoto_non_prova_niente() -> None:
    """Un file senza finding non dice «nessun difetto»: dice «non ho guardato»."""
    print("\nun file vuoto")
    with tempfile.TemporaryDirectory() as tmp:
        percorso = Path(tmp) / "vuoto.yaml"
        percorso.write_text("", encoding="utf-8")
        rifiutato = False
        try:
            finding.valida_file(percorso)
        except finding.FindingRifiutato:
            rifiutato = True
        check("rifiutato", rifiutato)


def test_il_cli_esce_col_codice() -> None:
    """Il CLI: 0 validi, 1 rifiutati, 2 illeggibile."""
    print("\nil CLI")
    with tempfile.TemporaryDirectory() as tmp:
        import yaml

        valido = Path(tmp) / "valido.yaml"
        valido.write_text(yaml.safe_dump(COMPLETO), encoding="utf-8")
        esito = subprocess.run(
            [sys.executable, str(RADICE / "tools" / "finding.py"), "check", str(valido)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        check("valido -> 0", esito.returncode == 0, f"{esito.returncode}: {esito.stderr[:150]}")

        mancante = Path(tmp) / "senza_evidenza.yaml"
        senza = dict(COMPLETO)
        senza.pop("evidence")
        mancante.write_text(yaml.safe_dump(senza), encoding="utf-8")
        esito = subprocess.run(
            [sys.executable, str(RADICE / "tools" / "finding.py"), "check", str(mancante)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        check("senza evidence -> 1", esito.returncode == 1, f"{esito.returncode}: {esito.stdout[:150]}")

        esito = subprocess.run(
            [sys.executable, str(RADICE / "tools" / "finding.py"), "check", str(Path(tmp) / "non-esiste.yaml")],
            capture_output=True,
            text=True,
            timeout=60,
        )
        check("illeggibile -> 2", esito.returncode == 2, f"{esito.returncode}: {esito.stderr[:150]}")


def main() -> int:
    print("il modello dei finding")
    test_completo_e_valido()
    test_manca_evidenza()
    test_ogni_campo_obbligatorio()
    test_severita_fuori_elenco()
    test_reproducible_false_non_e_classificabile()
    test_valori_fuori_elenco()
    test_tutti_i_valori_ammessi_passano()
    test_file_con_lista()
    test_un_file_vuoto_non_prova_niente()
    test_il_cli_esce_col_codice()
    print()
    if FALLITI:
        print(f"FALLITO — {len(FALLITI)} controlli: " + ", ".join(FALLITI))
        return 1
    print("PASS — un finding senza forma e' rifiutato, e chi sta bene passa")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
