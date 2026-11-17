#!/usr/bin/env python3
"""Code Mode sul nostro MCP: due tool invece di tredici (M3b, `DEC-0114`).

Perche' esiste. Un client MCP carica **tutte** le definizioni dei tool prima di scegliere.
Cloudflare (Code Mode) e Anthropic (code execution with MCP) hanno mostrato che conviene
dare al modello **due tool** — uno per cercare le definizioni, uno per eseguire codice che le
usa — e lasciare che i risultati intermedi restino nel codice invece di tornare nel contesto.

Da noi il catalogo e' piccolo (13 tool, 6.632 byte ≈ 1.658 token stimati con byte/4): il risparmio di definizioni e'
reale ma modesto. Il guadagno che conta e' la **composizione**: un solo giro per piu'
operazioni, e i risultati intermedi non passano dal modello.

Come funziona. `esegui` scrive lo script del modello in una cartella temporanea e lo lancia
**dentro `tools/sandbox.py`** (bubblewrap: rete spenta, filesystem in sola lettura, ambiente
azzerato, timeout). Il ponte (`tools/ad_mcp/codice/ponte.mjs`) passa allo script **solo**
`strumenti`: un client che chiama il server via CLI, quindi con le stesse validazioni dei tool.
Limiti dichiarati (non nascosti): il confinamento e' la sandbox di M2, **non** un isolate V8
come i Dynamic Workers di Cloudflare; il codice gira nello stesso processo node, puo'
importare i moduli di node (`fs`, `child_process`) e leggere i file leggibili dell'host
(limite 1-bis di `SECURITY.md`). L'allowlist di sola lettura del ponte e' una comodita',
non un confine: la difesa e' la sandbox.

Uso:
    python3 tools/codice.py metriche [--json]
    python3 tools/codice.py cerca "<testo>" [--dettaglio breve|pieno] [--json]
    python3 tools/codice.py esegui <file.js> [--argomenti JSON] [--timeout S] [--json]

Lo script JS e' un modulo ES con `export default async function (strumenti) { ... }` che
restituisce un valore JSON-serializzabile.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]
PONTE = RADICE / "tools" / "ad_mcp" / "codice" / "ponte.mjs"
SERVER = RADICE / "tools" / "ad_mcp" / "server.py"
sys.path.insert(0, str(RADICE / "tools"))

import sandbox  # noqa: E402

MAX_OUTPUT = 200_000


def _server():
    """Carica il server MCP per leggerne il catalogo (una volta)."""
    specifica = importlib.util.spec_from_file_location("ad_mcp_server_codice", SERVER)
    modulo = importlib.util.module_from_spec(specifica)
    specifica.loader.exec_module(modulo)  # type: ignore[union-attr]
    return modulo


def catalogo() -> list[dict]:
    """I tool che un client vede in modalita' classica (i due di Code Mode non si cercano)."""
    server = _server()
    return [
        {
            "name": voce["name"],
            "description": voce["description"],
            "inputSchema": voce["inputSchema"],
            "annotations": voce["annotations"],
        }
        for voce in server.TOOLS
    ]


def cerca(testo: str, *, dettaglio: str = "breve") -> dict:
    """Cerca nel catalogo. Restituisce solo i campi richiesti: e' il "progressive disclosure"."""
    parole = [p for p in testo.lower().split() if p]
    risultati = []
    for voce in catalogo():
        cercabile = (voce["name"] + " " + voce["description"] + " " + json.dumps(voce["inputSchema"])).lower()
        if all(parola in cercabile for parola in parole):
            voce_pulita = {"name": voce["name"], "description": voce["description"]}
            if dettaglio == "pieno":
                voce_pulita["inputSchema"] = voce["inputSchema"]
            risultati.append(voce_pulita)
    return {
        "query": testo,
        "dettaglio": dettaglio,
        "trovati": len(risultati),
        "tools": risultati,
        "nota": "per usare un tool: ad_esegui con uno script che chiama strumenti.<nome>(argomenti)",
    }


def metriche() -> dict:
    """Il costo vero delle due modalita', misurato: byte e stima token (byte/4)."""
    classico = json.dumps(catalogo(), ensure_ascii=False)
    server = _server()
    codice = json.dumps([
        {chiave: voce[chiave] for chiave in ("name", "description", "inputSchema")}
        for voce in server.STRUMENTI_CODICE
    ], ensure_ascii=False)
    esempio_cerca = json.dumps(cerca("verdetto", dettaglio="breve")["tools"][:1], ensure_ascii=False)
    codice_completo = codice + esempio_cerca
    classico_token = len(classico) // 4
    codice_token = len(codice_completo) // 4
    risparmio = round((1 - codice_token / classico_token) * 100, 1) if classico_token else 0.0
    return {
        "classico": {"tool": len(catalogo()), "byte": len(classico), "token_stimati": classico_token},
        "codice": {
            "tool": len(server.STRUMENTI_CODICE),
            "byte": len(codice_completo),
            "token_stimati": codice_token,
            "nota": "2 tool + un risultato di ricerca tipico",
        },
        "risparmio_percento": risparmio,
        "stima": "token = byte / 4 (approssimazione dichiarata, non un tokenizer)",
    }


def _errore(messaggio: str, rimedio: str) -> dict:
    return {"ok": False, "errore": messaggio, "rimedio": rimedio}


def esegui_sorgente(sorgente: str, *, argomenti: dict | None = None, timeout: int = 60) -> dict:
    """Esegue lo script JS nella sandbox. Restituisce il risultato o un errore dichiarato."""
    node = shutil.which("node")
    if node is None:
        return _errore("node non installato", "installa Node.js (>= 20) per la modalita' codice")
    if not PONTE.is_file():
        return _errore("ponte mancante", "manca tools/ad_mcp/codice/ponte.mjs")
    with tempfile.TemporaryDirectory(prefix="ad-codice-") as tmp:
        cartella = Path(tmp)
        script = cartella / "script.mjs"
        script.write_text(sorgente, encoding="utf-8")
        argomenti_file = cartella / "argomenti.json"
        argomenti_file.write_text(json.dumps(argomenti or {}, ensure_ascii=False), encoding="utf-8")
        # Il ponte espone solo i tool in sola lettura. ATTENZIONE, e' dichiarato onestamente:
        # questa NON e' la difesa. Il codice JS gira nello stesso processo node e puo'
        # importare i moduli di node (fs, child_process): puo' leggere file leggibili e
        # chiamare `server.py --tool` per conto suo. La difesa e' la sandbox (bwrap: rete
        # spenta, FS in sola lettura, ambiente azzerato) + le validazioni del server; il
        # filtro qui sotto e' una **comodita'** che evita gli errori, non un confine.
        consentiti = sorted(
            voce["name"]
            for voce in _server().TOOLS
            if (voce.get("annotations") or {}).get("readOnlyHint") is True
        )
        consentiti_file = cartella / "consentiti.json"
        consentiti_file.write_text(json.dumps(consentiti), encoding="utf-8")
        try:
            esito = sandbox.esegui(
                [node, str(PONTE), str(script), str(argomenti_file), str(SERVER), sys.executable, str(consentiti_file)],
                scrittura=(cartella,),
                timeout=timeout,
                # La chiave di firma non deve essere leggibile dal codice generato: la
                # sandbox monta un tmpfs sopra ~/.dsh (DEC-0115). Restano leggibili gli
                # altri file dell'host: limite dichiarato in SECURITY.md §4 1-bis.
                nascondi=(Path.home() / ".dsh",),
            )
        except subprocess.TimeoutExpired:
            return _errore("esecuzione scaduta", f"lo script ha superato {timeout}s: accorcialo o alza --timeout")
    if esito.returncode != 0:
        dettaglio = (esito.stderr or esito.stdout or "").strip()
        if esito.returncode == 124 or "timed out" in dettaglio.lower() or esito.returncode == -9:
            return _errore("esecuzione scaduta", f"lo script ha superato {timeout}s: accorcialo o alza --timeout")
        return _errore(
            f"esecuzione fallita (exit {esito.returncode})",
            (dettaglio[-1500:] or "il ponte non ha prodotto un risultato"),
        )
    uscita = (esito.stdout or "").strip()
    if len(uscita) > MAX_OUTPUT:
        uscita = uscita[:MAX_OUTPUT] + "\n…troncato (tetto di output)"
    try:
        return json.loads(uscita)
    except json.JSONDecodeError:
        return _errore("risposta del ponte non leggibile", uscita[:800] or "(vuota)")


def esegui_file(percorso: Path, *, argomenti: dict | None = None, timeout: int = 60) -> dict:
    if not percorso.is_file():
        return _errore(f"script non trovato: {percorso}", "indica un file .js/.mjs")
    return esegui_sorgente(percorso.read_text(encoding="utf-8"), argomenti=argomenti, timeout=timeout)


def main(argv: list[str] | None = None) -> int:
    analizzatore = argparse.ArgumentParser(description="Code Mode sul MCP: cerca ed esegui")
    sotto = analizzatore.add_subparsers(dest="azione", required=True)
    m = sotto.add_parser("metriche", help="costo delle due modalita'")
    m.add_argument("--json", action="store_true")
    c = sotto.add_parser("cerca", help="cerca nel catalogo dei tool")
    c.add_argument("testo")
    c.add_argument("--dettaglio", choices=("breve", "pieno"), default="breve")
    c.add_argument("--json", action="store_true")
    e = sotto.add_parser("esegui", help="esegue uno script JS nella sandbox")
    e.add_argument("script")
    e.add_argument("--argomenti", default="{}")
    e.add_argument("--timeout", type=int, default=60)
    e.add_argument("--json", action="store_true")

    args = analizzatore.parse_args(argv)
    if args.azione == "metriche":
        dati = metriche()
        if args.json:
            print(json.dumps(dati, indent=2, ensure_ascii=False))
        else:
            print(f"  classico: {dati['classico']['tool']} tool · {dati['classico']['byte']} byte · ~{dati['classico']['token_stimati']} token")
            print(f"  codice:   {dati['codice']['tool']} tool + ricerca · {dati['codice']['byte']} byte · ~{dati['codice']['token_stimati']} token")
            print(f"  risparmio: {dati['risparmio_percento']}%  ({dati['stima']})")
        return 0
    if args.azione == "cerca":
        dati = cerca(args.testo, dettaglio=args.dettaglio)
        if args.json:
            print(json.dumps(dati, indent=2, ensure_ascii=False))
        else:
            print(f"  {dati['trovati']} tool per «{args.testo}»:")
            for voce in dati["tools"]:
                print(f"    - {voce['name']}: {voce['description']}")
        return 0
    try:
        argomenti = json.loads(args.argomenti)
    except json.JSONDecodeError as errore:
        print(f"  --argomenti non e' JSON: {errore}", file=sys.stderr)
        return 2
    risultato = esegui_file(Path(args.script), argomenti=argomenti, timeout=args.timeout)
    print(json.dumps(risultato, indent=2, ensure_ascii=False))
    return 0 if risultato.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
