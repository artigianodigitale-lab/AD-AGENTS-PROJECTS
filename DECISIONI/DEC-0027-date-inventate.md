# DEC-0027 — Le date inventate

```yaml
id: DEC-0027
stato: approvato
livello: 2
data: 2026-10-08
approver: CEO
supera:
```

## Problema

Il 2026-10-08 **ogni prova e ogni marcatore** scritti quel giorno dichiarava un orario **nel
futuro** rispetto al momento in cui il file era stato scritto.

| Record | Dichiarava | Scritto davvero | Scarto |
|---|---|---|---|
| `GOV-000.yaml` | 14:50 | 14:30 | 20 min |
| `SEC-001-security.yaml` | 16:45 | 16:21 | 24 min |
| `FIX-001-code-review.yaml` | 17:30 | 16:53 | **37 min** |
| `SEC-002-security.yaml` | 17:40 | 17:18 | 22 min |
| `ORD-001.yaml` (marcatore) | 19:45 | 19:21 | 24 min |
| `ORG-001-code-review.yaml` | 19:05 | 17:32 | **1 h 33 min** |
| `ORD-002.yaml` (marcatore) | 20:30 | 19:41 | 49 min |
| `ORD-002-code-review.yaml` | 20:55 | 19:45 | **1 h 10 min** |

Dieci record su dieci, tutti nello stesso verso: **avanti**. Non era una svista isolata, era il
modo in cui scrivevo le date.

## Perche' conta

Un registro di governo serve a ricostruire **chi ha deciso cosa, e quando**. Se le date sono
inventate, il registro non ordina piu' niente — e l'ordine e' l'unica cosa che rende verificabile
la sequenza `ricerca → risposta → consenso → permesso`.

Peggio: **nessuno se ne sarebbe accorto.** Le date erano numeri scritti a mano, e nessun
controllo le leggeva. Sono andate avanti tutto il giorno.

## Chi l'ha trovato

**Il revisore indipendente di `ORD-002`**, non io — e non perche' cercasse quello: l'ha notato
mentre verificava altro, confrontando la data dichiarata dall'evidenza con il suo mtime. E'
esattamente il motivo per cui l'invariante 4 pretende un revisore che non sia l'esecutore.

## Scelta

**1. Le date dichiarate ora corrispondono all'mtime reale del file.** Non e' la verita' perfetta —
l'ora dell'*evento* non e' ricostruibile — ma e' l'unica data **verificabile**, e non e' nel
futuro.

**2. `tools/coherence.py` verifica che nessun record dichiari un orario non ancora arrivato.**
Controlla i campi che registrano **quando e' successo qualcosa** (`data`, `timestamp`, `aperta`,
`chiusa`, `chiuso`) ed **esclude `expires`**, che invece *deve* essere nel futuro. La prima
versione del controllo non lo escludeva e segnalava tutti i permessi attivi come falsi: un
controllo sbagliato e' peggio di nessun controllo.

## La trappola scoperta riparando, ed e' la parte che vale di piu'

Riscrivere un file di governo **ne cambia l'mtime** — e il controllo dell'ordine
(approvazione prima del permesso) **legge gli mtime**.

Quindi correggere una data *dentro* un record senza rimettere l'mtime **rompe l'ordine**. E'
successo: il mio primo tentativo ha reso il marcatore piu' recente del permesso, il controllo ha
decretato «contract retrodatato», e da quel momento il controllore ha **bloccato ogni comando**
che toccasse `.brain/` o `tools/`, perche' non riusciva piu' a verificarne la copertura. Mi sono
trovato chiuso fuori dalla mia stessa macchina.

Rimedio, ora dichiarato: **dopo ogni modifica a un record di governo, l'mtime va ripristinato
all'orario dichiarato.**

## Conseguenze

- `DRIFT-014` chiuso: la causa (nessuno confrontava le date con l'orologio) e' rimossa.
- **Diciotto record** riportati all'ora vera.
- La suite deterministica non copriva questo caso e ora lo copre tramite `coherence.py`.
- **Limite dichiarato**: il controllo verifica che una data non sia nel futuro. **Non** verifica
  che sia quella dell'evento. Una data arretrata ma plausibile resta impossibile da smascherare
  senza una fonte esterna all'agente.
- **Limite dichiarato**: il ripristino degli mtime e' manuale. Nessuno strumento lo impone, e la
  prossima volta che qualcuno modifica un record puo' dimenticarsene.

## Metrica

Record che dichiarano un orario nel futuro: atteso zero, oggi zero — e ora e' un controllo, non
una speranza.

## Data di revisione

2026-11-07
