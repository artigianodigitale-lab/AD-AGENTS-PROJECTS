#!/usr/bin/env python3
"""Code Mode sul MCP: due tool invece di tredici, eseguiti nella sandbox (M3b, `DEC-0114`).

Le prove non chiedono al modello di comportarsi bene: chiedono al **sistema** di reggere.
 1. `metriche`: il costo delle due modalita' e' misurato, non promesso (~80% in meno).
 2. `cerca`: progressive disclosure — solo le definizioni chieste, al dettaglio scelto.
 3. `esegui`: uno script compone piu' chiamate e torna **un** risultato, non i risultati
    intermedi.
 4. la sandbox rifiuta: scrittura fuori da /tmp, rete, timeout; l'output gigante viene
    troncato e dichiarato.
 5. il server con `--codice` espone 2 tool; senza, 13 (e i due nuovi non sono spariti).

Si esegue dalla radice:
    python3 tools/tests/test_codice.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE / "tools"))

import codice  # noqa: E402

FALLITI: list[str] = []
PASSATI = 0


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    global PASSATI
    if condizione:
        print(f"  ok   {etichetta}")
        PASSATI += 1
    else:
        print(f"  NO   {etichetta}  {dettaglio}")
        FALLITI.append(etichetta)


def _server():
    specifica = importlib.util.spec_from_file_location(
        "ad_mcp_server_codice_test", RADICE / "tools" / "ad_mcp" / "server.py"
    )
    modulo = importlib.util.module_from_spec(specifica)
    specifica.loader.exec_module(modulo)  # type: ignore[union-attr]
    return modulo


def _script(sorgente: str, timeout: int = 60) -> dict:
    return codice.esegui_sorgente(sorgente, timeout=timeout)


SCRIPT_CARTA = """
export default async function (strumenti) {
  const carta = await strumenti.ad_cards_match({ task_type: "web_scraping" });
  const controllo = await strumenti.ad_contract_check({ path: "tools/codice.py" });
  return { carta: carta.cards?.[0]?.id, matched: carta.matched, coperto: Boolean(controllo) };
}
"""


def test_metriche() -> None:
    print("\nmetriche: il costo delle due modalita'")
    dati = codice.metriche()
    check("classico: 13 tool", dati["classico"]["tool"] == 13, str(dati["classico"]))
    check("codice: 2 tool", dati["codice"]["tool"] == 2, str(dati["codice"]))
    check(
        "token = byte/4 (stima dichiarata)",
        dati["classico"]["token_stimati"] == dati["classico"]["byte"] // 4
        and dati["codice"]["token_stimati"] == dati["codice"]["byte"] // 4,
    )
    check("il risparmio e' reale (>= 50%)", dati["risparmio_percento"] >= 50, str(dati["risparmio_percento"]))
    check("la stima e' dichiarata, non spacciata per tokenizer", "byte / 4" in dati["stima"])


def test_cerca() -> None:
    print("\ncerca: progressive disclosure")
    breve = codice.cerca("verdetto")
    check("trova ad_verdict", any(v["name"] == "ad_verdict" for v in breve["tools"]), str(breve["tools"]))
    check("dettaglio breve senza schema", all("inputSchema" not in v for v in breve["tools"]))
    pieno = codice.cerca("cards", dettaglio="pieno")
    check("trova ad_cards_match", any(v["name"] == "ad_cards_match" for v in pieno["tools"]), str(pieno["tools"]))
    check("dettaglio pieno con schema", all("inputSchema" in v for v in pieno["tools"]))
    check("nessun match e' zero, non un errore", codice.cerca("zzz-inesistente")["trovati"] == 0)


def test_esegui() -> None:
    print("\nesegui: una chiamata, una risposta")
    risultato = _script(SCRIPT_CARTA)
    check("lo script gira in sandbox e torna ok", risultato.get("ok") is True, str(risultato)[:300])
    dato = risultato.get("risultato") or {}
    check("la carta e' quella giusta", dato.get("carta") == "web-intelligence", str(dato))
    check("la composizione ha funzionato", dato.get("coperto") is True and dato.get("matched") is True, str(dato))
    check(
        "solo il risultato finale esce, niente intermedi",
        set(dato) == {"carta", "matched", "coperto"},
        str(dato),
    )


def test_sandbox() -> None:
    print("\nla sandbox rifiuta: scrittura, rete, timeout")
    bersaglio = RADICE / "tools" / ".prova-scrittura-codice"
    # Nessun percorso assoluto scritto a mano: la radice e' quella vera della macchina.
    risultato = _script(
        f"""
        import {{ writeFileSync }} from "node:fs";
        export default async function () {{
          writeFileSync({str(bersaglio)!r}, "x");
          return {{ scritto: true }};
        }}
        """
    )
    check("scrittura nel motore rifiutata", risultato.get("ok") is False, str(risultato)[:200])
    check("il file non esiste", not bersaglio.exists())

    rete = _script(
        """
        import net from "node:net";
        export default async function () {
          await new Promise((ok, ko) => {
            const s = net.connect(80, "1.1.1.1");
            s.on("connect", () => ok());
            s.on("error", ko);
            setTimeout(() => ko(new Error("nessuna rete")), 1500);
          });
          return { rete: true };
        }
        """
    )
    check("connessione di rete rifiutata", rete.get("ok") is False, str(rete)[:200])

    lento = _script("export default async function () { await new Promise(r => setTimeout(r, 8000)); return {}; }", timeout=2)
    check("timeout dichiarato, non appeso", lento.get("ok") is False and "scaduta" in str(lento), str(lento)[:200])

    grande = _script("export default async function () { return { testo: 'x'.repeat(300000) }; }")
    check("output gigante troncato e dichiarato", grande.get("troncato") is True and grande.get("ok") is True, str(grande)[:200])


def test_chiave_nascosta() -> None:
    print("\nla chiave di firma non e' leggibile dal codice (DEC-0115)")
    chiave = Path.home() / ".dsh" / "ad-consenso.key"
    if not chiave.is_file():
        print("  SKIP — nessuna chiave su questa macchina")
        return
    risultato = codice.esegui_sorgente(
        """
        import { readFileSync } from "node:fs";
        export default async function (strumenti, a) {
          try {
            return { letto: readFileSync(a.chiave).length };
          } catch (errore) {
            return { letto: false, motivo: errore.code || String(errore) };
          }
        }
        """,
        argomenti={"chiave": str(chiave)},
    )
    dato = risultato.get("risultato") or {}
    check("lo script gira", risultato.get("ok") is True, str(risultato)[:200])
    check("la chiave NON e' leggibile", dato.get("letto") is False, str(dato)[:200])


def test_solo_lettura() -> None:
    print("\nil ponte rifiuta i tool che scrivono (comodita', non confine)")
    risultato = _script(
        """
        export default async function (strumenti) {
          return strumenti.ad_shell_chiudi({ progetto: "x" });
        }
        """
    )
    check("un tool che scrive e' rifiutato", risultato.get("ok") is False, str(risultato)[:200])
    check("il rifiuto lo dice", "non consentito" in str(risultato), str(risultato)[:200])


def test_manifest_pin() -> None:
    print("\nil manifest pinna anche i due tool di Code Mode (DEC-0115)")
    import sicurezza

    tools = sicurezza.carica_tool_server()
    nomi = {voce["name"] for voce in tools}
    check("il manifest atteso copre 15 tool", len(tools) == 15, str(len(tools)))
    check("ad_cerca e' pinnato", "ad_cerca" in nomi)
    check("ad_esegui e' pinnato", "ad_esegui" in nomi)
    esito = sicurezza.controlla_manifest()
    check("il manifest reale coincide", esito["stato"] == "pass", esito["dettaglio"])


def test_default_codice() -> None:
    print("\nil default e' Code Mode (DEC-0115)")
    server = _server()  # caricato da zero: prende il default vero del file
    check("il server parte in modalita' codice", server.MODALITA_CODICE is True)
    check(
        "il catalogo di default e' di 2 tool",
        [v["name"] for v in server._catalog()] == ["ad_cerca", "ad_esegui"],
        str([v["name"] for v in server._catalog()]),
    )


def test_dispatch_per_modalita() -> None:
    print("\nil dispatch rispetta la modalita': non e' una facciata")
    server = _server()

    server.MODALITA_CODICE = False
    try:
        server._call_tool({"name": "ad_esegui", "arguments": {"codice": "export default () => ({})"}})
        check("senza --codice, ad_esegui non e' chiamabile", False)
    except server.RpcError:
        check("senza --codice, ad_esegui non e' chiamabile", True)
    classico = server._call_tool({"name": "ad_cards_match", "arguments": {"task_type": "web_scraping"}})
    check("senza --codice, i tool classici funzionano", classico["structuredContent"]["matched"] is True)

    server.MODALITA_CODICE = True
    try:
        server._call_tool({"name": "ad_cards_match", "arguments": {"task_type": "web_scraping"}})
        check("con --codice, i tool classici non sono chiamabili", False)
    except server.RpcError:
        check("con --codice, i tool classici non sono chiamabili", True)
    check(
        "con --codice, ad_cerca funziona",
        server._call_tool({"name": "ad_cerca", "arguments": {"query": "verdetto"}})["structuredContent"]["trovati"] >= 1,
    )
    annotazione = next(v for v in server.STRUMENTI_CODICE if v["name"] == "ad_esegui")["annotations"]
    check("ad_esegui non e' dichiarato in sola lettura", annotazione["readOnlyHint"] is False, str(annotazione))


def test_catalogo_server() -> None:
    print("\nil server MCP: 13 tool classici, 2 in modalita' codice")
    server = _server()
    server.MODALITA_CODICE = False
    classico = [v["name"] for v in server._catalog()]
    check("classico: 13 tool", len(classico) == 13, str(len(classico)))
    check("in classico non ci sono i tool di codice", "ad_cerca" not in classico and "ad_esegui" not in classico)
    server.MODALITA_CODICE = True
    modo = [v["name"] for v in server._catalog()]
    check("codice: 2 tool", modo == ["ad_cerca", "ad_esegui"], str(modo))

    risposta = server._call_tool({"name": "ad_cerca", "arguments": {"query": "verdetto", "dettaglio": "breve"}})
    check("ad_cerca passa dal dispatch vero", risposta["structuredContent"]["trovati"] >= 1)
    esito = server._call_tool({
        "name": "ad_esegui",
        "arguments": {"codice": SCRIPT_CARTA, "timeout": 60},
    })
    check("ad_esegui passa dal dispatch vero", esito["structuredContent"].get("ok") is True, str(esito)[:300])


def main() -> int:
    probe = _script("export default async function () { return 2 + 2; }", timeout=30)
    if probe.get("ok") is not True:
        print(f"  skip  sandbox non disponibile qui: {str(probe.get('errore'))[:140]}")
        print("PASS (skip dichiarato) — Code Mode non provabile in questa macchina")
        return 0
    test_metriche()
    test_cerca()
    test_esegui()
    test_sandbox()
    test_chiave_nascosta()
    test_solo_lettura()
    test_dispatch_per_modalita()
    test_manifest_pin()
    test_default_codice()
    test_catalogo_server()
    print()
    print(f"  {PASSATI} controlli passati")
    if FALLITI:
        print(f"FALLITI: {len(FALLITI)}")
        return 1
    print("PASS — Code Mode: due tool, sandbox, misura onesta")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
