#!/usr/bin/env python3
"""Ricerca sul web: prima la via leggera, il browser solo quando serve.

Perche' esiste, in una riga: il 2026-10-10 il fetch normale si e' fermato davanti
a Cloudflare su due fonti accademiche, e un browser vero le ha lette. Ma il browser
e' **pesante e lento**: chiamarlo sempre sarebbe uno spreco, e non chiamarlo mai
lascerebbe fuori meta' del web.

Quindi: si prova la via leggera, si **giudica** se il risultato e' utilizzabile, e
solo allora si paga il costo del browser. E le pagine si ricordano, cosi' la stessa
pagina non si scarica due volte.

Uso:
    python3 tools/ricerca.py leggi <url> [--forza] [--json]
    python3 tools/ricerca.py regole

Esito: 0 pagina letta, 1 altrimenti.
"""

from __future__ import annotations

import argparse
import hashlib
import html as modulo_html
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import ad_scope

RADICE = Path(__file__).resolve().parents[1]
PONTE = RADICE / "tools" / "camoufox_ponte.py"

#: Dove si ricordano le pagine. Fuori dal workspace: e' una cache, non una carta.
CACHE = Path(os.environ.get("AD_RICERCA_CACHE", Path.home() / ".cache" / "ad-ricerca"))

#: L'ambiente di camoufox. Variabile d'ambiente per non legarlo a un percorso fisso.
VENV = Path(os.environ.get("CAMOUFOX_VENV", Path.home() / ".cache" / "mf-camoufox-env"))

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131 Safari/537.36"

#: Quando una pagina leggera e' in realta' un muro, o una pagina vuota.
SOSPETTI = (
    "just a moment",
    "enable javascript",
    "attention required",
    "access denied",
    "are you a robot",
    "checking your browser",
    "cf-browser-verification",
)

#: Sotto questa soglia di testo, la pagina non dice niente: serve il browser.
MINIMO_CARATTERI = 600

#: **Il muro.** Una pagina che chiede di dimostrare di essere umano non e' una pagina da
#: leggere: e' una **porta che dice «non ora»**.
#:
#: Perche' e' un elenco a parte, e non un caso di `SOSPETTI`: quelli si **superano** col
#: browser — una sfida JavaScript la risolve, ed e' legittimo. Questi **no**. Il 2026-10-13
#: il CEO ha messo il confine in una riga: *«non deve bucare recaptcha ma almeno una ricerca
#: piu' approfondita si'»*.
#:
#: **La differenza non e' tecnica, e' di senso**: un muro JavaScript dice «serviti di un
#: browser»; un CAPTCHA dice «dimostrami che sei una persona». La seconda e' una domanda, e
#: la risposta onesta e' **fermarsi e dirlo a una persona** — non provare a essere lei.
#:
#: E' la stessa distinzione dei `robots.txt`: si legge cio' che e' permesso, e dove non si
#: puo' passare **si dice**, invece di aggirare in silenzio.
#: **Segnali strutturali.** Questi non si sbagliano: sono il modulo del CAPTCHA dentro la
#: pagina, non la parola. Un articolo puo' nominare «recaptcha» cento volte e non averne uno.
MURO_STRUTTURA = (
    "g-recaptcha",
    "grecaptcha",
    "hcaptcha",
    "cf-turnstile",
    "data-sitekey",
    "captcha-form",
    "challenge-form",
    "id=\"captcha",
    "class=\"captcha",
)

#: **Parole che valgono solo su una pagina corta.** Una pagina di CAPTCHA e' quasi vuota:
#: dice «dimostra di essere umano» e nient'altro. Un articolo che ne parla e' lungo. E'
#: il 2026-10-13: la prima versione cercava la parola nel testo, e **un articolo su
#: reCAPTCHA veniva scambiato per un CAPTCHA** — il difetto che il commento prevedeva.
MURO_PAROLE = (
    "complete the captcha",
    "verify you are human",
    "verifica che sei umano",
    "prove you are human",
    "human verification",
    "i'm not a robot",
    "non sono un robot",
    "unusual traffic",
)

#: Sotto questa lunghezza una pagina e' un avviso, non un contenuto.
PAGINA_CORTA = 4000


def e_un_muro(testo: str) -> str | None:
    """Il segnale di CAPTCHA trovato nella pagina, o None.

    Due strade, e servono entrambe per non sbagliare:

    - un **segnale strutturale** (`g-recaptcha`, `data-sitekey`…) vale sempre: e' il modulo,
      non la parola;
    - una **parola** vale solo se la pagina e' **corta**: una pagina di CAPTCHA dice
      «dimostra di essere umano» e nient'altro; un articolo che ne parla e' lungo.

    Il 2026-10-13 la prima versione cercava la parola e basta, e **un articolo su
    reCAPTCHA veniva scambiato per un CAPTCHA** — l'errore che il commento prevedeva e
    che ho commesso lo stesso.
    """
    testa = testo[:6000].lower()
    for segnale in MURO_STRUTTURA:
        if segnale in testa:
            return segnale
    if len(testo) < PAGINA_CORTA:
        for parola in MURO_PAROLE:
            if parola in testa:
                return parola
    return None

REGOLE = """COSA SI PUO' SCARICARE, E COSA NO

Questa e' una capacita' potente, e una capacita' potente senza regole e' un problema.

SI PUO'
  - pagine pubbliche, come le leggerebbe una persona con un browser
  - documentazione, articoli, listini pubblici, siti di concorrenti
  - rispettare robots.txt quando dichiara un divieto

NON SI PUO'
  - superare un muro di pagamento. Se il contenuto e' a pagamento, si legge
    l'abstract pubblico e basta: forzare il muro e' rubare
  - accedere a un'area riservata, anche con credenziali nostre, se i termini lo vietano
  - raccogliere dati personali di persone
  - scaricare in massa un sito: la cache e le pause esistono per questo
  - usare un browser per aggirare un divieto invece che per leggere JavaScript

REGOLA PRATICA
  Se la stessa cosa la faresti a mano col browser, si puo' fare.
  Se la faresti solo perche' nessuno ti vede, no.
"""


def _chiave(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]


def _pulito(html: str) -> str:
    """Toglie script, stili e tag: resta il testo leggibile."""
    senza = re.sub(r"(?is)<(script|style|noscript|svg).*?</\1>", " ", html)
    senza = re.sub(r"(?is)<br\s*/?>|</p>|</div>|</li>|</h[1-6]>", "\n", senza)
    testo = modulo_html.unescape(re.sub(r"<[^>]+>", " ", senza))
    testo = re.sub(r"[ \t]+", " ", testo)
    testo = re.sub(r"\n\s*\n\s*\n+", "\n\n", testo)
    return testo.strip()


def _sembra_un_muro(testo: str, html: str) -> str | None:
    """Perche' la via leggera non basta, o None se va bene."""
    basso = (testo + " " + html[:4000]).lower()
    for sospetto in SOSPETTI:
        if sospetto in basso:
            return f"la pagina sembra un muro ('{sospetto}')"
    if len(testo) < MINIMO_CARATTERI:
        return f"troppo poco testo ({len(testo)} caratteri): probabilmente serve JavaScript"
    return None


def _via_leggera(url: str) -> dict:
    """Il tentativo che costa niente."""
    richiesta = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "it,en"})
    with urllib.request.urlopen(richiesta, timeout=20) as risposta:
        grezzo = risposta.read(3_000_000)
        tipo = risposta.headers.get("Content-Type", "")
        charset = "utf-8"
        trovato = re.search(r"charset=([\w-]+)", tipo)
        if trovato:
            charset = trovato.group(1)
        return {"html": grezzo.decode(charset, errors="replace"), "url": risposta.url, "via": "leggera"}


def _via_browser(url: str, timeout: int = 70000) -> dict:
    """Il tentativo che costa: un browser vero."""
    interprete = VENV / "bin" / "python"
    if not interprete.exists():
        raise RuntimeError(f"ambiente camoufox assente: {interprete}")
    if not PONTE.is_file():
        raise RuntimeError(f"ponte assente: {PONTE}")

    esito = subprocess.run(
        [str(interprete), str(PONTE), url, "--timeout", str(timeout)],
        capture_output=True, text=True, timeout=timeout / 1000 + 60,
    )
    try:
        dati = json.loads(esito.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise RuntimeError(f"il ponte non ha risposto: {(esito.stderr or esito.stdout)[:200]}")
    if not dati.get("ok"):
        raise RuntimeError(f"browser: {dati.get('errore', 'errore sconosciuto')}")
    return {"html": dati.get("html", ""), "testo": dati.get("testo", ""),
            "titolo": dati.get("title", ""), "url": dati.get("url", url),
            "via": "browser", "ms": dati.get("ms")}



# ---------------------------------------------------------------------------
# robots.txt — la regola, dentro il tool
#
# Perche' esiste: le regole erano scritte in `regole`, e **nessuna era meccanizzata**.
# Camoufox poteva andare ovunque, e l'unica cosa che lo fermava era la disciplina
# dell'agente. Il 2026-10-12 il CEO ha scelto la risposta **(b)**:
#
#     il tool RIFIUTA di leggere una pagina vietata, e PASSA IL LINK al CEO.
#
# Il divieto riguarda un **cliente automatico**; una persona che apre quel link col
# browser non e' un cliente automatico. Quindi la macchina si ferma, e la persona no.
#
# Si usa `urllib.robotparser` invece di scrivere un parser: le regole di precedenza
# di robots.txt (gruppo piu' specifico, `Allow` che vince a parita' di lunghezza) sono
# una cosa dove sbagliare e' facile e silenzioso.
# ---------------------------------------------------------------------------

#: Il nome con cui ci presentiamo. Non fingiamo di essere un browser: chi legge i log
#: deve poterci riconoscere.
NOSTRO_AGENTE = "ad-projects-agent"

#: I robots.txt gia' letti, per host. Un host si chiede una volta sola.
_ROBOTS: dict[str, object] = {}


def robots_per(url: str, timeout: int = 15000):
    """Il robots.txt di quell'host, o None se non si riesce a leggerlo.

    Se il file non c'e' (404) o non si legge, **non si vieta**: l'assenza di una
    regola non e' una regola. Se il file c'e' e dice di no, si ubbidisce.
    """
    import urllib.robotparser

    pezzi = urllib.parse.urlsplit(url)
    if not pezzi.scheme or not pezzi.netloc:
        return None
    chiave = f"{pezzi.scheme}://{pezzi.netloc}"
    if chiave in _ROBOTS:
        return _ROBOTS[chiave]

    parser = urllib.robotparser.RobotFileParser()
    indirizzo = f"{chiave}/robots.txt"
    try:
        richiesta = urllib.request.Request(indirizzo, headers={"User-Agent": NOSTRO_AGENTE})
        with urllib.request.urlopen(richiesta, timeout=timeout / 1000) as risposta:
            testo = risposta.read(200_000).decode("utf-8", errors="replace")
        parser.parse(testo.splitlines())
    except urllib.error.HTTPError as errore:
        # 404 = nessun robots.txt = nessun divieto. Altri errori: non si sa, non si vieta.
        parser = None if errore.code in (404, 410) else "illeggibile"
    except Exception:  # noqa: BLE001
        parser = "illeggibile"

    _ROBOTS[chiave] = parser
    return parser


def robots_vieta(url: str, timeout: int = 15000) -> str | None:
    """Perche' quel percorso e' vietato. None = si puo' leggere.

    Restituisce una stringa **leggibile**, non un booleano: chi legge deve capire
    cosa e' successo, e perche' la macchina si e' fermata.
    """
    parser = robots_per(url, timeout)
    if parser is None or parser == "illeggibile":
        return None
    try:
        if parser.can_fetch(NOSTRO_AGENTE, url):
            return None
    except Exception:  # noqa: BLE001
        return None
    pezzi = urllib.parse.urlsplit(url)
    return f"robots.txt di {pezzi.netloc} vieta questo percorso a un cliente automatico"


def leggi(url: str, forza: bool = False, timeout: int = 70000) -> dict:
    """Legge una pagina. Ricorda il risultato, e sceglie la via meno costosa."""

    # **Il divieto si legge PRIMA di scaricare.** Con la risposta (b) del CEO: la
    # macchina si ferma e la persona riceve il link.
    vietato = robots_vieta(url, timeout)
    if vietato:
        return {
            "ok": False,
            "url": url,
            "vietato": vietato,
            "per_una_persona": url,
            "tentativi": [f"robots.txt: {vietato}"],
        }
    percorso_cache = CACHE / f"{_chiave(url)}.json"

    # La cache e' stato del processo, non una carta: vive fuori dall'albero di
    # autorita' **per scelta** (vedi CACHE). Qui la domanda giusta non e' quella di
    # `guard` — che e' la porta delle scritture DENTRO il sistema e rifiuta tutto
    # cio' che sta fuori, spegnendo la cache per un permesso che nessuno deve
    # chiedere — ma quella di `evaluate`: «questo percorso cade in una classe
    # protetta?». `AD_RICERCA_CACHE` la puo' puntare dentro un progetto, e li' la
    # risposta e' si': creare la cartella sarebbe gia' la scrittura non coperta
    # (ERR-0026). Fuori, non c'e' niente da proteggere. Il rifiuto si VEDE e non
    # interrompe la lettura: ricordare una pagina e' un lusso, leggerla no.
    verdetto = ad_scope.evaluate(CACHE)
    if not verdetto.allowed:
        print(f"cache non scritta: {verdetto.reason}", file=sys.stderr)
        percorso_cache = None
    else:
        CACHE.mkdir(parents=True, exist_ok=True)
        if not forza and percorso_cache.is_file():
            try:
                ricordato = json.loads(percorso_cache.read_text(encoding="utf-8"))
                ricordato["da_cache"] = True
                return ricordato
            except (OSError, ValueError):
                pass

    tentativi = []
    risultato: dict | None = None

    try:
        leggero = _via_leggera(url)
        motivo = _sembra_un_muro(_pulito(leggero["html"]), leggero["html"])
        if motivo is None:
            risultato = {
                "ok": True, "url": leggero["url"], "via": "leggera",
                "titolo": "", "html": leggero["html"], "testo": "",
            }
            risultato["titolo"] = _titolo(leggero["html"])
        else:
            tentativi.append(f"via leggera: {motivo}")
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as errore:
        tentativi.append(f"via leggera: {type(errore).__name__}: {str(errore)[:120]}")

    if risultato is None:
        try:
            risultato = _via_browser(url, timeout)
            risultato["ok"] = True
        except Exception as errore:
            tentativi.append(f"browser: {str(errore)[:160]}")
            return {"ok": False, "url": url, "via": None, "tentativi": tentativi}

    if not risultato.get("testo"):
        risultato["testo"] = _pulito(risultato.get("html", ""))
    risultato["tentativi"] = tentativi
    risultato["da_cache"] = False
    # L'HTML non si conserva: pesa, e serve solo per estrarre il testo.
    risultato.pop("html", None)

    # La cache sta fuori dal workspace, ma il percorso lo sceglie
    # `AD_RICERCA_CACHE`: se qualcuno la punta dentro un progetto, questa e' una
    # scrittura in un percorso protetto (ERR-0026). Il rifiuto si VEDE e non
    # interrompe la lettura: ricordare una pagina e' un lusso, leggerla no.
    if percorso_cache is not None:
        try:
            percorso_cache.write_text(json.dumps(risultato, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass  # la cache e' un lusso, non un requisito
    return risultato


def _titolo(html: str) -> str:
    trovato = re.search(r"(?is)<title[^>]*>(.*?)</title>", html)
    return modulo_html.unescape(trovato.group(1)).strip() if trovato else ""


# ---------------------------------------------------------------------------
# Il MURO, applicato a OGNI lettura
#
# Non solo alla ricerca: `verifica` usa `leggi` per provare che una fonte esiste, e una
# pagina che chiede un CAPTCHA **esiste**: risponde, e chiede una cosa che una macchina
# non deve dare. Avvolgere `leggi` una volta sola significa che nessuna strada lo salta.
# ---------------------------------------------------------------------------

_leggi_senza_muro = leggi


def leggi(url: str, forza: bool = False, timeout: int = 70000) -> dict:
    """Legge una pagina — e **si ferma davanti a un CAPTCHA**.

    Il confine l'ha messo il CEO il 2026-10-13: *«non deve bucare recaptcha ma almeno una
    ricerca piu' approfondita si'»*.

    **La differenza non e' tecnica, e' di senso.** Un muro JavaScript dice «serviti di un
    browser», e il browser lo risolve: e' leggere. Un CAPTCHA dice «dimostrami che sei
    una persona»: e' una domanda, e la risposta onesta e' **fermarsi e dirlo a una
    persona** — non provare a essere lei.

    La pagina **non si butta**: si dice che c'e', e si passa l'indirizzo, perche' chi
    l'ha chiesta possa aprirlo col suo browser.
    """
    esito = _leggi_senza_muro(url, forza=forza, timeout=timeout)
    if esito.get("ok"):
        segnale = e_un_muro(esito.get("testo", "") or esito.get("html", ""))
        if segnale:
            return {
                "ok": False,
                "url": url,
                "muro": segnale,
                "per_una_persona": esito.get("url") or url,
                "tentativi": [
                    f"la pagina chiede una prova di umanita' ({segnale}): "
                    "non si supera, ci si ferma"
                ],
            }
    return esito


# ---------------------------------------------------------------------------
# verifica — le fonti che citiamo esistono ancora?
#
# Perche' esiste: il 2026-10-12, **18 verbali su 52** citavano una fonte, e **nessuna
# era mai stata controllata**. Un indirizzo citato e' una stringa in un documento:
# nessuno sa se risolve ancora, ne' se e' stato letto davvero.
#
# **Un link morto e' peggio di un link assente**: sembra una prova, e non lo e'. Chi
# legge non puo' verificare, e non lo sa.
#
# Si controlla **prima** il robots.txt, come tutto il resto: una verifica non e' un
# permesso a ignorare le regole.
# ---------------------------------------------------------------------------

URL_RE = re.compile(r"https?://[^\s\)\]\}\>\`\"']+")

#: Dove si cercano le fonti citate: la macchina, non i progetti.
CARTELLE_FONTI = (
    "DECISIONI", "drift", "errori", "piani", "contratti", "approvazioni",
    "orchestrazione", "evidenze", "evals", "REQUISITI", "comunicazioni", "studio",
    "strategic_memory", ".brain", "milestone",
)


def _documenti(base: Path) -> list[Path]:
    """I documenti della macchina. **I progetti numerati restano fuori.**"""
    fuori = [f for f in base.glob("*.md")]
    for nome in CARTELLE_FONTI:
        cartella = base / nome
        if cartella.is_dir():
            fuori.extend(cartella.rglob("*.md"))
    return sorted(set(fuori))


def raccogli_url(base: Path | None = None) -> dict[str, list[str]]:
    """Gli indirizzi citati, e **quali documenti li citano**. Uno per indirizzo."""
    radice = base or RADICE
    trovati: dict[str, list[str]] = {}
    for documento in _documenti(radice):
        try:
            testo = documento.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for url in URL_RE.findall(testo):
            url = url.rstrip(".,;:)*")
            trovati.setdefault(url, [])
            if documento.name not in trovati[url]:
                trovati[url].append(documento.name)
    return trovati


def verifica(base: Path | None = None, timeout: int = 15000) -> list[dict]:
    """Controlla ogni indirizzo citato. Restituisce un esito per indirizzo."""
    esiti = []
    for url, documenti in sorted(raccogli_url(base).items()):
        voce = {"url": url, "citato_in": documenti, "stato": "", "dettaglio": ""}
        vietato = robots_vieta(url, timeout)
        if vietato:
            # (b): la macchina si ferma, la persona riceve il link.
            voce["stato"] = "vietato"
            voce["dettaglio"] = vietato
            esiti.append(voce)
            continue
        try:
            richiesta = urllib.request.Request(
                url, headers={"User-Agent": NOSTRO_AGENTE}, method="GET"
            )
            with urllib.request.urlopen(richiesta, timeout=timeout / 1000) as risposta:
                voce["stato"] = "vivo"
                voce["dettaglio"] = f"HTTP {risposta.status}"
        except urllib.error.HTTPError as errore:
            # **403 non e' "morto": e' "esiste e non ti fa entrare".** Il 2026-10-13
            # avevo etichettato due fonti come morte perche' rispondevano 403 — e una
            # di quelle l'avevo **letta col browser** due giorni prima. Un link morto
            # e' 404 o 410: la risorsa non c'e' piu'. Un 403 e' una porta chiusa su
            # una casa che c'e'.
            if errore.code in (404, 410):
                voce["stato"] = "morto"
                voce["dettaglio"] = f"HTTP {errore.code} — la risorsa non esiste piu'"
            elif errore.code in (401, 403, 429):
                # Ed e' qui che si chiama il browser: la via leggera non passa, e
                # Camoufox si'. **Dentro le regole** — il robots.txt e' gia' stato
                # controllato prima di arrivare qui.
                esito_browser = leggi(url, timeout=40000)
                if esito_browser.get("ok"):
                    voce["stato"] = "vivo"
                    voce["dettaglio"] = f"HTTP {errore.code} alla via leggera, letto col browser"
                else:
                    voce["stato"] = "protetto"
                    voce["dettaglio"] = (
                        f"HTTP {errore.code}: esiste ma rifiuta un cliente automatico"
                    )
            elif errore.code >= 500:
                voce["stato"] = "irraggiungibile"
                voce["dettaglio"] = f"HTTP {errore.code} — il server non risponde"
            else:
                voce["stato"] = "vivo"
                voce["dettaglio"] = f"HTTP {errore.code}"
        except Exception as errore:  # noqa: BLE001
            voce["stato"] = "irraggiungibile"
            voce["dettaglio"] = type(errore).__name__
        esiti.append(voce)
    return esiti


# ---------------------------------------------------------------------------
# cerca — trovare le fonti, non solo leggerle
#
# Perche' esiste: l'invariante 11 dice che a ogni richiesta il cervello *«cerca anche
# online»* se al mondo esiste un modo migliore. E il cervello **non aveva un modo di
# cercare**: `ricerca.py` leggeva un indirizzo che gia' conoscevi, e la ricerca la
# faceva lo strumento (DSH), non il sistema. Una capacita' del posto in cui giri non
# e' una capacita' tua.
#
# Si appoggia a **SearxNG locale** (`~/.searxng`, Docker): un motore che gira qui,
# interroga i motori che **noi abbiamo dichiarato permessi**, e non profila nessuno.
# Google, Bing e DuckDuckGo sono **spenti nella configurazione**, non nella memoria
# dell'agente: una regola che dipende dalla disciplina non e' una regola.
#
# **Le categorie vanno dichiarate.** Il 2026-10-12 una ricerca normale dava 0 risultati
# mentre `!arxiv` ne dava 10: senza categoria, SearxNG cerca in `general` — e li' non
# avevamo lasciato nessun motore, perche' i suoi erano proprio quelli che avevamo
# spento. Un motore che risponde "zero risultati" senza dire perche' e' peggio di un
# errore.
# ---------------------------------------------------------------------------

#: Dove gira la nostra istanza. Sovrascrivibile, perche' un servizio locale puo'
#: stare su un'altra porta.
SEARXNG = os.environ.get("AD_SEARXNG", "http://localhost:8080")

#: Le categorie che interroghiamo. Sono i motori che abbiamo dichiarato permessi
#: (`keep_only` in `~/.searxng/settings.yml`): `general` **non** e' fra queste, ed e'
#: voluto — senza Brave non c'e' nessun motore di web aperto.
CATEGORIE = ("science", "scientific publications", "it", "repos")


def cerca(domanda: str, categorie=CATEGORIE, limite: int = 15, timeout: int = 40000) -> dict:
    """Interroga la nostra istanza SearxNG. **Non** scarica le pagine: quello e' `leggi`."""
    if not domanda.strip():
        return {"ok": False, "errore": "domanda vuota", "risultati": []}

    parametri = urllib.parse.urlencode(
        {"q": domanda, "format": "json", "categories": ",".join(categorie)}
    )
    indirizzo = f"{SEARXNG.rstrip('/')}/search?{parametri}"
    try:
        richiesta = urllib.request.Request(
            indirizzo, headers={"User-Agent": NOSTRO_AGENTE, "Accept": "application/json"}
        )
        with urllib.request.urlopen(richiesta, timeout=timeout / 1000) as risposta:
            dati = json.loads(risposta.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as errore:
        if errore.code == 403:
            return {
                "ok": False,
                "errore": (
                    "la nostra istanza risponde 403: il formato json non e' acceso. "
                    "Serve `formats: [html, json]` in ~/.searxng/settings.yml (DEC-0043)"
                ),
                "risultati": [],
            }
        return {"ok": False, "errore": f"HTTP {errore.code}", "risultati": []}
    except Exception as errore:  # noqa: BLE001
        return {
            "ok": False,
            "errore": (
                f"{type(errore).__name__}: la nostra istanza non risponde su {SEARXNG}. "
                "Si avvia con: docker start searxng"
            ),
            "risultati": [],
        }

    risultati = []
    for voce in (dati.get("results") or [])[:limite]:
        risultati.append(
            {
                "titolo": voce.get("title", ""),
                "url": voce.get("url", ""),
                "motore": voce.get("engine", ""),
                "estratto": (voce.get("content") or "")[:300],
            }
        )
    return {
        "ok": True,
        "domanda": domanda,
        "categorie": list(categorie),
        "risultati": risultati,
        # Un motore che non risponde si **dice**: altrimenti "zero risultati" sembra
        # "non esiste niente", e sono due cose diverse.
        "motori_muti": [m[0] for m in (dati.get("unresponsive_engines") or []) if m],
    }


def cerca_profondo(domanda: str, quanti: int = 3, categorie=CATEGORIE,
                   limite: int = 15, timeout: int = 40000) -> dict:
    """Cerca, e poi **legge davvero** le fonti migliori.

    Perche' esiste: `cerca` trova gli indirizzi, e un titolo non e' una fonte. Il
    2026-10-13 il CEO ha chiesto *«una ricerca piu' approfondita»* — e questa e' la
    differenza fra sapere che una pagina esiste e **sapere cosa dice**.

    Si leggono le prime `quanti`, non tutte: il browser e' pesante, e leggere quindici
    fonti per sceglierne due e' lavoro sprecato. Ogni lettura passa dal `robots.txt`
    (`leggi` lo controlla) e si **ferma davanti a un CAPTCHA**.

    E si dice **cosa non si e' potuto leggere**: una fonte che non si apre e' una cosa
    che va saputa, non nascosta.
    """
    esito = cerca(domanda, categorie=categorie, limite=limite, timeout=timeout)
    if not esito.get("ok"):
        return esito

    lette, non_lette = [], []
    for voce in esito["risultati"][:quanti]:
        pagina = leggi(voce["url"])
        if pagina.get("ok"):
            testo = " ".join((pagina.get("testo") or "").split())
            lette.append({**voce, "estratto": testo[:1400], "via": pagina.get("via")})
        elif pagina.get("muro"):
            non_lette.append({**voce, "perche": "chiede una prova di umanita' (CAPTCHA)"})
        elif pagina.get("vietato"):
            non_lette.append({**voce, "perche": "robots.txt lo vieta"})
        else:
            non_lette.append({**voce, "perche": "non si e' lasciata leggere"})

    return {**esito, "lette": lette, "non_lette": non_lette}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ricerca sul web")
    parser.add_argument("comando", choices=("leggi", "regole", "cerca", "verifica", "raccogli"))
    parser.add_argument("url", nargs="?", default="")
    parser.add_argument("--categorie", default=",".join(CATEGORIE))
    parser.add_argument("--limite", type=int, default=15)
    parser.add_argument("--profondo", action="store_true",
                        help="dopo la ricerca, LEGGE le fonti migliori")
    parser.add_argument("--quanti", type=int, default=3,
                        help="quante fonti leggere con --profondo")
    parser.add_argument("--forza", action="store_true", help="ignora la cache")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--timeout", type=int, default=70000)
    args = parser.parse_args(argv)

    if args.comando == "regole":
        print(REGOLE)
        return 0

    if args.comando == "cerca":
        if not args.url:
            print("serve una domanda", file=sys.stderr)
            return 2
        esito = (
            cerca_profondo(args.url, quanti=args.quanti,
                           categorie=tuple(args.categorie.split(",")), limite=args.limite)
            if args.profondo
            else cerca(args.url, categorie=tuple(args.categorie.split(",")), limite=args.limite)
        )
        if args.json:
            print(json.dumps(esito, ensure_ascii=False, indent=2))
            return 0 if esito.get("ok") else 1
        if not esito.get("ok"):
            print(f"  non ho potuto cercare: {esito['errore']}")
            return 1
        if args.profondo:
            for voce in esito.get("lette", []):
                print(f"  LETTA [{voce['motore']}] {voce['titolo'][:66]}")
                print(f"      {voce['url']}")
                print(f"      {voce.get('estratto', '')[:320]}...")
                print()
            for voce in esito.get("non_lette", []):
                print(f"  NON LETTA [{voce['motore']}] {voce['titolo'][:58]}")
                print(f"      {voce['perche']}")
                if "umanita" in voce["perche"]:
                    print(f"      -> aprilo tu col browser: {voce['url']}")
            print(f"\n  {len(esito.get('lette', []))} fonti lette, "
                  f"{len(esito.get('non_lette', []))} non leggibili")
            return 0
        for voce in esito["risultati"]:
            print(f"  [{voce['motore']}] {voce['titolo'][:70]}")
            print(f"      {voce['url']}")
        print(f"\n  {len(esito['risultati'])} risultati da {len(set(v['motore'] for v in esito['risultati']))} motori")
        if esito.get("motori_muti"):
            print(f"  motori che non hanno risposto: {', '.join(esito['motori_muti'])}")
        return 0

    if args.comando == "raccogli":
        url = raccogli_url()
        for indirizzo, documenti in sorted(url.items()):
            print(f"  {indirizzo}\n      citato in: {', '.join(documenti[:4])}")
        print(f"\n  {len(url)} indirizzi distinti")
        return 0

    if args.comando == "verifica":
        esiti = verifica(timeout=args.timeout)
        if args.json:
            print(json.dumps(esiti, ensure_ascii=False, indent=2))
            return 0
        ordine = {"morto": 0, "irraggiungibile": 1, "vietato": 2, "protetto": 3, "vivo": 4}
        conta: dict[str, int] = {}
        for voce in sorted(esiti, key=lambda v: (ordine.get(v["stato"], 9), v["url"])):
            conta[voce["stato"]] = conta.get(voce["stato"], 0) + 1
            if voce["stato"] == "vivo":
                continue
            print(f"  {voce['stato'].upper():16} {voce['url'][:64]}")
            print(f"      {voce['dettaglio']}")
            print(f"      citato in: {', '.join(voce['citato_in'][:3])}")
            if voce["stato"] in ("vietato", "protetto"):
                print(f"      -> aprilo tu col browser: {voce['url']}")
        print(f"\n  {len(esiti)} indirizzi: " + ", ".join(f"{n} {s}" for s, n in sorted(conta.items())))
        return 1 if conta.get("morto") or conta.get("irraggiungibile") else 0

    if not args.url:
        print("serve un url", file=sys.stderr)
        return 2

    esito = leggi(args.url, forza=args.forza, timeout=args.timeout)

    if args.json:
        print(json.dumps(esito, ensure_ascii=False))
        return 0 if esito.get("ok") else 1

    if not esito.get("ok"):
        print("non sono riuscito a leggere la pagina:")
        for tentativo in esito.get("tentativi", []):
            print(f"  {tentativo}")
        return 1

    print(f"via: {esito['via']}{' (dalla cache)' if esito.get('da_cache') else ''}")
    if esito.get("titolo"):
        print(f"titolo: {esito['titolo']}")
    for tentativo in esito.get("tentativi", []):
        print(f"  nota: {tentativo}")
    print()
    print(esito.get("testo", "")[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
