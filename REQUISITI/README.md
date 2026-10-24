# REQUISITI — Requisiti di Business

Requisiti di business **approvati**. Sono il ponte fra il dominio business e quello tecnico, secondo la catena fissa:

```text
Decision Record  →  Requisito di Business  →  contract tecnico
```

Fonte normativa: [GOVERNANCE-AZIENDALE.md](../GOVERNANCE-AZIENDALE.md). Meccanismo di traduzione in lavoro: [TASK-CONTRACTS.md](../TASK-CONTRACTS.md).

Un file per requisito: `REQUISITI/REQ-<numero>-<slug>.md`.

## Regole

- Senza un Decision Record approvato collegato, il requisito **non è approvato**.
- Il requisito dice **cosa, perché e per chi**. Il **come**, la fattibilità e la qualità tecnica sono del dominio tecnico.
- LB-MASTER ORCHESTRATOR traduce il requisito in uno o più contract tecnici. BUSINESS ORCHESTRATOR non scrive contract tecnici e LB-MASTER non scrive requisiti di business.
- Un requisito non assegna agenti e non autorizza produzione, spesa, invio esterno o pubblicazione.
- Le modifiche a un requisito approvato producono un **nuovo** requisito collegato, non una riscrittura di quello esistente.
- Ogni requisito dichiara i criteri di accettazione osservabili: senza di essi il contract tecnico non può chiudersi.

## Avvio rapido

```sh
cp REQUISITI/_TEMPLATE.md "REQUISITI/REQ-001-<slug>.md"
```

## Indice

Nessun requisito approvato.
