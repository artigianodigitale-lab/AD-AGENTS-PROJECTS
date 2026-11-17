#!/usr/bin/env python3
"""La build incrementale del motore (M5, `DEC-0117`).

Perche' esiste. La «build» di AAP sono i controlli: sintassi, coerenza, suite veloce. Ogni
giro li riesegue tutti anche quando nulla e' cambiato, e il tempo speso e' **tempo che non
protegge niente**: una prova che non dipende dal file cambiato non sta verificando nulla di
nuovo.

Come funziona. Ogni fase dichiara i suoi **input** (file e cartelle). La build calcola
l'impronta SHA-256 degli input; se l'impronta e' la stessa di un'esecuzione **verde**
registrata, la fase si salta e lo dice. Se un solo input cambia, l'impronta cambia e la fase
torna a girare. `--forza` esegue tutto (il sospetto vince sempre). Un esito **rosso non si
cacha**: un guasto non e' uno stato da riusare.

La cache dello stato vive **fuori dal repository** (`~/.cache/ad-build`, o `AD_BUILD_DIR`).
Limite dichiarato: una modifica che non tocca gli input dichiarati di una fase non la
invalida — per questo `--forza` esiste, ed e' la prima cosa da provare quando qualcosa non
torna.

Uso:
    python3 tools/build.py                 # le fasi incrementali
    python3 tools/build.py --forza         # tutto, sempre
    python3 tools/build.py --fasi sintassi # solo alcune
    python3 tools/build.py --pulisca       # svuota la cache dello stato
    python3 tools/build.py --json

Esiti: 0 tutte le fasi verdi (eseguite o saltate), 1 una fase rossa, 2 uso sbagliato.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

RADICE = Path(__file__).resolve().parents[1]
STATO_PREDEFINITO = Path.home() / ".cache" / "ad-build" / "stato.json"


def cartella_stato() -> Path:
    indicata = os.environ.get("AD_BUILD_DIR")
    percorso = Path(indicata) / "stato.json" if indicata else STATO_PREDEFINITO
    risolto = percorso.resolve()
    if risolto == RADICE.resolve() or RADICE.resolve() in risolto.parents:
        raise ErroreBuild(f"la build non cacha nel repository: {risolto}",
                          "usa ~/.cache/ad-build (o AD_BUILD_DIR fuori dal repository)")
    return risolto


class ErroreBuild(Exception):
    def __init__(self, messaggio: str, rimedio: str) -> None:
        super().__init__(messaggio)
        self.messaggio = messaggio
        self.rimedio = rimedio


#: Le fasi, con i loro input dichiarati. L'ordine conta: la sintassi prima delle prove.
FASI: list[dict[str, Any]] = [
    {
        "nome": "sintassi",
        "descrizione": "compila i moduli Python (sintassi, non comportamento)",
        "comando": [sys.executable, "-m", "compileall", "-q", "tools", "tests"],
        "input": ["tools", "tests"],
    },
    {
        "nome": "coerenza",
        "descrizione": "documenti e sistema dicono la stessa cosa",
        "comando": [sys.executable, "tools/coherence.py"],
        "input": ["tools", "tests", "README.md", "SECURITY.md", "CRAWLING.md", "DECISIONI", "piani"],
    },
    {
        "nome": "prove",
        "descrizione": "la suite veloce della macchina",
        "comando": [sys.executable, "tests/ci.py"],
        "input": ["tools", "tests", "DECISIONI", "contratti", "approvazioni", "piani", "evidenze", "drift", "errori"],
    },
]


def _file_di(percorso: Path) -> list[Path]:
    if percorso.is_file():
        return [percorso]
    if percorso.is_dir():
        return sorted(p for p in percorso.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
    return []


def impronta_inputs(inputs: list[str]) -> tuple[str, int]:
    """SHA-256 del contenuto degli input dichiarati (percorsi relativi inclusi)."""
    digest = hashlib.sha256()
    numero = 0
    for voce in inputs:
        for file in _file_di(RADICE / voce):
            try:
                dati = file.read_bytes()
            except OSError:
                continue
            try:
                nome = str(file.relative_to(RADICE))
            except ValueError:
                nome = str(file)  # input fuori dal repository (fasi di prova)
            digest.update(nome.encode("utf-8"))
            digest.update(dati)
            numero += 1
    return digest.hexdigest(), numero


def impronta_fase(fase: dict[str, Any]) -> tuple[str, int]:
    """L'impronta dipende dagli input E dal comando: se il comando cambia, la fase e' nuova."""
    impronta_input, file_letti = impronta_inputs(fase["input"])
    materiale = impronta_input + "|" + json.dumps(fase["comando"], ensure_ascii=False)
    return hashlib.sha256(materiale.encode("utf-8")).hexdigest(), file_letti


def _stato_letto(percorso: Path) -> dict[str, Any]:
    if not percorso.is_file():
        return {"schema": 1, "fasi": {}}
    try:
        dati = json.loads(percorso.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema": 1, "fasi": {}}
    return dati if isinstance(dati.get("fasi"), dict) else {"schema": 1, "fasi": {}}


def _stato_scritto(percorso: Path, dati: dict[str, Any]) -> None:
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_text(json.dumps(dati, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _esegui_fase(fase: dict[str, Any], timeout: int) -> tuple[bool, str, float]:
    inizio = time.monotonic()
    try:
        esito = subprocess.run(
            fase["comando"], cwd=str(RADICE), capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return False, f"timeout {timeout}s", time.monotonic() - inizio
    uscita = (esito.stdout or "") + (esito.stderr or "")
    return esito.returncode == 0, uscita.strip()[-800:], time.monotonic() - inizio


def esegui(
    *,
    forza: bool = False,
    pulisca: bool = False,
    fasi: list[dict[str, Any]] | None = None,
    timeout: int = 600,
) -> dict[str, Any]:
    percorso_stato = cartella_stato()
    if pulisca:
        percorso_stato.unlink(missing_ok=True)
        return {"pulita": True, "stato": str(percorso_stato), "fasi": []}

    fasi = list(fasi or FASI)
    stato = _stato_letto(percorso_stato)
    risultati: list[dict[str, Any]] = []
    risparmio = 0.0
    tutte_verdi = True

    for fase in fasi:
        nome = fase["nome"]
        impronta, file_letti = impronta_fase(fase)
        precedente = stato["fasi"].get(nome, {})
        saltata = (
            not forza
            and precedente.get("impronta") == impronta
            and precedente.get("esito") == "verde"
        )
        if saltata:
            durata = float(precedente.get("durata", 0.0))
            risparmio += durata
            risultati.append({
                "nome": nome, "stato": "saltata", "durata_risparmiata": round(durata, 2),
                "impronta": impronta[:12], "input": file_letti,
            })
            continue

        verde, uscita, durata = _esegui_fase(fase, timeout)
        tutte_verdi = tutte_verdi and verde
        risultati.append({
            "nome": nome, "stato": "eseguita", "esito": "verde" if verde else "rosso",
            "durata": round(durata, 2), "impronta": impronta[:12], "input": file_letti,
            "uscita": "" if verde else uscita,
        })
        if verde:
            stato["fasi"][nome] = {
                "impronta": impronta, "esito": "verde", "durata": round(durata, 3),
                "quando": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            }
        else:
            # un rosso non si cacha: il prossimo giro riprova.
            stato["fasi"].pop(nome, None)
        _stato_scritto(percorso_stato, stato)
        if not verde:
            break

    durata_totale = sum(r.get("durata", 0.0) for r in risultati)
    return {
        "fasi": risultati,
        "verde": tutte_verdi,
        "durata_eseguita_secondi": round(durata_totale, 2),
        "risparmio_stimato_secondi": round(risparmio, 2),
        "stato": str(percorso_stato),
        "forza": forza,
    }


def main(argv: list[str] | None = None) -> int:
    analizzatore = argparse.ArgumentParser(description="La build incrementale del motore")
    analizzatore.add_argument("--forza", action="store_true", help="esegue tutte le fasi, senza cache")
    analizzatore.add_argument("--pulisca", action="store_true", help="svuota la cache dello stato")
    analizzatore.add_argument("--fasi", default="", help="nomi separati da virgola (default: tutte)")
    analizzatore.add_argument("--timeout", type=int, default=600)
    analizzatore.add_argument("--json", action="store_true")
    args = analizzatore.parse_args(argv)

    scelte = [nome.strip() for nome in args.fasi.split(",") if nome.strip()]
    fasi = [fase for fase in FASI if not scelte or fase["nome"] in scelte]
    if scelte and len(fasi) != len(scelte):
        print(f"  fasi sconosciute: {sorted(set(scelte) - {f['nome'] for f in FASI})}", file=sys.stderr)
        return 2

    try:
        esito = esegui(forza=args.forza, pulisca=args.pulisca, fasi=fasi, timeout=args.timeout)
    except ErroreBuild as errore:
        print(f"  {errore.messaggio}\n  rimedio: {errore.rimedio}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(esito, indent=2, ensure_ascii=False))
    elif esito.get("pulita"):
        print(f"  cache della build svuotata: {esito['stato']}")
    else:
        for voce in esito["fasi"]:
            if voce["stato"] == "saltata":
                print(f"  cache  {voce['nome']:10} saltata (input invariati, risparmio {voce['durata_risparmiata']}s)")
            else:
                print(f"  {'ok  ' if voce['esito'] == 'verde' else 'NO  '} {voce['nome']:10} "
                      f"eseguita in {voce['durata']}s")
                if voce["esito"] == "rosso":
                    print(voce["uscita"])
        print(f"  durata eseguita: {esito['durata_eseguita_secondi']}s · "
              f"risparmio: {esito['risparmio_stimato_secondi']}s · stato: {esito['stato']}")
    return 0 if esito.get("verde", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
