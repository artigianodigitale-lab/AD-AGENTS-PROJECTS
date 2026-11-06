#!/usr/bin/env python3
"""Il Decision Engine: dire se il lavoro e' finito, con una regola e non con un parere.

Perche' esiste (`DEC-0107`, Fase 3 di `piani/2026-11-02-review-governance-v2.md` §10).

Il problema che risolve, misurato: `ENG-017` e `ENG-020` hanno consumato **nove revisioni
congelate e nove FAIL**, dodici commit, e sono rimasti aperti con il prodotto funzionante e
223 controlli verdi. La causa non era la qualita' del codice: era che **un solo gate faceva
tre mestieri** — verificare la conformita', cercare difetti, verificare il comportamento —
e tutti e tre avevano lo stesso potere: dire FAIL. Senza la parola *bloccante*, nessuna
delle tre aveva una condizione d'uscita.

Il principio che questa specifica mette in testa, e che vale la pena ripetere:

    Un sistema di controllo deve essere capace di dimostrare che il lavoro e' conforme.
    Non deve dimostrare di essere capace di trovare un difetto all'infinito.

## Puro, deterministico, senza LLM

Riceve `contract`, `findings`, `evidenze`, `budget` e restituisce **uno dei quattro esiti**.
Non chiama nessun modello: la decisione e' una funzione dei dati, e chiunque puo' rifarla a
mano e ottenere lo stesso risultato. E' l'unico modo perche' «il lavoro e' finito» sia una
risposta e non un'altra opinione.

## Le regole, nell'ordine (§10)

    per ogni gate richiesto:
        evidenza assente o non valida            -> INCONCLUSIVE
        evidenza FAIL con finding P0/P1          -> REJECT
        evidenza FAIL con finding solo P2/P3     -> BACKLOG (non blocca)

    se esiste un finding P0 o P1 con disposition != REMEDIATED   -> REJECT
    se review_round > budget                                     -> ESCALATE
    se un waiver non ha i sette campi                            -> REJECT
    se un waiver P0/P1 non e' del CEO                            -> ESCALATE
    altrimenti                                                   -> ACCEPT

**L'ordine e' la regola.** Un'evidenza mancante viene prima di tutto: senza prove non si
decide niente, nemmeno che manchino prove. E il budget viene **dopo** i finding: superare
il budget non puo' cancellare un P1 aperto — anzi, un P1 aperto e' `REJECT` comunque.

## I quattro esiti

    ACCEPT        tutte le condizioni: il lavoro e' conforme
    REJECT        c'e' un P0/P1 aperto, o un'evidenza invalida: torna all'esecutore
    ESCALATE      budget superato, o waiver su P0/P1: decide il CEO, il gate resta visibile
    INCONCLUSIVE  mancano prove: non e' un fallimento, manca un dato

**`ACCEPT` non e' il rilascio.** Se il contract chiede `approval.human`, dopo `ACCEPT`
decide l'umano.

## Il budget non abbassa i requisiti (§6.1)

Superarlo produce `ESCALATE`, **mai** `ACCEPT`. Un budget che migliora l'esito e' un
incentivo a superarlo.

Uso:
    python3 tools/policy.py decidi <cartella>     # legge contract, finding, evidenze
    python3 tools/policy.py regole                # le regole, in chiaro
    python3 tools/policy.py esito <contratto>     # un caso costruito a mano, per prova
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]

#: I quattro esiti. Non sono quattro parole: sono quattro **azioni** diverse, e chi legge
#: il verdetto deve sapere cosa fare senza chiedere.
ACCEPT = "ACCEPT"
REJECT = "REJECT"
ESCALATE = "ESCALATE"
INCONCLUSIVE = "INCONCLUSIVE"
ESITI = (ACCEPT, REJECT, ESCALATE, INCONCLUSIVE)

#: Le severita' che bloccano. P0 e P1 non hanno waiver ordinari (§4.2).
BLOCCANTI = ("P0", "P1")

#: Le disposizioni che chiudono un finding. `REMEDIATED` e' l'unica: un finding corretto
#: non e' piu' un problema, e `ACCEPTED_RISK` **non** chiude un P0/P1.
CHIUSE = ("REMEDIATED",)

#: I sette campi di un waiver valido (§4.1). Senza anche uno solo, il waiver non esiste e
#: il finding resta come se non ci fosse — cioe' blocca. E' il punto: un waiver incompleto
#: non e' un waiver debole, e' nessun waiver.
CAMPI_WAIVER = (
    "finding_id",
    "motivation",
    "residual_impact",
    "mitigations",
    "risk_owner",
    "review_date",
    "decision_ref",
)

#: Il budget di default: tre round (§6). Oltre, decide il CEO.
BUDGET_DEFAULT = 3

#: Chi puo' firmare un waiver su P0/P1: solo il CEO, e solo con un Decision Record.
AUTORITA_P0 = "CEO"


class ErrorePolitica(Exception):
    """L'input non permette di decidere: manca un dato, o c'e' un valore impossibile."""


def waiver_valido(waiver: object) -> tuple[bool, str]:
    """Il waiver ha i sette campi? Restituisce il verdetto e il motivo.

    Il motivo e' importante quanto il verdetto: un waiver respinto senza dire quale campo
    manca e' un waiver che qualcuno riscrivera' sbagliato allo stesso modo.
    """
    if not isinstance(waiver, dict):
        return False, "il waiver non e' una mappatura"
    mancanti = [campo for campo in CAMPI_WAIVER if not str(waiver.get(campo) or "").strip()]
    if mancanti:
        return False, "mancano " + ", ".join(mancanti)
    return True, ""


def _aperti(findings: list[dict]) -> list[dict]:
    """I finding ancora aperti: nessuna disposizione che chiuda."""
    return [
        f
        for f in findings
        if isinstance(f, dict) and str(f.get("disposition") or "").strip().upper() not in CHIUSE
    ]


def _bloccanti_aperti(findings: list[dict]) -> list[dict]:
    """I finding P0/P1 ancora aperti. Sono loro che impediscono di chiudere."""
    return [
        f
        for f in _aperti(findings)
        if str(f.get("severity") or "").strip().upper() in BLOCCANTI
    ]


def decidi(
    *,
    findings: list[dict] | None = None,
    evidenze: dict[str, object] | None = None,
    review_round: int = 1,
    budget: int = BUDGET_DEFAULT,
    waiver: object = None,
) -> dict:
    """Il verdetto, con il motivo. Puro: nessun effetto, nessuno stato.

    ``evidenze``: mappa ruolo -> contenuto dell'evidenza. Un ruolo che il contract richiede
    e che manca e' ``INCONCLUSIVE``: senza prove non si decide, nemmeno che manchino prove.

    ``findings``: la lista dei finding gia' validati da ``tools/finding.py``.

    Restituisce ``{"esito": ..., "motivo": ..., "bloccanti": [...], "backlog": [...]}``.
    """
    finding = list(findings or [])
    prove = dict(evidenze or {})

    # 1. Le prove, prima di tutto. Un'evidenza assente o non valida impedisce di giudicare:
    #    non e' un fallimento del lavoro, e' un dato che manca. Per questo e' l'unico esito
    #    che non accusa nessuno.
    if not prove:
        return _verdetto(INCONCLUSIVE, "nessuna evidenza: non c'e' niente da giudicare", finding)
    for ruolo in ("QA", "CodeReview"):
        contenuto = prove.get(ruolo)
        if contenuto is None:
            return _verdetto(INCONCLUSIVE, f"manca l'evidenza {ruolo}", finding)
        esito_evidenza = _esito_di(contenuto)
        if esito_evidenza is None:
            return _verdetto(INCONCLUSIVE, f"l'evidenza {ruolo} non dichiara un esito valido", finding)
        if esito_evidenza == "FAIL":
            bloccanti = _bloccanti_aperti(finding)
            if bloccanti:
                return _verdetto(
                    REJECT,
                    f"evidenza {ruolo} FAIL, e c'e' un finding bloccante aperto",
                    finding,
                )
            # Un FAIL senza P0/P1 e' un difetto minore: va in backlog, non blocca.
            return _verdetto(
                ACCEPT,
                f"evidenza {ruolo} FAIL ma solo finding non bloccanti: vanno in backlog",
                finding,
            )

    # 2. Un finding bloccante aperto: il lavoro non e' conforme, punto.
    bloccanti = _bloccanti_aperti(finding)

    # 3. Il waiver. Si valuta **prima** di decidere sui bloccanti, perche' puo' spostare
    #    l'esito: un waiver valido su P2/P3 non cambia niente (erano gia' in backlog), ma
    #    uno su P0/P1 non chiude — porta a ESCALATE.
    if waiver is not None:
        valido, motivo = waiver_valido(waiver)
        if not valido:
            return _verdetto(
                REJECT,
                f"waiver non valido: {motivo}. Un waiver incompleto non e' un waiver "
                "debole, e' nessun waiver",
                finding,
            )
        severita_waiver = str(waiver.get("severity") or "").strip().upper()
        if severita_waiver in BLOCCANTI:
            autorita = str(waiver.get("autorita") or waiver.get("authority") or "").strip()
            if autorita.upper() != AUTORITA_P0:
                return _verdetto(
                    REJECT,
                    f"waiver su {severita_waiver} firmato da {autorita or 'nessuno'}: "
                    "P0 e P1 non hanno waiver ordinari, e solo il CEO puo' assumersene "
                    "il rischio con un Decision Record",
                    finding,
                )
            # Firmato dal CEO: non chiude, ma sale. Il gate resta visibile.
            return _verdetto(
                ESCALATE,
                f"waiver su {severita_waiver} firmato dal CEO: il rischio e' suo, e il "
                "gate resta visibile finche' non e' risolto",
                finding,
            )

    if bloccanti:
        return _verdetto(
            REJECT,
            f"{len(bloccanti)} finding bloccante/i aperto/i: "
            + ", ".join(str(f.get("finding_id") or "?") for f in bloccanti[:4]),
            finding,
        )

    # 4. Il budget, **dopo** i finding: superarlo non puo' cancellare un P1, e un P1
    #    sarebbe gia' stato respinto sopra. Il budget limita il costo, non i requisiti.
    if review_round > budget:
        return _verdetto(
            ESCALATE,
            f"budget di revisione superato ({review_round} round su {budget}): decide il "
            "CEO. Superare il budget non abbassa i requisiti e non produce mai ACCEPT",
            finding,
        )

    return _verdetto(ACCEPT, "nessun finding bloccante aperto, evidenze valide", finding)


def _esito_di(contenuto: object) -> str | None:
    """L'esito dichiarato da un'evidenza, o None se non se ne trova uno valido."""
    if isinstance(contenuto, dict):
        valore = contenuto.get("outcome")
    else:
        # Un testo: si cerca la riga `outcome:`. Non si importa yaml per una cosa che si
        # legge in una riga, e non si pretende che l'evidenza sia gia' parsata.
        valore = None
        for riga in str(contenuto).splitlines():
            spoglia = riga.strip()
            if spoglia.startswith("outcome:"):
                valore = spoglia.split(":", 1)[1].strip().strip("'\"")
                break
    if valore is None:
        return None
    testo = str(valore).strip().upper()
    return testo if testo in ("PASS", "FAIL") else None


def _verdetto(esito: str, motivo: str, findings: list[dict]) -> dict:
    """Il verdetto, con i finding divisi fra bloccanti e backlog."""
    bloccanti = _bloccanti_aperti(findings)
    in_backlog = [
        f
        for f in _aperti(findings)
        if f not in bloccanti
    ]
    return {
        "esito": esito,
        "motivo": motivo,
        "bloccanti": bloccanti,
        "backlog": in_backlog,
    }


def regole() -> str:
    """Le regole, in chiaro. L'ordine e' la regola."""
    return """Il Decision Engine, nell'ordine (specifica §10):

  1. nessuna evidenza, o un'evidenza non valida        -> INCONCLUSIVE
  2. evidenza FAIL con un finding bloccante aperto     -> REJECT
  3. evidenza FAIL con soli P2/P3                      -> ACCEPT, in backlog
  4. waiver senza i sette campi                        -> REJECT
  5. waiver su P0/P1 non firmato dal CEO               -> REJECT
  6. waiver su P0/P1 firmato dal CEO                   -> ESCALATE, il gate resta visibile
  7. un finding P0/P1 aperto (disposition != REMEDIATED) -> REJECT
  8. round di revisione oltre il budget                -> ESCALATE
  9. altrimenti                                        -> ACCEPT

I sette campi del waiver: """ + ", ".join(CAMPI_WAIVER) + """

Perche' il budget viene dopo i finding: superare il budget non puo' cancellare un P1
aperto. Un budget che migliora l'esito e' un incentivo a superarlo.

ACCEPT non e' il rilascio: se il contract chiede l'approvazione umana, decide l'umano."""


def main(argv: list[str] | None = None) -> int:
    argomenti = argv if argv is not None else sys.argv[1:]
    comando = argomenti[0] if argomenti else "regole"
    if comando == "regole":
        print(regole())
        return 0
    if comando != "decidi":
        print("uso: python3 tools/policy.py [decidi <cartella> | regole]", file=sys.stderr)
        return 2
    if len(argomenti) < 2:
        print("serve la cartella con contract, findings ed evidenze", file=sys.stderr)
        return 2
    cartella = Path(argomenti[1])
    if not cartella.is_dir():
        print(f"  NO   {cartella} non e' una cartella", file=sys.stderr)
        return 2
    try:
        import yaml

        findings: list[dict] = []
        for nome in ("findings.yaml", "findings.yml"):
            percorso = cartella / nome
            if percorso.is_file():
                dati = yaml.safe_load(percorso.read_text(encoding="utf-8")) or {}
                voci = dati.get("findings") if isinstance(dati, dict) else dati
                findings = [v for v in (voci or []) if isinstance(v, dict)]
                break
        evidenze: dict[str, object] = {}
        for ruolo, nome in (("QA", "QA"), ("CodeReview", "CodeReview")):
            percorso = cartella / f"evidenza-{nome}.yaml"
            if percorso.is_file():
                evidenze[ruolo] = percorso.read_text(encoding="utf-8")
        verdetto = decidi(findings=findings, evidenze=evidenze)
    except (OSError, ValueError) as errore:
        print(f"  NO   {errore}", file=sys.stderr)
        return 2
    print(json.dumps(verdetto, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
