#!/usr/bin/env python3
"""Il motore e' separato dai progetti (`DEC-0111`, M1 del 2026-11-15).

Prima esisteva anche `100.AAP`, una seconda macchina in casa (`GOV-027`) con un progetto
dentro. Il CEO l'ha dichiarata un test e l'ha fatta cancellare: il motore deve stare da solo
in una cartella, e i progetti in quella dichiarata da `sede.yaml`.

Questo file difende due cose:

1. **i progetti stanno fuori**: nessuna cartella numerata dentro la cartella del motore;
2. **la macchina non si confonde con un prodotto**: `100.AAP` non e' piu' dichiarata
   macchina, e `CARTELLE_MACCHINA` non contiene nomi che non esistono.

Si esegue dalla radice:
    python3 tools/tests/test_100_aap.py
"""

from __future__ import annotations

import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE / "tools"))

import ad_docs  # noqa: E402
import ad_scope  # noqa: E402

FALLITI: list[str] = []


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    if condizione:
        print(f"  ok   {etichetta}")
    else:
        print(f"  NO   {etichetta}  {dettaglio}")
        FALLITI.append(etichetta)


def test_nessun_progetto_dentro_il_motore() -> None:
    """Le cartelle numerate non stanno nella cartella del motore."""
    print("\nnessun progetto dentro il motore")
    dentro = sorted(
        voce.name
        for voce in RADICE.iterdir()
        if voce.is_dir() and ad_scope.PROTECTED_DIR.match(voce.name)
    )
    check("la cartella del motore non contiene cartelle numerate", not dentro, str(dentro))


def test_la_cartella_dei_progetti_e_dichiarata() -> None:
    """`sede.yaml` dice dove stanno i progetti, e ci sono."""
    print("\nla cartella dei progetti e' dichiarata")
    check(
        "macchina.progetti e' dichiarato",
        bool(str(ad_docs.sede().get("macchina", {}).get("progetti") or "").strip()),
        str(ad_docs.sede().get("macchina")),
    )
    check("la cartella esiste", ad_docs.PROGETTI_ROOT.is_dir(), str(ad_docs.PROGETTI_ROOT))
    check(
        "e contiene progetti",
        any(ad_docs.PROGETTI_ROOT.iterdir()),
        str(ad_docs.PROGETTI_ROOT),
    )


def test_100_aap_non_e_piu_dichiarata() -> None:
    """La seconda macchina non c'e' piu': nemmeno la dichiarazione deve restare."""
    print("\n100.AAP non e' piu' dichiarata")
    check("100.AAP non e' in CARTELLE_MACCHINA", "100.AAP" not in ad_scope.CARTELLE_MACCHINA)
    check("100.AAP non esiste piu' su disco", not (RADICE / "100.AAP").exists())


def test_i_gruppi_del_registro_sono_collegamenti() -> None:
    """I gruppi dei progetti sono collegamenti al registro che vive nel progetto."""
    print("\ni gruppi del registro sono collegamenti")
    for registro in ("contratti", "approvazioni"):
        cartella = RADICE / registro
        if not cartella.is_dir():
            continue
        for voce in sorted(cartella.iterdir()):
            if not voce.is_dir() or voce.name == "societa" or voce.name.startswith("_"):
                continue
            check(f"{registro}/{voce.name} e' un collegamento", voce.is_symlink(), str(voce))
            check(f"{registro}/{voce.name} punta a qualcosa", voce.exists(), str(voce))


def main() -> int:
    test_nessun_progetto_dentro_il_motore()
    test_la_cartella_dei_progetti_e_dichiarata()
    test_100_aap_non_e_piu_dichiarata()
    test_i_gruppi_del_registro_sono_collegamenti()
    print()
    if FALLITI:
        print(f"FALLITI: {len(FALLITI)}")
        return 1
    print("tutto ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
