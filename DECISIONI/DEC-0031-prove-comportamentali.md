# DEC-0031 — Le prove comportamentali

```yaml
id: DEC-0031
stato: approvato
livello: 2
data: 2026-10-10
approver: CEO
supera:
```

## Problema

Avevamo **193 controlli sui programmi** e **zero sul comportamento**. Provavamo che gli
strumenti funzionano, non che l'agente li usi bene. **Non sapevamo se stessimo migliorando o
peggiorando**: potevamo cambiare una regola e sperare.

## Cosa NON e' stato costruito, e perche'

Il `pass@k` delle fonti — «quante volte l'agente ci azzecca in k tentativi» — richiede di far
girare lo **stesso compito più volte** e contare i successi. Non abbiamo un modo affidabile di
farlo, e **fingere di averlo sarebbe peggio che non averlo**. Se lo costruiremo, sarà una tappa
a sé con il suo costo.

## Cosa e' stato costruito

**Sette asserzioni sul comportamento registrato.** Ogni permesso, firma, rapporto, Blueprint ed
errore che l'agente lascia dietro di sé è la traccia di come si è mosso: le prove leggono quella
traccia. Deterministico, costa niente, e prende le regressioni vere.

| Prova | Cosa verifica | Da dove viene |
|---|---|---|
| B1 | l'ordine firma → permesso regge | `ERR-0004` |
| B2 | nessun record dichiara un orario futuro | `ERR-0001` |
| B3 | ogni permesso chiuso ha la storia completa | `ERR-0003` |
| B4 | ogni errore registrato ha una difesa che esiste | le voci incomplete |
| B5 | la radice tiene solo i documenti normativi | invariante 15 |
| B6 | nessun Blueprint mente | `ERR-0009` |
| B7 | il registro è raggruppato per progetto | il mescolarsi |

**E la domanda giusta non è «va tutto bene?» ma «è peggiorato qualcosa?».** `evals/baseline.yaml`
è il punto di partenza; `comportamento.py check` confronta e segnala **solo** le prove che prima
passavano e ora no.

E' esattamente ciò che dice la fonte — [Google, *Anatomy of Harness Engineering*](https://developers.googleblog.com/en/the-anatomy-of-harness-engineering-how-to-evaluate-iterate-and-guard-ai-coding-agents/):

> *«Lo scopo principale di una suite di valutazione non è festeggiare quando rendi l'agente
> migliore del 2%; è darti la certezza incrollabile che una modifica […] non abbia reso l'agente
> complessivamente peggiore.»*

## Evidenze

- `tools/comportamento.py` — `check`, `show`, `--update`; la baseline in `evals/baseline.yaml`.
- Test: da **193 a 199 controlli**, incluse le prove della funzione che decide cos'è una
  regressione (pura, quindi provabile senza toccare il workspace).
- **Provato rompendo davvero**: un file estraneo nella radice → `B5 FALLITA` + `REGRESSIONE`,
  uscita 1; l'ordine firma→permesso invertito a mano → `B1 FALLITA` + `REGRESSIONE`, uscita 1;
  rimesso a posto → 7/7, nessuna regressione.
- **La regola della cartella ha una prova**: ogni asserzione deve dichiarare da dove viene.

## Conseguenze

- Il sistema ora risponde alla domanda che non sapeva porsi.
- **La disciplina di `--update` è dichiarata**: aggiornare la baseline senza guardare cosa è
  cambiato cancella la regressione. E' una firma, non un tasto.
- Le due famiglie sono ora distinte e lo dicono: **i controlli provano i programmi, le prove
  provano l'agente.**

## Limiti dichiarati

- **Misura la traccia, non l'agente in tempo reale.** Un comportamento sbagliato che non lascia
  traccia nei registri non viene visto, e nessuna prova lo prenderà mai.
- **Sette prove non sono una suite.** Sono quelle che gli errori veri hanno giustificato. La
  regola è: quando accade un errore meccanizzabile, diventano otto.
- **Nessuna prova dice perché.** Dice che qualcosa è peggiorato; il perché lo trova chi guarda.
- **Il numero dell'affidabilità resta incompleto.** Abbiamo la sorveglianza delle regressioni e
  la statistica di `errori.py` (stiamo imparando o avendo fortuna), ma **non** il `pass@k`. Chi
  dirà che «il 100% è raggiunto» dovrà dire quale dei due numeri sta guardando.

## Metrica

Regressioni rilevate su un cambiamento: atteso **zero**. E il numero da guardare nel tempo è la
coppia: **prove passate / prove totali** e **errori trovati da un controllo / errori totali**.

## Data di revisione

2026-11-09
