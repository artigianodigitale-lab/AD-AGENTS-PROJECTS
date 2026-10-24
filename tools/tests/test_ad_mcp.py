#!/usr/bin/env python3
"""Il server MCP di AD: handshake, catalogo, ogni tool, i rifiuti, la parita'.

    python3 tools/tests/test_ad_mcp.py

Perche' esiste. Un server che "espone i tool" senza che nessuno ci abbia parlato
non e' provato: e' dichiarato. Questa suite lancia il processo vero, gli parla il
protocollo vero (JSON-RPC 2.0 su stdio, una riga per messaggio) e controlla quello
che risponde — compresi i rifiuti, che sono la parte che conta: un server che non
rifiuta niente non e' un confine, e' un passacarte.

Il test di parita' e' il piu' importante: `ad_verdict` deve dare lo **stesso**
esito di `tools/verdict.py` sugli stessi input. Se il server riscrivesse la
regola, prima o poi direbbe una cosa diversa dal CLI — due autorita' che
divergono sono peggio di una sola.
"""

from __future__ import annotations

import json
import shutil

import yaml
import tempfile
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "tools" / "ad_mcp" / "server.py"

sys.path.insert(0, str(ROOT / "tools"))

import ad_evidence  # noqa: E402

PASSED = 0


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    """Assert one expectation, with the label of what broke."""
    global PASSED
    if not condizione:
        raise AssertionError(f"{etichetta}: {dettaglio or 'condizione falsa'}")
    PASSED += 1


class Client:
    """A minimal MCP client over the server's stdio."""

    def __init__(self) -> None:
        self.processo = subprocess.Popen(
            [sys.executable, str(SERVER)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=str(ROOT),
        )
        self._id = 0

    def send(self, metodo: str, parametri: dict | None = None) -> dict:
        """Send one request and return the whole response (result or error)."""
        self._id += 1
        messaggio = {"jsonrpc": "2.0", "id": self._id, "method": metodo}
        if parametri is not None:
            messaggio["params"] = parametri
        assert self.processo.stdin is not None
        self.processo.stdin.write(json.dumps(messaggio) + "\n")
        self.processo.stdin.flush()
        assert self.processo.stdout is not None
        riga = self.processo.stdout.readline()
        if not riga:
            errore = self.processo.stderr.read() if self.processo.stderr else ""
            raise AssertionError(f"il server non ha risposto ({metodo}): {errore[:400]}")
        return json.loads(riga)

    def raw_bytes(self, dati: bytes) -> dict:
        """Send raw bytes (for protocol-encoding tests)."""
        assert self.processo.stdin is not None
        self.processo.stdin.buffer.write(dati + b"\n")
        self.processo.stdin.buffer.flush()
        assert self.processo.stdout is not None
        riga = self.processo.stdout.readline()
        if not riga:
            raise AssertionError(f"il server non ha risposto a {dati!r}")
        return json.loads(riga)

    def raw(self, testo: str) -> dict:
        """Send raw bytes as one line, to test protocol errors."""
        assert self.processo.stdin is not None
        self.processo.stdin.write(testo + "\n")
        self.processo.stdin.flush()
        assert self.processo.stdout is not None
        riga = self.processo.stdout.readline()
        if not riga:
            raise AssertionError(f"il server non ha risposto a {testo!r}")
        return json.loads(riga)

    def call(self, nome: str, argomenti: dict | None = None) -> dict:
        """Call one tool and return its structured content."""
        risposta = self.send("tools/call", {"name": nome, "arguments": argomenti or {}})
        assert "result" in risposta, f"{nome}: {risposta}"
        return risposta["result"]["structuredContent"]

    def close(self) -> None:
        """Terminate the server."""
        self.processo.terminate()
        try:
            self.processo.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.processo.kill()


def _contratto_attivo() -> str:
    """Return the path of an active contract, discovered instead of hardcoded.

    Un test che nomina un contract preciso si rompe quando quel contract viene
    chiuso e un successore prende gli stessi percorsi (famiglia ERR-0049, rilievo 1
    di ENG-003; vedi DRIFT-027).
    """
    for percorso in sorted((ROOT / "contratti").rglob("*.yaml")):
        if percorso.name.startswith("_"):
            continue
        try:
            dati = yaml.safe_load(percorso.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if isinstance(dati, dict) and str(dati.get("status")) == "active":
            return str(percorso.relative_to(ROOT))
    return ""


def test_handshake_e_catalogo() -> None:
    """initialize, ping, tools/list: il server si presenta e dichiara i suoi confini."""
    client = Client()
    try:
        init = client.send("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}})
        check("initialize risponde", "result" in init, str(init)[:200])
        risultato = init["result"]
        check("protocolVersion", bool(risultato.get("protocolVersion")), str(risultato))
        check("capabilities.tools", "tools" in risultato.get("capabilities", {}), str(risultato))
        check("serverInfo ha un nome", risultato["serverInfo"]["name"] == "ad-projects", str(risultato))

        pong = client.send("ping")
        check("ping risponde", pong.get("result") == {}, str(pong)[:120])

        catalogo = client.send("tools/list")["result"]["tools"]
        check("almeno 10 tool", len(catalogo) >= 10, f"{len(catalogo)} tool")
        nomi = {voce["name"] for voce in catalogo}
        attesi = {
            "ad_session", "ad_contract_check", "ad_contract_validate", "ad_cards_match",
            "ad_verdict", "ad_evidence_check", "ad_unknowns", "ad_bundle", "ad_tree",
            "ad_registry",
        }
        check("i tool attesi ci sono", attesi <= nomi, f"mancano: {sorted(attesi - nomi)}")
        for voce in catalogo:
            check(f"{voce['name']}: schema", isinstance(voce.get("inputSchema"), dict) and "type" in voce["inputSchema"], str(voce.get("inputSchema")))
            check(f"{voce['name']}: descrizione", len(voce.get("description", "")) > 20, "descrizione troppo corta")
            check(f"{voce['name']}: annotazioni", "readOnlyHint" in voce.get("annotations", {}), str(voce.get("annotations")))

        sconosciuto = client.send("resources/list")
        check("metodo sconosciuto rifiutato", sconosciuto.get("error", {}).get("code") == -32601, str(sconosciuto)[:150])
        check(
            "il rifiuto dice il rimedio",
            bool(sconosciuto["error"].get("data", {}).get("remediation")),
            str(sconosciuto)[:150],
        )
    finally:
        client.close()


def test_session() -> None:
    """ad_session: l'inventario dice cosa esiste davvero."""
    client = Client()
    try:
        inventario = client.call("ad_session")
        check("machine e' la root", Path(inventario["machine"]).resolve() == ROOT, inventario["machine"])
        check("contratti attivi", isinstance(inventario["contracts"]["active"], list), str(inventario["contracts"]))
        # Niente id cablati e nessun requisito che esistano contract attivi: la
        # suite deve passare anche con tutti i contract chiusi (criterio 1 di
        # ENG-004, rilievo del gate). L'inventario deve essere *coerente*, non pieno.
        contratti = inventario["contracts"]
        attivi = contratti["active"]
        check("l'inventario conta i contratti", isinstance(contratti["total"], int), str(contratti))
        check("gli attivi non superano il totale", len(attivi) <= contratti["total"], str(contratti))
        check(
            "ogni contract attivo ha task_id e write_scope",
            all(c.get("task_id") and isinstance(c.get("write_scope"), list) for c in attivi),
            str(attivi),
        )
        check(
            "i modelli non sono contratti",
            not any(str(c["task_id"]).startswith(("MAN-", "PROD-")) for c in inventario["contracts"]["active"]),
            str([c["task_id"] for c in inventario["contracts"]["active"]]),
        )
        check("registri contati", inventario["registers"]["errori"] > 0, str(inventario["registers"]))
        check("i tool sono elencati", len(inventario["tools"]) >= 10, str(inventario["tools"]))
    finally:
        client.close()


def test_confine() -> None:
    """ad_contract_check: il confine si applica, e dice chi copre."""
    client = Client()
    try:
        # Nessun id di contract cablato e nessun percorso la cui copertura cambia
        # quando un contract si chiude (famiglia ERR-0049, rilievo 1 di ENG-003).
        # Si prova la regola su percorsi strutturalmente stabili.
        libero = client.call("ad_contract_check", {"path": "piani/README.md"})
        check("un percorso libero e' scrivibile", libero["allowed"] is True, str(libero))
        check("un percorso libero non e' protetto", libero["protected"] is False, str(libero))

        protetto = client.call("ad_contract_check", {"path": ".brain/README.md"})
        check(".brain/ e' artefatto di governance", protetto["protected"] is True, str(protetto))

        fuori = client.send("tools/call", {"name": "ad_contract_check", "arguments": {"path": "../fuori"}})
        check("percorso fuori rifiutato", fuori.get("error", {}).get("code") == -32602, str(fuori)[:200])

        senza = client.send("tools/call", {"name": "ad_contract_check", "arguments": {}})
        check("parametro mancante rifiutato", senza.get("error", {}).get("code") == -32602, str(senza)[:200])
    finally:
        client.close()


def test_parita_col_cli() -> None:
    """ad_verdict deve dare lo stesso esito di tools/verdict.py: una sola autorita'."""
    contratto = ROOT / "contratti" / "societa" / "ENG-001.yaml"
    prove = [
        ROOT / "evidenze" / "ENG-001-QA.yaml",
        ROOT / "evidenze" / "ENG-001-CodeReview.yaml",
    ]
    processo = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "verdict.py"), "--contract", str(contratto),
         "--evidence", *[str(p) for p in prove]],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    client = Client()
    try:
        dal_server = client.call(
            "ad_verdict",
            {"contract": str(contratto), "evidence": [str(p) for p in prove]},
        )
    finally:
        client.close()
    cli_accept = processo.returncode == 0 and "verdetto: ACCEPT" in processo.stdout
    check("CLI: ACCEPT su ENG-001", cli_accept, processo.stdout[-200:])
    check("server: stesso esito del CLI", dal_server["outcome"] == "ACCEPT", str(dal_server)[:200])
    check(
        "server: stessi gate",
        [g["gate"] for g in dal_server["gates"]] == ["QA", "Code Review"],
        str(dal_server["gates"]),
    )


def test_prove_e_incognite() -> None:
    """ad_evidence_check e ad_unknowns: leggono i registri veri."""
    client = Client()
    try:
        prova = client.call("ad_evidence_check", {"evidence": ["evidenze/ENG-001-QA.yaml"]})
        check("evidenza del gate valida", prova["ok"] is True, str(prova))
        check("identita' calcolata", prova["records"][0]["evidence_id"].startswith("ev_"), str(prova["records"][0]))

        registro = client.call("ad_unknowns", {"action": "list"})
        check("il registro reale ha 4 voci", len(registro["unknowns"]) == 4, str(len(registro["unknowns"])))
        controllo = client.call("ad_unknowns", {"action": "check"})
        check("il registro reale e' coerente", controllo["ok"] is True, str(controllo["problems"]))

        fuori_root = client.send(
            "tools/call",
            {"name": "ad_unknowns", "arguments": {
                "action": "list", "ledger": "/tmp/incognite.yaml"}},
        )
        check(
            "ledger fuori dalla macchina rifiutato",
            fuori_root.get("error", {}).get("code") == -32602,
            str(fuori_root)[:200],
        )

        # Il ledger di prova sta DENTRO la macchina (il server non ha autorita'
        # fuori): vive in `evidenze/`, che non e' sorvegliata, e si cancella.
        ledger = ROOT / "evidenze" / ".test-incognite.yaml"
        try:
            nuovo = client.call(
                "ad_unknowns",
                {"action": "new", "ledger": "evidenze/.test-incognite.yaml",
                 "question": "X?", "domain": "d", "severity": "high",
                 "required_authority": "execution"},
            )
            check("voce creata", str(nuovo["written"]).startswith("unk_"), str(nuovo))
            finto = client.send(
                "tools/call",
                {"name": "ad_unknowns", "arguments": {
                    "action": "resolve", "ledger": "evidenze/.test-incognite.yaml",
                    "id": nuovo["written"],
                    "disposition": "verified", "rationale": "detto io",
                    "evidence_ids": ["ev_" + "0" * 64]}},
            )
            check(
                "chiusura con prova inventata rifiutata",
                finto.get("error", {}).get("code") == -32602,
                str(finto)[:200],
            )
        finally:
            ledger.unlink(missing_ok=True)
    finally:
        client.close()


def test_bundle_e_albero() -> None:
    """ad_bundle verifica il pacchetto vero; ad_tree verifica l'albero vero."""
    client = Client()
    try:
        bundle = client.call("ad_bundle", {"action": "check", "bundle_path": "evidenze/ENG-001-bundle.json"})
        check("il bundle sigillato e' attendibile", bundle["ok"] is True, str(bundle))

        non_bundle = client.send(
            "tools/call",
            {"name": "ad_bundle", "arguments": {"action": "check", "bundle_path": "evidenze/incognite.yaml"}},
        )
        check("un file che non e' bundle viene rifiutato", "error" in non_bundle, str(non_bundle)[:150])

        # L'albero si prova su una radice sua, dentro la macchina: registrare e
        # controllare quello vero dipende dallo stato del workspace, e un test che
        # passa solo se il workspace e' fermo non prova il codice (ERR-0049).
        radice = ROOT / "evidenze" / ".test-tree"
        try:
            (radice / "a").mkdir(parents=True, exist_ok=True)
            (radice / "a" / "uno.txt").write_text("uno\n", encoding="utf-8")
            registrato = client.call("ad_tree", {
                "action": "record", "root": "evidenze/.test-tree", "paths": ["a"],
                "witness": "evidenze/.test-tree/w.yaml",
            })
            check("albero registrato", registrato["files"] == 1, str(registrato))

            pulito = client.call("ad_tree", {
                "action": "check", "root": "evidenze/.test-tree",
                "witness": "evidenze/.test-tree/w.yaml",
            })
            check("albero coerente", pulito["ok"] is True, str(pulito["contaminations"]))

            (radice / "a" / "due.txt").write_text("x\n", encoding="utf-8")
            contaminato = client.call("ad_tree", {
                "action": "check", "root": "evidenze/.test-tree",
                "witness": "evidenze/.test-tree/w.yaml",
            })
            check("aggiunta fuori banda rilevata", contaminato["ok"] is False, str(contaminato))
            check(
                "la contaminazione dice il percorso",
                any("due.txt" in c for c in contaminato["contaminations"]),
                str(contaminato["contaminations"]),
            )
        finally:
            shutil.rmtree(radice, ignore_errors=True)
    finally:
        client.close()


def test_registro() -> None:
    """ad_registry: riassunto e paginazione, due letture diverse dello stesso registro."""
    client = Client()
    try:
        riassunto = client.call("ad_registry", {"kind": "errori"})
        check("riassunto errori", riassunto["total"] > 0, str(riassunto))
        check("riassunto per stato", "chiuso" in riassunto["by_state"] or riassunto["by_state"], str(riassunto))

        completa = client.call("ad_registry", {"kind": "errori", "detail": "complete", "limit": 3})
        check("pagina di 3", completa["returned"] == 3, str(completa))
        check("c'e' la pagina dopo", completa["next_offset"] == 3, str(completa))

        sbagliato = client.send("tools/call", {"name": "ad_registry", "arguments": {"kind": "boh"}})
        check("registro sconosciuto rifiutato", sbagliato.get("error", {}).get("code") == -32602, str(sbagliato)[:150])
    finally:
        client.close()




def test_schemi_imposti() -> None:
    """M3: lo schema si applica. Un argomento in piu' o un tipo sbagliato non passano."""
    client = Client()
    try:
        estraneo = client.send("tools/call", {"name": "ad_contract_check", "arguments": {"path": "tools/", "inutile": 1}})
        check("argomento non previsto rifiutato", estraneo.get("error", {}).get("code") == -32602, str(estraneo)[:200])
        check(
            "il rifiuto dice cosa e' ammesso",
            "ammessi" in str(estraneo.get("error", {}).get("data", {})),
            str(estraneo.get("error", {}).get("data")),
        )
        tipo = client.send("tools/call", {"name": "ad_contract_check", "arguments": {"path": 123}})
        check("tipo sbagliato rifiutato", tipo.get("error", {}).get("code") == -32602, str(tipo)[:200])
        enum = client.send("tools/call", {"name": "ad_registry", "arguments": {"kind": "boh"}})
        check("valore fuori enum rifiutato", enum.get("error", {}).get("code") == -32602, str(enum)[:200])
        vuoto = client.send("tools/call", {"name": "ad_verdict", "arguments": {"contract": "contratti/societa/ENG-002.yaml", "evidence": []}})
        check("lista vuota rifiutata", vuoto.get("error", {}).get("code") == -32602, str(vuoto)[:200])
    finally:
        client.close()


def test_protocollo_rifiuti() -> None:
    """-32700 e -32600 hanno il rimedio, e il server resta vivo dopo un errore."""
    client = Client()
    try:
        malformato = client.raw("{non json")
        check("JSON malformato -> -32700", malformato.get("error", {}).get("code") == -32700, str(malformato)[:150])
        check(
            "il parse error dice il rimedio",
            bool(malformato["error"].get("data", {}).get("remediation")),
            str(malformato)[:150],
        )
        non_oggetto = client.raw("[1, 2, 3]")
        check("richiesta non oggetto -> -32600", non_oggetto.get("error", {}).get("code") == -32600, str(non_oggetto)[:150])
        senza_versione = client.raw('{"id": 9, "method": "ping"}')
        check("jsonrpc mancante rifiutato", senza_versione.get("error", {}).get("code") == -32600, str(senza_versione)[:150])
        check(
            "il rifiuto jsonrpc dice il rimedio",
            bool(senza_versione["error"].get("data", {}).get("remediation")),
            str(senza_versione)[:150],
        )
        vivo = client.send("ping")
        check("il server resta vivo dopo gli errori", vivo.get("result") == {}, str(vivo)[:120])
    finally:
        client.close()


def test_cards_match() -> None:
    """ad_cards_match: H2 del gate. Il match vero non deve andare in crash."""
    client = Client()
    try:
        trovata = client.call("ad_cards_match", {"task_type": "assignment"})
        check("un tipo autorizzato trova una card", trovata["matched"] is True, str(trovata)[:200])
        check("la card dice il suo tipo", bool(trovata["cards"][0].get("type")), str(trovata["cards"][0]))
        nessuna = client.call("ad_cards_match", {"task_type": "tipo_che_non_esiste"})
        check("nessun match e' STOP", nessuna["matched"] is False, str(nessuna)[:200])
        check("lo STOP lo dice", "STOP" in nessuna["reason"], nessuna["reason"])
    finally:
        client.close()


def test_contract_validate() -> None:
    """H3: un warning non e' una violazione. Il server deve concordare col CLI."""
    client = Client()
    try:
        # Nessuna dipendenza dallo stato: si valida un contract scoperto (attivo se
        # c'e') e la REGOLA che deve reggere sempre: `ok` e' l'assenza di violazioni,
        # e gli avvisi sono separati. Se un contract chiuso non produce piu' avvisi,
        # il test non deve fallire: la suite passa anche con tutti i contract chiusi
        # (criterio 1 di ENG-004, rilievo del gate).
        attivo = _contratto_attivo() or "contratti/societa/ADMF-008.yaml"
        valido = client.call("ad_contract_validate", {"contract": attivo})
        check("la risposta ha la forma attesa", isinstance(valido.get("ok"), bool) and isinstance(valido.get("violations"), list) and isinstance(valido.get("warnings"), list), str(valido)[:200])
        check("ok e' l'assenza di violazioni", valido["ok"] == (not valido["violations"]), str(valido)[:200])
        check(
            "gli avvisi sono elencati e separati",
            all(isinstance(voce, str) for voce in valido.get("warnings") or []),
            str(valido.get("warnings")),
        )

        inesistente = client.send("tools/call", {"name": "ad_contract_validate", "arguments": {"contract": "contratti/societa/NON-ESISTE.yaml"}})
        check("contract inesistente rifiutato", "error" in inesistente, str(inesistente)[:150])
    finally:
        client.close()


def test_tree_rifiuti() -> None:
    """H1/M1: ad_tree non esce dalla radice e non accetta azioni inventate."""
    client = Client()
    try:
        azione = client.send("tools/call", {"name": "ad_tree", "arguments": {"action": "nope"}})
        check("azione inventata rifiutata", azione.get("error", {}).get("code") == -32602, str(azione)[:150])

        # `paths` su check: rifiutato, perche' il perimetro e' quello del testimone.
        su_check = client.send("tools/call", {"name": "ad_tree", "arguments": {"action": "check", "paths": ["tools"]}})
        check("paths su check rifiutato", su_check.get("error", {}).get("code") == -32602, str(su_check)[:150])

        testimone = ROOT / "evidenze" / ".test-tree-arg.yaml"
        try:
            for etichetta, percorsi in (
                ("percorso che esce", ["../"]),
                ("percorso assoluto fuori", ["/etc"]),
                ("'paths' vuoto", []),
                ("elemento vuoto", [""]),
                ("solo spazi", ["   "]),
                ("byte NUL in paths", ["tools\x00x"]),
            ):
                esito = client.send("tools/call", {"name": "ad_tree", "arguments": {
                    "action": "record", "paths": percorsi,
                    "witness": "evidenze/.test-tree-arg.yaml"}})
                check(f"ad_tree record: {etichetta} rifiutato", esito.get("error", {}).get("code") == -32602, str(esito)[:160])
                check(f"ad_tree record: {etichetta} non scrive", not testimone.exists(), "testimone scritto")
        finally:
            testimone.unlink(missing_ok=True)
    finally:
        client.close()


def test_bundle_unknowns_rifiuti() -> None:
    """Le azioni inventate e i campi obbligatori mancanti hanno errori chiari."""
    client = Client()
    try:
        bundle = client.send("tools/call", {"name": "ad_bundle", "arguments": {"action": "nope"}})
        check("ad_bundle: azione inventata rifiutata", bundle.get("error", {}).get("code") == -32602, str(bundle)[:150])
        senza_out = client.send("tools/call", {"name": "ad_bundle", "arguments": {"action": "export", "evidence": ["evidenze/ENG-001-QA.yaml"]}})
        check("ad_bundle: 'out' obbligatorio", senza_out.get("error", {}).get("code") == -32602, str(senza_out)[:150])
        senza_file = client.send("tools/call", {"name": "ad_bundle", "arguments": {"action": "check"}})
        check("ad_bundle: 'bundle_path' obbligatorio", senza_file.get("error", {}).get("code") == -32602, str(senza_file)[:150])
        incognite = client.send("tools/call", {"name": "ad_unknowns", "arguments": {"action": "nope"}})
        check("ad_unknowns: azione inventata rifiutata", incognite.get("error", {}).get("code") == -32602, str(incognite)[:150])
    finally:
        client.close()


def test_un_rifiuto_per_tool() -> None:
    """Ogni tool ha almeno un rifiuto provato: un confine che non si prova non c'e'."""
    client = Client()
    try:
        casi = [
            ("ad_session", {"inutile": 1}),
            ("ad_contract_check", {}),
            ("ad_contract_validate", {}),
            ("ad_cards_match", {}),
            ("ad_verdict", {"contract": "contratti/societa/ENG-002.yaml"}),
            ("ad_evidence_check", {}),
            ("ad_unknowns", {"action": "nope"}),
            ("ad_bundle", {"action": "nope"}),
            ("ad_tree", {"action": "nope"}),
            ("ad_registry", {"kind": "nope"}),
        ]
        for nome, argomenti in casi:
            esito = client.send("tools/call", {"name": nome, "arguments": argomenti})
            check(
                f"{nome}: rifiuto con codice",
                esito.get("error", {}).get("code") in (-32602, -32603),
                str(esito)[:180],
            )
            check(
                f"{nome}: rifiuto con rimedio",
                bool(esito.get("error", {}).get("data", {}).get("remediation")),
                str(esito)[:180],
            )
    finally:
        client.close()



def test_limiti_e_range() -> None:
    """M3 residuo: minimum e maximum si impongono, non si 'clampano' in silenzio."""
    client = Client()
    try:
        for valore in (0, 500):
            esito = client.send("tools/call", {"name": "ad_registry", "arguments": {"kind": "errori", "detail": "complete", "limit": valore}})
            check(f"limit {valore} rifiutato", esito.get("error", {}).get("code") == -32602, str(esito)[:160])
        negativo = client.send("tools/call", {"name": "ad_registry", "arguments": {"kind": "errori", "detail": "complete", "offset": -3}})
        check("offset negativo rifiutato", negativo.get("error", {}).get("code") == -32602, str(negativo)[:160])
    finally:
        client.close()


def test_utf8_e_method() -> None:
    """Il confine non muore su byte non UTF-8 e non tace su una richiesta senza method."""
    client = Client()
    try:
        rotto = client.raw_bytes(b"\xff\xfe non utf8")
        check("byte non UTF-8 -> -32700", rotto.get("error", {}).get("code") == -32700, str(rotto)[:150])
        check(
            "il rifiuto dice il rimedio",
            bool(rotto["error"].get("data", {}).get("remediation")),
            str(rotto)[:150],
        )
        vivo = client.send("ping")
        check("il server resta vivo dopo byte invalidi", vivo.get("result") == {}, str(vivo)[:120])

        senza = client.raw('{"jsonrpc": "2.0", "id": 77}')
        check("richiesta senza method -> -32600", senza.get("error", {}).get("code") == -32600, str(senza)[:150])
        check(
            "il rifiuto dice il rimedio",
            bool(senza["error"].get("data", {}).get("remediation")),
            str(senza)[:150],
        )
    finally:
        client.close()


def test_percorsi_vuoti_e_cartelle() -> None:
    """Un percorso vuoto non e' 'tutta la macchina'; `out` non puo' essere una cartella."""
    client = Client()
    try:
        vuoto = client.send("tools/call", {"name": "ad_evidence_check", "arguments": {"evidence": [""]}})
        check("percorso vuoto rifiutato", vuoto.get("error", {}).get("code") == -32602, str(vuoto)[:150])

        cartella = client.send(
            "tools/call",
            {"name": "ad_bundle", "arguments": {
                "action": "export", "evidence": ["evidenze/ENG-001-QA.yaml"],
                "out": "evidenze", "no_witness": True}},
        )
        check("out su una cartella rifiutato", cartella.get("error", {}).get("code") == -32602, str(cartella)[:160])

        # Destinazione protetta e NON coperta: un prodotto non ancora autorizzato.
        # Si usa un numero che non esiste, per non creare (e non toccare) niente.
        vietata = client.send(
            "tools/call",
            {"name": "ad_bundle", "arguments": {
                "action": "export", "evidence": ["evidenze/ENG-001-QA.yaml"],
                "out": "99. Prova autorizzazione/x.json", "no_witness": True}},
        )
        check("destinazione non coperta rifiutata", vietata.get("error", {}).get("code") == -32602, str(vietata)[:160])
        check(
            "il rifiuto cita il cancello",
            "contract" in str(vietata.get("error", {})).lower() or "copert" in str(vietata.get("error", {})).lower(),
            str(vietata)[:160],
        )

        # Una scrittura nella propria area di evidenze passa, e si cancella.
        sicura = ROOT / "evidenze" / ".test-out.json"
        try:
            esito = client.call("ad_bundle", {
                "action": "export", "evidence": ["evidenze/ENG-001-QA.yaml"],
                "out": "evidenze/.test-out.json", "no_witness": True,
            })
            check("scrittura nella propria area ammessa", sicura.is_file(), str(esito))
        finally:
            sicura.unlink(missing_ok=True)
    finally:
        client.close()


def test_artifact_producer() -> None:
    """L4: con esecutore ignoto un artifact_producer dichiarato non e' una violazione."""
    prova = ROOT / "evidenze" / ".test-art.yaml"
    try:
        prova.write_text(
            "schema: 2\ntask_id: TEST\ngate: QA\noutcome: PASS\nproducer: qa\n"
            "artifact_producer: engine-tooling\nconfidence: observed\n"
            "authority: execution\ncoverage: {status: complete, examined: 1, total: 1}\n"
            "limitations: []\n"
            "side_effects: {code: YES, database: NO, schema: NO, deps: NO, env: NO, "
            "external_services: NO}\n",
            encoding="utf-8",
        )
        client = Client()
        try:
            esito = client.call("ad_evidence_check", {"evidence": ["evidenze/.test-art.yaml"]})
        finally:
            client.close()
        check("artifact_producer non bocciato per esecutore ignoto", esito["ok"] is True, str(esito["records"]))
    finally:
        prova.unlink(missing_ok=True)



def test_stringhe_vuote_e_cartelle() -> None:
    """L1/N5/N6: percorso vuoto non e' 'la macchina'; una cartella non e' un file."""
    client = Client()
    try:
        contract_vuoto = client.send("tools/call", {"name": "ad_contract_validate", "arguments": {"contract": ""}})
        check("contract vuoto rifiutato", contract_vuoto.get("error", {}).get("code") == -32602, str(contract_vuoto)[:150])

        root_vuota = client.send("tools/call", {"name": "ad_tree", "arguments": {"action": "check", "root": ""}})
        check("root vuota rifiutata", root_vuota.get("error", {}).get("code") == -32602, str(root_vuota)[:150])

        bundle_cartella = client.send("tools/call", {"name": "ad_bundle", "arguments": {"action": "check", "bundle_path": "evidenze"}})
        check("bundle su una cartella rifiutato", bundle_cartella.get("error", {}).get("code") == -32602, str(bundle_cartella)[:150])

        ledger_cartella = client.send("tools/call", {"name": "ad_unknowns", "arguments": {"action": "list", "ledger": "evidenze"}})
        check("ledger su una cartella rifiutato", ledger_cartella.get("error", {}).get("code") == -32602, str(ledger_cartella)[:150])

        testimone_cartella = client.send("tools/call", {"name": "ad_tree", "arguments": {"action": "check", "witness": "evidenze"}})
        check("testimone su una cartella rifiutato", testimone_cartella.get("error", {}).get("code") == -32602, str(testimone_cartella)[:150])
    finally:
        client.close()



def test_json_profondo_non_uccide() -> None:
    """Un JSON annidato 30.000 volte non deve uccidere il server (RecursionError)."""
    client = Client()
    try:
        profondo = '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":' + "[" * 30000 + "]" * 30000 + "}"
        esito = client.raw(profondo)
        check("JSON profondo -> -32700", esito.get("error", {}).get("code") == -32700, str(esito)[:150])
        check(
            "il rifiuto dice il rimedio",
            bool(esito["error"].get("data", {}).get("remediation")),
            str(esito)[:150],
        )
        vivo = client.send("ping")
        check("il server resta vivo", vivo.get("result") == {}, str(vivo)[:120])
    finally:
        client.close()


def test_import_non_esce_dalla_destinazione() -> None:
    """Il nome del file viene dal `gate` di un bundle: non deve uscire da `into`."""
    sorgente = ROOT / "evidenze" / ".test-escape-src.yaml"
    bundle_path = ROOT / "evidenze" / ".test-escape.json"
    destinazione = ROOT / "evidenze" / ".test-escape-dest"
    try:
        sorgente.write_text(
            "schema: 2\ntask_id: T\ngate: '../../tmp/escape'\noutcome: PASS\n"
            "producer: qa\nconfidence: observed\nauthority: execution\n"
            "coverage: {status: complete, examined: 1, total: 1}\nlimitations: []\n"
            "side_effects: {code: YES, database: NO, schema: NO, deps: NO, env: NO, "
            "external_services: NO}\n",
            encoding="utf-8",
        )
        bundle = ad_evidence.create_bundle([ad_evidence.load_evidence(sorgente)], [])
        bundle_path.write_text(ad_evidence.canonical_payload(bundle) + "\n", encoding="utf-8")
        client = Client()
        try:
            esito = client.call("ad_bundle", {
                "action": "import",
                "bundle_path": "evidenze/.test-escape.json",
                "into": "evidenze/.test-escape-dest",
            })
        finally:
            client.close()
        scritti = sorted(x.name for x in destinazione.iterdir())
        check("import riuscito", esito.get("records") == 1, str(esito))
        check("un solo file scritto", len(scritti) == 1, str(scritti))
        check("il nome e' sanificato", ".." not in scritti[0] and "/" not in scritti[0], scritti[0])
        check(
            "niente e' uscito dalla destinazione",
            not list(Path("/tmp").glob("escape*")),
            str(list(Path("/tmp").glob("escape*"))),
        )
    finally:
        sorgente.unlink(missing_ok=True)
        bundle_path.unlink(missing_ok=True)
        shutil.rmtree(destinazione, ignore_errors=True)


def test_witness_vuoto_nel_bundle() -> None:
    """Un `witness` passato e vuoto non e' 'usa il default': si rifiuta."""
    client = Client()
    try:
        esito = client.send("tools/call", {"name": "ad_bundle", "arguments": {
            "action": "export", "evidence": ["evidenze/ENG-001-QA.yaml"],
            "out": "evidenze/.test-w.json", "witness": ""}})
        check("witness vuoto rifiutato", esito.get("error", {}).get("code") == -32602, str(esito)[:150])
    finally:
        (ROOT / "evidenze" / ".test-w.json").unlink(missing_ok=True)
        client.close()



def test_residui_del_terzo_gate() -> None:
    """Ledger-cartella e percorso lunghissimo sono RIFIUTI, non errori interni."""
    client = Client()
    try:
        ledger_dir = client.send("tools/call", {"name": "ad_bundle", "arguments": {
            "action": "export", "evidence": ["evidenze/ENG-001-QA.yaml"],
            "out": "evidenze/.test-l.json", "ledger": "evidenze", "no_witness": True}})
        check("bundle con ledger-cartella rifiutato", ledger_dir.get("error", {}).get("code") == -32602, str(ledger_dir)[:160])

        lungo = "a" * 100000
        esito = client.send("tools/call", {"name": "ad_contract_check", "arguments": {"path": lungo}})
        check("percorso lunghissimo rifiutato, non interno", esito.get("error", {}).get("code") == -32602, str(esito)[:160])
        check(
            "il rifiuto dice il rimedio",
            bool(esito["error"].get("data", {}).get("remediation")),
            str(esito)[:160],
        )
    finally:
        (ROOT / "evidenze" / ".test-l.json").unlink(missing_ok=True)
        client.close()



def test_nul_e_percorsi_vuoti() -> None:
    """4o gate: un byte NUL e' un rifiuto con la ragione, non un errore interno."""
    client = Client()
    try:
        casi = [
            ("ad_contract_check", {"path": "tools/x\x00y"}),
            ("ad_contract_validate", {"contract": "contratti/x\x00.yaml"}),
            ("ad_verdict", {"contract": "contratti/x\x00.yaml", "evidence": ["evidenze/ENG-001-QA.yaml"]}),
            ("ad_evidence_check", {"evidence": ["evidenze/ENG-001-QA.yaml\x00"]}),
            ("ad_bundle", {"action": "check", "bundle_path": "evidenze/x\x00.json"}),
            ("ad_unknowns", {"action": "list", "ledger": "evidenze/x\x00.yaml"}),
            ("ad_tree", {"action": "check", "witness": "evidenze/x\x00.yaml"}),
            ("ad_tree", {"action": "record", "paths": ["tools\x00x"], "witness": "evidenze/.nul-tree.yaml"}),
        ]
        for nome, argomenti in casi:
            esito = client.send("tools/call", {"name": nome, "arguments": argomenti})
            codice = esito.get("error", {}).get("code")
            check(f"{nome}: NUL -> -32602", codice == -32602, str(esito)[:150])
            rimedio = str(esito.get("error", {}).get("data", {}).get("remediation", ""))
            check(f"{nome}: rimedio vero", "riprova" not in rimedio.lower(), rimedio[:120])

        for elenco in ([""], ["   "]):
            esito = client.send("tools/call", {"name": "ad_tree", "arguments": {
                "action": "record", "paths": elenco, "witness": "evidenze/.nul-tree.yaml"}})
            check(f"ad_tree paths={elenco!r} rifiutato", esito.get("error", {}).get("code") == -32602, str(esito)[:150])

        vivo = client.send("ping")
        check("il server resta vivo", vivo.get("result") == {}, str(vivo)[:120])
    finally:
        client.close()


def test_cli_rifiuta_percorsi_vuoti() -> None:
    """La libreria rifiuta i percorsi vuoti anche dal CLI (parita')."""
    with tempfile.TemporaryDirectory() as tmp:
        testimone = Path(tmp) / "w.yaml"
        esito = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "verdict.py"), "--tree", "record",
             "--tree-root", tmp, "--paths", "", "--witness", str(testimone)],
            capture_output=True, text=True, cwd=str(ROOT),
        )
    check("CLI: percorso vuoto rifiutato", esito.returncode == 2, f"exit {esito.returncode}: {esito.stdout[:120]}")
    check("CLI: nessun testimone scritto", not testimone.exists(), "testimone scritto")



def test_symlink_che_esce() -> None:
    """Un symlink che porta fuori dalla macchina e' rifiutato (il README lo dichiara:
    ora c'e' anche il test, rilievo E del gate di ENG-004)."""
    collegamento = ROOT / "evidenze" / ".test-symlink-esterno"
    try:
        collegamento.unlink(missing_ok=True)
        collegamento.symlink_to("/etc")
        client = Client()
        try:
            esito = client.send("tools/call", {"name": "ad_contract_check", "arguments": {
                "path": "evidenze/.test-symlink-esterno"}})
            check("symlink fuori: rifiutato", esito.get("error", {}).get("code") == -32602, str(esito)[:160])
            check(
                "symlink fuori: la ragione e' il confine",
                "fuori dalla macchina" in str(esito.get("error", {}).get("message", "")),
                str(esito)[:160],
            )
            controlla = client.send("tools/call", {"name": "ad_evidence_check", "arguments": {
                "evidence": ["evidenze/.test-symlink-esterno"]}})
            check("symlink fuori: rifiutato con la ragione", controlla.get("error", {}).get("code") == -32602, str(controlla)[:150])
        finally:
            client.close()
    except OSError:
        # Un filesystem senza symlink non deve far fallire la suite.
        check("symlink non disponibile su questo filesystem", True)
    finally:
        collegamento.unlink(missing_ok=True)

def test_nessuna_dipendenza() -> None:
    """Il server importa solo la libreria standard e PyYAML (gia' dipendenza di AD)."""
    testo = SERVER.read_text(encoding="utf-8")
    for vietato in ("import requests", "import httpx", "import anyio", "import mcp", "from mcp"):
        check(f"niente {vietato}", vietato not in testo, f"il server importa {vietato}")
    check("server con main", "def main()" in testo, "manca main")


def main() -> int:
    """Run the suite."""
    print("server MCP: handshake, catalogo, tool, rifiuti, parita'")
    test_handshake_e_catalogo()
    test_session()
    test_confine()
    test_parita_col_cli()
    test_prove_e_incognite()
    test_bundle_e_albero()
    test_registro()
    test_schemi_imposti()
    test_protocollo_rifiuti()
    test_cards_match()
    test_contract_validate()
    test_tree_rifiuti()
    test_bundle_unknowns_rifiuti()
    test_un_rifiuto_per_tool()
    test_limiti_e_range()
    test_utf8_e_method()
    test_percorsi_vuoti_e_cartelle()
    test_artifact_producer()
    test_stringhe_vuote_e_cartelle()
    test_json_profondo_non_uccide()
    test_import_non_esce_dalla_destinazione()
    test_witness_vuoto_nel_bundle()
    test_residui_del_terzo_gate()
    test_nul_e_percorsi_vuoti()
    test_cli_rifiuta_percorsi_vuoti()
    test_symlink_che_esce()
    test_nessuna_dipendenza()
    print(f"PASS — {PASSED} controlli sul server MCP")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
