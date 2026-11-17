#!/usr/bin/env python3
"""Il crawler legge dentro le regole, e lascia la traccia (M3, `DEC-0113`).

Le prove girano su un **sito finto locale** servito in-process: nessun traffico verso
siti di terzi, nessuna dipendenza dalla rete, risultati riproducibili.

Cosa si prova:
  1. guardia SSRF: loopback e metadata rifiutati; `--consenti-loopback` solo per le prove;
     schemi diversi da http/https rifiutati;
  2. URL canonico: frammento, porta, caso, ordine dei parametri;
  3. robots.txt rispettato: una pagina vietata non viene **mai** chiesta al server;
  4. dedup e scala: 1.000 pagine in una passata, manifesto completo, 0 URL duplicati,
     ogni snapshot con l'impronta giusta;
  5. 429 con `Retry-After`: ritentato e poi riuscito;
  6. limiti: `--max-pagine`, `--max-profondita`;
  7. browser headless: una pagina resa da JavaScript contiene il testo reso
     (`chromium --dump-dom`), e se il browser manca il caso e' `SKIP`, non un finto verde;
  8. `pulisci`: lo scarico si cancella (policy di conservazione minima).

Si esegue dalla radice:
    python3 tools/tests/test_crawler.py
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE / "tools"))

import cache  # noqa: E402
import crawler  # noqa: E402

FALLITI: list[str] = []
PASSATI = 0
PAGINE = 1000


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    global PASSATI
    if condizione:
        print(f"  ok   {etichetta}")
        PASSATI += 1
    else:
        print(f"  NO   {etichetta}  {dettaglio}")
        FALLITI.append(etichetta)


class SitoFinto(BaseHTTPRequestHandler):
    protette_chieste = 0
    retry_429 = 0
    retry_negativo = 0
    sempre_429 = 0
    cache_chieste = 0

    def log_message(self, *_args) -> None:  # silenzio: e' un sito di prova
        return

    def _invia(self, corpo: str, status: int = 200, tipo: str = "text/html", extra: dict | None = None) -> None:
        dati = corpo.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(dati)))
        for nome, valore in (extra or {}).items():
            self.send_header(nome, valore)
        self.end_headers()
        self.wfile.write(dati)

    def do_GET(self) -> None:  # noqa: N802 - nome imposto da BaseHTTPRequestHandler
        percorso = self.path.split("?")[0]
        if percorso == "/robots.txt":
            self._invia("User-agent: *\nDisallow: /privato\nCrawl-delay: 0\n", tipo="text/plain")
        elif percorso == "/":
            link = "".join(
                f'<a href="{href}">{href}</a>' for href in
                ["/a", "/a/", "/a#frammento", "/a?b=2&a=1", "/a?a=1&b=2", "/privato", "/errore", "/429", "/indice", "/js"]
            )
            self._invia(f"<html><title>Radice</title><body><h1>Radice</h1>{link}</body></html>")
        elif percorso in ("/a", "/a/"):
            self._invia("<html><title>A</title><body><h1>A</h1><a href='/'>torna</a></body></html>")
        elif percorso == "/privato":
            SitoFinto.protette_chieste += 1
            self._invia("<html><title>Vietata</title><body>non si deve leggere</body></html>")
        elif percorso == "/errore":
            self._invia("errore", status=500, tipo="text/plain")
        elif percorso == "/429-negativo":
            if SitoFinto.retry_negativo == 0:
                SitoFinto.retry_negativo += 1
                self._invia("aspetta", status=429, tipo="text/plain", extra={"Retry-After": "-3"})
            else:
                self._invia("<html><title>Dopo retry</title><body>ok</body></html>")
        elif percorso == "/sempre-429":
            SitoFinto.sempre_429 += 1
            self._invia("no", status=429, tipo="text/plain", extra={"Retry-After": "0"})
        elif percorso == "/binario":
            self._invia("pdf", tipo="application/pdf")
        elif percorso == "/429":
            if SitoFinto.retry_429 == 0:
                SitoFinto.retry_429 += 1
                self._invia("troppe richieste", status=429, tipo="text/plain", extra={"Retry-After": "0"})
            else:
                self._invia("<html><title>Dopo retry</title><body>ok</body></html>")
        elif percorso == "/indice":
            link = "".join(f'<a href="/p/{n}">p{n}</a>' for n in range(PAGINE))
            self._invia(f"<html><title>Indice</title><body>{link}</body></html>")
        elif percorso.startswith("/p/"):
            try:
                numero = int(percorso[3:])
            except ValueError:
                self._invia("no", status=404, tipo="text/plain")
                return
            self._invia(f"<html><title>Pagina {numero}</title><body><p>contenuto {numero}</p><a href='/indice'>indice</a></body></html>")
        elif percorso == "/verso-a":
            self.send_response(302)
            self.send_header("Location", "/a")
            self.end_headers()
        elif percorso == "/verso-privato":
            self.send_response(302)
            self.send_header("Location", "http://169.254.169.254/latest/meta-data/")
            self.end_headers()
        elif percorso == "/con-cache":
            SitoFinto.cache_chieste += 1
            self._invia("<html><title>Con cache</title><body>pagina con cache</body></html>")
        elif percorso == "/con-link-storti":
            self._invia(
                "<html><title>Link storti</title><body>"
                "<a href='http://example.com:99999/x'>porta storta</a>"
                "<a href='http://user:pass@example.com/y'>credenziali</a>"
                "<a href='/a'>lecito</a></body></html>"
            )
        elif percorso == "/js":
            self._invia(
                "<html><title>JS</title><body><p id='x'></p>"
                "<script>document.getElementById('x').textContent='RENDERIZZATO-DA-JS';</script>"
                "</body></html>"
            )
        else:
            self._invia("non trovato", status=404, tipo="text/plain")


def con_sito():
    import contextlib

    @contextlib.contextmanager
    def gestore():
        SitoFinto.protette_chieste = 0
        SitoFinto.retry_429 = 0
        SitoFinto.retry_negativo = 0
        SitoFinto.sempre_429 = 0
        SitoFinto.cache_chieste = 0
        server = ThreadingHTTPServer(("127.0.0.1", 0), SitoFinto)
        filo = threading.Thread(target=server.serve_forever, daemon=True)
        filo.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}"
        finally:
            server.shutdown()
            server.server_close()

    return gestore()


def test_guardia_ssrf() -> None:
    print("\nguardia SSRF e schemi")
    for url in ("http://127.0.0.1:1/", "http://169.254.169.254/latest/meta-data/", "http://10.0.0.1/", "http://[::1]/"):
        try:
            crawler.verifica_rete(url)
        except crawler.ErroreCrawler:
            check(f"rifiutato: {url}", True)
        else:
            check(f"rifiutato: {url}", False, "nessun rifiuto")
    try:
        crawler.verifica_rete("http://127.0.0.1:1/", consenti_loopback=True)
        check("loopback ammesso solo con --consenti-loopback", True)
    except crawler.ErroreCrawler:
        check("loopback ammesso solo con --consenti-loopback", False, "rifiutato anche col flag")
    for url in ("file:///etc/passwd", "ftp://example.com/x", "gopher://x"):
        try:
            crawler.verifica_rete(url, consenti_loopback=True)
        except crawler.ErroreCrawler:
            check(f"schema rifiutato: {url.split(':', 1)[0]}", True)
        else:
            check(f"schema rifiutato: {url.split(':', 1)[0]}", False)


def test_canonico() -> None:
    print("\nURL canonico")
    check("frammento tolto", crawler.canonico("http://x/a#f") == "http://x/a")
    check("porta 80 tolta", crawler.canonico("http://x:80/a") == "http://x/a")
    check("barra finale tolta", crawler.canonico("http://x/a/") == "http://x/a")
    check("caso dell'host", crawler.canonico("http://X.Example/a") == "http://x.example/a")
    check(
        "ordine dei parametri",
        crawler.canonico("http://x/a?b=2&a=1") == crawler.canonico("http://x/a?a=1&b=2"),
    )
    check("`.` e `..` risolti", crawler.canonico("http://x/a/../b") == "http://x/b")
    check("`.` nel mezzo", crawler.canonico("http://x/a/./b/") == "http://x/a/b")
    try:
        crawler.canonico("http://x:99999/")
    except crawler.ErroreCrawler:
        check("porta fuori range rifiutata, non traceback", True)
    else:
        check("porta fuori range rifiutata, non traceback", False)
    check(
        "la CLI rifiuta la porta invalida senza traceback",
        crawler.main(["avvia", "http://127.0.0.1:99999/", "--consenti-loopback"]) == 1,
    )
    try:
        crawler.avvia("http://user:pass@127.0.0.1:1/", uscita=Path("/tmp/x"), consenti_loopback=True)
    except crawler.ErroreCrawler:
        check("credenziali rifiutate anche dal flusso avvia", True)
    else:
        check("credenziali rifiutate anche dal flusso avvia", False)


def test_robots(base: str) -> None:
    print("\nrobots.txt")
    SitoFinto.protette_chieste = 0
    with tempfile.TemporaryDirectory() as tmp:
        uscita = Path(tmp) / "scarico"
        riepilogo, _ = crawler.avvia(
            base + "/", uscita=uscita, max_pagine=10, max_profondita=1, ritardo=0,
            consenti_loopback=True,
        )
        manifest = [json.loads(r) for r in (uscita / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
    check("la pagina vietata non e' mai stata chiesta", SitoFinto.protette_chieste == 0, str(SitoFinto.protette_chieste))
    check("robots ha bloccato qualcosa", riepilogo.robots_bloccate >= 1, str(riepilogo.robots_bloccate))
    check("la pagina vietata non e' nel manifesto", all("privato" not in v["canonico"] for v in manifest))


def test_mille_pagine(base: str) -> None:
    print(f"\n{PAGINE} pagine in una passata")
    with tempfile.TemporaryDirectory() as tmp:
        uscita = Path(tmp) / "scarico"
        riepilogo, cartella = crawler.avvia(
            base + "/indice", uscita=uscita, max_pagine=PAGINE + 1, max_profondita=1,
            ritardo=0, max_secondi=180, consenti_loopback=True,
        )
        righe = (uscita / "manifest.jsonl").read_text(encoding="utf-8").splitlines()
        voci = [json.loads(r) for r in righe]
        canonici = [v["canonico"] for v in voci]
        impronte_ok = all(
            (uscita / "pagine" / f"{v['sha256']}.html").is_file()
            and hashlib.sha256((uscita / "pagine" / f"{v['sha256']}.html").read_bytes()).hexdigest() == v["sha256"]
            for v in voci
        )
        indice = json.loads((uscita / "indice.json").read_text(encoding="utf-8"))

    check("ha scaricato tutte le pagine", riepilogo.pagine == PAGINE + 1, str(riepilogo.pagine))
    check("manifesto completo", len(voci) == riepilogo.pagine, f"{len(voci)} vs {riepilogo.pagine}")
    check("0 URL duplicati nel manifesto", len(canonici) == len(set(canonici)), str(len(canonici) - len(set(canonici))))
    check("ogni contenuto salvato una volta", len({v["sha256"] for v in voci}) == len(voci))
    check("ogni snapshot ha l'impronta giusta", impronte_ok)
    check("il manifesto ha la provenance", all(
        v.get("url") and v.get("status") == 200 and v.get("fetched_at") and v.get("via") == "http"
        and v.get("estrattore") for v in voci
    ))
    check("l'indice dichiara la policy", indice.get("policy") == "CRAWLING.md")
    check("costo per pagina misurato", indice["pagine"]["costo_medio_byte"] > 0)


def test_redirect(base: str) -> None:
    print("\nredirect: leggittimi e verso la rete interna")
    with tempfile.TemporaryDirectory() as tmp:
        male, _ = crawler.avvia(
            base + "/verso-privato", uscita=Path(tmp) / "male", max_pagine=1,
            max_profondita=0, ritardo=0, consenti_loopback=True,
        )
        bene, uscita = crawler.avvia(
            base + "/verso-a", uscita=Path(tmp) / "bene", max_pagine=1,
            max_profondita=0, ritardo=0, consenti_loopback=True,
        )
        voci = [
            json.loads(r)
            for r in (uscita / "manifest.jsonl").read_text(encoding="utf-8").splitlines()
        ]
    check("un redirect verso la rete interna e' rifiutato", male.pagine == 0 and male.errori == 1, male.motivi[:1])
    check("un redirect lecito viene seguito", bene.pagine == 1, str(bene.pagine))
    check(
        "la provenance tiene l'URL chiesto e quello finale",
        bool(voci) and voci[0]["richiesto"].endswith("/verso-a") and voci[0]["url"].endswith("/a"),
        str(voci[0]) if voci else "",
    )
    try:
        crawler.verifica_rete("http://user:pass@example.com/")
    except crawler.ErroreCrawler:
        check("URL con credenziali rifiutato", True)
    else:
        check("URL con credenziali rifiutato", False, "nessun rifiuto")


def test_casi_limite(base: str) -> None:
    print("\ncasi limite: retry, non-HTML, credenziali")
    with tempfile.TemporaryDirectory() as tmp:
        negativo, _ = crawler.avvia(
            base + "/429-negativo", uscita=Path(tmp) / "neg", max_pagine=1,
            max_profondita=0, ritardo=0, consenti_loopback=True,
        )
        SitoFinto.sempre_429 = 0
        sempre, _ = crawler.avvia(
            base + "/sempre-429", uscita=Path(tmp) / "sempre", max_pagine=1,
            max_profondita=0, ritardo=0, consenti_loopback=True,
        )
        binario, _ = crawler.avvia(
            base + "/binario", uscita=Path(tmp) / "bin", max_pagine=1,
            max_profondita=0, ritardo=0, consenti_loopback=True,
        )
    check("Retry-After negativo non manda in crash", negativo.pagine == 1, str(negativo.motivi[:1]))
    check("i retry sono al massimo MAX_RETRY", SitoFinto.sempre_429 == crawler.MAX_RETRY + 1, str(SitoFinto.sempre_429))
    check("un 429 definitivo diventa un errore, non una pagina", sempre.pagine == 0 and sempre.errori == 1)
    check("un contenuto non testuale e' rifiutato", binario.pagine == 0 and binario.errori == 1, str(binario.motivi[:1]))


def test_link_storti(base: str) -> None:
    print("\nun link malformato non ferma lo scarico")
    with tempfile.TemporaryDirectory() as tmp:
        uscita = Path(tmp) / "scarico"
        riepilogo, _ = crawler.avvia(
            base + "/con-link-storti", uscita=uscita, max_pagine=10,
            max_profondita=1, ritardo=0, consenti_loopback=True,
        )
        canonici = [
            json.loads(r)["canonico"]
            for r in (uscita / "manifest.jsonl").read_text(encoding="utf-8").splitlines()
        ]
    check("lo scarico non abortisce", riepilogo.pagine >= 2, str(riepilogo.pagine))
    check("i link storti sono scartati e contati", riepilogo.saltate >= 2, str(riepilogo.saltate))
    check("il link lecito e' stato seguito", any(c.endswith("/a") for c in canonici), str(canonici))
    check("lo scarto e' motivato", any("link scartato" in m for m in riepilogo.motivi), str(riepilogo.motivi[:2]))


def test_cache_crawler(base: str) -> None:
    print("\nla cache del crawler (M5)")
    with tempfile.TemporaryDirectory(prefix="ad-crawl-cache-") as tmp:
        os.environ["AD_CACHE_DIR"] = str(Path(tmp) / "cache")
        SitoFinto.cache_chieste = 0
        primo, _ = crawler.avvia(
            base + "/con-cache", uscita=Path(tmp) / "primo", max_pagine=1,
            max_profondita=0, ritardo=0, consenti_loopback=True, usa_cache=True,
        )
        richieste_primo = SitoFinto.cache_chieste
        secondo, uscita2 = crawler.avvia(
            base + "/con-cache", uscita=Path(tmp) / "secondo", max_pagine=1,
            max_profondita=0, ritardo=0, consenti_loopback=True, usa_cache=True,
        )
        richieste_secondo = SitoFinto.cache_chieste
        voci2 = [json.loads(r) for r in (uscita2 / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
        cache.salva(base + "/con-cache", b"<html><title>vecchia</title></html>",
                    policy="crawler-v1", ttl=0)
        terzo, _ = crawler.avvia(
            base + "/con-cache", uscita=Path(tmp) / "terzo", max_pagine=1,
            max_profondita=0, ritardo=0, consenti_loopback=True, usa_cache=True,
        )
        richieste_terzo = SitoFinto.cache_chieste
        os.environ.pop("AD_CACHE_DIR", None)
    check("il primo giro tocca il server", richieste_primo >= 1, str(richieste_primo))
    check("il secondo giro NON tocca il server", richieste_secondo == richieste_primo,
          f"{richieste_primo} -> {richieste_secondo}")
    check("il secondo giro viene dalla cache", secondo.via_cache == 1 and voci2[0]["via"] == "cache",
          str(voci2[:1]))
    check("una voce scaduta si riscarica", richieste_terzo > richieste_secondo and terzo.via_cache == 0,
          f"{richieste_secondo} -> {richieste_terzo}")


def test_429(base: str) -> None:
    print("\n429 con Retry-After")
    with tempfile.TemporaryDirectory() as tmp:
        riepilogo, uscita = crawler.avvia(
            base + "/429", uscita=Path(tmp) / "scarico", max_pagine=1, max_profondita=0,
            ritardo=0, consenti_loopback=True,
        )
        voci = [json.loads(r) for r in (uscita / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
    check("la pagina e' stata scaricata dopo il retry", riepilogo.pagine == 1, str(riepilogo.pagine))
    check("nessun errore registrato", riepilogo.errori == 0, str(riepilogo.motivi))


def test_limiti(base: str) -> None:
    print("\nlimiti di pagine e profondita'")
    with tempfile.TemporaryDirectory() as tmp:
        tre, _ = crawler.avvia(
            base + "/", uscita=Path(tmp) / "tre", max_pagine=3, max_profondita=1,
            ritardo=0, consenti_loopback=True,
        )
        sola, _ = crawler.avvia(
            base + "/indice", uscita=Path(tmp) / "sola", max_pagine=10, max_profondita=0,
            ritardo=0, consenti_loopback=True,
        )
    check("max-pagine rispettato", tre.pagine == 3, str(tre.pagine))
    check("max-profondita 0 = solo la partenza", sola.pagine == 1, str(sola.pagine))


def test_browser(base: str) -> None:
    print("\nbrowser headless (solo se installato)")
    if not (shutil.which("chromium") or shutil.which("google-chrome")):
        print("  SKIP — nessun browser headless installato: il caso non e' provato")
        return
    with tempfile.TemporaryDirectory() as tmp:
        riepilogo, uscita = crawler.avvia(
            base + "/js", uscita=Path(tmp) / "scarico", max_pagine=1, max_profondita=0,
            ritardo=0, consenti_loopback=True, browser=True,
        )
        voci = [json.loads(r) for r in (uscita / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
        corpo = (uscita / "pagine" / f"{voci[0]['sha256']}.html").read_text(encoding="utf-8", errors="replace")
    check("il browser e' stato usato", riepilogo.via_browser == 1, str(riepilogo.via_browser))
    check(
        "la pagina contiene il testo reso da JavaScript",
        "<p id=\"x\">RENDERIZZATO-DA-JS</p>" in corpo.replace("'", '"'),
        corpo[:200],
    )


def main() -> int:
    with con_sito() as base:
        test_guardia_ssrf()
        test_canonico()
        test_robots(base)
        test_mille_pagine(base)
        test_redirect(base)
        test_link_storti(base)
        test_cache_crawler(base)
        test_429(base)
        test_casi_limite(base)
        test_limiti(base)
        test_browser(base)

    print("\nconservazione minima")
    with tempfile.TemporaryDirectory() as tmp:
        finta = Path(tmp) / "non-uno-scarico"
        finta.mkdir()
        (finta / "x.txt").write_text("x", encoding="utf-8")
        try:
            crawler.pulisci(finta)
        except crawler.ErroreCrawler:
            check("una cartella qualunque non si cancella", finta.exists())
        else:
            check("una cartella qualunque non si cancella", False)
    with tempfile.TemporaryDirectory() as tmp:
        vero = Path(tmp) / "vero"
        vero.mkdir()
        (vero / "manifest.jsonl").write_text("", encoding="utf-8")
        crawler.pulisci(vero)
        check("uno scarico vero si cancella", not vero.exists())

    print()
    print(f"  {PASSATI} controlli passati")
    if FALLITI:
        print(f"FALLITI: {len(FALLITI)}")
        return 1
    print("PASS — il crawler legge dentro le regole e lascia la traccia")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
