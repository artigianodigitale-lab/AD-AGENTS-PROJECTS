"""Accesso in sola lettura ai documenti normativi della root di AD Projects.

Nessun modulo di ``tools/`` scrive nei documenti: la catena documentale e' la
sorgente di verita' e questo pacchetto la legge soltanto.
"""

from __future__ import annotations

from pathlib import Path

#: Root di AD Projects: il genitore di ``tools/``.
DOCS_ROOT: Path = Path(__file__).resolve().parents[1]

GOVERNANCE = "GOVERNANCE-AZIENDALE.md"
TECH_CARDS = "AGENT-CARDS-V2.md"
BUSINESS_CARDS = "AGENT-CARDS-BUSINESS.md"
TASK_CONTRACTS = "TASK-CONTRACTS.md"
RUNTIME = "RUNTIME.md"
QUALITY_GATES = "QUALITY-GATES.md"
SPECIALIZATION = "SPECIALIZATION.md"
COMMUNICATION = "COMMUNICATION.md"
AGENTI = "AGENTI-V2.md"


class DocumentMissing(Exception):
    """Raised when a normative document is not present in the root."""


def read(name: str) -> str:
    """Return the text of a normative document.

    Args:
        name: File name relative to the root of AD Projects.

    Returns:
        The document text.

    Raises:
        DocumentMissing: If the file does not exist.
    """
    path = DOCS_ROOT / name
    if not path.exists():
        raise DocumentMissing(f"documento normativo assente: {name} ({path})")
    return path.read_text(encoding="utf-8")


def read_optional(name: str) -> str:
    """Return the text of a document, or an empty string when it is absent."""
    path = DOCS_ROOT / name
    return path.read_text(encoding="utf-8") if path.exists() else ""
# ---------------------------------------------------------------------------
# La prenotazione di un id
#
# Da dove viene: il 2026-10-11 due sessioni hanno scritto negli stessi registri
# nello stesso momento, e hanno scelto **lo stesso numero** due volte di fila
# (ERR-0018 e ERR-0019). Il controllo dei duplicati li ha presi — ma **dopo**.
#
# La causa non e' la distrazione: e' **come si sceglie un id**. Leggere il massimo,
# decidere il prossimo, scrivere. Fra il leggere e lo scrivere, un'altra sessione
# fa lo stesso. E' una corsa critica, e succede ogni volta che due sessioni
# lavorano insieme.
#
# La soluzione: **l'id si prenota creando il file**, non leggendo il massimo.
# `O_CREAT | O_EXCL` e' atomico — il sistema operativo garantisce che uno solo
# vince, fra processi e fra sessioni, senza nessun protocollo di coordinamento.
# Il filesystem e' il lucchetto.
#
# Una regola ne discende: **gli id non si scelgono, si chiedono.**
# ---------------------------------------------------------------------------


class IdNonPrenotabile(RuntimeError):
    """Nessun id libero nel intervallo tentato."""


def prenota_id(
    cartella: Path,
    prefisso: str,
    *,
    cifre: int = 4,
    slug: str = "nuovo",
    estensione: str = ".md",
    tentativi: int = 500,
) -> tuple[str, Path]:
    """Prenota il primo id libero **creando il file**, e restituisce (id, percorso).

    Atomico: se due sessioni provano lo stesso numero nello stesso istante, una
    vince e l'altra passa al successivo. Il file nasce vuoto — il chiamante lo
    riempie subito dopo — perche' **la prenotazione e' il file**, non un numero
    tenuto altrove.

    La cartella la sceglie il chiamante, quindi la guardia sta **qui**: e' il punto
    in cui il percorso diventa una scrittura. `errori/` e `DECISIONI/` stanno fuori
    dalle classi protette e non serve nessun permesso; ma con `--root` dentro un
    progetto questa sarebbe una scrittura non coperta (ERR-0026).

    Raises:
        PermissionError: Se nessun contract approvato copre il percorso.
    """
    import os

    # Import locale: `ad_scope` importa questo modulo, e in cima sarebbe un ciclo.
    import ad_scope

    ad_scope.guard(cartella)
    cartella.mkdir(parents=True, exist_ok=True)

    # Si parte dal massimo **come suggerimento**, non come risposta: la risposta
    # arriva dal filesystem, che dira' se quel numero e' ancora libero.
    massimo = 0
    for percorso in cartella.glob(f"{prefisso}-*"):
        pezzi = percorso.stem.split("-")
        if len(pezzi) >= 2 and pezzi[1].isdigit():
            massimo = max(massimo, int(pezzi[1]))

    for numero in range(massimo + 1, massimo + 1 + tentativi):
        identificatore = f"{prefisso}-{numero:0{cifre}d}"
        percorso = cartella / f"{identificatore}-{slug}{estensione}"
        try:
            descrittore = os.open(percorso, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            continue  # qualcuno l'ha preso: si prova il prossimo
        except OSError as errore:
            raise IdNonPrenotabile(f"non si prenota {percorso}: {errore}") from errore
        os.close(descrittore)
        return identificatore, percorso

    raise IdNonPrenotabile(
        f"nessun id libero in {cartella} dopo {tentativi} tentativi dal {massimo}"
    )


# ---------------------------------------------------------------------------
# Chi e' il CEO, e come si chiama questa macchina
#
# Perche' esiste: le regole parlano al **CEO**, che e' un ruolo. Il nome e' un dato,
# e sta in un posto solo — `sede.yaml` nella radice. Prima «il CEO» era scritto 63
# volte in 12 file e 18 nei comandi: cambiare utente significava riscrivere la
# macchina, e un motore che si puo' usare in un posto solo non e' un motore.
#
# Se `sede.yaml` non c'e', **l'engine non e' avviato**: non e' un errore, e' il primo
# avvio che non e' ancora avvenuto. Vedi `.brain/skills/ad-avvio`.
# ---------------------------------------------------------------------------

SEDE = DOCS_ROOT / "sede.yaml"


def sede() -> dict:
    """Il contenuto di `sede.yaml`, o un dizionario vuoto se l'engine non e' avviato."""
    try:
        import yaml

        letto = yaml.safe_load(SEDE.read_text(encoding="utf-8"))
        return letto if isinstance(letto, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def avviata() -> bool:
    """L'engine e' stato avviato? Cioe': qualcuno ha detto chi e' il CEO."""
    return bool(sede().get("ceo", {}).get("nome"))


def ceo() -> str:
    """Il nome del CEO. **Un ruolo prima di un nome**: se non c'e', si dice il ruolo."""
    return str(sede().get("ceo", {}).get("nome") or "il CEO")


def progetti_root():
    """**Dove stanno i progetti.** Il motore non li cerca piu' solo accanto a se'.

    Perche' esiste: il 2026-10-13, preparando `AD-AGENTS-PROJECTS` come motore finito,
    ho misurato che sette comandi cercavano i progetti nella **propria** cartella. Cosi'
    spostare il motore significava perdere i progetti — e un motore che si puo' usare in
    un posto solo non e' un motore.

    L'ordine e' questo, e non si indovina:

    1. `macchina.progetti` in `sede.yaml` — **dichiarato**, ed e' la fonte
    2. la cartella del motore — il comportamento di sempre, quando nessuno ha dichiarato

    Il campo vuoto **non e' un errore**: significa «accanto a me», che e' come funziona
    da sempre. Si dichiara solo quando i progetti stanno altrove.
    """
    dichiarato = str(sede().get("macchina", {}).get("progetti") or "").strip()
    if dichiarato:
        return Path(dichiarato).expanduser().resolve()
    return DOCS_ROOT


#: La cartella dei progetti, risolta una volta. Chi la usa la importa da qui, cosi'
#: non ci sono due idee di dove siano i progetti.
PROGETTI_ROOT = progetti_root()
