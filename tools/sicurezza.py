#!/usr/bin/env python3
"""La sicurezza in un comando: le difese sono ancora in piedi?

Perche' esiste (M2, `DEC-0112`). Il motore ha difese vere — il cancello sui write_scope,
il consenso firmato con una chiave esterna al repository, le evidenze con identita', lo
scanner dei segreti, la sandbox — ma nessuna di queste si accorge **da sola** quando cade.
Un documento di sicurezza non lo prende; un comando che esegue i controlli si'.

Cosa controlla (ogni voce dice il suo stato e perche'):

  segreti        gitleaks: nessuna credenziale nei file che possono finire in un commit
  chiave         la chiave di firma del consenso esiste, e solo il proprietario la legge
  manifest-mcp   i tool del server MCP e le loro descrizioni corrispondono al manifest
  tool-mcp       nessun tool fuori dall'allowlist `ad_*`, nessun duplicato
  sandbox        bubblewrap c'e' e funziona (rete spenta, filesystem in sola lettura)
  egress         la regola di lettura del web e' dichiarata (`ricerca.py regole`)
  istruzioni     nessun file che porta ordini oltre ai due legittimi del motore
  dipendenze     vulnerabilita' note nelle dipendenze dei file tracciati
  consenso       nessun marcatore di approvazione manomesso
  backup         un bundle recente del repository (via di ritorno)
  budget         ogni contract attivo dichiara un budget di tentativi
  audit          la vista operativa e' aggiornata (la memoria non mente)

**La regola che vale piu' di tutte**: un controllo che non si puo' eseguire e' `skip`,
mai `pass`. Un finto verde e' peggio di una lacuna dichiarata.

Uso:
    python3 tools/sicurezza.py             # umano
    python3 tools/sicurezza.py --json      # per la macchina
    python3 tools/sicurezza.py --aggiorna-manifest   # dopo un cambio vero dei tool MCP

Esito: 0 nessun controllo fallito (gli skip non contano come verdi ma non bloccano),
       1 almeno un controllo fallito, 2 uso sbagliato.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RADICE / "tools"))

import ad_consenso  # noqa: E402
import ad_coherence  # noqa: E402
import ad_docs  # noqa: E402
import ad_scope  # noqa: E402
import security_scan  # noqa: E402

MANIFEST = RADICE / "tools" / "ad_mcp" / "manifest.json"
SERVER = RADICE / "tools" / "ad_mcp" / "server.py"

#: I nomi dei tool sono un contratto con i client: quasi tutti `ad_*`.
PREFISSO_TOOL = "ad_"
#: I file del MOTORE che portano ordini per costruzione (costituzione e regola Cursor).
ISTRUZIONI_LEGITTIME = {"AGENTS.md", ".cursor/rules/ad-projects.mdc"}


def _esito(nome: str, stato: str, dettaglio: str, evidenza: str = "") -> dict:
    return {"controllo": nome, "stato": stato, "dettaglio": dettaglio, "evidenza": evidenza}


def _impronta_tool(voce: dict) -> str:
    """Impronta stabile di un tool: nome, descrizione e schema d'ingresso."""
    materiale = json.dumps(
        {
            "name": voce.get("name", ""),
            "description": voce.get("description", ""),
            "inputSchema": voce.get("inputSchema", {}),
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(materiale.encode("utf-8")).hexdigest()


def carica_tool_server() -> list[dict]:
    """I tool veri, letti dal server (non da una copia che puo' divergere).

    Include anche i due tool di Code Mode (`ad_cerca`, `ad_esegui`): il pinning
    anti-tool-poisoning deve coprire **tutti** i tool, non solo i classici (ENG-047).
    """
    specifica = importlib.util.spec_from_file_location("ad_mcp_server_sicurezza", SERVER)
    modulo = importlib.util.module_from_spec(specifica)
    specifica.loader.exec_module(modulo)  # type: ignore[union-attr]
    tutti = list(modulo.TOOLS) + list(modulo.STRUMENTI_CODICE)
    return tutti


def manifest_atteso(tools: list[dict]) -> dict:
    return {
        "schema": 1,
        "server": "ad-projects",
        "nota": "Impronta di nome+descrizione+schema. Se cambia senza questo file, la baseline va rossa: e' il tool poisoning.",
        "tools": {voce["name"]: _impronta_tool(voce) for voce in tools},
    }


# ---------------------------------------------------------------------------
# I controlli. Ognuno restituisce uno `_esito`.
# ---------------------------------------------------------------------------


def albero_solo_impronte(percorso: Path | None = None) -> tuple[bool, str]:
    """Controllo compensativo dell'esenzione di gitleaks: solo impronte, nessun valore.

    `evidenze/albero.yaml` e' un YAML con `digest`, `files` (percorso -> sha256), e due
    metadati. Se ci finisse una credenziale, non rispetterebbe questa forma.
    """
    import re

    import yaml

    file_albero = percorso or (RADICE / "evidenze" / "albero.yaml")
    if not file_albero.is_file():
        return True, "nessun file di impronte dell'albero"
    try:
        dati = yaml.safe_load(file_albero.read_text(encoding="utf-8"))
    except yaml.YAMLError as errore:
        return False, f"non e' YAML leggibile: {errore.__class__.__name__}"
    if not isinstance(dati, dict) or not isinstance(dati.get("files"), dict):
        return False, "manca la mappa `files`"
    # Una credenziale non starebbe in `files`: starebbe in una chiave nuova. Il
    # controllo compensativo vale solo se rifiuta TUTTO cio' che non e' dichiarato —
    # altrimenti l'esenzione di gitleaks sarebbe una porta aperta con una tenda.
    ammesse = {"digest", "exclude", "files", "paths", "recorded_at", "tree_version"}
    estranee = sorted(set(dati) - ammesse)
    if estranee:
        return False, f"chiavi non ammesse: {', '.join(estranee)}"
    if not re.fullmatch(r"tree_[0-9a-f]{64}", str(dati.get("digest", ""))):
        return False, "il `digest` non e' un'impronta tree_<64 hex>"
    for nome, impronta in dati["files"].items():
        if not re.fullmatch(r"[0-9a-f]{64}", str(impronta)):
            return False, f"`files/{nome}` non e' un'impronta sha256"
    return True, f"solo impronte ({len(dati['files'])} file)"


def controlla_segreti() -> dict:
    if security_scan._installed("gitleaks") is None:
        return _esito("segreti", "skip", "gitleaks non installato: nessuna prova")
    with tempfile.TemporaryDirectory(prefix="sicurezza-segreti-") as tmp:
        esito = security_scan.scan_segreti(RADICE, Path(tmp))
    if "errore" in esito:
        return _esito("segreti", "skip", f"scanner non eseguibile: {esito['errore']}")
    tracciabili = esito.get("tracciabili", [])
    if tracciabili:
        nomi = ", ".join(sorted({str(v.get("file")) for v in tracciabili})[:5])
        return _esito("segreti", "fail", f"{len(tracciabili)} segreti in file tracciabili: {nomi}")
    # Controllo compensativo dell'esenzione in `.gitleaks.toml`: il file delle impronte
    # e' esentato per percorso, quindi si verifica che contenga SOLO impronte. Se una
    # credenziale vera finisse li', avrebbe un'altra forma e questo la prenderebbe.
    ok, dettaglio = albero_solo_impronte()
    if not ok:
        return _esito("segreti", "fail", f"evidenze/albero.yaml: {dettaglio}")
    return _esito("segreti", "pass", "nessuna credenziale nei file tracciabili (e l'albero contiene solo impronte)")


def controlla_chiave(percorso: Path | None = None) -> dict:
    chiave = percorso or (ad_consenso.CARTELLA_CHIAVE / ad_consenso.NOME_CHIAVE)
    if not chiave.exists():
        return _esito("chiave", "fail", f"manca la chiave di firma: {chiave}")
    modo = stat.S_IMODE(chiave.stat().st_mode)
    if modo & 0o077:
        return _esito("chiave", "fail", f"permessi troppo larghi: {modo:o} (servono 600)")
    return _esito("chiave", "pass", f"chiave presente, permessi {modo:o}")


def controlla_manifest(tools: list[dict] | None = None, manifest: dict | None = None) -> dict:
    tools = tools if tools is not None else carica_tool_server()
    atteso = manifest_atteso(tools)
    if manifest is None:
        if not MANIFEST.is_file():
            return _esito("manifest-mcp", "fail", f"manca {MANIFEST.relative_to(RADICE)}: nessun pinning")
        try:
            manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as errore:
            return _esito("manifest-mcp", "fail", f"manifest illeggibile: {errore}")
    if manifest.get("tools") != atteso["tools"]:
        attuali = set(atteso["tools"])
        dichiarati = set(manifest.get("tools", {}))
        cambiati = sorted(
            nome for nome in attuali & dichiarati
            if manifest["tools"][nome] != atteso["tools"][nome]
        )
        dettaglio = []
        if cambiati:
            dettaglio.append(f"descrizioni/schemi cambiati: {', '.join(cambiati[:5])}")
        if attuali - dichiarati:
            dettaglio.append(f"tool nuovi: {', '.join(sorted(attuali - dichiarati)[:5])}")
        if dichiarati - attuali:
            dettaglio.append(f"tool spariti: {', '.join(sorted(dichiarati - attuali)[:5])}")
        return _esito(
            "manifest-mcp",
            "fail",
            "; ".join(dettaglio) + " — aggiorna il manifest solo se il cambio e' voluto",
        )
    return _esito("manifest-mcp", "pass", f"{len(atteso['tools'])} tool pinnati")


def controlla_tool(tools: list[dict] | None = None, nomi: list[str] | None = None) -> dict:
    tools = tools if tools is not None else carica_tool_server()
    elenco = nomi if nomi is not None else [voce.get("name", "") for voce in tools]
    fuori = [nome for nome in elenco if not nome.startswith(PREFISSO_TOOL)]
    duplicati = sorted({nome for nome in elenco if elenco.count(nome) > 1})
    if fuori:
        return _esito("tool-mcp", "fail", f"tool fuori dall'allowlist: {fuori[:5]}")
    if duplicati:
        return _esito("tool-mcp", "fail", f"tool duplicati: {duplicati[:5]}")
    return _esito("tool-mcp", "pass", f"{len(elenco)} tool, tutti `{PREFISSO_TOOL}*`")


def controlla_sandbox() -> dict:
    bwrap = shutil.which("bwrap")
    if bwrap is None:
        return _esito("sandbox", "skip", "bubblewrap non installato: la sandbox non c'e'")
    esito = subprocess.run(
        [bwrap, "--die-with-parent", "--unshare-net", "--ro-bind", "/", "/",
         "--dev", "/dev", "--proc", "/proc", "--tmpfs", "/tmp", "/bin/true"],
        capture_output=True, text=True, timeout=30,
    )
    if esito.returncode != 0:
        return _esito("sandbox", "fail", f"bwrap presente ma non esegue: {esito.stderr.strip()[:160]}")
    return _esito("sandbox", "pass", "bubblewrap funziona con rete spenta e filesystem in sola lettura")


def controlla_egress() -> dict:
    ricerca = RADICE / "tools" / "ricerca.py"
    if not ricerca.is_file():
        return _esito("egress", "fail", "manca tools/ricerca.py: nessuna regola di lettura del web")
    esito = subprocess.run([sys.executable, str(ricerca), "regole"], capture_output=True, text=True, timeout=30)
    if esito.returncode != 0:
        return _esito("egress", "fail", f"le regole del web non si leggono: {esito.stderr.strip()[:160]}")
    testo = esito.stdout.lower()
    for parola in ("muro di pagamento", "dati personali", "scaricare in massa"):
        if parola not in testo:
            return _esito("egress", "fail", f"la regola del web non nomina «{parola}»")
    return _esito("egress", "pass", "la regola di lettura del web e' dichiarata e completa")


def controlla_istruzioni() -> dict:
    esito = security_scan.scan_istruzioni(RADICE)
    attivi = [voce for voce in esito.get("attivi", []) if voce.get("file") not in ISTRUZIONI_LEGITTIME]
    if attivi:
        return _esito(
            "istruzioni",
            "fail",
            "file che portano ordini fuori dall'elenco ammesso: "
            + ", ".join(str(v.get("file")) for v in attivi[:5]),
        )
    return _esito("istruzioni", "pass", "solo i due documenti legittimi portano ordini")


def controlla_dipendenze() -> dict:
    if security_scan._installed("osv-scanner") is None:
        return _esito("dipendenze", "skip", "osv-scanner non installato: nessuna prova")
    esito = security_scan.scan_dipendenze(RADICE)
    if "errore" in esito:
        return _esito("dipendenze", "skip", f"scanner non eseguibile: {esito['errore']}")
    vulns = [v for v in esito.get("vulnerabilita", []) if not str(v.get("file", "")).startswith("studio/")]
    file_letti = [f for f in esito.get("file_letti", []) if "studio/" not in f]
    if not file_letti:
        return _esito("dipendenze", "skip", "nessun lockfile tracciato: le dipendenze del motore sono la libreria standard")
    if vulns:
        return _esito("dipendenze", "fail", f"{len(vulns)} vulnerabilita' con fix disponibile nei file tracciati")
    return _esito("dipendenze", "pass", f"{len(file_letti)} lockfile tracciati, nessuna vulnerabilita' con fix")


def controlla_consenso() -> dict:
    try:
        esiti = ad_consenso.verifica_tutti(RADICE)
    except ad_consenso.Rifiuto as errore:
        return _esito("consenso", "skip", f"chiave non disponibile: {errore}")
    manomessi = [task for stato, task, _ in esiti if stato == "manomessa"]
    if manomessi:
        return _esito("consenso", "fail", f"marcatori manomessi: {', '.join(manomessi[:5])}")
    return _esito("consenso", "pass", f"{len(esiti)} marcatori, nessuno manomesso")


def controlla_backup(giorni: int = 30) -> dict:
    cartella = RADICE / "backup"
    if not cartella.is_dir():
        return _esito("backup", "fail", "manca backup/: nessuna via di ritorno")
    bundle = sorted(cartella.glob("*.bundle"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not bundle:
        return _esito("backup", "fail", "nessun bundle in backup/")
    import datetime

    eta = (datetime.datetime.now().timestamp() - bundle[0].stat().st_mtime) / 86400
    if eta > giorni:
        return _esito("backup", "fail", f"l'ultimo bundle ha {eta:.0f} giorni (soglia {giorni})")
    return _esito("backup", "pass", f"ultimo bundle: {bundle[0].name} ({eta:.0f} giorni fa)")


def controlla_budget() -> dict:
    import yaml

    mancanti = []
    for scope in ad_scope.load_write_scopes(RADICE):
        try:
            dati = yaml.safe_load(Path(scope.source).read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(dati.get("budget"), dict):
            mancanti.append(scope.task_id)
    if mancanti:
        return _esito("budget", "fail", f"contract attivi senza budget: {mancanti[:5]}")
    return _esito("budget", "pass", "ogni contract attivo dichiara il suo budget")


def controlla_audit() -> dict:
    esito = subprocess.run(
        [sys.executable, str(RADICE / "tools" / "stato.py"), "check"],
        capture_output=True, text=True, timeout=60,
    )
    if esito.returncode != 0:
        return _esito("audit", "fail", "la vista operativa non e' aggiornata: rigenerala con `stato.py render`")
    return _esito("audit", "pass", "la vista operativa e' aggiornata")


CONTROLLI = (
    controlla_segreti,
    controlla_chiave,
    controlla_manifest,
    controlla_tool,
    controlla_sandbox,
    controlla_egress,
    controlla_istruzioni,
    controlla_dipendenze,
    controlla_consenso,
    controlla_backup,
    controlla_budget,
    controlla_audit,
)


def esegui() -> list[dict]:
    esiti = []
    for controllo in CONTROLLI:
        try:
            esiti.append(controllo())
        except Exception as errore:  # noqa: BLE001 - un controllo che esplode e' un fail
            esiti.append(_esito(getattr(controllo, "__name__", "?"), "fail", f"il controllo e' esploso: {errore}"))
    return esiti


def main(argv: list[str] | None = None) -> int:
    analizzatore = argparse.ArgumentParser(description="La sicurezza del motore, in un comando")
    analizzatore.add_argument("--json", action="store_true", help="esito strutturato")
    analizzatore.add_argument(
        "--aggiorna-manifest",
        action="store_true",
        help="riscrive il manifest MCP dai tool veri (dopo un cambio voluto)",
    )
    args = analizzatore.parse_args(argv)

    if args.aggiorna_manifest:
        atteso = manifest_atteso(carica_tool_server())
        MANIFEST.write_text(json.dumps(atteso, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"  manifest aggiornato: {MANIFEST.relative_to(RADICE)} ({len(atteso['tools'])} tool)")
        return 0

    esiti = esegui()
    falliti = [e for e in esiti if e["stato"] == "fail"]
    passati = [e for e in esiti if e["stato"] == "pass"]
    saltati = [e for e in esiti if e["stato"] == "skip"]

    if args.json:
        print(json.dumps({"esiti": esiti, "falliti": len(falliti), "passati": len(passati),
                          "saltati": len(saltati), "ok": not falliti}, indent=2, ensure_ascii=False))
        return 0 if not falliti else 1

    for esito in esiti:
        segno = {"pass": "ok  ", "fail": "NO  ", "skip": "skip"}[esito["stato"]]
        print(f"  {segno} {esito['controllo']:<14} {esito['dettaglio']}")
    print()
    print(f"  {len(passati)} pass · {len(falliti)} fail · {len(saltati)} skip")
    if saltati:
        print("  Gli skip NON sono verdi: dicono cosa non e' stato possibile provare.")
    if falliti:
        print("  esito: ROSSO — una difesa dichiarata non e' piu' in piedi")
        return 1
    print("  esito: verde sulle difese eseguibili")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
