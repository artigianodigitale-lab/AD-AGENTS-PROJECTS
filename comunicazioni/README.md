# COMUNICAZIONI — log per task

Canale condiviso dell'Agentic Agile Organization. Un file per task:
`comunicazioni/<task_id>.md`. Materializza il layer di [COMMUNICATION.md](../COMMUNICATION.md)
come artefatto leggibile da tutti, senza broadcast: si legge il file.

## Perché un file per task

`send_message` consegna a **un destinatario per volta**: far sapere qualcosa a tutti
richiederebbe N messaggi e N turni svegliati. Il log risolve il problema alla radice — chi
vuole sapere legge, chi partecipa scrive.

Un file per `task_id`, non un log unico, perché il runtime **non garantisce lock** sulle
scritture: file distinti riducono le collisioni e il task resta l'unità di lavoro di
[RUNTIME.md](../RUNTIME.md).

## Regole

- **Append-only**: si aggiungono righe in coda, non si riscrive e non si riordina il file.
- **Un file per task**: `comunicazioni/<task_id>.md`, aperto da chi avvia lo scambio (di
  norma il Lead).
- **Niente segreti**: nessuna credenziale, nessun token, nessun dato personale.
- **Il log non è autorità**: non assegna task, non crea competenze, non autorizza la
  produzione.
- **Il log non è un gate**: le evidenze di gate vivono nel formato di
  [ad-quality-gate](../.brain/skills/ad-quality-gate/SKILL.md) — `task_id`, `gate`,
  `outcome`, `producer` — e non in questo log.
- **Resta come evidenza**: a task chiuso il file resta allegato al `task_id`.

## Formato della riga

```yaml
sender:                 # id della card mittente
recipient:              # id della card destinataria, oppure "*" per il canale condiviso
task_id:                # uguale al contract
message_type:           # request | evidence | proposal | dependency | blocker | result
content:                # una o due righe, concreta
timestamp:              # ISO 8601
evidence_reference:     # path, comando o artefatto; vuoto se non serve
```

I valori ammessi per `message_type` sono quelli di [COMMUNICATION.md](../COMMUNICATION.md).

## Chi scrive cosa

| Mittente | Destinatario tipico | Quando |
|---|---|---|
| qualsiasi card | `lb-master-orchestrator` | blocco, dubbio di scope, escalation, esito |
| card esecutrice | card nominata come dipendenza nel contract | handoff tecnico tra pari |
| `lb-master-orchestrator` | un membro attivo (uno per volta) | assegnazione, sblocco, richiesta di evidenza |
| `quality-gate` | `lb-master-orchestrator` | verdetto ACCEPT o REJECT |

## Avvio rapido

```sh
cp comunicazioni/_TEMPLATE.md "comunicazioni/<TASK_ID>.md"
```

Poi si scrive solo in coda. Il template è in [_TEMPLATE.md](_TEMPLATE.md).
