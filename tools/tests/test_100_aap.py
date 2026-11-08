#!/usr/bin/env python3
"""`100.AAP` è una seconda macchina, non un prodotto (`GOV-027`).

Il CEO ha chiesto il 2026-11-07: *«costruisci questo nuovo AAP in una cartella qui come se
fosse un progetto e chiamalo 100.AAP»*. E poi ha spiegato l'intento: importare progetti da
altri motori e trattarli come nuovi.

Il nodo che questo file difende: **una cartella numerata è un prodotto**, e `PROTECTED_DIR`
lo decide da `^\\d+\\.`. Ma `100.AAP` è una macchina: ha il suo cervello, i suoi registri, il
suo CEO. Senza una regola, ogni scrittura in una seconda macchina chiederebbe un contract
della prima, che è il contrario di autonomo.

La regola sta in un posto solo: `ad_scope.CARTELLE_MACCHINA`. Se una cartella è lì, non è
un prodotto — neanche se il nome comincia con un numero.

Si esegue dalla radice:
    python3 tools/tests/test_100_aap.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE / "tools"))

import ad_scope  # noqa: E402

FALLITI: list[str] = []

SECONDA = RADICE / "100.AAP"


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    if condizione:
        print(f"  ok   {etichetta}")
    else:
        print(f"  NO   {etichetta}  {dettaglio}")
        FALLITI.append(etichetta)


def test_la_regola_esiste() -> None:
    """`100.AAP` è dichiarata macchina, in un posto solo."""
    print("\nla regola esiste")
    check(
        "100.AAP è in CARTELLE_MACCHINA",
        "100.AAP" in ad_scope.CARTELLE_MACCHINA,
        str(sorted(ad_scope.CARTELLE_MACCHINA)[-3:]),
    )


def test_il_cancello_la_lascia_toccare() -> None:
    """Una macchina si tocca: il cancello non chiede un contract della prima macchina."""
    print("\nil cancello la lascia toccare")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        (base / "tools").mkdir()
        for nome in ("contract_scope.py", "ad_scope.py"):
            (base / "tools" / nome).write_bytes((RADICE / "tools" / nome).read_bytes())
        for nome in ("contratti", "approvazioni"):
            (base / nome / "societa").mkdir(parents=True)
        (base / "100.AAP").mkdir()
        (base / "100.AAP" / "sede.yaml").write_text("ceo:\n  nome: X\n", encoding="utf-8")

        esito = subprocess.run(
            [sys.executable, str(base / "tools" / "contract_scope.py"),
             "check", "100.AAP/sede.yaml"],
            cwd=str(base), capture_output=True, text=True, timeout=120,
        )
        # Con la regola, 100.AAP non è una cartella prodotto: il cancello non la blocca
        testo = esito.stdout + esito.stderr
        check(
            "non dice «non è raggruppata» né «fuori da ogni gruppo»",
            "non e' raggruppat" not in testo and "fuori da ogni gruppo" not in testo,
            testo[:160],
        )


def test_un_progetto_resta_protetto() -> None:
    """La controprova: una cartella numerata che NON è macchina resta un prodotto."""
    print("\nun progetto resta protetto")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        (base / "tools").mkdir()
        for nome in ("contract_scope.py", "ad_scope.py"):
            (base / "tools" / nome).write_bytes((RADICE / "tools" / nome).read_bytes())
        for nome in ("contratti", "approvazioni"):
            (base / nome / "societa").mkdir(parents=True)
        (base / "8. Progetto").mkdir()

        esito = subprocess.run(
            [sys.executable, str(base / "tools" / "contract_scope.py"),
             "check", "8. Progetto/x.md"],
            cwd=str(base), capture_output=True, text=True, timeout=120,
        )
        check(
            "una scrittura in un progetto è negata",
            esito.returncode != 0,
            f"exit {esito.returncode}: una scrittura passerebbe senza permesso",
        )


def test_la_macchina_e_costruita() -> None:
    """`100.AAP` esiste, ha il cervello, i registri, e una sede propria."""
    print("\nla macchina è costruita")
    check("la cartella esiste", SECONDA.is_dir())
    if not SECONDA.is_dir():
        return
    for pezzo in (".brain", "tools", "tests", "sede.yaml"):
        check(f"{pezzo} c'è", (SECONDA / pezzo).exists())
    for registro in ("contratti", "approvazioni", "DECISIONI", "errori", "evidenze"):
        check(f"{registro}/ c'è", (SECONDA / registro).is_dir())


def test_la_sede_e_diversa() -> None:
    """Due macchine non sono una casa sola: la sede di 100.AAP non è quella del motore vero."""
    print("\nla sede è propria")
    sede = SECONDA / "sede.yaml"
    if not sede.is_file():
        check("sede.yaml esiste", False)
        return
    testo = sede.read_text(encoding="utf-8")
    vera = (RADICE / "sede.yaml").read_text(encoding="utf-8")
    check("la sede esiste", True)
    check(
        "non è copiata da quella del motore vero",
        testo != vera,
        "la seconda macchina ha ereditato la carta d'identità della prima",
    )
    check("dichiara un nome macchina", "macchina" in testo and "nome:" in testo)


def test_non_eredita_la_memoria_della_prima() -> None:
    """`100.AAP` nasce **senza la memoria** del motore vero, e senza i suoi nomi.

    Non «senza progetti»: una macchina di lavoro serve proprio a contenere progetti,
    importati con `importa.py`. Quello che non deve ereditare e' **la memoria della
    prima macchina** — i suoi registri, i suoi contratti, i suoi errori — e i nomi che
    quei registri portano.

    La differenza conta: una vetrina pubblica non deve contenere nomi di clienti; una
    macchina di lavoro, si'. Il controllo qui e' che i nomi non vengano dalla prima
    macchina, cioe' che non siano nei **suoi** registri.
    """
    print("\nnon eredita la memoria della prima macchina")
    if not SECONDA.is_dir():
        return

    # 1. I registri propri sono vuoti: nessun contract, nessuna decisione, nessun errore
    for registro, pattern in (
        ("contratti", "*.yaml"),
        ("DECISIONI", "*.md"),
        ("errori", "*.yaml"),
        ("approvazioni", "*.yaml"),
    ):
        cartella = SECONDA / registro
        if not cartella.is_dir():
            continue
        voci = [
            p for p in cartella.rglob(pattern)
            if p.is_file() and p.name not in ("README.md",)
        ]
        check(f"{registro}/ è vuoto (nessuna memoria ereditata)", not voci, str([p.name for p in voci][:4]))

    # 2. I nomi della prima macchina non sono nei registri PROPRI di 100.AAP
    #    (i progetti importati possono contenerli: sono progetti, non memoria).
    esito = subprocess.run(
        ["grep", "-rilE", "Modello|Progetto|Cliente|Esempio|Cognome",
         "--include=*.yaml", "--include=*.md",
         "contratti", "DECISIONI", "errori", "approvazioni", "evidenze"],
        cwd=SECONDA, capture_output=True, text=True,
    )
    residui = [r for r in esito.stdout.splitlines() if r.strip()]
    check(
        "nessun nome di cliente nei registri propri",
        not residui,
        str(residui[:5]),
    )


def main() -> int:
    print("100.AAP — una seconda macchina")
    test_la_regola_esiste()
    test_il_cancello_la_lascia_toccare()
    test_un_progetto_resta_protetto()
    test_la_macchina_e_costruita()
    test_la_sede_e_diversa()
    test_non_eredita_la_memoria_della_prima()
    print()
    if FALLITI:
        print(f"FALLITO — {len(FALLITI)} controlli: " + ", ".join(FALLITI))
        return 1
    print("PASS — è una macchina: autonoma, vuota, e distinta dalla prima")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
