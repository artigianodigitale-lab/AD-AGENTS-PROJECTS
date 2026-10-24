# RUNTIME V1.2

Come una card inattiva e un task contract valido diventano un'istanza, e come l'istanza finisce. Non aggiunge agenti.

## Avvio

L'orchestratore competente avvia un'istanza solo se valgono insieme: LB-MASTER per un contract `technical`; BUSINESS ORCHESTRATOR per un contract `business`. Non possono avviare istanze nel dominio reciproco.

- la card esiste nel registry ed è inactive
- il contract nomina l'id di quella card
- il `domain` del contract coincide con il dominio della card e dell'orchestratore
- c'è match esplicito tra il task e authorized_task_types
- il task non è in excluded_task_types
- i permessi richiesti non superano la card

Manca una condizione: STOP. Nessuna istanza.

## Contesto caricato

L'istanza riceve solo:

- la propria card
- il task contract, in sola lettura
- gli input nominati dal contract
- il `learning_context` nominato dal contract, se presente
- la memoria accessibile dichiarata dalla card

Non riceve le card altrui, i contract altrui, né la memoria globale se la card non la elenca.

## Permessi

I permessi dell'istanza sono l'intersezione tra card e vincoli del contract. Il contract può togliere permessi, non aggiungerne. L'istanza non può alzare i propri permessi.

Le fonti formative caricate sono in sola lettura e non modificano i permessi, l'autonomia, i criteri di accettazione o il livello decisionale dell'istanza.

## Vita

```text
INACTIVE CARD + CONTRACT VALIDO
        ↓
      MATCH
        ↓
     ISTANZA
        ↓
     EVIDENZE
        ↓
   QUALITY GATE
        ├── REJECT → istanza terminata, card di nuovo inactive, nuovo tentativo sullo stesso contract
        └── ACCEPT → istanza terminata, card di nuovo inactive
```

L'istanza vive per quel solo task. A ACCEPT o REJECT viene terminata. Non resta in attesa del task successivo.

## Reject

REJECT non modifica il contract e non riassegna da solo. L'orchestratore del dominio può avviare una nuova istanza sullo stesso contract, entro `budget.max_retries`, per produrre nuove evidenze. Se devono cambiare scope, owner, permessi o criteri, apre una nuova assegnazione collegata al task precedente; non la chiama rework. Le evidenze di ogni tentativo restano allegate al task_id.
