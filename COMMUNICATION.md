# COMMUNICATION

Layer controllato. Non modifica autorità, card, contract, permessi o Quality Gate. Un messaggio non assegna task, non crea competenze e non autorizza produzione, spesa o azioni esterne.

```yaml
sender:
recipient:
task_id:
message_type: request | evidence | proposal | dependency | blocker | result
content:
timestamp:
evidence_reference:
```

Il runtime decide il contesto ricevuto dall'istanza. La strategic memory (`strategic_memory/`, vedi [STRATEGIC-MEMORY.md](STRATEGIC-MEMORY.md)) non è condivisa per default: il contract può nominare esclusivamente fonti pertinenti al task.
