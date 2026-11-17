#!/usr/bin/env python3
"""La baseline di sicurezza misura davvero quello che dichiara (M2, `DEC-0112`).

Si prova la baseline sul motore vero — e si prova che le funzioni che possono fallire
**falliscono davvero** su un caso costruito: un permesso di chiave largo, un manifest
alterato, un tool fuori allowlist. Una difesa che non si e' mai vista fallire non e' una
difesa: e' una speranza.

Si esegue dalla radice:
    python3 tools/tests/test_sicurezza.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RADICE / "tools"))

import sicurezza  # noqa: E402

FALLITI: list[str] = []


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    if condizione:
        print(f"  ok   {etichetta}")
    else:
        print(f"  NO   {etichetta}  {dettaglio}")
        FALLITI.append(etichetta)


def test_baseline_reale() -> None:
    print("\nla baseline sul motore vero")
    esito = subprocess.run(
        [sys.executable, str(RADICE / "tools" / "sicurezza.py"), "--json"],
        cwd=str(RADICE), capture_output=True, text=True, timeout=300,
    )
    try:
        dati = json.loads(esito.stdout)
    except json.JSONDecodeError:
        check("la baseline produce JSON", False, (esito.stdout + esito.stderr)[:300])
        return
    check("la baseline produce JSON", True)
    check("la baseline non ha fallimenti", dati.get("ok") is True, str(dati.get("falliti")))
    check(
        "ogni controllo ha stato e dettaglio",
        all(e.get("stato") in ("pass", "fail", "skip") and e.get("dettaglio") for e in dati["esiti"]),
        str(dati["esiti"])[:400],
    )
    check(
        "gli skip sono dichiarati, non verdi",
        all(e["stato"] == "skip" for e in dati["esiti"] if e.get("stato") == "skip"),
        "",
    )
    print(f"       {dati['passati']} pass · {dati['falliti']} fail · {dati['saltati']} skip")


def test_chiave_larga_fallisce() -> None:
    print("\nla verifica della chiave morde")
    with tempfile.TemporaryDirectory(prefix="prova-chiave-") as tmp:
        chiave = Path(tmp) / "chiave"
        chiave.write_bytes(b"x" * 32)
        chiave.chmod(0o644)
        largo = sicurezza.controlla_chiave(chiave)
        chiave.chmod(0o600)
        stretto = sicurezza.controlla_chiave(chiave)
    check("permessi 644 -> fail", largo["stato"] == "fail", largo["dettaglio"])
    check("permessi 600 -> pass", stretto["stato"] == "pass", stretto["dettaglio"])
    check("una chiave assente -> fail", sicurezza.controlla_chiave(Path("/non/esiste/chiave"))["stato"] == "fail")


def test_manifest_alterato_fallisce() -> None:
    print("\nil manifest alterato fa rosso")
    tools = sicurezza.carica_tool_server()
    atteso = sicurezza.manifest_atteso(tools)
    check("il manifest copre tutti i tool", set(atteso["tools"]) == {t["name"] for t in tools})
    alterato = sicurezza.manifest_atteso(tools)
    primo = sorted(alterato["tools"])[0]
    alterato["tools"][primo] = "sha256:" + "0" * 64
    esito = sicurezza.controlla_manifest(tools, manifest=alterato)
    check("descrizione alterata -> fail", esito["stato"] == "fail", esito["dettaglio"])
    pulito = sicurezza.controlla_manifest(tools, manifest=sicurezza.manifest_atteso(tools))
    check("manifest coerente -> pass", pulito["stato"] == "pass", pulito["dettaglio"])


def test_tool_fuori_allowlist() -> None:
    print("\nil tool fuori allowlist non passa")
    esito = sicurezza.controlla_tool(nomi=["ad_session", "esegui_comando"])
    check("tool arbitrario -> fail", esito["stato"] == "fail", esito["dettaglio"])
    check(
        "tool ad_* -> pass",
        sicurezza.controlla_tool(nomi=["ad_session", "ad_verdict"])["stato"] == "pass",
    )


def test_controllo_compensativo_albero() -> None:
    print("\nl'esenzione delle impronte non copre una credenziale")
    import tempfile

    buono = (
        "digest: tree_" + "a" * 64 + "\n"
        "files:\n  tools/x.py: " + "b" * 64 + "\n"
        "tree_version: 1\n"
    )
    # Costruita a runtime: scritta per intero sarebbe un segreto in un file tracciato.
    cattivo = buono + "aws_key: " + "AKIA" + "3X7QZ2LMN5OPQRST\n"
    with tempfile.TemporaryDirectory(prefix="prova-albero-") as tmp:
        percorso = Path(tmp) / "albero.yaml"
        percorso.write_text(buono, encoding="utf-8")
        ok, dettaglio = sicurezza.albero_solo_impronte(percorso)
        check("un albero di sole impronte -> pass", ok, dettaglio)
        percorso.write_text(cattivo, encoding="utf-8")
        ok, dettaglio = sicurezza.albero_solo_impronte(percorso)
        check("una chiave aggiunta all'albero -> fail", not ok, dettaglio)


def main() -> int:
    test_baseline_reale()
    test_chiave_larga_fallisce()
    test_manifest_alterato_fallisce()
    test_tool_fuori_allowlist()
    test_controllo_compensativo_albero()
    print()
    if FALLITI:
        print(f"FALLITI: {len(FALLITI)}")
        return 1
    print("PASS — la baseline misura, e le sue difese mordono")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
