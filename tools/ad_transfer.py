#!/usr/bin/env python3
"""Il libro mastro dei trasferimenti di proprieta' (DEC-0093).

Perche' esiste. Il registro delle autorizzazioni impedisce che due contract scrivano lo
stesso percorso: e' la regola giusta (DEC-0054). Ma non distingueva due casi diversi:

  - un titolare che **sta lavorando**: deve bloccare;
  - un titolare il cui lavoro **e' finito** ma il cui contract resta aperto: bloccava
    per sempre, e la macchina si fermava su un conflitto di forma.

Il 2026-11-02 e' successo: `tests/gate_kit.py` era di `ENG-019`, il lavoro era fatto e
verde, e nessun altro contract poteva toccarlo. La reazione giusta e' stata fermarsi
(invariante 9), ma senza una via d'uscita il sistema si blocca a ogni ritiro.

La via d'uscita e' un **atto esplicito**, non un effetto collaterale:

  1. il ritiro (`superseded`) **non libera** i percorsi;
  2. la liberazione e' un trasferimento, con cedente, ricevente e decisione;
  3. il trasferimento verifica tre cose prima di scrivere (vedi `trasferisci`);
  4. resta nel libro mastro, che si legge e non si modifica;
  5. la storia non si riscrive: si aggiunge una riga, non si cancella un fatto.

Uso:
    python3 tools/ad_transfer.py elenca
    python3 tools/ad_transfer.py verifica --da ENG-019 --a ENG-021
    python3 tools/ad_transfer.py trasferisci --da ENG-019 --a ENG-021 \
        --decisione DECISIONI/DEC-0093-proprietario-trasferimento-percorsi.md

Esito: 0 tutto a posto · 1 rifiutato (e il messaggio dice perche') · 2 uso sbagliato.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

RADICE = Path(__file__).resolve().parents[1]
#: Il libro mastro: accanto ai contract, e non dentro un contract.
LIBRO = RADICE / "contratti" / "_trasferimenti.yaml"
#: Gli stati in cui un contract puo' cedere: il lavoro e' finito, la forma non e' chiusa.
CEDENTI_AMMESSI = ("superseded", "superato", "closed", "chiuso")
#: Gli stati in cui un contract puo' ricevere.
RICEVENTI_AMMESSI = ("active", "attivo", "approvato")


class Rifiuto(Exception):
    """Un trasferimento non si puo' fare, e il messaggio dice perche'. Esito 1."""


def _cartella_contract(root: Path) -> Path:
    return root / "contratti"


def _leggi_contract(percorso: Path) -> dict:
    """Il contract, o un rifiuto con la ragione. Non solleva mai su un file storto."""
    try:
        testo = percorso.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as errore:
        raise Rifiuto(f"«{percorso}» non si legge: {errore}") from None
    try:
        dato = yaml.safe_load(testo)
    except yaml.YAMLError as errore:
        raise Rifiuto(f"«{percorso}» non e' YAML valido: {errore}") from None
    if not isinstance(dato, dict):
        raise Rifiuto(f"«{percorso}» non contiene una mappatura")
    return dato


def trova(task: str, root: Path = RADICE) -> Path:
    """Il file di un contract, cercando in ogni gruppo del registro."""
    cercato = task.strip().upper()
    for percorso in sorted(_cartella_contract(root).glob("*/*.yaml")):
        if percorso.stem.upper() == cercato:
            return percorso
    raise Rifiuto(
        f"nessun contract «{task}». I contract stanno in contratti/<gruppo>/<TASK>.yaml"
    )


def stato(percorso: Path) -> str:
    """Lo stato dichiarato dal contract, in minuscolo."""
    return str(_leggi_contract(percorso).get("status") or "").strip().lower()


def percorsi(percorso: Path) -> tuple[str, ...]:
    """Il write_scope del contract, normalizzato."""
    grezzo = _leggi_contract(percorso).get("write_scope") or []
    if not isinstance(grezzo, list):
        raise Rifiuto(f"«{percorso}» ha un write_scope che non e' un elenco")
    return tuple(str(voce).strip() for voce in grezzo if str(voce).strip())


def leggi_libro(root: Path = RADICE) -> dict:
    """Il libro mastro, o un libro vuoto se non c'e' ancora."""
    libro = root / "contratti" / "_trasferimenti.yaml"
    if not libro.is_file():
        return {"trasferimenti": []}
    try:
        dato = yaml.safe_load(libro.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as errore:
        raise Rifiuto(f"il libro mastro non si legge ({errore}): non trasferisco a meta'") from None
    if not isinstance(dato, dict):
        return {"trasferimenti": []}
    voci = dato.get("trasferimenti")
    if not isinstance(voci, list):
        dato["trasferimenti"] = []
    return dato


def gia_trasferiti(root: Path = RADICE) -> dict[str, str]:
    """I percorsi gia' ceduti, con il task che li ha ricevuti."""
    ceduti: dict[str, str] = {}
    for voce in leggi_libro(root).get("trasferimenti", []):
        if not isinstance(voce, dict):
            continue
        ricevente = str(voce.get("a") or "")
        for percorso in voce.get("percorsi") or []:
            ceduti[str(percorso)] = ricevente
    return ceduti


def _modifiche_concorrenti(elenco: tuple[str, ...], root: Path) -> list[str]:
    """I percorsi con modifiche non committate: trasferirli ora mescolerebbe due lavori."""
    sporchi: list[str] = []
    for percorso in elenco:
        esito = subprocess.run(
            ["git", "status", "--porcelain", "--", percorso],
            cwd=str(root),
            capture_output=True,
            text=True,
        )
        if esito.returncode == 0 and esito.stdout.strip():
            sporchi.append(percorso)
    return sporchi


def verifica(da: str, a: str, root: Path = RADICE) -> tuple[tuple[str, ...], list[str]]:
    """Le tre verifiche del protocollo. Restituisce (percorsi, avvisi) o solleva Rifiuto."""
    cedente = trova(da, root)
    ricevente = trova(a, root)

    stato_cedente = stato(cedente)
    if stato_cedente not in CEDENTI_AMMESSI:
        raise Rifiuto(
            f"{da} e' «{stato_cedente}»: puo' cedere soltanto un contract ritirato o chiuso "
            f"({', '.join(CEDENTI_AMMESSI)}). Un contract che lavora non si tocca."
        )

    stato_ricevente = stato(ricevente)
    if stato_ricevente not in RICEVENTI_AMMESSI:
        raise Rifiuto(
            f"{a} e' «{stato_ricevente}»: puo' ricevere soltanto un contract attivo "
            f"({', '.join(RICEVENTI_AMMESSI)})."
        )

    elenco = percorsi(cedente)
    if not elenco:
        raise Rifiuto(f"{da} non dichiara percorsi nel write_scope: non c'e' niente da cedere")

    gia = gia_trasferiti(root)
    doppi = [p for p in elenco if p in gia and gia[p] != a]
    if doppi:
        raise Rifiuto(
            "questi percorsi sono gia' stati trasferiti altrove: "
            + ", ".join(f"{p} -> {gia[p]}" for p in doppi)
        )

    sporchi = _modifiche_concorrenti(elenco, root)
    if sporchi:
        raise Rifiuto(
            "questi percorsi hanno modifiche non committate: committale o mettile da parte "
            "prima di trasferirli, altrimenti il trasferimento mescola due lavori — "
            + ", ".join(sporchi)
        )

    avvisi: list[str] = []
    miei_ricevente = percorsi(ricevente)
    for percorso in elenco:
        if percorso not in miei_ricevente:
            avvisi.append(
                f"«{percorso}» non e' nel write_scope di {a}: dopo il trasferimento nessuno "
                "lo coprira' finche' non lo aggiungi"
            )
    return elenco, avvisi


def trasferisci(da: str, a: str, decisione: str, root: Path = RADICE) -> dict:
    """Esegue il trasferimento e scrive la riga nel libro mastro."""
    import time

    if not decisione.strip():
        raise Rifiuto("serve la decisione che autorizza il trasferimento (--decisione DEC-...)")
    percorso_decisione = root / decisione.strip()
    if not percorso_decisione.is_file():
        raise Rifiuto(f"la decisione «{decisione}» non esiste: un trasferimento senza una "
                      "decisione scritta e' un atto senza titolo")

    elenco, avvisi = verifica(da, a, root)
    libro = leggi_libro(root)
    libretto = root / "contratti" / "_trasferimenti.yaml"
    voce = {
        "data": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "da": da.strip().upper(),
        "a": a.strip().upper(),
        "decisione": decisione.strip(),
        "percorsi": list(elenco),
    }
    libro.setdefault("trasferimenti", []).append(voce)
    libretto.parent.mkdir(parents=True, exist_ok=True)
    libretto.write_text(
        "# Il libro mastro dei trasferimenti di proprieta' (DEC-0093).\n"
        "# Si legge e si aggiunge: non si modifica e non si cancella. Ogni riga dice chi\n"
        "# ha ceduto cosa, a chi, e con quale decisione.\n"
        + yaml.safe_dump(libro, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return {"voce": voce, "avvisi": avvisi}


def cmd_elenca(root: Path = RADICE) -> int:
    libro = leggi_libro(root)
    voci = libro.get("trasferimenti") or []
    if not voci:
        print("  nessun trasferimento registrato")
        return 0
    for voce in voci:
        if not isinstance(voce, dict):
            continue
        print(f"  {voce.get('data', '?')}  {voce.get('da')} -> {voce.get('a')}  "
              f"({len(voce.get('percorsi') or [])} percorsi)  {voce.get('decisione', '')}")
        for percorso in voce.get("percorsi") or []:
            print(f"      {percorso}")
    return 0


def cmd_verifica(da: str, a: str, root: Path = RADICE) -> int:
    elenco, avvisi = verifica(da, a, root)
    print(f"  trasferibili: {len(elenco)} percorsi")
    for percorso in elenco:
        print(f"    {percorso}")
    for avviso in avvisi:
        print(f"  AVVISO: {avviso}")
    print("  OK   il trasferimento si puo' fare")
    return 0


def cmd_trasferisci(da: str, a: str, decisione: str, root: Path = RADICE) -> int:
    esito = trasferisci(da, a, decisione, root)
    voce = esito["voce"]
    print(f"  TRASFERITI {len(voce['percorsi'])} percorsi: {voce['da']} -> {voce['a']}")
    for percorso in voce["percorsi"]:
        print(f"    {percorso}")
    for avviso in esito["avvisi"]:
        print(f"  AVVISO: {avviso}")
    print(f"  registrato in contratti/_trasferimenti.yaml con {voce['decisione']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ad_transfer.py",
        description="Il libro mastro dei trasferimenti di proprieta' fra contract (DEC-0093).",
    )
    sotto = parser.add_subparsers(dest="comando", required=True)
    sotto.add_parser("elenca", help="mostra i trasferimenti registrati")
    p_ver = sotto.add_parser("verifica", help="dice se un trasferimento si puo' fare")
    p_ver.add_argument("--da", required=True)
    p_ver.add_argument("--a", required=True)
    p_fai = sotto.add_parser("trasferisci", help="esegue il trasferimento")
    p_fai.add_argument("--da", required=True)
    p_fai.add_argument("--a", required=True)
    p_fai.add_argument("--decisione", required=True, help="il DEC che autorizza il trasferimento")
    argomenti = parser.parse_args(argv)

    try:
        if argomenti.comando == "elenca":
            return cmd_elenca()
        if argomenti.comando == "verifica":
            return cmd_verifica(argomenti.da, argomenti.a)
        return cmd_trasferisci(argomenti.da, argomenti.a, argomenti.decisione)
    except Rifiuto as errore:
        print(f"ad_transfer: {errore}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
