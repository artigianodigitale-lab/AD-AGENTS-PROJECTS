---
name: ad-agent-cards
description: Consulta il registry delle Agent Card di AD Projects e decide quale card copre un task. 26 card tecniche in AGENT-CARDS-V2.md e 16 card business in AGENT-CARDS-BUSINESS.md. Usa quando devi assegnare un lavoro, verificare chi puo' fare cosa, o quando nessuna card sembra coprire il task.
whenToUse: Quando serve l'id di una card, i suoi task autorizzati, i suoi permessi o le sue esclusioni.
---

# Registry delle Agent Card

Root: `/home/luka/Scrivania/AD Projects/`

Due cataloghi, un solo registry:

| File | Contenuto | Formato |
|---|---|---|
| `AGENT-CARDS-V2.md` | 26 card tecniche | un blocco YAML per card |
| `AGENT-CARDS-BUSINESS.md` | orchestratore + 15 specialisti | YAML la governance, **tabella** gli specialisti |

## Non dedurre: interroga

```sh
python3 tools/cards.py check                      # integrita' e lacune
python3 tools/cards.py list                       # tutte le card
python3 tools/cards.py list --domain business      # solo un dominio
python3 tools/cards.py show backend                # una card completa
python3 tools/cards.py match api_implementation    # chi autorizza questo task
```

`match` esce 1 quando non trova nulla: e' il caso STOP.

## Campi che contano per l'assegnazione

- `authorized_task_types` — il match esplicito. **Senza questo campo la card non
  e' assegnabile.**
- `excluded_task_types` — il task qui dentro non si assegna mai.
- `permissions` — `none` < `read` < `write`. Il contract puo' togliere, non
  aggiungere.
- `status` — deve essere `inactive` perche' parta un'istanza.
- `escalation` — quando la card deve fermarsi e salire di livello.

## Struttura del registry

**Governance (3)** — `lb-master-orchestrator`, `program-orchestrator`,
`quality-gate`. Decompongono, coordinano e verificano; non sviluppano.

**Squadra di prodotto (8)** — `product-owner`, `business-analyst`, `architect`,
`frontend`, `backend`, `review`, `qa`, `devops`.

**Squadre a chiamata (6)** — `security`, `integration`, `data-ai`, `ux`,
`platform`, `release`.

**Specialisti (9)** — `technical-writer`, `accessibility`, `performance`, `seo`,
`gdpr`, `migration`, `localization`, `database`, `finance`.

**Business (16)** — `lb-business-orchestrator` piu' 15 specialisti
(`lb-strategy`, `lb-marketing`, `lb-sales`, `lb-legal`, `lb-operations`,
`lb-fundraising`, `lb-people`, `lb-brand-identity`, `lb-archetypal-branding`,
`lb-personas`, `lb-customer-success`, `lb-business-coach`, `lb-finance`).

## Stato del catalogo

Tutte le **42 card sono assegnabili** (DEC-0006). Le 16 card business dichiarano
ora `capabilities`, `authorized_task_types` ed `excluded_task_types`, derivati
dalla missione e dalle esclusioni che il catalogo gia' riportava in prosa: nessuna
competenza nuova, solo la forma che rende possibile il match esplicito.

`cards.py check` lo verifica e resta a zero problemi bloccanti. Le uniche note di
completezza riguardano il campo `mission`, che `AGENTI-V2.md` pretende su ogni
card e che le 26 card tecniche non dichiarano: e' un drift tra documenti, non
un'autorizzazione mancante, e non blocca l'assegnazione.

Per il dominio business, un task si assegna cosi':

```sh
python3 tools/cards.py match pricing_analysis    # -> lb-sales
python3 tools/cards.py show lb-finance           # unit economics, business case
```

I due domini non condividono nessun task type: un task business non puo' finire
su una card tecnica, e viceversa.

## Quando nessuna card copre il task

1. Fermati: non assegnare alla card piu' vicina.
2. Dichiaralo all'utente con l'elenco dei `match` tentati.
3. La via d'uscita e' una card nuova o un Transient Worker, autorizzato da
   BUSINESS ORCHESTRATOR per il business e da LB-MASTER per il tecnico, con
   scope, tool, permessi e definition of done propri.
