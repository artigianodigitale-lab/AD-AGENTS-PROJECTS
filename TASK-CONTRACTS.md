# TASK CONTRACTS V1.2

Meccanismo con cui gli orchestratori assegnano lavoro alle card autorizzate. Il dominio tecnico resta in capo a LB-MASTER; il dominio business resta in capo a BUSINESS ORCHESTRATOR. Nessun orchestratore assegna card dell'altro dominio.

## Regole

- Senza contract il task non parte.
- Senza evidenze non è DONE.
- Senza Quality Gate non è ACCEPT.
- Un agente non può modificare il proprio task contract, i propri permessi o i criteri di accettazione.
- Un agente senza task non parte.

## Schema

```yaml
task_id: PROD-000
title: ""
domain: ""         # technical | business
agent: ""          # id presente nel registry del dominio
product: ""        # artigiano-digitale | ad-stock-tracker | biocimatica | altro
decision_record: "" # obbligatorio per decisioni di Livello 2 o 3

objective: >

inputs:
  - requirements
  - api_specification
  - architecture

acceptance_criteria:
  - ""

constraints:
  - no production access
  - do not edit this contract
  - do not change own permissions

outputs:
  - code
  - tests
  - evidence

required_gates:
  - QA

learning_context:
  sources: []       # fonti/modelli verificabili pertinenti al task
  applicability: "" # perché sono pertinenti e quali limiti hanno
  decision_rule: "evidence_over_authority"

approval:
  human: false

budget:
  max_retries: 2

priority: P2

impact_forecast:
  data: NONE
  schema: NONE
  auth: NONE
  security: NONE
  shared_platform: NONE
  product: LOW

# Obbligatori quando write_scope tocca una cartella prodotto (invariante 13).
# Lo sprint deve essere APERTO: Milestone N/Sprint M/PROMPT.md deve esistere.
milestone: 1
sprint: 1
```

### Milestone e sprint sono obbligatori per i contract di progetto

Se `write_scope` include un percorso dentro una cartella prodotto — `3. AD-Marketing-Factory/`, `11. Modelbel/` — allora `milestone` e `sprint` sono **obbligatori**, e il `PROMPT.md` di quello sprint **deve esistere**.

Non è una formalità: è il percorso che non si può imboccare al contrario. Non si apre un contract su un progetto senza aver scritto il prompt dello sprint, e non si scrive il prompt senza aver creato la milestone, perché `tools/milestone.py` rifiuta di aprire uno sprint in una milestone inesistente.

```sh
python3 tools/milestone.py new-milestone "<progetto>" --goal "..."
python3 tools/milestone.py new-sprint "<progetto>" 1 --objective "..."
python3 tools/milestone.py check "<progetto>"
```

Il consenso del CEO è sulle **milestone**, non «sul lavoro»: la sequenza è ricerca → risposta → analisi di avvio → milestone → consenso → sprint → contract.

Vale anche per le sanatorie di un solo file: entrano nella storia del progetto come sprint, invece di restare interventi isolati.

Per `domain: technical`, `agent` può essere solo: lb-master-orchestrator, program-orchestrator, product-owner, business-analyst, architect, frontend, backend, qa, devops, quality-gate, oppure una card tecnica autorizzata dal registry.

Per `domain: business`, `agent` può essere solo: lb-business-orchestrator oppure una card business presente nel relativo registry e con match esplicito. Un contract business non concede accesso a repository, produzione o dati non previsti dalla card.

`required_gates` elenca solo i controlli che questo task richiede. Il Quality Gate non ne aggiunge e non ne toglie. Un gate richiesto senza evidenza è REJECT.

### Priorità

`priority` è `P0`, `P1`, `P2`, `P3` o `P4`. **Se la modifica tocca più livelli vale il massimo**: una UI che forza un KPI a `0` invece di `N/A` è `P0`, non una rifinitura. Un impatto `HIGH` nella previsione impone `P0`, e il validatore lo controlla.

### Previsione di impatto

`impact_forecast` è il **dovere di previsione prima del diff**: cosa può rompersi, su ciascuna area — `data`, `schema`, `auth`, `security`, `shared_platform`, `product` — con livello `NONE`, `LOW`, `MED`, `HIGH` o `UNKNOWN`.

`UNKNOWN` è ammesso e onesto: dichiarare di non sapere è meglio che dichiarare `NONE` senza aver guardato. Prevedere l'impatto **dopo** il diff non è previsione.

## Chi scrive cosa

LB-MASTER ORCHESTRATOR scrive e assegna solo contract `technical`. BUSINESS ORCHESTRATOR scrive e assegna solo contract `business`. Per il passaggio business → tecnico, il Business Orchestrator emette un Requisito di Business collegato a un Decision Record; LB-MASTER lo traduce in uno o più contract tecnici. L'agente esecutore restituisce evidenze, non un nuovo contract. Quando tutte le evidenze richieste sono depositate, l'orchestratore del dominio avvia QUALITY-GATE; QUALITY-GATE legge contract ed evidenze e risponde ACCEPT o REJECT. PROGRAM-ORCHESTRATOR non scrive contract di un singolo prodotto.

## Esempio

```yaml
task_id: BIO-142
title: Endpoint di lettura
domain: technical
agent: backend
product: biocimatica

objective: >
  Esporre l'endpoint descritto nel contratto API, senza cambiare lo schema di produzione.

inputs:
  - requirements
  - api_specification
  - architecture

acceptance_criteria:
  - endpoint disponibile nel percorso concordato
  - validazione degli input
  - test automatizzati presenti

constraints:
  - no production access
  - existing API compatibility
  - do not edit this contract

outputs:
  - code
  - tests
  - evidence

required_gates:
  - QA
  - Architecture

approval:
  human: false

budget:
  max_retries: 2
```

## Specializzazione

La capacità percepita non equivale all'autorizzazione.

Un agente esegue solo task compatibili con la propria Agent Card. Se nessuna card autorizzata copre il task, l'orchestratore competente sospende l'assegnazione e chiede una nuova card o un Transient Worker autorizzato: BUSINESS ORCHESTRATOR per `business`, LB-MASTER per `technical`. Non assegna il task all'agente più vicino. L'agente non può auto-attribuirsi una competenza assente dalla card.

Un Transient Worker non è una scappatoia: nasce solo dopo richiesta di specializzazione e autorizzazione, con scope, tool, permessi e definition of done propri.

## Formazione e modelli di riferimento

Ogni card deve avere una base formativa documentata, aggiornata e pertinente al proprio ruolo. Un modello, un autore o un libro è una fonte di lavoro, non un'autorità che sostituisce dati, legge, sicurezza, contratti o Quality Gate. Per i task non banali il contract dichiara le fonti o i modelli usati, perché sono adatti al caso e i loro limiti. In caso di conflitto prevalgono evidenze attuali, requisiti approvati e vincoli di compliance.

Controllo:

```text
TASK
  ↓
REQUISITI
  ↓
AGENT REGISTRY
  ↓
MATCH ESPLICITO
  ├── MATCH → assegna
  └── NO MATCH → STOP → nuova specializzazione
```
