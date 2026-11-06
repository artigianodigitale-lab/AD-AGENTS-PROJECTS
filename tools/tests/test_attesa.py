#!/usr/bin/env python3
"""L'attesa deve distinguere «fermo» da «vivo» (`DEC-0108`).

Il problema che questo strumento chiude, misurato il 2026-11-06 su `GOV-026`:

    Code Review   finito di scrivere alle 12:07:03, messaggio alle 12:16
    Documentation finito alle            11:54:58, messaggio alle 12:06:49

Dieci minuti di attesa con il file completo. La causa non era il revisore: era che si
aspettava il **messaggio** invece del **file**.

I cinque stati, e ognuno deve mordere:

    assente      il file non c'e'
    in-crescita  il file cresce: e' vivo
    ferma        non cambia da oltre la soglia: fermo o bloccato
    completa     valido per il gate: il verdetto c'e'
    non-valida   fermo ma non valido: manca qualcosa

Il caso che conta: «non e' arrivato niente» non dice se aspettare o interrompere.
`ferma` dice che si puo' interrompere. Senza questa distinzione si interrompe alla cieca,
che e' quello che e' successo.

Si esegue dalla radice:
    python3 tools/tests/test_attesa.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE / "tools"))

import attesa  # noqa: E402

FALLITI: list[str] = []

EVIDENZA_VALIDA = """schema: 2
task_id: TEST-001
gate: QA
outcome: PASS
producer: qa
confidence: observed
authority: execution
coverage: {status: complete, examined: 1, total: 1}
limitations:
  - 'nessuna'
side_effects: {code: YES, database: NO, schema: NO, deps: NO, env: NO, external_services: NO}
"""


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    if condizione:
        print(f"  ok   {etichetta}")
    else:
        print(f"  NO   {etichetta}  {dettaglio}")
        FALLITI.append(etichetta)


class Finta:
    """Una cartella temporanea con un'evidenza, e il motore vero per validarla."""

    def __init__(self) -> None:
        self.base = Path(tempfile.mkdtemp())
        self.percorso = self.base / "TEST-001-QA.yaml"
        self._prima = attesa.RADICE
        attesa.RADICE = self.base

    def scrivi(self, contenuto: str) -> None:
        self.percorso.write_text(contenuto, encoding="utf-8")

    def invecchia(self, secondi: int) -> None:
        vecchio = time.time() - secondi
        os.utime(self.percorso, (vecchio, vecchio))

    def chiudi(self) -> None:
        attesa.RADICE = self._prima
        shutil.rmtree(self.base, ignore_errors=True)


def test_assente() -> None:
    """Senza file: il revisore sta ancora analizzando."""
    print("\nassente")
    finta = Finta()
    try:
        osservazione = attesa.osserva(finta.percorso, "TEST-001", "QA")
        check("stato assente", osservazione.stato == attesa.ASSENTE, osservazione.stato)
        check("e lo dice in parole", "non c'e'" in osservazione.frase(), osservazione.frase())
    finally:
        finta.chiudi()


def test_in_crescita() -> None:
    """Il file e' cambiato dall'ultima lettura: sta scrivendo."""
    print("\nin-crescita")
    finta = Finta()
    try:
        finta.scrivi(EVIDENZA_VALIDA[:40])
        prima = (40, finta.percorso.stat().st_mtime)
        finta.scrivi(EVIDENZA_VALIDA)  # cresce
        osservazione = attesa.osserva(finta.percorso, "TEST-001", "QA", prima=prima)
        check("stato in-crescita", osservazione.stato == attesa.IN_CRESCITA, osservazione.stato)
        check("dice quanti byte", osservazione.byte > 40, str(osservazione.byte))
    finally:
        finta.chiudi()


def test_ferma_oltre_la_soglia() -> None:
    """Non cambia da oltre la soglia: fermo. Si puo' decidere di interrompere."""
    print("\nferma")
    finta = Finta()
    try:
        finta.scrivi(EVIDENZA_VALIDA[:40])  # parziale: non e' valida
        finta.invecchia(600)
        osservazione = attesa.osserva(finta.percorso, "TEST-001", "QA", soglia=180)
        check("stato non-valida (e' ferma ma incompleta)", osservazione.stato == attesa.NON_VALIDA, osservazione.stato)
        check(
            "dice da quanti secondi e' ferma",
            (osservazione.secondi_fermo or 0) > 180,
            str(osservazione.secondi_fermo),
        )
    finally:
        finta.chiudi()


def test_completa() -> None:
    """Il file e' valido: il verdetto c'e', e non serve aspettare il messaggio."""
    print("\ncompleta")
    finta = Finta()
    try:
        finta.scrivi(EVIDENZA_VALIDA)
        finta.invecchia(30)  # scritta poco fa, ma non sta crescendo
        osservazione = attesa.osserva(finta.percorso, "TEST-001", "QA", soglia=5)
        check("stato completa", osservazione.stato == attesa.COMPLETA, f"{osservazione.stato}: {osservazione.motivo}")
        check(
            "e la frase dice che il verdetto c'e'",
            "verdetto c'e'" in osservazione.frase(),
            osservazione.frase(),
        )
    finally:
        finta.chiudi()


def test_non_valida_mai_completa() -> None:
    """Fermo e incompleto: non si dichiara completo qualcosa che il gate rifiuterebbe."""
    print("\nnon-valida")
    finta = Finta()
    try:
        finta.scrivi("schema: 2\ntask_id: TEST-001\n")  # manca quasi tutto
        finta.invecchia(600)
        osservazione = attesa.osserva(finta.percorso, "TEST-001", "QA", soglia=180)
        check(
            "non e' completa",
            osservazione.stato != attesa.COMPLETA,
            "ha dichiarato completa un'evidenza invalida",
        )
        check("il motivo e' detto", bool(osservazione.motivo), osservazione.motivo)
    finally:
        finta.chiudi()


def test_il_ruolo_del_gate_e_diverso_dal_nome_del_file() -> None:
    """`CodeReview` e' il file, `Code Review` il ruolo. Confonderli da' falsi «non-valida».

    L'ho scoperto sulla prima esecuzione sul motore vero: il Code Review veniva detto
    invalido mentre `gate_kit close` lo accettava.
    """
    print("\nil ruolo e il nome del file")
    suffissi = {suffisso for suffisso, _, _ in attesa.evidenze_da_guardare("GOV-026")}
    ruoli = {ruolo for _, ruolo, _ in attesa.evidenze_da_guardare("GOV-026")}
    check("i file sono QA e CodeReview", suffissi == {"QA", "CodeReview"}, str(suffissi))
    check(
        "i ruoli per il gate sono QA e 'Code Review'",
        ruoli == {"QA", "Code Review"},
        str(ruoli),
    )


def test_il_motore_vero_e_completo() -> None:
    """Sul motore vero: le due evidenze di GOV-026 sono valide, e lo strumento lo dice."""
    print("\nil motore vero")
    attesa.RADICE = RADICE
    bersagli = attesa.evidenze_da_guardare("GOV-026")
    for suffisso, ruolo_gate, percorso in bersagli:
        if not percorso.is_file():
            check(f"{suffisso} esiste", False, "evidenza assente sul motore vero")
            continue
        osservazione = attesa.osserva(percorso, "GOV-026", ruolo_gate, soglia=1)
        check(
            f"{suffisso} risulta completa",
            osservazione.stato == attesa.COMPLETA,
            f"{osservazione.stato}: {osservazione.motivo}",
        )


def test_evidenza_di_un_giro_precedente() -> None:
    """Un'evidenza valida ma **piu' vecchia del congelamento** non e' il verdetto di oggi.

    Difetto trovato il 2026-11-06 su `GOV-024` R2: `attesa.py` diceva «completa» sulle due
    evidenze di R1 (13:12 e 13:15) mentre la revisione era stata congelata alle 13:34.
    Leggere il verdetto vecchio come se fosse nuovo e' peggio che non leggere niente:
    sembra una risposta, e chiude l'attesa su una domanda che nessuno ha ancora guardato.
    """
    print("\nl'evidenza di un giro precedente")
    finta = Finta()
    try:
        # La macchina finta ha la sua revisione, congelata "adesso".
        import yaml

        (finta.base / "evidenze").mkdir(exist_ok=True)
        (finta.base / "evidenze" / "TEST-001-revisione.yaml").write_text(
            yaml.safe_dump(
                {"task_id": "TEST-001", "frozen_at": "2026-11-06T13:34:11+01:00"}
            ),
            encoding="utf-8",
        )
        finta.scrivi(EVIDENZA_VALIDA)
        # L'evidenza e' di un'ora prima del congelamento: e' il verdetto di un altro giro.
        vecchio = 1762437290.0  # 2026-11-06 ~12:14, prima delle 13:34
        os.utime(finta.percorso, (vecchio, vecchio))
        osservazione = attesa.osserva(finta.percorso, "TEST-001", "QA", soglia=1)
        check(
            "stato vecchia, non completa",
            osservazione.stato == attesa.VECCHIA,
            f"{osservazione.stato}: {osservazione.motivo}",
        )
        check(
            "la frase dice che e' di un giro precedente",
            "giro precedente" in osservazione.frase(),
            osservazione.frase(),
        )
    finally:
        finta.chiudi()


def test_fail_e_un_verdetto_non_un_incompiuto() -> None:
    """`FAIL` **e'** un verdetto: dire «non ha concluso» fa aspettare una risposta gia' arrivata.

    Bug del primo tentativo di `incompleta`, trovato dal Code Review di R3 nella stessa ora:
    avevo scritto `if esito != "PASS" -> incompleta`, che tratta **FAIL** come se il revisore
    non avesse finito. E' l'errore opposto a quello che `incompleta` esiste per evitare:
    prima aspettavo una verifica conclusa, poi avrei aspettato una verifica che aveva gia'
    dato la risposta negativa.

    La distinzione giusta: `PASS` e `FAIL` sono verdicti e si leggono subito;
    `UNKNOWN`/`TRUNCATED`/`SKIPPED`/`UNSUPPORTED` dicono «non ho potuto stabilire l'esito».
    """
    print("\nFAIL e' un verdetto")
    for esito in ("PASS", "FAIL"):
        finta = Finta()
        try:
            import yaml

            (finta.base / "evidenze").mkdir(exist_ok=True)
            (finta.base / "evidenze" / "TEST-001-revisione.yaml").write_text(
                yaml.safe_dump({"task_id": "TEST-001", "frozen_at": "2020-01-01T00:00:00+00:00"}),
                encoding="utf-8",
            )
            finta.scrivi(EVIDENZA_VALIDA.replace("outcome: PASS", f"outcome: {esito}"))
            finta.invecchia(2)
            osservazione = attesa.osserva(finta.percorso, "TEST-001", "QA", soglia=1)
            check(
                f"{esito} e' un verdetto: completo",
                osservazione.stato == attesa.COMPLETA,
                f"{osservazione.stato}: {osservazione.motivo}",
            )
        finally:
            finta.chiudi()


def test_esito_unknown_no_e_completa() -> None:
    """Un'evidenza che dichiara `UNKNOWN` non e' un verdetto: il revisore non ha finito.

    Difetto trovato il 2026-11-06 su `GOV-024` R3. Due errori in uno:

    1. `gate_kit._evidenza_problemi` accettava solo `PASS` e `FAIL`, mentre gli esiti
       ammessi sono **sei** — `UNKNOWN`, `TRUNCATED`, `SKIPPED`, `UNSUPPORTED` sono
       legittimi e significano «non ho potuto stabilire l'esito». Cosi' un revisore che
       rispondeva **onestamente** «non ho finito» veniva trattato come un file rotto.
    2. una volta accettato, sarebbe stato detto «completa» — cioe' «il verdetto c'e'» — ed
       e' falso: il file e' completo, il verdetto no.

    La differenza che si perdeva e' tutta: «non ha finito» e «ha scritto male» chiedono due
    cose diverse — aspettare la prima, correggere la seconda.
    """
    print("\nesito UNKNOWN — il revisore non ha concluso")
    for esito in ("UNKNOWN", "TRUNCATED", "SKIPPED", "UNSUPPORTED"):
        finta = Finta()
        try:
            import yaml

            (finta.base / "evidenze").mkdir(exist_ok=True)
            (finta.base / "evidenze" / "TEST-001-revisione.yaml").write_text(
                yaml.safe_dump({"task_id": "TEST-001", "frozen_at": "2020-01-01T00:00:00+00:00"}),
                encoding="utf-8",
            )
            finta.scrivi(EVIDENZA_VALIDA.replace("outcome: PASS", f"outcome: {esito}"))
            finta.invecchia(2)
            osservazione = attesa.osserva(finta.percorso, "TEST-001", "QA", soglia=1)
            check(
                f"{esito} non e' «completa»",
                osservazione.stato != attesa.COMPLETA,
                f"ha detto completa con esito {esito}: il verdetto non c'e'",
            )
            check(
                f"{esito} e' «incompleta», non «non-valida»",
                osservazione.stato == attesa.INCOMPLETA,
                f"{osservazione.stato}: {osservazione.motivo}",
            )
        finally:
            finta.chiudi()


def test_evidenza_nuova_e_completa() -> None:
    """La controprova: scritta DOPO il congelamento, e' il verdetto di oggi."""
    print("\nun'evidenza nuova e' completa")
    finta = Finta()
    try:
        import yaml

        (finta.base / "evidenze").mkdir(exist_ok=True)
        (finta.base / "evidenze" / "TEST-001-revisione.yaml").write_text(
            yaml.safe_dump(
                {"task_id": "TEST-001", "frozen_at": "2020-01-01T00:00:00+00:00"}
            ),
            encoding="utf-8",
        )
        finta.scrivi(EVIDENZA_VALIDA)
        finta.invecchia(2)  # ferma, ma dopo il congelamento
        osservazione = attesa.osserva(finta.percorso, "TEST-001", "QA", soglia=1)
        check(
            "stato completa",
            osservazione.stato == attesa.COMPLETA,
            f"{osservazione.stato}: {osservazione.motivo}",
        )
    finally:
        finta.chiudi()


def test_verifica_senza_registro_fallisce() -> None:
    """DEC-0109 — il monitoraggio obbligatorio deve **mordere** quando non c'e'.

    Il CEO, il 2026-11-06: «il monitoraggio da oggi è obbligatorio su tutto ciò che viene
    lanciato, non si può rischiare che un lavoro venga bloccato a causa di una svista o una
    mancata lettura quando il risultato c'è».

    Una regola cosi', se resta un'abitudine, vale fino alla prima distrazione — e io mi sono
    distratto quattro volte in un giorno. Il registro e' la prova che l'attesa c'e' stata.
    """
    print("\nDEC-0109 — senza registro, la verifica fallisce")
    finta = Finta()
    try:
        esito = attesa.verifica("TEST-001", root=finta.base)
        check("esce 1 senza registro", esito == 1, str(esito))
    finally:
        finta.chiudi()


def test_verifica_con_registro_incompleto_fallisce() -> None:
    """Un registro che si ferma a «assente» dice che qualcuno ha guardato e poi ha smesso."""
    print("\nDEC-0109 — registro incompleto")
    finta = Finta()
    try:
        (finta.base / "evidenze").mkdir(exist_ok=True)
        registro = attesa.percorso_registro("TEST-001", finta.base)
        # C'e' solo il CodeReview completo: il QA manca.
        registro.write_text(
            '{"quando":"2026-11-06T16:00:00","stato":"completa","file":"TEST-001-CodeReview.yaml","byte":100,"motivo":""}\n'
            '{"quando":"2026-11-06T16:01:00","stato":"assente","file":"TEST-001-QA.yaml","byte":0,"motivo":""}\n',
            encoding="utf-8",
        )
        esito = attesa.verifica("TEST-001", root=finta.base)
        check("esce 1 con un ruolo mai completo", esito == 1, str(esito))
    finally:
        finta.chiudi()


def test_verifica_con_registro_completo_passa() -> None:
    """La controprova: entrambi i ruoli completi, la verifica passa."""
    print("\nDEC-0109 — registro completo")
    finta = Finta()
    try:
        (finta.base / "evidenze").mkdir(exist_ok=True)
        registro = attesa.percorso_registro("TEST-001", finta.base)
        registro.write_text(
            '{"quando":"2026-11-06T16:00:00","stato":"completa","file":"TEST-001-QA.yaml","byte":100,"motivo":""}\n'
            '{"quando":"2026-11-06T16:01:00","stato":"completa","file":"TEST-001-CodeReview.yaml","byte":200,"motivo":""}\n',
            encoding="utf-8",
        )
        esito = attesa.verifica("TEST-001", root=finta.base)
        check("esce 0 con entrambi completi", esito == 0, str(esito))
    finally:
        finta.chiudi()


def test_il_registro_si_aggiunge_non_si_riscrive() -> None:
    """Due giri lasciano due righe: il registro e' una traccia, non uno stato."""
    print("\nDEC-0109 — il registro si aggiunge")
    finta = Finta()
    try:
        (finta.base / "evidenze").mkdir(exist_ok=True)
        osservazione = attesa.Osservazione(attesa.COMPLETA, Path("TEST-001-QA.yaml"), 100)
        attesa.registra("TEST-001", [osservazione], finta.base)
        attesa.registra("TEST-001", [osservazione], finta.base)
        registro = attesa.percorso_registro("TEST-001", finta.base)
        righe = [r for r in registro.read_text(encoding="utf-8").splitlines() if r.strip()]
        check("due giri, due righe", len(righe) == 2, f"{len(righe)} righe")
    finally:
        finta.chiudi()


def main() -> int:
    print("l'attesa si misura sul file")
    test_assente()
    test_in_crescita()
    test_ferma_oltre_la_soglia()
    test_completa()
    test_non_valida_mai_completa()
    test_evidenza_di_un_giro_precedente()
    test_fail_e_un_verdetto_non_un_incompiuto()
    test_esito_unknown_no_e_completa()
    test_evidenza_nuova_e_completa()
    test_il_ruolo_del_gate_e_diverso_dal_nome_del_file()
    test_verifica_senza_registro_fallisce()
    test_verifica_con_registro_incompleto_fallisce()
    test_verifica_con_registro_completo_passa()
    test_il_registro_si_aggiunge_non_si_riscrive()
    test_il_motore_vero_e_completo()
    print()
    if FALLITI:
        print(f"FALLITO — {len(FALLITI)} controlli: " + ", ".join(FALLITI))
        return 1
    print("PASS — i sei stati si distinguono, e «vecchia» non si legge come «completa»")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
