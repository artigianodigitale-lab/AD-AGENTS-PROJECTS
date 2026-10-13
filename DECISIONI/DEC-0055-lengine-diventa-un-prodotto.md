# DEC-0055 — L'engine diventa un prodotto

```yaml
id: DEC-0055
stato: approvato
livello: 3
data: "2026-10-13"
approver: il CEO
supera: "DEC-0040, DEC-0054 nella parte sui raggi"
```

## Problema

`AD-AGENTS-PROJECTS` era **l'installazione personale del CEO**: funzionava, ed era tarata su una
persona, un computer e una cartella.

Misurato il 2026-10-13, prima di toccare niente:

```
«il CEO» scritto 63 volte in 12 file + 18 nei comandi
26 card descritte in markdown, 0 agenti eseguibili
SearxNG su localhost:8080                      il web e' un servizio che c'e' solo la'
nessun AGENTS.md nella cartella                collegare la cartella non da' niente
nessun sede.yaml                               il CEO non esiste come dato
un progetto non numerato PASSA il cancello     buco di protezione, misurato
Root: /home/luka/Scrivania/AD Projects/        percorso assoluto nella costituzione
```

E il difetto piu' grave stava nella **prima riga** della costituzione:

> *«Questo blocco vale **solo** per lavori dentro `/home/luka/...`. **Se il lavoro non riguarda
> quella cartella, ignora tutto cio' che segue.**»*

**Un altro utente che collega la cartella altrove viene istruito a ignorare le regole.**

## Opzioni

1. **Non fare nulla.** L'engine resta personale. Conseguenza: chiunque altro colleghi la cartella
   **non ottiene niente**, e il sistema non e' pubblicabile. Fonte: la misura qui sopra.
2. **Pubblicare cosi' com'e'.** Conseguenza: chi lo prova trova «il CEO» come CEO, una cartella
   che dice di ignorare le regole, e nessun modo di partire. **Il primo utente e' anche l'ultimo.**
3. **Aggiungere un manuale di installazione.** Conseguenza: carta che invecchia. Il sistema ha
   imparato in quattro giorni che **una regola scritta non cambia il comportamento**: serve un
   controllo che fallisce, non un paragrafo in piu'.
4. **Rendere l'engine un prodotto**: il CEO diventa un **ruolo** e il nome un **dato**, la
   cartella una **porta d'ingresso**, il primo avvio una **procedura**, e i numeri una **regola
   con un controllo**. Fonte: [AGENTS.md come standard di fatto](https://agents.md) letto da DSH
   via `@deepseek-ai/dsh-agent-instructions`, che dichiara di leggere «le istruzioni di workspace
   dai file globali dell'utente e dai file **a livello di progetto**».

## Evidenze

- **`AGENTS.md` e' la porta, e funziona**: creato come collegamento alla costituzione, DSH lo
  carica da solo appena la cartella e' collegata. Provato: il sistema ha annunciato
  *«Additional instructions from: AGENTS.md — apply to work under `.`»*
- **Un progetto senza numero passava il cancello**: `ProgettoSenzaNumero` → PASSA,
  `19. ProgettoNumerato` → BLOCCATO. Ora il primo e' **BLOCCATO** e il rifiuto dice
  *«Rinominala in 18. ProgettoSenzaNumero. Il prossimo numero libero e' 18»*
- **La regola era scritta da nessuna parte**: `GOVERNANCE-AZIENDALE.md:40` diceva **cosa
  significa** avere un numero, non che un progetto **deve** averlo. Nessun comando lo pretendeva
- **63 «il CEO»** sostituiti con **il CEO** in 10 file; il nome vive in `sede.yaml`, e i comandi
  che lo mostrano lo leggono da li' (`ad_docs.ceo()`)
- **`sede.yaml`** dichiara il CEO, il nome della macchina e dove stanno i progetti

## Scelta

**Opzione 4.** Approvata dal CEO il 2026-10-13 (*«AGENTS.md è il comando — procedi pure con la
chiusura dei punti 1,2,3»*), con due decisioni sue:

- **I progetti si numerano: bloccare e spiegare** (scelta **(a)**), con il numero suggerito
- **Aggiungere la rete**: se l'engine non e' avviato, dirglielo invece di lasciarlo scoprire

**Il CEO e' un ruolo, il nome e' un dato.** `sede.yaml` lo dichiara; la costituzione, la
governance e le skill parlano al **ruolo**. E l'**ambito** non e' piu' un percorso assoluto: e'
*«la cartella che contiene questo file, dovunque sia»*.

**La porta d'ingresso** e' `AGENTS.md`, collegato alla costituzione: **una sola fonte**, letta
da DSH da sola.

**Il primo avvio** e' la skill `ad-avvio`: chiede il nome, chiede il permesso di scaricare,
installa, **prova** — e scrive `sede.yaml` solo alla fine.

**I numeri** sono una regola scritta **e** un controllo: `ad_scope.py` blocca una cartella nella
radice che non sia di macchina e non sia numerata. L'elenco delle cartelle di macchina e'
**dichiarato**, non dedotto: dedurlo accetterebbe come macchina qualunque cartella qualcuno crei.

## Conseguenze

- **Chi collega la cartella riceve le regole** senza installare niente
- **L'engine funziona ovunque sia**: la radice si scopre, le regole viaggiano con la cartella,
  e nessun percorso assoluto resta nella costituzione
- **Il primo avvio e' una procedura provata**, non un manuale
- **Un progetto senza numero e' impossibile**, non «sconsigliato»
- **Cambiare utente non richiede di riscrivere la macchina**: si cambia `sede.yaml`
- Suite: 457 controlli, e le prove dell'impalcatura **rispettano la regola che verificano**

## Limiti dichiarati

- **Il cancello non si acquisisce, si installa.** In DSH il montaggio del plugin vive nel profilo
  del programma: collegare la cartella da' **le regole**, non il cancello. Serve `setup.py`
- **Cursor riceve le regole e basta**: non esiste un gancio, e `DEC-0039` ha gia' deciso di non
  trattarlo come superficie da bloccare
- **Gli adattatori per gli altri IDE sono dichiarati, non provati**: non ho Claude Code, Codex
  ne' Antigravity su questa macchina, e **non dico che funzionino**
- **SearxNG e' infrastruttura**: chi lo installa si prende un servizio da aggiornare
- **`comportamento.py:67` legge ancora gli mtime** per un controllo d'ordine: su una copia
  direbbe il falso. Trovato misurando, **non corretto**
- **La separazione fra macchina e progetti non e' fatta**: `sede.yaml` ha il campo `progetti`,
  ma nessuno lo legge ancora. I progetti stanno ancora accanto alla macchina

## Metrica

«il CEO» nei documenti normativi e nelle skill: da **63 a 0** (restano solo nei commenti che
registrano chi ha chiesto). Cartelle di progetto non numerate accettate: da **tutte a zero**.
Passi del primo avvio: da **nessuno a sei**. Documenti con un percorso assoluto: da **2 a 0**.

## Data di revisione

2026-11-09

## Esito misurato

<Da compilare il 2026-11-09: se qualcuno che non sia il CEO attuale ha usato la macchina, se il
primo avvio ha funzionato senza spiegazioni a voce, e se `setup.py` e' bastato.>
