#!/usr/bin/env python3
"""I verbali sono immutabili, e la prova e' git (`ERR-0081`, `DEC-0121`).

Prima: il registro diceva «immutabili», nessuno lo controllava. Un verbale riscritto dopo il
commit cambiava la storia in silenzio. `verbali.py check` ora confronta ogni verbale con la
versione in `HEAD`: se differisce, e' un errore.

Si prova su un repository git finto, in `/tmp`.

    python3 tools/tests/test_verbali_immutabili.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE / "tools"))

import verbali  # noqa: E402

FALLITI: list[str] = []
PASSATI = 0

VERBALE = """# DEC-9001 — esempio per il test

```yaml
id: DEC-9001
stato: approvato
data: 2026-11-16
approver: CEO
```

## Problema

Un problema di prova, per esercitare la guardia sull'immutabilita'.

## Opzioni

1. **Non fare nulla** — costo zero.
2. **Fare** — fonte: https://example.com/documento, consultato il 2026-11-16.

## Evidenze

- una prova di prova.

## Conseguenze

- nessuna, e' un test.

## Data di revisione

2026-12-16

## Esito misurato

Da compilare alla data di revisione.
"""


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    global PASSATI
    if condizione:
        print(f"  ok   {etichetta}")
        PASSATI += 1
    else:
        print(f"  NO   {etichetta}  {dettaglio}")
        FALLITI.append(etichetta)


def _git(base: Path, *argomenti: str) -> None:
    subprocess.run(
        ["git", *argomenti],
        cwd=base,
        check=True,
        capture_output=True,
        env={
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
            "PATH": "/usr/bin:/bin",
        },
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="ad-verbali-") as tmp:
        base = Path(tmp)
        cartella = base / "DECISIONI"
        cartella.mkdir()
        percorso = cartella / "DEC-9001-esempio.md"
        percorso.write_text(VERBALE, encoding="utf-8")
        _git(base, "init", "-q")
        _git(base, "add", "DECISIONI/DEC-9001-esempio.md")
        _git(base, "commit", "-q", "-m", "verbale di prova")

        errori, _ = verbali.problemi(base)
        check("verbale committato e non toccato: nessun errore di immutabilita'",
              not any("verbale modificato" in e for e in errori), str(errori)[:300])

        # Riscrittura dopo il commit: la regola deve mordere.
        percorso.write_text(VERBALE.replace("nessuna", "una"), encoding="utf-8")
        errori, _ = verbali.problemi(base)
        check("verbale modificato dopo il commit: ERRORE",
              any("verbale modificato" in e for e in errori), str(errori)[:300])
        check("il messaggio cita ERR-0081", any("ERR-0081" in e for e in errori), str(errori)[:300])

        # Un verbale nuovo, non ancora committato, non ha una storia da difendere.
        nuovo = cartella / "DEC-9002-nuovo.md"
        nuovo.write_text(VERBALE.replace("DEC-9001", "DEC-9002"), encoding="utf-8")
        errori, _ = verbali.problemi(base)
        check("verbale nuovo non committato: nessun errore di immutabilita'",
              not any("DEC-9002" in e and "verbale modificato" in e for e in errori),
              str(errori)[:300])

    print()
    print(f"  {PASSATI} controlli passati")
    if FALLITI:
        print(f"FALLITI: {len(FALLITI)}")
        return 1
    print("PASS — un verbale riscritto non passa piu' in silenzio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
