# DEC-0056 — L'avvio dichiara e chiede, non cerca

```yaml
id: DEC-0056
stato: approvato
livello: 3
data: "2026-10-13"
approver: il CEO
supera: "DEC-0055 nella parte sull'avvio"
```

## Problema

Con `DEC-0055` l'engine era diventato portabile, ma **l'avvio era sbagliato**: leggendo
`AGENTS.md`, un agente tende a **cercare un progetto** — guarda le cartelle numerate, ne
sceglie una, e comincia. E' l'istinto giusto per un programma, ed e' sbagliato per AAP.

Il CEO l'ha detto in una riga: *«all'avvio del comando AGENTS.md l'AI non deve cercare il
progetto, deve rispondere che ha capito come si comportera' e che ha implementato AAP come
comportamento d'ora in avanti e deve chiedere subito all'utente se vuole iniziare un nuovo
progetto oppure collegare un progetto esistente»*.

**Il primo passo di AAP non e' un lavoro: e' una risposta.**

## Opzioni

1. **Non fare nulla.** L'agente cerca un progetto e ne apre uno. Conseguenza: **l'utente
   perde il controllo del primo passo**, e un agente che «comincia» su un progetto scelto da
   lui e' esattamente cio' che l'invariante 5 vieta — *la capacita' percepita non e'
   autorizzazione*. Fonte: la costituzione, invariante 5.
2. **Chiedere solo «cosa vuoi fare?».** Conseguenza: l'utente non sa **cosa sta attivando**.
   Ha collegato una cartella e riceve una domanda, senza sapere quali regole sono entrate in
   vigore. E' il difetto di `ERR-0014`: rispondere senza far capire.
3. **Dichiarare, adottare, e chiedere.** Tre parti in ordine: *cosa farai e cosa non farai*,
   *«da adesso lavoro cosi'»*, e *«nuovo o esistente?»*. Fonte: la
   [specifica di `AGENTS.md`](https://agents.md), che DSH legge come istruzioni di progetto;
   e la pratica dei programmi che chiedono **una conferma esplicita** prima di prendere il
   controllo.
4. **Far scegliere il progetto all'agente e farlo approvare.** Conseguenza: un passo in piu'
   per niente — l'agente **non sa** quale progetto vuole l'utente, e proporne uno consuma un
   giro di conversazione per arrivare alla stessa domanda.

## Evidenze

- **Il primo passo era ambiguo**: la costituzione diceva *«fermati e dillo all'utente»* solo
  **quando `sede.yaml` mancava**. Con `sede.yaml` presente, il blocco non scattava e l'agente
  proseguiva — verso un progetto.
- **La skill `ad-avvio` era «primo avvio»**, non «avvio»: il suo `whenToUse` diceva *«quando
  `sede.yaml` non c'e'»* e *«se c'e', si va da `ad-kickoff`»* — cioe' **diritto a un
  progetto**, saltando la domanda.
- **L'import di una cartella non numerata e' rifiutato dal cancello** con il numero suggerito:
  verificato il 2026-10-13, `ProgettoSenzaNumero` → BLOCCATO, *«Rinominala in 18.»*

## Scelta

**Opzione 3.** Approvata dal CEO il 2026-10-13.

**Le tre parti dell'avvio, in ordine:**

1. **Di' di aver capito come ti comporterai** — cosa farai e cosa non farai, in parole
   comprensibili. Non un riassunto del file.
2. **Dichiara che AAP e' il tuo comportamento da quel momento** — non un'opzione fra tante.
3. **Chiedi subito**: progetto **nuovo** (cartella numerata) o **esistente** (importare una
   cartella numerata col nome del progetto).

**E due divieti espliciti**: non cercare un progetto, non aprirne uno di iniziativa.

**Se l'engine non e' avviato**, prima delle due strade servono nome e permessi — e
`setup.py` deve **provare** di aver funzionato.

**L'import ha una regola in piu'**: la cartella deve essere **numerata**. Spostarla e'
irreversibile, quindi si dice cosa si sta per fare e **dove**, e si aspetta un si' esplicito
(`ERR-0024`).

## Conseguenze

- **L'utente comanda il primo passo**, e sa cosa ha attivato prima di chiederlo
- **La skill `ad-avvio` si usa a ogni avvio**, non solo al primo: `sede.yaml` che c'e' cambia
  i primi passi, non l'avvio
- **L'ingresso e' scritto in due posti e dicono la stessa cosa**: il blocco in cima alla
  costituzione, e la skill. La costituzione e' cio' che l'agente legge **sempre**; la skill e'
  la procedura
- Suite: 457 controlli

## Limiti dichiarati

- **Creare e importare non hanno ancora un comando.** Oggi si fa a mano: si trova il numero
  con `ad_scope.primo_numero_libero()`, si crea la cartella. **Un comando `progetto.py` con
  `nuovo` e `collega` sarebbe la cosa giusta**, e non l'ho fatto
- **L'import non e' provato su un caso vero**: nessuna cartella e' stata spostata per
  verificarlo, e non ho voluto spostarne una senza il consenso del CEO
- **`ad-kickoff` non e' stato adeguato**: parla ancora di «crearne uno nuovo» senza il
  passaggio dal numero. Va allineato, ed e' fuori da questo raggio solo per la regola dei file

## Metrica

L'avvio che cerca un progetto: da **possibile a vietato**, in due posti. Le strade offerte
all'utente: **due**, dichiarate. Le prove che l'installazione ha funzionato: **una scrittura
rifiutata**, non una dichiarazione.

## Data di revisione

2026-11-09

## Esito misurato

<Da compilare il 2026-11-09: se un utente nuovo ha capito cosa stava attivando senza
spiegazioni a voce, e se l'import di una cartella esistente ha funzionato al primo colpo.>
