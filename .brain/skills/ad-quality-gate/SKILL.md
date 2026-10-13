---
name: ad-quality-gate
description: >-
  Legge le evidenze di un task di AD Projects e risponde ACCEPT o REJECT. Un
  gate richiesto senza evidenza valida e' REJECT, e chi ha prodotto l'artefatto
  non puo' validare il proprio gate. Usa quando un lavoro va verificato prima di
  considerarlo chiuso.
whenToUse: >-
  Quando un task ha prodotto artefatti e servono le evidenze dei gate richiesti
  dal contract, oppure quando bisogna capire perche' un lavoro non e' ACCEPT.
---

# Quality Gate

Root: `/home/luka/Scrivania/AD Projects/`

Il Quality Gate **non sviluppa** e **non reinterpreta** il lavoro. Riceve il
contract intatto e le evidenze dei `required_gates`, e risponde solo ACCEPT o
REJECT. Non aggiunge gate, non ne toglie, non deroga
(`QUALITY-GATES.md`).

## Evidenza valida

Un'evidenza vale **solo** se dichiara, per quel task:

- `task_id` uguale al contract;
- `gate` tra quelli richiesti;
- esito `PASS` oppure `FAIL`;
- chi l'ha prodotta, **diverso** dall'agente che ha prodotto l'artefatto.

Manca un campo: l'evidenza non conta.

Formato del contenitore (non specificato dai documenti, fissato da `tools/`):

```yaml
task_id: BIO-142
gate: QA
outcome: PASS
producer: qa
timestamp: 2026-10-08T07:20:00+02:00   # opzionale, decide nel rework
references:
  - artefatti/report.txt
```

## Verdetto

```text
per ogni gate in required_gates:
  evidenza valida PASS  -> avanti
  evidenza valida FAIL  -> REJECT
  evidenza assente      -> REJECT
tutti PASS -> ACCEPT
```

ACCEPT **non e' il rilascio**. Se il contract ha `approval.human: true`, dopo
ACCEPT decide l'umano.

## Comando

```sh
python3 tools/verdict.py --contract <contract.yaml> --evidence <file-o-cartella> [altri...]
python3 tools/verdict.py --contract <c> --evidence <dir> --json
```

Esce 0 su ACCEPT e 1 su REJECT: e' utilizzabile come gate di pipeline.

## Owner di default delle evidenze

Il contract nomina un owner diverso dall'esecutore. Se l'indipendenza non e'
possibile, il task **si ferma** e l'orchestratore richiede una card o un
professionista indipendente.

| Gate | Owner di default |
|---|---|
| QA | `qa` |
| Code Review | `review` |
| Security | `security` |
| Architecture | `architect` |
| UX | `ux` |
| Accessibility | `accessibility` |
| Performance | `performance` |
| Documentation | `technical-writer` |
| Strategy | `lb-business-coach` |
| Brand | `lb-brand-identity` o `lb-archetypal-branding` |
| Legal | `lb-legal`, o un avvocato esterno quando richiesto |
| GDPR | `gdpr` |
| Finance | `lb-finance` |
| SEO | `seo` |
| Platform | `platform` |

## Chi non decide

Business Orchestrator e LB-MASTER assegnano e **non** dichiarano ACCEPT.
L'esecutore non valida da solo il proprio artefatto. Program Orchestrator non
emette il verdetto di un task di prodotto.

## Dopo il verdetto

- **REJECT** apre un nuovo tentativo sullo **stesso** contract: si producono
  nuove evidenze senza modificare scope, agente, permessi o criteri, entro
  `budget.max_retries`.
- Dopo due REJECT locali il task si ferma e si escala con le evidenze: non entra
  in un loop di prompt.
- Serve cambiare scope, owner, permessi o criteri? Non e' un rework: e' una
  **nuova assegnazione** collegata al task precedente.
- Le evidenze di ogni tentativo restano allegate al `task_id`.
