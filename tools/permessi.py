#!/usr/bin/env python3
"""I permessi attivi mentono? La mappa delle autorizzazioni contro la realta'.

    python3 tools/permessi.py check [--strict] [--json] [--root <cartella>]
    python3 tools/permessi.py autotest

Con piu' sessioni che lavorano insieme, un permesso puo' restare aperto quando il
lavoro e' finito, o puntare a qualcosa che non c'e' piu'. Questo controllo e' di
**sola lettura**: trova i permessi che mentono, non li chiude.

Quattro difetti, tre gravi e uno da guardare:

(a) **scaduto** — `expires` nel passato e `status: active`: il permesso dichiara
    di valere ma non vale piu' (e' la forma di `DRIFT-019`);
(b) **cartella inesistente** — un `write_scope` su una cartella numerata che non
    c'e' piu': e' il caso di `NLT-036`, rimasto attivo dopo la cancellazione del
    progetto 17 (`DRIFT-030`). Si controllano **tutte** le cartelle numerate del
    raggio, non solo la prima;
(c) **senza marcatore** — nessun file in `approvazioni/` per quel `task_id`: un
    permesso attivo senza consenso del CEO non copre niente, e la mappa mente
    comunque (vedi `ad_scope.coverage`);
(d) **appeso** — il passo (`milestone`/`sprint`) ha gia' il suo `REPORT.md`, ma il
    permesso e' ancora `active`: il lavoro e' chiuso e il permesso dovrebbe
    esserlo. E' un avviso, perche' fra il report e la chiusura passano minuti
    normali; con `--strict` diventa un errore, **anche con `--json`**.

Esito: 0 nessun errore (gli avvisi restano visibili, salvo `--strict`),
1 almeno un errore.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ad_scope  # noqa: E402
import yaml

NUMERATA = re.compile(r"^(\d+)\.")


def _scaduto(valore: object) -> bool:
    """True se una data ISO dichiarata e' nel passato."""
    if not isinstance(valore, str) or not valore.strip():
        return False
    testo = valore.strip().replace("Z", "+00:00")
    try:
        momento = datetime.fromisoformat(testo)
    except ValueError:
        return False
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return momento < datetime.now(timezone.utc)


def _dati(percorso: Path) -> dict:
    """Legge il blocco YAML di un contract, o un dizionario vuoto."""
    try:
        dati = yaml.safe_load(percorso.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return dati if isinstance(dati, dict) else {}


def _scopes(dati: dict) -> tuple[str, ...]:
    """I percorsi di un contract, normalizzati."""
    grezzo = dati.get("write_scope")
    if isinstance(grezzo, str):
        grezzo = [grezzo]
    if not isinstance(grezzo, list):
        return ()
    return tuple(str(voce) for voce in grezzo if str(voce).strip())


def _progetti(scopes: tuple[str, ...]) -> list[tuple[str, Path]]:
    """**Tutte** le cartelle numerate di un raggio, in ordine e senza doppioni.

    Un contract puo' nominare piu' di una cartella di progetto: guardare solo la
    prima lascerebbe un buco (un raggio che nomina anche una cartella sparita).
    """
    visti: dict[str, Path] = {}
    for scope in scopes or ():
        testa = (
            str(scope).replace("\\", "/").strip().strip('"').strip("'").split("/", 1)[0]
        )
        if NUMERATA.match(testa):
            visti.setdefault(testa, Path(testa))
    return list(visti.items())


def _contracts(base: Path) -> list[tuple[Path, dict]]:
    """Tutti i contract che dichiarano uno ``write_scope``, anche scaduti.

    Il caricatore di ``ad_scope`` salta di proposito i contract scaduti: per
    l'autorizzazione e' giusto (non coprono nulla), per la **mappa** no — un
    permesso scaduto rimasto `active` e' proprio cio' che questo controllo cerca.
    """
    cartella = base / ad_scope.CONTRACTS_DIR
    if not cartella.is_dir():
        return []
    trovati: list[tuple[Path, dict]] = []
    for percorso in sorted(set(cartella.rglob("*.yaml")) | set(cartella.rglob("*.yml"))):
        if percorso.name.startswith("_"):
            continue
        dati = _dati(percorso)
        if dati:
            trovati.append((percorso, dati))
    return trovati


def esito(
    errori: list[str], avvisi: list[str], strict: bool = False
) -> tuple[bool, int]:
    """Decide l'esito e il codice di uscita, con o senza ``--strict``.

    E' una funzione sola perche' i due rami (testo e JSON) devono dire la stessa
    cosa: la prima versione applicava `--strict` solo al ramo di testo, e un
    chiamante automatico riceveva un verde falso (`GOV-013`, R1 REJECT).
    """
    if errori:
        return False, 1
    if strict and avvisi:
        return False, 1
    return True, 0


#: La data da cui la regola vale: chi si e' chiuso prima e' storia, non un difetto.
REGOLA_DAL = "2026-11-03"


def _chiuso_dopo_la_regola(dati: dict) -> bool:
    """E' un ritiro successivo a DEC-0100? Solo quelli vanno controllati."""
    for chiave in ("chiuso_il", "closed_at", "data", "aperto"):
        valore = str(dati.get(chiave) or "").strip()
        if valore:
            return valore[:10] >= REGOLA_DAL
    # Senza una data non si accusa: un dato che manca non e' una colpa.
    return False


def _percorsi_trasferiti(base: Path) -> set[str]:
    """I percorsi gia' ceduti, letti dal libro mastro (DEC-0093)."""
    import yaml

    libro = base / ad_scope.CONTRACTS_DIR / "_trasferimenti.yaml"
    if not libro.is_file():
        return set()
    try:
        dato = yaml.safe_load(libro.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return set()
    if not isinstance(dato, dict):
        return set()
    ceduti: set[str] = set()
    for voce in dato.get("trasferimenti") or []:
        if isinstance(voce, dict):
            ceduti.update(str(p) for p in (voce.get("percorsi") or []))
    return ceduti


def esamina(root: Path | str | None = None) -> tuple[list[str], list[str]]:
    """Elenca gli errori e gli avvisi dei permessi attivi.

    Args:
        root: radice della macchina (default: quella di questo checkout).

    Returns:
        ``(errori, avvisi)``: messaggi pronti da stampare.
    """
    base = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    errori: list[str] = []
    avvisi: list[str] = []

    # DEC-0100 — IL RITIRO SENZA TRASFERIMENTO LASCIA I PERCORSI IN TERRA DI NESSUNO.
    #
    # Il 2026-11-03 e' successo: `ENG-017` era `superseded` e i suoi quattro percorsi
    # non appartenevano piu' a nessuno. `ad_scope` li dava «NON coperto», e per una
    # notte una sessione ci ha scritto senza che il cancello potesse fermarla — non
    # perche' il cancello fosse rotto, ma perche' non c'era un contract da interrogare.
    #
    # Il protocollo di trasferimento esiste (DEC-0093). Questo controllo obbliga a
    # usarlo: un ritiro e' completo solo quando i percorsi sono stati ceduti a qualcuno,
    # oppure dichiarati abbandonati. Senza, il buco si ripete a ogni ritiro.
    trasferiti = _percorsi_trasferiti(base)
    for percorso, dati in _contracts(base):
        task_id = str(dati.get("task_id", percorso.stem))
        status = str(dati.get("status", "active")).strip().lower()
        # Vale per OGNI stato che non copre piu': `superseded` **e** `closed`. Un
        # contract chiuso con i suoi percorsi lasciati li' e' lo stesso buco — misurato
        # il 2026-11-03: chiuso ENG-020, `tests/test_banco.py` non era coperto da
        # nessuno, e il controllo taceva perche' guardava solo i ritirati.
        if status not in ("superseded", "superato", "closed", "chiuso"):
            continue
        # SOLO I RITIRI NUOVI. La regola vale da DEC-0100 (2026-11-03): i 400 contract
        # chiusi prima non si toccano — sono storia, e chiedere il trasferimento per
        # ognuno produrrebbe 34 avvisi su archeologia che nessuno legge. Un controllo che
        # segnala 34 cose vecchie e 0 nuove insegna a ignorarlo, che e' peggio di non
        # averlo (e' la lezione di ERR-0088). Si guarda solo chi si e' chiuso da quando
        # la regola esiste.
        if not _chiuso_dopo_la_regola(dati):
            continue
        orfani = [voce for voce in _scopes(dati) if voce not in trasferiti]
        if orfani and str(dati.get("percorsi_abbandonati", "")).strip().lower() != "true":
            avvisi.append(
                f"{task_id}: ritirato (`{status}`) ma {len(orfani)} percorsi non sono stati "
                f"trasferiti — nessun contract li copre, e il cancello non puo' fermare chi "
                f"ci scrive: {', '.join(orfani[:3])}"
                f"{'…' if len(orfani) > 3 else ''}. "
                f"Rimedio: `python3 tools/ad_transfer.py trasferisci --da {task_id} "
                f"--a <nuovo> --decisione <DEC>`, oppure dichiara "
                f"`percorsi_abbandonati: true` in {percorso.name} se non servono piu'"
            )

    approvazioni = ad_scope.load_approvals(base)
    conosco: set[str] = set()
    for percorso, dati in _contracts(base):
        task_id = str(dati.get("task_id", percorso.stem))
        conosco.add(task_id)
        status = str(dati.get("status", "active")).strip().lower()
        if status not in ad_scope.ACTIVE_STATES:
            continue
        scopes = _scopes(dati)

        if _scaduto(dati.get("expires")):
            errori.append(
                f"{task_id}: scaduto il {dati.get('expires')} ma ancora `active` "
                f"({percorso})"
            )
        if task_id not in approvazioni:
            errori.append(
                f"{task_id}: `active` ma senza il marcatore di approvazione del CEO "
                f"in {ad_scope.APPROVALS_DIR}/ — non copre niente ({percorso})"
            )

        progetti = _progetti(scopes)
        if not progetti:
            # Permesso di macchina: niente cartella di progetto da controllare.
            continue

        tappa = dati.get("milestone")
        passo = dati.get("sprint")
        passo_valido = (
            isinstance(tappa, int)
            and not isinstance(tappa, bool)
            and isinstance(passo, int)
            and not isinstance(passo, bool)
        )
        if not passo_valido:
            avvisi.append(
                f"{task_id}: permesso di progetto senza `milestone`/`sprint` ({percorso})"
            )

        for testa, cartella in progetti:
            if not (base / cartella).is_dir():
                errori.append(
                    f"{task_id}: `active` su \"{testa}\", che non esiste piu' ({percorso})"
                )
                continue
            if not passo_valido:
                continue
            rapporto = (
                base
                / cartella
                / "Analisi-Prompt-Report"
                / f"Milestone {tappa}"
                / f"Sprint {passo}"
                / "REPORT.md"
            )
            if rapporto.is_file():
                avvisi.append(
                    f"{task_id}: appeso — il passo {tappa}/{passo} ha gia' il suo report, "
                    f"ma il permesso e' ancora `active` ({percorso})"
                )

    for task_id, marker in sorted(approvazioni.items()):
        if task_id not in conosco:
            avvisi.append(
                f"{task_id}: marcatore di approvazione senza nessun contract "
                f"({marker.source})"
            )
    return errori, avvisi


def cmd_check(args: argparse.Namespace) -> int:
    """Stampa l'esito del controllo."""
    errori, avvisi = esamina(args.root)
    ok, codice = esito(errori, avvisi, strict=bool(args.strict))
    if args.json:
        print(
            json.dumps(
                {
                    "errori": errori,
                    "avvisi": avvisi,
                    "strict": bool(args.strict),
                    "ok": ok,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return codice
    for messaggio in errori:
        print(f"  ERRORE  {messaggio}")
    for messaggio in avvisi:
        print(f"  avviso  {messaggio}")
    if errori:
        print(
            f"\nesito: {len(errori)} errori, {len(avvisi)} avvisi — "
            "la mappa dei permessi non e' vera"
        )
        return codice
    if avvisi and args.strict:
        print(f"\nesito: {len(avvisi)} avvisi (trattati come errori per --strict)")
        return codice
    print(f"OK   nessun permesso mente ({len(avvisi)} avvisi)")
    return codice


def cmd_autotest(args: argparse.Namespace) -> int:
    """Costruisce un albero finto e verifica che il controllo morda."""
    fallite: list[str] = []
    ok = 0

    def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
        nonlocal ok
        if condizione:
            ok += 1
        else:
            fallite.append(f"{etichetta}: {dettaglio or 'condizione falsa'}")

    with tempfile.TemporaryDirectory(prefix="permessi-") as temporanea:
        base = Path(temporanea)
        (base / "contratti" / "prova").mkdir(parents=True)
        (base / "approvazioni" / "prova").mkdir(parents=True)
        (base / "9. Prova" / "Analisi-Prompt-Report" / "Milestone 1" / "Sprint 1").mkdir(
            parents=True
        )

        def contract(
            nome: str,
            scopes: list[str],
            expires: str = "",
            tappa: int | None = None,
            passo: int | None = None,
            stato: str = "active",
        ) -> None:
            righe = [f"task_id: {nome}", "agent: platform", f"status: {stato}"]
            if expires:
                righe.append(f'expires: "{expires}"')
            if tappa is not None:
                righe.append(f"milestone: {tappa}")
            if passo is not None:
                righe.append(f"sprint: {passo}")
            righe.append("write_scope:")
            righe.extend(f'  - "{s}"' for s in scopes)
            (base / "contratti" / "prova" / f"{nome}.yaml").write_text(
                "\n".join(righe) + "\n", encoding="utf-8"
            )

        def marker(nome: str) -> None:
            (base / "approvazioni" / "prova" / f"{nome}.yaml").write_text(
                f'task_id: {nome}\napprovato_da: CEO\ndata: "2026-10-22T10:00:00+02:00"\n',
                encoding="utf-8",
            )

        # (a) scaduto, (b) cartella inesistente, (b2) inesistente come SECONDA
        # cartella del raggio, (c) senza marcatore, (d) appeso.
        contract("SCA-001", ["9. Prova/Analisi-Prompt-Report/"], expires="2020-01-01")
        marker("SCA-001")
        contract("FAN-001", ["77. Fantasma/Analisi-Prompt-Report/"], tappa=1, passo=1)
        marker("FAN-001")
        contract(
            "MUL-001",
            ["9. Prova/Analisi-Prompt-Report/", "88. Fantasma/Analisi-Prompt-Report/"],
            tappa=1,
            passo=1,
        )
        marker("MUL-001")
        contract("SEN-001", ["9. Prova/Analisi-Prompt-Report/"], tappa=1, passo=1)
        contract("APP-001", ["9. Prova/Analisi-Prompt-Report/"], tappa=9, passo=9)
        marker("APP-001")
        (base / "9. Prova" / "Analisi-Prompt-Report" / "Milestone 9" / "Sprint 9").mkdir(
            parents=True
        )
        (
            base
            / "9. Prova"
            / "Analisi-Prompt-Report"
            / "Milestone 9"
            / "Sprint 9"
            / "REPORT.md"
        ).write_text("# report\n", encoding="utf-8")
        # Caso pulito: attivo, non scaduto, con marcatore, senza passo chiuso.
        contract("BON-001", ["9. Prova/Analisi-Prompt-Report/"], tappa=1, passo=1)
        marker("BON-001")

        errori, avvisi = esamina(base)
        uniti = "\n".join(errori)
        check("prende il permesso scaduto", "SCA-001: scaduto" in uniti, uniti)
        check(
            "prende il permesso su cartella inesistente",
            "FAN-001" in uniti and "non esiste" in uniti,
            uniti,
        )
        check(
            "guarda tutte le cartelle del raggio, non solo la prima",
            "MUL-001" in uniti and "88. Fantasma" in uniti,
            uniti,
        )
        check(
            "prende il permesso senza marcatore",
            "SEN-001" in uniti and "senza il marcatore" in uniti,
            uniti,
        )
        check(
            "segnala il permesso appeso fra gli avvisi",
            any("APP-001" in voce and "appeso" in voce for voce in avvisi),
            "\n".join(avvisi),
        )
        check(
            "non segnala il caso pulito",
            not any("BON-001" in voce for voce in errori + avvisi),
            "\n".join(errori + avvisi),
        )
        check("il caso pulito non aggiunge errori", len(errori) == 4, str(errori))
        # strict: un solo avviso, nessun errore -> senza strict verde, con strict rosso,
        # anche nella forma macchina (stdout JSON e codice di uscita).
        solo_avvisi = ["APP-001: appeso"]
        check("senza --strict un avviso non e' un errore", esito([], solo_avvisi)[1] == 0)
        check("con --strict un avviso e' un errore", esito([], solo_avvisi, True)[1] == 1)
        check("con --strict il verde resta verde", esito([], [], True)[1] == 0)
        check("un errore e' rosso anche senza --strict", esito(["x"], [], False)[1] == 1)

    if fallite:
        for voce in fallite:
            print(f"  FALLITO  {voce}")
        print(f"\nesito: {len(fallite)} prove fallite")
        return 1
    print(f"OK   {ok} prove passate: il controllo morde")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(description="I permessi attivi mentono?")
    sub = parser.add_subparsers(dest="comando", required=True)
    controlla = sub.add_parser("check", help="elenca i permessi che mentono")
    controlla.add_argument("--root", default=None, help="radice da controllare")
    controlla.add_argument(
        "--strict",
        action="store_true",
        help="tratta gli avvisi come errori (anche con --json)",
    )
    controlla.add_argument("--json", action="store_true", help="output JSON")
    prova = sub.add_parser("autotest", help="prova che il controllo morde, su un albero finto")
    prova.add_argument(
        "--root", default=None, help="ignorato: la prova usa una cartella temporanea"
    )
    args = parser.parse_args(argv)
    if args.comando == "autotest":
        return cmd_autotest(args)
    return cmd_check(args)


if __name__ == "__main__":
    raise SystemExit(main())
