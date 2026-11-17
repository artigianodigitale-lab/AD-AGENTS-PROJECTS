# QUALITY GATES V1.2

Come QUALITY-GATE legge le evidenze già previste dal task contract e risponde ACCEPT oppure REJECT. Non aggiunge agenti e non reinterpreta il lavoro.

## Ingresso

QUALITY-GATE riceve solo:

- il task contract, intatto
- le evidenze prodotte per i `required_gates` di quel contract

Non riceve un parere libero. Non sceglie gate nuovi. Non toglie un gate richiesto. Non può rinunciare a una condizione fallita (`waive_gate: forbidden`).

## Catalogo dei gate

I gate disponibili sono: QA, Code Review, Security, Architecture, UX, Accessibility, Performance, Documentation, Strategy, Brand, Legal, GDPR, Finance, SEO e Platform. `Brand` è un gate formale: verifica coerenza con identità, tono, naming e linee guida di marca approvati. I gate business sono richiesti solo quando il contract ne dichiara l'applicabilità; non sono automatici né sostituiscono l'approvazione del CEO quando prevista.

Ogni gate deve avere una check-list versionata, un produttore di evidenza indipendente dall'esecutore quando il controllo è di validazione, e un riferimento al requisito o Decision Record applicabile. Legal, GDPR e Finance producono valutazioni operative: non sostituiscono il professionista abilitato quando il contract o la card lo richiedono.

### Owner delle evidenze

Il contract nomina un owner diverso dall'esecutore. Per impostazione predefinita: Strategy → `lb-business-coach`; Brand → `lb-brand-identity` o `lb-archetypal-branding`, mai la card che ha prodotto l'artefatto; Legal → `lb-legal` oppure un avvocato esterno quando richiesto; GDPR → `gdpr`; Finance → `lb-finance`; Code Review → `review`; QA → `qa`. Per gli altri gate si usa la card tecnica omonima. Se l'indipendenza non è possibile, il task si ferma e l'orchestratore richiede una card o un professionista indipendente.

### Avvio del Quality Gate

L'orchestratore del dominio del contract avvia QUALITY-GATE solo dopo che tutte le evidenze richieste sono state depositate: BUSINESS ORCHESTRATOR per `domain: business`, LB-MASTER per `domain: technical`. L'avvio non influenza il verdetto.

## Evidenza valida

Un'evidenza è valida solo se dice, per quel task:

- task_id uguale al contract
- gate tra quelli richiesti
- esito PASS oppure FAIL
- chi l'ha prodotta, che non è l'agente che ha prodotto l'artefatto quando il gate è di validazione
- la **dichiarazione dei side-effect** (sotto)
- etichette valide per le **affermazioni** dichiarate (sotto)

Manca uno di questi campi: l'evidenza non conta.

### Dichiarazione dei side-effect

Sei chiavi fisse, ognuna `YES`, `NO` oppure `NOT_VERIFIED`:

```yaml
side_effects:
  code: "YES"                 # ha modificato codice
  database: "NO"              # ha scritto dati persistenti
  schema: "NO"                # ha toccato schema o migrazioni
  deps: "NO"                  # ha aggiunto o aggiornato dipendenze
  env: "NO"                   # ha toccato variabili d'ambiente o segreti
  external_services: "NO"     # ha chiamato servizi esterni
```

È il complemento del `write_scope`: il `write_scope` dice **dove** si poteva scrivere, questa dichiarazione dice **cosa** si è toccato. Un task che resta nel perimetro ma semina il database o chiama un'API esterna smette di essere invisibile.

**Se non è verificabile, `NOT_VERIFIED`. Mai inventare `NO`.** Dichiarare `database: NO` quando il `write_scope` tocca dati persistenti è una contraddizione, e viene rifiutata.

**Attenzione a YAML**: `NO` senza virgolette è il booleano `False` (YAML 1.1). Il validatore lo interpreta correttamente, ma per chiarezza scrivete `"NO"`.

### Etichette delle affermazioni

Ogni affermazione portante dell'evidenza porta la sua etichetta, nel campo `claims`:

| Etichetta | Significato |
|---|---|
| `VERIFIED` | confermato dal codice, dalla configurazione o da un test **attuali** |
| `DOCUMENTED` | dichiarato da un documento, non confermato in modo indipendente |
| `INFERRED` | dedotto dall'architettura, senza prova diretta |
| `NOT_VERIFIED` | prova insufficiente |
| `NOT_AVAILABLE` | la capacità o il dato **non esiste** |
| `DOCUMENTATION_MISMATCH` | documento e realtà si contraddicono |

Differenza che conta: `NOT_AVAILABLE` = la cosa non c'è; `NOT_VERIFIED` = la cosa c'è ma non l'ho provata.

Un'etichetta fuori elenco invalida l'evidenza. **Un'affermazione senza etichetta vale `NOT_VERIFIED`, mai `VERIFIED` per default.** Un `PASS` storico in un report non è `VERIFIED`: è `DOCUMENTED`, finché non viene rieseguito.

La norma che rende utile tutto questo: **non nascondere l'incertezza.** Il valore di una verifica dipende più da un'incertezza dichiarata con onestà che da una completezza apparente.

## Verdetto

```text
per ogni gate in required_gates:
  evidenza valida PASS  → avanti
  evidenza valida FAIL  → REJECT
  evidenza assente o non valida → REJECT
tutti PASS → ACCEPT
```

ACCEPT non è il rilascio. Se il contract ha `approval.human: true`, dopo ACCEPT decide l'umano. REJECT apre un nuovo tentativo sullo stesso contract: si producono nuove evidenze senza modificare scope, agent, permessi o criteri. Un nuovo contract è ammesso soltanto se cambia scope, owner, permessi o criteri di accettazione; in tal caso non è un rework, ma una nuova assegnazione collegata al task precedente.

## Chi non decide

BUSINESS ORCHESTRATOR e LB-MASTER assegnano e non dichiarano ACCEPT. L'agente esecutore non valida da solo il proprio artefatto al posto del gate richiesto. PROGRAM-ORCHESTRATOR non emette il verdetto di un task di prodotto.
