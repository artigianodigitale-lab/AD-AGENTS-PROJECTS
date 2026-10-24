#!/usr/bin/env python3
"""Ponte verso il browser vero (Camoufox). Va eseguito con il python del suo ambiente.

Perche' esiste: alcuni siti restituiscono pagine vuote senza JavaScript, o bloccano
le richieste automatiche. Un browser vero li legge. Ma e' **pesante e lento**: per
questo non si chiama da solo — lo chiama `tools/ricerca.py`, e solo quando la via
leggera non basta.

Uso (dall'ambiente di camoufox):
    ~/.cache/mf-camoufox-env/bin/python tools/camoufox_ponte.py <url> [--timeout 45000]

Output: **una riga JSON su stdout, sempre.** Gli errori NON finiscono su stdout:
un messaggio di errore stampato li' romperebbe il JSON e il chiamante non saprebbe
distinguere un errore da una pagina legittima.
"""

from __future__ import annotations

import argparse
import json
import sys
import time


def errore(msg: str) -> None:
    print(json.dumps({"ok": False, "errore": msg}, ensure_ascii=False))
    sys.exit(0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--timeout", type=int, default=45000, help="timeout di navigazione (ms)")
    ap.add_argument("--attesa", type=int, default=2500, help="attesa dopo il load (ms)")
    ap.add_argument("--max-html", type=int, default=3_000_000, help="tetto all'HTML restituito")
    args = ap.parse_args()

    try:
        from camoufox.sync_api import Camoufox
    except Exception as e:  # pragma: no cover - dipende dall'ambiente
        errore(f"camoufox non importabile: {type(e).__name__}: {e}")

    inizio = time.time()
    try:
        with Camoufox(headless=True, geoip=False) as browser:
            page = browser.new_page()
            page.goto(args.url, wait_until="domcontentloaded", timeout=args.timeout)
            # Rete + rendering: senza questa attesa i siti che costruiscono il DOM via
            # JavaScript restituiscono pagine quasi vuote — ed e' esattamente il motivo
            # per cui serve un browser invece di un fetch.
            if args.attesa > 0:
                page.wait_for_timeout(args.attesa)
            html = page.content()
            if len(html) > args.max_html:
                html = html[: args.max_html]
            testo = page.inner_text("body") if page.query_selector("body") else ""
            print(
                json.dumps(
                    {
                        "ok": True,
                        "url": page.url,
                        "title": page.title(),
                        "html": html,
                        "testo": testo[:200_000],
                        "ms": int((time.time() - inizio) * 1000),
                    },
                    ensure_ascii=False,
                )
            )
    except Exception as e:
        errore(f"{type(e).__name__}: {str(e)[:300]}")


if __name__ == "__main__":
    main()
