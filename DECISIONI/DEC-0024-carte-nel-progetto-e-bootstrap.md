# DEC-0024 — Le carte nel progetto, il cane che si morde la coda, il revisore indipendente

```yaml
id: DEC-0024
stato: approvato
livello: 2
data: 2026-10-08
approver: CEO
supera:
```

## Problema

Quattro cose, emerse dal primo lavoro vero su un progetto (`17. Michele Clementi Project`) e dalla
revisione del CEO.

**1. Il cane che si morde la coda (`DRIFT-010`).** La regola dice: non si lavora in un progetto
senza il passo aperto. Ma il foglio del passo va **scritto**, e scriverlo richiede un contract.
Se il contract pretendesse il passo gia' aperto, il primo contract di un progetto non potrebbe
mai essere valido: non si partirebbe mai.

**2. Il revisore indipendente.** L'agente si e' dato **REJECT** perche' era solo e la regola
dice che chi scrive non verifica il proprio lavoro. Ha fatto la cosa giusta — ma il sistema non
gli offriva nessun modo di soddisfare la regola.

**3. Le carte sparse (`DRIFT-012`).** Lavorando, l'agente ha creato piani, requisiti, evidenze e
analisi nella **root** di AD Projects. Il CEO ha dovuto spostarle a mano dentro il progetto, in una
cartella chiamata `Analisi-Prompt-Report`.

**4. La regola che ne deriva.** «Tutte le cartelle e i file che crei devono andare a finire
dentro al progetto di cui stiamo parlando.»

## Scelte

**Le carte stanno nel progetto (invariante 15).** Analisi, requisiti, tappe, passi e rapporti
vivono in `<progetto>/Analisi-Prompt-Report/`. `milestone.py` ora **crea le tappe li' dentro**.
I progetti aperti prima continuano a funzionare: la lettura sceglie la posizione dove le tappe
sono davvero.

Restano nella root — e non sono carte di progetto — i 12 documenti normativi, `DECISIONI/`,
`EVOLUZIONE/`, `drift/`, i modelli di `milestone/` e il **registro delle autorizzazioni**
(`contratti/`, `approvazioni/`). Il motivo e' pratico: e' cio' che il controllore legge **a ogni
scrittura**. Sparpagliarlo dentro i progetti significherebbe, per ogni controllo, cercare in
tutti i progetti.

**Il confine e' dove si scrive, non l'esistenza del contract (`DRIFT-010`).** Finche' il passo
dichiarato non e' aperto, il contract copre **soltanto la cartella di quel passo**: il foglio che
lo apre e il suo rapporto. Fuori di li' serve il passo aperto. E il validatore ora **avvisa**
invece di rifiutare: rifiutare significava bocciare il contract che serve ad aprire il passo.

**Il revisore indipendente esiste (invariante 4, esteso).** Quando l'esecutore e' solo, il gate
si affida a un **subagente con contesto separato**, che non ha scritto l'artefatto. Se non e'
possibile, il verdetto resta REJECT e il lavoro resta aperto. E' la differenza fra un controllo e
una firma su sé stessi.

## Conseguenze

- Il primo passo di un progetto si puo' aprire: la contraddizione e' rimossa, e il confine e'
  dove deve stare — sulla scrittura.
- La root non si riempie piu' delle carte dei progetti: ognuna nel suo progetto, in una cartella
  sola.
- Un agente che lavora da solo **puo' comunque chiudere il gate**, delegandolo a un revisore
  indipendente. Prima poteva solo fermarsi.
- La suite passa da 166 a **170 controlli**, con quattro asserzioni nuove sul bootstrap del passo.
- `coherence.py` e' stato corretto: verificava l'esistenza di `Analisi-Prompt-Report/` **nella
  root**, mentre quella cartella vive dentro i progetti. Ora controlla solo le cartelle della
  mappa della root.
- `DRIFT-010` e `DRIFT-012` chiusi.
- **Limite dichiarato**: un subagente e' indipendente nel contesto e nell'interesse, **non nel
  modello**. Se sbaglia nello stesso modo, il gate non se ne accorge. Non e' un revisore umano, e
  non va raccontato come tale.
- **Limite dichiarato**: il progetto `17. Michele Clementi Project` ha ancora le tappe nella
  posizione vecchia (radice del progetto). Spostarle e' un'operazione sul progetto e richiede un
  contract: **non e' stata fatta**, ed e' registrata.

## Metrica

Cartelle di progetto nella root di AD Projects: atteso zero. E gate chiusi da un revisore
indipendente sul totale dei gate: oggi zero su due — i due di Michele Clementi sono aperti con
REJECT, ed e' corretto che lo siano.

## Data di revisione

2026-11-07
