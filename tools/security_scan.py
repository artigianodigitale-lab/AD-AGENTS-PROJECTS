#!/usr/bin/env python3
"""Scanner di sicurezza: segreti, dipendenze, SBOM.

    python3 tools/security_scan.py <percorso> [--json] [--sbom]

Tre scanner indipendenti, ognuno con il suo ambito:

- **segreti** — `gitleaks`: cerca credenziali in chiaro. I risultati sono
  separati fra file **tracciabili da git** e file ignorati (artefatti di build),
  perche' la domanda che conta e' cosa puo' finire in un commit.
- **dipendenze** — `osv-scanner`: incrocia i lockfile con il database OSV.
  Complementare a `npm audit`, che usa il registro npm e puo' non vedere
  dipendenze annidate.
- **SBOM** — `syft`: inventario dei pacchetti. Solo con `--sbom`, perche' e' la
  parte lenta.

Perche' tre e non uno: verificato sul campo che `npm audit` e `osv-scanner`
**danno risposte diverse** sullo stesso lockfile. Un solo scanner e' un'opinione.

Esito:
    0  nessun segreto tracciabile, nessuna vulnerabilita' con fix disponibile
    1  almeno un segreto in un file tracciabile, o una vulnerabilita' con fix
    2  uno scanner non e' installato o il percorso non esiste
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import ad_scope

SEGRETI = "gitleaks"
ISTRUZIONI = "istruzioni-mascherate"
DIPENDENZE = "osv-scanner"
SBOM = "syft"

def _installed(nome: str) -> str | None:
    """Return the scanner path if installed, else None."""
    return shutil.which(nome)


def _run(cmd: list[str], cwd: Path, timeout: int = 600) -> tuple[int, str]:
    """Run a scanner, returning its exit code and stdout."""
    try:
        res = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
        return res.returncode, res.stdout
    except (subprocess.TimeoutExpired, OSError) as exc:
        return 1, f"errore di esecuzione: {exc}"


def tracked_files(radice: Path) -> set[str] | None:
    """Return the files that could end up in a commit, or None outside a repository.

    Non basta `git ls-files`: elenca i **tracciati**, e il caso pericoloso e'
    esattamente quello opposto. Un file non tracciato e **non ignorato** viene
    preso da un `git add -A` senza che nessuno lo abbia deciso — quindi
    `--cached --others --exclude-standard`, che e' "cio' che puo' essere
    committato". La prima versione di questo strumento usava solo i tracciati e
    classificava `docs/chat-history.md` fra gli artefatti innocui: nascondeva
    proprio il ritrovamento che contava.
    """
    esito, stdout = _run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"], radice, timeout=60
    )
    if esito != 0:
        return None
    return {riga.strip() for riga in stdout.splitlines() if riga.strip()}


def _versioni_fix(vulnerabilita: dict) -> list[str]:
    """Extract the fixed versions from an OSV vulnerability entry.

    OSV non mette un campo `fixed_version`: la correzione sta negli eventi dei
    range, in `affected[].ranges[].events[].fixed`.
    """
    trovate: list[str] = []
    for affected in vulnerabilita.get("affected") or []:
        for rng in affected.get("ranges") or []:
            for evento in rng.get("events") or []:
                if "fixed" in evento:
                    trovate.append(str(evento["fixed"]))
    return sorted(set(trovate))


def scan_segreti(radice: Path, lavoro: Path) -> dict:
    """Scan for secrets, splitting tracked and untracked findings."""
    eseguibile = _installed(SEGRETI)
    if eseguibile is None:
        return {"scanner": SEGRETI, "errore": "non installato"}
    report = lavoro / "gitleaks.json"
    esito, stdout = _run(
        [eseguibile, "dir", ".", "--report-format", "json", "--report-path", str(report),
         "--exit-code", "0"],
        radice,
    )
    if not report.is_file():
        return {"scanner": SEGRETI, "errore": stdout.strip()[:200] or "nessun report"}
    try:
        voci = json.loads(report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        voci = []

    tracciati = tracked_files(radice)
    in_commit, ignorati, finte, non_committabili = [], [], [], []
    for voce in voci:
        percorso = str(voce.get("File", ""))
        riga = {"regola": voce.get("RuleID", ""), "file": percorso,
                "riga": voce.get("StartLine"),
                # gitleaks dice gia' QUALE valore ha trovato: non serve che lo
                # estragga io dalla riga. La mia estrazione sbagliava sulle righe
                # CSV, e sbagliare l'ingresso vuol dire sbagliare il giudizio.
                "valore": voce.get("Secret", "")}
        if tracciati is None:
            # FUORI DA UN REPOSITORY. Qui la domanda «puo' finire in un commit?» non
            # ha risposta, perche' **non c'e' nessun commit**. Prima tutto finiva in
            # `tracciabili`, e 4 progetti su 17 gonfiavano il conteggio: e' cosi' che
            # il 2026-10-10 ho detto al CEO che un token Cloudflare rischiava di
            # finire nella storia di un repository che non esiste.
            non_committabili.append(riga)
        elif percorso in tracciati:
            perche = forma_da_fixture(radice, riga)
            if perche:
                riga["perche_finta"] = perche
                finte.append(riga)
            else:
                in_commit.append(riga)
        else:
            ignorati.append(riga)
    return {
        "scanner": SEGRETI,
        "tracciabili": in_commit,
        "forme_da_fixture": finte,
        "e_repository": tracciati is not None,
        "fuori_da_un_repository": non_committabili,
        "in_artefatti_ignorati": len(ignorati),
    }


# ---------------------------------------------------------------------------
# Plausibile o forma da fixture?
#
# Perche' esiste: il 2026-10-10 `security_scan.py` usciva **1 su 15 progetti su
# 17**, tutti e 15 per la sola regola `generic-api-key`, su campioni che erano
# **fixture**:
#
#     openrouter_api_key="sk-or-test-key-12345"     <- si chiama test-key
#     dedupeKey: "sbx21-warm-neutrals"              <- un nome di campo
#
# Un allarme che suona su 15 progetti su 17 **spegne il controllo**: nessuno lo
# legge piu'. E in mezzo al rumore restavano invisibili tre vulnerabilita' vere.
#
# La causa: la regola `generic-api-key` cerca un valore accanto a un nome che
# contiene «key» — e `dedupeKey` e' un nome di campo come un altro.
#
# I finti NON si nascondono: restano elencati. Ma **non spengono la luce**.
# ---------------------------------------------------------------------------

#: Parole che un segreto vero non contiene.
PAROLE_FINTA = (
    "test", "example", "esempio", "dummy", "fake", "finto", "sample", "placeholder",
    "changeme", "your-", "your_", "xxx", "lorem", "foobar", "notreal", "redacted",
)

#: La forma di un UUID: non e' un segreto, qualunque cosa dica la regola.
UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)

#: Percorsi che ospitano quasi sempre valori finti.
PERCORSI_FINTI = ("test", "spec", "fixture", "mock", "example", "sample", "demo", "__tests__")


def _valore(radice: Path, percorso: str, numero: int | None) -> str:
    """La riga incriminata, che e' quello che decide se e' un segreto o una somiglianza."""
    if not numero:
        return ""
    try:
        righe = (radice / percorso).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return righe[numero - 1].strip() if 0 < numero <= len(righe) else ""


def forma_da_fixture(radice: Path, voce: dict) -> str | None:
    """Perche' questa voce **non** e' un segreto. None = plausibile, e va guardata.

    Una spiegazione, non un punteggio: chi legge deve poter dire se il filtro ha
    sbagliato. Un filtro che nasconde senza dire perche' e' peggio del rumore.
    """
    riga = _valore(radice, voce["file"], voce.get("riga"))
    valore = voce.get("valore") or ""
    if not valore:
        # ripiego: il valore assegnato nella riga
        valore = riga.split(":", 1)[-1].split("=", 1)[-1].strip().strip("\"'`,;)")
    if not valore and not riga:
        return None

    basso = (valore + " " + riga).lower()
    for parola in PAROLE_FINTA:
        if parola in basso:
            return f"il valore contiene «{parola}»"

    # Un UUID non e' un segreto, e nemmeno un identificatore con la forma di un UUID.
    # Presi dall'enciclopedia di `8. APP-WEB-GEORN`: 2302 righe di un CSV esportato,
    # che la regola generica legge come chiavi perche' sono lunghe e ad alta entropia.
    if UUID_RE.fullmatch(valore):
        return "e' un UUID, non una chiave"

    # Un segreto vero e' un blocco unico e casuale. Una frase leggibile no.
    pezzi = [p for p in re.split(r"[-_.\s]+", valore) if p]
    parole = [p for p in pezzi if p.isalpha() and len(p) >= 3]
    blocco_lungo = any(
        len(p) >= 20 and sum(c.isdigit() for c in p) >= 3 for p in pezzi
    )
    if len(parole) >= 2 and not blocco_lungo:
        return f"il valore e' fatto di parole ({', '.join(parole[:3])}), non e' casuale"

    if any(p in basso for p in PERCORSI_FINTI) and not blocco_lungo:
        return "e' in un file di prova, e il valore non e' casuale"

    return None


def scan_dipendenze(radice: Path) -> dict:
    """Scan the dependencies for known vulnerabilities.

    **Ricorsivo e multiecosistema, di proposito.** La prima versione cercava
    `package-lock.json` nella sola radice del progetto: su `1. AD-AIOS`, che tiene
    le dipendenze in `dashboard/package-lock.json`, `requirements.txt` e
    `pyproject.toml`, rispondeva «assente» e usciva **con successo**. Un controllo
    di sicurezza che non guarda e dichiara di aver guardato e' peggio di nessun
    controllo: da' fiducia falsa. Trovato da un agente indipendente il 2026-10-08.

    Ora e' `osv-scanner` a sapere cosa cercare — riconosce da solo i formati — e il
    risultato dichiara **quali file ha letto**, cosi' «nessuna vulnerabilita'» non
    si confonde con «nessun file trovato».
    """
    eseguibile = _installed(DIPENDENZE)
    if eseguibile is None:
        return {"scanner": DIPENDENZE, "errore": "non installato"}
    # `--no-ignore`: osv-scanner rispetta `.gitignore` di default, e dal 2026-10-11
    # la **supercartella e' un repository** che esclude i 17 progetti. Senza questo
    # flag risale al repository genitore, trova `/3. AD-Marketing-Factory/` fra le
    # esclusioni, e **pota tutto**: rispondeva «nessun file di dipendenze» su un
    # progetto con 910 pacchetti. Un `git init` aveva spento un controllo di
    # sicurezza, in silenzio.
    #
    # Il costo dichiarato: senza `.gitignore` vengono letti anche gli artefatti
    # derivati (`node_modules/`), quindi il conteggio puo' includere copie vendute.
    esito, stdout = _run(
        [eseguibile, "scan", "source", "-r", ".", "--format", "json", "--no-ignore"],
        radice,
    )
    vulnerabili = []
    letti: set[str] = set()
    # Quando non c'e' nulla da scansionare, osv-scanner non produce JSON: esce 0
    # e scrive il motivo su stderr, che qui non leggiamo. Un output vuoto e' quindi
    # "niente da controllare", e va detto — non interpretato come "tutto a posto".
    if not stdout.strip() or "No package sources found" in stdout:
        return {
            "scanner": DIPENDENZE,
            "vulnerabilita": [],
            "con_fix_disponibile": [],
            "file_letti": [],
            "errore": (
                "nessun file di dipendenze riconosciuto: il progetto potrebbe non averne, "
                "oppure usa un formato che lo scanner non legge. Da verificare a mano."
            ),
        }
    try:
        dati = json.loads(stdout)
    except json.JSONDecodeError:
        return {
            "scanner": DIPENDENZE,
            "errore": f"output non leggibile: {stdout.strip()[:160] or '(vuoto)'}",
        }
    for risultato in dati.get("results", []):
        sorgente = risultato.get("source") or {}
        percorso = str(sorgente.get("path", "")).strip()
        if percorso:
            letti.add(percorso)
        for pacchetto in risultato.get("packages", []):
            for v in pacchetto.get("vulnerabilities", []):
                vulnerabili.append(
                    {
                        "pacchetto": pacchetto.get("package", {}).get("name", ""),
                        "versione": pacchetto.get("package", {}).get("version", ""),
                        "id": v.get("id", ""),
                        "fix": ", ".join(_versioni_fix(v)) or "--",
                        "file": percorso,
                    }
                )
    con_fix = [v for v in vulnerabili if v["fix"] != "--"]
    esito_finale: dict = {
        "scanner": DIPENDENZE,
        "vulnerabilita": vulnerabili,
        "con_fix_disponibile": con_fix,
        "file_letti": sorted(letti),
    }
    if not letti:
        esito_finale["errore"] = (
            "nessun file di dipendenze riconosciuto: il progetto potrebbe non averne, "
            "oppure usa un formato che lo scanner non legge. Da verificare a mano."
        )
    return esito_finale


def scan_sbom(radice: Path, lavoro: Path) -> dict:
    """Build a software bill of materials."""
    eseguibile = _installed(SBOM)
    if eseguibile is None:
        return {"scanner": SBOM, "errore": "non installato"}
    destinazione = lavoro / "sbom.json"
    esito, stdout = _run(
        [eseguibile, "dir:.", "-o", f"json={destinazione}", "--quiet",
         "--exclude", "./node_modules/**", "--exclude", "./.next/**"],
        radice,
    )
    if not destinazione.is_file():
        return {"scanner": SBOM, "errore": stdout.strip()[:200] or "nessun SBOM"}
    try:
        dati = json.loads(destinazione.read_text(encoding="utf-8"))
        return {"scanner": SBOM, "pacchetti": len(dati.get("artifacts", [])),
                "report": str(destinazione)}
    except (OSError, json.JSONDecodeError):
        return {"scanner": SBOM, "errore": "SBOM non leggibile"}


# ---------------------------------------------------------------------------
# Istruzioni mascherate da materiale
#
# Perche' esiste: il 2026-10-11 ho aperto `studio/graphify-8/` per studiarlo, e
# dentro c'era un `AGENTS.md`. Quel file **non e' un documento**: e' un insieme di
# istruzioni che l'agente legge come proprie — mi e' arrivato nel contesto come
# «Additional instructions from: studio/graphify-8/AGENTS.md», non come dato.
#
# Il file non era malevolo. E' il normale `AGENTS.md` di un repository. Il problema
# e' **strutturale**: `studio/` esiste per ricevere materiale di terzi, e qualunque
# cartella puo' portare istruzioni dentro. Non serve la malafede: serve che nessuno
# se ne accorga.
#
# La regola: **il materiale di studio e' DATO, non istruzioni.** Chi lo legge lo
# legge, non lo esegue.
# ---------------------------------------------------------------------------

#: Nomi che un agente carica come **istruzioni**, non come documenti.
NOMI_ISTRUZIONI = (
    "agents.md",
    "claude.md",
    "gemini.md",
    "copilot-instructions.md",
    ".cursorrules",
    "systemprompt.md",
)

#: Percorsi che portano istruzioni per posizione, non per nome.
PERCORSI_ISTRUZIONI = (
    ".cursor/rules",
    ".cursor/hooks",
    ".github/copilot",
    ".claude/",
    ".aider.conf",
)


def scan_istruzioni(radice: Path) -> dict:
    """Trova i file che un agente legge come istruzioni, dentro materiale di studio.

    Restituisce anche i **gia' disattivati** (rinominati), cosi' si vede cosa e'
    stato neutralizzato e non solo cosa resta.
    """
    attivi, disattivati = [], []
    for percorso in radice.rglob("*"):
        if not percorso.is_file() or ".git/" in str(percorso):
            continue
        nome = percorso.name.lower()
        rel = str(percorso.relative_to(radice))
        if nome.endswith(".disattivato"):
            if nome.replace(".disattivato", "") in NOMI_ISTRUZIONI:
                disattivati.append(rel)
            continue
        if nome in NOMI_ISTRUZIONI:
            attivi.append({"file": rel, "perche": f"si chiama `{percorso.name}`"})
            continue
        for segno in PERCORSI_ISTRUZIONI:
            if segno in rel.replace("\\", "/"):
                attivi.append({"file": rel, "perche": f"sta in `{segno}`"})
                break
    return {"scanner": ISTRUZIONI, "attivi": attivi, "disattivati": disattivati}


def disattiva(radice: Path, voci: list[dict]) -> list[str]:
    """Rinomina le istruzioni in modo che l'agente non le carichi piu'.

    **Rinomina, non cancella.** Il contenuto resta leggibile: e' materiale di
    studio, e studiarlo e' il motivo per cui e' li'. Si toglie solo l'**effetto**,
    non l'informazione.

    `radice` la sceglie chi chiama — e' un argomento della riga di comando — quindi
    la guardia sta qui: `security_scan.py "<progetto>"` era una rinomina dentro un
    progetto senza nessun contract (ERR-0026).

    Raises:
        PermissionError: Se nessun contract approvato copre il percorso.
    """
    fatti = []
    for voce in voci:
        percorso = radice / voce["file"]
        # Prima di toccare qualsiasi cosa, e prima ancora di sapere se il file
        # esiste: il permesso riguarda il PERCORSO, non il file che oggi c'e'.
        ad_scope.guard(percorso)
        if not percorso.is_file():
            continue
        destinazione = percorso.with_name(percorso.name + ".disattivato")
        percorso.rename(destinazione)
        fatti.append(f"{voce['file']} -> {destinazione.name}")
    return fatti


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description="Scanner di sicurezza")
    parser.add_argument("percorso")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--sbom", action="store_true", help="esegui anche syft")
    args = parser.parse_args(argv)

    radice = Path(args.percorso).resolve()
    if not radice.is_dir():
        print(f"percorso inesistente: {radice}", file=sys.stderr)
        return 2

    # Un errore del programma NON e' un rilievo di sicurezza. Prima non si
    # distinguevano: entrambi uscivano 1 con un messaggio diverso, e misurando
    # «quanti progetti escono 1» ho contato gli uni per gli altri. Il 2 e' «non
    # ho potuto guardare», ed e' una cosa diversa da «ho guardato e ho trovato».
    try:
        return _esegui(args, radice)
    except Exception as errore:  # noqa: BLE001
        print(f"\nesito: SCANSIONE NON RIUSCITA — {type(errore).__name__}: {errore}")
        return 2


def _esegui(args, radice: Path) -> int:

    lavoro = Path("/tmp/security-scan")
    lavoro.mkdir(parents=True, exist_ok=True)

    esiti = [scan_segreti(radice, lavoro), scan_dipendenze(radice), scan_istruzioni(radice)]
    if args.sbom:
        esiti.append(scan_sbom(radice, lavoro))

    mancanti = [e["scanner"] for e in esiti if e.get("errore") == "non installato"]
    if args.json:
        # `--json` stampa SOLO il JSON. Prima stampava anche la riga finale, e chi
        # legge l'output con un parser falliva: una macchina non deve indovinare
        # dove finisce il dato. L'uscita 0/1/2 resta, ed e' quella che si legge.
        print(json.dumps(esiti, indent=2, ensure_ascii=False))
        if mancanti:
            return 2
        return 1 if (
            any(e.get("tracciabili") for e in esiti)
            or any(e.get("con_fix_disponibile") for e in esiti)
        ) else 0
    else:
        for esito in esiti:
            print(f"\n== {esito['scanner']}")
            if "errore" in esito:
                print(f"   {esito['errore']}")
                continue
            if esito["scanner"] == SEGRETI:
                if not esito.get("e_repository", True):
                    fuori = len(esito.get("fuori_da_un_repository") or [])
                    print("   NON e' un repository Git: nessun commit possibile, quindi")
                    print(f"   nessun rischio di finire nella storia. Segnalazioni: {fuori} (non contate)")
                print(f"   segnali plausibili: {len(esito['tracciabili'])}")
                for voce in esito["tracciabili"][:10]:
                    print(f"     {voce['regola']:18} {voce['file']}:{voce['riga']}")
                finte = esito.get("forme_da_fixture") or []
                if finte:
                    # NON nascoste: elencate con la ragione. Un filtro che nasconde
                    # senza spiegare e' peggio del rumore che toglie.
                    print(f"   forme da fixture (escluse dal verdetto): {len(finte)}")
                    for voce in finte[:8]:
                        print(f"     {voce['regola']:18} {voce['file']}:{voce['riga']}")
                        print(f"       perche': {voce['perche_finta']}")
                print(f"   in artefatti ignorati: {esito['in_artefatti_ignorati']}")
            elif esito["scanner"] == DIPENDENZE:
                letti = esito.get("file_letti") or []
                print(f"   file di dipendenze letti: {len(letti)}")
                for percorso in letti[:8]:
                    print(f"     {percorso}")
                print(f"   vulnerabilita': {len(esito['vulnerabilita'])}"
                      f"  (con fix disponibile: {len(esito['con_fix_disponibile'])})")
                for voce in esito["vulnerabilita"][:10]:
                    print(f"     {voce['pacchetto']:18} {voce['versione']:10} "
                          f"fix: {voce['fix']:10} {voce['file']}")
            elif esito["scanner"] == ISTRUZIONI:
                attivi = esito.get("attivi") or []
                # **Informativo, non allarme.** Un `AGENTS.md` in un progetto puo'
                # essere legittimo. In materiale di studio e' un'altra cosa — e li'
                # lo impone la suite, non il codice di uscita.
                print(f"   file che un agente legge come ISTRUZIONI: {len(attivi)}")
                for voce in attivi[:8]:
                    print(f"     {voce['file']}  ({voce['perche']})")
                if attivi:
                    print("     -> sono DATO, non ordini: non si eseguono")
                for voce in (esito.get("disattivati") or [])[:5]:
                    print(f"     disattivato: {voce}")
            else:
                print(f"   pacchetti nell'SBOM: {esito['pacchetti']}  -> {esito['report']}")

    if mancanti:
        print(f"\nscanner non installati: {mancanti}", file=sys.stderr)
        return 2
    # L'uscita 1 vale solo per cio' che merita un occhio umano: un segnale
    # plausibile, o una vulnerabilita' con un fix disponibile. Le forme da fixture
    # restano elencate ma **non spengono la luce**: era il difetto del 2026-10-10,
    # quando 15 progetti su 17 uscivano 1 per la stessa regola su valori finti.
    problemi = any(e.get("tracciabili") for e in esiti) or any(
        e.get("con_fix_disponibile") for e in esiti
    )
    print("\nesito: " + ("da esaminare" if problemi else "nessun rilievo"))
    return 1 if problemi else 0


if __name__ == "__main__":
    raise SystemExit(main())
