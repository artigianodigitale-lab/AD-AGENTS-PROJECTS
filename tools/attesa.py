#!/usr/bin/env python3
"""L'attesa di un revisore: guardare il FILE, non aspettare il messaggio.

Il problema, misurato il 2026-11-06 su `GOV-026`:

    Code Review   ha finito di scrivere l'evidenza alle 12:07:03
                  il suo messaggio e' arrivato alle          12:16
    Documentation ha finito alle                               11:54:58
                  il messaggio e' arrivato alle              12:06:49

**Dieci minuti di ritardo**, con il file completo e leggibile per tutto il tempo.

La causa: un subagente consegna **un solo messaggio, alla fine del suo turno**. Il file lo
scrive prima — ma il turno non e' finito: sta ancora rileggendo, riassumendo, preparando la
risposta. Chi aspetta il messaggio aspetta un riassunto di qualcosa che ha gia' in mano.

**Questo strumento guarda il file.** Quando l'evidenza e' valida, il verdetto c'e': inutile
aspettare altro.

## Gli stati

    assente      il file non c'e': il revisore sta ancora analizzando, o non e' partito
    in-crescita  il file cresce: sta scrivendo, ed e' vivo
    ferma        non cambia da oltre la soglia: fermo o bloccato — si puo' decidere di
                 interrompere, invece di indovinare
    completa     valido per il gate: il verdetto c'e', si legge
    non-valida   fermo ma non valido: manca qualcosa, o e' scritto a meta'

La distinzione fra `ferma` e `in-crescita` e' il punto: senza, «non e' arrivato niente» non
dice se aspettare o interrompere. Con, dice quale delle due.

## Perche' non un diario scritto dal revisore

Un diario funzionerebbe, ma chiederebbe al revisore di scrivere **anche** il diario — e il
revisore e' gia' lento. Questo strumento legge un file che il revisore scrive **comunque**:
non costa una riga in piu'.

## La regola di «completa» vive in un posto solo

`completa` non si decide qui: si chiede al validatore del gate
(`gate_kit._evidenza_problemi`). Una regola, un posto — se il gate cambia idea su cosa rende
valida un'evidenza, questo strumento cambia con lui senza che nessuno tocchi due file.

Uso:
    python3 tools/attesa.py GOV-026                       # una lettura, e dice lo stato
    python3 tools/attesa.py GOV-026 --ruolo QA            # una sola evidenza
    python3 tools/attesa.py GOV-026 --ogni 90             # ripete ogni 90 secondi
    python3 tools/attesa.py GOV-026 --ogni 90 --soglia 300
    python3 tools/attesa.py GOV-026 --json

Esito: 0 evidenza completa · 1 tempo massimo scaduto senza completezza · 2 errore d'uso.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RADICE / "tests"))

#: Gli stati. Sono sei, e ognuno dice una cosa diversa su cosa fare.
ASSENTE = "assente"
IN_CRESCITA = "in-crescita"
FERMA = "ferma"
COMPLETA = "completa"
NON_VALIDA = "non-valida"
#: L'evidenza e' valida ma **di un giro precedente**: il revisore nuovo non ha ancora
#: scritto. Leggerla come «completa» significherebbe rispondere alla domanda di oggi con
#: il verdetto di ieri.
VECCHIA = "vecchia"
#: L'evidenza e' valida e di questa revisione, ma **dichiara che la verifica non e'
#: conclusa** (`UNKNOWN`, `TRUNCATED`, `SKIPPED`, `UNSUPPORTED`). Il file e' completo; il
#: verdetto no. Diverso da `non-valida`, che e' un file rotto: qui il revisore ha parlato,
#: e ha detto che non ha finito.
INCOMPLETA = "incompleta"

#: Gli esiti che **non sono un verdetto**: dicono «non ho potuto stabilire l'esito».
#: `PASS` e `FAIL` sono verdicti, e si leggono subito — chi aspetta vuole sapere se ha gia'
#: una risposta. Confondere `FAIL` con «non ha finito» (il primo bugs di questo stato) fa
#: aspettare una risposta che e' gia' arrivata, ed e' l'errore opposto a quello che lo
#: stato `incompleta` esiste per evitare.
ESITI_SENZA_VERDETTO = ("UNKNOWN", "TRUNCATED", "SKIPPED", "UNSUPPORTED")

#: Dopo quanti secondi senza cambiamenti un file si considera fermo. Tre minuti: abbastanza
#: perche' un revisore che pensa non venga dichiarato fermo, poco abbastanza per accorgersi
#: di un blocco prima che passi mezz'ora.
SOGLIA_DEFAULT = 180


class Osservazione:
    """Cosa si e' visto, in un istante."""

    def __init__(
        self,
        stato: str,
        percorso: Path,
        byte: int = 0,
        secondi_fermo: int | None = None,
        motivo: str = "",
    ) -> None:
        self.stato = stato
        self.percorso = percorso
        self.byte = byte
        self.secondi_fermo = secondi_fermo
        self.motivo = motivo

    def a_dizionario(self) -> dict:
        return {
            "stato": self.stato,
            "percorso": str(self.percorso),
            "byte": self.byte,
            "secondi_fermo": self.secondi_fermo,
            "motivo": self.motivo,
        }

    def frase(self) -> str:
        """Una riga in parole comprensibili: e' quello che si legge a schermo."""
        if self.stato == ASSENTE:
            return "l'evidenza non c'e' ancora: il revisore sta analizzando"
        if self.stato == IN_CRESCITA:
            return f"il revisore sta scrivendo ({self.byte} byte)"
        if self.stato == COMPLETA:
            return f"l'evidenza e' completa e valida ({self.byte} byte): il verdetto c'e'"
        if self.stato == FERMA:
            return (
                f"l'evidenza non cambia da {self.secondi_fermo}s "
                f"({self.byte} byte): fermo, o bloccato"
            )
        if self.stato == VECCHIA:
            return f"l'evidenza e' di un giro precedente — {self.motivo}"
        if self.stato == INCOMPLETA:
            return f"il revisore ha scritto, ma non ha concluso — {self.motivo}"
        return f"l'evidenza e' ferma ma non valida: {self.motivo}"


def _congelata_il(task: str) -> float | None:
    """Quando e' stata congelata la revisione in corso, come epoch. ``None`` se non c'e'.

    Senza questa data non si distingue un'evidenza di oggi da una di ieri: e leggere il
    verdetto vecchio come se fosse nuovo e' peggio che non leggere niente, perche' sembra
    una risposta.
    """
    percorso = RADICE / "evidenze" / f"{task}-revisione.yaml"
    try:
        import yaml

        dati = yaml.safe_load(percorso.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - senza il manifest non si puo' dire nulla
        return None
    if not isinstance(dati, dict):
        return None
    testo = str(dati.get("frozen_at") or "").strip()
    if not testo:
        return None
    try:
        from datetime import datetime

        return datetime.fromisoformat(testo.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _validatore():
    """Il validatore del gate, importato una volta. Se non c'e', si dice."""
    try:
        import gate_kit  # noqa: PLC0415 - import pigro: serve solo quando si valida

        return gate_kit
    except ImportError:
        return None


def osserva(
    percorso: Path,
    task: str,
    ruolo: str = "",
    *,
    soglia: int = SOGLIA_DEFAULT,
    prima: tuple[int, float] | None = None,
    adesso: float | None = None,
) -> Osservazione:
    """Lo stato dell'evidenza in questo istante.

    ``prima`` e' ``(byte, mtime)`` di una lettura precedente: serve a distinguere un file
    che cresce da uno fermo. Senza, il primo giro non puo' sapere se sta crescendo — e
    dice ``ferma`` solo se il file e' gia' vecchio, il che e' la risposta giusta.
    """
    ora = time.time() if adesso is None else adesso
    try:
        stato_file = percorso.stat()
    except OSError:
        return Osservazione(ASSENTE, percorso)

    byte = stato_file.st_size
    eta = ora - stato_file.st_mtime

    # L'evidenza e' **di questa revisione**? Un file valido ma vecchio e' il verdetto di
    # un giro precedente: dirlo «completa» mentre il revisore nuovo non ha ancora scritto
    # significa leggere la risposta di ieri alla domanda di oggi. Il 2026-11-06, su R2 di
    # `GOV-024`, `attesa.py` ha detto «completa» sulle due evidenze di R1 (13:12 e 13:15)
    # mentre la revisione era stata congelata alle 13:34. Un difetto vero, trovato subito
    # perche' lo stampava accanto all'ora del congelamento.
    congelata = _congelata_il(task)
    if congelata is not None and stato_file.st_mtime < congelata:
        return Osservazione(
            VECCHIA, percorso, byte, int(eta),
            f"scritta alle {time.strftime('%H:%M', time.localtime(stato_file.st_mtime))}, "
            f"la revisione e' congelata alle {time.strftime('%H:%M', time.localtime(congelata))}: "
            "e' il verdetto di un giro precedente",
        )

    if prima is not None:
        byte_prima, mtime_prima = prima
        if stato_file.st_mtime != mtime_prima or byte != byte_prima:
            return Osservazione(IN_CRESCITA, percorso, byte)
        # Niente e' cambiato da prima: e' fermo da quando lo abbiamo visto.
        return _decidi_fermo(percorso, task, ruolo, byte, int(eta), soglia)

    # Prima lettura: se il file e' molto vecchio, e' gia' fermo; altrimenti non si sa
    # ancora, e si dice «in crescita» perche' non si puo' dire il contrario.
    if eta > soglia:
        return _decidi_fermo(percorso, task, ruolo, byte, int(eta), soglia)
    return Osservazione(IN_CRESCITA, percorso, byte)


def _decidi_fermo(
    percorso: Path, task: str, ruolo: str, byte: int, eta: int, soglia: int
) -> Osservazione:
    """Fermo: ma completo o no?

    La domanda «e' valido?» non si risponde qui: si chiede al gate. Se il gate non c'e',
    si dice ``non-valida`` — nel dubbio non si dichiara completo qualcosa che nessuno ha
    verificato.
    """
    if eta <= soglia and byte == 0:
        return Osservazione(ASSENTE, percorso)

    validatore = _validatore()
    if validatore is None:
        return Osservazione(
            NON_VALIDA, percorso, byte, eta, "il validatore del gate non e' importabile"
        )
    try:
        motivo = validatore._evidenza_problemi(percorso, task, ruolo)  # noqa: SLF001
    except Exception as errore:  # noqa: BLE001 - qualunque cosa renda il file illeggibile
        return Osservazione(NON_VALIDA, percorso, byte, eta, f"non si valida: {errore}")
    if motivo:
        return Osservazione(NON_VALIDA, percorso, byte, eta, motivo)

    # Un'evidenza **valida** puo' pero' dichiarare che il verdetto **non c'e'**:
    # `UNKNOWN`, `TRUNCATED`, `SKIPPED`, `UNSUPPORTED` sono esiti legittimi, e
    # significano «non ho potuto stabilire l'esito», non «non ho finito di scrivere».
    # Chiamarli «completa» sarebbe un errore di lettura: il file e' completo, il
    # **verdetto** no. Il 2026-11-06, su `GOV-024` R3, il Code Review ha risposto
    # `UNKNOWN` perche' non aveva finito — e dire «il verdetto c'e'» avrebbe fatto
    # chiudere l'attesa su una verifica che nessuno aveva concluso.
    # `FAIL` **e' un verdetto**, e va letto: il revisore ha concluso che il lavoro non
    # va bene. Solo `UNKNOWN`/`TRUNCATED`/`SKIPPED`/`UNSUPPORTED` dicono «non ho potuto
    # stabilire l'esito». Distinguerli e' il punto: chi legge deve sapere se aspettare
    # ancora, o se ha gia' una risposta negativa in mano.
    esito = _esito_dichiarato(percorso).upper()
    if esito in ESITI_SENZA_VERDETTO:
        return Osservazione(
            INCOMPLETA, percorso, byte, eta,
            f"il file e' valido ma dichiara esito {esito}: la verifica non e' conclusa",
        )
    return Osservazione(COMPLETA, percorso, byte, eta)


def _esito_dichiarato(percorso: Path) -> str:
    """L'esito scritto nell'evidenza, o stringa vuota."""
    try:
        testo = percorso.read_text(encoding="utf-8")
    except OSError:
        return ""
    for riga in testo.splitlines():
        spoglia = riga.strip()
        if spoglia.startswith("outcome:"):
            return spoglia.split(":", 1)[1].strip().strip("'\"")
    return ""


#: Il nome del file dell'evidenza e il ruolo che il gate si aspetta. Sono **due cose
#: diverse**: il file si chiama `-CodeReview.yaml`, il ruolo nel gate e' `Code Review` con
#: lo spazio (`RUOLI_ATTESI`). Confonderli fa dire «non valida» a un'evidenza che il gate
#: accetterebbe — l'ho scoperto sulla prima esecuzione.
RUOLI: tuple[tuple[str, str], ...] = (
    ("QA", "QA"),
    ("CodeReview", "Code Review"),
)


def evidenze_da_guardare(task: str, ruolo: str = "") -> list[tuple[str, str, Path]]:
    """Le evidenze che contano: (suffisso del file, ruolo per il gate, percorso)."""
    voci = RUOLI if not ruolo else tuple(v for v in RUOLI if v[0] == ruolo)
    return [
        (suffisso, ruolo_gate, RADICE / "evidenze" / f"{task}-{suffisso}.yaml")
        for suffisso, ruolo_gate in voci
    ]


def percorso_registro(task: str, root: Path | None = None) -> Path:
    """Dove vive il registro del monitoraggio di un task."""
    base = root if root is not None else RADICE
    return base / "evidenze" / f".monitoraggio-{task}.jsonl"


def registra(task: str, osservazioni: list["Osservazione"], root: Path | None = None) -> None:
    """Aggiunge una riga al registro del monitoraggio. Una riga per giro, non una per file.

    Perche' un registro (`DEC-0110`). Il monitoraggio e' obbligatorio dal 2026-11-06, e una
    regola obbligatoria che non lascia traccia non e' verificabile: chi controlla domani non
    puo' sapere se l'attesa c'e' stata. Il registro e' la prova che il risultato e' stato
    **letto**, non solo che il file esiste.

    Il file e' `.monitoraggio-<TASK>.jsonl`: una riga JSON per osservazione, si aggiunge e
    non si riscrive. Il punto davanti lo tiene fuori dai lettori del registro delle
    evidenze, che cercano `*.yaml`.
    """
    percorso = percorso_registro(task, root)
    try:
        percorso.parent.mkdir(parents=True, exist_ok=True)
        with percorso.open("a", encoding="utf-8", newline="\n") as uscita:
            for osservazione in osservazioni:
                uscita.write(
                    json.dumps(
                        {
                            "quando": datetime.now().isoformat(timespec="seconds"),
                            "stato": osservazione.stato,
                            "file": osservazione.percorso.name,
                            "byte": osservazione.byte,
                            "motivo": osservazione.motivo,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
    except OSError:
        # Il monitoraggio e' un dovere; il registro e' la sua prova. Se non si scrive, lo
        # si dice e il lavoro continua: perdere la prova e' meglio che perdere il lavoro.
        print("  avviso: non ho potuto scrivere il registro del monitoraggio", file=sys.stderr)


def verifica(task: str, ruoli: tuple[str, ...] = ("QA", "CodeReview"), root: Path | None = None) -> int:
    """Il monitoraggio e' avvenuto? Esce 0 se si', 1 se no, dicendo cosa manca.

    Non basta che il registro esista: deve contenere, **per ogni ruolo atteso**,
    un'osservazione `completa` o un verdetto (`PASS`/`FAIL`). Un registro che si ferma a
    «assente» dice che qualcuno ha guardato una volta e poi ha smesso — che e' la cosa che
    la regola vuole impedire.
    """
    percorso = percorso_registro(task, root)
    if not percorso.is_file():
        print(f"  NO   nessun registro di monitoraggio per {task}: {percorso}", file=sys.stderr)
        print("       il monitoraggio e' obbligatorio (DEC-0110): attesa.py --ogni N --registra", file=sys.stderr)
        return 1
    visti: set[str] = set()
    try:
        for riga in percorso.read_text(encoding="utf-8").splitlines():
            if not riga.strip():
                continue
            try:
                voce = json.loads(riga)
            except json.JSONDecodeError:
                continue
            if voce.get("stato") == COMPLETA:
                # Il file dell'evidenza porta il suffisso: `-QA.yaml` o `-CodeReview.yaml`.
                nome = str(voce.get("file", ""))
                for ruolo in ruoli:
                    if nome.endswith(f"-{ruolo}.yaml"):
                        visti.add(ruolo)
    except OSError as errore:
        print(f"  NO   registro illeggibile: {errore}", file=sys.stderr)
        return 1
    mancanti = [ruolo for ruolo in ruoli if ruolo not in visti]
    if mancanti:
        print(
            f"  NO   monitoraggio incompleto per {task}: mai arrivato a «completa» per "
            + ", ".join(mancanti),
            file=sys.stderr,
        )
        return 1
    print(f"  ok   monitoraggio di {task}: «completa» visto per " + ", ".join(ruoli))
    return 0


def main(argv: list[str] | None = None) -> int:
    analizzatore = argparse.ArgumentParser(
        description="Guarda l'evidenza di un revisore invece di aspettarne il messaggio."
    )
    analizzatore.add_argument("task", help="l'identificatore del task, per esempio GOV-026")
    analizzatore.add_argument(
        "--ruolo", choices=("QA", "CodeReview", ""), default="",
        help="una sola evidenza; senza, si guardano tutte",
    )
    analizzatore.add_argument(
        "--ogni", type=int, default=0,
        help="ripete ogni N secondi finche' non e' completa (0 = una volta sola)",
    )
    analizzatore.add_argument(
        "--soglia", type=int, default=SOGLIA_DEFAULT,
        help=f"secondi senza cambiamenti dopo cui il file e' fermo (default {SOGLIA_DEFAULT})",
    )
    analizzatore.add_argument(
        "--massimo", type=int, default=3600,
        help="quanti secondi continuare prima di arrendersi (default 3600)",
    )
    analizzatore.add_argument(
        "--registra", action="store_true",
        help="scrive il registro del monitoraggio in evidenze/.monitoraggio-<TASK>.jsonl",
    )
    analizzatore.add_argument(
        "--verifica", action="store_true",
        help="controlla che il monitoraggio sia avvenuto ed esca 0/1 (DEC-0110)",
    )
    analizzatore.add_argument("--json", action="store_true", help="gli stati in JSON")
    args = analizzatore.parse_args(argv)

    # `--verifica` non guarda i file: legge il registro che il monitoraggio ha lasciato.
    if args.verifica:
        return verifica(args.task)

    if args.ogni and args.ogni < 5:
        print("  --ogni deve essere almeno 5 secondi", file=sys.stderr)
        return 2

    bersagli = evidenze_da_guardare(args.task, args.ruolo)
    if not bersagli:
        print("  nessuna evidenza da guardare", file=sys.stderr)
        return 2

    precedenti: dict[str, tuple[int, float]] = {}
    inizio = time.time()
    ultimi: list[Osservazione] = []

    while True:
        ultimi = []
        for suffisso, ruolo_gate, percorso in bersagli:
            try:
                percorso.stat()
                prima = precedenti.get(suffisso)
            except OSError:
                prima = None
            osservazione = osserva(
                percorso, args.task, ruolo_gate, soglia=args.soglia, prima=prima
            )
            ultimi.append(osservazione)
            try:
                stato_file = percorso.stat()
                precedenti[suffisso] = (stato_file.st_size, stato_file.st_mtime)
            except OSError:
                precedenti.pop(suffisso, None)

        if args.json:
            print(
                json.dumps(
                    {"quando": time.strftime("%H:%M:%S"), "evidenze": [o.a_dizionario() for o in ultimi]},
                    ensure_ascii=False,
                )
            )
        else:
            print(f"[{time.strftime('%H:%M:%S')}]")
            for osservazione in ultimi:
                print(f"  {osservazione.percorso.name:34} {osservazione.frase()}")

        # Il registro si scrive a ogni giro, prima di decidere: anche l'ultimo giro —
        # quello che trova tutto completo — deve restare scritto, altrimenti la prova che
        # il risultato e' stato **letto** manca proprio nel caso che conta.
        if args.registra:
            registra(args.task, ultimi)

        tutte_complete = all(o.stato == COMPLETA for o in ultimi)
        if tutte_complete:
            return 0
        if not args.ogni:
            return 1 if not tutte_complete else 0
        if time.time() - inizio > args.massimo:
            print(f"  tempo massimo ({args.massimo}s) scaduto", file=sys.stderr)
            return 1
        time.sleep(args.ogni)


if __name__ == "__main__":
    raise SystemExit(main())
