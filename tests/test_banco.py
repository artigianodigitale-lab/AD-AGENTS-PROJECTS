#!/usr/bin/env python3
"""I test del banco (ENG-016): la dichiarazione, il permesso, la scrittura.

    python3 tests/test_banco.py

Perche' esiste. Il banco e' l'unico strumento del motore che **scrive un file
dentro un progetto** mentre qualcuno lo usa dal browser: il posto dove un errore
non e' un messaggio sbagliato, e' un contenuto rovinato. Qui si prova che:

  - senza `contenuti.yaml`, o con uno non valido, non si avvia **niente** (esito 2);
  - il salvataggio accetta solo i percorsi dichiarati, solo l'`Origin` del sito,
    e solo un corpo piccolo;
  - un salvataggio rifiutato lascia il file **identico**, byte per byte, e non
    lascia file temporanei in giro;
  - il salvataggio buono scrive il valore, conserva il resto e i permessi, e
    tiene l'indentazione del file.

I test non avviano il sito di un progetto: quello lo prova il banco sul campo.
Qui si avvia solo il server dell'editor, su una porta libera scelta dal sistema.
"""

from __future__ import annotations

import http.client
import json
import os
import subprocess
import sys
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import banco  # noqa: E402

PASSED = 0

#: L'origine del sito di prova: e' l'unica che il salvataggio deve accettare.
ORIGINE = "http://127.0.0.1:4321"

DICHIARAZIONE = """file: dati/sito.json
avvio: python3 -m http.server 4321
url: http://127.0.0.1:4321
campi:
  home.eroe.titolo: { etichetta: "Titolo", tipo: testo }
  home.eroe.righe: { etichetta: "Righe", tipo: elenco }
"""

CONTENUTI = {
    "home": {"eroe": {"titolo": "Titolo attuale", "righe": ["prima", "seconda"]}},
    "altro": {"valore": "non toccare"},
}


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    """Assert one expectation."""
    global PASSED
    if not condizione:
        raise AssertionError(f"{etichetta}: {dettaglio or 'condizione falsa'}")
    PASSED += 1


def crea_progetto(
    radice: Path, dichiarazione: str | None = DICHIARAZIONE, contenuti: dict | None = None
) -> Path:
    """Un progetto finto con il suo `contenuti.yaml` e il suo file JSON."""
    progetto = radice / "12. Progetto Di Prova"
    (progetto / "dati").mkdir(parents=True)
    dati = CONTENUTI if contenuti is None else contenuti
    (progetto / "dati" / "sito.json").write_text(
        json.dumps(dati, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if dichiarazione is not None:
        (progetto / "contenuti.yaml").write_text(dichiarazione, encoding="utf-8")
    return progetto


def esegui(progetto: Path, *argomenti: str) -> subprocess.CompletedProcess[str]:
    """Esegue il comando vero, come lo lancerebbe una persona."""
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "banco.py"), str(progetto), *argomenti],
        capture_output=True,
        text=True,
        timeout=30,
    )


@contextmanager
def server_di(progetto: Path):
    """Avvia solo il server dell'editor, su una porta libera, e lo ferma dopo."""
    configurazione = banco.carica(progetto)
    server = banco.crea_server(configurazione, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield configurazione, server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def richiesta(
    porta: int,
    metodo: str,
    percorso: str,
    corpo: object | None = None,
    origine: str | None = ORIGINE,
    tipo: str | None = "application/json",
) -> tuple[int, object, dict]:
    """Una richiesta HTTP vera, e la risposta letta come JSON quando c'e'."""
    intestazioni: dict[str, str] = {}
    if origine is not None:
        intestazioni["Origin"] = origine
    dati: bytes | None = None
    if corpo is not None:
        dati = corpo if isinstance(corpo, bytes) else json.dumps(corpo).encode("utf-8")
        if tipo:
            intestazioni["Content-Type"] = tipo
        intestazioni["Content-Length"] = str(len(dati))
    connessione = http.client.HTTPConnection("127.0.0.1", porta, timeout=10)
    try:
        connessione.request(metodo, percorso, body=dati, headers=intestazioni)
        risposta = connessione.getresponse()
        grezzo = risposta.read()
        letto: object = {}
        if grezzo:
            try:
                letto = json.loads(grezzo)
            except (UnicodeDecodeError, json.JSONDecodeError):
                letto = grezzo.decode("utf-8", "replace")
        return risposta.status, letto, dict(risposta.getheaders())
    finally:
        connessione.close()


# --------------------------------------------------------------------------- #
# La dichiarazione                                                             #
# --------------------------------------------------------------------------- #


def test_dichiarazione_mancante() -> None:
    """Senza `contenuti.yaml` non parte niente: esito 2 e il messaggio lo dice."""
    with tempfile.TemporaryDirectory() as tmp:
        progetto = crea_progetto(Path(tmp), dichiarazione=None)
        esito = esegui(progetto)
        check("contenuti.yaml mancante: esito 2", esito.returncode == 2, str(esito.returncode))
        check(
            "il messaggio nomina contenuti.yaml e dice che manca",
            "contenuti.yaml" in esito.stderr and "manca" in esito.stderr,
            esito.stderr,
        )
        check(
            "il messaggio mostra la forma minima",
            "file:" in esito.stderr and "campi:" in esito.stderr,
            esito.stderr,
        )
        check(
            "nessun processo avviato",
            "avvio:" not in esito.stdout and "Editor:" not in esito.stdout,
            esito.stdout,
        )


def test_progetto_inesistente() -> None:
    """Un progetto che non c'e' e' un errore d'uso, non un avvio a vuoto."""
    with tempfile.TemporaryDirectory() as tmp:
        inesistente = Path(tmp) / "non-esiste"
        esito = esegui(inesistente)
        check("progetto inesistente: esito 2", esito.returncode == 2, str(esito.returncode))
        check("il messaggio dice che non esiste", "non esiste" in esito.stderr, esito.stderr)


def test_yaml_non_valido() -> None:
    """Ogni forma sbagliata si rifiuta con la riga e il motivo, prima di avviare."""
    casi = [
        (
            "chiave sconosciuta",
            DICHIARAZIONE.replace("avvio:", "avvioo:"),
            "chiave sconosciuta",
        ),
        (
            "manca il valore",
            "file:\navvio: x\nurl: http://127.0.0.1:4321\ncampi:\n  a.b: { tipo: testo }\n",
            "manca il valore",
        ),
        (
            "tipo sconosciuto",
            DICHIARAZIONE.replace("tipo: testo", "tipo: numero"),
            "tipo",
        ),
        (
            "url non locale",
            DICHIARAZIONE.replace("http://127.0.0.1:4321", "http://example.com"),
            "solo locale",
        ),
        (
            "file che esce dal progetto",
            DICHIARAZIONE.replace("dati/sito.json", "../sito.json"),
            "senza",
        ),
        (
            # Con PyYAML la tabulazione e' un errore di sintassi, non un errore del
            # nostro parser: il rifiuto c'e' e il messaggio dice che lo YAML non va.
            # Il vecchio parser custom diceva «tabulazione»; il requisito e' rifiutare.
            "tabulazione nel rientro",
            DICHIARAZIONE.replace("  home.eroe.titolo", "\thome.eroe.titolo"),
            "YAML",
        ),
        (
            "campo dichiarato ma assente dal JSON",
            DICHIARAZIONE.replace(
                "home.eroe.righe", "home.eroe.inesistente"
            ),
            "non esiste",
        ),
        (
            "file dei contenuti assente",
            DICHIARAZIONE.replace("dati/sito.json", "dati/manca.json"),
            "non esiste",
        ),
        (
            "virgoletta non chiusa",
            DICHIARAZIONE.replace('"Titolo"', '"Titolo'),
            "YAML",
        ),
    ]
    for etichetta, testo, atteso in casi:
        with tempfile.TemporaryDirectory() as tmp:
            progetto = crea_progetto(Path(tmp), dichiarazione=testo)
            esito = esegui(progetto)
            check(f"{etichetta}: esito 2", esito.returncode == 2, f"{esito.returncode} {esito.stderr}")
            check(
                f"{etichetta}: il messaggio spiega",
                atteso in esito.stderr,
                f"atteso «{atteso}» in: {esito.stderr}",
            )
            check(
                f"{etichetta}: niente avviato",
                "avvio:" not in esito.stdout,
                esito.stdout,
            )


def test_forma_dell_esempio() -> None:
    """La forma scritta nella decisione — mappa in linea e trattino lungo — si legge."""
    testo = (
        "file: dati/sito.json\n"
        "avvio: npm run dev\n"
        "url: http://127.0.0.1:4321\n"
        "campi:\n"
        '  home.eroe.titolo: { etichetta: "Titolo — prima riga", tipo: testo }\n'
    )
    letto = banco.leggi_dichiarazione(testo)
    campi = letto["campi"]
    check("la mappa dei campi si legge", isinstance(campi, dict), str(campi))
    check(
        "l'etichetta tiene il trattino lungo",
        campi["home.eroe.titolo"]["etichetta"] == "Titolo — prima riga",
        str(campi),
    )


def test_aiuto() -> None:
    """`--aiuto` spiega cosa serve, e non avvia niente."""
    esito = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "banco.py"), "--aiuto"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    check("--aiuto esce 0", esito.returncode == 0, str(esito.returncode))
    check("l'aiuto mostra la forma del file", "contenuti.yaml" in esito.stdout, esito.stdout[:300])
    check(
        "l'aiuto mostra il comando",
        "python3 tools/banco.py" in esito.stdout,
        esito.stdout[:300],
    )
    senza = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "banco.py")],
        capture_output=True,
        text=True,
        timeout=30,
    )
    check("senza progetto: esito 2", senza.returncode == 2, str(senza.returncode))


# --------------------------------------------------------------------------- #
# Il server: lettura                                                           #
# --------------------------------------------------------------------------- #


def test_letture() -> None:
    """Editor, stato e contenuti si servono; gli errori parlano JSON."""
    with tempfile.TemporaryDirectory() as tmp:
        progetto = crea_progetto(Path(tmp))
        with server_di(progetto) as (configurazione, porta):
            stato, corpo, _ = richiesta(porta, "GET", "/api/stato", origine=None)
            check("GET /api/stato: 200", stato == 200, str(stato))
            check("lo stato dichiara il file", corpo.get("file") == "dati/sito.json", str(corpo))
            check("lo stato dichiara i campi", len(corpo.get("campi") or {}) == 2, str(corpo))
            check(
                "lo stato dichiara l'editor",
                str(porta) in str(corpo.get("editor")),
                str(corpo),
            )
            stato, contenuti, _ = richiesta(porta, "GET", "/api/contenuti", origine=None)
            check("GET /api/contenuti: 200", stato == 200, str(stato))
            check(
                "i contenuti sono quelli del file",
                contenuti.get("altro", {}).get("valore") == "non toccare",
                str(contenuti),
            )

            stato, _, intestazioni = richiesta(porta, "GET", "/editor.js", origine=ORIGINE)
            check("GET /editor.js: 200", stato == 200, str(stato))
            check(
                "editor.js e' JavaScript",
                "javascript" in (intestazioni.get("Content-Type") or "").lower(),
                str(intestazioni.get("Content-Type")),
            )
            check(
                "l'editor usa gli attributi data-scritta",
                b"data-scritta" in (ROOT / "tools" / "banco" / "editor.js").read_bytes(),
                "editor.js",
            )

            # IL CRITERIO 10, SECONDA META' — «ogni funzione aggiunta coperta da un test».
            #
            # Mancava, e il Code Review di R7 l'ha provato per mutazione: cancellando il
            # bottone «Invia» e il ramo Enter, la suite restava «PASS — 246 controlli»,
            # identica all'intatto. Il criterio era scritto, il gate chiuso, e nessuna
            # prova lo sosteneva. Nel repository non c'e' un harness JS, e non e' una
            # ragione per non provare niente: il comportamento e' nel testo del file, e si
            # puo' leggere. Non e' una prova di esecuzione — e' la prova che il codice c'e'
            # e che nessuno l'ha tolto senza accorgersene. Il limite si dichiara qui.
            editor = (ROOT / "tools" / "banco" / "editor.js").read_text(encoding="utf-8")
            # Contare non basta: cercare «il frammento esiste» trova anche le copie
            # superstiti. La mutazione del Code Review di R7 cambiava UNA occorrenza e
            # lasciava le altre, e la prova passava. Quindi si contano: se una sparisce,
            # il numero scende e il controllo fallisce.
            # I MINIMI SONO LE OCCORRENZE VERE, non una stima prudente.
            #
            # La prima versione metteva 2/2/2/1/2 contro 4/2/2/2/3 reali, con `>=`:
            # togliere UNA occorrenza restava sopra soglia, e la suite passava. Il QA di
            # ENG-022 l'ha misurato — la mutazione esatta di R7 (`textContent` cambiato)
            # non veniva presa. Era lo stesso errore delle soglie di righe: una soglia
            # sotto il valore vero non misura niente.
            #
            # Ora e' `==`: il numero deve essere **esattamente** quello. Cosi' una
            # occorrenza tolta O aggiunta si vede, senza dover scegliere un margine.
            for etichetta, frammento, attese in (
                ("il bottone della richiesta dice «Invia»", "textContent = 'Invia'", 4),
                ("Enter manda la richiesta", "evento.key === 'Enter'", 2),
                ("Shift+Enter va a capo", "!evento.shiftKey", 2),
                ("la conferma ha il suo blocco", "banco-ai-conferma", 2),
                ("la richiesta si invia davvero", "inviaRichiesta(", 3),
            ):
                quante = editor.count(frammento)
                check(
                    f"editor.js: {etichetta} ({quante} volte, attese {attese})",
                    quante == attese,
                    f"«{frammento}» compare {quante} volte invece di {attese}: una funzione e' "
                    "stata tolta, aggiunta o rinominata senza aggiornare la prova (criterio 10)",
                )

            stato, _, intestazioni = richiesta(porta, "GET", "/editor.css", origine=ORIGINE)
            check("GET /editor.css: 200", stato == 200, str(stato))
            check(
                "editor.css e' CSS",
                "text/css" in (intestazioni.get("Content-Type") or "").lower(),
                str(intestazioni.get("Content-Type")),
            )
            check(
                "editor.css disegna l'indicatore",
                b"banco-indicatore" in (ROOT / "tools" / "banco" / "editor.css").read_bytes(),
                "banco-indicatore",
            )
            stato, corpo, _ = richiesta(porta, "GET", "/api/inesistente", origine=None)
            check("rotta sconosciuta: 404", stato == 404, str(stato))
            check("rotta sconosciuta: errore JSON", "errore" in corpo, str(corpo))
            check(
                "le origini ammesse sono solo quelle loopback del sito",
                configurazione.origini == frozenset({ORIGINE, "http://localhost:4321"}),
                str(configurazione.origini),
            )


# --------------------------------------------------------------------------- #
# Il server: permesso, origine, corpo                                          #
# --------------------------------------------------------------------------- #


def test_solo_loopback() -> None:
    """Il server dell'editor ascolta su 127.0.0.1, non su tutte le interfacce."""
    with tempfile.TemporaryDirectory() as tmp:
        progetto = crea_progetto(Path(tmp))
        configurazione = banco.carica(progetto)
        server = banco.crea_server(configurazione, 0)
        try:
            check(
                "il server ascolta su 127.0.0.1",
                server.server_address[0] == "127.0.0.1",
                str(server.server_address),
            )
        finally:
            server.server_close()


def test_percorso_fuori_allowlist() -> None:
    """Un percorso non dichiarato si rifiuta e il file resta identico."""
    with tempfile.TemporaryDirectory() as tmp:
        progetto = crea_progetto(Path(tmp))
        file_contenuti = progetto / "dati" / "sito.json"
        prima = file_contenuti.read_bytes()
        with server_di(progetto) as (_configurazione, porta):
            stato, corpo, _ = richiesta(
                porta,
                "POST",
                "/api/salva",
                {"percorso": "home.altro", "valore": "invasione"},
            )
            check("percorso non dichiarato: 404", stato == 404, f"{stato} {corpo}")
            check(
                "il rifiuto spiega che il campo non e' dichiarato",
                "contenuti.yaml" in str(corpo.get("errore")),
                str(corpo),
            )
            check(
                "il file e' identico dopo il rifiuto",
                file_contenuti.read_bytes() == prima,
                "il file e' cambiato",
            )
            check(
                "nessun file temporaneo lasciato",
                sorted(p.name for p in file_contenuti.parent.iterdir() if p.suffix == ".tmp") == [],
                str(sorted(p.name for p in file_contenuti.parent.iterdir())),
            )


def test_corpo_troppo_grande() -> None:
    """Un corpo oltre il limite si rifiuta, e il file resta identico."""
    with tempfile.TemporaryDirectory() as tmp:
        progetto = crea_progetto(Path(tmp))
        file_contenuti = progetto / "dati" / "sito.json"
        prima = file_contenuti.read_bytes()
        with server_di(progetto) as (_configurazione, porta):
            corpo = b"x" * (banco.LIMITE_CORPO + 1000)
            stato, letto, _ = richiesta(porta, "POST", "/api/salva", corpo)
            check("corpo troppo grande: 413", stato == 413, f"{stato} {letto}")
            check(
                "il rifiuto dice il limite",
                "limite" in str(letto.get("errore")),
                str(letto),
            )
            check(
                "il file e' identico dopo il corpo troppo grande",
                file_contenuti.read_bytes() == prima,
                "il file e' cambiato",
            )


def test_origine() -> None:
    """Il salvataggio risponde solo all'Origin del sito: niente, null e altrui no."""
    with tempfile.TemporaryDirectory() as tmp:
        progetto = crea_progetto(Path(tmp))
        file_contenuti = progetto / "dati" / "sito.json"
        prima = file_contenuti.read_bytes()
        corpo = {"percorso": "home.eroe.titolo", "valore": "da un altro sito"}
        with server_di(progetto) as (_configurazione, porta):
            for etichetta, origine in (
                ("Origin assente", None),
                ("Origin null", "null"),
                ("Origin di un altro sito", "http://evil.example"),
            ):
                stato, letto, _ = richiesta(porta, "POST", "/api/salva", corpo, origine=origine)
                check(f"{etichetta}: 403", stato == 403, f"{stato} {letto}")
            check(
                "nessuna delle origini rifiutate ha scritto",
                file_contenuti.read_bytes() == prima,
                "il file e' cambiato",
            )
            stato, _, intestazioni = richiesta(porta, "OPTIONS", "/api/salva", origine=ORIGINE)
            check("preflight consentito: 204", stato == 204, str(stato))
            check(
                "il preflight dice l'origine ammessa",
                intestazioni.get("Access-Control-Allow-Origin") == ORIGINE,
                str(intestazioni),
            )
            stato, _, _ = richiesta(porta, "OPTIONS", "/api/salva", origine="http://evil.example")
            check("preflight di un'altra origine: 403", stato == 403, str(stato))
            stato, _, _ = richiesta(porta, "GET", "/api/contenuti", origine="http://evil.example")
            check("GET da un'altra origine: 403", stato == 403, str(stato))


def test_tipi() -> None:
    """Il tipo dichiarato conta: un elenco vuoto e un testo troppo lungo si rifiutano."""
    with tempfile.TemporaryDirectory() as tmp:
        progetto = crea_progetto(Path(tmp))
        file_contenuti = progetto / "dati" / "sito.json"
        prima = file_contenuti.read_bytes()
        with server_di(progetto) as (_configurazione, porta):
            stato, corpo, _ = richiesta(
                porta,
                "POST",
                "/api/salva",
                {"percorso": "home.eroe.righe", "valore": []},
            )
            check("elenco vuoto: 422", stato == 422, f"{stato} {corpo}")
            stato, corpo, _ = richiesta(
                porta,
                "POST",
                "/api/salva",
                {"percorso": "home.eroe.titolo", "valore": "a" * (banco.LIMITE_TESTO + 1)},
            )
            check("testo troppo lungo: 422", stato == 422, f"{stato} {corpo}")
            stato, corpo, _ = richiesta(
                porta,
                "POST",
                "/api/salva",
                {"percorso": "home.eroe.titolo", "valore": 123},
            )
            check("tipo sbagliato: 422", stato == 422, f"{stato} {corpo}")
            check(
                "nessun rifiuto di tipo ha scritto",
                file_contenuti.read_bytes() == prima,
                "il file e' cambiato",
            )


def test_percorso_sparito_dal_file() -> None:
    """Se il JSON cambia sotto il banco, il salvataggio lo dice invece di inventare."""
    with tempfile.TemporaryDirectory() as tmp:
        progetto = crea_progetto(Path(tmp))
        file_contenuti = progetto / "dati" / "sito.json"
        with server_di(progetto) as (_configurazione, porta):
            dati = json.loads(file_contenuti.read_text(encoding="utf-8"))
            del dati["home"]["eroe"]["titolo"]
            file_contenuti.write_text(json.dumps(dati, indent=2) + "\n", encoding="utf-8")
            prima = file_contenuti.read_bytes()
            stato, corpo, _ = richiesta(
                porta,
                "POST",
                "/api/salva",
                {"percorso": "home.eroe.titolo", "valore": "nuovo"},
            )
            check("percorso sparito: 409", stato == 409, f"{stato} {corpo}")
            check(
                "il file resta com'e'",
                file_contenuti.read_bytes() == prima,
                "il file e' cambiato",
            )


# --------------------------------------------------------------------------- #
# La scrittura                                                                 #
# --------------------------------------------------------------------------- #


def test_scrittura_atomica() -> None:
    """Il salvataggio buono scrive, conserva il resto e i permessi, e non lascia tmp."""
    with tempfile.TemporaryDirectory() as tmp:
        progetto = crea_progetto(Path(tmp))
        file_contenuti = progetto / "dati" / "sito.json"
        os.chmod(file_contenuti, 0o640)
        prima = file_contenuti.read_text(encoding="utf-8")
        with server_di(progetto) as (_configurazione, porta):
            stato, corpo, intestazioni = richiesta(
                porta,
                "POST",
                "/api/salva",
                {"percorso": "home.eroe.titolo", "valore": "Titolo nuovo"},
            )
            check("salvataggio buono: 200", stato == 200, f"{stato} {corpo}")
            check("la risposta dice il file", corpo.get("file") == "dati/sito.json", str(corpo))
            check(
                "la risposta dichiara l'origine del sito (il browser la richiede)",
                intestazioni.get("Access-Control-Allow-Origin") == ORIGINE,
                str(intestazioni),
            )
            check(
                "la risposta e' dichiarata JSON",
                "application/json" in (intestazioni.get("Content-Type") or ""),
                str(intestazioni.get("Content-Type")),
            )
            nuovo = json.loads(file_contenuti.read_text(encoding="utf-8"))
            check(
                "il valore e' scritto",
                nuovo["home"]["eroe"]["titolo"] == "Titolo nuovo",
                str(nuovo),
            )
            check(
                "il resto del file non cambia",
                nuovo["altro"]["valore"] == "non toccare"
                and nuovo["home"]["eroe"]["righe"] == ["prima", "seconda"],
                str(nuovo),
            )
            check(
                "l'indentazione resta quella del file",
                '\n  "home"' in file_contenuti.read_text(encoding="utf-8"),
                file_contenuti.read_text(encoding="utf-8")[:120],
            )
            check(
                "il file finisce con un a capo",
                file_contenuti.read_text(encoding="utf-8").endswith("\n"),
                repr(file_contenuti.read_text(encoding="utf-8")[-20:]),
            )
            check(
                "i permessi restano quelli di prima",
                oct(file_contenuti.stat().st_mode & 0o777) == oct(0o640),
                oct(file_contenuti.stat().st_mode & 0o777),
            )
            check(
                "nessun file temporaneo lasciato",
                [p.name for p in file_contenuti.parent.iterdir() if p.suffix == ".tmp"] == [],
                str(sorted(p.name for p in file_contenuti.parent.iterdir())),
            )
            stato, corpo, _ = richiesta(
                porta,
                "POST",
                "/api/salva",
                {"percorso": "home.eroe.righe", "valore": ["una", "due", "tre"]},
            )
            check("salvataggio di un elenco: 200", stato == 200, f"{stato} {corpo}")
            elenco = json.loads(file_contenuti.read_text(encoding="utf-8"))
            check(
                "l'elenco e' scritto",
                elenco["home"]["eroe"]["righe"] == ["una", "due", "tre"],
                str(elenco),
            )
            check(
                "dopo un salvataggio buono il file cambia",
                prima != file_contenuti.read_text(encoding="utf-8"),
                "il file non e' cambiato",
            )
            dopo_il_salvataggio = file_contenuti.read_bytes()
            stato, corpo, _ = richiesta(
                porta,
                "POST",
                "/api/salva",
                {"percorso": "home.eroe.titolo", "valore": "Titolo nuovo"},
            )
            check("riscrivere lo stesso valore: 200", stato == 200, f"{stato} {corpo}")
            check(
                "riscrivere lo stesso valore lascia il file identico, byte per byte",
                file_contenuti.read_bytes() == dopo_il_salvataggio,
                "il file e' cambiato senza che il valore cambiasse",
            )


def test_scrittura_fallita_non_tocca_il_file() -> None:
    """Se il temporaneo non si puo' creare, il file originale resta intatto."""
    if os.geteuid() == 0:  # pragma: no cover - in una sandbox da root i permessi non fermano
        print("  (salto: si e' root, i permessi della cartella non fermano la scrittura)")
        return
    with tempfile.TemporaryDirectory() as tmp:
        progetto = crea_progetto(Path(tmp))
        cartella = progetto / "dati"
        file_contenuti = cartella / "sito.json"
        prima = file_contenuti.read_bytes()
        os.chmod(cartella, 0o500)
        try:
            with server_di(progetto) as (_configurazione, porta):
                stato, corpo, _ = richiesta(
                    porta,
                    "POST",
                    "/api/salva",
                    {"percorso": "home.eroe.titolo", "valore": "non deve passare"},
                )
                check("cartella non scrivibile: 500", stato == 500, f"{stato} {corpo}")
                check(
                    "il file originale e' intatto",
                    file_contenuti.read_bytes() == prima,
                    "il file e' cambiato",
                )
                check(
                    "nessun temporaneo lasciato",
                    [p.name for p in cartella.iterdir() if p.suffix == ".tmp"] == [],
                    str(sorted(p.name for p in cartella.iterdir())),
                )
        finally:
            os.chmod(cartella, 0o700)



def test_dichiarazione_non_leggibile() -> None:
    """Un `contenuti.yaml` non UTF-8 e un JSON dei contenuti non UTF-8 non devono
    produrre un traceback: sono configurazioni sbagliate, e si dicono con la riga
    e il motivo, esito 2 — come una dichiarazione mancante.
    """
    with tempfile.TemporaryDirectory() as cartella:
        base = Path(cartella)
        progetto = crea_progetto(base)
        dichiarazione = progetto / "contenuti.yaml"

        # 1. la dichiarazione contiene un byte che non e' UTF-8 valido
        testo_buono = dichiarazione.read_text(encoding="utf-8")
        dichiarazione.write_bytes(testo_buono.encode("utf-8") + b"\xe9")
        esito = esegui(progetto)
        check("dichiarazione non UTF-8: esito 2", esito.returncode == 2, str(esito.returncode))
        check(
            "dichiarazione non UTF-8: nessun traceback",
            "Traceback" not in esito.stderr,
            esito.stderr[-200:],
        )
        check(
            "dichiarazione non UTF-8: dice perche'",
            "UTF-8" in (esito.stderr or esito.stdout),
            esito.stderr[-200:],
        )

        # 2. la dichiarazione torna buona, ma il file dei contenuti non e' UTF-8
        dichiarazione.write_text(testo_buono, encoding="utf-8")
        file_contenuti = progetto / "dati" / "sito.json"
        file_contenuti.write_bytes(b'{"saluto": "citt\xe0"}')
        esito = esegui(progetto)
        check("contenuti non UTF-8: esito 2", esito.returncode == 2, str(esito.returncode))
        check(
            "contenuti non UTF-8: nessun traceback",
            "Traceback" not in esito.stderr,
            esito.stderr[-200:],
        )
        check(
            "contenuti non UTF-8: dice perche'",
            "UTF-8" in (esito.stderr or esito.stdout),
            esito.stderr[-200:],
        )


def test_percorso_non_valido() -> None:
    """Un `file` che non e' un percorso legale si rifiuta con un messaggio, non con
    un'eccezione di sistema."""
    with tempfile.TemporaryDirectory() as cartella:
        progetto = crea_progetto(Path(cartella))
        # un NUL VERO nel percorso, non la sequenza "backslash u zero zero zero zero"
        (progetto / "contenuti.yaml").write_text(
            'file: "dati/' + chr(0) + '.json"\n'
            "avvio: echo\n"
            "url: http://127.0.0.1:4321\n"
            "campi:\n"
            "  saluto: { etichetta: Saluto, tipo: testo }\n",
            encoding="utf-8",
        )
        esito = esegui(progetto)
        check("percorso con NUL: esito 2", esito.returncode == 2, str(esito.returncode))
        check(
            "percorso con NUL: nessun traceback",
            "Traceback" not in esito.stderr,
            esito.stderr[-200:],
        )


def test_contenuti_json_non_valido() -> None:
    """Un file dei contenuti che non e' JSON valido si rifiuta all'avvio, con la
    riga e la colonna: e' un errore di configurazione, non un traceback."""
    with tempfile.TemporaryDirectory() as cartella:
        progetto = crea_progetto(Path(cartella))
        (progetto / "dati" / "sito.json").write_text('{ "home": ', encoding="utf-8")
        esito = esegui(progetto)
        check("JSON dei contenuti invalido: esito 2", esito.returncode == 2, str(esito.returncode))
        check(
            "JSON dei contenuti invalido: nessun traceback",
            "Traceback" not in esito.stderr,
            esito.stderr[-200:],
        )
        messaggio = esito.stderr or esito.stdout
        check(
            "JSON dei contenuti invalido: dice riga e colonna",
            "JSON valido" in messaggio and "riga" in messaggio,
            messaggio[-200:],
        )

# --------------------------------------------------------------------------- #
# Le foto: solo riferimenti, mai file (ENG-017)                                #
# --------------------------------------------------------------------------- #

DICHIARAZIONE_FOTO = """file: dati/sito.json
avvio: python3 -m http.server 4321
url: http://127.0.0.1:4321
campi:
  home.eroe.titolo: { etichetta: "Titolo", tipo: testo }
  home.eroe.foto: { etichetta: "Foto", tipo: foto }
"""

CONTENUTI_FOTO = {"home": {"eroe": {"titolo": "Titolo", "foto": "/immagini/team.jpg"}}}


def crea_progetto_foto(radice: Path) -> Path:
    """Un progetto con una cartella di immagini e un campo `foto`."""
    progetto = crea_progetto(radice, DICHIARAZIONE_FOTO, CONTENUTI_FOTO)
    immagini = progetto / "immagini"
    immagini.mkdir(parents=True)
    (immagini / "team.jpg").write_bytes(b"\xff\xd8\xff\xe0finta-immagine")
    (immagini / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\nfinta")
    (immagini / "rotella.svg").write_text("<svg/>", encoding="utf-8")
    (immagini / "note.txt").write_text("non e' un'immagine", encoding="utf-8")
    (progetto / "dati" / "sito.json").write_text(
        json.dumps(CONTENUTI_FOTO, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return progetto


def test_foto_valida_e_rifiutati() -> None:
    """Un percorso di foto vale solo se e' un'immagine **dentro** il progetto."""
    print("\nfoto: riferimenti")
    with tempfile.TemporaryDirectory() as temporanea:
        progetto = crea_progetto_foto(Path(temporanea))
        banco.carica(progetto)  # la dichiarazione con `foto` e' valida
        check("una foto esistente passa", banco.valida_foto(progetto, "/immagini/team.jpg") is None)
        check("senza barra iniziale passa", banco.valida_foto(progetto, "immagini/logo.png") is None)
        for valore, perche in (
            ("/immagini/manca.jpg", "un file che non c'e'"),
            ("../fuori.jpg", "un percorso che esce dal progetto"),
            ("https://esempio.it/a.jpg", "un indirizzo web"),
            ("/immagini/rotella.svg", "un SVG, che puo' contenere codice"),
            ("/immagini/note.txt", "un file che non e' un'immagine"),
            ("", "un percorso vuoto"),
            ("/immagini/team.jpg\x00.png", "un NUL dopo un'estensione ammessa"),
            ("/immagini/a\x00b", "un NUL in mezzo al nome"),
            ("/immagini/team\x01.jpg", "un carattere di controllo"),
            ("/immagini/\ud800.png", "un surrogato solitario (meta' di una coppia)"),
            ("/immagini/team.jpg\udfff", "un surrogato in coda"),
        ):
            try:
                problema = banco.valida_foto(progetto, valore)
            except Exception as errore:  # noqa: BLE001 - il difetto e' proprio l'eccezione
                check(
                    f"rifiuta {perche} senza sollevare eccezioni",
                    False,
                    f"{type(errore).__name__}: {errore}",
                )
                continue
            check(f"rifiuta {perche}", problema is not None, str(problema))


def test_un_messaggio_non_uccide_la_risposta() -> None:
    """Un carattere che l'UTF-8 non sa codificare non deve chiudere la connessione.

    Il 2026-11-02 la revisione di ENG-017 l'ha trovato dopo il NUL: un surrogato
    (`\\ud800` come escape JSON) arrivava nel messaggio d'errore e `_invia` esplodeva in
    `UnicodeEncodeError`, lasciando il client senza risposta. La difesa e' doppia: il
    filtro all'ingresso, e `_testo_sicuro` all'uscita.
    """
    print("\nun messaggio con un surrogato non uccide la risposta")
    check(
        "il testo con surrogato diventa codificabile",
        banco._testo_sicuro("a\ud800b").encode("utf-8") == b"a?b",
        repr(banco._testo_sicuro("a\ud800b")),
    )
    check(
        "un testo normale non cambia",
        banco._testo_sicuro("Il percorso «/immagini/a.png»") == "Il percorso «/immagini/a.png»",
    )
    with tempfile.TemporaryDirectory() as temporanea:
        progetto = crea_progetto_foto(Path(temporanea))
        with server_di(progetto) as (_configurazione, porta):
            # Il surrogato nel campo: rifiutato con un messaggio, non con una caduta.
            try:
                stato, corpo, _ = richiesta(
                    porta, "POST", "/api/salva",
                    {"percorso": "home.eroe.foto", "valore": "/immagini/\ud800.png"},
                )
                check("il surrogato nel valore riceve un rifiuto", stato == 422, (stato, corpo))
                check(
                    "e il messaggio e' comprensibile",
                    isinstance(corpo, dict) and "errore" in corpo,
                    str(corpo),
                )
            except Exception as errore:  # noqa: BLE001 - il difetto era proprio l'eccezione
                check(
                    "il surrogato nel valore non chiude la connessione",
                    False,
                    f"{type(errore).__name__}: {errore}",
                )
            # Nessuna rotta puo' cadere: il surrogato in un testo, in un elenco,
            # nell'istruzione e nel percorso della richiesta.
            for etichetta, percorso_http, corpo_richiesta in (
                ("testo", "/api/salva", {"percorso": "home.eroe.titolo", "valore": "ciao \ud800"}),
                ("elenco", "/api/salva", {"percorso": "home.eroe.righe", "valore": ["ok", "x \ud800"]}),
                ("istruzione", "/api/richieste", {"percorso": "home.eroe.titolo", "istruzione": "x \ud800"}),
                ("percorso della richiesta", "/api/richieste", {"percorso": "home.\ud800", "istruzione": "x"}),
                ("foto della richiesta", "/api/richieste", {"percorso": "home.eroe.titolo", "istruzione": "x", "foto": ["/immagini/\ud800.png"]}),
            ):
                try:
                    stato, corpo, _ = richiesta(porta, "POST", percorso_http, corpo_richiesta)
                    check(
                        f"il surrogato nel {etichetta} riceve un rifiuto",
                        stato in (404, 422),
                        (stato, corpo),
                    )
                    check(
                        f"e il rifiuto del {etichetta} e' un messaggio, non una caduta",
                        isinstance(corpo, dict) and "errore" in corpo,
                        str(corpo),
                    )
                except Exception as errore:  # noqa: BLE001 - il difetto era proprio l'eccezione
                    check(
                        f"il surrogato nel {etichetta} non chiude la connessione",
                        False,
                        f"{type(errore).__name__}: {errore}",
                    )

            # Il server e' ancora vivo: le richieste dopo rispondono.
            stato, corpo, _ = richiesta(
                porta, "POST", "/api/salva",
                {"percorso": "home.eroe.foto", "valore": "/immagini/logo.png"},
            )
            check("il server e' ancora vivo dopo il rifiuto", stato == 200, (stato, corpo))
            stato, corpo, _ = richiesta(
                porta, "POST", "/api/salva",
                {"percorso": "home.eroe.titolo", "valore": "un titolo nuovo"},
            )
            check("e accetta ancora un testo valido", stato == 200, (stato, corpo))


def test_un_json_annidato_non_uccide_la_risposta() -> None:
    """Un corpo profondamente annidato riceve un rifiuto, non una caduta.

    `json.loads` su `[[[[…` solleva **RecursionError**, che non e' un `JSONDecodeError`:
    sfuggiva al filtro e chiudeva la connessione senza risposta. Trovato dalla revisione
    di ENG-017 con 9.998 livelli in 20 KB — sotto il limite di 413 e sopra la validazione.
    """
    print("\nun JSON annidato non uccide la risposta")
    with tempfile.TemporaryDirectory() as temporanea:
        progetto = crea_progetto_foto(Path(temporanea))
        with server_di(progetto) as (_configurazione, porta):
            for livelli, etichetta in ((9998, "9.998"), (16000, "16.000"), (40000, "oltre il limite")):
                corpo = b"[" * livelli
                try:
                    stato, letto, _ = richiesta(porta, "POST", "/api/salva", corpo)
                    check(
                        f"il JSON annidato ({etichetta} livelli) riceve un rifiuto",
                        stato in (400, 413, 422),
                        (stato, str(letto)[:120]),
                    )
                except Exception as errore:  # noqa: BLE001 - il difetto era proprio l'eccezione
                    check(
                        f"il JSON annidato ({etichetta} livelli) non chiude la connessione",
                        False,
                        f"{type(errore).__name__}: {errore}",
                    )
            stato, corpo, _ = richiesta(
                porta, "POST", "/api/salva",
                {"percorso": "home.eroe.foto", "valore": "/immagini/logo.png"},
            )
            check("il server e' ancora vivo dopo i rifiuti", stato == 200, (stato, corpo))


def test_le_quattro_porte_della_classe() -> None:
    """Quattro ingressi che chiudevano la risposta: riga di richiesta, file avvelenato,
    file non UTF-8, e l'annidamento visto dall'encoder (che si ferma molto prima del
    decoder). Trovati dalla revisione di ENG-017 il 2026-11-02, uno per volta."""
    print("\nle quattro porte della stessa classe")
    with tempfile.TemporaryDirectory() as temporanea:
        progetto = crea_progetto_foto(Path(temporanea))
        file_json = progetto / "dati" / "sito.json"
        sano = json.dumps(CONTENUTI_FOTO, indent=2, ensure_ascii=False) + "\n"

        with server_di(progetto) as (_configurazione, porta):
            # --- porta 1: la riga di richiesta, non il corpo ---
            for riga in (
                b"GET http://[ HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n",
                b"GET http://[] HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n",
                b"GET http://[::1 HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n",
            ):
                risposta = _grezza(porta, riga)
                check(
                    f"la riga {riga[:14]!r} riceve una risposta",
                    risposta.startswith("HTTP/"),
                    risposta[:80],
                )

            # --- porta 2: surrogato nel FILE, riemesso dalla richiesta ---
            file_json.write_text('{"home":{"eroe":{"titolo":"x\\ud800y","foto":"/immagini/team.jpg"}}}', encoding="utf-8")
            try:
                stato, corpo, _ = richiesta(
                    porta, "POST", "/api/richieste",
                    {"percorso": "home.eroe.titolo", "istruzione": "accorcia"},
                )
                check("il surrogato nel file non chiude la risposta", stato in (201, 422, 500), (stato, str(corpo)[:100]))
            except Exception as errore:  # noqa: BLE001
                check("il surrogato nel file non chiude la risposta", False, f"{type(errore).__name__}: {errore}")
            file_json.write_text(sano, encoding="utf-8")

            # --- porta 3: il file non e' UTF-8 ---
            file_json.write_bytes(b'{"home":{"eroe":{"titolo":"caff\xe8","foto":"/immagini/team.jpg"}}}')
            for etichetta, percorso_http, corpo_richiesta in (
                ("GET /api/contenuti", "/api/contenuti", None),
                ("POST /api/salva", "/api/salva", {"percorso": "home.eroe.titolo", "valore": "x"}),
                ("POST /api/richieste", "/api/richieste", {"percorso": "home.eroe.titolo", "istruzione": "x"}),
            ):
                try:
                    stato = richiesta(porta, "GET" if corpo_richiesta is None else "POST", percorso_http, corpo_richiesta)[0]
                    check(f"{etichetta} su file non UTF-8 risponde", stato >= 200, stato)
                except Exception as errore:  # noqa: BLE001
                    check(f"{etichetta} su file non UTF-8 risponde", False, f"{type(errore).__name__}: {errore}")
            file_json.write_text(sano, encoding="utf-8")

            # --- porta 4: file valido, annidato oltre l'encoder ---
            def annida(n: int) -> dict:
                d: dict = {"titolo": "x", "foto": "/immagini/team.jpg"}
                for _ in range(n):
                    d = {"a": d}
                return d

            file_json.write_text(json.dumps({"home": {"eroe": annida(990)}}, indent=2), encoding="utf-8")
            try:
                stato, corpo, _ = richiesta(
                    porta, "POST", "/api/salva",
                    {"percorso": "home.eroe.a.a.titolo", "valore": "x"},
                )
                # 404 va bene: con il file annidato, il percorso dichiarato non c'e' piu'.
                # Cio' che conta e' che la risposta ci sia: 0 byte sarebbe la caduta.
                check(
                    "il file annidato oltre l'encoder riceve un rifiuto",
                    stato in (404, 409, 422, 500),
                    (stato, str(corpo)[:100]),
                )
            except Exception as errore:  # noqa: BLE001
                check("il file annidato oltre l'encoder riceve un rifiuto", False, f"{type(errore).__name__}: {errore}")

            file_json.write_text(sano, encoding="utf-8")
            stato, corpo, _ = richiesta(
                porta, "POST", "/api/salva",
                {"percorso": "home.eroe.foto", "valore": "/immagini/logo.png"},
            )
            check("il server e' vivo dopo tutte e quattro", stato == 200, (stato, corpo))


def _grezza(porta: int, petizione: bytes) -> str:
    """Una richiesta HTTP scritta a mano, per provare la riga di richiesta."""
    import socket

    connessione = socket.create_connection(("127.0.0.1", porta), timeout=10)
    try:
        connessione.sendall(petizione)
        dati = connessione.recv(200)
        return dati.decode("latin-1", "replace") if dati else ""
    finally:
        connessione.close()


def test_i_sei_difetti_di_robustezza() -> None:
    """Sei ingressi trovati dalla revisione R5: nessuno deve dare un traceback,
    e uno di essi — `--chiudi` — non deve uccidere un processo estraneo."""
    print("\nsei difetti di robustezza")
    with tempfile.TemporaryDirectory() as temporanea:
        progetto = crea_progetto_foto(Path(temporanea))
        cartella_stato = progetto / ".banco"
        cartella_stato.mkdir(exist_ok=True)

        # 1) pid oltre il long di C: OverflowError
        (cartella_stato / "stato.json").write_text(
            '{"pid": 99999999999999999999, "porta": 4320}', encoding="utf-8"
        )
        for opzione in ("--stato", "--chiudi"):
            esito = esegui(progetto, opzione)
            check(
                f"{opzione} con un pid enorme non va in traceback",
                "Traceback" not in esito.stderr,
                esito.stderr[:200],
            )
            # Il difetto era che il comando USCIVA 1 senza spiegare: il criterio non
            # e' «niente traceback», e' «dice cosa succede e non si blocca».
            check(
                f"{opzione} con un pid enorme spiega il motivo",
                len((esito.stdout + esito.stderr).strip()) > 10,
                (esito.stdout + esito.stderr)[:120],
            )
        check("un pid enorme non e' un processo vivo", banco.stato_vivo(progetto) is None)
        check(
            "ma non conta come processo vivo",
            banco._processo_vivo(99999999999999999999) is False,
        )
        check(
            "e non fa credere che ci sia un banco acceso",
            banco.stato_vivo(progetto) is None,
        )
        # Il criterio 5: uno stato vecchio non blocca un nuovo avvio. Con un pid enorme
        # `--servizio` deve partire (o fallire per il sito, non per lo stato).
        esito = esegui(progetto, "--servizio")
        check(
            "--servizio non e' bloccato da un pid enorme nello stato",
            "Traceback" not in esito.stderr,
            esito.stderr[:200],
        )
        esegui(progetto, "--chiudi")
        (cartella_stato / "stato.json").unlink(missing_ok=True)

        check(
            "un pid oltre il long di C non e' vivo",
            banco._processo_vivo(2**31) is False and banco._processo_vivo(2**63) is False,
        )
        check(
            "un pid normale ma inesistente non e' vivo",
            banco._processo_vivo(999999) is False,
        )

        # 2) stato.json non UTF-8: UnicodeDecodeError
        (cartella_stato / "stato.json").write_bytes(b'{"pid": 1, "x": "\xe0"}')
        for opzione in ("--stato", "--chiudi"):
            esito = esegui(progetto, opzione)
            check(
                f"{opzione} con uno stato non UTF-8 non va in traceback",
                "Traceback" not in esito.stderr,
                esito.stderr[:200],
            )
        check("e lo stato illeggibile non risulta vivo", banco.stato_vivo(progetto) is None)

        # 3) collegamento circolare: RuntimeError da resolve()
        circolare = progetto / "immagini" / "giro.png"
        try:
            circolare.symlink_to(circolare)
        except OSError:
            circolare = None
        if circolare is not None:
            configurazione = banco.carica(progetto)
            check("il collegamento circolare non impedisce di caricare", configurazione is not None)
            check(
                "e non entra nell'elenco delle immagini",
                "/immagini/giro.png" not in banco.elenca_immagini(progetto),
                str(banco.elenca_immagini(progetto)),
            )
            check(
                "e viene rifiutato come percorso",
                banco.valida_foto(progetto, "/immagini/giro.png") is not None,
            )
            circolare.unlink(missing_ok=True)

        # 4) avvio con un byte NUL: rifiutato alla lettura, non in Popen
        dichiarazione = progetto / "contenuti.yaml"
        sano = dichiarazione.read_text(encoding="utf-8")
        dichiarazione.write_text(
            sano.replace("python3 -m http.server 4321", "python3\x00evil"), encoding="utf-8"
        )
        try:
            banco.carica(progetto)
            check("un avvio con NUL viene rifiutato", False, "nessun rifiuto")
        except Exception as errore:  # noqa: BLE001
            check(
                # PyYAML rifiuta un NUL come carattere non ammesso: il rifiuto c'e',
                # prima di Popen, con un messaggio. Il requisito e' quello.
                "un avvio con NUL viene rifiutato",
                "controllo" in str(errore) or "comando" in str(errore) or "non ammess" in str(errore) or "YAML" in str(errore),
                f"{type(errore).__name__}: {errore}",
            )
        dichiarazione.write_text(sano, encoding="utf-8")

        # 5) --inizia su una cartella non scrivibile: messaggio, non traceback
        non_scrivibile = Path(temporanea) / "9. Non Scrivibile"
        non_scrivibile.mkdir()
        os.chmod(non_scrivibile, 0o555)
        try:
            esito = esegui(non_scrivibile, "--inizia")
            check(
                "--inizia su una cartella non scrivibile non va in traceback",
                "Traceback" not in esito.stderr,
                esito.stderr[:200],
            )
            check(
                "e dice cosa controllare",
                "permess" in (esito.stdout + esito.stderr).lower(),
                (esito.stdout + esito.stderr)[:160],
            )
        finally:
            os.chmod(non_scrivibile, 0o755)

        # 6) --chiudi non uccide un processo estraneo
        vittima = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            (cartella_stato / "stato.json").write_text(
                json.dumps({"pid": vittima.pid, "porta": 4320}), encoding="utf-8"
            )
            esito = esegui(progetto, "--chiudi")
            check(
                # Il comportamento e' cambiato in meglio (QA di ENG-020, R4): la
                # scansione dei processi veri esclude gia' il pid estraneo, quindi non
                # serve «rifiutarlo» — si trova che non c'e' nessun banco di questo
                # progetto e si ripulisce lo stato. Cio' che conta e' che la VITTIMA
                # sopravviva, e quello si verifica sotto.
                "--chiudi non tocca un pid che non e' il banco",
                "non era piu' in esecuzione" in esito.stdout
                or "nessun banco" in esito.stdout.lower(),
                esito.stdout[:160],
            )
            check("e la vittima e' ancora viva", vittima.poll() is None, "il processo e' stato ucciso")
        finally:
            vittima.kill()
            vittima.wait(timeout=10)


def test_elenco_immagini() -> None:
    """`/api/immagini` elenca solo le immagini vere del progetto."""
    print("\nimmagini del progetto")
    with tempfile.TemporaryDirectory() as temporanea:
        progetto = crea_progetto_foto(Path(temporanea))
        trovate = banco.elenca_immagini(progetto)
        check("trova le due immagini", sorted(trovate) == ["/immagini/logo.png", "/immagini/team.jpg"], str(trovate))
        check("non elenca l'SVG", "/immagini/rotella.svg" not in trovate)
        check("non elenca il testo", "/immagini/note.txt" not in trovate)
        with server_di(progetto) as (_configurazione, porta):
            stato, corpo, _ = richiesta(porta, "GET", "/api/immagini", origine=None)
            check("la rotta risponde", stato == 200, stato)
            check("e riporta le immagini", sorted(corpo.get("immagini", [])) == ["/immagini/logo.png", "/immagini/team.jpg"], corpo)


def test_salvataggio_foto() -> None:
    """Salvare una foto scrive il percorso; una foto fuori dal progetto no."""
    print("\nsalvataggio di una foto")
    with tempfile.TemporaryDirectory() as temporanea:
        progetto = crea_progetto_foto(Path(temporanea))
        file_json = progetto / "dati" / "sito.json"
        prima = file_json.read_bytes()
        with server_di(progetto) as (_configurazione, porta):
            stato, corpo, _ = richiesta(
                porta, "POST", "/api/salva",
                {"percorso": "home.eroe.foto", "valore": "/immagini/logo.png"},
            )
            check("una foto valida viene salvata", stato == 200, corpo)
            dati = json.loads(file_json.read_text(encoding="utf-8"))
            check("il valore e' scritto", dati["home"]["eroe"]["foto"] == "/immagini/logo.png", dati)
            dopo = file_json.read_bytes()
            stato, corpo, _ = richiesta(
                porta, "POST", "/api/salva",
                {"percorso": "home.eroe.foto", "valore": "/etc/passwd.png"},
            )
            check("una foto fuori dal progetto e' rifiutata", stato == 422, corpo)
            check("e il file resta com'era", file_json.read_bytes() == dopo, "il file e' cambiato")
        check("il file non e' mai rimasto a meta'", prima != dopo)


def test_richiesta_all_ai() -> None:
    """`/api/richieste` registra un file e **non** tocca il contenuto."""
    print("\nrichiesta all'AI")
    with tempfile.TemporaryDirectory() as temporanea:
        progetto = crea_progetto_foto(Path(temporanea))
        file_json = progetto / "dati" / "sito.json"
        prima = file_json.read_bytes()
        with server_di(progetto) as (_configurazione, porta):
            stato, corpo, _ = richiesta(
                porta, "POST", "/api/richieste",
                {
                    "percorso": "home.eroe.titolo",
                    "istruzione": "Rendi il titolo piu' corto",
                    "foto": ["/immagini/team.jpg"],
                },
            )
            check("la richiesta viene accettata", stato == 201, corpo)
            check("e dice dove e' finita", "RIC-" in str(corpo.get("richiesta")), corpo)
            destinazione = progetto / corpo["richiesta"]
            check("il file esiste", destinazione.is_file(), str(destinazione))
            letto = json.loads(destinazione.read_text(encoding="utf-8"))
            check("contiene il percorso", letto.get("percorso") == "home.eroe.titolo", letto)
            check("contiene il valore attuale", letto.get("valore_attuale") == "Titolo", letto)
            check("contiene l'istruzione", letto.get("istruzione") == "Rendi il titolo piu' corto", letto)
            check("contiene la foto indicata", letto.get("foto") == ["/immagini/team.jpg"], letto)
            check("e resta in attesa", letto.get("stato") == "in attesa", letto)
            check("il contenuto non e' stato toccato", file_json.read_bytes() == prima, "il JSON e' cambiato")
            stato, corpo, _ = richiesta(
                porta, "POST", "/api/richieste",
                {"percorso": "home.eroe.titolo", "istruzione": "   "},
            )
            check("un'istruzione vuota e' rifiutata", stato == 422, corpo)
            stato, corpo, _ = richiesta(
                porta, "POST", "/api/richieste",
                {"percorso": "home.eroe.titolo", "istruzione": "cambia", "foto": ["/etc/passwd.jpg"]},
            )
            check("una foto fuori dal progetto e' rifiutata", stato == 422, corpo)
            stato, corpo, _ = richiesta(
                porta, "POST", "/api/richieste",
                {"percorso": "non.esiste", "istruzione": "cambia"},
            )
            check("un campo non dichiarato e' rifiutato", stato == 404, corpo)
            stato, corpo, _ = richiesta(
                porta, "POST", "/api/richieste",
                {"percorso": "home.eroe.titolo", "istruzione": "cambia"},
                origine=None,
            )
            check("senza Origin e' rifiutata", stato == 403, corpo)


def test_inizia() -> None:
    """`--inizia` crea la dichiarazione, e non sovrascrive quella che c'e'."""
    print("\ninizia: lo scaffold della shell")
    with tempfile.TemporaryDirectory() as temporanea:
        progetto = Path(temporanea) / "13. Progetto Nuovo"
        progetto.mkdir()
        esito = esegui(progetto, "--inizia")
        check("crea contenuti.yaml", (progetto / "contenuti.yaml").is_file(), esito.stderr)
        check("esce 0", esito.returncode == 0, esito.returncode)
        testo = (progetto / "contenuti.yaml").read_text(encoding="utf-8")
        check("spiega i tre tipi", "testo" in testo and "elenco" in testo and "foto" in testo, testo[:200])
        prima = testo
        esito = esegui(progetto, "--inizia")
        check("la seconda volta non sovrascrive", (progetto / "contenuti.yaml").read_text(encoding="utf-8") == prima)
        check("e lo dice", "esiste gia" in esito.stdout, esito.stdout)


def test_stato_del_servizio() -> None:
    """Lo stato su disco distingue un banco vivo da uno morto."""
    print("\nstato del servizio")
    with tempfile.TemporaryDirectory() as temporanea:
        progetto = crea_progetto(Path(temporanea))
        check("senza stato non c'e' niente", banco.stato_vivo(progetto) is None)
        cartella = progetto / ".banco"
        cartella.mkdir()
        (cartella / "stato.json").write_text(
            json.dumps({"pid": 999999999, "porta": 4320, "editor": "http://127.0.0.1:4320/"}) + "\n",
            encoding="utf-8",
        )
        check("un pid morto non e' un banco acceso", banco.stato_vivo(progetto) is None)
        # Un processo vivo ma innocuo: `sleep`. Non si usa il pid del test, perche'
        # `ferma_dal_file` manda il segnale al **gruppo** e fermerebbe la suite.
        import time as _time

        figlio = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        try:
            (cartella / "stato.json").write_text(
                json.dumps(
                    {"pid": figlio.pid, "porta": 4320, "editor": "http://127.0.0.1:4320/"}
                )
                + "\n",
                encoding="utf-8",
            )
            vivo = banco.stato_vivo(progetto)
            check("un pid vivo e' un banco acceso", vivo is not None and vivo.get("porta") == 4320, str(vivo))
            check("e il controllo del processo non mente", banco._processo_vivo(figlio.pid) is True)
        finally:
            figlio.terminate()
            figlio.wait(timeout=10)
        _time.sleep(0.2)
        check("un processo finito non e' piu' vivo", banco._processo_vivo(figlio.pid) is False)
        (cartella / "stato.json").unlink(missing_ok=True)
        fermato, messaggio = banco.ferma_dal_file(progetto)
        check("senza stato lo dice", fermato is False and "Nessun banco" in messaggio, messaggio)


def test_shell_apri_chiudi() -> None:
    """`--servizio` accende davvero, e `--chiudi` spegne e libera la porta."""
    print("\nshell: accendi, chiedi, spegni")
    with tempfile.TemporaryDirectory() as temporanea:
        progetto = crea_progetto_foto(Path(temporanea))
        sito = (
            "import http.server,socketserver,os\n"
            f"os.chdir({str(progetto)!r})\n"
            "socketserver.TCPServer.allow_reuse_address=True\n"
            "socketserver.TCPServer(('127.0.0.1',4397),http.server.SimpleHTTPRequestHandler)"
            ".serve_forever()\n"
        )
        (progetto / "sito.py").write_text(sito, encoding="utf-8")
        (progetto / "contenuti.yaml").write_text(
            DICHIARAZIONE_FOTO.replace("python3 -m http.server 4321", "python3 sito.py").replace(
                "4321", "4397"
            ),
            encoding="utf-8",
        )
        esito = esegui(progetto, "--servizio")
        check("il servizio parte", esito.returncode == 0, (esito.stdout + esito.stderr)[:400])
        stato_file = progetto / ".banco" / "stato.json"
        check("lo stato e' scritto", stato_file.is_file(), str(stato_file))
        dati = json.loads(stato_file.read_text(encoding="utf-8"))
        check("lo stato dice la porta", isinstance(dati.get("porta"), int), dati.get("porta"))
        check("lo stato elenca i campi foto", dati.get("campo_foto") == ["home.eroe.foto"], dati.get("campo_foto"))
        esito = esegui(progetto, "--stato")
        check("`--stato` dice acceso", esito.returncode == 0 and "editor" in esito.stdout, esito.stdout)
        esito = esegui(progetto, "--chiudi")
        check("`--chiudi` ferma", esito.returncode == 0, (esito.stdout + esito.stderr)[:300])
        check("lo stato sparisce", not stato_file.exists())
        esito = esegui(progetto, "--chiudi")
        check("chiudere due volte non e' un errore grave", esito.returncode in (0, 1), esito.returncode)


def _nodi_proibiti(sorgente: str) -> list[tuple[int, str, str]]:
    """Le chiamate proibite nel sorgente: ``(riga, funzione, descrizione)``.

    Si analizza l'**AST**, non il testo: un filtro testuale si aggira con `A = 1; f()`,
    con `from subprocess import Popen`, con un alias di modulo, o con una riga che
    comincia con una stringa. Il revisore di ENG-020 l'ha dimostrato; questa e' la
    risposta, e la ragione per cui non c'e' piu' una regex.
    """
    import ast

    albero = ast.parse(sorgente)

    #: (modulo, attributo) che devono stare solo nei portieri. `None` come attributo
    #: significa «il nome nudo», per gli import diretti.
    proibiti = {
        ("json", "loads"), ("json", "dumps"),
        ("subprocess", "Popen"),
        ("os", "kill"), ("os", "killpg"), ("os", "remove"), ("os", "unlink"),
    }
    #: I metodi di Path che leggono o scrivono.
    metodi_path = {"read_text", "write_text", "read_bytes", "write_bytes", "resolve"}

    #: Il nome di ogni nodo, per sapere dove siamo.
    class Visitatore(ast.NodeVisitor):
        def __init__(self) -> None:
            self.pila: list[str] = []
            self.trovati: list[tuple[int, str, str]] = []
            self.alias: dict[str, str] = {}

        def _dove(self) -> str:
            return ".".join(self.pila) if self.pila else "<modulo>"

        def visit_ClassDef(self, nodo: ast.ClassDef) -> None:
            self.pila.append(nodo.name)
            self.generic_visit(nodo)
            self.pila.pop()

        def visit_ImportFrom(self, nodo: ast.ImportFrom) -> None:
            for nome in nodo.names:
                if nodo.module:
                    self.alias[nome.asname or nome.name] = f"{nodo.module}.{nome.name}"
            self.generic_visit(nodo)

        def visit_Import(self, nodo: ast.Import) -> None:
            for nome in nodo.names:
                self.alias[nome.asname or nome.name.split(".")[0]] = nome.name
            self.generic_visit(nodo)

        def visit_FunctionDef(self, nodo: ast.FunctionDef) -> None:
            self.pila.append(nodo.name)
            self.generic_visit(nodo)
            self.pila.pop()

        visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

        def visit_Call(self, nodo: ast.Call) -> None:
            descrizione = self._descrizione(nodo.func)
            if descrizione is not None:
                self.trovati.append((nodo.lineno, self._dove(), descrizione))
            self.generic_visit(nodo)

        def _descrizione(self, funzione: ast.expr) -> str | None:
            if isinstance(funzione, ast.Name):
                # un nome importato direttamente: `from subprocess import Popen`
                risolto = self.alias.get(funzione.id)
                if risolto and risolto.split(".")[0] in ("json", "subprocess", "os"):
                    modulo, _, attributo = risolto.rpartition(".")
                    if (modulo, attributo) in proibiti or funzione.id in (
                        "loads", "dumps", "Popen", "kill", "killpg", "open"
                    ):
                        return f"{modulo}.{attributo}"
                if funzione.id == "open":
                    return "open"
                # `getattr(oggetto, "read_" + "text")`: il nome del metodo e' costruito a
                # runtime, quindi l'analisi statica non lo legge. Non si indovina: si
                # dichiara che l'operazione non e' verificabile. Era il buco che la prova
                # in negativo ha trovato in R4 — il controllo non aveva questo ramo, e
                # l'iniezione con `getattr` passava senza essere vista.
                if funzione.id == "getattr":
                    return "getattr"
                return None
            if isinstance(funzione, ast.Attribute):
                if isinstance(funzione.value, ast.Name):
                    base = self.alias.get(funzione.value.id, funzione.value.id)
                    base = base.split(".")[0]
                    if (base, funzione.attr) in proibiti:
                        return f"{base}.{funzione.attr}"
                    # `Path(...).read_text()`: il metodo sta su qualunque oggetto
                    if funzione.attr in metodi_path:
                        return funzione.attr
                else:
                    if funzione.attr in metodi_path:
                        return funzione.attr
            return None

    visitatore = Visitatore()
    visitatore.visit(albero)
    return visitatore.trovati


#: Dove un'operazione e' ammessa, per **coppia** (funzione, operazione).
#: Non e' una whitelist di funzioni: `Processi.vivo` puo' fare `os.kill`, ma non
#: `write_text`; `Uscita.corpo` puo' fare `json.dumps`, ma non `os.kill`.
_AMMESSI: frozenset[tuple[str, str]] = frozenset({
    ("Portiere.file_json", "json.loads"),
    ("Portiere.file_json", "read_text"),
    ("Portiere.leggi_testo", "read_bytes"),
    ("Portiere.leggi_testo_utf8", "read_text"),
    ("Portiere.leggi_bytes", "read_bytes"),
    ("Portiere.corpo_json", "json.loads"),
    ("Portiere.risolvi", "resolve"),
    ("Portiere.cartella_esistente", "resolve"),
    ("Uscita.corpo", "json.dumps"),
    ("Uscita.scrivi_json", "json.dumps"),
    ("Uscita.scrivi_file", "write_text"),
    ("Uscita.riscrivi_json", "read_text"),
    ("Uscita.apri_log", "open"),
    ("Uscita.json_breve", "json.dumps"),
    ("Uscita._indentazione", "read_text"),
    ("Processi.vivo", "os.kill"),
    ("Processi.avvia", "subprocess.Popen"),
    ("Processi.ferma", "os.kill"),
    ("Processi.ferma", "os.killpg"),
    ("Processi.ferma_gruppo", "os.killpg"),
    ("_dentro", "resolve"),
    ("_risolvi_progetto", "resolve"),
    ("_prendi_possesso", "open"),
    ("_prendi_possesso", "os.remove"),
    ("cancella_stato", "os.unlink"),
    ("_propio_file", "resolve"),
})


def _proibiti_fuori_dai_portieri(
    sorgente: str, ammessi: set[tuple[str, str]] | None = None
) -> list[str]:
    """Le operazioni che il contract dichiara confinate e che stanno altrove.

    E' il **filtro**, separato dalla scoperta: `_nodi_proibiti` dice cosa c'e' nel file,
    questa dice cosa non doveva esserci. La distinzione conta per la prova in negativo:
    se si indebolisce `metodi_path` dentro `_nodi_proibiti` — cioe' si spegne la
    sorveglianza su un'operazione — questa funzione lo vede, e la suite fallisce.
    Prima non succedeva, e una regressione della difesa restava muta (Code Review R4).
    """
    import re

    if ammessi is None:
        ammessi = _AMMESSI
    righe = sorgente.splitlines()
    fuori: list[str] = []
    for riga, dove, descrizione in _nodi_proibiti(sorgente):
        if (dove, descrizione) in ammessi:
            continue
        # Le costanti di modulo sono lette una volta all'import e non sono pilotabili
        # da fuori: `_FILE = Path(__file__).resolve()`.
        if dove == "<modulo>" and re.match(r"^_?[A-Z][A-Z0-9_]*\s*=", righe[riga - 1].strip()):
            continue
        fuori.append(f"riga {riga} in {dove}: {descrizione}")
    return fuori


def test_architettura_due_portieri(percorso: Path | None = None) -> None:
    """La classe dei difetti non si riapre: letture e scritture passano dai portieri.

    Questa e' la ragione per cui il banco e' stato riscritto (DEC-0091). Sei revisioni
    respinte, sempre per un ingresso o un'uscita che il codice presumeva innocuo.

    Il controllo e' su **AST**, non su testo: la versione a espressioni regolari si
    aggirava con `A = 1; f()`, con un import diretto o con un alias di modulo — e il
    revisore di ENG-020 l'ha dimostrato tre volte. E la copertura e' per
    **(funzione, operazione)**, non per nome di funzione: avere `Popen` dentro
    `_propio_file` non e' «un portiere che fa il suo mestiere».
    """
    print("\narchitettura: i portieri, e solo loro")

    sorgente = (percorso or ROOT / "tools" / "banco.py").read_text(encoding="utf-8")
    trovati = _nodi_proibiti(sorgente)

    ammessi = _AMMESSI

    # Le costanti di modulo (riga che assegna un NOME MAIUSCOLO) sono lette una volta
    # all'import e non sono pilotabili da fuori: `_FILE = Path(__file__).resolve()`.
    righe = sorgente.splitlines()
    # Il filtro e' una funzione a se' perche' la prova in negativo deve poterlo
    # interrogare: scoprire un nodo non basta, conta se finisce fra i proibiti.
    # (R4, terza versione della prova: vedi `test_architettura_negativo`.)
    fuori = _proibiti_fuori_dai_portieri(sorgente, ammessi)
    check(
        "nessuna lettura, scrittura o operazione sui processi fuori dal suo portiere",
        not fuori,
        "Il permesso e' per COPPIA (funzione, operazione): aggiungere `Popen` in una "
        "funzione che non e' `Processi.avvia` non e' «un portiere che fa il suo mestiere». "
        "Trovate:\n  " + "\n  ".join(fuori),
    )
    check("ci sono i tre portieri", all(
        f"class {nome}" in sorgente for nome in ("Portiere", "Uscita", "Processi")
    ))

    # IL PONTE FRA IL FILTRO E CHI LO USA.
    #
    # Il Code Review di R4 ha smontato questa difesa tre volte, e l'ultima e' la piu'
    # istruttiva: neutralizzando `fuori = []` qui sopra, la suite passava lo stesso —
    # 227 controlli, esito 0. Perche'? Perche' `_proibiti_fuori_dai_portieri` restava
    # corretta: era il **test** a non usarla. Il filtro giusto, il collegamento assente.
    #
    # Un controllo che verifica il filtro non verifica l'impianto. Questo lo fa: legge il
    # proprio sorgente e pretende che il risultato del filtro venga usato davvero, non
    # buttato via. Se qualcuno scrive `fuori = []`, questa riga lo vede.
    # Si guarda il CODICE, non il testo: cercare la stringa dentro il proprio sorgente
    # trova anche... la stringa di questo controllo, e si autocertifica. Si analizza
    # l'AST e si verifica che in `test_architettura_due_portieri` ci sia un'assegnazione
    # a `fuori` il cui valore e' una **chiamata** a `_proibiti_fuori_dai_portieri`.
    # Con `fuori = []` il valore e' una lista vuota, e il controllo fallisce.
    import ast as _ast

    proprio = Path(__file__).read_text(encoding="utf-8")
    collegato = False
    for nodo in _ast.walk(_ast.parse(proprio)):
        if not isinstance(nodo, _ast.FunctionDef) or nodo.name != "test_architettura_due_portieri":
            continue
        for interno in _ast.walk(nodo):
            if not isinstance(interno, _ast.Assign):
                continue
            if not any(isinstance(t2, _ast.Name) and t2.id == "fuori" for t2 in interno.targets):
                continue
            valore = interno.value
            if isinstance(valore, _ast.Call) and isinstance(valore.func, _ast.Name):
                if valore.func.id == "_proibiti_fuori_dai_portieri":
                    collegato = True
    check(
        "il filtro e' davvero collegato al controllo (non neutralizzato)",
        collegato,
        "il risultato del filtro non viene usato: la difesa e' scritta ma spenta. "
        "E' la prova (b) del Code Review di R4: `fuori = []` faceva passare tutto.",
    )

    # Le soglie del contract, **misurate**. Erano state perse nella riscrittura del controllo
    # ad AST: il QA di ENG-020 l'ha visto (225 -> 223 controlli, e il numero non deve scendere).
    righe = sorgente.splitlines()
    codice = [r for r in righe if r.strip() and not r.strip().startswith("#")]
    check(
        "il file non e' cresciuto (era 2.244 righe)",
        len(righe) < 2100,
        f"{len(righe)} righe",
    )
    check(
        "il codice vero e' sotto 1.800 (era 1.893)",
        len(codice) < 1800,
        f"{len(codice)} righe di codice non-commento",
    )


def test_architettura_negativo() -> None:
    """Il test di architettura **funziona**? Si prova ingannandolo.

    Un controllo che non e' mai stato visto fallire non e' un controllo: e' una speranza.
    Il revisore di ENG-020 l'ha contestato per questo (e aveva ragione: la dichiarazione
    di commit diceva «provato in negativo» mentre la prova non c'era). Qui si fa davvero,
    su copie in /tmp: per **ogni** pattern sorvegliato si inietta la chiamata in una
    funzione qualunque e si verifica che il controllo la veda.
    """
    print("\narchitettura: il controllo sa fallire?")
    import shutil
    import subprocess as _sp

    sorgente = ROOT / "tools" / "banco.py"
    prove = (
        ("read_text", "Path('x').read_text()"),
        ("write_text", "Path('x').write_text('y')"),
        ("read_bytes", "Path('x').read_bytes()"),
        ("json.loads", "json.loads('{}')"),
        ("json.dumps", "json.dumps({})"),
        ("Popen", "subprocess.Popen(['echo'])"),
        ("os.kill", "os.kill(1, 0)"),
        ("os.killpg", "os.killpg(1, 0)"),
        ("resolve", "Path('.').resolve()"),
        ("open nudo", "open('/tmp/x')"),
        ("getattr", "getattr(Path('x'), 'read_' + 'text')()"),
    )
    for etichetta, iniezione in prove:
        with tempfile.TemporaryDirectory() as temporanea:
            base = Path(temporanea)
            (base / "tools").mkdir()
            (base / "tests").mkdir()
            copia = base / "tools" / "banco.py"
            shutil.copyfile(sorgente, copia)
            testo = copia.read_text(encoding="utf-8")
            marcatore = "def _esempio_dichiarazione() -> str:"
            if marcatore not in testo:
                marcatore = "def leggi_dichiarazione("
            testo = testo.replace(marcatore, marcatore + "\n    _iniettata = " + iniezione, 1)
            copia.write_text(testo, encoding="utf-8")
            # SI INTERROGA IL FILTRO VERO, non un controllo ombra e non la sola scoperta.
            #
            # Due versioni precedenti di questa prova erano mute, e il Code Review di R4
            # le ha smontate entrambe: la prima lanciava `--solo-architettura`, un
            # controllo testuale che falliva anche sul sorgente INTATTO; la seconda
            # interrogava `_nodi_proibiti`, che elenca le chiamate ma non applica la
            # tabella dei permessi — e togliendo `read_text` da `metodi_path`, cioe'
            # spegnendo la sorveglianza su un'operazione che il criterio nomina, la suite
            # passava lo stesso con 227 controlli ed esito 0.
            #
            # Ora si chiama `_proibiti_fuori_dai_portieri`: scopre E filtra. Se il
            # controllo perde un'operazione, l'iniezione non finisce fra i proibiti e
            # questa prova fallisce.
            import importlib.util

            nome_modulo = f"controllo_prova_{abs(hash(etichetta))}"
            specifica = importlib.util.spec_from_file_location(
                nome_modulo, ROOT / "tests" / "test_banco.py"
            )
            modulo = importlib.util.module_from_spec(specifica)
            sys.modules[nome_modulo] = modulo
            try:
                specifica.loader.exec_module(modulo)
            finally:
                sys.modules.pop(nome_modulo, None)
            proibiti = modulo._proibiti_fuori_dai_portieri(copia.read_text(encoding="utf-8"))
            check(
                f"il controllo vede {etichetta} iniettato fuori dai portieri",
                bool(proibiti),
                f"il controllo non ha visto {etichetta}: non difende la classe",
            )
            # E BISOGNA CHE A QUALCUNO IMPORTI. Interrogare la funzione non basta: se
            # `test_architettura_due_portieri` smettesse di chiamarla — o ne ignorasse il
            # risultato — la prova sopra passerebbe lo stesso, e la difesa resterebbe
            # scritta ma spenta. E' la prova (b) del Code Review di R4: neutralizzando
            # `fuori = []`, la suite diceva «PASS — 227, esito 0». Ora anche questo si vede.
            # E il controllo VERO — `test_architettura_due_portieri` — deve fallire sulla
            # stessa copia. Non basta che `_proibiti_fuori_dai_portieri` veda la
            # violazione: se il test che la usa ne ignorasse il risultato (`fuori = []`),
            # la difesa resterebbe scritta ma spenta. E' la prova (b) del Code Review R4:
            # neutralizzando `fuori = []`, la suite diceva «PASS — 227, esito 0».
            # Il controllo si esegue su una copia di QUESTO file, non su quello vero:
            # cosi' la prova vede anche una regressione del test stesso — se qualcuno
            # neutralizza il filtro (`fuori = []`), la copia lo riflette e il codice
            # d'uscita non e' piu' 0. Con il file vero, quella regressione restava muta
            # (prova (b) del Code Review R4).
            copia_controllo = base / "controllo_portieri.py"
            shutil.copyfile(ROOT / "tests" / "test_banco.py", copia_controllo)
            esito_suite = _sp.run(
                [
                    sys.executable,
                    str(copia_controllo),
                    "--solo-portieri",
                    str(copia),
                ],
                cwd=str(base),
                capture_output=True,
                text=True,
                timeout=180,
            )
            check(
                f"e il controllo vero fallisce sulla stessa violazione ({etichetta})",
                esito_suite.returncode != 0,
                "il controllo vero passa con una violazione iniettata: non presidia niente",
            )


def test_il_file_dei_contenuti_sta_dentro() -> None:
    """Il file dei contenuti non esce dal progetto, nemmeno via collegamento.

    Il finding P2 del gate di ENG-020: `_valida` controllava `..` e la radice sul
    percorso **scritto**, non su quello che il filesystem risolve. Un symlink dentro il
    progetto puntava fuori, e `GET /api/contenuti` serviva il file esterno con 200.

    La scrittura non usciva — ma per caso, perche' `os.replace` sostituisce il
    collegamento. Una difesa che regge per caso e' una difesa che invecchia male.
    """
    print("\nil file dei contenuti sta dentro il progetto")
    import tempfile

    with tempfile.TemporaryDirectory() as cartella:
        base = Path(cartella)
        progetto = crea_progetto(base)
        segreto = base / "segreto.json"
        segreto.write_text('{"saluto": "RISERVATO"}', encoding="utf-8")
        collegamento = progetto / "dati" / "collegato.json"
        if collegamento.exists():
            collegamento.unlink()
        collegamento.symlink_to(segreto)
        dichiarazione = (progetto / "contenuti.yaml").read_text(encoding="utf-8")
        (progetto / "contenuti.yaml").write_text(
            dichiarazione.replace("dati/sito.json", "dati/collegato.json"), encoding="utf-8"
        )
        try:
            banco.carica(progetto)
            check("un collegamento che esce dal progetto e' rifiutato", False, "e' stato accettato")
        except banco.ErroreConfig as errore:
            check(
                "un collegamento che esce dal progetto e' rifiutato",
                "fuori dal progetto" in str(errore),
                str(errore)[:120],
            )
        # e il caso legittimo non si tocca
        (progetto / "contenuti.yaml").write_text(dichiarazione, encoding="utf-8")
        try:
            banco.carica(progetto)
            check("un file vero dentro il progetto resta valido", True)
        except banco.ErroreConfig as errore:
            check("un file vero dentro il progetto resta valido", False, str(errore)[:120])


def test_richieste_in_attesa() -> None:
    """Le richieste del pannello sono un ponte: si leggono, e non si perdono.

    Il criterio 10 di ENG-020, riformulato (DEC-0098), chiede che **ogni funzione nuova
    degli editor sia coperta da un test**. Questa e' quella funzione: il pannello registra
    una richiesta, `--richieste` la mostra, e una richiesta esaudita o rifiutata non
    compare piu'. Senza il test, il criterio sarebbe una promessa senza prova.
    """
    print("\nrichieste del pannello: il ponte fra editor e chat")
    import tempfile

    with tempfile.TemporaryDirectory() as cartella:
        base = Path(cartella)
        progetto = crea_progetto(base)
        configurazione = banco.carica(progetto)

        check("senza cartella, nessuna richiesta", banco.richieste_in_attesa(configurazione) == [])

        # una richiesta vera, registrata come fa il server
        percorso = banco.registra_richiesta(
            configurazione, "home.eroe.titolo", "cambia il titolo", []
        )
        attese = banco.richieste_in_attesa(configurazione)
        check("una richiesta registrata si vede", len(attese) == 1, str(attese))
        if attese:
            check(
                "e dice quale campo e cosa chiede",
                attese[0].get("percorso") == "home.eroe.titolo"
                and "titolo" in str(attese[0].get("istruzione")),
                str(attese[0])[:120],
            )
            check("nasce «in attesa»", attese[0].get("stato") == "in attesa")

        # esaudita: non e' piu' in attesa
        import json

        dati = json.loads(percorso.read_text(encoding="utf-8"))
        dati["stato"] = "esaudita"
        percorso.write_text(json.dumps(dati), encoding="utf-8")
        check(
            "una richiesta esaudita non e' piu' in attesa",
            banco.richieste_in_attesa(configurazione) == [],
        )

        # rifiutata: idem
        dati["stato"] = "rifiutata"
        percorso.write_text(json.dumps(dati), encoding="utf-8")
        check(
            "una richiesta rifiutata non e' piu' in attesa",
            banco.richieste_in_attesa(configurazione) == [],
        )

        # un file rotto non fa cadere la lettura
        (progetto / "Analisi-Prompt-Report" / "Richieste" / "RIC-rotto.json").write_text(
            "non sono json", encoding="utf-8"
        )
        check(
            "un file rotto non fa cadere la lettura",
            isinstance(banco.richieste_in_attesa(configurazione), list),
        )


def main() -> int:
    """Run the suite."""
    print("banco: dichiarazione, permesso, scrittura atomica")
    test_dichiarazione_mancante()
    test_progetto_inesistente()
    test_yaml_non_valido()
    test_dichiarazione_non_leggibile()
    test_contenuti_json_non_valido()
    test_percorso_non_valido()
    test_forma_dell_esempio()
    test_aiuto()
    test_letture()
    test_solo_loopback()
    test_percorso_fuori_allowlist()
    test_corpo_troppo_grande()
    test_origine()
    test_tipi()
    test_percorso_sparito_dal_file()
    test_scrittura_atomica()
    test_scrittura_fallita_non_tocca_il_file()
    test_foto_valida_e_rifiutati()
    test_il_file_dei_contenuti_sta_dentro()
    test_richieste_in_attesa()
    test_un_messaggio_non_uccide_la_risposta()
    test_un_json_annidato_non_uccide_la_risposta()
    test_le_quattro_porte_della_classe()
    test_i_sei_difetti_di_robustezza()
    test_architettura_due_portieri()
    test_architettura_negativo()
    test_elenco_immagini()
    test_salvataggio_foto()
    test_richiesta_all_ai()
    test_inizia()
    test_stato_del_servizio()
    test_shell_apri_chiudi()
    print(f"PASS — {PASSED} controlli sul banco")
    return 0


if __name__ == "__main__":
    if "--solo-portieri" in sys.argv:
        # Esegue SOLO il controllo dei portieri, quello VERO, sul sorgente di `banco.py`.
        # Esce 1 se trova una violazione. Sostituisce il vecchio `--solo-architettura`,
        # che era un controllo OMBRA testuale, diverso dall'AST: falliva anche sul
        # sorgente intatto, e per questo la prova in negativo non provava niente
        # (Code Review R4, prove (a) e (b)).
        from pathlib import Path as _P

        # Il percorso si puo' passare: la prova in negativo gli da' la COPIA iniettata,
        # non l'albero vero. Senza, il controllo passerebbe sempre — che e' esattamente
        # il difetto della versione ombra.
        _indice = sys.argv.index("--solo-portieri")
        _percorso = (
            _P(sys.argv[_indice + 1])
            if len(sys.argv) > _indice + 1 and not sys.argv[_indice + 1].startswith("-")
            else _P(__file__).resolve().parents[1] / "tools" / "banco.py"
        )
        # Si esegue IL TEST VERO (`test_architettura_due_portieri`), non il solo filtro.
        # La differenza e' tutta qui: se qualcuno neutralizza il risultato del filtro
        # dentro il test (`fuori = []`), il filtro resta corretto e la prova sarebbe muta.
        # Eseguendo il test, quella regressione fa fallire il codice d'uscita.
        try:
            test_architettura_due_portieri(_percorso)
        except AssertionError as errore:
            print(f"FALLITO: {errore}")
            raise SystemExit(1) from None
        raise SystemExit(0)

    raise SystemExit(main())
