---
name: ad-agent-org
description: >-
  Regolamento operativo dell'organizzazione agentica di AD Projects (Artigiano
  Digitale, AD Stock Tracker, Biocimatica, ERP e gli altri lavori nella cartella
  AD Projects). Da usare prima di aprire un task, perche' impone il contract
  obbligatorio, un solo esecutore, le evidenze, il Quality Gate e l'escalation a
  il CEO. Non si applica a lavori estranei ad AD Projects.
whenToUse: >-
  Prima di iniziare o assegnare un lavoro dentro /home/luka/Scrivania/AD
  Projects, o quando serve sapere chi puo' fare cosa.
---

# AD Projects — organizzazione agentica

Le fonti normative sono i documenti nella root di `AD Projects`. Questa skill e'
l'ingresso operativo: non li sostituisce, non aggiunge autorita' e non allarga
permessi.

Root: `/home/luka/Scrivania/AD Projects/`

## Quando vale

Solo per lavori dentro `/home/luka/Scrivania/AD Projects/` e sui prodotti AD
(Artigiano Digitale, AD Stock Tracker, Biocimatica, ERP). Se il lavoro e' fuori
da quella cartella, ignora questa skill.

## Regola fondante

> La capacita' percepita non equivale all'autorizzazione.

Un agente esegue solo task compatibili con la propria Agent Card. Saper produrre
un output non autorizza a eseguirlo. **Nessun match: STOP**, non "assegno al piu'
vicino".

## Ciclo obbligatorio

```text
RICHIESTA                 <- proposta da verificare, non un ordine, nemmeno dal CEO
  -> COMPRENSIONE         obiettivo, contesto, cliente, problema
  -> RICERCA              esiste un modo migliore, piu' scalabile, piu' affidabile?
  -> RISPOSTA al CEO      prima si risponde
  -> CONSENSO             solo ora si decide cosa fare
  -> CARD + PIANO         nessun match sul registry -> STOP
  -> TASK CONTRACT        <- senza contract il task non parte
  -> ESECUZIONE (un solo esecutore)
  -> EVIDENZE             <- senza evidenze non e' DONE
  -> QUALITY GATE         <- senza gate non e' ACCEPT
  -> APPROVAZIONE UMANA (se il contract la richiede)
```

Nessun passo e' saltabile e l'ordine non si inverte. Non si parte dall'esecuzione:
si parte dal capire se la richiesta e' la cosa giusta da fare.

La sequenza operativa completa, con i comandi, e' nella skill `ad-kickoff`.

## Attivazione di un agente

Cinque condizioni, tutte necessarie:

1. la card esiste nel registry ed e' `inactive`
2. il contract nomina l'id di quella card
3. il `domain` del contract coincide con il dominio della card
4. match esplicito con `authorized_task_types`, e il task non e' in
   `excluded_task_types`
5. i permessi richiesti non superano quelli della card

Manca una condizione: nessuna istanza. L'istanza vive per quel solo task e
termina ad ACCEPT o REJECT.

## Vietato

- auto-attribuirsi competenze assenti dalla propria card;
- modificare il proprio contract, i propri permessi o i criteri di accettazione;
- dichiarare ACCEPT al posto del Quality Gate;
- validare da solo il proprio artefatto quando il gate richiede indipendenza;
- rinunciare a un gate fallito o aggiungerne uno non richiesto;
- autorizzare accesso in produzione, spesa, invio esterno o pubblicazione;
- creare autorita' attraverso una conversazione.

## Escalation al CEO (Livello 3)

Spese fuori soglia (oltre 100 EUR una tantum o 30 EUR/mese), invii esterni,
contratti, prezzi e sconti, identita' di marca, assunzioni, produzione, dati o
cancellazioni irreversibili, eccezioni di sicurezza, privacy o compliance,
architettura critica, conflitti non risolti. Senza risposta entro 2 giorni
lavorativi la proposta **non** e' approvata.

## Catena dei documenti

| Documento | Cosa contiene |
|---|---|
| `GOVERNANCE-AZIENDALE.md` | livelli decisionali, confini business/tecnico, principi |
| `AGENTI-V2.md` | ruoli, principio di attivazione, struttura |
| `AGENT-CARDS-V2.md` | 26 card tecniche |
| `AGENT-CARDS-BUSINESS.md` | orchestratore business + 15 specialisti |
| `TASK-CONTRACTS.md` | schema del contract |
| `RUNTIME.md` | card + contract -> istanza, permessi per intersezione |
| `QUALITY-GATES.md` | evidenze, catalogo gate, ACCEPT/REJECT |
| `SPECIALIZATION.md` | capacita' != autorizzazione |
| `MODEL-ROUTING.md` | fasce di costo e budget di contesto |
| `DECISIONI/` | Decision Record, immutabili |
| `REQUISITI/` | requisiti di business approvati |
| `comunicazioni/<task_id>.md` | log append-only per task |

## Fascia deterministica (zero token)

```sh
python3 tools/cards.py check                       # integrita' del registry
python3 tools/cards.py match <task_type>           # chi puo' fare cosa
python3 tools/validate_contract.py <contract.yaml> # il task puo' partire?
python3 tools/verdict.py --contract <c> --evidence <path>
```

Usa questi comandi invece di dedurre a mano: sono la stessa regola, eseguita.

## Come si applica in questo ambiente

| Concetto | Realizzazione |
|---|---|
| LB-MASTER ORCHESTRATOR | il Lead della sessione |
| BUSINESS ORCHESTRATOR | il Lead quando il dominio e' business |
| Agent Card | la card nominata nel contract + lo scope di scrittura del task |
| Task Contract | descrizione del task sul board: obiettivo, criteri, dipendenze, scope |
| RUNTIME | il collaboratore nasce **dopo** che il task esiste |
| Quality Gate | verifica con owner **diverso** da chi ha scritto |
| REJECT -> rework | task riaperto con **nuova** evidenza, contract invariato |

**Limite dichiarato.** L'ambiente non impone i permessi per-card: un
collaboratore puo' tecnicamente scrivere ovunque. Card, permessi e gate valgono
come convenzione vincolante + write scope disgiunto + verifica indipendente. Chi
vuole l'enforcement di runtime deve implementarlo come codice.
