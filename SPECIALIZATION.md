# SPECIALIZATION

Regola stabile. Non aggiunge agenti.

La capacità percepita non equivale all'autorizzazione.

Un agente può eseguire esclusivamente task compatibili con la propria Agent Card. La capacità di produrre un output non è autorizzazione a eseguire il task. Se nessuna Agent Card autorizzata copre il task, l'orchestratore competente sospende l'assegnazione e richiede una nuova Agent Card oppure un Transient Worker esplicitamente autorizzato: BUSINESS ORCHESTRATOR per il dominio business, LB-MASTER per quello tecnico. L'agente non può auto-attribuirsi una competenza assente dalla propria card.

Nessun agente può accettare un task sulla base della propria capacità percepita. Può eseguire esclusivamente task autorizzati dalla propria Agent Card e compatibili con il Task Contract.

Il Transient Worker non nasce per coprire un buco al volo. Sequenza: necessità specialistica, nessuna card adeguata, richiesta, autorizzazione, poi un worker con scope, tool, permessi e definition of done.

Il registry non elenca solo il nome. Per ogni agente dichiara capability, authorized_task_types, excluded_task_types e permissions. L'orchestratore competente assegna solo su match esplicito. Nessun match: stop, non improvvisazione.
