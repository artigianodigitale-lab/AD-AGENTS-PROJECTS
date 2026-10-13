---
name: ad-task-contract
description: Scrive e valida un Task Contract per un lavoro su AD Projects. Senza contract il task non parte, senza evidenze non e' DONE, senza Quality Gate non e' ACCEPT. Usa quando devi aprire, assegnare o verificare un incarico a un agente o a un collaboratore.
whenToUse: Quando nasce un lavoro da assegnare, o quando un contract esistente va controllato prima di partire.
---

# Task Contract

Meccanismo con cui gli orchestratori assegnano lavoro
(`TASK-CONTRACTS.md`). Root: `/home/luka/Scrivania/AD Projects/`

## Regole

- Senza contract il task non parte.
- Senza evidenze non e' DONE.
- Senza Quality Gate non e' ACCEPT.
- Un agente non modifica il proprio contract, i propri permessi o i criteri di
  accettazione.
- Un agente senza task non parte.
- L'esecutore restituisce **evidenze**, non un nuovo contract.
- Un contract avvia **un solo esecutore**. Un secondo agente entra solo se e' un
  gate richiesto o una dipendenza esplicita.

## Schema

Il template canonico — completo dei campi di `TASK-CONTRACTS.md` **e** di quelli del
layer di enforcement (`status`, `write_scope`) — e' uno solo:

```sh
cp "/home/luka/Scrivania/AD Projects/contratti/_TEMPLATE.yaml" "contratti/<TASK_ID>.yaml"
```

Non esistono due template: una copia sola evita che divergano. Quello che segue e'
lo schema per riferimento:

```yaml
task_id: PROD-000
title: ""
domain: technical        # technical | business
agent: ""                # id presente nel registry del dominio
task_type: ""            # deve stare in authorized_task_types della card
product: ""              # artigiano-digitale | ad-stock-tracker | biocimatica | altro
decision_record: ""      # obbligatorio per decisioni di Livello 2 o 3

objective: >
  ...

inputs: [requirements, api_specification, architecture]

acceptance_criteria:
  - ""

constraints:
  - no production access
  - do not edit this contract
  - do not change own permissions

outputs: [code, tests, evidence]

required_gates:
  - QA

approval:
  human: false

budget:
  max_retries: 2
```

## Sequenza

**Precondizione.** Un contract si scrive **solo dopo** che la richiesta e' stata
verificata, la risposta e' stata data al CEO e lui ha dato il consenso su cosa
fare (`ad-kickoff`, passi 1-6). Scrivere un contract prima del consenso e'
un'inversione dell'ordine, non un anticipo.

1. **Obiettivo** in una frase, con esito misurabile.
2. **Ambito**: quali cartelle sono toccate.
3. **Card**: `python3 tools/cards.py match <task_type>`. Se non trova nulla,
   STOP: serve una card nuova o un Transient Worker autorizzato.
4. **Contract** compilato con il template.
5. **Validazione**: `python3 tools/validate_contract.py <file.yaml>`. Il task
   non parte con una VIOLATION.
6. **Un owner per task**, con write scope disgiunto dagli altri.
7. **Dipendenze** dichiarate prima di partire.
8. **Gate**: chi verifica e' diverso da chi scrive.

## Cosa fa fallire il contract

| VIOLATION | Perche' |
|---|---|
| `agent-unknown` | l'id non esiste nel registry |
| `agent-domain-mismatch` | un orchestratore assegna una card dell'altro dominio |
| `agent-not-assignable` | la card non dichiara `authorized_task_types` |
| `task-type-excluded` | il task e' in `excluded_task_types` |
| `task-type-no-match` | il task non e' autorizzato da quella card |
| `permission-escalation` | il contract chiede piu' permessi di quanti la card conceda |
| `gate-unknown` | il gate non e' nel catalogo di `QUALITY-GATES.md` |
| `gates-empty` | nessun gate: il lavoro non potrebbe mai essere ACCEPT |
| `gate-owner-conflict` | l'esecutore e' anche l'owner del gate che deve validarlo |
| `decision-record-missing` / `not-approved` | il record citato non esiste o non e' approvato |

## WARNING da non ignorare

- `task-type-undeclared` — senza `task_type` il match resta una dichiarazione,
  non un controllo. E' il rilievo piu' frequente e il piu' importante.
- `decision-record-absent` — se il task e' Livello 2 o 3 il record e' dovuto.
- `governance-card-producing-code` — una card di governance non sviluppa.

Con `--strict` anche gli avvisi fanno fallire il contract.

## Passaggio business -> tecnico

Il Business Orchestrator emette un **Requisito di Business** collegato a un
Decision Record (`REQUISITI/`); LB-MASTER lo traduce in uno o piu' contract
tecnici. Nessuno dei due scrive nel dominio dell'altro.
