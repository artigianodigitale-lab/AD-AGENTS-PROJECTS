#!/usr/bin/env python3
"""Il crawler del motore: legge il web dentro le regole, e lascia la traccia (M3, `DEC-0113`).

Perche' esiste. `ricerca.py` legge **una pagina** per volta. Un sistema che deve alimentare
una memoria verificabile ha bisogno di seguire i link, deduplicare, rispettare `robots.txt`
e i limiti del sito, **rifiutare la rete interna** e conservare la **provenienza** di ogni
pagina: senza queste cose lo scraping e' scaricare HTML a caso, e un crawler con URL
arbitrari e' anche una porta SSRF verso `127.0.0.1` e `169.254.169.254`.

Cosa fa, e in che ordine:

  1. **guardia SSRF** — reti private, loopback, link-local, metadata cloud e CGNAT rifiutate;
     `--consenti-loopback` esiste **solo** per le prove locali e lo dichiara;
  2. **robots.txt** — letto una volta per sito e applicato; se non si legge (5xx), il sito
     si disabilita (conservativo); un 404 non impone niente;
  3. **rate limit** per dominio e `Crawl-delay`; backoff su 429/503 rispettando `Retry-After`;
  4. **HTTP prima**, **browser headless** (`chromium --dump-dom`) solo se la pagina senza
     JavaScript resta vuota — e solo con `--browser`;
  5. **snapshot + manifesto**: ogni pagina ha URL canonico, sha256 del corpo, status, data,
     profondita'. Il dato senza la sua traccia non entra;
  6. **estrazione deterministica**: titolo, meta, titoli, JSON-LD, link, testo; con `--schema`
     si estraggono campi dichiarati (tag/classe/attributo), senza modello.

La policy che questo strumento implementa e' `CRAWLING.md`: si leggono pagine pubbliche, non
si superano paywall o login, non si raccolgono dati personali in massa, non si aggira un
divieto.

Uso:
    python3 tools/crawler.py avvia <url> [--max-pagine N] [--max-profondita K] [--ritardo S]
        [--dominio D ...] [--uscita DIR] [--schema FILE] [--browser]
        [--max-secondi S] [--consenti-loopback] [--json]

Esito: 0 lo scarico e' riuscito (almeno una pagina), 1 nessuna pagina o errori, 2 uso sbagliato.
"""

from __future__ import annotations

import argparse
import hashlib
import html as modulo_html
import ipaddress
import json
import posixpath
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

RADICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RADICE / "tools"))

import ad_docs  # noqa: E402
import cache  # noqa: E402  (M5: la cache verificabile di M4)

UA = "AD-AGENTS-PROJECTS-crawler/1.0 (policy: CRAWLING.md)"
SCHEMI_AMMESSI = ("http", "https")
TIPI_BUONI = ("text/html", "application/xhtml+xml", "text/plain", "application/json")
MAX_BYTES = 5_000_000
MAX_RETRY = 2
ATTESA_MASSIMA_RETRY = 10.0
#: Sotto questa quantita' di testo, senza JavaScript la pagina e' probabilmente vuota.
TESTO_MINIMO = 200
VERSIONE_ESTRATTORE = "1"


class ErroreCrawler(Exception):
    """Un errore con un rimedio: senza rimedio e' un vicolo cieco."""

    def __init__(self, messaggio: str, rimedio: str) -> None:
        super().__init__(messaggio)
        self.messaggio = messaggio
        self.rimedio = rimedio


# ---------------------------------------------------------------------------
# URL canonici e rete
# ---------------------------------------------------------------------------


def canonico(url: str) -> str:
    """L'URL su cui si deduplica: frammento, porta, caso, ordine dei parametri, `.`/`..`."""
    pezzi = urllib.parse.urlsplit(url.strip())
    if pezzi.username is not None or pezzi.password is not None:
        raise ErroreCrawler(
            "URL con credenziali",
            "non si mandano credenziali in un crawler: l'accesso a un'area riservata "
            "non e' materiale da scaricare (CRAWLING.md)",
        )
    schema = pezzi.scheme.lower()
    host = (pezzi.hostname or "").lower()
    try:
        porta = pezzi.port
    except ValueError as errore:
        raise ErroreCrawler(
            f"porta non valida: {url}",
            "una porta deve stare fra 0 e 65535: correggi l'URL",
        ) from errore
    if porta in (80, 443) or porta is None:
        rete = host
    else:
        rete = f"{host}:{porta}"
    # `..` e `.` vanno risolti PRIMA della dedup: altrimenti /a/../b e /b sono due URL
    # diversi per il dizionario e la stessa pagina per il server (rilievo della revisione).
    percorso = posixpath.normpath(pezzi.path or "/")
    if not percorso.startswith("/"):
        percorso = "/" + percorso
    percorso = re.sub(r"/{2,}", "/", percorso)
    if percorso != "/" and percorso.endswith("/"):
        percorso = percorso.rstrip("/")
    parametri = urllib.parse.parse_qsl(pezzi.query, keep_blank_values=True)
    query = urllib.parse.urlencode(sorted(parametri), doseq=True)
    return urllib.parse.urlunsplit((schema, rete, percorso, query, ""))


def _indirizzi(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    try:
        return [ipaddress.ip_address(str(v[4][0])) for v in socket.getaddrinfo(host, None)]
    except (socket.gaierror, ValueError) as errore:
        raise ErroreCrawler(
            f"nome non risolvibile: {host}",
            "controlla l'URL o la connessione: un host che non risolve non si scarica",
        ) from errore


def indirizzo_privato(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """True per tutto cio' che non e' Internet pubblico (guardia SSRF)."""
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast:
        return True
    if ip.is_reserved or ip.is_unspecified:
        return True
    if isinstance(ip, ipaddress.IPv4Address) and ip in ipaddress.ip_network("100.64.0.0/10"):
        return True  # CGNAT
    return False


def verifica_rete(url: str, *, consenti_loopback: bool = False) -> None:
    """Rifiuta gli URL che porterebbero alla rete interna (SSRF)."""
    pezzi = urllib.parse.urlsplit(url)
    if pezzi.scheme.lower() not in SCHEMI_AMMESSI:
        raise ErroreCrawler(
            f"schema non ammesso: {pezzi.scheme or '(nessuno)'}",
            "si scaricano solo pagine http/https",
        )
    if pezzi.username is not None or pezzi.password is not None:
        raise ErroreCrawler(
            "URL con credenziali",
            "non si mandano credenziali in un crawler: l'accesso a un'area riservata "
            "non e' materiale da scaricare (CRAWLING.md)",
        )
    host = pezzi.hostname
    if not host:
        raise ErroreCrawler("URL senza host", "indica un indirizzo completo, per esempio https://example.com")
    for ip in _indirizzi(host):
        if not indirizzo_privato(ip):
            continue
        if consenti_loopback and ip.is_loopback:
            continue
        raise ErroreCrawler(
            f"indirizzo non pubblico: {host} -> {ip}",
            "la rete interna e' vietata (SSRF). Per le prove locali usa --consenti-loopback, "
            "che vale solo per il loopback e lo dichiara",
        )


# ---------------------------------------------------------------------------
# robots.txt
# ---------------------------------------------------------------------------


@dataclass
class Robots:
    """Le regole del sito, lette una volta."""

    consentito: bool
    motivo: str
    crawl_delay: float | None = None
    _parser: Any = None

    def puo(self, url: str) -> tuple[bool, str]:
        if self._parser is None:
            return self.consentito, self.motivo
        return bool(self._parser.can_fetch(UA, url)), "robots.txt"


class _RedirectSicuro(urllib.request.HTTPRedirectHandler):
    """Ogni salto di un redirect passa dalla guardia SSRF.

    Senza questo, un URL pubblico che risponde `302 Location: http://169.254.169.254/…`
    porterebbe il crawler dentro la rete interna: la guardia guarda l'URL di partenza,
    non i salti. E' il buco classico del SSRF via redirect.
    """

    def __init__(self, consenti_loopback: bool) -> None:
        super().__init__()
        self.consenti_loopback = consenti_loopback

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        verifica_rete(newurl, consenti_loopback=self.consenti_loopback)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _apri(url: str, *, timeout: float, consenti_loopback: bool):
    opener = urllib.request.build_opener(_RedirectSicuro(consenti_loopback))
    richiesta = urllib.request.Request(url, headers={"User-Agent": UA})
    return opener.open(richiesta, timeout=timeout)


def leggi_robots(base: str, *, timeout: float, consenti_loopback: bool) -> Robots:
    """Legge `/robots.txt`. Se non si legge, il sito si disabilita (conservativo)."""
    pezzi = urllib.parse.urlsplit(base)
    robots_url = urllib.parse.urlunsplit((pezzi.scheme, pezzi.netloc, "/robots.txt", "", ""))
    verifica_rete(robots_url, consenti_loopback=consenti_loopback)
    try:
        with _apri(robots_url, timeout=timeout, consenti_loopback=consenti_loopback) as risposta:
            # Tetto anche su robots: non e' una pagina da leggere per intero.
            testo = risposta.read(512_000).decode("utf-8", errors="replace")
    except ErroreCrawler as errore:
        # Un redirect che porta nella rete interna rende robots illeggibile: e un sito
        # con robots illeggibile si disabilita (conservativo, come un 5xx).
        return Robots(False, f"robots.txt non leggibile ({errore.messaggio}): sito disabilitato")
    except urllib.error.HTTPError as errore:
        if errore.code in (404, 410):
            return Robots(True, "robots.txt assente (404): nessuna restrizione")
        return Robots(False, f"robots.txt illeggibile (HTTP {errore.code}): sito disabilitato")
    except (urllib.error.URLError, socket.timeout, OSError) as errore:
        return Robots(False, f"robots.txt non raggiungibile ({errore}): sito disabilitato")
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(testo.splitlines())
    ritardo = parser.crawl_delay(UA)
    return Robots(True, "robots.txt letto", float(ritardo) if ritardo else None, parser)


# ---------------------------------------------------------------------------
# Scarico
# ---------------------------------------------------------------------------


@dataclass
class Pagina:
    url: str
    canonico: str
    status: int
    content_type: str
    corpo: bytes
    profondita: int
    via: str = "http"  # http | browser
    #: L'URL chiesto, quando un redirect ha portato altrove: la provenance li tiene tutti e due.
    url_richiesto: str = ""


def scarica(
    url: str,
    *,
    timeout: float,
    consenti_loopback: bool,
    max_bytes: int = MAX_BYTES,
    tentativi: int = 0,
) -> Pagina:
    """Scarica una pagina. Su 429/503 ritenta rispettando `Retry-After`."""
    verifica_rete(url, consenti_loopback=consenti_loopback)
    try:
        # Ogni salto di redirect passa dalla guardia SSRF (`_RedirectSicuro`).
        with _apri(url, timeout=timeout, consenti_loopback=consenti_loopback) as risposta:
            tipo = risposta.headers.get("Content-Type", "").split(";")[0].strip().lower()
            finale = risposta.geturl()
            corpo = risposta.read(max_bytes + 1)
            status = risposta.status
    except ErroreCrawler:
        raise
    except urllib.error.HTTPError as errore:
        if errore.code in (429, 503) and tentativi < MAX_RETRY:
            attesa = _retry_after(errore.headers.get("Retry-After"))
            time.sleep(max(0.0, min(attesa, ATTESA_MASSIMA_RETRY)))
            return scarica(
                url, timeout=timeout, consenti_loopback=consenti_loopback,
                max_bytes=max_bytes, tentativi=tentativi + 1,
            )
        raise ErroreCrawler(
            f"HTTP {errore.code} su {url}",
            "il server ha rifiutato: dopo i retry il crawler si ferma su questa pagina",
        ) from errore
    except (urllib.error.URLError, socket.timeout, OSError) as errore:
        raise ErroreCrawler(
            f"pagina non raggiungibile: {url} ({errore})",
            "controlla la rete; una pagina che non risponde non si inventa",
        ) from errore

    if len(corpo) > max_bytes:
        raise ErroreCrawler(
            f"pagina oltre il tetto di {max_bytes} byte: {url}",
            "alza --max-byte o escludi la pagina: un file enorme non e' una pagina",
        )
    if tipo and tipo not in TIPI_BUONI:
        raise ErroreCrawler(
            f"contenuto non testuale ({tipo}): {url}",
            "il crawler legge testo e HTML: per i binari serve un altro strumento",
        )
    return Pagina(url=finale, canonico=canonico(finale), status=status, content_type=tipo,
                  corpo=corpo, profondita=0, url_richiesto=url)


def _retry_after(valore: str | None) -> float:
    if not valore:
        return 1.0
    try:
        # Un `Retry-After` negativo o assente non deve far esplodere lo sleep.
        return max(0.0, float(valore))
    except ValueError:
        return 1.0


def scarica_browser(url: str, *, timeout: float = 90, consenti_loopback: bool = False) -> Pagina:
    """Rende una pagina con JavaScript usando il browser headless gia' installato.

    Limite dichiarato: il browser si chiama con `--no-sandbox` (dentro un contenitore il
    sandbox di sistema non parte). Chi vuole il confine in piu' lo lancia dentro
    `tools/sandbox.py --rete`: la sandbox del motore e' quella di M2.
    """
    verifica_rete(url, consenti_loopback=consenti_loopback)
    eseguibile = shutil.which("chromium") or shutil.which("google-chrome") or shutil.which("chromium-browser")
    if eseguibile is None:
        raise ErroreCrawler(
            "nessun browser headless installato",
            "installa chromium (o google-chrome) per il rendering JavaScript; "
            "senza browser il crawler funziona in modalita' HTTP e lo dichiara",
        )
    comando = [
        eseguibile, "--headless=new", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--virtual-time-budget=8000", "--dump-dom", url,
    ]
    try:
        esito = subprocess.run(comando, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as errore:
        raise ErroreCrawler(
            f"il browser ha superato {timeout}s su {url}",
            "la pagina e' troppo lenta: resta la modalita' HTTP con il suo contenuto",
        ) from errore
    if esito.returncode != 0:
        raise ErroreCrawler(
            f"browser fallito su {url}",
            "il fallback del browser non ha prodotto HTML: resta la pagina HTTP",
        )
    corpo = esito.stdout or b""
    return Pagina(url=url, canonico=canonico(url), status=200, content_type="text/html",
                  corpo=corpo, profondita=0, via="browser", url_richiesto=url)


# ---------------------------------------------------------------------------
# Estrazione deterministica
# ---------------------------------------------------------------------------


class Estrattore(HTMLParser):
    """Titolo, meta, titoli, JSON-LD, link, testo. Niente modello, niente dipendenze."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.titolo = ""
        self.meta: dict[str, str] = {}
        self.h1: list[str] = []
        self.h2: list[str] = []
        self.link: list[str] = []
        self.jsonld: list[str] = []
        self.testo: list[str] = []
        self.campi: dict[str, list[str]] = {}
        self._schema: dict[str, dict[str, str]] = {}
        self._stack: list[tuple[str, set[str], dict[str, str]]] = []
        self._dentro: set[str] = set()
        self._buffer: list[str] = []
        self._jsonld = False

    def con_schema(self, schema: dict[str, dict[str, str]]) -> None:
        self._schema = schema

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributi = {nome: (valore or "") for nome, valore in attrs}
        classi = set(attributi.get("class", "").split())
        self._stack.append((tag, classi, attributi))
        if tag == "title":
            self._dentro.add("titolo")
            self._buffer = []
        elif tag in ("h1", "h2"):
            self._dentro.add(tag)
            self._buffer = []
        elif tag == "a" and attributi.get("href"):
            self.link.append(attributi["href"].strip())
        elif tag == "meta":
            nome = attributi.get("name") or attributi.get("property") or ""
            if nome and attributi.get("content"):
                self.meta[nome.lower()] = attributi["content"].strip()
        elif tag == "script" and "ld+json" in attributi.get("type", "").lower():
            self._jsonld = True
            self._buffer = []
        for campo, regola in self._schema.items():
            if regola.get("tag") != tag:
                continue
            if regola.get("classe") and regola["classe"] not in classi:
                continue
            valore = attributi.get(regola["attributo"], "") if regola.get("attributo") else None
            if valore is not None:
                self.campi.setdefault(campo, []).append(valore.strip())
            elif tag in ("title", "h1", "h2", "p", "span", "li", "div"):
                self._dentro.add(f"campo:{campo}")
                self._buffer = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._jsonld:
            testo = "".join(self._buffer).strip()
            if testo:
                self.jsonld.append(testo)
            self._jsonld = False
            self._buffer = []
        for etichetta, raccolta in (("titolo", None), ("h1", self.h1), ("h2", self.h2)):
            if etichetta in self._dentro and tag == etichetta:
                testo = " ".join("".join(self._buffer).split())
                if raccolta is None:
                    self.titolo = testo
                elif testo:
                    raccolta.append(testo)
                self._dentro.discard(etichetta)
                self._buffer = []
        for campo in [c for c in self._dentro if c.startswith("campo:")]:
            valore = " ".join("".join(self._buffer).split())
            if valore:
                self.campi.setdefault(campo.split(":", 1)[1], []).append(valore)
            self._dentro.discard(campo)
            self._buffer = []
        if self._stack:
            self._stack.pop()

    def handle_data(self, data: str) -> None:
        if self._jsonld:
            self._buffer.append(data)
            return
        if self._dentro:
            self._buffer.append(data)
            return
        if data.strip():
            self.testo.append(data)

    def risultato(self) -> dict[str, Any]:
        testo = " ".join(" ".join(self.testo).split())
        return {
            "titolo": self.titolo,
            "meta": self.meta,
            "h1": self.h1[:10],
            "h2": self.h2[:20],
            "link": self.link,
            "jsonld": self.jsonld[:10],
            "testo": testo[:20000],
            "campi": self.campi,
        }


def estrai_html(corpo: bytes) -> dict[str, Any]:
    parser = Estrattore()
    parser.feed(corpo.decode("utf-8", errors="replace"))
    return parser.risultato()


# ---------------------------------------------------------------------------
# Lo scarico vero
# ---------------------------------------------------------------------------


@dataclass
class Riepilogo:
    pagine: int = 0
    duplicati_evitati: int = 0
    robots_bloccate: int = 0
    errori: int = 0
    saltate: int = 0
    byte: int = 0
    via_browser: int = 0
    via_cache: int = 0
    motivi: list[str] = field(default_factory=list)

    def come_dict(self) -> dict[str, Any]:
        return {
            "pagine": self.pagine,
            "duplicati_evitati": self.duplicati_evitati,
            "robots_bloccate": self.robots_bloccate,
            "errori": self.errori,
            "saltate": self.saltate,
            "byte_scaricati": self.byte,
            "via_browser": self.via_browser,
            "pagine_da_cache": self.via_cache,
            "costo_medio_byte": (self.byte // self.pagine) if self.pagine else 0,
            "motivi": self.motivi[:20],
        }


def _dominio(url: str) -> str:
    return (urllib.parse.urlsplit(url).hostname or "").lower()


def _nel_perimetro(url: str, partenza: str, domini: list[str]) -> bool:
    host = _dominio(url)
    if domini:
        return any(host == d.lower() or host.endswith("." + d.lower()) for d in domini)
    return host == _dominio(partenza)


def _firma(corpo: bytes) -> str:
    return hashlib.sha256(corpo).hexdigest()


def avvia(
    partenza: str,
    *,
    uscita: Path,
    max_pagine: int = 100,
    max_profondita: int = 3,
    ritardo: float = 0.5,
    domini: list[str] | None = None,
    browser: bool = False,
    max_secondi: float = 600.0,
    consenti_loopback: bool = False,
    schema: Path | None = None,
    timeout: float = 20.0,
    usa_cache: bool = False,
    cache_ttl: int = cache.TTL_PREDEFINITO,
) -> tuple[Riepilogo, Path]:
    """Esegue lo scarico. Restituisce il riepilogo e la cartella del manifesto."""
    domini = list(domini or [])
    inizio = time.monotonic()
    scadenza = inizio + max_secondi
    partenza = canonico(partenza)
    verifica_rete(partenza, consenti_loopback=consenti_loopback)

    uscita.mkdir(parents=True, exist_ok=True)
    cartella_pagine = uscita / "pagine"
    cartella_pagine.mkdir(exist_ok=True)
    manifesto = uscita / "manifest.jsonl"
    manifesto.write_text("", encoding="utf-8")

    schema_campi: dict[str, dict[str, str]] = {}
    if schema is not None:
        try:
            schema_campi = json.loads(schema.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as errore:
            raise ErroreCrawler(
                f"schema illeggibile: {schema} ({errore})",
                "lo schema e' un JSON di campi: {\"campo\": {\"tag\": \"h1\"}}",
            ) from errore

    coda: deque[tuple[str, int]] = deque([(partenza, 0)])
    visti: set[str] = set()
    firme: set[str] = set()
    robots_per_sito: dict[str, Robots] = {}
    ultimo_per_sito: dict[str, float] = {}
    riepilogo = Riepilogo()

    while coda and riepilogo.pagine < max_pagine and time.monotonic() < scadenza:
        url, profondita = coda.popleft()
        if url in visti:
            riepilogo.duplicati_evitati += 1
            continue
        visti.add(url)
        if not _nel_perimetro(url, partenza, domini):
            riepilogo.saltate += 1
            riepilogo.motivi.append(f"fuori perimetro: {url}")
            continue

        sito = urllib.parse.urlunsplit((*urllib.parse.urlsplit(url)[:2], "", "", ""))
        if sito not in robots_per_sito:
            robots_per_sito[sito] = leggi_robots(
                sito, timeout=timeout, consenti_loopback=consenti_loopback
            )
        robots = robots_per_sito[sito]
        consentito, motivo = robots.puo(url)
        if not consentito:
            riepilogo.robots_bloccate += 1
            riepilogo.motivi.append(f"robots: {url}")
            continue

        attesa = max(ritardo, robots.crawl_delay or 0.0)
        ultimo = ultimo_per_sito.get(sito)
        if ultimo is not None:
            pausa = attesa - (time.monotonic() - ultimo)
            if pausa > 0:
                time.sleep(min(pausa, attesa))
        ultimo_per_sito[sito] = time.monotonic()

        pagina: Pagina | None = None
        if usa_cache:
            # La cache si consulta DOPO robots e rate limit: non e' una scorciatoia per
            # aggirare le regole, e' una scorciatoia per non richiedere due volte lo stesso
            # contenuto (M5, DEC-0117). La voce scaduta non viene usata.
            voce = cache.leggi(url, policy="crawler-v1")
            if voce is not None:
                corpo = voce["corpo"]
                tipo = "text/html" if corpo.lstrip().startswith(b"<") else "text/plain"
                pagina = Pagina(url=url, canonico=canonico(url), status=200,
                                content_type=tipo, corpo=corpo, profondita=profondita,
                                via="cache", url_richiesto=url)
                riepilogo.via_cache += 1
        if pagina is None:
            try:
                pagina = scarica(
                    url, timeout=timeout, consenti_loopback=consenti_loopback
                )
                estratto_pre = estrai_html(pagina.corpo) if "html" in pagina.content_type or not pagina.content_type else {}
                if browser and len(estratto_pre.get("testo", "")) < TESTO_MINIMO:
                    try:
                        pagina = scarica_browser(
                            url, consenti_loopback=consenti_loopback
                        )
                        riepilogo.via_browser += 1
                    except ErroreCrawler as errore:
                        riepilogo.motivi.append(f"browser: {url} ({errore.messaggio})")
                if usa_cache:
                    cache.salva(url, pagina.corpo, via=pagina.via, policy="crawler-v1", ttl=cache_ttl)
            except ErroreCrawler as errore:
                riepilogo.errori += 1
                riepilogo.motivi.append(f"errore: {url} ({errore.messaggio})")
                continue
            except cache.ErroreCache as errore:
                riepilogo.errori += 1
                riepilogo.motivi.append(f"cache: {url} ({errore.messaggio})")
                continue

        firma = _firma(pagina.corpo)
        if firma in firme:
            riepilogo.duplicati_evitati += 1
            continue
        firme.add(firma)
        # Un redirect puo' portare a un URL gia' visto: si segna anche quello finale,
        # cosi' il manifesto non contiene due volte la stessa pagina.
        visti.add(pagina.canonico)
        (cartella_pagine / f"{firma}.html").write_bytes(pagina.corpo)
        estratto = estrai_html(pagina.corpo) if pagina.corpo else {}
        if schema_campi:
            parser = Estrattore()
            parser.con_schema(schema_campi)
            parser.feed(pagina.corpo.decode("utf-8", errors="replace"))
            estratto["campi"] = parser.campi
        riepilogo.pagine += 1
        riepilogo.byte += len(pagina.corpo)
        voce = {
            "url": pagina.url,
            "canonico": pagina.canonico,
            "status": pagina.status,
            "sha256": firma,
            "content_type": pagina.content_type,
            "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "profondita": pagina.profondita or profondita,
            "via": pagina.via,
            "estrattore": VERSIONE_ESTRATTORE,
            "titolo": estratto.get("titolo", ""),
            "richiesto": pagina.url_richiesto or pagina.url,
            "link": len(estratto.get("link", []) or []),
        }
        with manifesto.open("a", encoding="utf-8") as aperto:
            aperto.write(json.dumps(voce, ensure_ascii=False) + "\n")

        if profondita < max_profondita:
            for href in estratto.get("link", []) or []:
                try:
                    assoluto = urllib.parse.urljoin(page_url(pagina), href)
                except ValueError:
                    continue
                if not assoluto.lower().startswith(("http://", "https://")):
                    continue
                try:
                    nuovo = canonico(assoluto)
                except ErroreCrawler as errore:
                    # Un link storto (porta fuori range, credenziali) si SCARTA: non deve
                    # far abortire l'intero crawl (rilievo della seconda revisione di M3).
                    riepilogo.saltate += 1
                    riepilogo.motivi.append(f"link scartato: {href} ({errore.messaggio})")
                    continue
                if nuovo not in visti and not any(nuovo == u for u, _ in coda):
                    coda.append((nuovo, profondita + 1))

    indice = {
        "partenza": partenza,
        "pagine": riepilogo.come_dict(),
        "manifesto": str(manifesto),
        "pagine_dir": str(cartella_pagine),
        "schema": str(schema) if schema else "",
        "limiti": {
            "max_pagine": max_pagine,
            "max_profondita": max_profondita,
            "max_secondi": max_secondi,
            "ritardo": ritardo,
            "consenti_loopback": consenti_loopback,
            "browser": browser,
        },
        "durata_secondi": round(time.monotonic() - inizio, 2),
        "policy": "CRAWLING.md",
    }
    (uscita / "indice.json").write_text(
        json.dumps(indice, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return riepilogo, uscita


def page_url(pagina: Pagina) -> str:
    return pagina.url


def pulisci(cartella: Path) -> None:
    """Cancella uno scarico (policy: conservazione minima, cancellazione su richiesta).

    Solo uno scarico vero: deve contenere il manifesto o l'indice, e non deve stare dentro
    il motore. `rmtree` su una cartella qualunque e' un comando che cancella il lavoro di
    qualcun altro (rilievo della revisione di M3).
    """
    percorso = Path(cartella).resolve()
    if not percorso.is_dir():
        raise ErroreCrawler(f"non esiste: {percorso}", "controlla il percorso dello scarico")
    radice = RADICE.resolve()
    if percorso == radice or radice in percorso.parents:
        raise ErroreCrawler(
            f"dentro il motore: {percorso}",
            "uno scarico vive fuori dal repository (per esempio in ~/.cache/ad-crawl): "
            "qui non si cancella niente",
        )
    if percorso == Path.home().resolve():
        raise ErroreCrawler("la cartella di casa non e' uno scarico", "indica la cartella dello scarico")
    if not ((percorso / "manifest.jsonl").is_file() or (percorso / "indice.json").is_file()):
        raise ErroreCrawler(
            f"non sembra uno scarico: {percorso}",
            "manca manifest.jsonl (o indice.json): non cancello una cartella che non ho creato io",
        )
    shutil.rmtree(percorso)


def main(argv: list[str] | None = None) -> int:
    analizzatore = argparse.ArgumentParser(
        description="Legge il web dentro le regole e lascia la traccia (CRAWLING.md)"
    )
    sotto = analizzatore.add_subparsers(dest="azione", required=True)
    avvio = sotto.add_parser("avvia", help="esegue uno scarico")
    avvio.add_argument("url")
    avvio.add_argument("--max-pagine", type=int, default=100)
    avvio.add_argument("--max-profondita", type=int, default=3)
    avvio.add_argument("--ritardo", type=float, default=0.5)
    avvio.add_argument("--dominio", action="append", default=[])
    avvio.add_argument("--uscita", default="")
    avvio.add_argument("--schema")
    avvio.add_argument("--browser", action="store_true")
    avvio.add_argument("--max-secondi", type=float, default=600.0)
    avvio.add_argument("--timeout", type=float, default=20.0)
    avvio.add_argument("--cache", action="store_true", help="usa la cache verificabile (M4) invece di riscaricare")
    avvio.add_argument("--cache-ttl", type=int, default=cache.TTL_PREDEFINITO, help="secondi di validita' della voce")
    avvio.add_argument("--consenti-loopback", action="store_true")
    avvio.add_argument("--json", action="store_true")
    pulire = sotto.add_parser("pulisci", help="cancella uno scarico")
    pulire.add_argument("cartella")

    args = analizzatore.parse_args(argv)
    if args.azione == "pulisci":
        try:
            pulisci(Path(args.cartella))
        except ErroreCrawler as errore:
            print(f"  {errore.messaggio}\n  {errore.rimedio}", file=sys.stderr)
            return 2
        print("  scarico cancellato")
        return 0

    uscita = Path(args.uscita) if args.uscita else (
        Path.home() / ".cache" / "ad-crawl" / datetime.now().strftime("%Y%m%d-%H%M%S")
    )
    try:
        riepilogo, cartella = avvia(
            args.url,
            uscita=uscita,
            max_pagine=args.max_pagine,
            max_profondita=args.max_profondita,
            ritardo=args.ritardo,
            domini=args.dominio,
            browser=args.browser,
            max_secondi=args.max_secondi,
            consenti_loopback=args.consenti_loopback,
            schema=Path(args.schema) if args.schema else None,
            timeout=args.timeout,
            usa_cache=args.cache,
            cache_ttl=args.cache_ttl,
        )
    except ErroreCrawler as errore:
        print(f"  {errore.messaggio}", file=sys.stderr)
        print(f"  rimedio: {errore.rimedio}", file=sys.stderr)
        return 1

    dati = riepilogo.come_dict()
    if args.json:
        print(json.dumps({"riepilogo": dati, "uscita": str(cartella),
                          "policy": "CRAWLING.md"}, indent=2, ensure_ascii=False))
    else:
        print(f"  pagine:            {dati['pagine']}")
        print(f"  duplicati evitati: {dati['duplicati_evitati']}")
        print(f"  bloccate da robots:{dati['robots_bloccate']}")
        print(f"  errori:            {dati['errori']}")
        print(f"  byte scaricati:    {dati['byte_scaricati']} ({dati['costo_medio_byte']} per pagina)")
        if dati["via_browser"]:
            print(f"  pagine col browser: {dati['via_browser']}")
        for motivo in dati["motivi"][:5]:
            print(f"    · {motivo}")
        print(f"  manifesto: {cartella / 'manifest.jsonl'}")
        print("  policy: CRAWLING.md")
    return 0 if riepilogo.pagine else 1


if __name__ == "__main__":
    raise SystemExit(main())
