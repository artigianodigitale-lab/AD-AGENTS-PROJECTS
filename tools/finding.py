#!/usr/bin/env python3
"""Il modello dei finding: una severita' non si dichiara, si giustifica.

Perche' esiste (`DEC-0106`, Fase 2 di `piani/2026-11-02-review-governance-v2.md` §3).

Un **finding** non e' un verdetto: e' un fatto documentato. Il verdetto lo produce il
Decision Engine applicando la politica. Ma perche' una politica lo possa applicare, il
fatto deve avere una forma — e senza forma non e' un fatto, e' un'opinione con la data
sopra.

Il problema che questo risolve, misurato su `ENG-020`: sette revisioni, e ogni volta il
revisore scriveva un finding in prosa. Il verdetto era PASS o FAIL, e il difetto trovato
finiva in un paragrafo — dove nessuno poteva contarlo, confrontarlo o verificare se era
ancora aperto. Un criterio scritto come requisito e' stato declassato a finding P2 e il
gate e' stato chiuso lo stesso (`ERR-0091`): quel declassamento non si vedeva, perche' un
finding senza forma non si puo' contare.

## Le severita' (specifica §3.1)

    P0 CRITICAL  compromissione, perdita di dati, controllo non autorizzato, scrittura fuori
                 perimetro -> REJECT immediato, nessun waiver
    P1 HIGH      violazione di un requisito fondamentale -> REJECT, nessun waiver ordinario
    P2 MEDIUM    difetto reale, impatto limitato, c'e' un workaround -> BACKLOG o escalation
    P3 LOW       cosmetica, stile, messaggi, refactoring -> BACKLOG

## I campi, e cosa deve dire ognuno (specifica §3.3)

    finding_id             F-001
    reviewer               CODE_REVIEW | QA | SECURITY
    commit_sha             lo snapshot congelato
    category               SECURITY | CORRECTNESS | ARCHITECTURE | UX | DOCS | PERFORMANCE
    severity               P0 | P1 | P2 | P3
    title                  una riga
    evidence               il file con la riproduzione, eseguibile da chiunque
    reproducible           true | false — se false, il finding NON e' classificabile
    impact                 l'effetto concreto, non «potrebbe essere un problema»
    trigger                la condizione o la probabilita' di attivazione
    surface                dati | autorizzazione | rete | filesystem | stato
    compensating_controls  cosa rende il difetto non sfruttabile OGGI
    recommendation         il rimedio proposto
    disposition            proposta del revisore — il Decision Engine la conferma o la corregge

**Un finding senza questi campi non e' classificabile**, e un finding non classificabile e'
`NOT_VERIFIED`: non blocca, ma **non chiude nemmeno**. Va risolto o escalato. E' la
differenza fra «non ho trovato niente» e «non ho guardato».

Uso:
    python3 tools/finding.py check <file.yaml>   # 0 validi, 1 almeno uno rifiutato, 2 illeggibile
    python3 tools/finding.py elenco              # i campi obbligatori, e cosa devono dire
    python3 tools/finding.py esempio             # un finding valido, da copiare
"""

from __future__ import annotations

import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]

#: Le severita' ammesse. Un valore fuori elenco non e' «quasi giusto»: e' un errore, perche'
#: il Decision Engine decide su questi valori e non su una scala continua.
SEVERITA = ("P0", "P1", "P2", "P3")

#: Chi puo' produrre un finding. Le stesse tre famiglie di verifica.
REVISORI = ("CODE_REVIEW", "QA", "SECURITY")

#: Le categorie della specifica §3.3. Servono a raggruppare i finding per tipo di
#: problema, che e' l'unico modo per dire «questo progetto ha un problema ricorrente di
#: correttezza» invece di «questo progetto ha dodici finding».
CATEGORIE = ("SECURITY", "CORRECTNESS", "ARCHITECTURE", "UX", "DOCS", "PERFORMANCE")

#: Cosa propone il revisore. Non e' la decisione: e' l'intenzione, che il Decision Engine
#: conferma o corregge. `NOT_VERIFIED` non e' una proposta: e' uno stato, e lo assegna il
#: validatore quando il finding non e' classificabile.
DISPOSIZIONI = (
    "BLOCKING",
    "BACKLOG",
    "DEFERRED",
    "ACCEPTED_RISK",
    "REMEDIATED",
    "NOT_VERIFIED",
)

#: I campi obbligatori, con cosa deve dire ognuno. L'ordine e' quello della specifica.
CAMPI: tuple[tuple[str, str], ...] = (
    ("finding_id", "un identificatore stabile, per esempio F-001"),
    ("reviewer", "chi lo ha prodotto: " + " | ".join(REVISORI)),
    ("commit_sha", "lo snapshot congelato su cui e' stato trovato"),
    ("category", "il tipo di problema: " + " | ".join(CATEGORIE)),
    ("severity", "quanto e' grave: " + " | ".join(SEVERITA)),
    (
        "evidence",
        "il file con la riproduzione, eseguibile da chiunque — senza, non e' un fatto "
        "documentato ma un'opinione",
    ),
    ("reproducible", "true | false — se false il finding non e' classificabile"),
    ("impact", "l'effetto concreto, non «potrebbe essere un problema»"),
    ("trigger", "la condizione o la probabilita' di attivazione"),
    ("surface", "cosa e' toccato: dati, autorizzazione, rete, filesystem, stato"),
    ("compensating_controls", "cosa rende il difetto non sfruttabile oggi, o «nessuno»"),
    ("recommendation", "il rimedio proposto, il piu' stretto che risolve"),
    ("disposition", "cosa propone il revisore: " + " | ".join(DISPOSIZIONI)),
)

#: I campi il cui valore deve venire da un elenco chiuso.
A_ELENCO: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("reviewer", REVISORI),
    ("category", CATEGORIE),
    ("severity", SEVERITA),
    ("disposition", DISPOSIZIONI),
)


class FindingRifiutato(Exception):
    """Il finding non ha la forma che la specifica richiede."""


def _testo(dato: object) -> str:
    """Un valore come testo, senza spazi attorno. Vuoto se non e' un valore utile."""
    if dato is None:
        return ""
    if isinstance(dato, bool):
        return "true" if dato else "false"
    return str(dato).strip()


def valida(voce: object, indice: int = 0) -> list[str]:
    """I motivi per cui una voce non e' un finding valido. Vuoto = valido.

    Non si ferma al primo errore: chi legge vuole sapere **tutto** quello che manca, non
    ricominciare da capo a ogni correzione. Ma i motivi sono ordinati, e il primo e'
    sempre il piu' importante.
    """
    dove = f"finding #{indice + 1}"
    if not isinstance(voce, dict):
        return [f"{dove}: non e' una mappatura"]
    problemi: list[str] = []

    # `reproducible` decide **quali campi servono**, quindi si legge prima degli altri.
    # Se e' `false` il finding non e' classificabile: e' `NOT_VERIFIED`, e un
    # `NOT_VERIFIED` non porta una severita' — la specifica §3.1 lo dice esplicito, e
    # pretendere una severita' da un finding non riproducibile sarebbe chiedere di
    # dichiarare quanto e' grave una cosa che non si e' vista succedere.
    riproducibile = voce.get("reproducible")
    non_verificato = riproducibile is False

    for campo, cosa in CAMPI:
        if campo == "severity" and non_verificato:
            continue  # non classificabile: la severita' non ci va
        if campo not in voce or _testo(voce.get(campo)) == "":
            problemi.append(f"{dove}: manca «{campo}» — {cosa}")

    for campo, ammessi in A_ELENCO:
        valore = _testo(voce.get(campo))
        if valore and valore not in ammessi:
            problemi.append(
                f"{dove}: «{campo}» vale {valore!r}, non e' fra i valori ammessi "
                f"({', '.join(ammessi)})"
            )

    # `reproducible` non e' un campo come gli altri: e' cio' che distingue un fatto da
    # un sospetto.
    if non_verificato:
        if _testo(voce.get("severity")):
            problemi.append(
                f"{dove}: `reproducible: false` ma dichiara `severity: "
                f"{_testo(voce.get('severity'))}` — un finding non riproducibile non e' "
                "classificabile: non blocca, ma non chiude. Togliere la severita' o "
                "fornire una riproduzione"
            )
        if _testo(voce.get("disposition")) not in ("", "NOT_VERIFIED"):
            problemi.append(
                f"{dove}: `reproducible: false` e `disposition: "
                f"{_testo(voce.get('disposition'))}` — un finding non riproducibile "
                "puo' solo essere NOT_VERIFIED"
            )
    elif not isinstance(riproducibile, bool):
        if "reproducible" in voce and _testo(riproducibile) not in ("true", "false"):
            problemi.append(
                f"{dove}: «reproducible» deve essere `true` o `false`, non "
                f"{riproducibile!r}"
            )

    return problemi


def valida_file(percorso: Path) -> tuple[list[str], int]:
    """Valida un file: una mappatura (un finding) o una lista di finding.

    Restituisce i problemi e **quanti finding validi** contiene. Un file vuoto non e'
    un file valido: un'evidenza senza finding non prova che non ce ne siano.
    """
    try:
        grezzo = percorso.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as errore:
        raise FindingRifiutato(f"non si legge: {errore.__class__.__name__}") from errore
    if not grezzo.strip():
        raise FindingRifiutato("il file e' vuoto")
    import yaml

    try:
        dati = yaml.safe_load(grezzo)
    except yaml.YAMLError as errore:
        raise FindingRifiutato(f"non e' YAML valido: {errore}") from errore

    if isinstance(dati, dict) and "findings" in dati:
        dati = dati.get("findings")
    voci = dati if isinstance(dati, list) else [dati]
    if not voci:
        raise FindingRifiutato("non contiene nessun finding")

    problemi: list[str] = []
    validi = 0
    for indice, voce in enumerate(voci):
        esiti = valida(voce, indice)
        if esiti:
            problemi.extend(esiti)
        else:
            validi += 1
    return problemi, validi


def elenco() -> str:
    """I campi obbligatori, con cosa deve dire ognuno."""
    righe = ["I campi di un finding, e cosa deve dire ognuno:", ""]
    for campo, cosa in CAMPI:
        righe.append(f"  {campo:24} {cosa}")
    righe.append("")
    righe.append("La severita': " + " · ".join(SEVERITA))
    righe.append("Le categorie: " + " · ".join(CATEGORIE))
    righe.append("Le disposizioni: " + " · ".join(DISPOSIZIONI))
    righe.append("")
    righe.append("Un finding senza `evidence` non e' un fatto documentato: e' un'opinione.")
    return "\n".join(righe)


def esempio() -> str:
    """Un finding valido, da copiare."""
    return """finding_id: F-001
reviewer: CODE_REVIEW
commit_sha: abc1234
category: SECURITY
severity: P1
title: "Scrittura fuori dalla cartella del progetto"
evidence: "evidenze/F-001.log"
reproducible: true
impact: "Un percorso con symlink fa scrivere il banco fuori dal progetto"
trigger: "Il campo foto contiene un collegamento che esce dalla cartella"
surface: "filesystem"
compensating_controls: "nessuno"
recommendation: "Verificare il percorso risolto, non quello dichiarato"
disposition: BLOCKING
"""


def main(argv: list[str] | None = None) -> int:
    argomenti = argv if argv is not None else sys.argv[1:]
    comando = argomenti[0] if argomenti else "elenco"
    if comando == "elenco":
        print(elenco())
        return 0
    if comando == "esempio":
        sys.stdout.write(esempio())
        return 0
    if comando != "check":
        print("uso: python3 tools/finding.py [check <file.yaml> | elenco | esempio]", file=sys.stderr)
        return 2
    if len(argomenti) < 2:
        print("serve il file da controllare", file=sys.stderr)
        return 2
    percorso = Path(argomenti[1])
    try:
        problemi, validi = valida_file(percorso)
    except FindingRifiutato as errore:
        print(f"  NO   {percorso}: {errore}", file=sys.stderr)
        return 2
    if problemi:
        for problema in problemi:
            print(f"  NO   {problema}", file=sys.stderr)
        print(f"finding rifiutati: {len(problemi)} problemi, {validi} validi")
        return 1
    print(f"  ok   {validi} finding validi in {percorso.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
