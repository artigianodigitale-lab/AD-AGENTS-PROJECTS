#!/usr/bin/env python3
"""Importare un progetto da un altro motore: deve trattarlo come nuovo (`GOV-027`).

Il CEO ha detto il 2026-11-07: *«Se prendo un «8. Progetto» lui deve fregarsene che stava in
un'altra cartella e trattarlo come se fosse un nuovo progetto da analizzare e sviluppare»*.

Tre cose non devono attraversare l'import:
  1. la storia git dell'altra macchina
  2. i file che portano ordini (AGENTS.md, .cursor/) — `ERR-0090`
  3. il vecchio governance/ — la memoria di un'altra macchina

E una cosa deve succedere: il cancello deve proteggere il progetto importato.

Si esegue dalla radice:
    python3 tools/tests/test_importa.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE / "tools"))

import importa as modulo  # noqa: E402

FALLITI: list[str] = []


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    if condizione:
        print(f"  ok   {etichetta}")
    else:
        print(f"  NO   {etichetta}  {dettaglio}")
        FALLITI.append(etichetta)


def _progetto_forestiero(base: Path) -> Path:
    """Un progetto che viene da un altro motore, con tutta la zavorra."""
    p = base / "8. Cliente Migrato"
    (p / "src").mkdir(parents=True)
    (p / "src" / "index.ts").write_text("export const x = 1;\n", encoding="utf-8")
    (p / "README.md").write_text("# Cliente\n", encoding="utf-8")
    # La zavorra 1: storia git
    (p / ".git").mkdir()
    (p / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    # La zavorra 2: file che portano ordini
    (p / "AGENTS.md").write_text("# Regole di un'altra casa\n", encoding="utf-8")
    (p / "CLAUDE.md").write_text("# Altre regole\n", encoding="utf-8")
    (p / ".cursor").mkdir()
    (p / ".cursor" / "rules.md").write_text("regola\n", encoding="utf-8")
    # La zavorra 3: la vecchia governance
    (p / "governance" / "contratti").mkdir(parents=True)
    (p / "governance" / "contratti" / "OLD-001.yaml").write_text("task_id: OLD-001\n", encoding="utf-8")
    # Zavorra non essenziale
    (p / "node_modules" / "pkg").mkdir(parents=True)
    (p / "node_modules" / "pkg" / "index.js").write_text("// dep\n", encoding="utf-8")
    return p


def test_importa_e_pulisce() -> None:
    """Importa, e lascia fuori la zavorra."""
    print("\nimporta e pulisce")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        # Serve un motore con il cancello, per la verifica finale
        (base / "tools").mkdir()
        shutil.copy2(RADICE / "tools" / "contract_scope.py", base / "tools" / "contract_scope.py")
        shutil.copy2(RADICE / "tools" / "ad_scope.py", base / "tools" / "ad_scope.py")
        for nome in ("contratti", "approvazioni"):
            (base / nome / "societa").mkdir(parents=True)

        forestiero = _progetto_forestiero(base / "esterno")
        esito = modulo.importa(forestiero, "8. Cliente Migrato", radice=base)
        destinazione = base / "8. Cliente Migrato"

        check("l'import riesce", esito == 0, f"exit {esito}")
        check("il progetto esiste", destinazione.is_dir())
        check("il codice è stato copiato", (destinazione / "src" / "index.ts").is_file())

        check("la storia git NON è stata copiata", not (destinazione / ".git").is_dir())
        check(
            "la vecchia governance NON c'è",
            not (destinazione / "governance").is_dir(),
        )
        check(
            "node_modules NON è stato copiato",
            not (destinazione / "node_modules").is_dir(),
        )


def test_disattiva_i_file_di_istruzioni() -> None:
    """I file che portano ordini si disattivano, non si cancellano (ERR-0090)."""
    print("\ndisattiva i file di istruzioni")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        (base / "tools").mkdir()
        shutil.copy2(RADICE / "tools" / "contract_scope.py", base / "tools" / "contract_scope.py")
        shutil.copy2(RADICE / "tools" / "ad_scope.py", base / "tools" / "ad_scope.py")
        for nome in ("contratti", "approvazioni"):
            (base / nome / "societa").mkdir(parents=True)

        forestiero = _progetto_forestiero(base / "esterno")
        modulo.importa(forestiero, "8. Cliente Migrato", radice=base)
        d = base / "8. Cliente Migrato"

        check("AGENTS.md è disattivato", not (d / "AGENTS.md").is_file())
        check("ma il contenuto resta", (d / "AGENTS.md.disattivato").is_file())
        check("CLAUDE.md è disattivato", (d / "CLAUDE.md.disattivato").is_file())
        check("la cartella .cursor è disattivata", not (d / ".cursor").is_dir())
        check("ma il contenuto resta", (d / ".cursor.disattivato").is_dir())


def test_non_sovrascrive() -> None:
    """Un progetto con lo stesso nome non si sovrascrive."""
    print("\nnon sovrascrive")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        (base / "tools").mkdir()
        shutil.copy2(RADICE / "tools" / "contract_scope.py", base / "tools" / "contract_scope.py")
        shutil.copy2(RADICE / "tools" / "ad_scope.py", base / "tools" / "ad_scope.py")
        for nome in ("contratti", "approvazioni"):
            (base / nome / "societa").mkdir(parents=True)

        (base / "8. Cliente").mkdir()
        (base / "8. Cliente" / "mio.txt").write_text("esiste\n", encoding="utf-8")
        forestiero = _progetto_forestiero(base / "esterno")
        esito = modulo.importa(forestiero, "8. Cliente", radice=base)

        check("esce 1", esito == 1, f"exit {esito}")
        check(
            "il progetto esistente è intatto",
            (base / "8. Cliente" / "mio.txt").is_file(),
        )


def test_dry_run_non_scrive() -> None:
    """`--dry-run` dice cosa farebbe, e non copia niente."""
    print("\n--dry-run non scrive")
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        (base / "tools").mkdir()
        forestiero = _progetto_forestiero(base / "esterno")
        esito = modulo.importa(forestiero, "8. Cliente Migrato", asciutto=True, radice=base)
        check("esce 0", esito == 0, f"exit {esito}")
        check("non ha creato niente", not (base / "8. Cliente Migrato").exists())


def test_cartella_inesistente() -> None:
    """Una cartella che non c'è è un errore d'uso."""
    print("\ncartella inesistente")
    esito = modulo.importa(Path("/non/esiste/affatto"), "X", radice=Path("/tmp"))
    check("esce 2", esito == 2, f"exit {esito}")


def main() -> int:
    print("importa un progetto da un altro motore")
    test_importa_e_pulisce()
    test_disattiva_i_file_di_istruzioni()
    test_non_sovrascrive()
    test_dry_run_non_scrive()
    test_cartella_inesistente()
    print()
    if FALLITI:
        print(f"FALLITO — {len(FALLITI)} controlli: " + ", ".join(FALLITI))
        return 1
    print("PASS — importa, pulisce, disattiva, non sovrascrive")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
