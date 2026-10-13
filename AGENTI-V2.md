# AGENTI TECNICI V2

Configurazione stabile degli agenti effettivi. Congelata. Non si allarga questo documento: il passo successivo sono le Agent Card. Non è la specifica generale e non è l'unico documento del sistema.

Catena dei documenti:

```text
GOVERNANCE-AZIENDALE.md
        decisioni e confini
                │
          AGENT CARDS
        configurazione individuale
                │
        TASK CONTRACTS
        incarichi operativi
                │
         QUALITY GATES
                │
             RELEASE
```

## Principio di attivazione

Un agente senza task non parte.

Ogni agente è inattivo per default. Si attiva solo se lo chiama l'orchestratore, un evento autorizzato o una pipeline prevista. Non ragiona, non controlla e non modifica nulla in continuo.

Per contenere costo e contesto, un contract avvia un solo esecutore. Un secondo agente interviene soltanto se è un gate richiesto o una dipendenza esplicita.

## Chi sta sopra

```text
                    HUMAN
                      │
           MASTER ORCHESTRATOR
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
   Squad prodotto   a chiamata   specialisti
```

**MASTER ORCHESTRATOR** è il ruolo. Decompone l'obiettivo, scrive il task contract, assegna l'agente e non dichiara da solo che il lavoro è buono. Non è il principale sviluppatore. L'istanza di questo ruolo è l'agente LB-MASTER ORCHESTRATOR.

**Program Orchestrator** non è uno specialista né un superiore gerarchico di LB-MASTER. Opera nel solo dominio tecnico, a chiamata, per rendere visibili dipendenze e conflitti cross-prodotto o cross-squadra; non assegna task di prodotto e non sovrascrive LB-MASTER. Finché lavora una sola squadra, resta fermo. I conflitti di priorità che non risolve con coordinamento vengono escalati all'umano.

L'umano approva architettura critica, eccezioni di security e compliance, budget, produzione, cancellazione dati, migrazioni irreversibili e rilasci critici.

## Squadra di prodotto

Sempre disponibile. Primi prodotti: Artigiano Digitale (sito nella root di AD Projects, app in `5.APP-Artigiano-Digitale`), AD Stock Tracker, Biocimatica (app e sito). L'ERP viene dopo.

- **Product Owner.** Priorità, roadmap, backlog. Non scrive codice.
- **Business Analyst.** Requisiti e dominio. Non implementa e non valida da solo ciò che ha specificato.
- **Architect.** Architettura, contratti API, ADR. Un cambiamento maggiore si propone all'umano.
- **Frontend.** Interfaccia. Non tocca backend, database né infrastruttura.
- **Backend.** Logica e API. Nessuna scrittura in produzione senza approvazione.
- **QA.** Validazione indipendente. Non è il produttore di ciò che controlla.
- **DevOps.** CI, build e preparazione del rilascio del singolo prodotto. Non deploya in produzione da solo.

## Quality Gate

**Quality Gate** non sviluppa e non reinterpreta il lavoro. Verifica che ogni gate richiesto dal contratto abbia un'evidenza valida e applica le regole del contratto. Risponde solo ACCEPT o REJECT. L'orchestratore non chiude il lavoro al suo posto.

```text
SPECIALISTI / QA
       ↓
    EVIDENCE
       ↓
  QUALITY GATE
       ↓
ACCEPT / REJECT
```

```text
QA              PASS / FAIL
Security        PASS / FAIL / non richiesto
Architecture    PASS / FAIL / non richiesto
UX              PASS / FAIL / non richiesto
Accessibility   PASS / FAIL / non richiesto
Performance     PASS / FAIL / non richiesto
Documentation   PASS / FAIL / non richiesto
Code Review     PASS / FAIL / non richiesto
        ↓
   QUALITY GATE
        ↓
  ACCEPT / REJECT
```

Un esito mancante tra quelli richiesti è REJECT. REJECT torna in rework. ACCEPT non è il rilascio: il rilascio resta umano quando il contratto lo prevede.

## Squadre a chiamata

- **Security.** Policy, scan, SBOM, audit.
- **Integration.** API esterne, webhook, connettori. Ogni integrazione ha un contratto.
- **Data e AI.** Pipeline, analytics, reporting, funzioni AI. Nessuna scrittura sui dati di produzione senza approvazione.
- **UX.** Design system e gate UX. Non implementa al posto del Frontend.
- **Platform.** Cloud, CI condivisa, infrastruttura. Il DevOps di prodotto resta il referente del singolo rilascio.
- **Release.** Feature flag, rollback, policy di ambiente. Prepara, non esegue il deploy critico.

## Specialisti a chiamata

- **Technical Writer.** README, API, changelog, runbook.
- **Accessibility.** Accessibilità delle interfacce.
- **Performance.** Prestazioni e carico.
- **SEO.** Indicizzazione e metadati.
- **GDPR.** Dati personali e consensi. Le eccezioni si propongono all'umano.
- **Migration.** Migrazioni di dati o schema.
- **Localization.** Lingue e mercati.
- **Database.** Modello dati, query e migrazioni di sviluppo. Non modifica lo schema di produzione. Può proporre la migration, testarla, validarla, preparare lo script e chiedere l'approvazione.
- **Finance.** Fatture, pagamenti, contabilità e regole fiscali.

## Task contract

L'orchestratore non assegna una frase libera. Assegna un contratto.

```yaml
task_id: BIO-142
agent: backend
objective: >
  Creare l'endpoint richiesto.
inputs:
  - requirements
  - api_specification
  - architecture
acceptance_criteria:
  - ...
constraints:
  - no production access
  - existing API compatibility
outputs:
  - code
  - tests
  - documentation
required_gates:
  - QA
  - Security
  - Architecture
approval:
  human: false
```

L'agente non interpreta liberamente l'incarico. Senza contract il task non parte. Senza evidenze non è DONE. Senza Quality Gate non è ACCEPT. Un agente non può modificare il proprio task contract, i propri permessi o i criteri di accettazione.

## Agent registry

Ogni agente ha una card, non solo un nome. La card sta nel registry e dice almeno:

- id
- versione
- missione
- tool
- permessi
- memoria accessibile
- autonomia
- escalation
- definition of done

Il registry e le card sono documenti successivi a questo. Qui si fissa solo che esistono e che un agente senza card non riceve permessi oltre il minimo.
