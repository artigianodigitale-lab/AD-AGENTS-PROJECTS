#!/usr/bin/env python3
"""La cache verificabile del motore (M4, `DEC-0116`).

Perche' esiste. Una cache che non dice **cosa** ha salvato, **quando** e **da dove** non e'
una cache: e' un file vecchio che sembra vero. Questa cache salva, per ogni voce:

  - l'impronta SHA-256 del corpo (se il corpo cambia, la voce non e' piu' quella);
  - la provenienza (URL, via, data di presa, policy con cui e' stata presa);
  - la scadenza (TTL): dopo, la voce non si usa piu' — non si «rinnova» da sola.

E vive **fuori dal repository**: la cache non e' un prodotto del motore, e' un risparmio
locale. `pulisci` tocca solo voci che ha creato lei.

Uso:
    python3 tools/cache.py salva --url <url> --testo <file> [--via http] [--ttl 604800]
    python3 tools/cache.py leggi --url <url> [--json]
    python3 tools/cache.py stato [--json]
    python3 tools/cache.py verifica [--json]
    python3 tools/cache.py pulisci

Esiti: 0 ok, 1 non trovata/scaduta (per `leggi`), 2 uso sbagliato.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]
VERSIONE_POLICY = "1"
TTL_PREDEFINITO = 7 * 24 * 3600
MARCATORE = "ad-cache-meta"

sys.path.insert(0, str(RADICE / "tools"))


class ErroreCache(Exception):
    def __init__(self, messaggio: str, rimedio: str) -> None:
        super().__init__(messaggio)
        self.messaggio = messaggio
        self.rimedio = rimedio


def canonico(url: str) -> str:
    """La chiave si calcola su un URL stabile: frammento, porta, caso, ordine dei parametri."""
    pezzi = urllib.parse.urlsplit(url.strip())
    host = (pezzi.hostname or "").lower()
    porta = pezzi.port
    rete = host if porta in (None, 80, 443) else f"{host}:{porta}"
    percorso = re.sub(r"/{2,}", "/", pezzi.path or "/")
    if percorso != "/" and percorso.endswith("/"):
        percorso = percorso.rstrip("/")
    parametri = sorted(urllib.parse.parse_qsl(pezzi.query, keep_blank_values=True))
    return urllib.parse.urlunsplit((pezzi.scheme.lower(), rete, percorso, urllib.parse.urlencode(parametri), ""))


def cartella_cache() -> Path:
    """La cache vive fuori dal repository. `AD_CACHE_DIR` permette di spostarla."""
    indicata = os.environ.get("AD_CACHE_DIR")
    percorso = Path(indicata) if indicata else Path.home() / ".cache" / "ad-cache"
    risolto = percorso.resolve()
    if risolto == RADICE.resolve() or RADICE.resolve() in risolto.parents:
        raise ErroreCache(
            f"la cache non sta nel repository: {risolto}",
            "usa ~/.cache/ad-cache (o AD_CACHE_DIR fuori dal repository)",
        )
    return risolto


def chiave(url: str, policy: str = VERSIONE_POLICY) -> str:
    return hashlib.sha256(f"{canonico(url)}|{policy}".encode("utf-8")).hexdigest()


def _meta_path(chiave_voce: str) -> Path:
    return cartella_cache() / f"{chiave_voce}.json"


def _corpo_path(chiave_voce: str) -> Path:
    return cartella_cache() / f"{chiave_voce}.bin"


def salva(
    url: str,
    corpo: bytes,
    *,
    via: str = "http",
    policy: str = VERSIONE_POLICY,
    ttl: int = TTL_PREDEFINITO,
    adesso: float | None = None,
) -> dict:
    cartella = cartella_cache()
    cartella.mkdir(parents=True, exist_ok=True)
    chiave_voce = chiave(url, policy)
    ora = time.time() if adesso is None else adesso
    meta = {
        "marcatore": MARCATORE,
        "url": canonico(url),
        "sha256": hashlib.sha256(corpo).hexdigest(),
        "via": via,
        "policy": policy,
        "presa_il": ora,
        "scade_il": ora + ttl,
        "byte": len(corpo),
        "hit": 0,
    }
    _corpo_path(chiave_voce).write_bytes(corpo)
    _meta_path(chiave_voce).write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"chiave": chiave_voce, **meta}


def leggi(url: str, *, policy: str = VERSIONE_POLICY, adesso: float | None = None) -> dict | None:
    """Legge una voce se esiste, non e' scaduta e il corpo corrisponde all'impronta."""
    chiave_voce = chiave(url, policy)
    meta_path = _meta_path(chiave_voce)
    corpo_path = _corpo_path(chiave_voce)
    if not meta_path.is_file() or not corpo_path.is_file():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if meta.get("marcatore") != MARCATORE or meta.get("policy") != policy:
        return None
    ora = time.time() if adesso is None else adesso
    if ora > float(meta.get("scade_il", 0)):
        return None
    corpo = corpo_path.read_bytes()
    if hashlib.sha256(corpo).hexdigest() != meta.get("sha256"):
        return None  # manomessa: si tratta come assente, non si «ripara» da sola
    meta["hit"] = int(meta.get("hit", 0)) + 1
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"chiave": chiave_voce, "corpo": corpo, "meta": meta}


def _meta_del_motore(meta_path: Path) -> dict | None:
    """Il meta e' una voce NOSTRA? Se non ha il marcatore, e' un file estraneo: non si tocca."""
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(meta, dict) or meta.get("marcatore") != MARCATORE:
        return None
    return meta


def stato() -> dict:
    cartella = cartella_cache()
    voci = 0
    byte = 0
    scadute = 0
    hit = 0
    ora = time.time()
    if cartella.is_dir():
        for meta_path in cartella.glob("*.json"):
            meta = _meta_del_motore(meta_path)
            if meta is None:
                continue  # file estraneo: non e' una voce, non si conta
            voci += 1
            byte += int(meta.get("byte", 0))
            hit += int(meta.get("hit", 0))
            if ora > float(meta.get("scade_il", 0)):
                scadute += 1
    return {"cartella": str(cartella), "voci": voci, "byte": byte, "scadute": scadute, "hit_totali": hit}


def verifica() -> dict:
    cartella = cartella_cache()
    ok = 0
    rotte: list[str] = []
    if cartella.is_dir():
        for meta_path in cartella.glob("*.json"):
            meta = _meta_del_motore(meta_path)
            if meta is None:
                continue  # estraneo: non e' una voce della cache
            try:
                corpo = _corpo_path(meta_path.stem).read_bytes()
            except OSError:
                rotte.append(meta_path.stem)
                continue
            if hashlib.sha256(corpo).hexdigest() == meta.get("sha256"):
                ok += 1
            else:
                rotte.append(meta_path.stem)
    return {"verificate": ok, "rotte": rotte, "ok": not rotte}


def pulisci() -> dict:
    """Cancella SOLO le voci create da questa cache: un file estraneo non si tocca.

    Il nome della funzione non e' un permesso: una cartella puo' contenere altro, e
    `rmtree`/glob su tutto e' il modo in cui una cache cancella il lavoro di qualcun
    altro (rilievo della revisione di ENG-048).
    """
    cartella = cartella_cache()
    rimosse = 0
    if cartella.is_dir():
        for meta_path in list(cartella.glob("*.json")):
            meta = _meta_del_motore(meta_path)
            if meta is None:
                continue
            corpo = _corpo_path(meta_path.stem)
            meta_path.unlink(missing_ok=True)
            corpo.unlink(missing_ok=True)
            rimosse += 1
    return {"rimosse": rimosse, "cartella": str(cartella)}


def main(argv: list[str] | None = None) -> int:
    analizzatore = argparse.ArgumentParser(description="La cache verificabile del motore")
    sotto = analizzatore.add_subparsers(dest="azione", required=True)
    s = sotto.add_parser("salva")
    s.add_argument("--url", required=True)
    s.add_argument("--testo", required=True, help="file da cui leggere il corpo")
    s.add_argument("--via", default="http")
    s.add_argument("--ttl", type=int, default=TTL_PREDEFINITO)
    s.add_argument("--json", action="store_true")
    l = sotto.add_parser("leggi")
    l.add_argument("--url", required=True)
    l.add_argument("--json", action="store_true")
    st = sotto.add_parser("stato")
    st.add_argument("--json", action="store_true")
    v = sotto.add_parser("verifica")
    v.add_argument("--json", action="store_true")
    sotto.add_parser("pulisci")

    args = analizzatore.parse_args(argv)
    try:
        if args.azione == "salva":
            corpo = Path(args.testo).read_bytes()
            meta = salva(args.url, corpo, via=args.via, ttl=args.ttl)
            print(json.dumps(meta, indent=2, ensure_ascii=False) if args.json else f"  salvata: {meta['chiave']} ({meta['byte']} byte)")
            return 0
        if args.azione == "leggi":
            voce = leggi(args.url)
            if voce is None:
                print("  non in cache (o scaduta, o manomessa)")
                return 1
            if args.json:
                print(json.dumps({"chiave": voce["chiave"], "meta": voce["meta"]}, indent=2, ensure_ascii=False))
            else:
                print(f"  hit: {voce['chiave']} ({voce['meta']['byte']} byte, presa il {voce['meta']['presa_il']})")
            return 0
        if args.azione == "stato":
            dati = stato()
            print(json.dumps(dati, indent=2, ensure_ascii=False) if args.json else
                  f"  {dati['voci']} voci, {dati['byte']} byte, {dati['scadute']} scadute, {dati['hit_totali']} hit")
            return 0
        if args.azione == "verifica":
            dati = verifica()
            print(json.dumps(dati, indent=2, ensure_ascii=False) if args.json else
                  f"  {dati['verificate']} verificate, {len(dati['rotte'])} rotte")
            return 0 if dati["ok"] else 1
        if args.azione == "pulisci":
            dati = pulisci()
            print(f"  rimosse {dati['rimosse']} voci da {dati['cartella']}")
            return 0
    except ErroreCache as errore:
        print(f"  {errore.messaggio}\n  rimedio: {errore.rimedio}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
