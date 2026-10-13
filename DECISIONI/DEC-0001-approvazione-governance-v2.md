# DEC-0001 — Approvazione di GOVERNANCE AZIENDALE V2.0

```yaml
id: DEC-0001
stato: approvato
livello: 3
data: 2026-10-08
approver: CEO
supera:
```

## Problema

`GOVERNANCE-AZIENDALE.md` è la fonte normativa dell'organizzazione agentica — livelli decisionali, confini fra dominio business e tecnico, catalogo dei gate, formazione — ma è rimasta in stato di *proposta operativa da approvare*. Finché resta una bozza:

1. nessuna decisione di Livello 2 o 3 può appoggiarsi a essa senza contestarla;
2. nessun layer di istruzioni sempre attivo può normarla, perché congelerebbe una bozza;
3. la catena `GOVERNANCE → AGENT CARDS → TASK CONTRACTS → RUNTIME → QUALITY GATES` non ha una base approvata.

La decisione non è rinviabile perché il passo successivo — rendere la catena sempre attiva su ogni lavoro e ogni chat — richiede che la fonte sia approvata.

## Opzioni

1. **Approvare V2.0 così com'è** — costo zero, sblocca la catena; il documento resta modificabile solo con un nuovo Decision Record.
2. **Approvare con modifiche** — richiede di concordare prima quali clausole cambiare; rinvia il resto.
3. **Mantenere lo stato di bozza** — nessun layer sempre attivo può citarla come norma; la governance continua a non essere vincolante.
4. **Non fare nulla** — la catena documentale resta priva di una base approvata e ogni lavoro futuro eredita l'ambiguità.

## Evidenze

- `GOVERNANCE-AZIENDALE.md`, intestazione: *"Stato: proposta operativa da approvare dal CEO,"* (stato precedente a questo record).
- Conferma esplicita del CEO, in sessione: la governance si considera approvata (2026-10-08).
- Coerenza interna verificata: i 12 documenti della root si incatenano senza contraddizioni bloccanti; due difetti trovati e corretti in questa stessa data (vedi Conseguenze).
- `tests/test_strategic_memory.py`: guard-rail di integrità della catena documentale, reso eseguibile e verde in questa data.

## Scelta

**Opzione 1 — approvare GOVERNANCE AZIENDALE V2.0.** Nessuna clausola è stata modificata nel merito: l'unica modifica all'intestazione è la sostituzione dello stato di bozza con lo stato approvato e il rimando a questo record.

## Conseguenze

- `GOVERNANCE-AZIENDALE.md` diventa vincolante e citabile da qualunque card, contract o layer di istruzioni.
- Ogni modifica successiva alla governance richiede un **nuovo** Decision Record (sezione Revisione).
- Difetto corretto: il catalogo dei gate in `GOVERNANCE-AZIENDALE.md` elencava 14 gate e ometteva **Code Review**, presente in `QUALITY-GATES.md`. Il catalogo canonico è ora dichiarato esplicitamente in `QUALITY-GATES.md`.
- Difetto corretto: `MODEL-ROUTING.md` indicava come implementazione VS Code con Continue, ambiente non in uso. La sezione è ora allineata alle superfici reali (Cursor e DeepSeek Harness) e dichiara che il layer sempre attivo deve restare minimo.
- Restano aperti, non coperti da questo record: `RELEASE.md` mancante come ultimo nodo della catena; `AGENT-CARDS-BUSINESS.md` che espone i 13 specialisti come tabella Markdown invece che come card machine-readable, con i campi comuni ereditati non espansi.

## Metrica

Numero di lavori avviati senza un task contract conforme alla governance. Atteso: zero. La metrica si misura ogni 30 giorni nella revisione del CEO insieme a tempi di decisione, escalation, reject/rework e accuratezza delle stime.

## Data di revisione

2026-11-07
