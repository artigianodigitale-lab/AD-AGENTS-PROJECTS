#!/usr/bin/env python3
"""La verifica automatica della macchina (ENG-006): si prova anche il guasto.

    python3 tests/test_ci.py

Perche' esiste. Una verifica che "passa" non e' una verifica: lo e' solo se
fallisce quando deve. Qui si inietta il guasto nel runner e si controlla che (a)
venga nominato, (b) l'eccezione dichiarata sia stretta — solo la divergenza nota e
nominata, non qualunque guasto — e (c) il gancio git rifiuti davvero un commit con
la verifica rossa.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import ci  # noqa: E402

PASSED = 0


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    """Assert one expectation."""
    global PASSED
    if not condizione:
        raise AssertionError(f"{etichetta}: {dettaglio or 'condizione falsa'}")
    PASSED += 1


def _runner_ok(comando: list[str]) -> tuple[int, str]:
    return 0, ""


def _runner_rosso(comando: list[str]) -> tuple[int, str]:
    return 1, "ERRORE  qualcosa e' rotto"


def test_macchina_verde() -> None:
    """Sulla macchina com'e' adesso, il profilo veloce non ha fallimenti."""
    esiti = ci.verifica("fast")
    check("profilo veloce senza fallimenti", ci.fallimenti(esiti) == [], str([e.controllo.nome for e in ci.fallimenti(esiti)]))
    check("almeno 8 controlli", len(esiti) >= 8, str(len(esiti)))
    check("i contract attivi sono controllati", any("contract " in e.controllo.nome for e in esiti), str([e.controllo.nome for e in esiti]))


def test_guasto_viene_nominato() -> None:
    """Un guasto iniettato diventa un fallimento, con il nome del controllo."""
    rotti = {"coerenza"}

    def runner(comando: list[str]) -> tuple[int, str]:
        return 1, "ERRORE  rotto apposta"

    esiti = ci.verifica("fast", runner=runner)
    falliti = ci.fallimenti(esiti)
    check("il guasto e' un fallimento", len(falliti) == len(esiti), str(len(falliti)))
    nomi = {e.controllo.nome for e in falliti}
    check("il nome del controllo c'e'", "coerenza" in nomi, str(nomi))
    check("il guasto iniettato e' quello", rotti <= nomi, str(nomi))


def test_eccezioni_sono_strette() -> None:
    """L'eccezione dichiarata copre SOLO il guasto noto e nominato."""
    storico = ci.Controllo("suite-storica", ["x"], tipo="eccezione")
    noto = ci._classifica(storico, 1, "FileNotFoundError: .../13. Progetto Eta")
    check("DRIFT-023 e' riconosciuta", noto.stato == "noto", noto.stato)
    altro = ci._classifica(storico, 1, "AssertionError: qualcosa d'altro")
    check("un altro guasto storico fallisce", altro.stato == "fallito", altro.stato)

    # Dopo DEC-0061 lo snapshot e' riallineato: nessun documento diverge, e il
    # controllo e' OBBLIGATORIO (l'eccezione DRIFT-028 e' stata rimossa).
    reali = ci.documenti_divergenti_dal_snapshot()
    check("nessun documento normativo diverge", reali == set(), str(reali))
    memoria = next(voce for voce in ci.controlli_full() if voce.nome == "test-memoria")
    check("il controllo delle impronte e' obbligatorio", memoria.tipo == "obbligatorio", memoria.tipo)
    check(
        "un guasto delle impronte e' un fallimento",
        ci._classifica(memoria, 1, "AGENTS.md: modificato rispetto allo snapshot approvato").stato == "fallito",
        "promosso",
    )



def test_informativo_non_blocca() -> None:
    """Il controllo dell'albero non blocca un commit: il testimone e' una fotografia."""
    albero = ci.Controllo("albero", ["x"], tipo="informativo")
    esito = ci._classifica(albero, 3, "contaminazioni")
    check("informativo non e' fallimento", esito.stato == "informativo", esito.stato)
    check("informativo non blocca", ci.fallimenti([esito]) == [], "ha bloccato")


def test_cli_e_json() -> None:
    """--json produce un esito strutturato; le opzioni sbagliate escono 2."""
    esito = subprocess.run(
        [sys.executable, str(ROOT / "tests" / "ci.py"), "--json"],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    check("--json esce 0", esito.returncode == 0, esito.stderr[:200])
    dati = json.loads(esito.stdout)
    check("json ha il profilo", dati.get("profilo") == "fast", str(dati)[:200])
    check("json ha l'esito complessivo", isinstance(dati.get("verde"), bool), str(dati)[:200])
    check("json elenca i controlli", len(dati.get("controlli") or []) >= 8, str(len(dati.get("controlli") or [])))
    for voce in dati["controlli"]:
        check(
            f"{voce['nome']}: campi",
            {"nome", "comando", "stato", "codice", "secondi"} <= set(voce),
            str(voce),
        )
        check(f"{voce['nome']}: comando e' una lista non vuota", isinstance(voce["comando"], list) and bool(voce["comando"]), str(voce["comando"]))

    doppio = subprocess.run(
        [sys.executable, str(ROOT / "tests" / "ci.py"), "--fast", "--full"],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    check("--fast e --full insieme: exit 2", doppio.returncode == 2, str(doppio.returncode))
    ignoto = subprocess.run(
        [sys.executable, str(ROOT / "tests" / "ci.py"), "--boh"],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    check("opzione sconosciuta: exit 2", ignoto.returncode == 2, str(ignoto.returncode))


def test_messaggio_rosso_dice_come_tornare_indietro() -> None:
    """Quando e' rosso, la verifica dice come ripristinare (index compreso)."""
    import io
    from contextlib import redirect_stdout

    esiti = ci.verifica("fast", runner=lambda comando: (1, "ERRORE  rotto"))
    catturato = io.StringIO()
    with redirect_stdout(catturato):
        ci._stampa(esiti, "fast")
    testo = catturato.getvalue()
    check("il messaggio nomina git restore", "git restore --source=HEAD" in testo, testo[-300:])
    check("avverte che checkout non basta", "checkout" in testo, testo[-300:])


def test_il_gancio_rifiuta_il_commit_rosso() -> None:
    """Meccanismo provato in un repository scratch: con la verifica rossa il commit non parte."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = Path(tmp)
        (radice / "tests").mkdir()
        (radice / "tests" / "ci.py").write_text("#!/usr/bin/env python3\nraise SystemExit(1)\n", encoding="utf-8")
        (radice / ".githooks").mkdir()
        gancio = radice / ".githooks" / "pre-commit"
        gancio.write_text(
            "#!/bin/sh\nexec python3 \"$(git rev-parse --show-toplevel)/tests/ci.py\" --fast\n",
            encoding="utf-8",
        )
        gancio.chmod(0o755)
        (radice / "vuoto.txt").write_text("x\n", encoding="utf-8")
        for comando in (
            ["git", "init", "-q", "-b", "main"],
            ["git", "config", "user.email", "ci@test.local"],
            ["git", "config", "user.name", "CI Test"],
            ["git", "config", "core.hooksPath", ".githooks"],
            ["git", "add", "-A"],
        ):
            subprocess.run(comando, cwd=str(radice), capture_output=True, text=True, check=True)
        commit = subprocess.run(
            ["git", "commit", "-m", "prova"],
            cwd=str(radice), capture_output=True, text=True,
        )
        check("commit con verifica rossa RIFIUTATO", commit.returncode != 0, commit.stdout[:200])
        log = subprocess.run(["git", "log", "--oneline"], cwd=str(radice), capture_output=True, text=True)
        check("nessun commit creato", log.stdout.strip() == "", log.stdout[:200])


def test_il_gancio_rifiuta_la_scrittura_fuori_scope() -> None:
    """ERR-0062: un file di governance staged senza contract attivo non entra nel commit."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = Path(tmp)
        (radice / "tests").mkdir()
        (radice / "tests" / "ci.py").write_text("#!/usr/bin/env python3\nraise SystemExit(0)\n", encoding="utf-8")
        (radice / "tools").mkdir()
        (radice / "tools" / "contract_scope.py").write_text(
            "import sys\nsys.exit(1)\n", encoding="utf-8"
        )
        (radice / "tools" / "artefatto.py").write_text("x = 1\n", encoding="utf-8")
        (radice / ".githooks").mkdir()
        reale = (ROOT / ".githooks" / "pre-commit").read_text(encoding="utf-8")
        gancio = radice / ".githooks" / "pre-commit"
        gancio.write_text(reale, encoding="utf-8")
        gancio.chmod(0o755)
        for comando in (
            ["git", "init", "-q", "-b", "main"],
            ["git", "config", "user.email", "ci@test.local"],
            ["git", "config", "user.name", "CI Test"],
            ["git", "config", "core.hooksPath", ".githooks"],
            ["git", "add", "-A"],
        ):
            subprocess.run(comando, cwd=str(radice), capture_output=True, text=True, check=True)
        commit = subprocess.run(["git", "commit", "-m", "prova"], cwd=str(radice), capture_output=True, text=True)
        check("governance fuori scope: commit RIFIUTATO", commit.returncode != 0, commit.stdout[:300])
        check("il rifiuto nomina il file", "artefatto.py" in (commit.stdout + commit.stderr), commit.stdout[:200])

        # con il contract che lo copre, il commit passa
        (radice / "tools" / "contract_scope.py").write_text(
            "import sys\nsys.exit(0)\n", encoding="utf-8"
        )
        subprocess.run(["git", "add", "-A"], cwd=str(radice), capture_output=True, text=True, check=True)
        commit = subprocess.run(["git", "commit", "-m", "prova ok"], cwd=str(radice), capture_output=True, text=True)
        check("con il contract: commit passa", commit.returncode == 0, (commit.stdout + commit.stderr)[:300])



def test_il_gancio_controlla_le_cartelle_progetto() -> None:
    """ERR-0062/ENG-013: un file in una cartella "N. Nome" e' governance, con lo spazio."""
    with tempfile.TemporaryDirectory() as tmp:
        radice = Path(tmp)
        (radice / "tests").mkdir()
        (radice / "tests" / "ci.py").write_text("#!/usr/bin/env python3\nraise SystemExit(0)\n", encoding="utf-8")
        (radice / "tools").mkdir()
        (radice / "tools" / "contract_scope.py").write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
        (radice / ".githooks").mkdir()
        (radice / ".githooks" / "pre-commit").write_text(
            (ROOT / ".githooks" / "pre-commit").read_text(encoding="utf-8"), encoding="utf-8")
        (radice / ".githooks" / "pre-commit").chmod(0o755)
        (radice / "7. Progetto").mkdir()
        (radice / "7. Progetto" / "nota.md").write_text("x\n", encoding="utf-8")
        for comando in (
            ["git", "init", "-q", "-b", "main"],
            ["git", "config", "user.email", "ci@test.local"],
            ["git", "config", "user.name", "CI Test"],
            ["git", "config", "core.hooksPath", ".githooks"],
            ["git", "add", "-A"],
        ):
            subprocess.run(comando, cwd=str(radice), capture_output=True, text=True, check=True)
        commit = subprocess.run(["git", "commit", "-m", "prova"], cwd=str(radice), capture_output=True, text=True)
        check("cartella progetto con spazio: RIFIUTATA", commit.returncode != 0, commit.stdout[:300])
        check("il rifiuto nomina il file con lo spazio", "7. Progetto" in (commit.stdout + commit.stderr), commit.stdout[:300])



def main() -> int:
    """Run the suite."""
    print("verifica automatica: verde, guasto nominato, eccezioni strette, gancio")
    test_macchina_verde()
    test_guasto_viene_nominato()
    test_eccezioni_sono_strette()
    test_informativo_non_blocca()
    test_cli_e_json()
    test_messaggio_rosso_dice_come_tornare_indietro()
    test_il_gancio_rifiuta_il_commit_rosso()
    test_il_gancio_rifiuta_la_scrittura_fuori_scope()
    test_il_gancio_controlla_le_cartelle_progetto()
    print(f"PASS — {PASSED} controlli sulla verifica automatica")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
