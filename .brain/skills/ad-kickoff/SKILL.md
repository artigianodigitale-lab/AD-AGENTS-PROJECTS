---
name: ad-kickoff
description: >-
  Porta d'ingresso del cervello di AD Projects. Quando l'utente chiede di
  lavorare su un progetto esistente o di crearne uno nuovo, costruisce il piano
  di lavoro, lo sottopone al CEO e solo dopo l'approvazione apre i task contract
  che sbloccano le scritture. Primo passo di ogni richiesta su un progetto.
whenToUse: >-
  All'apertura di una richiesta che nomina un progetto di AD Projects o chiede
  di crearne uno nuovo.
---

> **Prima di tutto: il progetto ha un numero?** Se non ce l'ha, non si apre
> niente: si usa `python3 tools/progetto.py nuovo "<nome>"` (o `collega` per una
> cartella esistente). Il numero e' **cio' che dice al sistema che quella cartella e'
> un prodotto**: senza, passa il cancello e nessuno se ne accorge. Vedi `ad-avvio`.

# Kickoff di un progetto

Root: `/home/luka/Scrivania/AD Projects/`
Cervello: `.brain/` (costituzione, skill, plugin). Documenti normativi: root.

## La regola che comanda tutto

> Un progetto non viene toccato se non e' chiamato.

"Chiamato" significa: esiste un **task contract** in `contratti/` che copre il
percorso. Finche' non esiste, il plugin di enforcement `ad-enforce-contract`
**blocca** ogni scrittura dentro le cartelle prodotto, e anche i comandi shell
che le modificano. Non e' un ostacolo da aggirare: e' il meccanismo che
garantisce la regola.

Quindi: **prima il piano, poi il CEO, poi il contract, poi il lavoro.**

## Sequenza

```text
1 RICHIESTA        la richiesta del CEO e' una proposta da verificare, non un ordine
2 COMPRENSIONE     cosa vuole ottenere davvero, oltre le parole usate
3 RICERCA          esiste un modo migliore, piu' scalabile, piu' affidabile? (anche online)
4 CARD             python3 tools/cards.py match <task_type>
                   nessun match -> STOP: serve una card nuova
5 RISPOSTA         si risponde al CEO PRIMA di fare
6 ANALISI DI AVVIO cosa serve, per intero, per arrivare a prodotto finito.
                   Il risultato si scrive in piani/ e DIVENTA la milestone.
7 CONSENSO         il CEO approva le MILESTONE, non "il lavoro". Il marcatore va in
                   approvazioni/<task_id>.yaml — senza, il contract non copre nulla
8 PERMESSO         contratti/<task_id>.yaml con write_scope, milestone e sprint
                   dichiarati. SI SCRIVE **PRIMA** DELLA TAPPA: contratti/ e' libero
                   apposta, e il permesso copre la cartella della tappa **finche' il
                   passo non e' aperto**. Al contrario il cancello BLOCCA.
9 MILESTONE        l'analisi si struttura in milestone con i suoi sprint:
                   python3 tools/milestone.py new-milestone "<progetto>" --goal "..."
10 SPRINT          si apre lo sprint 1:
                   python3 tools/milestone.py new-sprint "<progetto>" 1 --objective "..."
11 ESECUZIONE      un solo esecutore -> evidenze -> Quality Gate ->
                   Milestone N/Sprint M/REPORT.md
12 CHIUSURA        ACCEPT / REJECT. Lo sprint successivo riparte dal passo 10, e solo
                   a report dello sprint precedente chiuso
```

Nessun passo si salta e l'ordine non si inverte: **ricerca, risposta, analisi, milestone,
consenso, poi il lavoro**. Senza risposta non c'e' proposta; senza milestone non c'e' niente
da approvare; senza marcatore il contract non copre; senza sprint aperto il validatore
**rifiuta** il contract.

**Il consenso del CEO e' sulle milestone.** Anche quando dice «procedi», la prima cosa che si
apre e' uno sprint — non un cantiere. Analizzare un progetto significa **leggerlo**, e questo
non richiede autorizzazione: cio' che diventa impossibile senza milestone e' **scriverci**.

## Passi 1-3 — richiesta, comprensione, ricerca

**La richiesta non e' un ordine.** Vale anche quando arriva dal CEO, ed e' il punto
piu' facile da sbagliare: la tentazione e' eseguire subito.

1. **Riformula l'obiettivo**, non le parole. "Crea un progetto per X" puo' voler
   dire "risolvi il problema Y": sono due lavori diversi.
2. **Chiediti se al mondo esiste un modo migliore, piu' scalabile e piu'
   affidabile** di ottenere lo stesso risultato. Le tre dimensioni sono
   cumulative: piu' veloce ma meno affidabile non e' migliore.
3. **Cerca davvero**, dentro e fuori. Il protocollo e' in `ad-evolution`.

Se trovi di meglio, non e' un'insubordinazione: e' il tuo lavoro. Se non trovi di
meglio, dillo esplicitamente — un silenzio non e' una verifica.

## Passi 5-6 — risposta e consenso

**Prima si risponde, poi si decide.** La risposta al CEO sta in chat e contiene
quattro cose, in quest'ordine:

```text
COSA HAI CHIESTO      la richiesta, riformulata
COSA HO TROVATO       l'esito della ricerca, con le fonti
COSA CONSIGLIO        la raccomandazione, che puo' differire dalla richiesta
COSA SERVE DA TE      il consenso richiesto, in una domanda secca
```

Poi **ci si ferma**. Solo con il consenso si passa al piano operativo e al
contract.

Tre esiti sono legittimi, e tutti e tre si argomentano:

| Esito | Quando |
|---|---|
| **la richiesta va bene cosi'** | la ricerca non trova di meglio |
| **conviene cambiarla** | esiste un modo migliore, piu' scalabile o piu' affidabile |
| **conviene non farla** | il costo supera il beneficio, o il problema si risolve altrove |

Silenzio, ambiguita' o "vediamo" non sono consensi. Senza risposta entro 2 giorni
lavorativi la proposta non e' approvata.

## Classificazione del progetto

**Progetto esistente:** una cartella numerata nella root.

```sh
ls -d "/home/luka/Scrivania/AD Projects/"[0-9]*/
```

**Progetto nuovo:** si sceglie il prossimo numero libero e un nome breve. La
cartella non si crea subito: si dichiara nel piano, e si crea dopo
l'approvazione, dentro il `write_scope` del contract.

**Dominio:** business (cosa, perche', per chi) o tecnico (come, fattibilita',
qualita'). Nel dubbio si parte dal business.

## Passo 4 — la card

```sh
python3 tools/cards.py match api_implementation
python3 tools/cards.py show backend
python3 tools/cards.py check          # lacune note del catalogo
```

Se nessuna card copre il task: **STOP**. Si chiede una card nuova o un Transient
Worker autorizzato. Non si assegna alla card piu' vicina.

Tutte le **42 card sono assegnabili**, tecniche e business (DEC-0006). Per il
business si interroga il registry come per il resto:

```sh
python3 tools/cards.py match unit_economics    # -> lb-finance
python3 tools/cards.py match icp               # -> lb-personas
```

Gli owner dei gate business — Strategy, Brand, Legal, Finance — sono card
assegnabili, quindi un artefatto business puo' passare i propri gate.

## Passo 6 — il consenso

Il piano si presenta al CEO in chat, in forma breve: obiettivo, ambito, card,
gate, decisioni richieste, rischi. Poi **ci si ferma**.

Si procede solo con un'approvazione esplicita. Silenzio, ambiguita' o "vediamo"
non sono approvazioni. Senza risposta entro 2 giorni lavorativi la proposta non
e' approvata.

Se la decisione e' di Livello 2 o 3, l'approvazione si registra in `DECISIONI/`
con un Decision Record, che il contract poi cita in `decision_record`.

## Passo 7 — il piano

Copia `piani/_TEMPLATE.md` e compila. Il piano dice almeno:

- obiettivo in una frase con esito misurabile;
- progetto e ambito: quali cartelle e quali file;
- card coinvolte, con l'id esatto;
- contract da aprire, con `write_scope` per ciascuno;
- gate richiesti e chi verifica, **diverso da chi scrive**;
- decisioni che spettano al CEO e livello (2 o 3);
- rischi, dipendenze, ordine dei passi;
- fascia di costo e modello previsti (`MODEL-ROUTING.md`);
- cosa non e' incluso.

## Passo 8 — l'analisi di avvio

Prima di compilare si scova **tutto** cio' che serve per rendere il progetto un
prodotto finito e ufficiale. Non e' una stima: e' un inventario.

- cosa deve esistere perche' il prodotto sia completo — funzioni, contenuti, dati, integrazioni;
- cosa serve per renderlo **ufficiale** — dominio, hosting, ambienti, privacy, cookie, termini, fatturazione;
- cosa manca oggi e da dove si parte;
- rischi noti e dipendenze esterne;
- cosa **non** fara' parte del prodotto, detto esplicitamente.

Senza inventario le milestone sono wishful thinking.

## Passo 9 — milestone e sprint

Dall'inventario si pianificano le milestone necessarie ad arrivare a prodotto finito,
e per la prima gli sprint. Poi si apre la prima milestone.

```sh
python3 tools/milestone.py new-milestone "<progetto>" --goal "..."
python3 tools/milestone.py new-sprint "<progetto>" 1 --objective "..."
python3 tools/milestone.py check "<progetto>"
```

La procedura completa e' in `ad-milestone`. Due cose non si negoziano: il **prompt
dello sprint si scrive prima** di eseguirlo, e il **report si rilascia alla chiusura**
con cosa e' stato fatto e come. Senza report lo sprint non e' chiuso e il successivo
non parte.

## Passo 10 — i contract

Solo dopo l'approvazione:

```sh
cp contratti/_TEMPLATE.yaml "contratti/<TASK_ID>.yaml"
python3 tools/validate_contract.py "contratti/<TASK_ID>.yaml"
python3 tools/contract_scope.py check "<percorso che si vuole scrivere>"
```

I campi che contano: `task_id`, `agent`, `status: active`, `write_scope` che
include i percorsi del piano. `status` diverso da `active`/`attivo`/`approvato`
non copre nulla.

`write_scope` e' il confine reale del lavoro: tutto cio' che sta fuori viene
bloccato dal plugin, non solo sconsigliato.

## Passi 11-12 — sprint, esecuzione e chiusura

- Un contract avvia **un solo esecutore**. Un secondo agente entra solo se e' un
  gate richiesto o una dipendenza esplicita.
- L'esecutore produce l'artefatto e le **evidenze**, non un nuovo contract.
- Verdetto: `python3 tools/verdict.py --contract <c> --evidence <path>`
- **REJECT** apre un nuovo tentativo sullo stesso contract, entro
  `budget.max_retries`. Dopo due REJECT locali si escala, non si insiste.
- **ACCEPT** non e' il rilascio: se il contract ha `approval.human`, decide il CEO.

## Quando il plugin blocca

Il messaggio di blocco e' il promemoria del passo mancante, non un guasto. Se
compare, significa una di queste cose:

| Messaggio | Cosa manca |
|---|---|
| nessun contract copre il percorso | il passo 7, oppure il `write_scope` e' troppo stretto |
| il comando modifica una cartella prodotto | il comando va limitato al `write_scope`, o serve un contract |
| la verifica non e' disponibile | `tools/contract_scope.py` non risponde: si controlla a mano e si segnala |

Non si aggira il blocco con un altro strumento. Se il blocco e' sbagliato, si
corregge il contract o il plugin, e lo si dice.
