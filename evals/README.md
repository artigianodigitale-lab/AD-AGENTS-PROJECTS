# EVALS — le prove comportamentali

Qui vive la **baseline** delle prove che verificano come si comporta l'agente, non come
funzionano i programmi.

## Perché servono

Avevamo **193 controlli sui programmi** e **zero sul comportamento**: provavamo che gli
strumenti funzionano, non che l'agente li usi bene.

Il [team di Google lo chiama *harness engineering*](https://developers.googleblog.com/en/the-anatomy-of-harness-engineering-how-to-evaluate-iterate-and-guard-ai-coding-agents/), e dice la cosa che conta:

> *«Lo scopo principale di una suite di valutazione non è festeggiare quando rendi l'agente
> migliore del 2%; è darti la certezza incrollabile che una modifica al prompt, allo schema di
> uno strumento o un aggiornamento del modello **non abbia reso l'agente complessivamente
> peggiore**.»*

Ecco cosa fa questa cartella: **risponde a una domanda sola — è peggiorato qualcosa?**

## Cosa misura, e cosa NON misura

**Non è il `pass@k`.** Quello — «quante volte ci azzecca in k tentativi» — richiede di far
girare lo **stesso compito più volte** e contare i successi. Non abbiamo modo di farlo in modo
onesto. Fingere di averlo sarebbe peggio che non averlo.

**Misura il comportamento registrato.** Ogni permesso, firma, rapporto ed errore che l'agente
lascia dietro di sé è la traccia di come si è mosso. Le prove leggono quella traccia: è
deterministico, costa niente, e prende le regressioni vere.

## La regola di questa cartella

**Ogni prova esiste perché un errore vero è accaduto.** Se una prova non nasce da una voce di
`errori/`, non ha ragione di stare qui — e va cancellata.

| Prova | Cosa verifica | Nasce da |
|---|---|---|
| **B1** | l'ordine firma → permesso regge | `ERR-0004` |
| **B2** | nessun record dichiara un orario futuro | `ERR-0001` |
| **B3** | ogni permesso chiuso ha la storia completa | `ERR-0003` |
| **B4** | ogni errore registrato ha una difesa che esiste | le voci incomplete |
| **B5** | la radice tiene solo i documenti normativi | l'invariante 15 |
| **B6** | nessun Blueprint mente | `ERR-0009` |
| **B7** | il registro è raggruppato per progetto | il mescolarsi |

## La disciplina della baseline

`baseline.yaml` è il **punto di partenza**: quali prove passavano quando è stata fissata.

```sh
python3 tools/comportamento.py check            # e' peggiorato qualcosa?
python3 tools/comportamento.py check --update   # accetta lo stato attuale
python3 tools/comportamento.py show             # solo l'esito
```

**Aggiornare la baseline senza guardare cosa è cambiato cancella la regressione.** È l'unico
modo di rendere inutile questa cartella: `--update` è una firma, non un tasto.

## Il limite, detto

- **Misura la traccia, non l'agente in tempo reale.** Un comportamento sbagliato che non lascia
  traccia nei registri non viene visto — e nessuna prova lo prenderà mai.
- **Nessuna prova dice perché.** Dice che qualcosa è peggiorato. Il perché lo trova chi guarda.
- **Sette prove non sono una suite.** Sono quelle che gli errori veri hanno giustificato. Quando
  ne accadrà un altro meccanizzabile, diventeranno otto.
