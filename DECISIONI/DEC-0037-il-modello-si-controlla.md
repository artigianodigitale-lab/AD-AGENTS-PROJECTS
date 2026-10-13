# DEC-0037 — Il modello dei verbali si controlla

```yaml
id: DEC-0037
stato: approvato
livello: 2
data: 2026-10-10
approver: CEO
supera:
```

## Problema

Il controllo completo della super cartella ha trovato **tre registri mai usati**. Uno era
`EVOLUZIONE/`, rimosso con `DEC-0036`. Ma il CEO ha chiesto: **«quindi il registro di evoluzione
può servire?»** — e la risposta onesta ha rivelato un problema più grande.

Il registro chiedeva sette cose, tutte buone: le alternative **con la fonte**, il confronto con
il **non fare nulla**, l'esito **misurato** dopo. Cose che un verbale, di suo, non registra: un
verbale dice **cosa hai scelto**, non **cosa hai considerato e perché no**.

Misurato su **36 verbali**:

| La domanda | Quanti verbali la contengono |
|---|---|
| Le alternative scartate | **20 su 36** |
| Cosa succede se non si fa nulla | **10 su 36** |
| L'esito misurato | **3 su 36** |

**E poi la scoperta:** il modello `DECISIONI/_TEMPLATE.md` **chiedeva già tutte e tre**. Sezioni
«Opzioni» con dentro «Non fare nulla», «Metrica», «Data di revisione».

**Il modello non era sbagliato. Sono io che non l'ho seguito** — ho scritto sezioni mie, ogni
volta diverse («La domanda», «La diagnosi era sbagliata», «La prescrizione, dalla fonte»).
Un modello che nessuno verifica è un buon proposito, e i buoni propositi non cambiano il
comportamento.

## Opzioni

1. **Resuscitare `EVOLUZIONE/` con un controllo** — il registro torna, con `tools/evoluzione.py`
   a verificarne le sette sezioni. Costo: 250 righe già scritte e poi cancellate, più un secondo
   registro da tenere vivo accanto a `piani/`, che fa la stessa cosa. Rischio: **resta vuoto una
   seconda volta**, perché chiede sette sezioni per una decisione che in chat prende trenta
   secondi — fonte: è esattamente quello che è successo in quattro occasioni su quattro.
2. **Mettere le tre domande nel modello del verbale, e controllarle** — nessun registro nuovo, e
   `tools/verbali.py` verifica che il modello sia seguito. Costo: **cinque righe nel modello più
   un controllo**. Rischio: il controllo vale solo per i verbali **nuovi**, perché i 36 vecchi
   sono immutabili — fonte: [hexisteme, *Your Report's Numbers Are Computed. Its Sentences Are
   Not.*, 8 ago 2026](https://hexisteme.github.io/notes/your-reports-numbers-are-computed-its-sentences-are-not.html),
   che documenta la stessa disciplina: *«un controllo che non hai mai visto fallire non è un
   controllo»*.
3. **Non fare nulla** — i verbali restano come sono. Le alternative scartate si perdono nel 44%
   dei casi, il confronto con il non fare nulla nel 72%, **l'esito misurato nel 92%**. Il costo
   non è immediato: è che fra sei mesi nessuno saprà **se una decisione ha funzionato**, e le
   stesse idee torneranno perché nessuno ricorda di averle già scartate.

## Evidenze

- **20/36, 10/36, 3/36** — misurato con `grep` sui 36 verbali il 2026-10-10
- `DECISIONI/_TEMPLATE.md` conteneva già «Opzioni» con «Non fare nulla», «Metrica» e «Data di
  revisione»: **il modello era giusto**
- `DEC-0035` come esempio del problema: le sue sezioni sono «La domanda», «La diagnosi era
  sbagliata», «Misurato», «La prescrizione, dalla fonte», «Scelta», «Evidenze», «Una cosa che ho
  scoperto provando», «Conseguenze», «Limiti dichiarati», «Metrica», «Data di revisione» —
  **tre sezioni del modello su otto**
- `EVO-001`, la proposta scritta col modello di `EVOLUZIONE/`: **ha prodotto la ricerca
  accademica e la scoperta che l'articolo non fa quello che ci serve**. La forma ha migliorato il
  lavoro — una volta su una, e solo perché l'ho compilata io su richiesta

## Scelta

**Opzione 2.** Le tre domande entrano nel modello del verbale, e si controllano.

- **`## Esito misurato`** aggiunta al modello: era l'unica delle tre che mancava davvero
- **«Opzioni»** ora chiede esplicitamente **la fonte** e il **non fare nulla**
- **`tools/verbali.py`**: verifica campi, sezioni, fonti nelle opzioni, presenza del non fare
  nulla, e che a revisione passata l'esito ci sia
- **`EVOLUZIONE/` resta rimosso.** Il contenuto serviva, il posto no: `piani/` fa già quel
  lavoro, e due registri per la stessa cosa ne lasciano uno vuoto — è successo

**I 36 verbali vecchi sono esenti**, e il perché è scritto nel codice: sono record a mano libera,
**immutabili**, e riscriverli per farli entrare in una regola nata dopo sarebbe falsificare la
storia. Se dichiarano una revisione passata senza esito, il controllo li **mostra** senza
contarli come errori.

## Conseguenze

- **Un registro in meno**, non uno in più: `EVOLUZIONE/` rimosso, nessun sostituto.
- **Un comando in più**: `tools/verbali.py` (15 comandi).
- **Il modello ora si applica davvero**, perché qualcuno lo controlla.
- **I verbali futuri dovranno citare una fonte**: una decisione senza fonti verificabili diventa
  un errore, non un'omissione.
- `DEC-0037` è **il primo verbale scritto seguendo il modello**, e lo dichiara il codice.

## Metrica

Verbali che contengono le tre domande: oggi **20/36, 10/36, 3/36**; atteso **tre su tre** dal
`DEC-0037` in poi. Verbali fuori modello: atteso **zero**.

## Data di revisione

2026-11-09

## Esito misurato

<Da compilare il 2026-11-09: quanti verbali nuovi hanno le tre domande, e se il controllo ha
preso qualcosa.>
