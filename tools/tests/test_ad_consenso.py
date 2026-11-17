#!/usr/bin/env python3
"""Il consenso verificabile: la firma dice chi, non solo cosa (DEC-0096).

Il difetto che questo test difende: un'approvazione valeva se il file aveva tre campi.
Chiunque potesse scrivere in `approvazioni/` creava un marcatore che diceva «approvato da
Luca», e il cancello lo accettava. **Un file che afferma un consenso non e' un consenso.**

I cinque casi che contano, tutti in negativo:
  1. manomettere un campo dopo la firma -> `manomessa`
  2. cambiare il piano dopo l'approvazione -> `piano cambiato`
  3. firmare senza i tre campi obbligatori -> rifiutato
  4. una chiave leggibile da altri -> rifiutata (la firma non vale se il segreto e' pubblico)
  5. un marcatore senza firma -> `legacy`, e **non** un errore: e' la storia

Si esegue dalla radice:
    python3 tools/tests/test_ad_consenso.py
"""

from __future__ import annotations

import os
import shutil
import stat
import sys
import tempfile
from pathlib import Path

import yaml

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE / "tools"))

import ad_consenso  # noqa: E402

FALLITI: list[str] = []


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    if condizione:
        print(f"  ok   {etichetta}")
    else:
        print(f"  NO   {etichetta}  {dettaglio}")
        FALLITI.append(etichetta)


class CasaFinta:
    """Una casa con la chiave in una cartella temporanea, e la radice del motore finta.

    La chiave si sposta perche' il test non deve toccare `~/.dsh`: una prova che
    scrive nella home dell'utente non e' una prova, e' un effetto collaterale.
    """

    def __init__(self) -> None:
        self.base = Path(tempfile.mkdtemp())
        self.casa = self.base / "casa"
        self.radice = self.base / "motore"
        (self.casa / ".dsh").mkdir(parents=True)
        (self.radice / "approvazioni" / "societa").mkdir(parents=True)
        (self.radice / "DECISIONI").mkdir(parents=True)

    def __enter__(self) -> "CasaFinta":
        self._prima_casa = ad_consenso.CARTELLA_CHIAVE
        self._prima_radice = ad_consenso.RADICE
        ad_consenso.CARTELLA_CHIAVE = self.casa / ".dsh"
        ad_consenso.RADICE = self.radice
        return self

    def __exit__(self, *_errore: object) -> None:
        ad_consenso.CARTELLA_CHIAVE = self._prima_casa
        ad_consenso.RADICE = self._prima_radice
        shutil.rmtree(self.base, ignore_errors=True)

    def chiave(self, *, modo: int = 0o600) -> Path:
        percorso = self.casa / ".dsh" / ad_consenso.NOME_CHIAVE
        percorso.write_bytes(b"k" * 64)
        os.chmod(percorso, modo)
        return percorso

    def piano(self, nome: str = "DECISIONI/DEC-0001-piano.md", testo: str = "# piano\n") -> Path:
        percorso = self.radice / nome
        percorso.parent.mkdir(parents=True, exist_ok=True)
        percorso.write_text(testo, encoding="utf-8")
        return percorso

    def marcatore(self, task: str = "T-1", **extra: object) -> Path:
        dati = {
            "task_id": task,
            "approvato_da": "Luca",
            "data": "2026-11-02T10:00:00+01:00",
            "piano": "DECISIONI/DEC-0001-piano.md",
            "consenso": "approvato",
        }
        dati.update(extra)
        percorso = self.radice / "approvazioni" / "societa" / f"{task}.yaml"
        percorso.write_text(yaml.safe_dump(dati, sort_keys=False), encoding="utf-8")
        return percorso


def test_firma_e_verifica() -> None:
    """Il caso felice: firmata, verificata, e la provenienza c'e'."""
    print("\nuna firma valida")
    with CasaFinta() as casa:
        casa.chiave()
        casa.piano()
        casa.marcatore()
        dati = ad_consenso.firma("T-1", "chat", casa.radice)
        check("la firma e' scritta", bool(dati.get("firma")), str(dati.keys()))
        check("la provenienza c'e'", dati.get("superficie") == "chat", str(dati.get("superficie")))
        check("il momento della firma e' distinto dal consenso",
              dati.get("firmato_il") != dati.get("data"))
        check("il piano e' legato con la sua impronta", bool(dati.get("piano_sha256")))
        chiave = ad_consenso.leggi_chiave()
        stato, messaggio = ad_consenso.verifica_uno(
            casa.radice / "approvazioni" / "societa" / "T-1.yaml", chiave, casa.radice
        )
        check("risulta firmata", stato == "firmata", f"{stato}: {messaggio}")


def test_manomissione() -> None:
    """Un campo cambiato dopo la firma: la firma non combacia, e si vede."""
    print("\nmanomettere un campo")
    with CasaFinta() as casa:
        casa.chiave()
        casa.piano()
        percorso = casa.marcatore()
        ad_consenso.firma("T-1", "chat", casa.radice)
        dati = yaml.safe_load(percorso.read_text(encoding="utf-8"))
        dati["consenso"] = "approvato DOPO, e anche di piu'"
        percorso.write_text(yaml.safe_dump(dati, sort_keys=False), encoding="utf-8")
        chiave = ad_consenso.leggi_chiave()
        stato, _ = ad_consenso.verifica_uno(percorso, chiave, casa.radice)
        check("manomessa", stato == "manomessa", stato)


def test_piano_cambiato() -> None:
    """Il piano approvato e' cambiato: il consenso era a un altro testo."""
    print("\n cambiare il piano dopo l'approvazione")
    with CasaFinta() as casa:
        casa.chiave()
        piano = casa.piano()
        percorso = casa.marcatore()
        ad_consenso.firma("T-1", "chat", casa.radice)
        piano.write_text("# piano DIVERSO, scritto dopo\n", encoding="utf-8")
        chiave = ad_consenso.leggi_chiave()
        stato, messaggio = ad_consenso.verifica_uno(percorso, chiave, casa.radice)
        check("piano cambiato", stato == "piano cambiato", f"{stato}: {messaggio}")


def test_non_si_firma_un_incompleto() -> None:
    """Firmare un marcatore senza i tre campi gli darebbe un'autorita' che non ha."""
    print("\n un marcatore incompleto non si firma")
    with CasaFinta() as casa:
        casa.chiave()
        casa.piano()
        (casa.radice / "approvazioni" / "societa" / "T-2.yaml").write_text(
            yaml.safe_dump({"task_id": "T-2", "consenso": "si'"}, sort_keys=False),
            encoding="utf-8",
        )
        try:
            ad_consenso.firma("T-2", "chat", casa.radice)
            check("incompleto rifiutato", False, "la firma e' stata scritta")
        except ad_consenso.Rifiuto as errore:
            check("incompleto rifiutato", "non ha" in str(errore), str(errore))


def test_chiave_esposta() -> None:
    """Una chiave leggibile da altri non e' un segreto, e una firma senza segreto non vale."""
    print("\n una chiave leggibile da altri")
    with CasaFinta() as casa:
        casa.chiave(modo=0o644)
        casa.piano()
        casa.marcatore()
        try:
            ad_consenso.leggi_chiave()
            check("chiave 644 rifiutata", False, "la chiave e' stata accettata")
        except ad_consenso.Rifiuto as errore:
            check("chiave 644 rifiutata", "leggibile da altri" in str(errore), str(errore))


def test_legacy_non_e_un_errore() -> None:
    """Le 413 approvazioni senza firma sono la storia, non un difetto da correggere."""
    print("\n un marcatore senza firma e' legacy, non un errore")
    with CasaFinta() as casa:
        casa.chiave()
        casa.piano()
        percorso = casa.marcatore()
        chiave = ad_consenso.leggi_chiave()
        stato, _ = ad_consenso.verifica_uno(percorso, chiave, casa.radice)
        check("legacy", stato == "non firmata (legacy)", stato)
        # e `verifica_tutti` non lo conta come guaio
        esiti = ad_consenso.verifica_tutti(casa.radice)
        gravi = [e for e in esiti if e[0] not in ("firmata", "non firmata (legacy)")]
        check("non conta come problema", not gravi, str(gravi))


def test_firma_con_chiave_diversa_non_vale() -> None:
    """La ragione d'essere della firma: senza la chiave non si puo' rifarla."""
    print("\n una firma con un'altra chiave non vale")
    with CasaFinta() as casa:
        casa.chiave()
        casa.piano()
        percorso = casa.marcatore()
        ad_consenso.firma("T-1", "chat", casa.radice)
        # un altro firmatario, con la sua chiave
        altra = bytes(b"z" * 64)
        dati = yaml.safe_load(percorso.read_text(encoding="utf-8"))
        dati["firma"] = ad_consenso.calcola_firma(dati, altra)
        percorso.write_text(yaml.safe_dump(dati, sort_keys=False), encoding="utf-8")
        chiave = ad_consenso.leggi_chiave()
        stato, _ = ad_consenso.verifica_uno(percorso, chiave, casa.radice)
        check("firma di un altro -> manomessa", stato == "manomessa", stato)


def main() -> int:
    print("il consenso verificabile (DEC-0096)")
    test_firma_e_verifica()
    test_manomissione()
    test_piano_cambiato()
    test_non_si_firma_un_incompleto()
    test_chiave_esposta()
    test_legacy_non_e_un_errore()
    test_firma_con_chiave_diversa_non_vale()
    print()
    if FALLITI:
        print(f"FALLITO — {len(FALLITI)} controlli: " + ", ".join(FALLITI))
        return 1
    print("PASS — la firma distingue un consenso da un file che lo afferma")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
