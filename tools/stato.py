#!/usr/bin/env python3
"""La vista operativa: che cosa c'e' aperto, e come si sta comportando l'agente.

Perche' esiste, in una riga: `orchestrazione/stato.md` era scritto a mano, e le cose
scritte a mano invecchiano in silenzio. I numeri dentro — quante prove comportamentali
passano, quanti errori ha trovato il sistema — sono **gia' macchina**: qui si mettono
insieme, **generati dai registri**, con lo stesso meccanismo del Blueprint.

Uso:
    python3 tools/stato.py render    # scrive (tenendo la parte scritta a mano)
    python3 tools/stato.py check     # aggiornato / indietro / manomesso
    python3 tools/stato.py show      # stampa, senza scrivere

Esito: 0 nessun problema, 1 se qualcosa e' manomesso, 2 scrittura rifiutata
perche' nessun contract approvato copre il percorso.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import ad_docs
import ad_drift
import ad_scope
import blueprint
import comportamento
import errori

RADICE = Path(__file__).resolve().parents[1]
FILE = "orchestrazione/stato.md"

INIZIO = blueprint.INIZIO
FINE = blueprint.FINE

TESTA = """# STATO OPERATIVO

Vista umana dello stato. Non viene caricata automaticamente nel contesto del modello.

**La parte sopra il marcatore la scrive una persona. La parte sotto la genera
`tools/stato.py` leggendo i registri**, e il controllo la rigenera e confronta: dice
**aggiornato**, **indietro** (autentica ma di registri piu' vecchi) o **manomesso**.

"""


def comandi(base: Path | None = None) -> list[str]:
    """I comandi, non le librerie. **Una regola sola**, presa da `ad_coherence`.

    Prima contavo i `.py` che contengono la stringa `__name__ == "__main__"`. E'
    la ricerca ingenua da cui `ad_coherence` mette in guardia nel suo stesso
    commento: su `ad_coherence.py` trova la riga che *definisce* quella regex, e la
    conta come un comando. La vista diceva **23**, poi **15**; i comandi sono **14**.

    Due file che contano la stessa cosa devono usare la stessa funzione, altrimenti
    il numero e' due e la verita' e' una.
    """
    import ad_coherence  # noqa: PLC0415

    return sorted(ad_coherence.comandi_nel_progetto(base))


def genera(base: Path | None = None) -> str:
    """Il blocco generato. Deterministico: nessuna data, nessun ordine casuale."""
    radice = base or RADICE
    righe: list[str] = []

    # --- chi puo' scrivere, adesso -------------------------------------------
    attivi = ad_scope.load_write_scopes(radice)
    righe.append("## Permessi attivi")
    righe.append("")
    if not attivi:
        righe.append("**Nessuno.** Nessun lavoro e' aperto: ogni scrittura su un progetto e' bloccata.")
    else:
        righe.append("| Permesso | Su cosa | Chi | Scade |")
        righe.append("|---|---|---|---|")
        for scope in sorted(attivi, key=lambda s: s.task_id):
            dove = ad_scope._primo_progetto(scope.scopes) or ", ".join(scope.scopes)
            scadenza = _scadenza(scope, radice)
            righe.append(f"| `{scope.task_id}` | {dove} | `{scope.agent}` | {scadenza} |")

    # --- come si comporta l'agente -------------------------------------------
    righe.append("")
    righe.append("## L'agente si comporta come deve?")
    righe.append("")
    esiti = comportamento.esegui(radice)
    passate = sum(1 for v in esiti.values() if v["ok"])
    righe.append(f"| | |")
    righe.append("|---|---|")
    righe.append(f"| Prove comportamentali | **{passate}/{len(esiti)}** |")
    statistiche = errori.statistiche(radice)
    righe.append(f"| Errori registrati | {statistiche['totale']} |")
    righe.append(f"| Trovati da un **controllo** | {statistiche['dal_controllo']} |")
    righe.append(f"| Trovati per **fortuna** | {statistiche['per_fortuna']} |")
    righe.append("")
    righe.append(f"*{statistiche['giudizio']}*")
    if not all(v["ok"] for v in esiti.values()):
        righe.append("")
        righe.append("Prove che non passano:")
        righe.append("")
        for nome, voce in sorted(esiti.items()):
            if not voce["ok"]:
                righe.append(f"- **{nome}** — {voce['descrizione']}: {voce['dettaglio']}")

    # --- cosa aspetta una decisione ------------------------------------------
    righe.append("")
    righe.append("## Cosa aspetta una decisione")
    righe.append("")
    attese: list[str] = []

    for scope in attivi:
        scadenza = _scadenza_iso(scope, radice)
        if scadenza:
            giorni = _giorni_a(scadenza)
            if giorni is not None and giorni <= 30:
                attese.append(
                    f"- Il permesso `{scope.task_id}` **scade fra {giorni} giorni** "
                    f"({scadenza}). Un agente non puo' rinnovare il proprio permesso "
                    "(invariante 7)"
                )

    for voce in ad_drift.load(radice):
        if not voce.closed:
            attese.append(f"- Discrepanza aperta **{voce.id}** ({voce.severity or '—'}) — {voce.title}")

    aperti = [v["dati"] for v in errori.carica(radice) if v["dati"] and v["dati"].get("stato") != "chiuso"]
    for voce in aperti:
        attese.append(
            f"- Errore aperto **{voce.get('id', '?')}** — {str(voce.get('cosa_e_fallito', ''))[:120]}"
        )

    if not attese:
        righe.append("Niente in attesa.")
    else:
        righe.extend(sorted(attese))

    # --- gli ultimi lavori, di tutti i progetti -------------------------------
    # I documenti **restano nel progetto** (invariante 15): qui se ne mostra una riga,
    # per sapere che esistono. Chi vuole il resto apre il rapporto dove sta.
    lavori = ultimi_lavori(radice)
    righe.append("")
    righe.append("## Gli ultimi lavori chiusi")
    righe.append("")
    if not lavori:
        righe.append("Nessun passo chiuso in nessun progetto.")
    else:
        righe.append("| Giorno | Progetto | Tappa·Passo | Obiettivo |")
        righe.append("|---|---|---|---|")
        for voce in lavori:
            righe.append(
                f"| {voce['giorno']} | {voce['progetto']} | "
                f"{voce['tappa']}·{voce['passo']} | {voce['obiettivo']} |"
            )

    # --- i numeri ------------------------------------------------------------
    righe.append("")
    righe.append("## I numeri")
    righe.append("")
    righe.append("| Cosa | Quanti |")
    righe.append("|---|---|")
    righe.append(f"| Verbali (Decision Record) | {len(list((radice / 'DECISIONI').glob('DEC-*.md')))} |")
    righe.append(f"| Discrepanze registrate | {len(ad_drift.load(radice))} |")
    righe.append(f"| Errori registrati | {statistiche['totale']} |")
    righe.append(f"| Skill del cervello | {len(list((radice / '.brain' / 'skills').glob('ad-*')))} |")
    righe.append(f"| Comandi nella fascia deterministica | {len(comandi(radice))} |")
    righe.append(f"| Progetti | {len(ad_scope.protected_folders(radice))} |")

    righe.append("")
    righe.append(
        "Generato da `tools/stato.py`. **Non si modifica a mano**: il controllo rigenera e "
        "confronta, e un testo che non corrisponde al proprio sigillo e' **manomesso**."
    )
    return "\n".join(righe)


# ---------------------------------------------------------------------------
# Gli ultimi lavori, di tutti i progetti
#
# Perche' esiste: il 2026-10-13 il CEO ha chiesto se la documentazione del lavoro
# **si puo' condividere fra gli agenti**, cosi' che capiscano cosa e' stato fatto.
#
# La risposta e' un compromesso, e sta nell'invariante 15: **il lavoro resta nel
# progetto** — un agente su Modelbel non ha bisogno dei rapporti di Marketing
# Factory, e la root non deve diventare il posto dove tutto si mescola. Ma
# **sapere che quei lavori esistono** serve a chiunque.
#
# Quindi **non si sposta niente**: si legge dove sta, e se ne mostra **una riga per
# passo**. Chi vuole il resto apre il rapporto nel progetto.
# ---------------------------------------------------------------------------

#: Quanti passi mostrare. Pochi: e' un orientamento, non un archivio.
ULTIMI_QUANTI = 8


def ultimi_lavori(base: Path | None = None, quanti: int = ULTIMI_QUANTI) -> list[dict]:
    """Gli ultimi passi **chiusi** di tutti i progetti, dal piu' recente.

    Legge soltanto: nessun documento si copia, si sposta o si riscrive.
    """
    import datetime
    import re

    import ad_milestone

    # I progetti, non il motore: sede.yaml puo' dichiararli altrove.
    radice = base or ad_docs.PROGETTI_ROOT
    trovati: list[dict] = []

    for progetto in sorted(radice.iterdir()):
        if not progetto.is_dir() or not ad_scope.PROTECTED_DIR.match(progetto.name):
            continue
        try:
            tappe = ad_milestone.scan(progetto)
        except Exception:  # noqa: BLE001
            continue
        for tappa in tappe:
            for passo in tappa.sprints:
                rapporto = passo.path / ad_milestone.SPRINT_REPORT
                if not rapporto.is_file():
                    continue
                try:
                    testo = rapporto.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                if "stato: chiusa" not in testo and "stato: chiuso" not in testo:
                    continue
                quando = re.search(
                    r"^(?:chius[oa]|data):\s*[\"\']?(\d{4}-\d{2}-\d{2})", testo, re.M
                )
                giorno = (
                    quando.group(1)
                    if quando
                    else datetime.date.fromtimestamp(rapporto.stat().st_mtime).isoformat()
                )
                # L'obiettivo: dal prompt del passo, che e' dove sta scritto.
                obiettivo = ""
                prompt = passo.path / ad_milestone.SPRINT_PROMPT
                if prompt.is_file():
                    p_testo = prompt.read_text(encoding="utf-8", errors="replace")
                    # Il prompt scrive `obiettivo:` — in italiano. `objective:` e' il
                    # nome inglese nel modello del contract: si accettano entrambi,
                    # perche' un controllo che pretende la parola esatta sbaglia su
                    # chi ha scritto bene ma in un altro modo.
                    m = re.search(
                        r"^(?:obiettivo|objective):\s*>?-?\s*(.+)$", p_testo, re.M
                    )
                    if m:
                        obiettivo = " ".join(m.group(1).split()).strip("\"'")
                if not obiettivo:
                    prima = testo.splitlines()[0] if testo else ""
                    obiettivo = prima.lstrip("# ").strip()[:90]
                trovati.append(
                    {
                        "giorno": giorno,
                        "progetto": progetto.name,
                        "tappa": tappa.number,
                        "passo": passo.number,
                        "obiettivo": obiettivo[:96],
                    }
                )

    trovati.sort(key=lambda v: (v["giorno"], v["progetto"], v["tappa"], v["passo"]), reverse=True)
    return trovati[:quanti]



def _scadenza(scope: ad_scope.WriteScope, base: Path) -> str:
    iso = _scadenza_iso(scope, base)
    if not iso:
        return "—"
    giorni = _giorni_a(iso)
    return f"{iso[:10]}" + (f" ({giorni} gg)" if giorni is not None else "")


def _scadenza_iso(scope: ad_scope.WriteScope, base: Path) -> str | None:
    """La data di scadenza dichiarata nel contratto, se c'e'."""
    import yaml

    try:
        dati = yaml.safe_load(scope.source.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    valore = dati.get("expires")
    return str(valore) if valore else None


def _giorni_a(iso: str) -> int | None:
    import datetime

    try:
        quando = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    adesso = datetime.datetime.now(quando.tzinfo)
    return max(0, (quando - adesso).days)


def genera_con_sigillo(base: Path | None = None, impronta: str | None = None) -> str:
    """Il blocco generato con il sigillo in cima. Vedi `blueprint.genera`."""
    radice = base or RADICE
    corpo = genera(radice)
    fp = impronta if impronta is not None else blueprint._impronta(corpo)
    return (
        f"> **Vista generata dai registri.** impronta: `{fp}`\n"
        "> Il controllo la rigenera e confronta. **Autentica non vuol dire giusta**: il sigillo "
        "protegge dall'alterazione, non dall'errore.\n\n" + corpo
    )


def percorso(base: Path | None = None) -> Path:
    return (base or RADICE) / FILE


def scrivi(base: Path | None = None) -> Path:
    """Genera e scrive, conservando la parte scritta a mano.

    Raises:
        PermissionError: Se nessun contract approvato copre il percorso. La vista
            vive fuori dai progetti, quindi di norma non serve un permesso — ma il
            percorso lo sceglie `--root`: con `--root` dentro un progetto questa
            sarebbe una scrittura non coperta (ERR-0026).
    """
    radice = base or RADICE
    destinazione = percorso(radice)
    ad_scope.guard(destinazione)
    destinazione.parent.mkdir(parents=True, exist_ok=True)

    testa = TESTA
    if destinazione.is_file():
        attuale = destinazione.read_text(encoding="utf-8")
        taglio = attuale.find(INIZIO)
        if taglio > 0:
            testa = attuale[:taglio].rstrip("\n") + "\n\n"

    destinazione.write_text(
        testa + INIZIO + "\n" + genera_con_sigillo(radice).strip("\n") + "\n" + FINE + "\n",
        encoding="utf-8",
    )
    return destinazione


def controlla(base: Path | None = None) -> tuple[str, str]:
    """(aggiornato|indietro|manomesso|senza-impronta|senza-marcatori|assente, dettaglio)."""
    radice = base or RADICE
    percorso_file = percorso(radice)
    if not percorso_file.is_file():
        return "assente", f"{FILE}: non esiste"
    try:
        testo = percorso_file.read_text(encoding="utf-8")
    except OSError as errore:
        return "assente", f"{FILE}: non si legge ({errore})"

    blocco = blueprint.blocco_generato(testo)
    if blocco is None:
        return "senza-marcatori", f"{FILE}: mancano i marcatori {INIZIO} / {FINE}"
    blocco = blocco.strip("\n")

    dichiarata, corpo = blueprint.separa_fotografia(blocco)
    if dichiarata is None:
        return "senza-impronta", (
            f"{FILE}: il blocco non comincia con il sigillo — o e' di una versione vecchia, "
            "o qualcuno ci ha scritto sopra"
        )
    if blueprint._impronta(corpo) != dichiarata:
        return "manomesso", f"{FILE}: il contenuto non corrisponde alla sua impronta"
    if dichiarata == blueprint._impronta(genera(radice)):
        return "aggiornato", f"{FILE}: aggiornato"
    return "indietro", f"{FILE}: vista autentica di registri piu' vecchi (impronta {dichiarata})"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Vista operativa")
    parser.add_argument("comando", choices=("render", "check", "show"))
    parser.add_argument("--root", default=str(RADICE))
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    base = Path(args.root).resolve()

    if args.comando == "render":
        try:
            scritto = scrivi(base)
        except PermissionError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(f"scritto {scritto.relative_to(base)}")
        return 0
    if args.comando == "show":
        print(genera_con_sigillo(base))
        return 0

    stato, dettaglio = controlla(base)
    if args.json:
        print(json.dumps({"stato": stato, "dettaglio": dettaglio}, ensure_ascii=False))
    else:
        print(f"  {stato.upper():14} {dettaglio}")
    return 1 if stato in ("manomesso", "senza-impronta", "senza-marcatori") else 0


if __name__ == "__main__":
    raise SystemExit(main())
