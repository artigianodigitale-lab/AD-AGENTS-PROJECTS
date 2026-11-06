#!/usr/bin/env python3
"""La cache dei registri: leggere 439 file YAML a ogni comando e' tempo buttato.

Il problema, misurato il 2026-11-06 sulla macchina vera:

    iter_registro (trovare i file)    3 ms    439 file
    yaml.safe_load di ognuno        758 ms    <- il 68% del tempo
    load_write_scopes             1.115 ms   27 contract utili su 439
    load_approvals                  274 ms

Ogni strumento che tocca il registro paga quel prezzo, e ce ne sono **quattordici**
che lo fanno, in otto strumenti diversi. `ci.py` li esegue tutti in fila.

Perche' una cache e non un'ottimizzazione del parser: il 412 file su 439 vengono
letti e **scartati** (stato non attivo, `write_scope` assente, scaduti). Ma quali
siano i 27 utili lo dice solo il contenuto, e il contenuto va letto. Non si puo'
sapere prima di leggere; si puo' pero' **non rileggere la prossima volta**.

La firma e' il CONTENUTO, non l'mtime. `ad_scope.py` lo dice gia' in un commento
(«L'mtime non e' un ripiego: e' una falsa accusa»): una copia azzera gli orari, e un
controllo che si basa sull'mtime accusa una macchina di essere stata manomessa quando
e' solo stata clonata. L'hash costa **4 ms** per tutti e 439 i file: 280 volte meno
del parsing, e non mente.

Cosa NON fa: non tiene in memoria lo stato fra un processo e l'altro in modo invisibile.
La cache vive su disco (`.cache/registri.json`), e se e' vecchia, corrotta o di
un'altra macchina, si **rifa'** invece di sbagliare. Una cache che sbaglia e' peggio
di nessuna cache: il cancello autorizzerebbe con dati vecchi.

Uso (come modulo):
    from cache_registri import con_cache
    scopes = con_cache("scopes", lambda: ..., lambda: ad_scope.iter_registro(...))

Uso (da riga di comando):
    python3 tools/cache_registri.py stato     # cosa c'e' in cache, e se e' valida
    python3 tools/cache_registri.py pulisci   # toglie la cache
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable

RADICE = Path(__file__).resolve().parents[1]
#: Il file della cache: dentro `.cache/`, che `.gitignore` esclude. Non e' un registro:
#: e' un derivato, e si puo' cancellare senza perdere niente.
CARTELLA_CACHE = ".cache"
NOME_FILE = "registri.json"
#: Oltre questa eta' la cache si rifa' comunque. Non e' sfiducia nel contenuto (la firma
#: lo copre): e' che un file puo' sparire senza che la firma cambi, se nessuno lo elenca
#: piu'. Mezz'ora e' molto piu' di quanto serva a un `ci.py`.
ETA_MASSIMA = 30 * 60


def percorso_cache(root: Path | None = None) -> Path:
    base = root if root is not None else RADICE
    return base / CARTELLA_CACHE / NOME_FILE


def _firma(elenco_file: list[Path]) -> str:
    """L'impronta del contenuto di quei file, in ordine stabile.

    Il percorso **e** il contenuto: se un contract viene rinominato, la firma cambia
    anche se i byte sono gli stessi, e la cache si rifa'. Costa 4 ms su 439 file.
    """
    impronta = hashlib.sha256()
    for percorso in elenco_file:
        try:
            dati = percorso.read_bytes()
        except OSError:
            dati = b"\0sparito\0"  # cambia la firma: la cache si rifa'
        impronta.update(str(percorso).encode("utf-8"))
        impronta.update(b"\0")
        impronta.update(hashlib.sha256(dati).digest())
    return impronta.hexdigest()


def _leggi(root: Path) -> dict:
    percorso = percorso_cache(root)
    try:
        dati = json.loads(percorso.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        return {}
    return dati if isinstance(dati, dict) else {}


def _scrivi(root: Path, dati: dict) -> None:
    """Scrive la cache in modo atomico: un mezzo file sarebbe una cache corrotta."""
    percorso = percorso_cache(root)
    try:
        percorso.parent.mkdir(parents=True, exist_ok=True)
        descrittore, temporaneo = tempfile.mkstemp(
            dir=str(percorso.parent), prefix=".registri.", suffix=".tmp"
        )
        with os.fdopen(descrittore, "w", encoding="utf-8", newline="\n") as uscita:
            json.dump(dati, uscita, ensure_ascii=False, sort_keys=True)
            uscita.flush()
            os.fsync(uscita.fileno())
        os.replace(temporaneo, percorso)
    except (OSError, ValueError, TypeError):
        # La cache e' un'ottimizzazione: se non si scrive, si continua senza. Non deve
        # MAI far fallire il lavoro — sarebbe un'ottimizzazione che rompe.
        pass


def con_cache(
    chiave: str,
    calcola: Callable[[], object],
    elenco_file: Callable[[], list[Path]],
    root: Path | None = None,
) -> object:
    """Il risultato di ``calcola()``, riusando la cache se i file non sono cambiati.

    Le tre cose che devono valere perche' la cache sia corretta:

      1. la firma copre il **contenuto** di tutti i file che contano, non l'mtime;
      2. una cache vecchia, corrotta o di un'altra macchina si **rifa'**, non si usa;
      3. se la scrittura della cache fallisce, il lavoro continua — la cache e' un
         guadagno, non un requisito.

    Il valore deve essere serializzabile in JSON: chi chiama converte i dataclass in
    dizionari e li riconverte. Non si mettono oggetti vivi in una cache su disco.
    """
    base = root if root is not None else RADICE
    try:
        file_ora = sorted(elenco_file())
    except OSError:
        return calcola()
    firma = _firma(file_ora)

    cache = _leggi(base)
    voce = cache.get(chiave) if isinstance(cache, dict) else None
    adesso = time.time()
    if isinstance(voce, dict) and voce.get("firma") == firma:
        quando = voce.get("quando")
        if isinstance(quando, (int, float)) and (adesso - quando) < ETA_MASSIMA:
            return voce.get("valore")

    valore = calcola()
    cache[chiave] = {"firma": firma, "quando": adesso, "valore": valore}
    _scrivi(base, cache)
    return valore


def svuota(root: Path | None = None) -> int:
    """Toglie la cache. Restituisce quanti byte ha liberato."""
    percorso = percorso_cache(root)
    try:
        byte = percorso.stat().st_size
        percorso.unlink()
        return byte
    except OSError:
        return 0


def stato(root: Path | None = None) -> dict:
    """Cosa c'e' in cache: chiavi, firme, eta'."""
    base = root if root is not None else RADICE
    cache = _leggi(base)
    percorso = percorso_cache(base)
    adesso = time.time()
    voci = {}
    for chiave, voce in (cache.items() if isinstance(cache, dict) else []):
        if not isinstance(voce, dict):
            continue
        quando = voce.get("quando")
        voci[chiave] = {
            "firma": str(voce.get("firma", ""))[:16],
            "eta_secondi": int(adesso - quando) if isinstance(quando, (int, float)) else None,
        }
    return {
        "file": str(percorso),
        "esiste": percorso.is_file(),
        "byte": percorso.stat().st_size if percorso.is_file() else 0,
        "voci": voci,
    }


def main(argv: list[str] | None = None) -> int:
    argomenti = argv if argv is not None else sys.argv[1:]
    comando = argomenti[0] if argomenti else "stato"
    if comando == "pulisci":
        byte = svuota()
        print(f"  cache svuotata: {byte} byte liberati")
        return 0
    if comando != "stato":
        print("uso: python3 tools/cache_registri.py [stato|pulisci]", file=sys.stderr)
        return 2
    dati = stato()
    if not dati["esiste"]:
        print(f"  cache assente: {dati['file']}")
        print("  (si crea al primo strumento che legge il registro)")
        return 0
    print(f"  cache: {dati['file']} ({dati['byte']} byte)")
    if not dati["voci"]:
        print("  nessuna voce valida")
        return 0
    for chiave, voce in sorted(dati["voci"].items()):
        eta = voce["eta_secondi"]
        quando = f"{eta}s fa" if eta is not None else "senza eta'"
        print(f"    {chiave}: firma {voce['firma']}… · {quando}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
