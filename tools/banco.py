#!/usr/bin/env python3
"""Il banco — la shell di un progetto, riscritta attorno a due portieri (DEC-0091).

Perche' e' riscritto, e non rattoppato. La versione precedente (ENG-017) e' stata
respinta **sei volte**, sempre per difetti della stessa famiglia: un ingresso o
un'uscita che il codice presumeva innocuo (NUL, surrogati, JSON annidato, file non
UTF-8, pid enorme, collegamento circolare, `try` troppo corti). Venti punti che
leggevano o scrivevano, ognuno con il suo `try/except` scritto a mano: chiuderli uno
per uno produceva la respinta successiva.

Qui il disegno e' l'opposto, e sta in tre regole:

  1. Ogni ingresso passa dal `Portiere`. Testo, percorso, corpo HTTP, file JSON, YAML,
     pid, url: chi riceve un valore sa che e' gia' valido.
  2. Ogni uscita passa dall'`Uscita`. Una sola funzione serializza una risposta
     (sanificando cio' che l'UTF-8 non sa codificare) e una sola scrive un file.
  3. Ogni comando ha un solo punto di errore. Le sei modalita' passano da `main`, che
     traduce ogni eccezione prevista in un messaggio e in un codice d'uscita. Non
     esiste un ramo nudo: era il difetto per cui `--servizio` andava in traceback
     mentre il primo piano spiegava.

Uso:
    python3 tools/banco.py "<progetto>"             # sito + editor, in primo piano
    python3 tools/banco.py "<progetto>" --apri      # e apre il browser
    python3 tools/banco.py "<progetto>" --servizio  # in background, con lo stato
    python3 tools/banco.py "<progetto>" --stato
    python3 tools/banco.py "<progetto>" --chiudi
    python3 tools/banco.py "<progetto>" --inizia    # crea contenuti.yaml di esempio
    python3 tools/banco.py --aiuto

Esito: 0 tutto a posto · 1 il sito o l'editor non sono partiti ·
2 dichiarazione mancante o non valida (e allora non si avvia niente).
"""

from __future__ import annotations

import argparse
import errno
import html
import json
import os
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import yaml

#: Il file di questo modulo, risolto una volta sola all'import: le costanti non sono
#: ingressi, e risolverle a ogni uso sarebbe una `resolve()` sparsa nel codice.
_FILE = Path(__file__).resolve()  # noqa: architettura - costante di modulo, non ingresso
RADICE = _FILE.parents[1]
CARTELLA_EDITOR = _FILE.parent / "banco"
NOME_DICHIARAZIONE = "contenuti.yaml"

PORTA_EDITOR = 4320
TENTATIVI_PORTA = 20

LIMITE_CORPO = 32 * 1024
LIMITE_TESTO = 5000
LIMITE_RIGHE = 20
LIMITE_RIGA = 500
LIMITE_ISTRUZIONE = 2000
#: Quanto si legge di un log per dire una causa: l'ultima parte e' quella che conta.
LIMITE_LOG = 256 * 1024

ATTESA_SITO = 30.0
ATTESA_STATO = 40.0

TIPI = ("testo", "elenco", "foto")
ESTENSIONI_FOTO = (".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif")
CARTELLE_IMMAGINI = ("public", "src", "assets", "static", "images", "immagini", "img")
LIMITE_IMMAGINI = 300
CARTELLA_RICHIESTE = ("Analisi-Prompt-Report", "Richieste")
CARTELLA_STATO = ".banco"

CHIAVI = ("file", "avvio", "url", "campi")
_ASSENTE = object()

#: Su Linux un singolo componente di percorso non puo' superare questo.
NAME_MAX = 255


class ErroreConfig(Exception):
    """La dichiarazione non va bene: si spiega, e non si avvia niente (esito 2)."""


class ErroreAvvio(Exception):
    """Il sito o l'editor non sono partiti (esito 1)."""


class ErroreRifiuto(Exception):
    """Un ingresso rifiutato, con lo stato HTTP e un messaggio comprensibile."""

    def __init__(self, stato: int, messaggio: str) -> None:
        super().__init__(messaggio)
        self.stato = stato
        self.messaggio = messaggio



# --------------------------------------------------------------------------- #
# IL PORTIERE — ogni ingresso passa di qui                                     #
# --------------------------------------------------------------------------- #


def _testo_sicuro(testo: object) -> str:
    """Il testo codificabile in UTF-8: i surrogati diventano ``U+FFFD``."""
    if not isinstance(testo, str):
        testo = str(testo)
    return testo.encode("utf-8", "replace").decode("utf-8")


def _senza_controlli(testo: str, *, ammessi: str = "") -> str | None:
    """Il motivo per cui il testo non e' valido, oppure ``None``."""
    for carattere in testo:
        codice = ord(carattere)
        if codice < 32 and carattere not in ammessi:
            return "contiene un carattere di controllo"
        if 0xD800 <= codice <= 0xDFFF:
            return "contiene un carattere non valido"
    return None


class Portiere:
    """Valida ogni ingresso. Chi riceve un valore da qui sa che e' gia' valido."""

    @staticmethod
    def testo(valore: object, *, massimo: int, dove: str) -> str:
        if not isinstance(valore, str):
            raise ErroreRifiuto(422, f"{dove}: serve un testo.")
        if len(valore) > massimo:
            raise ErroreRifiuto(422, f"{dove}: supera i {massimo} caratteri.")
        problema = _senza_controlli(valore, ammessi="\n\t")
        if problema:
            raise ErroreRifiuto(422, f"{dove}: {problema}.")
        return valore

    @staticmethod
    def righe(valore: object, *, dove: str) -> list[str]:
        if not isinstance(valore, list):
            raise ErroreRifiuto(422, f"{dove}: serve un elenco di righe.")
        if not valore:
            raise ErroreRifiuto(422, f"{dove}: serve almeno una riga.")
        if len(valore) > LIMITE_RIGHE:
            raise ErroreRifiuto(422, f"{dove}: massimo {LIMITE_RIGHE} righe.")
        for riga in valore:
            if not isinstance(riga, str):
                raise ErroreRifiuto(422, f"{dove}: ogni riga deve essere testo.")
            if not riga.strip():
                raise ErroreRifiuto(422, f"{dove}: una delle righe e' vuota.")
            if len(riga) > LIMITE_RIGA:
                raise ErroreRifiuto(422, f"{dove}: una riga supera i {LIMITE_RIGA} caratteri.")
            problema = _senza_controlli(riga, ammessi="\t")
            if problema:
                raise ErroreRifiuto(422, f"{dove}: una riga {problema}.")
        return list(valore)

    @staticmethod
    def percorso_foto(progetto: Path, valore: object) -> str:
        """Il percorso di un'immagine dentro il progetto, o un rifiuto."""
        if not isinstance(valore, str):
            raise ErroreRifiuto(422, "Per questo campo serve il percorso di un'immagine.")
        testo = valore.strip()
        if not testo:
            raise ErroreRifiuto(422, "Serve il percorso di un'immagine (per esempio «/immagini/team.jpg»).")
        if len(testo) > 400:
            raise ErroreRifiuto(422, "Il percorso e' troppo lungo.")
        problema = _senza_controlli(testo)
        if problema:
            raise ErroreRifiuto(422, f"Il percorso {problema}: non e' un nome di file.")
        if "://" in testo:
            raise ErroreRifiuto(422, "Serve un percorso interno al progetto, non un indirizzo web.")
        if "\\" in testo:
            raise ErroreRifiuto(422, "Usa le barre normali «/» nel percorso.")
        if testo.startswith("~"):
            raise ErroreRifiuto(422, "Serve un percorso relativo al progetto, non la tua cartella personale.")
        parti = [pezzo for pezzo in testo.split("/") if pezzo]
        if not parti:
            raise ErroreRifiuto(422, "Serve il percorso di un file.")
        if any(pezzo == ".." for pezzo in parti):
            raise ErroreRifiuto(422, "Il percorso non puo' uscire dalla cartella del progetto («..»).")
        if any(len(pezzo.encode("utf-8")) > NAME_MAX for pezzo in parti):
            raise ErroreRifiuto(422, "Un pezzo del percorso e' troppo lungo per questo filesystem.")
        relativo = Path(*parti)
        if relativo.suffix.lower() not in ESTENSIONI_FOTO:
            raise ErroreRifiuto(
                422,
                "Estensione non ammessa: servono "
                + ", ".join(ESTENSIONI_FOTO)
                + " (un SVG no: puo' contenere codice).",
            )
        abituali = ("home", "tmp", "etc", "usr", "var", "opt", "root", "mnt", "media")
        candidato = progetto / relativo
        if testo.startswith("/") and parti[0] in abituali and not candidato.exists():
            raise ErroreRifiuto(
                422,
                "Serve un percorso interno al progetto: quello sembra un percorso del "
                "computer. Metti l'immagine dentro il progetto e usa il suo percorso.",
            )
        if not _dentro(progetto, candidato):
            raise ErroreRifiuto(422, "Il percorso non puo' uscire dalla cartella del progetto.")
        if not candidato.is_file():
            raise ErroreRifiuto(422, f"Nel progetto non c'e' nessun file «{testo}».")
        return testo

    @staticmethod
    def corpo_json(corpo: bytes) -> dict:
        """Il corpo come oggetto JSON, o un rifiuto.

        `json.loads` solleva tre cose diverse: `UnicodeDecodeError`, `JSONDecodeError`
        e `RecursionError` (che non e' un `JSONDecodeError`). Qui, una volta sola.
        """
        try:
            letto = json.loads(corpo.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
            raise ErroreRifiuto(400, "Il contenuto inviato non e' JSON valido.") from None
        if not isinstance(letto, dict):
            raise ErroreRifiuto(400, "Il contenuto inviato deve essere un oggetto JSON.")
        return letto

    @staticmethod
    def file_json(percorso: Path, *, dove: str) -> object:
        """Il contenuto di un file JSON, o un rifiuto con la ragione."""
        try:
            grezzo = percorso.read_text(encoding="utf-8")
        except UnicodeDecodeError as errore:
            raise ErroreRifiuto(
                500, f"{dove} non e' testo UTF-8 (byte {errore.start}): salvalo in UTF-8."
            ) from None
        except OSError as errore:
            raise ErroreRifiuto(500, f"{dove} non si legge: {errore}") from None
        try:
            return json.loads(grezzo)
        except RecursionError:
            raise ErroreRifiuto(500, f"{dove} e' annidato troppo in profondita' per essere letto.") from None
        except json.JSONDecodeError as errore:
            raise ErroreRifiuto(
                500,
                f"{dove} non e' JSON valido (riga {errore.lineno}, colonna {errore.colno}): "
                "correggilo a mano e ricarica.",
            ) from None

    @staticmethod
    def leggi_testo_utf8(percorso: Path) -> str:
        """Il testo di un file UTF-8, o un rifiuto. Nessun traceback, mai."""
        try:
            return percorso.read_text(encoding="utf-8")
        except UnicodeDecodeError as errore:
            raise ErroreRifiuto(
                500, f"non e' testo UTF-8 (byte {errore.start}): salvalo in UTF-8"
            ) from None
        except OSError as errore:
            raise ErroreRifiuto(500, f"non si legge: {errore}") from None

    @staticmethod
    def leggi_bytes(percorso: Path) -> bytes:
        """I byte di un file, o un rifiuto. Nessun traceback su un file mancante."""
        try:
            return percorso.read_bytes()
        except (OSError, ValueError) as errore:
            raise ErroreRifiuto(500, f"{percorso} non si legge: {errore}") from None

    @staticmethod
    def leggi_testo(percorso: Path) -> str:
        """Il testo di un file, o un rifiuto con la ragione.

        E' un ingresso come gli altri: il log del servizio puo' essere enorme, assente,
        una cartella o non UTF-8, e nessuno di quei casi deve diventare un traceback.
        """
        try:
            grezzo = percorso.read_bytes()
        except OSError as errore:
            raise ErroreRifiuto(500, f"{percorso} non si legge: {errore}") from None
        if len(grezzo) > LIMITE_LOG:
            grezzo = grezzo[-LIMITE_LOG:]
        return grezzo.decode("utf-8", "replace")

    @staticmethod
    def yaml_dichiarazione(percorso: Path, testo: str) -> dict:
        try:
            letto = yaml.safe_load(testo)
        except yaml.YAMLError as errore:
            raise ErroreConfig(f"«{percorso}» non e' YAML valido: {errore}") from None
        except RecursionError:
            raise ErroreConfig(f"«{percorso}» e' annidato troppo in profondita'") from None
        if letto is None:
            raise ErroreConfig(f"«{percorso}» e' vuoto. Forma minima:\n" + _esempio_dichiarazione())
        if not isinstance(letto, dict):
            raise ErroreConfig(f"«{percorso}» deve contenere una mappatura YAML")
        return letto

    @staticmethod
    def url_locale(valore: str) -> frozenset[str]:
        try:
            parti = urlsplit(valore)
            porta = parti.port
        except (ValueError, UnicodeError) as errore:
            raise ErroreConfig(f"«url» non e' un indirizzo valido: {errore}") from None
        if parti.scheme not in ("http", "https"):
            raise ErroreConfig("«url» deve cominciare con http:// o https://")
        if parti.username or parti.password:
            raise ErroreConfig("«url» non deve contenere un nome utente o una password")
        host = (parti.hostname or "").lower()
        if host not in ("127.0.0.1", "localhost"):
            raise ErroreConfig(
                f"«url» punta a «{host}»: il banco e' solo locale, e accetta 127.0.0.1 o localhost"
            )
        finale = f":{porta}" if porta is not None else ""
        return frozenset(
            {f"{parti.scheme}://127.0.0.1{finale}", f"{parti.scheme}://localhost{finale}"}
        )

    @staticmethod
    def pid(valore: object) -> int | None:
        """Un pid plausibile, oppure ``None``.

        Oltre il `long` di C `os.kill` e `os.getpgid` sollevano `OverflowError`: si
        controlla prima, e un pid che non puo' esistere non e' un processo vivo.
        """
        if not isinstance(valore, int) or isinstance(valore, bool):
            return None
        if valore <= 1 or valore > 2**31 - 1:
            return None
        return valore

    @staticmethod
    def risolvi(percorso: Path) -> Path:
        """Il percorso risolto, o il percorso com'e' se non si puo' risolvere.

        `resolve()` solleva `ValueError` su un NUL e `RuntimeError` su un collegamento
        circolare. E' l'unico posto in cui lo si chiama: cosi' i due casi si trattano
        una volta, non in ogni funzione che ha bisogno di un percorso assoluto.
        """
        try:
            return percorso.resolve()
        except (OSError, ValueError, RuntimeError):
            return percorso

    @staticmethod
    def cartella_esistente(valore: str | Path, *, base: Path) -> Path | None:
        """La cartella risolta, se esiste; ``None`` altrimenti — senza mai sollevare."""
        try:
            percorso = Path(valore).expanduser()
            if not percorso.is_absolute():
                percorso = base / percorso
            if not percorso.is_dir():
                return None
            return Portiere.risolvi(percorso)
        except (OSError, ValueError, RuntimeError):
            return None

    @staticmethod
    def percorso_http(grezzo: str) -> str:
        """Il percorso di una richiesta HTTP, senza mai sollevare.

        `urlsplit` solleva `ValueError` su una riga con IPv6 malformato (`GET http://[`).
        Una riga storta e' un 404, non una caduta.
        """
        try:
            return urlsplit(grezzo).path or "/"
        except (ValueError, UnicodeError):
            return "/"


class Processi:
    """Le operazioni sui processi: avviare, sapere se vivo, fermare.

    Terzo portiere, accanto a `Portiere` (ingressi) e `Uscita` (uscite). Le sei
    respinte di ENG-017 sono nate anche qui: un pid enorme (`OverflowError`), un
    processo estraneo ucciso, un `Popen` che solleva su un NUL. Chi chiama non tocca
    piu' `os.kill` o `subprocess` direttamente: chiede a questo.
    """

    @staticmethod
    def vivo(pid: object) -> bool:
        """Il processo esiste? `os.kill(pid, 0)` non manda niente e non uccide."""
        valido = Portiere.pid(pid)
        if valido is None:
            return False
        try:
            os.kill(valido, 0)
        except (ProcessLookupError, OverflowError):
            return False
        except PermissionError:
            return True
        except OSError:
            return False
        return True

    @staticmethod
    def avvia(comando: list[str], *, cartella: Path, log: Path | None = None) -> subprocess.Popen:
        """Avvia un comando in una sessione sua. Un solo posto per `Popen`."""
        try:
            if log is None:
                return subprocess.Popen(list(comando), cwd=str(cartella), start_new_session=True)
            with Uscita.apri_log(log) as uscita:
                return subprocess.Popen(
                    list(comando),
                    cwd=str(cartella),
                    stdin=subprocess.DEVNULL,
                    stdout=uscita,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
        except FileNotFoundError as errore:
            raise ErroreAvvio(
                f"il comando di avvio non esiste: «{comando[0]}». Controlla che il "
                "programma sia installato."
            ) from errore
        except (OSError, ValueError) as errore:
            raise ErroreAvvio(f"il comando non e' partito: {errore}") from errore

    @staticmethod
    def ferma(figlio: subprocess.Popen | None, *, gruppo: bool = True) -> None:
        """Ferma un figlio e i suoi figli. Mai un'eccezione: si chiama in chiusura."""
        if figlio is None or figlio.poll() is not None:
            return
        for segnale in (signal.SIGTERM, signal.SIGKILL):
            try:
                if gruppo:
                    os.killpg(os.getpgid(figlio.pid), segnale)
                else:
                    os.kill(figlio.pid, segnale)
            except (ProcessLookupError, PermissionError, OverflowError, OSError):
                return
            try:
                figlio.wait(timeout=3)
                return
            except subprocess.TimeoutExpired:
                continue

    @staticmethod
    def ferma_gruppo(pid: int) -> tuple[bool, str]:
        """Manda SIGTERM al gruppo di ``pid`` e aspetta che sparisca."""
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OverflowError, OSError) as errore:
            return False, f"Non sono riuscito a fermare il processo: {errore}"
        for _ in range(40):
            if not Processi.vivo(pid):
                return True, ""
            time.sleep(0.25)
        return False, "Il processo non si e' fermato entro 10 secondi."


def _dentro(progetto: Path, candidato: Path) -> bool:
    """Il percorso risolto sta dentro il progetto?

    `resolve()` solleva `ValueError` su un NUL e `RuntimeError` su un collegamento
    circolare: entrambi sono «non sta dentro», non un'eccezione da aprire.
    """
    risolto = Portiere.risolvi(candidato)
    radice = Portiere.risolvi(progetto)
    return risolto == radice or radice in risolto.parents


# --------------------------------------------------------------------------- #
# L'USCITA — ogni uscita passa di qui                                          #
# --------------------------------------------------------------------------- #


class Uscita:
    """Serializza risposte e scrive file. Nessun altro punto lo fa."""

    @staticmethod
    def corpo(oggetto: object) -> bytes:
        """Il corpo di una risposta, codificabile sempre."""
        if isinstance(oggetto, (bytes, bytearray)):
            return bytes(oggetto)
        if isinstance(oggetto, str):
            return _testo_sicuro(oggetto).encode("utf-8")
        try:
            testo = json.dumps(oggetto, ensure_ascii=False)
        except (RecursionError, ValueError):
            return b'{"errore": "la risposta e\' troppo complessa per essere inviata"}'
        return _testo_sicuro(testo).encode("utf-8")

    @staticmethod
    def apri_log(percorso: Path):
        """Il log del servizio aperto in aggiunta. Un solo posto per questo `open`."""
        try:
            return open(percorso, "ab")
        except OSError as errore:
            raise ErroreAvvio(f"non posso scrivere il log {percorso}: {errore}") from None

    @staticmethod
    def _testo(percorso: Path) -> str:
        """Il testo di un file, per l'Uscita. Il mestiere e' del Portiere."""
        return Portiere.leggi_testo_utf8(percorso)

    @staticmethod
    def json_breve(dati: object) -> str:
        """Un JSON piccolo serializzato, o un rifiuto. Per il possesso e lo stato."""
        try:
            return json.dumps(dati, ensure_ascii=False)
        except (RecursionError, ValueError):
            raise ErroreRifiuto(422, "il valore e' troppo complesso per essere scritto") from None

    @classmethod
    def scrivi_json(cls, percorso: Path, dati: object, *, rientro: str | None = None) -> int:
        """Serializza e scrive un JSON. L'encoder Python si ferma prima del decoder C:
        un file leggibile puo' non essere riscrivibile, e allora si rifiuta."""
        try:
            testo = json.dumps(dati, ensure_ascii=False, indent=rientro or "  ") + "\n"
        except RecursionError:
            raise ErroreRifiuto(
                422,
                "Il contenuto e' annidato troppo in profondita' per essere scritto in "
                "sicurezza: non e' stato toccato niente.",
            ) from None
        return cls.scrivi_file(percorso, testo)

    @classmethod
    def riscrivi_json(cls, percorso: Path, dati: object) -> int:
        """Riscrive un JSON conservando la sua indentazione."""
        rientro = "  "
        try:
            grezzo = cls._testo(percorso)
            if grezzo.startswith("{\n"):
                prima = grezzo.split("\n", 1)[1]
                rientro = prima[: len(prima) - len(prima.lstrip())] or "  "
        except ErroreRifiuto:
            pass
        return cls.scrivi_json(percorso, dati, rientro=rientro)

    @staticmethod
    def scrivi_file(percorso: Path, testo: str) -> int:
        """Scrive un file in modo atomico. Restituisce i byte scritti."""
        testo = _testo_sicuro(testo)
        try:
            percorso.parent.mkdir(parents=True, exist_ok=True)
        except (OSError, ValueError) as errore:
            raise ErroreRifiuto(500, f"Non posso creare {percorso.parent}: {errore}") from None
        if not percorso.parent.is_dir():
            raise ErroreRifiuto(500, f"{percorso.parent} esiste ma non e' una cartella.")
        try:
            modo = stat.S_IMODE(percorso.stat().st_mode)
        except OSError:
            modo = 0o644
        try:
            descrittore, temporaneo = tempfile.mkstemp(
                dir=str(percorso.parent), prefix=f".{percorso.name}.", suffix=".tmp"
            )
        except OSError as errore:
            raise ErroreRifiuto(500, f"Non posso scrivere in {percorso.parent}: {errore}") from None
        try:
            with os.fdopen(descrittore, "w", encoding="utf-8", newline="\n") as uscita:
                uscita.write(testo)
                uscita.flush()
                os.fsync(uscita.fileno())
            os.chmod(temporaneo, modo)
            os.replace(temporaneo, percorso)
        except BaseException:
            Path(temporaneo).unlink(missing_ok=True)
            raise
        return len(testo.encode("utf-8"))


@dataclass(frozen=True)
class Campo:
    """Un testo modificabile: il percorso nel JSON, l'etichetta, il tipo."""

    percorso: str
    etichetta: str
    tipo: str


@dataclass(frozen=True)
class Banco:
    """Tutto cio' che il banco ha bisogno di sapere, gia' validato."""

    progetto: Path
    dichiarazione: Path
    file: Path
    file_relativo: str
    avvio: tuple[str, ...]
    url: str
    origini: frozenset[str]
    campi: dict[str, Campo]
    lock: threading.Lock = field(default_factory=threading.Lock, compare=False)


def _esempio_dichiarazione() -> str:
    return (
        "  file: src/content/scritte/sito.json\n"
        "  avvio: npm run dev\n"
        "  url: http://127.0.0.1:4321\n"
        "  campi:\n"
        '    home.eroe.titoloRiga1: { etichetta: "Titolo — prima riga", tipo: testo }\n'
    )


def _messaggio_mancante(progetto: Path) -> str:
    return (
        f'manca «{NOME_DICHIARAZIONE}» in {progetto}.\n'
        "  Il banco ha bisogno della dichiarazione dei testi. Per crearne una di partenza:\n"
        f'    python3 tools/banco.py "{progetto}" --inizia\n'
        "  Poi controlla «file», «avvio» e «url». Forma minima:\n" + _esempio_dichiarazione()
    )


def leggi_dichiarazione(testo: str) -> dict[str, object]:
    """La dichiarazione grezza. Non valida i campi: quello lo fa `_valida`."""
    return Portiere.yaml_dichiarazione(Path(NOME_DICHIARAZIONE), testo)


def _valida_campo(percorso: str, proprieta: object) -> Campo:
    if not percorso:
        raise ErroreConfig("un campo ha il percorso vuoto")
    if any(not pezzo for pezzo in percorso.split(".")):
        raise ErroreConfig(f"il campo «{percorso}» ha un punto doppio o inizia/finisce con un punto")
    problema = _senza_controlli(percorso)
    if problema:
        raise ErroreConfig(f"il campo «{percorso}» {problema}")
    if not isinstance(proprieta, dict):
        raise ErroreConfig(f"il campo «{percorso}» deve essere una mappa con «etichetta» e «tipo»")
    estranei = sorted(set(proprieta) - {"etichetta", "tipo"})
    if estranei:
        raise ErroreConfig(
            f"il campo «{percorso}» ha proprieta' sconosciute: {', '.join(estranei)}; "
            "ammesse: etichetta, tipo"
        )
    tipo = str(proprieta.get("tipo") or "testo").strip().lower()
    if tipo not in TIPI:
        raise ErroreConfig(f"il campo «{percorso}» ha tipo «{tipo}»; ammessi: {', '.join(TIPI)}")
    etichetta = str(proprieta.get("etichetta") or percorso).strip()
    if not etichetta:
        raise ErroreConfig(f"il campo «{percorso}» ha l'etichetta vuota")
    return Campo(percorso=percorso, etichetta=etichetta, tipo=tipo)


def leggi_percorso(dati: object, percorso: str) -> object:
    """Il valore a quel percorso in un albero JSON, o ``_ASSENTE``."""
    nodo = dati
    for chiave in percorso.split("."):
        if not isinstance(nodo, dict) or chiave not in nodo:
            return _ASSENTE
        nodo = nodo[chiave]
    return nodo


def _scrivi_percorso(dati: dict, percorso: str, valore: object) -> None:
    chiavi = percorso.split(".")
    nodo: object = dati
    for chiave in chiavi[:-1]:
        if not isinstance(nodo, dict):
            raise ErroreRifiuto(409, f"Il percorso «{percorso}» non esiste piu' nel file dei contenuti.")
        prossimo = nodo.get(chiave)
        if not isinstance(prossimo, dict):
            raise ErroreRifiuto(409, f"Il percorso «{percorso}» non esiste piu' nel file dei contenuti.")
        nodo = prossimo
    if not isinstance(nodo, dict):
        raise ErroreRifiuto(409, f"Il percorso «{percorso}» non esiste piu' nel file dei contenuti.")
    nodo[chiavi[-1]] = valore


def _valida(dati: dict, progetto: Path, dichiarazione: Path) -> Banco:
    """Trasforma la dichiarazione letta in una configurazione utilizzabile."""
    # Una chiave che non conosciamo e' un refuso, e un refuso silenzioso e' un campo
    # che «non funziona» senza dire perche'. Si rifiuta prima delle chiavi mancanti:
    # chi ha scritto «avvioo» deve sapere che il problema e' il nome, non altro.
    estranee = sorted(set(dati) - set(CHIAVI))
    if estranee:
        raise ErroreConfig(
            f"{dichiarazione}: chiave sconosciuta {', '.join(estranee)}. "
            f"Le chiavi ammesse sono: {', '.join(CHIAVI)}"
        )
    mancanti = [chiave for chiave in CHIAVI if chiave not in dati]
    if mancanti:
        raise ErroreConfig(
            f"{dichiarazione}: mancano {', '.join(mancanti)}. Forma minima:\n"
            + _esempio_dichiarazione()
            + f'\nPer crearne una di partenza: python3 tools/banco.py "{progetto}" --inizia\n'
        )
    for chiave in ("file", "avvio", "url"):
        if dati[chiave] is None:
            raise ErroreConfig(f"{dichiarazione}: «{chiave}» manca il valore")
        if not isinstance(dati[chiave], str) or not str(dati[chiave]).strip():
            raise ErroreConfig(f"{dichiarazione}: «{chiave}» deve essere un testo non vuoto")

    relativo = Path(str(dati["file"]).strip())
    if relativo.is_absolute() or any(pezzo == ".." for pezzo in relativo.parts):
        raise ErroreConfig(
            f"«file» deve essere un percorso senza «..» e senza radice, dentro il progetto: {relativo}"
        )
    if any(len(pezzo.encode("utf-8")) > NAME_MAX for pezzo in relativo.parts):
        raise ErroreConfig(f"«file» ha un pezzo di percorso troppo lungo: {relativo}")
    file_contenuti = progetto / relativo
    # Il controllo su `..` e sulla radice guarda il percorso **scritto**, non quello che
    # il filesystem risolve: un collegamento simbolico dentro il progetto puo' puntare
    # fuori, e il testo resta innocente. Per le foto `_dentro` c'era, per il file dei
    # contenuti no — e cosi' `GET /api/contenuti` serviva un file esterno con 200
    # (finding P2 del gate di ENG-020, riprodotto: la lettura usciva, la scrittura no).
    if not _dentro(progetto, file_contenuti):
        raise ErroreConfig(
            f"«file» punta fuori dal progetto: {file_contenuti}\n"
            "  Il percorso scritto sta dentro, ma il collegamento che trova porta altrove. "
            "Il file dei contenuti deve essere un file vero dentro il progetto, non un "
            "collegamento a un file esterno."
        )
    if not file_contenuti.is_file():
        raise ErroreConfig(f"il file dei contenuti non esiste: {file_contenuti}")

    avvio = tuple(str(dati["avvio"]).strip().split())
    if not avvio:
        raise ErroreConfig("«avvio» non contiene un comando")
    for pezzo in avvio:
        problema = _senza_controlli(pezzo)
        if problema:
            raise ErroreConfig(f"«avvio» {problema}: non e' un comando valido")

    url = str(dati["url"]).strip()
    origini = Portiere.url_locale(url)

    campi_dichiarati = dati.get("campi")
    if not isinstance(campi_dichiarati, dict) or not campi_dichiarati:
        raise ErroreConfig(f"{dichiarazione}: «campi» deve essere una mappa non vuota")
    campi = {percorso: _valida_campo(percorso, prop) for percorso, prop in campi_dichiarati.items()}

    try:
        contenuti = Portiere.file_json(file_contenuti, dove="Il file dei contenuti")
    except ErroreRifiuto as rifiuto:
        # All'avvio e' una configurazione sbagliata (esito 2), non un avvio fallito:
        # il file dei contenuti si legge una volta, e se non va non si parte.
        raise ErroreConfig(rifiuto.messaggio) from None
    if not isinstance(contenuti, dict):
        raise ErroreConfig("il file dei contenuti deve contenere un oggetto JSON")
    for percorso, campo in campi.items():
        valore = leggi_percorso(contenuti, percorso)
        if valore is _ASSENTE:
            raise ErroreConfig(
                f"il campo «{percorso}» e' dichiarato in {NOME_DICHIARAZIONE} ma non "
                f"esiste in {relativo.as_posix()}"
            )
        if campo.tipo == "testo" and not isinstance(valore, str):
            raise ErroreConfig(f"il campo «{percorso}» e' dichiarato «testo» ma non e' un testo")
        if campo.tipo == "elenco" and not isinstance(valore, list):
            raise ErroreConfig(f"il campo «{percorso}» e' dichiarato «elenco» ma non e' un elenco")
        if campo.tipo == "foto":
            if not isinstance(valore, str):
                raise ErroreConfig(f"il campo «{percorso}» e' dichiarato «foto» ma non e' un percorso")
            if valore.strip():
                try:
                    Portiere.percorso_foto(progetto, valore)
                except ErroreRifiuto as rifiuto:
                    raise ErroreConfig(f"il campo «{percorso}»: {rifiuto.messaggio}") from None

    return Banco(
        progetto=progetto,
        dichiarazione=dichiarazione,
        file=file_contenuti,
        file_relativo=relativo.as_posix(),
        avvio=avvio,
        url=url,
        origini=origini,
        campi=campi,
    )


def _risolvi_progetto(progetto: str | Path) -> Path:
    """La cartella del progetto, senza mai sollevare su un percorso storto."""
    percorso = Path(progetto).expanduser()
    return Portiere.risolvi(percorso if percorso.is_absolute() else RADICE / percorso)


def carica(progetto: str | Path) -> Banco:
    """Legge e valida la dichiarazione di un progetto. Non avvia niente.

    Limite di fiducia dichiarato: «avvio» e' un comando del progetto e viene eseguito
    cosi' com'e', senza sandbox. Il file `contenuti.yaml` e' codice fidato del progetto.
    """
    cartella = _risolvi_progetto(progetto)
    if not cartella.is_dir():
        raise ErroreConfig(f"il progetto non esiste: {cartella}")
    dichiarazione = cartella / NOME_DICHIARAZIONE
    if not dichiarazione.is_file():
        raise ErroreConfig(_messaggio_mancante(cartella))
    try:
        testo = Portiere.leggi_testo_utf8(dichiarazione)
    except ErroreRifiuto as rifiuto:
        raise ErroreConfig(f"«{dichiarazione}»: {rifiuto.messaggio}") from None
    return _valida(Portiere.yaml_dichiarazione(dichiarazione, testo), cartella, dichiarazione)


def valida_foto(progetto: Path, valore: object) -> str | None:
    """Compatibilita': il messaggio d'errore, oppure ``None``."""
    try:
        Portiere.percorso_foto(progetto, valore)
    except ErroreRifiuto as rifiuto:
        return rifiuto.messaggio
    return None


def elenca_immagini(progetto: Path) -> list[str]:
    """Le immagini gia' presenti nel progetto, come percorsi relativi con «/»."""
    trovate: list[str] = []
    for nome in CARTELLE_IMMAGINI:
        radice = progetto / nome
        if not radice.is_dir():
            continue
        try:
            candidati = sorted(radice.rglob("*"))
        except (OSError, RuntimeError):
            continue
        for percorso in candidati:
            if len(trovate) >= LIMITE_IMMAGINI:
                return trovate
            if percorso.suffix.lower() not in ESTENSIONI_FOTO:
                continue
            try:
                if not percorso.is_file() or not _dentro(progetto, percorso):
                    continue
                relativo = percorso.relative_to(progetto).as_posix()
            except (OSError, ValueError, RuntimeError):
                continue
            if relativo.startswith("node_modules/") or "/node_modules/" in relativo:
                continue
            trovate.append("/" + relativo)
    return sorted(set(trovate))[:LIMITE_IMMAGINI]


def _valore_del_campo(campo: Campo, valore: object, progetto: Path | None) -> object:
    """Il valore validato per il campo, o un rifiuto."""
    if campo.tipo == "testo":
        return Portiere.testo(valore, massimo=LIMITE_TESTO, dove="Il testo")
    if campo.tipo == "foto":
        if progetto is None:
            if not isinstance(valore, str):
                raise ErroreRifiuto(422, "Per questo campo serve un percorso.")
            return valore
        return Portiere.percorso_foto(progetto, valore)
    return Portiere.righe(valore, dove="L'elenco")


def scrivi_valore(banco: Banco, percorso: str, valore: object) -> int:
    """Scrive un solo valore, in modo atomico. Restituisce i byte scritti."""
    with banco.lock:
        dati = Portiere.file_json(banco.file, dove="Il file dei contenuti")
        if not isinstance(dati, dict):
            raise ErroreRifiuto(500, "Il file dei contenuti non contiene un oggetto JSON.")
        if leggi_percorso(dati, percorso) is _ASSENTE:
            raise ErroreRifiuto(409, f"Il percorso «{percorso}» non esiste nel file dei contenuti.")
        _scrivi_percorso(dati, percorso, valore)
        return Uscita.riscrivi_json(banco.file, dati)


def registra_richiesta(banco: Banco, percorso: str, istruzione: str, foto: list[str]) -> Path:
    """Scrive la richiesta di modifica come file. Non tocca il contenuto."""
    istruzione = Portiere.testo(istruzione, massimo=LIMITE_ISTRUZIONE, dove="L'istruzione")
    if not istruzione.strip():
        # Uno spazio non e' un'istruzione: si controlla DOPO la validazione del testo,
        # ma sul valore ripulito. Il `.strip()` prima nascondeva il vuoto.
        raise ErroreRifiuto(422, "Serve l'istruzione: cosa vuoi cambiare.")
    istruzione = istruzione.strip()
    riferimenti = [Portiere.percorso_foto(banco.progetto, voce) for voce in foto]
    with banco.lock:
        try:
            contenuti = Portiere.file_json(banco.file, dove="Il file dei contenuti")
        except ErroreRifiuto:
            contenuti = {}
        valore = leggi_percorso(contenuti, percorso) if isinstance(contenuti, dict) else _ASSENTE
        campo = banco.campi.get(percorso)
        cartella = banco.progetto.joinpath(*CARTELLA_RICHIESTE)
        istante = time.strftime("%Y%m%d-%H%M%S")
        destinazione = cartella / f"RIC-{istante}.json"
        contatore = 2
        while destinazione.exists():
            destinazione = cartella / f"RIC-{istante}-{contatore}.json"
            contatore += 1
        richiesta = {
            "percorso": percorso,
            "etichetta": campo.etichetta if campo else percorso,
            "tipo": campo.tipo if campo else "testo",
            "valore_attuale": None if valore is _ASSENTE else valore,
            "istruzione": istruzione,
            "foto": riferimenti,
            "file": banco.file_relativo,
            "progetto": banco.progetto.name,
            "momento": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "stato": "in attesa",
        }
        Uscita.scrivi_json(destinazione, richiesta)
    return destinazione


# --------------------------------------------------------------------------- #
# Lo stato del servizio                                                        #
# --------------------------------------------------------------------------- #


def _percorso_stato(banco: Banco) -> Path:
    return banco.progetto.joinpath(CARTELLA_STATO, "stato.json")


def leggi_stato(progetto: Path) -> dict[str, object] | None:
    """Lo stato salvato, oppure ``None``. Uno stato illeggibile non e' un banco acceso."""
    percorso = progetto.joinpath(CARTELLA_STATO, "stato.json")
    try:
        dato = Portiere.file_json(percorso, dove="lo stato del banco")
    except ErroreRifiuto:
        return None
    return dato if isinstance(dato, dict) else None


def _processo_vivo(pid: object) -> bool:
    """Compatibilita': il processo esiste? (il mestiere e' di `Processi.vivo`)."""
    return Processi.vivo(pid)


def stato_vivo(progetto: Path) -> dict[str, object] | None:
    """Lo stato, ma solo se il processo che lo ha scritto e' ancora vivo."""
    dati = leggi_stato(progetto)
    if dati is None:
        return None
    return dati if _processo_vivo(dati.get("pid")) else None


def _prendi_possesso(banco: Banco) -> None:
    """Registra che il servizio e' nostro, in modo atomico. Rifiuta se c'e' un altro.

    Il controllo «lo stato c'e' gia'» seguito da una scrittura lascia una finestra: due
    processi possono guardare insieme, trovare il vuoto e scrivere entrambi. Qui il
    possesso e' un file creato con ``O_CREAT|O_EXCL``: il filesystem decide chi vince, e
    il secondo non prova nemmeno. Se il possesso e' di un processo morto, si prende.
    """
    cartella = banco.progetto / CARTELLA_STATO
    if not cartella.exists():
        try:
            cartella.mkdir(parents=True)
        except (OSError, ValueError) as errore:
            raise ErroreAvvio(f"non posso creare {cartella}: {errore}") from None
    if not cartella.is_dir():
        raise ErroreAvvio(
            f"{cartella} esiste ma non e' una cartella: toglila e riprova."
        )
    possesso = cartella / "possesso"
    for _ in range(3):
        try:
            descrittore = os.open(possesso, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            # C'e' gia' un possesso: se e' di un processo morto si toglie e si riprova.
            try:
                dato = Portiere.file_json(possesso, dove="il possesso del banco")
                altro = Portiere.pid(dato.get("pid")) if isinstance(dato, dict) else None
                vivo = altro is not None and Processi.vivo(altro)
                if vivo and altro != os.getpid():
                    raise ErroreAvvio(
                        "un altro banco e' gia' acceso su questo progetto: non prendo il "
                        "suo posto. Fermalo con --chiudi, oppure usa quello."
                    )
                possesso.unlink(missing_ok=True)
            except ErroreRifiuto:
                possesso.unlink(missing_ok=True)
            continue
        except (OSError, ValueError) as errore:
            raise ErroreAvvio(f"non posso prendere il possesso dello stato: {errore}") from None
        try:
            with os.fdopen(descrittore, "w", encoding="utf-8", newline="\n") as uscita:
                uscita.write(Uscita.json_breve({"pid": os.getpid()}) + "\n")
                uscita.flush()
                os.fsync(uscita.fileno())
        except OSError:
            pass
        return
    raise ErroreAvvio(
        "non riesco a prendere il possesso dello stato: un altro processo lo tiene. "
        "Riprova fra un istante."
    )


def scrivi_stato(banco: Banco, porta: int, *, solo_se_libero: bool = False) -> Path:
    """Scrive lo stato in modo atomico. La cartella `.banco/` si auto-ignora.

    Con ``solo_se_libero`` la scrittura e' un **possesso**: se lo stato esiste gia' ed e'
    di un processo vivo e diverso dal nostro, si rifiuta. Senza questo, un `--servizio`
    che perde la corsa si scriveva sopra lo stato del vincente e poi lo cancellava —
    e `--chiudi` dichiarava «nessun banco acceso» mentre l'editor era ancora su e
    scriveva nel progetto. (Trovato dal gate di ENG-020, R3, da entrambi i revisori.)
    """
    percorso = _percorso_stato(banco)
    if solo_se_libero:
        _prendi_possesso(banco)
    if not percorso.parent.exists():
        try:
            percorso.parent.mkdir(parents=True)
        except (OSError, ValueError) as errore:
            raise ErroreAvvio(
                f"non posso creare la cartella dello stato {percorso.parent}: {errore}. "
                "Se e' un file, toglilo: il banco ha bisogno di una cartella."
            ) from None
    if not percorso.parent.is_dir():
        raise ErroreAvvio(
            f"{percorso.parent} esiste ma non e' una cartella: il banco ha bisogno di "
            "una cartella per lo stato. Toglila (o rinominala) e riprova."
        )
    auto_ignora = percorso.parent / ".gitignore"
    if not auto_ignora.exists():
        Uscita.scrivi_file(
            auto_ignora,
            "# Cartella dello strumento «banco»: stato e log del servizio, non del progetto.\n*\n",
        )
    dati = {
        "pid": os.getpid(),
        "porta": porta,
        "editor": f"http://127.0.0.1:{porta}/",
        "sito": banco.url,
        "progetto": banco.progetto.name,
        "progetto_path": str(banco.progetto),
        "file": banco.file_relativo,
        "avvio": list(banco.avvio),
        "campo_foto": sorted(c.percorso for c in banco.campi.values() if c.tipo == "foto"),
        "avviato_il": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    Uscita.scrivi_json(percorso, dati)
    return percorso


def cancella_stato(banco: Banco) -> None:
    """Toglie lo stato **se e' nostro**, e la cartella se resta vuota.

    Il confronto col pid e' il punto, non un dettaglio: due `--servizio` ravvicinati
    producono due processi, e il perdente che esce cancellava lo stato del vincente.
    Il risultato era che `--chiudi` diceva «nessun banco acceso» mentre l'editor
    restava su e accettava salvataggi: il comando con cui si accende la shell,
    premuto due volte, perdeva il controllo della shell. (Trovato dal gate di ENG-020,
    R2, ed era vero: riprodotto 3 volte su 3.)
    """
    percorso = _percorso_stato(banco)
    try:
        dati = Portiere.file_json(percorso, dove="lo stato del banco")
    except ErroreRifiuto:
        return
    if not isinstance(dati, dict):
        return
    if Portiere.pid(dati.get("pid")) != os.getpid():
        # Lo stato e' di un altro processo: non e' il nostro da cancellare.
        return
    try:
        percorso.unlink(missing_ok=True)
        possesso = banco.progetto / CARTELLA_STATO / "possesso"
        try:
            dato = Portiere.file_json(possesso, dove="il possesso del banco")
            if isinstance(dato, dict) and Portiere.pid(dato.get("pid")) == os.getpid():
                possesso.unlink(missing_ok=True)
        except ErroreRifiuto:
            possesso.unlink(missing_ok=True)
        (banco.progetto / CARTELLA_STATO).rmdir()
    except (OSError, ValueError):
        pass


def _e_il_nostro_banco(pid: int, progetto: Path) -> bool:
    """Il processo ``pid`` e' un `banco.py` avviato su questo progetto?

    Si legge la riga di comando da /proc. Se non si puo' leggere si risponde di no:
    non fermare e' meno dannoso che uccidere il processo sbagliato.
    """
    try:
        grezza = Portiere.leggi_bytes(Path(f"/proc/{pid}/cmdline"))
    except ErroreRifiuto:
        return False
    parti = [pezzo.decode("utf-8", "replace") for pezzo in grezza.split(b"\0") if pezzo]
    if not parti or not any(Path(pezzo).name in ("banco.py", "banco") for pezzo in parti[1:3]):
        return False
    atteso = _risolvi_progetto(progetto)
    for pezzo in parti[1:]:
        risolto = Portiere.cartella_esistente(pezzo, base=RADICE) or Portiere.cartella_esistente(
            pezzo, base=Path.cwd()
        )
        if risolto is not None and risolto == atteso:
            return True
        if _dentro(atteso, Path(pezzo)) and Path(pezzo).exists():
            return True
    return Path(atteso.name) in (Path(pezzo) for pezzo in parti)


def servizio_attivo(progetto: Path) -> dict[str, object] | None:
    """Lo stato, ma solo se il processo e' DAVVERO il banco di questo progetto.

    `stato_vivo` controlla che il pid esista; questo controlla anche che sia il nostro.
    Un file di stato che nomina un processo altrui non e' un servizio da riusare ne' da
    fermare (difetto trovato dalla revisione di R6: `--servizio` rispondeva «gia' acceso»
    guardando solo il pid, e `ad_shell_apri` riceveva un indirizzo morto).
    """
    dati = stato_vivo(progetto)
    if dati is None:
        return None
    pid = Portiere.pid(dati.get("pid"))
    if pid is None or not _e_il_nostro_banco(pid, progetto):
        return None
    return dati


def banchi_del_progetto(progetto: Path) -> list[int]:
    """Tutti i processi `banco.py` di QUESTO progetto, non solo quello nello stato.

    Il criterio dice che `--chiudi` ferma il banco e libera le porte. Fidarsi del solo
    pid nello stato non basta: quando il comando di avvio non copre la porta (un dev
    server con `strictPort: false` si sposta alla successiva), possono restare **due**
    banchi vivi; lo stato ne nomina uno, e l'altro resta acceso con il suo editor che
    scrive nel progetto. Trovato dal QA di ENG-020 (5 giri su 5), ed era vero.
    """
    trovati: list[int] = []
    try:
        voci = list(Path("/proc").iterdir())
    except OSError:
        return trovati
    for voce in voci:
        if not voce.name.isdigit():
            continue
        pid = Portiere.pid(int(voce.name))
        if pid is None or pid == os.getpid():
            continue
        if _e_il_nostro_banco(pid, progetto):
            trovati.append(pid)
    return trovati


def ferma_dal_file(progetto: Path) -> tuple[bool, str]:
    """Ferma **tutti** i banchi di questo progetto. ``(fermato, messaggio)``.

    Si parte dai processi **veri**, non dallo stato, per due ragioni distinte e vere:

    1. Un banco acceso **senza** stato esiste: `--apri` non lo scrive. Leggendo lo stato
       come prima istruzione si usciva senza scansionare, e il risultato era un vicolo
       cieco — `--chiudi` diceva «nessun banco acceso», `--servizio` diceva «gia' acceso,
       fermalo con --chiudi», e l'editor restava su accettando salvataggi nel progetto.
    2. Lo stato puo' essere **vecchio o sovrascritto**: il pid che nomina puo' non essere
       piu' il banco. Inseguirlo significherebbe aspettare dieci secondi un processo che
       non esiste.

    Quindi: prima si guarda cosa e' vivo; se non c'e' niente, si ripulisce lo stato; se
    c'e', si ferma cosa e' vivo e si verifica che **adesso** non resti nessuno.
    (Il primo difetto l'ha trovato il QA di ENG-020 in R4; il secondo il Code Review.)
    """
    veri = banchi_del_progetto(progetto)

    if not veri:
        dati = leggi_stato(progetto)
        if dati is None:
            return False, "Nessun banco risulta avviato su questo progetto."
        try:
            progetto.joinpath(CARTELLA_STATO, "stato.json").unlink(missing_ok=True)
        except OSError:
            pass
        return False, "Il banco non era piu' in esecuzione: ho tolto lo stato vecchio."

    # Un processo vivo ma che non e' il banco di QUESTO progetto non si tocca. La
    # scansione lo esclude gia'; il controllo resta come seconda barriera, perche' e'
    # quello che le vittime esterne hanno verificato.
    estranei = [pid for pid in veri if not _e_il_nostro_banco(pid, progetto)]
    if estranei and len(estranei) == len(veri):
        return False, (
            "Lo stato nomina un processo che non e' il banco di questo progetto: "
            "non lo fermo. Togli lo stato a mano se e' rimasto un residuo."
        )
    bersagli = [pid for pid in veri if pid not in estranei]
    for bersaglio in bersagli:
        Processi.ferma_gruppo(bersaglio)

    # La verifica che conta non e' «il kill e' tornato»: e' che adesso non ci sia piu'
    # nessun banco di questo progetto. Un pid puo' morire mentre lo aspettavamo.
    restanti = banchi_del_progetto(progetto)
    if restanti:
        return False, (
            f"Ho fermato il banco ma sono rimasti accesi {len(restanti)} processi "
            f"({', '.join(str(p) for p in restanti)}): fermali a mano."
        )
    try:
        progetto.joinpath(CARTELLA_STATO, "stato.json").unlink(missing_ok=True)
        (progetto / CARTELLA_STATO / "possesso").unlink(missing_ok=True)
    except OSError:
        pass
    if len(bersagli) > 1:
        return True, (
            f"Banco fermato: erano accesi {len(bersagli)} processi (uno aveva perso lo "
            "stato), ora sono spenti tutti e le porte sono libere."
        )
    return True, "Banco fermato: sito ed editor sono spenti, le porte libere."


def apri_nel_browser(url: str) -> bool:
    """Apre l'URL nel browser di sistema. ``False`` se non riesce."""
    try:
        import webbrowser

        return bool(webbrowser.open(url, new=2, autoraise=True))
    except Exception:  # pragma: no cover - dipende dall'ambiente desktop
        return False


# --------------------------------------------------------------------------- #
# La pagina che si apre sul server                                              #
# --------------------------------------------------------------------------- #


def _pagina(banco: Banco, porta: int) -> str:
    """La pagina di atterraggio: cosa fare, in due righe."""
    campi = "".join(
        f"<li><code>{html.escape(campo.percorso)}</code>"
        f"<span>{html.escape(campo.etichetta)} · {html.escape(campo.tipo)}</span></li>"
        for campo in banco.campi.values()
    )
    frammento = f'<script src="http://127.0.0.1:{porta}/editor.js" defer></script>'
    return f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Il banco — {html.escape(banco.progetto.name)}</title>
<style>
  :root {{ color-scheme: light; }}
  body {{ margin: 0; padding: 40px 24px; background: #f7f6f2; color: #1a2332;
         font: 400 15px/1.55 ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }}
  main {{ max-width: 760px; margin: 0 auto; }}
  h1 {{ margin: 0 0 4px; font-size: 22px; letter-spacing: -0.01em; }}
  p.lead {{ margin: 0 0 24px; color: #5c6572; }}
  section {{ padding: 18px 20px; margin: 0 0 14px; border: 1px solid rgba(26, 35, 50, 0.12);
             border-radius: 6px; background: #fdfcf8; }}
  h2 {{ margin: 0 0 8px; font-size: 13px; letter-spacing: 0.06em; text-transform: uppercase;
        color: #5c6572; }}
  a {{ color: #a8321f; }}
  code, pre {{ font: 400 13px/1.5 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
  pre {{ overflow-x: auto; padding: 10px 12px; border-radius: 4px; background: rgba(26, 35, 50, 0.06); }}
  ul {{ margin: 8px 0 0; padding: 0; list-style: none; }}
  li {{ display: flex; gap: 10px; justify-content: space-between; padding: 5px 0;
        border-top: 1px solid rgba(26, 35, 50, 0.07); }}
  li span {{ color: #5c6572; font-size: 13px; text-align: right; }}
</style>
</head>
<body>
<main>
  <h1>Il banco e' acceso</h1>
  <p class="lead">Solo su questa macchina. Il sito resta quello del progetto: l'editor e'
  un livello in piu', che in produzione non esiste.</p>
  <section>
    <h2>Il sito</h2>
    <p><a href="{html.escape(banco.url)}">{html.escape(banco.url)}</a></p>
    <p>Nel layout del progetto, <strong>solo in sviluppo</strong>, serve una riga:</p>
    <pre>{html.escape(frammento)}</pre>
    <p>Poi apri il sito: in basso a destra compare «Modifica in pagina». Clic su un
    testo, scrivi, Invio. Esc annulla.</p>
  </section>
  <section>
    <h2>I testi</h2>
    <p><code>{html.escape(banco.file_relativo)}</code> — {len(banco.campi)} campi dichiarati.</p>
    <ul>{campi}</ul>
  </section>
  <section>
    <h2>Se qualcosa non va</h2>
    <p>Il salvataggio risponde solo al sito qui sopra, ascolta solo su
    <code>127.0.0.1</code>, e scrive solo i percorsi di
    <code>{html.escape(NOME_DICHIARAZIONE)}</code>. Ctrl+C nel terminale ferma sito e banco
    insieme.</p>
    <p><a href="/editor.js">editor.js</a> · <a href="/editor.css">editor.css</a> ·
    <a href="/api/stato">/api/stato</a></p>
  </section>
</main>
</body>
</html>
"""


class GestoreBanco(BaseHTTPRequestHandler):
    """Le rotte del banco. Ogni risposta parla JSON, anche gli errori."""

    server_version = "Banco/2.0"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    @property
    def banco(self) -> Banco:
        return self.server.banco  # type: ignore[attr-defined]

    def log_message(self, formato: str, *argomenti: object) -> None:
        """Il log di default e' rumore: si stampano gli eventi veri."""

    # -- utilita' ---------------------------------------------------------- #

    def _origine(self) -> tuple[str | None, bool]:
        """(origine consentita, se la richiesta ne porta una)."""
        grezza = self.headers.get("Origin")
        if grezza is None:
            return None, False
        if grezza in self.banco.origini:
            return grezza, True
        return None, True

    def _invia(
        self,
        stato: int,
        corpo: object,
        tipo: str = "application/json; charset=utf-8",
        origine: str | None = None,
        chiudi: bool = False,
    ) -> None:
        """Manda una risposta. Il corpo passa SEMPRE dall'`Uscita`."""
        dati = Uscita.corpo(corpo)
        self.send_response(stato)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(dati)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if origine:
            self.send_header("Access-Control-Allow-Origin", origine)
            self.send_header("Vary", "Origin")
        if chiudi:
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()
        self.wfile.write(dati)

    def _errore(
        self,
        stato: int,
        messaggio: str,
        origine: str | None = None,
        chiudi: bool = False,
    ) -> None:
        self._invia(stato, {"errore": messaggio}, origine=origine, chiudi=chiudi)

    def _leggi_corpo(self) -> bytes:
        if self.headers.get("Transfer-Encoding"):
            raise ErroreRifiuto(400, "Il banco accetta solo un corpo con Content-Length.")
        dichiarata = self.headers.get("Content-Length")
        if dichiarata is None:
            raise ErroreRifiuto(411, "Manca Content-Length: il banco non sa quanto leggere.")
        try:
            lunghezza = int(dichiarata)
        except ValueError:
            raise ErroreRifiuto(400, "Content-Length non e' un numero.") from None
        if lunghezza < 0:
            raise ErroreRifiuto(400, "Content-Length negativo.")
        if lunghezza > LIMITE_CORPO:
            self.close_connection = True
            raise ErroreRifiuto(
                413, f"Il contenuto inviato supera il limite di {LIMITE_CORPO // 1024} KB."
            )
        corpo = self.rfile.read(lunghezza)
        if len(corpo) != lunghezza:
            raise ErroreRifiuto(400, "Il corpo della richiesta e' incompleto.")
        return corpo

    # -- GET --------------------------------------------------------------- #

    def do_GET(self) -> None:  # noqa: N802 - il nome lo impone http.server
        percorso = Portiere.percorso_http(self.path)
        origine, presente = self._origine()
        if presente and origine is None:
            self._errore(403, "Origine non consentita: il banco risponde solo al sito dichiarato.")
            return
        if percorso in ("/editor.js", "/editor.css"):
            nome = percorso[1:]
            tipo = "text/javascript; charset=utf-8" if nome.endswith(".js") else "text/css; charset=utf-8"
            try:
                contenuto = Portiere.leggi_bytes(CARTELLA_EDITOR / nome)
            except ErroreRifiuto:
                self._errore(500, f"Manca il file dell'editor: tools/banco/{nome}", origine)
                return
            self._invia(200, contenuto, tipo, origine)
            return
        if percorso == "/":
            self._invia(
                200,
                _pagina(self.banco, self.server.server_address[1]),  # type: ignore[attr-defined]
                "text/html; charset=utf-8",
                origine,
            )
            return
        if percorso == "/api/stato":
            self._invia(
                200,
                {
                    "ok": True,
                    "progetto": str(self.banco.progetto),
                    "file": self.banco.file_relativo,
                    "url": self.banco.url,
                    "editor": f"http://127.0.0.1:{self.server.server_address[1]}",  # type: ignore[attr-defined]
                    "campi": {
                        campo.percorso: {"etichetta": campo.etichetta, "tipo": campo.tipo}
                        for campo in self.banco.campi.values()
                    },
                },
                origine=origine,
            )
            return
        if percorso == "/api/contenuti":
            try:
                contenuti = Portiere.file_json(self.banco.file, dove="Il file dei contenuti")
            except ErroreRifiuto as rifiuto:
                self._errore(rifiuto.stato, rifiuto.messaggio, origine)
                return
            if not isinstance(contenuti, dict):
                self._errore(500, "Il file dei contenuti non contiene un oggetto JSON.", origine)
                return
            self._invia(200, contenuti, origine=origine)
            return
        if percorso == "/api/immagini":
            self._invia(
                200,
                {
                    "ok": True,
                    "progetto": self.banco.progetto.name,
                    "cartelle": list(CARTELLE_IMMAGINI),
                    "estensioni": list(ESTENSIONI_FOTO),
                    "immagini": elenca_immagini(self.banco.progetto),
                },
                origine=origine,
            )
            return
        self._errore(
            404,
            "Non trovato. Le rotte sono /, /editor.js, /editor.css, /api/stato, "
            "/api/contenuti, /api/immagini.",
        )

    def do_OPTIONS(self) -> None:  # noqa: N802
        origine, _ = self._origine()
        if origine is None:
            self._errore(403, "Origine non consentita.")
            return
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", origine)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Vary", "Origin")
        self.send_header("Content-Length", "0")
        self.end_headers()

    # -- POST -------------------------------------------------------------- #

    def do_POST(self) -> None:  # noqa: N802
        self.close_connection = True
        percorso = Portiere.percorso_http(self.path)
        origine, _ = self._origine()
        if origine is None:
            self._errore(
                403,
                "Origine non consentita: il salvataggio accetta solo il sito dichiarato "
                "in contenuti.yaml (Origin assente o «null» non bastano).",
                chiudi=True,
            )
            return
        if percorso not in ("/api/salva", "/api/richieste"):
            self._errore(
                404,
                "Non trovato: i percorsi di scrittura sono POST /api/salva e POST /api/richieste.",
                origine,
                chiudi=True,
            )
            return
        tipo = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if tipo != "application/json":
            self._errore(
                415, "Il contenuto deve essere JSON: manda Content-Type: application/json.",
                origine, chiudi=True,
            )
            return
        try:
            corpo = self._leggi_corpo()
            richiesta = Portiere.corpo_json(corpo)
        except ErroreRifiuto as rifiuto:
            self._errore(rifiuto.stato, rifiuto.messaggio, origine, chiudi=True)
            return
        if percorso == "/api/richieste":
            self._richiesta_modifica(richiesta, origine)
            return
        self._salvataggio(richiesta, origine)

    def _salvataggio(self, richiesta: dict, origine: str) -> None:
        if set(richiesta) - {"percorso", "valore"} or "percorso" not in richiesta or "valore" not in richiesta:
            self._errore(400, "Servono esattamente due campi: «percorso» e «valore».", origine, chiudi=True)
            return
        percorso = richiesta["percorso"]
        if not isinstance(percorso, str):
            self._errore(400, "«percorso» deve essere un testo.", origine, chiudi=True)
            return
        campo = self.banco.campi.get(percorso)
        if campo is None:
            self._errore(
                404,
                f"Il percorso «{percorso}» non e' fra i campi dichiarati in {NOME_DICHIARAZIONE}.",
                origine, chiudi=True,
            )
            return
        try:
            _valore_del_campo(campo, richiesta["valore"], self.banco.progetto)
            scritti = scrivi_valore(self.banco, campo.percorso, richiesta["valore"])
        except ErroreRifiuto as rifiuto:
            self._errore(rifiuto.stato, rifiuto.messaggio, origine, chiudi=True)
            return
        except OSError as errore:
            self._errore(
                500, f"Il salvataggio non e' riuscito e il file e' rimasto com'era: {errore}",
                origine, chiudi=True,
            )
            return
        print(f"  [banco] salvato: {campo.percorso} ({scritti} byte)")
        self._invia(
            200,
            {"ok": True, "percorso": campo.percorso, "file": self.banco.file_relativo, "byte": scritti},
            origine=origine,
            chiudi=True,
        )

    def _richiesta_modifica(self, richiesta: dict, origine: str) -> None:
        permessi = {"percorso", "istruzione", "foto"}
        if set(richiesta) - permessi or not {"percorso", "istruzione"} <= set(richiesta):
            self._errore(400, "Servono «percorso» e «istruzione» (e, se vuoi, «foto»).", origine, chiudi=True)
            return
        percorso = richiesta["percorso"]
        if not isinstance(percorso, str):
            self._errore(400, "«percorso» deve essere un testo.", origine, chiudi=True)
            return
        if percorso not in self.banco.campi:
            self._errore(
                404,
                f"Il percorso «{percorso}» non e' fra i campi dichiarati in {NOME_DICHIARAZIONE}.",
                origine, chiudi=True,
            )
            return
        istruzione = richiesta["istruzione"]
        if not isinstance(istruzione, str):
            self._errore(400, "«istruzione» deve essere un testo.", origine, chiudi=True)
            return
        foto = richiesta.get("foto", [])
        if not isinstance(foto, list) or not all(isinstance(voce, str) for voce in foto):
            self._errore(400, "«foto» deve essere un elenco di percorsi.", origine, chiudi=True)
            return
        try:
            destinazione = registra_richiesta(self.banco, percorso, istruzione, foto)
        except ErroreRifiuto as rifiuto:
            self._errore(rifiuto.stato, rifiuto.messaggio, origine, chiudi=True)
            return
        except OSError as errore:
            self._errore(500, f"La richiesta non e' stata registrata: {errore}", origine, chiudi=True)
            return
        relativo = destinazione.relative_to(self.banco.progetto).as_posix()
        print(f"  [banco] richiesta registrata: {relativo}")
        self._invia(
            201,
            {
                "ok": True,
                "richiesta": relativo,
                "percorso": percorso,
                "nota": "La richiesta e' un file: il contenuto non e' stato toccato. "
                "L'agente la legge e propone la modifica.",
            },
            origine=origine,
            chiudi=True,
        )


def crea_server(banco: Banco, porta: int = PORTA_EDITOR) -> ThreadingHTTPServer:
    """Il server dell'editor. Con ``porta=0`` ne sceglie una libera."""
    server = ThreadingHTTPServer(("127.0.0.1", porta), GestoreBanco)
    server.banco = banco  # type: ignore[attr-defined]
    server.daemon_threads = True
    return server


# --------------------------------------------------------------------------- #
# Avvio, attesa, fermata                                                       #
# --------------------------------------------------------------------------- #


def _avvia_sito(banco: Banco) -> subprocess.Popen[bytes]:
    """Avvia il comando del progetto, in una sessione sua.

    La sessione separata serve a fermare tutto con un segnale solo: npm lancia node,
    node il dev server, e fermare solo il primo lascerebbe la porta occupata. Niente
    ``shell=True``: la riga si divide in argomenti.
    """
    return Processi.avvia(list(banco.avvio), cartella=banco.progetto)


def _attendi_sito(url: str, figlio: subprocess.Popen[bytes]) -> None:
    """Aspetta che l'URL risponda. Un 404 va bene: vuol dire che il server c'e'."""
    scadenza = time.monotonic() + ATTESA_SITO
    print(f"  [banco] aspetto che il sito risponda su {url} …")
    while time.monotonic() < scadenza:
        codice = figlio.poll()
        if codice is not None:
            raise ErroreAvvio(
                f"il comando di avvio e' uscito (codice {codice}) prima che {url} "
                "rispondesse. L'errore vero e' qui sopra, nell'output del sito."
            )
        try:
            with urllib.request.urlopen(url, timeout=1.5):
                return
        except urllib.error.HTTPError:
            return
        except (urllib.error.URLError, OSError, ValueError):
            time.sleep(0.25)
    raise ErroreAvvio(
        f"il sito non ha risposto su {url} entro {int(ATTESA_SITO)} secondi. "
        "Controlla «avvio» e «url» in contenuti.yaml."
    )


def _apri_editor(banco: Banco) -> tuple[ThreadingHTTPServer, int]:
    """Il server dell'editor: 4320, o la prima porta libera da li' in poi."""
    ultimo: OSError | None = None
    for tentativo in range(TENTATIVI_PORTA):
        porta = PORTA_EDITOR + tentativo
        try:
            return crea_server(banco, porta), porta
        except OSError as errore:
            if errore.errno != errno.EADDRINUSE:
                raise ErroreAvvio(f"il server dell'editor non e' partito: {errore}") from errore
            ultimo = errore
    raise ErroreAvvio(
        f"nessuna porta libera fra {PORTA_EDITOR} e {PORTA_EDITOR + TENTATIVI_PORTA - 1}: "
        "chiudi un altro banco, o libera una porta."
    )


def _banner(banco: Banco, porta: int) -> None:
    riga = "─" * 66
    frammento = f'<script src="http://127.0.0.1:{porta}/editor.js" defer></script>'
    print()
    print(f"  {riga}")
    print("   Il banco — i testi si modificano dal browser, solo su questa macchina")
    print(f"   Sito:    {banco.url}")
    print(f"   Editor:  http://127.0.0.1:{porta}")
    print(f"   Testi:   {banco.file_relativo}  ({len(banco.campi)} campi)")
    print("   Nel layout del progetto, solo in sviluppo:")
    print(f"     {frammento}")
    print("   Ctrl+C ferma il sito e il banco insieme.")
    print(f"  {riga}")
    print()


def _installa_segnali() -> None:
    """Ctrl+C e SIGTERM passano dalla stessa fermata pulita."""

    def ferma(numero: int, frame: object) -> None:
        raise KeyboardInterrupt

    try:
        signal.signal(signal.SIGINT, ferma)
        signal.signal(signal.SIGTERM, ferma)
    except ValueError:  # pragma: no cover - non siamo nel thread principale
        pass


def avvia(banco: Banco, *, scrivi_lo_stato: bool = False, apri: bool = False) -> int:
    """Avvia sito ed editor, resta in ascolto, e ferma tutto prima di uscire."""
    _installa_segnali()
    print(f"banco: progetto {banco.progetto.name}")
    print(f"  [banco] avvio: {' '.join(banco.avvio)}")
    figlio = _avvia_sito(banco)
    server: ThreadingHTTPServer | None = None
    in_servizio = False
    esito = 0
    try:
        _attendi_sito(banco.url, figlio)
        server, porta = _apri_editor(banco)
        thread = threading.Thread(
            target=server.serve_forever, kwargs={"poll_interval": 0.2}, daemon=True
        )
        thread.start()
        in_servizio = True
        if scrivi_lo_stato:
            print(f"  [banco] stato:  {scrivi_stato(banco, porta, solo_se_libero=True)}")
        _banner(banco, porta)
        if apri:
            indirizzo = f"http://127.0.0.1:{porta}/"
            print(
                f"  [banco] apro {indirizzo}"
                if apri_nel_browser(indirizzo)
                else f"  [banco] apri tu: {indirizzo}"
            )
        try:
            while figlio.poll() is None:
                time.sleep(0.2)
            codice = figlio.returncode
            print(f"\n  [banco] il sito si e' fermato (codice {codice}): chiudo il banco.")
            esito = 0 if codice in (0, None) else 1
        except KeyboardInterrupt:
            print("\n  [banco] Ctrl+C: fermo il sito e il banco.")
    finally:
        if server is not None:
            if in_servizio:
                server.shutdown()
            server.server_close()
        Processi.ferma(figlio)
        if scrivi_lo_stato:
            cancella_stato(banco)
    return esito


def _processo_non_avviato(banco: Banco) -> int:
    """Il ramo `--servizio`: avvia staccato dal terminale e aspetta lo stato.

    Ogni errore e' tradotto qui: e' lo stesso punto in cui il primo piano lo fa.
    Era il difetto di R6, dove il ramo `--_servizio-interno` andava in traceback.
    """
    gia = servizio_attivo(banco.progetto)
    if gia is not None:
        print(f"  il banco e' gia' acceso: {gia.get('editor')}")
        return 0
    cartella = banco.progetto / CARTELLA_STATO
    if cartella.exists() and not cartella.is_dir():
        raise ErroreAvvio(
            f"{cartella} esiste ma non e' una cartella: il banco ha bisogno di una cartella "
            "per lo stato e i log. Toglila (o rinominala) e riprova."
        )
    try:
        cartella.mkdir(parents=True, exist_ok=True)
    except (OSError, ValueError) as errore:
        raise ErroreAvvio(f"non posso creare {cartella}: {errore}") from None
    log = cartella / "servizio.log"
    if log.exists() and not log.is_file():
        raise ErroreAvvio(
            f"{log} esiste ma non e' un file: toglilo, il banco ha bisogno di scrivere il log."
        )
    comando = [sys.executable, str(_FILE), str(banco.progetto), "--_servizio-interno"]
    figlio = Processi.avvia(comando, cartella=RADICE, log=log)
    scadenza = time.monotonic() + ATTESA_STATO
    while time.monotonic() < scadenza:
        dati = servizio_attivo(banco.progetto)
        if dati is not None:
            print(f"  banco acceso: {dati.get('editor')}")
            print(f"  sito:         {dati.get('sito')}")
            print(f"  log:          {log}")
            return 0
        if figlio.poll() is not None:
            # La causa si cerca nel log, saltando l'intestazione: la prima riga e'
            # «banco: progetto X», che non spiega niente. Si prende l'ultima riga che
            # dice *perche'*, e se non c'e' si dice che il log e' l'unico posto.
            messaggio = "il servizio e' uscito senza rispondere: guarda il log"
            try:
                coda = Portiere.leggi_testo(log).splitlines()[-20:]
            except ErroreRifiuto:
                coda = []
            # «non e'» e «non esiste» sono due modi diversi di dire la stessa cosa, e il
            # filtro ne conosceva uno solo: `FileNotFoundError` produce «non esiste», e la
            # causa restava nel log mentre il messaggio rimandava al log — che il criterio
            # vieta. Non si filtra per frase fatta: si cerca la riga che ha il prefisso
            # d'errore di `main` su qualunque messaggio, piu' le parole che indicano una
            # causa in chiaro.
            cause = [
                riga.strip()
                for riga in coda
                if riga.strip()
                and not riga.startswith("  [banco] avvio:")
                and not riga.strip().startswith("banco: progetto ")
                and (
                    riga.strip().startswith("banco:")
                    or "errore" in riga.lower()
                    or "non e'" in riga
                    or "non esiste" in riga
                    or "impossibile" in riga.lower()
                    or "Error" in riga
                    or "causa" in riga.lower()
                )
            ]
            if cause:
                # La riga del log porta gia' il prefisso «banco: » (l'ha scritta `main`
                # del processo interno): toglierlo evita il «banco: banco:» che il
                # criterio vieta, e che il QA di ENG-020 ha trovato due volte su due.
                messaggio = cause[-1]
                if messaggio.startswith("banco: "):
                    messaggio = messaggio[len("banco: ") :]
            raise ErroreAvvio(f"{messaggio} (log: {log})")
        time.sleep(0.3)
    raise ErroreAvvio(
        f"il servizio non ha risposto entro {int(ATTESA_STATO)} secondi. Guarda il log: {log}"
    )


# --------------------------------------------------------------------------- #
# Comando                                                                      #
# --------------------------------------------------------------------------- #


_MODELLO_CONTENUTI = """# I contenuti modificabili di questo progetto, per il banco del motore.
# Si apre con: python3 tools/banco.py "{progetto}"
#
# `file`   il file dei contenuti (JSON) che l'editor riscrive
# `avvio`  il comando che accende il sito in locale
# `url`    dove il sito risponde
# `campi`  cosa si puo' modificare: percorso nel JSON -> etichetta e tipo
#
# I tipi sono: testo, elenco, foto.
# `foto` NON carica niente: e' il percorso di un'immagine che hai gia' messo nel
# progetto (per esempio /immagini/team.jpg). L'editor propone quelle che trova.
file: src/content/contenuti.json
avvio: npm run dev
url: http://127.0.0.1:4321
campi:
  home.titolo: {{ etichetta: "Titolo della home", tipo: testo }}
  home.paragrafi: {{ etichetta: "Paragrafi (uno per riga)", tipo: elenco }}
  # home.foto: {{ etichetta: "Foto principale", tipo: foto }}
"""


def _progetto_da_argomento(valore: str) -> Path:
    """La cartella del progetto: un percorso, o un nome fra i progetti del motore."""
    candidato = Portiere.cartella_esistente(valore, base=Path.cwd())
    if candidato is not None:
        return candidato
    per_nome = Portiere.cartella_esistente(valore, base=RADICE)
    if per_nome is not None:
        return per_nome
    raise ErroreConfig(f"il progetto «{valore}» non esiste (ne' come cartella, ne' nella radice)")


def _inizia(progetto: Path) -> int:
    """Crea `contenuti.yaml` di esempio. Non sovrascrive mai un file esistente."""
    destinazione = progetto / NOME_DICHIARAZIONE
    if destinazione.exists():
        print(f"  {destinazione} esiste gia': non lo sovrascrivo.")
        return 2
    testo = _MODELLO_CONTENUTI.format(progetto=progetto.name)
    try:
        Uscita.scrivi_file(destinazione, testo)
    except (ErroreRifiuto, OSError) as errore:
        messaggio = errore.messaggio if isinstance(errore, ErroreRifiuto) else str(errore)
        raise ErroreConfig(
            f"non posso scrivere in {progetto}: {messaggio}. "
            "Controlla i permessi della cartella del progetto."
        ) from None
    print(f"  {destinazione}")
    print("  Ora controlla «file», «avvio» e «url», poi apri la shell:")
    print(f'    python3 tools/banco.py "{progetto}" --apri')
    return 0


def _richieste(progetto: Path) -> int:
    """Le richieste in attesa: e' il ponte fra il pannello e la chat."""
    banco = carica(progetto)
    attese = richieste_in_attesa(banco)
    if not attese:
        print("  Nessuna richiesta in attesa.")
        return 0
    print(f"  {len(attese)} richieste in attesa:\n")
    for r in attese:
        print(f"  {r.get('file')}  ·  {r.get('momento')}")
        print(f"    campo: {r.get('etichetta') or r.get('percorso')}")
        print(f"    chiede: {r.get('istruzione')}")
        print()
    return 0


def _stato(progetto: Path) -> int:
    """Dice se il banco di questo progetto e' acceso."""
    dati = servizio_attivo(progetto)
    if dati is None:
        raise ErroreAvvio(f"nessun banco acceso per «{progetto.name}»")
    print(f"  progetto: {dati.get('progetto')}")
    print(f"  editor:   {dati.get('editor')}")
    print(f"  sito:     {dati.get('sito')}")
    print(f"  pid:      {dati.get('pid')}")
    print(f"  testi:    {dati.get('file')}")
    return 0


def _chiudi(progetto: Path) -> int:
    """Ferma il banco avviato con `--servizio`."""
    fermato, messaggio = ferma_dal_file(progetto)
    print(f"  {messaggio}")
    if fermato:
        return 0
    raise ErroreAvvio(messaggio)



def richieste_in_attesa(banco: Banco) -> list[dict[str, object]]:
    """Le richieste registrate e non ancora esaudite. Sola lettura.

    Perche' esiste: il pannello non puo' svegliare la sessione in cui si lavora — un server
    locale non parla con una chat. Ma puo' lasciare un segno che costa zero leggere, e
    `--richieste` lo mostra: cosi' chi torna in chat le vede subito, invece di scoprirle
    per caso.
    """
    cartella = banco.progetto.joinpath(*CARTELLA_RICHIESTE)
    fuori: list[dict[str, object]] = []
    if not cartella.is_dir():
        return fuori
    for percorso in sorted(cartella.glob("RIC-*.json")):
        try:
            dato = Portiere.file_json(percorso, dove="una richiesta")
        except ErroreRifiuto:
            continue
        if not isinstance(dato, dict):
            continue
        if str(dato.get("stato") or "") in ("esaudita", "rifiutata"):
            continue
        fuori.append(dato)
    return fuori

def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="banco.py",
        add_help=False,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Il banco: avvia il sito di un progetto in locale e serve l'editor che\n"
            "permette di cliccare i testi e salvarli nel file dei contenuti."
        ),
        epilog=(
            'Uso:\n    python3 tools/banco.py "<progetto>"\n'
            '    python3 tools/banco.py "<progetto>" --apri      # e apre il browser\n'
            '    python3 tools/banco.py "<progetto>" --servizio  # in background, con lo stato\n'
            '    python3 tools/banco.py "<progetto>" --stato     # risponde su che porta\n'
            '    python3 tools/banco.py "<progetto>" --chiudi    # ferma quello in background\n'
            '    python3 tools/banco.py "<progetto>" --inizia    # crea contenuti.yaml di esempio\n\n'
            "La dichiarazione sta in <progetto>/contenuti.yaml, e ha questa forma:\n\n"
            + _esempio_dichiarazione()
            + "\nI tipi di campo sono: testo, elenco, foto (la foto e' solo il percorso di "
            "un'immagine gia' presente nel progetto: il banco non carica file).\n"
            "Il banco ascolta solo su 127.0.0.1. Ctrl+C ferma sito ed editor.\n"
            "Esito: 0 tutto a posto · 1 il sito o l'editor non sono partiti ·\n"
            "2 contenuti.yaml mancante o non valido (e allora non si avvia niente)."
        ),
    )
    parser.add_argument("progetto", nargs="?", help='la cartella del progetto')
    parser.add_argument("--apri", action="store_true", help="dopo l'avvio apre l'editor nel browser")
    parser.add_argument("--servizio", action="store_true", help="avvia in background, con lo stato")
    parser.add_argument("--stato", action="store_true", help="dice se il banco e' acceso, e su che porta")
    parser.add_argument("--chiudi", action="store_true", help="ferma il banco avviato con --servizio")
    parser.add_argument("--inizia", action="store_true", help="crea contenuti.yaml di esempio, se manca")
    parser.add_argument(
        "--richieste", action="store_true", help="elenca le richieste di modifica ancora in attesa"
    )
    parser.add_argument("--_servizio-interno", dest="servizio_interno", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("-h", "--aiuto", "--help", action="help", help="mostra questo aiuto")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point. **Un solo punto** in cui ogni errore diventa un messaggio.

    Ogni modalita' passa di qui: non esiste un ramo «nudo» che possa andare in
    traceback mentre un altro spiega. Era il difetto di R6.
    """
    parser = _parser()
    argomenti = parser.parse_args(argv)
    if not argomenti.progetto:
        parser.print_usage(sys.stderr)
        print('banco: serve il progetto: python3 tools/banco.py "<progetto>" (oppure --aiuto)', file=sys.stderr)
        return 2
    try:
        if argomenti.inizia:
            return _inizia(_progetto_da_argomento(argomenti.progetto))
        if argomenti.richieste:
            return _richieste(_progetto_da_argomento(argomenti.progetto))
        if argomenti.stato:
            return _stato(_progetto_da_argomento(argomenti.progetto))
        if argomenti.chiudi:
            return _chiudi(_progetto_da_argomento(argomenti.progetto))
        banco = carica(argomenti.progetto)
        if argomenti.servizio_interno:
            return avvia(banco, scrivi_lo_stato=True)
        if argomenti.servizio:
            return _processo_non_avviato(banco)
        return avvia(banco, apri=argomenti.apri)
    except ErroreConfig as errore:
        print(f"banco: {errore}", file=sys.stderr)
        return 2
    except ErroreAvvio as errore:
        print(f"banco: {errore}", file=sys.stderr)
        return 1
    except ErroreRifiuto as errore:
        print(f"banco: {errore.messaggio}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0
    except Exception as errore:  # noqa: BLE001 - l'ultima rete: un messaggio, non un traceback
        print(f"banco: errore imprevisto ({type(errore).__name__}): {errore}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
