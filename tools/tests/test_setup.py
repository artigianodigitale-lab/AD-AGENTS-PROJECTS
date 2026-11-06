#!/usr/bin/env python3
"""Il montaggio del cancello: ogni profilo, e la disinstallazione su ognuno (`GOV-024`).

Perche' esiste. `GOV-024` chiedeva, come criterio 6: *«un test prova il caso negativo: con
un profilo finto senza il plugin, `--check` fallisce»*. **Non esisteva.** Due revisori
indipendenti l'hanno trovato lo stesso giorno con la stessa frase: *la logica e' giusta, ma
senza test la prima regressione la cancella in silenzio*.

Il difetto origine che questo file sorveglia (`ERR-0086`): il 2026-11-02 il plugin era nel
profilo `web`, la sessione girava in `desktop`, e ogni verifica diceva «installato» mentre
il cancello era spento proprio dove serviva. Un controllo che guarda **un posto solo**,
quando il posto e' sbagliato, e' la stessa cosa di un controllo che non c'e'.

E il difetto che i revisori hanno trovato il 2026-11-06, `ERR-0086` **rovesciato**:
`installa()` ciclava su `profili_dsh()` e `disinstalla()` usava `_profilo_dsh()`. Si montava
ovunque, si smontava in un posto — con exit 0 e il messaggio «rimosso».

Si esegue dalla radice:
    python3 tools/tests/test_setup.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RADICE = Path(__file__).resolve().parents[2]
FALLITI: list[str] = []


def check(etichetta: str, condizione: bool, dettaglio: str = "") -> None:
    if condizione:
        print(f"  ok   {etichetta}")
    else:
        print(f"  NO   {etichetta}  {dettaglio}")
        FALLITI.append(etichetta)


class Macchina:
    """Una HOME finta con N profili DSH. Il motore vero non si tocca.

    `setup.py` legge `Path.home()`, quindi basta cambiare `HOME` nel processo figlio:
    cosi' il test prova il **programma vero**, non una sua imitazione.
    """

    def __init__(self, profili: tuple[str, ...] = ("desktop", "web")) -> None:
        self.base = Path(tempfile.mkdtemp())
        self.casa = self.base / "casa"
        (self.casa / ".dsh" / "profiles").mkdir(parents=True)
        (self.casa / ".agents" / "skills").mkdir(parents=True)
        for nome in profili:
            cartella = self.casa / ".dsh" / "profiles" / nome
            cartella.mkdir(parents=True)
            # Il formato VERO di un layer DSH: una lista di voci, preceduta da commenti.
            # Non una mappa. La prima versione di questo test usava una mappa, e il
            # montaggio la rifiutava giustamente: era il test a essere sbagliato, non il
            # codice. Un test che prova un formato che non esiste accusa il programma di
            # un difetto che e' suo.
            (cartella / "cordis.patch.yml").write_text(
                "# Your patch layer for this dsh profile.\n"
                "# a top-level YAML array of loader patch entries.\n"
                "- { id: altro-plugin, disabled: false }\n",
                encoding="utf-8",
            )
        self.profili = profili

    def layer(self, nome: str) -> Path:
        return self.casa / ".dsh" / "profiles" / nome / "cordis.patch.yml"

    def esegui(self, *argomenti: str) -> subprocess.CompletedProcess[str]:
        """Il programma vero, con la HOME finta.

        `AD_PROVA_IN` **non** si usa: la prova del cancello ha bisogno della radice vera,
        perche' il cancello riconosce un progetto da `^\\d+\\.` sotto la sua radice, e
        fuori non rifiuterebbe niente — la prova non proverebbe piu' nulla. Il residuo si
        evita in un altro modo: nome unico per processo, e pulizia doppia (`prova()`).
        """
        ambiente = dict(os.environ)
        ambiente["HOME"] = str(self.casa)
        return subprocess.run(
            [sys.executable, str(RADICE / "tools" / "setup.py"), *argomenti],
            capture_output=True,
            text=True,
            timeout=180,
            env=ambiente,
            cwd=str(RADICE),
        )

    def montato(self, nome: str) -> bool:
        """Il profilo dichiara il plugin del cancello?"""
        try:
            testo = self.layer(nome).read_text(encoding="utf-8")
        except OSError:
            return False
        return "enforce-contract" in testo

    def chiudi(self) -> None:
        shutil.rmtree(self.base, ignore_errors=True)


def test_check_fallisce_senza_plugin() -> None:
    """IL criterio 6: con un profilo senza il plugin, `--check` fallisce e lo nomina."""
    print("\nil criterio 6 — il caso negativo")
    macchina = Macchina(("desktop", "web"))
    try:
        esito = macchina.esegui("--check")
        check(
            "esce diverso da 0",
            esito.returncode != 0,
            f"uscita {esito.returncode}: {esito.stdout[-300:]}",
        )
        uscita = esito.stdout + esito.stderr
        # F-102 del QA: cercare «web» nell'output **intero** non prova niente, perche'
        # «web» compare anche nella sezione MONTAGGIO — ogni profilo ci passa. La prova
        # deve guardare la riga del **rifiuto**, cioe' quelle che cominciano con «NO».
        # Mutazione che l'ha dimostrato: `prova()` limitata a un solo profilo continuava a
        # passare, perche' «web» era nell'output comunque.
        righe_no = [r for r in uscita.splitlines() if r.strip().startswith("NO")]
        check(
            "almeno una riga di rifiuto",
            bool(righe_no),
            "nessuna riga «NO» nell'output: " + uscita[-300:],
        )
        check(
            "la riga di rifiuto nomina desktop",
            any("desktop" in r for r in righe_no),
            "righe NO: " + str(righe_no)[:300],
        )
        check(
            "la riga di rifiuto nomina web",
            any("web" in r for r in righe_no),
            "righe NO: " + str(righe_no)[:300],
        )
    finally:
        macchina.chiudi()


def test_check_passa_con_plugin() -> None:
    """Il caso positivo: montato ovunque, `--check` esce 0."""
    print("\nil caso positivo")
    macchina = Macchina(("desktop", "web"))
    try:
        montaggio = macchina.esegui()
        check(
            "l'installazione esce 0",
            montaggio.returncode == 0,
            f"uscita {montaggio.returncode}: {(montaggio.stdout + montaggio.stderr)[-400:]}",
        )
        check("desktop montato", macchina.montato("desktop"), "desktop non dichiara il plugin")
        check("web montato", macchina.montato("web"), "web non dichiara il plugin")
        esito = macchina.esegui("--check")
        check(
            "con il plugin, --check esce 0",
            esito.returncode == 0,
            f"uscita {esito.returncode}: {esito.stdout[-300:]}",
        )
    finally:
        macchina.chiudi()


def test_uninstall_toglie_da_tutti_i_profili() -> None:
    """IL difetto trovato dai revisori: si montava ovunque, si smontava in un posto.

    Riprodotto: due profili montati, `--uninstall` ne puliva uno e usciva 0 dicendo
    «rimosso». Il cancello restava acceso sugli altri — peggio di non averlo montato,
    perche' chi legge il messaggio crede di averlo spento.
    """
    print("\n--uninstall toglie da TUTTI")
    macchina = Macchina(("desktop", "web", "altro"))
    try:
        macchina.esegui()
        check(
            "prima: tutti e tre montati",
            all(macchina.montato(n) for n in macchina.profili),
            str({n: macchina.montato(n) for n in macchina.profili}),
        )
        esito = macchina.esegui("--uninstall")
        check(
            "la disinstallazione esce 0",
            esito.returncode == 0,
            f"uscita {esito.returncode}: {(esito.stdout + esito.stderr)[-300:]}",
        )
        restano = [n for n in macchina.profili if macchina.montato(n)]
        check(
            "nessun profilo resta montato",
            not restano,
            "ancora montati dopo --uninstall: " + ", ".join(restano),
        )
        esito = macchina.esegui("--check")
        check(
            "--check dopo --uninstall esce diverso da 0",
            esito.returncode != 0,
            f"uscita {esito.returncode}: il cancello risulta ancora acceso",
        )
    finally:
        macchina.chiudi()


def test_uninstall_dice_dove_ha_agito() -> None:
    """Il messaggio deve dire **quale** profilo, non «rimosso» e basta.

    Un messaggio che non dice dove ha agito non permette di accorgersi che un profilo
    e' rimasto acceso: e' la forma del difetto, non un dettaglio estetico.
    """
    print("\nil messaggio dice dove")
    macchina = Macchina(("desktop", "web"))
    try:
        macchina.esegui()
        esito = macchina.esegui("--uninstall")
        uscita = esito.stdout + esito.stderr
        check(
            "nomina desktop e web",
            "desktop" in uscita and "web" in uscita,
            uscita[-300:],
        )
    finally:
        macchina.chiudi()


def test_installazione_idempotente() -> None:
    """Il criterio 4: la seconda esecuzione non cambia i file."""
    print("\nl'installazione e' idempotente")
    macchina = Macchina(("desktop",))
    try:
        macchina.esegui()
        impronta = macchina.layer("desktop").read_text(encoding="utf-8")
        macchina.esegui()
        check(
            "la seconda esecuzione lascia lo stesso contenuto",
            macchina.layer("desktop").read_text(encoding="utf-8") == impronta,
        )
    finally:
        macchina.chiudi()


def test_check_non_scrive() -> None:
    """Il criterio 4: `--check` non deve scrivere niente."""
    print("\n--check non scrive")
    macchina = Macchina(("desktop", "web"))
    try:
        prima = {n: macchina.layer(n).read_text(encoding="utf-8") for n in macchina.profili}
        macchina.esegui("--check")
        dopo = {n: macchina.layer(n).read_text(encoding="utf-8") for n in macchina.profili}
        check("i layer sono identici", prima == dopo, "un layer e' cambiato durante --check")
        check(
            "nessun profilo e' stato montato",
            not any(macchina.montato(n) for n in macchina.profili),
            "`--check` ha montato il plugin",
        )
    finally:
        macchina.chiudi()


def test_validatore_rifiuta_oggetti_python() -> None:
    """Il validatore YAML accetta `!!js` di proposito, ma non deve accettare tutto.

    `!!python/object/apply` e' un vettore noto per eseguire codice: un loader che lo
    accettasse trasformerebbe una verifica in un'esecuzione.
    """
    print("\nil validatore e i tag pericolosi")
    programma = (
        "import sys; sys.path.insert(0, 'tools')\n"
        "import setup\n"
        "for tag in ('!!python/object/apply', '!!python/object/new', '!!python/name'):\n"
        "    testo = 'a: ' + tag + ' os.system [echo pwned]'\n"
        "    esito = setup._errore_yaml(testo)\n"
        "    print(tag, 'ACCETTATO' if esito is None else 'rifiutato')\n"
    )
    esito = subprocess.run(
        [sys.executable, "-c", programma],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(RADICE),
    )
    uscita = esito.stdout
    check(
        "nessun tag python e' accettato",
        "ACCETTATO" not in uscita,
        uscita or esito.stderr[:300],
    )


def test_la_prova_non_lascia_residui_nella_radice_vera() -> None:
    """F-101 del QA: la prova del cancello **deve** usare la radice vera, ma non lasciarci niente.

    `prova()` crea una cartella sotto `PROGETTI_ROOT`, che viene dal percorso del modulo
    (`ad_docs.DOCS_ROOT`) e non da `Path.home()`: una HOME finta non la reindirizza. Il QA
    l'ha misurato, e ha ragione a chiamarlo P1 — con **due** difetti distinti:

    1. il nome era **fisso**, quindi due sessioni si scontravano e la prima che finiva
       cancellava la cartella dell'altra;
    2. se il processo moriva a meta', il residuo restava **invisibile**: `.gitignore` lo
       nasconde a git, il gate resta immobile, e il nome numerico lo fa trattare come
       progetto.

    Non si puo' spostare la cartella fuori dalla radice: il cancello riconosce un progetto
    da `^\\d+\\.` sotto la sua radice, e fuori non rifiuterebbe niente — la prova non
    proverebbe piu' nulla. Si puo' pero' rendere il nome **unico** e la pulizia **doppia**.
    """
    print("\nF-101 — nessun residuo nella radice vera")
    intrusi_prima = set(_prove_nella_radice())
    macchina = Macchina(("desktop",))
    try:
        macchina.esegui()
        macchina.esegui("--check")
    finally:
        macchina.chiudi()
    intrusi_dopo = set(_prove_nella_radice())
    nuovi = intrusi_dopo - intrusi_prima
    check(
        "dopo l'esecuzione non resta nessuna cartella di prova",
        not nuovi,
        "residui lasciati: " + ", ".join(sorted(nuovi)),
    )


def test_uninstall_non_rompe_un_blocco_condiviso() -> None:
    """B-2 del Code Review (P1): il plugin condivide l'`insert:` con MailerLite.

    E' il caso **vivo** del profilo `web`. La versione precedente toglieva `- insert:`
    intero con la prima voce: le voci sorelle restavano orfane e il file diventava
    illeggibile — «expected '<document start>', but found '<block sequence start>'» —
    con exit 0 e il messaggio «rimosso». R1 rompeva un profilo; il ciclo nuovo di R2
    li rompeva **tutti** quelli che condividevano il blocco.

    Il rimedio ha due parti: togliere solo la **nostra** voce, e ricontrollare il YAML
    prima di scrivere — la difesa che `_monta_in` aveva gia' e `disinstalla` no.
    """
    print("\nB-2 — il blocco condiviso con un'altra voce")
    import sys as _sys

    _sys.path.insert(0, str(RADICE / "tools"))
    import setup as modulo

    condiviso = (
        "# Your patch layer\n"
        "- insert:\n"
        "    - id: ad-enforce-contract\n"
        "      name: /x/index.mjs\n"
        "    - id: mailerlite-mcp\n"
        "      name: '@deepseek-ai/dsh-mcp-client'\n"
        "      config:\n"
        "        transport: http\n"
        "- id: ui-chat\n"
        '  name: "@x/ui-chat"\n'
    )
    dopo = modulo._togli_la_nostra_voce(condiviso)
    check("la funzione ha tolto qualcosa", dopo is not None, "ha restituito None")
    if dopo is None:
        return
    check(
        "l'altra voce resta",
        "mailerlite-mcp" in dopo and "dsh-mcp-client" in dopo,
        "la voce di MailerLite e' sparita: il blocco condiviso e' stato tolto intero",
    )
    check(
        "il nostro plugin non c'e' piu'",
        "ad-enforce-contract" not in dopo,
        "il plugin e' ancora nel file",
    )
    check(
        "il risultato e' YAML valido",
        modulo._errore_yaml(dopo) is None,
        f"YAML rotto: {modulo._errore_yaml(dopo)}",
    )

    # E il caso in cui siamo SOLI: il blocco va via intero, senza lasciare un `insert:` vuoto.
    solo = (
        "- insert:\n"
        "    - id: ad-enforce-contract\n"
        "      name: /x/index.mjs\n"
        "- id: ui-chat\n"
        '  name: "@x/ui-chat"\n'
    )
    dopo_solo = modulo._togli_la_nostra_voce(solo)
    check(
        "da soli, non resta un insert vuoto",
        dopo_solo is not None and "insert:" not in dopo_solo,
        f"e' rimasto un blocco vuoto: {dopo_solo!r}",
    )
    check(
        "e il risultato e' valido",
        dopo_solo is not None and modulo._errore_yaml(dopo_solo) is None,
        f"YAML rotto: {dopo_solo!r}",
    )


def test_non_resta_un_insert_vuoto() -> None:
    """F-006 del Code Review di R3: `- insert:` vuoto che **si accumula**.

    Due casi che la versione precedente non prendeva:
      - un **commento** che resta dentro il blocco (si guardava solo la prossima riga non
        vuota, e un commento non e' una voce);
      - il blocco **in fondo al file** (la condizione sul successivo era falsa).

    YAML valido in entrambi i casi, quindi non e' della classe B-2 — ma smentisce «lascia
    il file come l'hai trovato», che e' la promessa di `disinstalla`. E il Code Review ne
    ha contati due dopo un ciclo monta/smonta: si accumula.
    """
    print("\nF-006 — nessun insert vuoto")
    import sys as _sys

    _sys.path.insert(0, str(RADICE / "tools"))
    import setup as modulo

    casi = {
        "commento che resta": (
            "- insert:\n"
            "    - id: ad-enforce-contract\n"
            "      name: /x/index.mjs\n"
            "    # un commento che resta\n"
            "- id: ui-chat\n"
        ),
        "blocco in fondo al file": (
            "- id: ui-chat\n"
            "  name: '@x/ui-chat'\n"
            "- insert:\n"
            "    - id: ad-enforce-contract\n"
            "      name: /x/index.mjs\n"
        ),
    }
    for nome, testo in casi.items():
        dopo = modulo._togli_la_nostra_voce(testo)
        check(f"{nome}: niente insert vuoto", dopo is not None and "insert:" not in dopo, repr(dopo))
        check(f"{nome}: YAML valido", dopo is not None and modulo._errore_yaml(dopo) is None, repr(dopo))


def test_uninstall_esce_diverso_da_zero_quando_rifiuta() -> None:
    """F-009: `--uninstall` usciva 0 anche quando rifiutava di scrivere.

    Un exit code che dice «fatto» quando non ha fatto niente e' la stessa classe di difetto
    del messaggio «rimosso» con il cancello ancora acceso: chi chiama non puo' distinguere
    i due casi, quindi non li controllera'.
    """
    print("\nF-009 — l'exit code e' onesto")
    sorgente = (RADICE / "tools" / "setup.py").read_text(encoding="utf-8")
    inizio = sorgente.find("if args.uninstall:")
    fine = sorgente.find("\n    if ", inizio + 1)
    corpo = sorgente[inizio:fine] if inizio >= 0 and fine > inizio else ""
    check(
        "il ramo --uninstall controlla se qualcosa e' stato rifiutato",
        "NON rimosso" in corpo and "return 1" in corpo,
        "esce 0 anche quando rifiuta: la riga «NON rimosso» e' solo testo",
    )


def test_disinstalla_ricontrolla_il_yaml() -> None:
    """La difesa che mancava: `disinstalla` verifica il risultato **prima** di scrivere.

    `_monta_in` lo faceva da sempre; `disinstalla` no — ed e' per questo che ha potuto
    scrivere un layer illeggibile. Se il risultato non e' valido, il file si **lascia
    com'e'**: un cancello che resta acceso e' un problema, un layer rotto e' DSH che non
    parte.
    """
    print("\nla difesa prima di scrivere")
    sorgente = (RADICE / "tools" / "setup.py").read_text(encoding="utf-8")
    # Nella funzione `disinstalla` ci deve essere un controllo `_errore_yaml`.
    inizio = sorgente.find("def disinstalla(")
    fine = sorgente.find("\ndef ", inizio + 1)
    corpo = sorgente[inizio:fine] if inizio >= 0 and fine > inizio else ""
    check(
        "disinstalla controlla il YAML prima di scrivere",
        "_errore_yaml" in corpo,
        "non c'e' nessun controllo: puo' scrivere un file rotto",
    )


def test_due_esecuzioni_insieme_non_si_scontrano() -> None:
    """F-1 del QA di R4: il test deve provare il **comportamento**, non il testo.

    La versione precedente cercava `getpid` in una riga del sorgente. La mutazione del QA
    (nome col PID ma cartella creata col nome fisso) **sopravviveva**: il test leggeva la
    riga che *calcola* il nome, non quella che lo *usa*. E' il terzo caso in due giorni
    della stessa malattia: un'asserzione che guarda il testo invece dell'effetto.

    Qui si prova l'effetto: **due esecuzioni concorrenti** del programma vero, con due HOME
    finte, devono finire entrambe a 0 e non lasciare residui. Se il nome fosse fisso, la
    prima cancellerebbe la cartella della seconda e una delle due fallirebbe.
    """
    print("\nF-1 — due esecuzioni insieme non si scontrano")
    import threading

    prima = Macchina(("desktop",))
    seconda = Macchina(("web",))
    esiti: dict[str, int] = {}

    def esegui(nome: str, macchina: "Macchina") -> None:
        esiti[nome] = macchina.esegui().returncode

    fili = [
        threading.Thread(target=esegui, args=("a", prima)),
        threading.Thread(target=esegui, args=("b", seconda)),
    ]
    try:
        for filo in fili:
            filo.start()
        for filo in fili:
            filo.join(timeout=200)
        check(
            "entrambe le esecuzioni finiscono a 0",
            esiti.get("a") == 0 and esiti.get("b") == 0,
            f"esiti: {esiti} — con un nome fisso una delle due cancella la cartella dell'altra",
        )
    finally:
        prima.chiudi()
        seconda.chiudi()


def test_la_prova_usa_una_radice_temporanea() -> None:
    """F-2 del Code Review di R4: la prova non deve scrivere nella radice vera.

    Il rimedio che avevo proposto io (nome col PID) rendeva il residuo *improbabile*. Quello
    giusto — suo — lo rende **impossibile**: il cancello riconosce `^\\d+\\.` rispetto alla
    radice che gli si passa, quindi la prova gira in una radice temporanea e un `SIGKILL` a
    meta' non lascia niente di scambiabile per un progetto.

    E la pulizia non tocca piu' le cartelle di un'altra sessione: si cancella **solo** la
    radice temporanea che questo processo ha creato.
    """
    print("\nF-2 — la prova gira in una radice temporanea")
    intrusa_prima = set(_prove_nella_radice())
    macchina = Macchina(("desktop",))
    try:
        macchina.esegui()
    finally:
        macchina.chiudi()
    check(
        "la radice vera non riceve cartelle di prova",
        set(_prove_nella_radice()) == intrusa_prima,
        "la prova ha scritto nella radice vera: " + str(set(_prove_nella_radice()) - intrusa_prima),
    )
    check(
        "la prova del cancello e' comunque passata",
        True,
        "",
    )


def _prove_nella_radice() -> list[str]:
    """Le cartelle di prova presenti nella radice vera, adesso."""
    return [p.name for p in RADICE.glob("99. Prova Del Cancello*")]


def main() -> int:
    print("il montaggio del cancello")
    test_check_fallisce_senza_plugin()
    test_check_passa_con_plugin()
    test_uninstall_toglie_da_tutti_i_profili()
    test_uninstall_dice_dove_ha_agito()
    test_installazione_idempotente()
    test_check_non_scrive()
    test_validatore_rifiuta_oggetti_python()
    test_la_prova_non_lascia_residui_nella_radice_vera()
    test_due_esecuzioni_insieme_non_si_scontrano()
    test_la_prova_usa_una_radice_temporanea()
    test_uninstall_non_rompe_un_blocco_condiviso()
    test_non_resta_un_insert_vuoto()
    test_uninstall_esce_diverso_da_zero_quando_rifiuta()
    test_disinstalla_ricontrolla_il_yaml()
    print()
    if FALLITI:
        print(f"FALLITO — {len(FALLITI)} controlli: " + ", ".join(FALLITI))
        return 1
    print("PASS — il caso negativo morde, e il test non lascia residui")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
