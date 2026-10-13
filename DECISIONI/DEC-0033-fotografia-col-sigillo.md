# DEC-0033 — La fotografia col sigillo

```yaml
id: DEC-0033
stato: approvato
livello: 2
data: 2026-10-10
approver: CEO
supera: DEC-0030 nella parte sul controllo
```

## Problema

In `DEC-0030` avevo dichiarato un limite che non sapevo risolvere:

> *«Il controllo la segnala, ma non distingue una fotografia vecchia da una manomissione: dal
> file, le due cose sono identiche.»*

E c'era un secondo problema, pratico: **rigenerare richiede un permesso sul progetto**, quindi un
verbale della società poteva lasciare vecchi i Blueprint di più progetti. L'avevo scritto senza
avere una soluzione.

## La proposta del CEO

> *«Siccome ad ogni modifica di codice cambierebbe, non si potrebbe creare un primo Blueprint del
> progetto completo e poi aggiornarlo a ogni Milestone?»*

**Due cose giuste, e una correzione:**

1. **Il Blueprint non cambia a ogni modifica di codice.** Legge i registri — tappe, permessi,
   prove, discrepanze, verbali — e nessuno di questi è codice. Cambia quando si chiude un passo.
2. **Ma la soluzione è quella.** Scattarlo **alla chiusura della tappa** è il momento in cui i
   registri si muovono **e** in cui chi chiude ha già il permesso in mano. Niente cerimonia in più.
3. **E serve un pezzo in più** per togliere il limite di `DEC-0030`: l'**impronta**.

## Scelta

Il Blueprint diventa una **fotografia sigillata**:

```text
> **Fotografia dei registri, scattata alla chiusura della tappa 2.** impronta: `5facda3b8954`
```

E il controllo distingue **quattro** cose, dove prima ne distingueva una:

| Esito | Cosa significa | Errore? |
|---|---|---|
| **aggiornato** | la fotografia è dei registri di adesso | no |
| **indietro** | fotografia **autentica** di registri più vecchi. Fra una tappa e l'altra è normale | no |
| **manomesso** | il contenuto non corrisponde alla propria impronta | **sì** |
| **senza-impronta** | il blocco non comincia col sigillo: versione vecchia, o qualcuno ci ha scritto sopra | **sì** |

## Il pezzo che fa funzionare tutto, e che avevo sbagliato

**L'impronta è un sigillo sul contenuto, non un puntatore ai registri.**

Ci avevo provato con un puntatore: `genera(impronta=dichiarata)` per ricostruire cosa il
generatore avrebbe prodotto dai registri di allora. **Non funziona**: per ricostruirlo servono i
registri di allora, che non abbiamo più.

Un **sigillo** invece si verifica **sempre**: basta confrontare il contenuto con la sua stessa
impronta. Se non corrispondono, qualcuno l'ha cambiato — e questo si sa **anche se i registri nel
frattempo si sono mossi**.

## Un buco trovato scrivendo le prove

La prima versione chiamava «indietro» (non un errore) un blocco che non cominciava col sigillo.
Quindi **bastava scrivere una riga prima del sigillo per scavalcare il controllo**.

Corretto: quel caso ha un verdetto suo, `senza-impronta`, ed è un **errore**. Meglio un falso
allarme che dice «rigenera» che un buco.

## Evidenze

- **I tre verdetti provati sul Blueprint vero** del Marketing Factory:
  - contenuto cambiato a mano → **MANOMESSO**, uscita 1
  - un verbale in più nei registri, file intatto → **indietro**, uscita **0**
  - rigenerato → **aggiornato**
- Test: da **211 a 216 controlli**, comprese le prove che un blocco modificato **dentro** il corpo
  è manomesso e una riga scritta **prima** del sigillo è segnalata.
- `B6` delle prove comportamentali aggiornato: **`indietro` dopo una tappa chiusa è un
  fallimento** — vuol dire che la chiusura non ha scattato la fotografia. Fra una tappa e l'altra,
  invece, è normale.
- La regola è nel **passo 12** della sequenza.

## Conseguenze

- Il limite di `DEC-0030` è **risolto**: vecchio e falso ora si distinguono.
- Il Blueprint non è più un documento da tenere aggiornato: è **la storia delle fotografie** del
  progetto, una per tappa.
- `comportamento.py` ora **pretende** che la chiusura scatti la fotografia: se non lo fa, B6
  fallisce.

## Limiti dichiarati

- **Il sigillo dice che il contenuto non è stato toccato. Non dice che è giusto.** Se il
  generatore sbaglia, il sigillo sigilla un errore — come è successo con `ERR-0009`, dove la
  tappa aperta veniva dichiarata chiusa. **Il sigillo protegge dall'alterazione, non dall'errore.**
- **`senza-impronta` accusa due cose diverse** — una versione vecchia o una manomissione — perché
  dal file non si distinguono. Il rimedio è lo stesso, ma va saputo che l'accusa è ambigua.
- **Il sigillo non copre la parte scritta a mano.** Quella può ancora mentire, e nessun controllo
  la verifica: è narrativa, non stato.

## Metrica

Blueprint manomessi: atteso **zero**, ed è un errore. Blueprint indietro dopo una tappa chiusa:
atteso **zero** — è una chiusura fatta a metà.

## Data di revisione

2026-11-09
