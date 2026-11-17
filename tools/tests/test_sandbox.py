#!/usr/bin/env python3
"""La sandbox fa quello che dichiara (M2, `DEC-0112`).

Non basta che `bwrap` esista: si prova che dentro la sandbox **la rete e' spenta**, che
`/tmp` si scrive e fuori non si scrive, e che l'ambiente non si eredita. Se `bwrap` manca,
il test dichiara `SKIP` e non finge un verde.

Si esegue dalla radice:
    python3 tools/tests/test_sandbox.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE / "tools"))

import sandbox  # noqa: E402

FALLITI: list[str] = []


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    if condizione:
        print(f"  ok   {etichetta}")
    else:
        print(f"  NO   {etichetta}  {dettaglio}")
        FALLITI.append(etichetta)


def main() -> int:
    print("la sandbox")
    if sandbox.bwrap_disponibile() is None:
        print("  SKIP — bubblewrap non installato: nessuna sandbox da provare")
        print("\nSKIP — non un verde")
        return 0

    esito = subprocess.run(
        [sys.executable, str(RADICE / "tools" / "sandbox.py"), "--autotest"],
        cwd=str(RADICE), capture_output=True, text=True, timeout=120,
    )
    check("l'autotest esce 0", esito.returncode == 0, (esito.stdout + esito.stderr)[-300:])
    for promessa in ("la rete e' spenta", "dentro /tmp si scrive", "fuori da /tmp non si scrive"):
        check(f"promessa verificata: {promessa}", promessa in esito.stdout)

    print("\nl'esecuzione di un comando innocuo")
    innocuo = sandbox.esegui(["python3", "-c", "print(2+2)"], timeout=60)
    check("il comando innocuo gira", innocuo.returncode == 0 and "4" in innocuo.stdout, innocuo.stderr[:200])

    print("\nle cartelle nascoste (DEC-0115: la chiave non deve essere leggibile)")
    import shutil
    import uuid

    # Cartella FUORI da /tmp: la sandbox maschera /tmp con un tmpfs.
    cartella = Path.home() / ".cache" / f"ad-sandbox-test-{uuid.uuid4().hex}"
    cartella.mkdir(parents=True)
    (cartella / "chiave").write_text("x", encoding="utf-8")
    try:
        comando = ["sh", "-c", f"test -r {cartella}/chiave"]
        visibile = sandbox.esegui(comando, timeout=60)
        nascosto = sandbox.esegui(comando, timeout=60, nascondi=(cartella,))
        check("una cartella non nascosta si legge", visibile.returncode == 0, str(visibile))
        check("una cartella nascosta NON si legge", nascosto.returncode != 0, str(nascosto))
    finally:
        shutil.rmtree(cartella, ignore_errors=True)

    print()
    if FALLITI:
        print(f"FALLITI: {len(FALLITI)}")
        return 1
    print("PASS — la sandbox fa quello che dichiara")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
