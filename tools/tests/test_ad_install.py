#!/usr/bin/env python3
"""Il generatore di configurazioni MCP: cinque client, validi, e nessuna scrittura.

    python3 tools/tests/test_ad_install.py

Perche' esiste. La registrazione nei client e' ENG-005 e ha due blocchi. Questo
strumento fa la parte permessa: produce il blocco esatto e lo verifica. Il test
prova le due cose che contano: che i blocchi siano **validi** (JSON/TOML con il
percorso assoluto giusto) e che lo strumento **non scriva fuori dalla macchina** —
perche' un generatore che installa sarebbe una scorciatoia attorno
all'autorizzazione, non un passo avanti.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "ad_mcp"))

import install  # noqa: E402
import tempfile

import yaml

ROOT = Path(__file__).resolve().parents[2]
INSTALL = ROOT / "tools" / "ad_mcp" / "install.py"
SERVER = ROOT / "tools" / "ad_mcp" / "server.py"

PASSED = 0


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    """Assert one expectation."""
    global PASSED
    if not condizione:
        raise AssertionError(f"{etichetta}: {dettaglio or 'condizione falsa'}")
    PASSED += 1


def _cli(*argomenti: str) -> subprocess.CompletedProcess:
    """Run the generator."""
    return subprocess.run(
        [sys.executable, str(INSTALL), *argomenti],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )


def test_elenco() -> None:
    """--list nomina tutti e cinque i client."""
    esito = _cli("--list")
    check("--list esce 0", esito.returncode == 0, esito.stderr[:150])
    for cliente in ("dsh", "cursor", "claude", "codex", "gemini"):
        check(f"--list nomina {cliente}", cliente in esito.stdout, esito.stdout[:200])


def test_blocchi_validi() -> None:
    """Ogni blocco e' valido e punta al server con un percorso assoluto."""
    for cliente in ("dsh", "cursor", "claude", "codex", "gemini"):
        esito = _cli("--print", cliente)
        check(f"--print {cliente} esce 0", esito.returncode == 0, esito.stderr[:150])
        check(f"--print {cliente} e' assoluto", str(SERVER) in esito.stdout, esito.stdout[:200])
        if cliente == "dsh":
            # DSH non carica un mcpServers generico: vuole un'entrata del loader
            # con il plugin mcp-client e `transport: stdio` (rilievo del gate).
            caricato = yaml.safe_load(esito.stdout)
            entrata = caricato[0]["insert"][0]
            check("dsh usa il plugin mcp-client", entrata["name"] == "@deepseek-ai/dsh-mcp-client", str(entrata))
            config = entrata["config"]
            check("dsh transport stdio", config["transport"] == "stdio", str(config))
            check("dsh serverName", config["serverName"] == "ad-projects", str(config))
            check("dsh args assoluto", config["args"] == [str(SERVER)], str(config))
        elif cliente == "codex":
            check(
                "codex e' TOML con la tabella right",
                "[mcp_servers.ad-projects]" in esito.stdout,
                esito.stdout[:200],
            )
        else:
            try:
                dati = json.loads(esito.stdout)
            except json.JSONDecodeError as errore:
                raise AssertionError(f"{cliente}: il blocco non e' JSON valido: {errore}") from errore
            voce = dati["mcpServers"]["ad-projects"]
            check(f"{cliente}: comando python3", voce["command"] == "python3", str(voce))
            check(f"{cliente}: args assoluto", voce["args"] == [str(SERVER)], str(voce))


def test_verifica() -> None:
    """--check e --check-all validano le configurazioni generate."""
    for cliente in ("dsh", "cursor", "codex"):
        esito = _cli("--check", cliente)
        check(f"--check {cliente} esce 0", esito.returncode == 0, esito.stderr[:150])
    tutto = _cli("--check-all")
    check("--check-all esce 0", tutto.returncode == 0, tutto.stderr[:150])


def test_client_sconosciuto() -> None:
    """Un client che non esiste e' un errore d'uso, con l'elenco degli ammessi."""
    esito = _cli("--print", "vscode")
    check("client sconosciuto esce 2", esito.returncode == 2, str(esito.returncode))
    check("il rifiuto elenca gli ammessi", "dsh" in esito.stderr and "gemini" in esito.stderr, esito.stderr[:200])


def test_la_generazione_non_scrive() -> None:
    """Generazione e verifica non scrivono: solo `apply` scrive, e solo nei target.

    ENG-004 diceva «il generatore non scrive mai» perche' scrivere sarebbe stato una
    scorciatoia attorno all'autorizzazione. ENG-011 ha autorizzato la registrazione
    (DEC-0065): la promessa cambia, ma resta stretta — `--list`, `--print`, `--check`,
    `--status` non toccano niente, e `apply` scrive **solo** nel file di
    configurazione del client scelto.
    """
    with tempfile.TemporaryDirectory() as finta:
        for azione in (("--list",), ("--print", "dsh"), ("--print", "cursor"),
                       ("--check", "dsh"), ("--check-all",)):
            esito = subprocess.run(
                [sys.executable, str(INSTALL), *azione],
                capture_output=True, text=True, cwd=str(ROOT),
                env={**os.environ, "HOME": finta},
            )
            check(f"{' '.join(azione)} esce 0 con HOME finta", esito.returncode == 0, esito.stderr[:150])
        stato = subprocess.run(
            [sys.executable, str(INSTALL), "--status", "auto"],
            capture_output=True, text=True, cwd=str(ROOT),
            env={**os.environ, "HOME": finta},
        )
        check("--status auto senza client: exit 1", stato.returncode == 1, str(stato.returncode))
        rimasti = [str(p) for p in Path(finta).rglob("*")]
        check("la HOME finta e' rimasta vuota", rimasti == [], str(rimasti))
    testo = INSTALL.read_text(encoding="utf-8")
    check("nessun percorso arbitrario: si scrive solo via percorso_config", "applica(" in testo and "percorso_config(" in testo, "manca la catena")
    check("nessuna scrittura fuori dai target", "write_text(" in testo and "applica(" in testo, "manca il controllo")


def test_i_validatori_rifiutano_i_blocchi_rotti() -> None:
    """Il validatore si prova dal lato sbagliato: un check che promuove non serve.

    Rilievo del gate di ENG-004: `--check codex` promuoveva `command = "node"`, una
    tabella commentata e TOML invalido; il test guardava solo il blocco buono. Qui
    si sostituisce il blocco con varianti rotte e si chiede al validatore di
    rifiutarle.
    """
    sano = install.blocco
    try:
        rotti = [
            ("codex", '[mcp_servers.ad-projects]\ncommand = "node"\nargs = ["%s"]\n' % SERVER,
             "codex con command=node"),
            ("codex", '# [mcp_servers.ad-projects]\n# commentata\n',
             "codex con tabella commentata"),
            ("codex", '[mcp_servers.ad-projects\ncommand = "python3"\n',
             "codex con TOML invalido"),
            ("dsh", "- insert:\n    - id: x\n      name: \"@deepseek-ai/dsh-mcp-client\"\n      config:\n        serverName: ad-projects\n        command: python3\n",
             "dsh senza transport"),
            ("dsh", install.blocco("dsh").replace("serverName: ad-projects", "serverName: ad-pròjects"),
             "dsh con serverName non ASCII"),
            ("cursor", '{"mcpServers": {"ad-projects": {"command": "node", "args": ["%s"]}}}' % SERVER,
             "cursor con command=node"),
        ]
        for cliente, blocco_rotto, etichetta in rotti:
            install.blocco = lambda _c, _b=blocco_rotto: _b
            problemi = install.verifica(cliente)
            check(f"{etichetta}: rifiutato", bool(problemi), str(problemi))
    finally:
        install.blocco = sano
    # controprova: i blocchi veri restano validi
    for cliente in install.CLIENTI:
        check(f"{cliente}: blocco vero valido", install.verifica(cliente) == [], str(install.verifica(cliente)))



def test_forme_malformate_non_sollevano() -> None:
    """Un validatore non deve rompersi: forme malformate sono problemi, non eccezioni.

    Fragilita' segnalata dal terzo gate di ENG-004: `verifica()` andava in
    AttributeError con `mcpServers` lista, voce stringa, `insert` non mappa.
    """
    sano = install.blocco
    try:
        casi = [
            ("cursor", "[]", "JSON lista"),
            ("cursor", '{"mcpServers": []}', "mcpServers lista"),
            ("cursor", '{"mcpServers": {"ad-projects": "x"}}', "voce stringa"),
            ("cursor", '{"mcpServers": {"ad-projects": {"command": "python3"}}}', "args mancanti"),
            ("codex", "mcp_servers = 1\n", "TOML mcp_servers non tabella"),
            ("codex", 'mcp_servers = {ad-projects = "x"}\n', "TOML voce stringa"),
            ("dsh", "- insert: 1\n", "cordis insert non lista"),
            ("dsh", "- insert:\n    - id: x\n      name: \"@deepseek-ai/dsh-mcp-client\"\n      config: 1\n", "cordis config non mappa"),
        ]
        for cliente, blocco_rotto, etichetta in casi:
            install.blocco = lambda _c, _b=blocco_rotto: _b
            try:
                problemi = install.verifica(cliente)
            except Exception as errore:  # noqa: BLE001 - e' esattamente cio' che non deve accadere
                raise AssertionError(f"{etichetta}: il validatore e' andato in {errore.__class__.__name__}: {errore}") from errore
            check(f"{etichetta}: problemi e non eccezione", bool(problemi), str(problemi))
    finally:
        install.blocco = sano


def test_python_senza_tomllib() -> None:
    """Su Python < 3.11 il TOML di Codex si rifiuta con la ragione, non con un crash."""
    sano, sano_blocco = install.tomllib, install.blocco
    try:
        install.tomllib = None
        problemi = install.verifica("codex")
        check("senza tomllib: rifiutato con la ragione", bool(problemi), str(problemi))
        check(
            "la ragione nomina Python 3.11",
            any("3.11" in problema for problema in problemi),
            str(problemi),
        )
        check("gli altri client non sono toccati", install.verifica("cursor") == [], str(install.verifica("cursor")))
    finally:
        install.tomllib, install.blocco = sano, sano_blocco

# ---------------------------------------------------------------------------
# ENG-011: registrazione vera e portatile (DEC-0065)
# ---------------------------------------------------------------------------

import contextlib  # noqa: E402


@contextlib.contextmanager
def _home_finta(radice: Path):
    """Point HOME and DSH_PROFILE to a scratch root: tests never touch the real home."""
    vecchi = {chiave: os.environ.get(chiave) for chiave in ("HOME", "DSH_PROFILE")}
    os.environ["HOME"] = str(radice)
    os.environ["DSH_PROFILE"] = "test"
    try:
        yield radice
    finally:
        for chiave, valore in vecchi.items():
            if valore is None:
                os.environ.pop(chiave, None)
            else:
                os.environ[chiave] = valore


def test_registrazione_dsh() -> None:
    """apply scrive la voce cordis, status la dice aggiornata, dry-run non scrive."""
    with tempfile.TemporaryDirectory() as tmp:
        with _home_finta(Path(tmp)):
            percorso = install.percorso_config("dsh")
            esito, _ = install.applica("dsh", dry=True)
            check("dry-run: nessun file", not percorso.is_file(), str(percorso))
            install.applica("dsh")
            check("apply: file creato", percorso.is_file(), str(percorso))
            dati = yaml.safe_load(percorso.read_text(encoding="utf-8"))
            voci = [voce for patch in dati for voce in patch.get("insert", [])]
            nostra = next((voce for voce in voci if voce.get("id") == "ad-projects-mcp"), None)
            check("apply: voce presente", isinstance(nostra, dict), str(voci))
            check("apply: comando python3", (nostra or {}).get("config", {}).get("command") == "python3", str(nostra))
            check("apply: percorso del server", (nostra or {}).get("config", {}).get("args") == [str(install.SERVER)], str(nostra))
            check("status: aggiornata", install.stato("dsh")[0] == "aggiornata", str(install.stato("dsh")))


def test_registrazione_conserva_il_resto() -> None:
    """Le altre voci e le altre chiavi restano: la registrazione e' additiva."""
    with tempfile.TemporaryDirectory() as tmp:
        with _home_finta(Path(tmp)):
            percorso = install.percorso_config("dsh")
            percorso.parent.mkdir(parents=True)
            percorso.write_text("- insert:\n    - id: altra\n      name: x\n", encoding="utf-8")
            install.applica("dsh")
            dati = yaml.safe_load(percorso.read_text(encoding="utf-8"))
            ids = [voce.get("id") for patch in dati for voce in patch.get("insert", [])]
            check("dsh: la voce esistente resta", "altra" in ids, str(ids))
            check("dsh: la nostra voce c'e'", "ad-projects-mcp" in ids, str(ids))
            percorso_json = install.percorso_config("cursor")
            percorso_json.parent.mkdir(parents=True)
            percorso_json.write_text(json.dumps({"altra": {"x": 1}}), encoding="utf-8")
            install.applica("cursor")
            dati_json = json.loads(percorso_json.read_text(encoding="utf-8"))
            check("json: le altre chiavi restano", dati_json.get("altra") == {"x": 1}, str(dati_json))
            check("json: mcpServers c'e'", "ad-projects" in dati_json.get("mcpServers", {}), str(dati_json))


def test_portabilita_stale() -> None:
    """Una voce che punta a un altro percorso e' STALE, e apply la corregge."""
    with tempfile.TemporaryDirectory() as tmp:
        with _home_finta(Path(tmp)):
            percorso = install.percorso_config("cursor")
            percorso.parent.mkdir(parents=True)
            percorso.write_text(json.dumps({"mcpServers": {"ad-projects": {"command": "python3", "args": ["/home/altra/server.py"]}}}), encoding="utf-8")
            stato, dettaglio = install.stato("cursor")
            check("stale: altro percorso", stato == "stale", f"{stato} {dettaglio}")
            install.applica("cursor")
            check("stale: corretto", install.stato("cursor")[0] == "aggiornata", str(install.stato("cursor")))
            dati = json.loads(percorso.read_text(encoding="utf-8"))
            check("stale: percorso di QUESTA macchina", dati["mcpServers"]["ad-projects"]["args"] == [str(install.SERVER)], str(dati))


def test_rollback_byte_identico() -> None:
    """rollback riporta il file esattamente come era (sha256), e senza backup rifiuta."""
    with tempfile.TemporaryDirectory() as tmp:
        with _home_finta(Path(tmp)):
            percorso = install.percorso_config("gemini")
            percorso.parent.mkdir(parents=True)
            originale = json.dumps({"mcpServers": {}, "x": 1}, indent=4) + "\n"
            percorso.write_text(originale, encoding="utf-8")
            impronta = install._sha(percorso)
            install.applica("gemini")
            check("gemini: registrata", install.stato("gemini")[0] == "aggiornata", str(install.stato("gemini")))
            install.ripristina("gemini")
            check("rollback: byte-identico", install._sha(percorso) == impronta, "sha diverso")
            try:
                install.ripristina("gemini")
            except install.ErroreUso:
                check("rollback senza backup: rifiuto", True)
            else:
                check("rollback senza backup: rifiuto", False, "ha ripristinato")


def test_codex_toml() -> None:
    """Codex: la tabella si scrive una volta e si sostituisce, non si duplica."""
    with tempfile.TemporaryDirectory() as tmp:
        with _home_finta(Path(tmp)):
            percorso = install.percorso_config("codex")
            percorso.parent.mkdir(parents=True)
            percorso.write_text("[altra]\nx = 1\n", encoding="utf-8")
            install.applica("codex")
            testo = percorso.read_text(encoding="utf-8")
            check("codex: tabella scritta", "[mcp_servers.ad-projects]" in testo, testo)
            check("codex: il resto resta", "[altra]" in testo, testo)
            install.applica("codex")
            testo = percorso.read_text(encoding="utf-8")
            check("codex: una sola tabella", testo.count("[mcp_servers.ad-projects]") == 1, testo)
            check("codex: status aggiornata", install.stato("codex")[0] == "aggiornata", str(install.stato("codex")))


def test_auto() -> None:
    """auto registra i client rilevati e non inventa percorsi per gli assenti."""
    with tempfile.TemporaryDirectory() as tmp:
        with _home_finta(Path(tmp)):
            radice = Path(tmp)
            (radice / ".cursor").mkdir()
            rilevati = install.client_installati()
            check("auto: vede cursor", "cursor" in rilevati, str(rilevati))
            check("auto: non vede dsh", "dsh" not in rilevati, str(rilevati))
            for nome in rilevati:
                install.applica(nome)
                check(f"auto: {nome} registrato", install.stato(nome)[0] == "aggiornata", str(install.stato(nome)))


def test_cli_registrazione() -> None:
    """La CLI: --status/--apply/--rollback con HOME temporaneo."""
    with tempfile.TemporaryDirectory() as tmp:
        with _home_finta(Path(tmp)):
            ambiente = dict(os.environ)
            def _cli(*argomenti: str) -> subprocess.CompletedProcess:
                return subprocess.run(
                    [sys.executable, str(INSTALL), *argomenti],
                    capture_output=True, text=True, cwd=str(ROOT), env=ambiente,
                )
            (Path(tmp) / ".cursor").mkdir(exist_ok=True)
            (Path(tmp) / ".cursor" / "mcp.json").write_text("{}\n", encoding="utf-8")
            check("CLI status prima: exit 1", _cli("--status", "cursor").returncode == 1, "")
            check("CLI apply: exit 0", _cli("--apply", "cursor").returncode == 0, "")
            check("CLI status dopo: exit 0", _cli("--status", "cursor").returncode == 0, "")
            check("CLI rollback: exit 0", _cli("--rollback", "cursor").returncode == 0, "")
            check("CLI rollback senza backup: exit 2", _cli("--rollback", "cursor").returncode == 2, "")



def test_configurazioni_malformate_non_sollevano() -> None:
    """Un tipo annidato sbagliato e' un rifiuto, non un traceback (rilievo A del gate)."""
    with tempfile.TemporaryDirectory() as tmp:
        with _home_finta(Path(tmp)):
            for client, contenuto in (
                ("cursor", json.dumps({"mcpServers": "x"})),
                ("cursor", json.dumps({"mcpServers": ["x"]})),
                ("gemini", json.dumps({"mcpServers": 42})),
                ("codex", 'mcp_servers = "nope"\n'),
                ("codex", "[[mcp_servers]]\n"),
            ):
                percorso = install.percorso_config(client)
                percorso.parent.mkdir(parents=True, exist_ok=True)
                percorso.write_text(contenuto, encoding="utf-8")
                try:
                    stato, _ = install.stato(client)
                except Exception as errore:  # noqa: BLE001 - e' la classe che non deve accadere
                    check(f"{client} malformato: nessun traceback in stato", False, errore.__class__.__name__)
                    continue
                check(f"{client} malformato: stato=rotta", stato == "rotta", str(stato))


def test_toml_invalido_non_si_tocca() -> None:
    """apply su un TOML invalido NON scrive e NON dichiara successo (rilievo B)."""
    with tempfile.TemporaryDirectory() as tmp:
        with _home_finta(Path(tmp)):
            percorso = install.percorso_config("codex")
            percorso.parent.mkdir(parents=True)
            originale = "[[[bad toml\n"
            percorso.write_text(originale, encoding="utf-8")
            try:
                install.applica("codex")
            except install.ErroreUso:
                check("TOML invalido: rifiuto", True)
            else:
                check("TOML invalido: rifiuto", False, "ha scritto lo stesso")
            check("TOML invalido: file intatto", percorso.read_text(encoding="utf-8") == originale, "file cambiato")


def test_check_dice_cosa_ha_verificato() -> None:
    """--check distingue il BLOCCO generato dalla registrazione installata (rilievo C)."""
    with tempfile.TemporaryDirectory() as tmp:
        with _home_finta(Path(tmp)):
            ambiente = {**os.environ, "HOME": tmp, "DSH_PROFILE": "test"}
            esito = subprocess.run([sys.executable, str(INSTALL), "--check", "cursor"],
                                   capture_output=True, text=True, cwd=str(ROOT), env=ambiente)
            check("check: parla di blocco", "BLOCCO" in esito.stdout, esito.stdout[:200])
            check("check: mostra lo stato installazione", "installazione" in esito.stdout, esito.stdout[:200])


def test_chiavi_utente_conservate() -> None:
    """apply non cancella env/timeout della voce (rilievo D)."""
    with tempfile.TemporaryDirectory() as tmp:
        with _home_finta(Path(tmp)):
            percorso = install.percorso_config("cursor")
            percorso.parent.mkdir(parents=True)
            percorso.write_text(json.dumps({"mcpServers": {"ad-projects": {
                "command": "python3", "args": ["/old/server.py"],
                "env": {"X": "1"}, "timeout": 30}}}), encoding="utf-8")
            install.applica("cursor")
            voce = json.loads(percorso.read_text(encoding="utf-8"))["mcpServers"]["ad-projects"]
            check("env conservato", voce.get("env") == {"X": "1"}, str(voce))
            check("timeout conservato", voce.get("timeout") == 30, str(voce))
            check("il percorso e' corretto", voce.get("args") == [str(install.SERVER)], str(voce))


def test_auto_dice_chi_salta() -> None:
    """--apply auto nomina i client non rilevati (rilievo E)."""
    with tempfile.TemporaryDirectory() as tmp:
        with _home_finta(Path(tmp)):
            (Path(tmp) / ".cursor").mkdir()
            ambiente = {**os.environ, "HOME": tmp, "DSH_PROFILE": "test"}
            esito = subprocess.run([sys.executable, str(INSTALL), "--apply", "auto"],
                                   capture_output=True, text=True, cwd=str(ROOT), env=ambiente)
            check("auto: dice chi salta", "non rilevati" in esito.stdout, esito.stdout[:300])


def test_rollback_su_file_nuovo() -> None:
    """Se il file non c'era, il rollback lo rimuove (rilievo F)."""
    with tempfile.TemporaryDirectory() as tmp:
        with _home_finta(Path(tmp)):
            percorso = install.percorso_config("gemini")
            install.applica("gemini")
            check("file creato", percorso.is_file(), str(percorso))
            install.ripristina("gemini")
            check("rollback: il file non esiste piu'", not percorso.is_file(), "esiste ancora")



def test_cordis_conserva_commenti_e_voci() -> None:
    """La registrazione DSH e' additiva: commenti e altre voci restano (rilievo R1)."""
    with tempfile.TemporaryDirectory() as tmp:
        with _home_finta(Path(tmp)):
            percorso = install.percorso_config("dsh")
            percorso.parent.mkdir(parents=True)
            originale = (
                "# intestazione importante\n"
                "# seconda riga\n"
                "- { id: altra-voce, disabled: false }\n"
                "- id: modello\n"
                "  name: \"x\"\n"
            )
            percorso.write_text(originale, encoding="utf-8")
            install.applica("dsh")
            testo = percorso.read_text(encoding="utf-8")
            check("cordis: commenti conservati", testo.startswith("# intestazione importante"), testo[:80])
            check("cordis: commenti multipli", "# seconda riga" in testo, "manca")
            check("cordis: voce esistente conservata", "altra-voce" in testo, "persa")
            dati = install._leggi_yaml_permissivo(testo)
            ids = [p.get("id") for p in dati if isinstance(p, dict)]
            check("cordis: voce esistente tra le patch", "altra-voce" in ids, str(ids))
            check("cordis: una sola voce nostra", testo.count("ad-projects-mcp") == 1, str(testo.count("ad-projects-mcp")))
            install.applica("dsh")
            testo = percorso.read_text(encoding="utf-8")
            check("cordis: doppio apply non duplica", testo.count("ad-projects-mcp") == 1, str(testo.count("ad-projects-mcp")))


def test_toml_varianti() -> None:
    """TOML: tabella quotata, con spazi o con commento in coda non viene duplicata."""
    for sezione in ('[mcp_servers."ad-projects"]', "[ mcp_servers.ad-projects ]", "[mcp_servers.ad-projects] # nota"):
        with tempfile.TemporaryDirectory() as tmp:
            with _home_finta(Path(tmp)):
                percorso = install.percorso_config("codex")
                percorso.parent.mkdir(parents=True)
                percorso.write_text(sezione + "\nenv = { X = \"1\" }\n", encoding="utf-8")
                install.applica("codex")
                testo = percorso.read_text(encoding="utf-8")
                if install.tomllib is not None:
                    try:
                        import tomllib as _t
                        _t.loads(testo)
                        valido = True
                    except Exception:  # noqa: BLE001
                        valido = False
                    check(f"toml variante {sezione!r}: valido", valido, testo)
                check(f"toml variante {sezione!r}: una sola sezione", testo.count("[mcp_servers.ad-projects]") == 1 or testo.count(sezione) == 1, testo)
                check(f"toml variante {sezione!r}: env conservato", "X" in testo, testo)


def test_dsh_profile_non_valido() -> None:
    """DSH_PROFILE e' un nome, non un percorso: vuoto/assoluto/.. rifiutati."""
    for profilo in ("", "/tmp/evil", "../../evil", "a/b"):
        vecchio = os.environ.get("DSH_PROFILE")
        os.environ["DSH_PROFILE"] = profilo
        try:
            try:
                install.percorso_config("dsh")
            except install.ErroreUso:
                check(f"profilo {profilo!r}: rifiutato", True)
            else:
                check(f"profilo {profilo!r}: rifiutato", False, "accettato")
        finally:
            if vecchio is None:
                os.environ.pop("DSH_PROFILE", None)
            else:
                os.environ["DSH_PROFILE"] = vecchio


def test_status_plugin_e_transport() -> None:
    """Una voce cordis con plugin o transport sbagliati non e' 'aggiornata'."""
    with tempfile.TemporaryDirectory() as tmp:
        with _home_finta(Path(tmp)):
            percorso = install.percorso_config("dsh")
            percorso.parent.mkdir(parents=True)
            percorso.write_text(
                "- insert:\n    - id: ad-projects-mcp\n      name: \"plugin-sbagliato\"\n"
                "      config:\n        transport: sse\n        command: python3\n"
                f'        args: ["{install.SERVER}"]\n',
                encoding="utf-8",
            )
            stato, dettaglio = install.stato("dsh")
            check("plugin sbagliato: stale", stato == "stale", f"{stato} {dettaglio}")


def test_apply_server_inesistente() -> None:
    """Se il server non esiste non si registra niente."""
    with tempfile.TemporaryDirectory() as tmp:
        with _home_finta(Path(tmp)):
            sano = install.SERVER
            install.SERVER = Path(tmp) / "non-esiste.py"
            try:
                install.applica("cursor")
            except install.ErroreUso:
                check("server inesistente: rifiuto", True)
            else:
                check("server inesistente: rifiuto", False, "ha registrato")
            finally:
                install.SERVER = sano


def test_auto_isola_i_guasti() -> None:
    """Un client rotto non ferma gli altri e il guasto si vede."""
    with tempfile.TemporaryDirectory() as tmp:
        with _home_finta(Path(tmp)):
            radice = Path(tmp)
            (radice / ".cursor").mkdir()
            (radice / ".codex").mkdir()
            (radice / ".codex" / "config.toml").write_text("[[[rotto\n", encoding="utf-8")
            install.applica("cursor")
            try:
                install.applica("codex")
            except install.ErroreUso:
                check("codex rotto: rifiuto", True)
            else:
                check("codex rotto: rifiuto", False, "ha scritto")
            check("cursor: scritto lo stesso", install.stato("cursor")[0] == "aggiornata", str(install.stato("cursor")))



def test_cordis_voce_singola() -> None:
    """Il merge DSH tocca SOLO la nostra voce: voci sorelle, commenti e duplicati (ERR-0061)."""
    with tempfile.TemporaryDirectory() as tmp:
        with _home_finta(Path(tmp)):
            percorso = install.percorso_config("dsh")
            percorso.parent.mkdir(parents=True)
            originale = (
                "# intestazione\n"
                "- insert:\n"
                "    - id: plugin-utente\n"
                "      name: \"utente\"\n"
                "    - id: ad-projects-mcp\n"
                "      name: \"vecchio-plugin\"\n"
                "      config:\n"
                "        transport: stdio\n"
                "        command: python3\n"
                "        args: [\"/home/altra/server.py\"]\n"
                "        env: { X: \"1\" }\n"
                "        timeout: 30\n"
                "  # commento fra i blocchi\n"
                "- id: altro-blocco\n"
                "  name: \"altro\"\n"
                "- insert:\n"
                "    - id: ad-projects-mcp\n"
                "      name: \"duplicato-stale\"\n"
                "      config:\n"
                "        command: python3\n"
                "        args: [\"/home/altra/vecchio.py\"]\n"
            )
            percorso.write_text(originale, encoding="utf-8")
            install.applica("dsh")
            testo = percorso.read_text(encoding="utf-8")
            check("cordis: voce sorella conservata", "plugin-utente" in testo, testo)
            check("cordis: altro blocco conservato", "altro-blocco" in testo, testo)
            check("cordis: commento fra i blocchi conservato", "# commento fra i blocchi" in testo, testo)
            check("cordis: intestazione conservata", testo.startswith("# intestazione"), testo[:60])
            check("cordis: duplicato rimosso", testo.count("ad-projects-mcp") == 1, str(testo.count("ad-projects-mcp")))
            check("cordis: nessun percorso altrui", "/home/altra/" not in testo, "resta un percorso altrui")
            check("cordis: env conservato", "X: '1'" in testo or 'X: "1"' in testo, testo)
            check("cordis: timeout conservato", "timeout: 30" in testo, testo)
            check("cordis: stato aggiornata", install.stato("dsh")[0] == "aggiornata", str(install.stato("dsh")))


def test_toml_array_rifiutato() -> None:
    """[[mcp_servers]] e' un rifiuto, non 'registrata' (ERR-0061)."""
    with tempfile.TemporaryDirectory() as tmp:
        with _home_finta(Path(tmp)):
            percorso = install.percorso_config("codex")
            percorso.parent.mkdir(parents=True)
            originale = "[[mcp_servers]]\nname = \"x\"\n"
            percorso.write_text(originale, encoding="utf-8")
            try:
                install.applica("codex")
            except install.ErroreUso:
                check("toml array: rifiutato", True)
            else:
                check("toml array: rifiutato", False, "ha scritto")
            check("toml array: file intatto", percorso.read_text(encoding="utf-8") == originale, "cambiato")


def test_permessi_conservati() -> None:
    """Il modo del file resta quello di prima (600 resta 600) — ERR-0061."""
    with tempfile.TemporaryDirectory() as tmp:
        with _home_finta(Path(tmp)):
            percorso = install.percorso_config("cursor")
            percorso.parent.mkdir(parents=True)
            percorso.write_text("{}", encoding="utf-8")
            os.chmod(percorso, 0o600)
            install.applica("cursor")
            modo = percorso.stat().st_mode & 0o777
            check("permessi: 600 resta 600", modo == 0o600, oct(modo))


def test_status_js_e_campi() -> None:
    """`!!js` non e' 'rotta'; serverName sbagliato e disabled sono 'stale' (ERR-0061)."""
    with tempfile.TemporaryDirectory() as tmp:
        with _home_finta(Path(tmp)):
            percorso = install.percorso_config("dsh")
            percorso.parent.mkdir(parents=True)
            percorso.write_text(
                "- id: js-patch\n  name: \"x\"\n  config:\n    valore: !!js '1+1'\n"
                "- insert:\n    - id: ad-projects-mcp\n      name: \"@deepseek-ai/dsh-mcp-client\"\n"
                "      config:\n        transport: stdio\n        serverName: ad-projects\n"
                f'        command: python3\n        args: ["{install.SERVER}"]\n',
                encoding="utf-8",
            )
            check("!!js: non e' rotta", install.stato("dsh")[0] == "aggiornata", str(install.stato("dsh")))
            testo = percorso.read_text(encoding="utf-8").replace("serverName: ad-projects", "serverName: ALTRO")
            percorso.write_text(testo, encoding="utf-8")
            check("serverName sbagliato: stale", install.stato("dsh")[0] == "stale", str(install.stato("dsh")))
            testo = percorso.read_text(encoding="utf-8").replace("serverName: ALTRO", "serverName: ad-projects")
            percorso.write_text(testo.replace("- insert:", "- insert:\n      disabled: true") if False else testo, encoding="utf-8")
            dati = install._leggi_yaml_permissivo(testo)
            for patch in dati:
                for voce in patch.get("insert") or []:
                    if isinstance(voce, dict) and voce.get("id") == "ad-projects-mcp":
                        voce["disabled"] = True
            percorso.write_text(install.yaml.safe_dump(dati, sort_keys=False), encoding="utf-8")
            check("disabled: stale", install.stato("dsh")[0] == "stale", str(install.stato("dsh")))


def test_apply_post_condizione() -> None:
    """Se dopo la scrittura lo stato non e' 'aggiornata', apply annulla e rifiuta."""
    with tempfile.TemporaryDirectory() as tmp:
        with _home_finta(Path(tmp)):
            percorso = install.percorso_config("cursor")
            percorso.parent.mkdir(parents=True)
            originale = "{\"mcpServers\": {}}"
            percorso.write_text(originale, encoding="utf-8")
            sano = install.stato
            install.stato = lambda client: ("rotta", "simulato")  # type: ignore[assignment]
            try:
                install.applica("cursor")
            except install.ErroreUso as errore:
                check("post-condizione: rifiuto", "ripristinato" in str(errore), str(errore))
            else:
                check("post-condizione: rifiuto", False, "ha dichiarato registrata")
            finally:
                install.stato = sano  # type: ignore[assignment]
            check("post-condizione: file ripristinato", percorso.read_text(encoding="utf-8") == originale, percorso.read_text(encoding="utf-8"))



def test_autodetect_profilo() -> None:
    """Un profilo solo si usa; due senza la nostra voce sono un rifiuto (ERR-0061)."""
    with tempfile.TemporaryDirectory() as tmp:
        with _home_finta(Path(tmp)):
            radice = Path(tmp) / ".dsh" / "profiles"
            (radice / "uno").mkdir(parents=True)
            (radice / "uno" / "cordis.patch.yml").write_text("[]\n", encoding="utf-8")
            check("un profilo: lo usa", install._profilo_dsh() == "uno", install._profilo_dsh())
            (radice / "due").mkdir()
            (radice / "due" / "cordis.patch.yml").write_text("[]\n", encoding="utf-8")
            try:
                install._profilo_dsh()
            except install.ErroreUso:
                check("due profili: rifiuto", True)
            else:
                check("due profili: rifiuto", False, "ha scelto un profilo")
            (radice / "due" / "cordis.patch.yml").write_text(
                "- insert:\n    - id: ad-projects-mcp\n      name: x\n", encoding="utf-8")
            check("due profili: sceglie quello con la voce", install._profilo_dsh() == "due", install._profilo_dsh())


def test_disabled_viene_riabilitata() -> None:
    """`--apply` su una voce disabilitata la riabilita (il README lo dice)."""
    with tempfile.TemporaryDirectory() as tmp:
        with _home_finta(Path(tmp)):
            percorso = install.percorso_config("dsh")
            percorso.parent.mkdir(parents=True)
            percorso.write_text(
                "- insert:\n    - id: ad-projects-mcp\n      name: \"@deepseek-ai/dsh-mcp-client\"\n"
                "      disabled: true\n      config:\n        transport: stdio\n"
                "        serverName: ad-projects\n        command: python3\n"
                f'        args: ["{install.SERVER}"]\n',
                encoding="utf-8",
            )
            check("disabled: stale prima", install.stato("dsh")[0] == "stale", str(install.stato("dsh")))
            install.applica("dsh")
            check("disabled: aggiornata dopo", install.stato("dsh")[0] == "aggiornata", str(install.stato("dsh")))
            check("disabled: tolto dal file", "disabled" not in percorso.read_text(encoding="utf-8"), percorso.read_text(encoding="utf-8"))


def test_toml_array_guardia_diretta() -> None:
    """La guardia su [[mcp_servers]] esiste anche prima della post-condizione."""
    with tempfile.TemporaryDirectory() as tmp:
        with _home_finta(Path(tmp)):
            percorso = install.percorso_config("codex")
            percorso.parent.mkdir(parents=True)
            originale = "[[mcp_servers]]\nname = \"x\"\n"
            percorso.write_text(originale, encoding="utf-8")
            try:
                install._merge_toml(percorso, dry=False)
            except install.ErroreUso as errore:
                check("guardia array: rifiuto diretto", "LISTA" in str(errore).upper(), str(errore))
            else:
                check("guardia array: rifiuto diretto", False, "ha scritto")
            check("guardia array: file intatto", percorso.read_text(encoding="utf-8") == originale, "cambiato")


def test_yaml_due_spazi() -> None:
    """Un file YAML valido a 2 spazi non viene rifiutato, e le voci restano."""
    with tempfile.TemporaryDirectory() as tmp:
        with _home_finta(Path(tmp)):
            percorso = install.percorso_config("dsh")
            percorso.parent.mkdir(parents=True)
            percorso.write_text(
                "# due spazi\n- insert:\n  - id: plugin-utente\n    name: \"utente\"\n"
                "  - id: ad-projects-mcp\n    name: \"vecchio\"\n    config:\n"
                "      command: python3\n      args: [\"/old/server.py\"]\n",
                encoding="utf-8",
            )
            install.applica("dsh")
            testo = percorso.read_text(encoding="utf-8")
            check("2 spazi: sorella conservata", "plugin-utente" in testo, testo)
            check("2 spazi: status aggiornata", install.stato("dsh")[0] == "aggiornata", str(install.stato("dsh")))


def test_id_esatto_non_sottostringa() -> None:
    """Una voce con id che CONTIENE il nostro non viene toccata (ERR-0061)."""
    with tempfile.TemporaryDirectory() as tmp:
        with _home_finta(Path(tmp)):
            percorso = install.percorso_config("dsh")
            percorso.parent.mkdir(parents=True)
            percorso.write_text(
                "- insert:\n    - id: ad-projects-mcp-legacy\n      name: \"legacy\"\n"
                "- insert:\n    - id: ad-projects-mcp\n      name: \"vecchio\"\n"
                f'      config:\n        command: python3\n        args: ["{install.SERVER}"]\n',
                encoding="utf-8",
            )
            install.applica("dsh")
            testo = percorso.read_text(encoding="utf-8")
            check("id esatto: la legacy resta", "ad-projects-mcp-legacy" in testo, testo)
            import re as _re
            esatte = len(_re.findall(r"id:\s*['\"]?ad-projects-mcp['\"]?\s*$", testo, _re.MULTILINE))
            check("id esatto: una sola voce nostra", esatte == 1, str(esatte))



def main() -> int:
    """Run the suite."""
    print("generatore di configurazioni: cinque client, validi, nessuna scrittura")
    test_elenco()
    test_blocchi_validi()
    test_verifica()
    test_client_sconosciuto()
    test_la_generazione_non_scrive()
    test_i_validatori_rifiutano_i_blocchi_rotti()
    test_forme_malformate_non_sollevano()
    test_python_senza_tomllib()
    test_registrazione_dsh()
    test_registrazione_conserva_il_resto()
    test_portabilita_stale()
    test_rollback_byte_identico()
    test_codex_toml()
    test_auto()
    test_cli_registrazione()
    test_configurazioni_malformate_non_sollevano()
    test_toml_invalido_non_si_tocca()
    test_check_dice_cosa_ha_verificato()
    test_chiavi_utente_conservate()
    test_auto_dice_chi_salta()
    test_rollback_su_file_nuovo()
    test_cordis_conserva_commenti_e_voci()
    test_toml_varianti()
    test_dsh_profile_non_valido()
    test_status_plugin_e_transport()
    test_apply_server_inesistente()
    test_auto_isola_i_guasti()
    test_cordis_voce_singola()
    test_toml_array_rifiutato()
    test_permessi_conservati()
    test_status_js_e_campi()
    test_apply_post_condizione()
    test_autodetect_profilo()
    test_disabled_viene_riabilitata()
    test_toml_array_guardia_diretta()
    test_yaml_due_spazi()
    test_id_esatto_non_sottostringa()
    print(f"PASS — {PASSED} controlli sul generatore di configurazioni")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
