#!/usr/bin/env python3
"""Il libro mastro dei trasferimenti: le cinque regole, provate in negativo (DEC-0093).

Il protocollo esiste per un motivo preciso: il 2026-11-02 la macchina si e' fermata su
`percorso-gia-di-un-altro` mentre il lavoro era pronto e verde. La reazione giusta e'
stata fermarsi (invariante 9), ma senza una via d'uscita ogni ritiro blocca i percorsi
per sempre. La via d'uscita e' un atto esplicito: questo test prova che l'atto
**rifiuta** quando deve, perche' un protocollo che accetta tutto non e' un protocollo.

Si esegue dalla radice:
    python3 tools/tests/test_ad_transfer.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE / "tools"))

import ad_transfer  # noqa: E402

FALLITI: list[str] = []


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    if condizione:
        print(f"  ok   {etichetta}")
    else:
        print(f"  NO   {etichetta}  {dettaglio}")
        FALLITI.append(etichetta)


def contract(base: Path, task: str, *, stato: str, percorsi: list[str]) -> None:
    """Scrive un contract finto, nella forma minima che il trasferimento legge."""
    cartella = base / "contratti" / "societa"
    cartella.mkdir(parents=True, exist_ok=True)
    (cartella / f"{task}.yaml").write_text(
        yaml.safe_dump(
            {"task_id": task, "status": stato, "write_scope": percorsi},
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def radice() -> Path:
    """Una radice temporanea, con un repository git vero (le modifiche concorrenti si vedono)."""
    base = Path(tempfile.mkdtemp())
    subprocess.run(["git", "init", "-q"], cwd=str(base), capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=str(base), capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=str(base), capture_output=True)
    (base / "DECISIONI").mkdir()
    (base / "DECISIONI" / "DEC-0001-prova.md").write_text("# prova\n", encoding="utf-8")
    return base


def chiudi(base: Path) -> None:
    shutil.rmtree(base, ignore_errors=True)


def test_cedente_deve_essere_ritirato() -> None:
    """Un contract che lavora non cede i suoi percorsi: e' la differenza che conta."""
    print("\nun contract attivo non puo' cedere")
    base = radice()
    try:
        contract(base, "AAA", stato="active", percorsi=["p/a.py"])
        contract(base, "BBB", stato="active", percorsi=[])
        try:
            ad_transfer.verifica("AAA", "BBB", base)
            check("attivo non cede", False, "il trasferimento e' stato permesso")
        except ad_transfer.Rifiuto as errore:
            check("attivo non cede", "active" in str(errore), str(errore))
    finally:
        chiudi(base)


def test_cedente_ritirato_puo_cedere() -> None:
    """Un contract superseded cede: e' il caso che ha bloccato il 2026-11-02."""
    print("\nun contract ritirato cede")
    base = radice()
    try:
        contract(base, "AAA", stato="superseded", percorsi=["p/a.py", "p/b.py"])
        contract(base, "BBB", stato="active", percorsi=["p/a.py", "p/b.py"])
        elenco, avvisi = ad_transfer.verifica("AAA", "BBB", base)
        check("superseded cede", len(elenco) == 2, str(elenco))
        check("senza avvisi se i percorsi sono del ricevente", not avvisi, str(avvisi))
    finally:
        chiudi(base)


def test_ricevente_deve_essere_attivo() -> None:
    """Non si trasferisce a un contract che non puo' ricevere."""
    print("\nii ricevente deve essere attivo")
    base = radice()
    try:
        contract(base, "AAA", stato="superseded", percorsi=["p/a.py"])
        contract(base, "BBB", stato="closed", percorsi=["p/a.py"])
        try:
            ad_transfer.verifica("AAA", "BBB", base)
            check("chiuso non riceve", False, "il trasferimento e' stato permesso")
        except ad_transfer.Rifiuto as errore:
            check("chiuso non riceve", "closed" in str(errore), str(errore))
    finally:
        chiudi(base)


def test_modifiche_concorrenti_bloccano() -> None:
    """Trasferire un percorso sporco mescolerebbe due lavori."""
    print("\nuna modifica non committata blocca il trasferimento")
    base = radice()
    try:
        (base / "p").mkdir()
        (base / "p" / "a.py").write_text("originale\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=str(base), capture_output=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=str(base), capture_output=True)
        contract(base, "AAA", stato="superseded", percorsi=["p/a.py"])
        contract(base, "BBB", stato="active", percorsi=["p/a.py"])
        (base / "p" / "a.py").write_text("cambiato\n", encoding="utf-8")
        try:
            ad_transfer.verifica("AAA", "BBB", base)
            check("sporco blocca", False, "il trasferimento e' stato permesso")
        except ad_transfer.Rifiuto as errore:
            check("sporco blocca", "non committate" in str(errore), str(errore))
    finally:
        chiudi(base)


def test_senza_decisione_non_si_trasferisce() -> None:
    """Un atto senza titolo non si fa: e' la regola che rende il protocollo una garanzia."""
    print("\nun trasferimento senza decisione e' rifiutato")
    base = radice()
    try:
        contract(base, "AAA", stato="superseded", percorsi=["p/a.py"])
        contract(base, "BBB", stato="active", percorsi=["p/a.py"])
        try:
            ad_transfer.trasferisci("AAA", "BBB", "", base)
            check("senza decisione rifiuta", False, "il trasferimento e' stato fatto")
        except ad_transfer.Rifiuto as errore:
            check("senza decisione rifiuta", "decisione" in str(errore), str(errore))
        try:
            ad_transfer.trasferisci("AAA", "BBB", "DECISIONI/DEC-9999-manca.md", base)
            check("decisione inesistente rifiuta", False, "il trasferimento e' stato fatto")
        except ad_transfer.Rifiuto as errore:
            check("decisione inesistente rifiuta", "non esiste" in str(errore), str(errore))
    finally:
        chiudi(base)


def test_trasferimento_riesce_e_si_registra() -> None:
    """Il caso felice: percorsi registrati, libro scritto, storia intatta."""
    print("\nil trasferimento riuscito")
    base = radice()
    try:
        contract(base, "AAA", stato="superseded", percorsi=["p/a.py"])
        contract(base, "BBB", stato="active", percorsi=["p/a.py"])
        esito = ad_transfer.trasferisci(
            "AAA", "BBB", "DECISIONI/DEC-0001-prova.md", base
        )
        check("due percorsi ceduti", len(esito["voce"]["percorsi"]) == 1, str(esito["voce"]))
        libro = base / "contratti" / "_trasferimenti.yaml"
        check("il libro mastro esiste", libro.is_file())
        dato = yaml.safe_load(libro.read_text(encoding="utf-8"))
        voci = dato.get("trasferimenti") or []
        check("una voce nel libro", len(voci) == 1, str(voci))
        check("la voce dice chi a chi", voci[0]["da"] == "AAA" and voci[0]["a"] == "BBB")
        check("la voce dice con quale decisione", "DEC-0001" in voci[0]["decisione"])
        check(
            "il contract del cedente NON e' stato modificato",
            "superseded" in (base / "contratti" / "societa" / "AAA.yaml").read_text(encoding="utf-8"),
        )
        # secondo trasferimento: si aggiunge, non si riscrive
        ad_transfer.trasferisci("AAA", "BBB", "DECISIONI/DEC-0001-prova.md", base)
        dato2 = yaml.safe_load(libro.read_text(encoding="utf-8"))
        check("il libro si aggiunge", len(dato2["trasferimenti"]) == 2,
              f"{len(dato2['trasferimenti'])} voci")
    finally:
        chiudi(base)


def test_percorso_gia_trasferito_altrove() -> None:
    """Due riceventi per lo stesso percorso e' il conflitto che il protocollo deve impedire."""
    print("\nun percorso gia' ceduto non va a un secondo ricevente")
    base = radice()
    try:
        contract(base, "AAA", stato="superseded", percorsi=["p/a.py"])
        contract(base, "BBB", stato="active", percorsi=["p/a.py"])
        contract(base, "CCC", stato="active", percorsi=["p/a.py"])
        ad_transfer.trasferisci("AAA", "BBB", "DECISIONI/DEC-0001-prova.md", base)
        try:
            ad_transfer.verifica("AAA", "CCC", base)
            check("doppio ricevente rifiuta", False, "il secondo trasferimento e' permesso")
        except ad_transfer.Rifiuto as errore:
            check("doppio ricevente rifiuta", "gia' stati trasferiti" in str(errore), str(errore))
    finally:
        chiudi(base)


def test_protocollo_non_modifica_gli_stati() -> None:
    """Il protocollo dichiara un trasferimento: non chiude e non ritira niente."""
    print("\nil protocollo non cambia lo stato di nessun contract")
    base = radice()
    try:
        contract(base, "AAA", stato="superseded", percorsi=["p/a.py"])
        contract(base, "BBB", stato="active", percorsi=["p/a.py"])
        prima = (base / "contratti" / "societa" / "BBB.yaml").read_text(encoding="utf-8")
        ad_transfer.trasferisci("AAA", "BBB", "DECISIONI/DEC-0001-prova.md", base)
        dopo = (base / "contratti" / "societa" / "BBB.yaml").read_text(encoding="utf-8")
        check("il ricevente e' intatto", prima == dopo)
    finally:
        chiudi(base)


def main() -> int:
    print("il libro mastro dei trasferimenti (DEC-0093)")
    test_cedente_deve_essere_ritirato()
    test_cedente_ritirato_puo_cedere()
    test_ricevente_deve_essere_attivo()
    test_modifiche_concorrenti_bloccano()
    test_senza_decisione_non_si_trasferisce()
    test_trasferimento_riesce_e_si_registra()
    test_percorso_gia_trasferito_altrove()
    test_protocollo_non_modifica_gli_stati()
    print()
    if FALLITI:
        print(f"FALLITO — {len(FALLITI)} controlli: " + ", ".join(FALLITI))
        return 1
    print("PASS — il protocollo rifiuta quando deve, e registra quando trasferisce")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
