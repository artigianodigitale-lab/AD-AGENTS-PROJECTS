# DEC-0028 — Il controllo che mancava: dopo la scrittura

```yaml
id: DEC-0028
stato: approvato
livello: 2
data: 2026-10-10
approver: CEO
supera:
```

## Problema

L'enforcement di AD Projects aveva **un solo gancio**: `tools/pre-execute`, che decide *prima*
che una scrittura avvenga. Andava bene per una cosa — impedire di scrivere dove nessun permesso
arriva — e lasciava scoperto tutto il resto.

Il 2026-10-08 **ogni prova e ogni marcatore** scritti quel giorno dichiaravano un orario nel
futuro, e nessuno se n'è accorto. Un revisore di passaggio l'ha trovato per caso. Il gancio
precedente non poteva vederlo: **il file non esisteva ancora**.

## Cosa e' stato aggiunto

**1. La meta' che avvisa — `tools/post-execute`.**

Due controlli, e sono i due errori che hanno gia' sbagliato una volta:

| Controllo | Cosa prende |
|---|---|
| Un orario dichiarato **nel futuro** | le date inventate. `expires` e' escluso: una scadenza *deve* essere nel futuro |
| Un marcatore di approvazione **piu' recente del suo permesso** | l'ordine invertito. Riscrivere un record ne cambia l'mtime, e l'ordine si legge dagli mtime |
| Un **permesso chiuso** mentre la storia del progetto ha ancora un passo senza rapporto | «finito» detto in due modi diversi. La tappa ha ragione lei |

Il terzo e' nato durante questo stesso lavoro: il 2026-10-08 avevo chiuso `ORD-001` e dato per
finito il riordino del Marketing Factory — file al loro posto, gate passato — **senza mai
scrivere il rapporto del passo**. Per due giorni la storia del progetto ha detto «passo mai
chiuso» mentre il permesso diceva «chiuso». Guardavo il permesso, non la tappa. Ora il
controllo guarda la tappa.

Quando scatta, il gancio restituisce `block` con il motivo: il modello vede subito che quella
scrittura non e' accettabile e la corregge.

**2. La meta' che impedisce — un `.md` nuovo nella radice.**

Invariante 15: la radice tiene la macchina, non le carte. E' l'unico caso in cui si puo'
**impedire** invece di avvisare, perche' il file non esiste ancora. Il CEO aveva dovuto spostare a
mano, piu' volte, file creati da un agente nella super cartella: una regola scritta non era
bastata. **Una regola si dimentica, un blocco no.**

L'elenco dei documenti ammessi nella radice sta in `settings.json` (`rootDocs`): per aggiungerne
uno legittimo non serve toccare il codice.

## Evidenze

- Test del plugin: da **25 a 36 controlli**, tutti passanti. Ogni controllo nuovo ha la sua
  prova, compreso il caso che **non** deve scattare (una data passata, una scadenza futura, un
  `.md` dentro una cartella).
- Passata sui **record veri**: 175 file esaminati, **0 falsi allarmi**. Un controllo che accusa
  roba corretta e' peggio di nessun controllo.
- La passata ha trovato **2 problemi veri** — `SEC-002` e `REL-001` avevano la firma **dopo** il
  permesso — e il terzo controllo ha trovato **un rapporto mancante**, il mio. Vedi sotto.

## Il difetto che il controllo ha trovato subito

`SEC-002` e `REL-001`: firma alle 17:25 e 17:55, permesso alle 17:18 e 17:21. **Ordine
invertito.**

Causa: due errori miei sovrapposti. Gli orari dichiarati erano **inventati** (numeri tondi, piu'
tardi della scrittura vera); poi, correggendo le date il 2026-10-08, ho ripristinato l'mtime dei
marcatori **proprio su quegli orari inventati** — spostandoli dopo i loro permessi. Ho rotto
l'ordine mentre riparavo le date.

Impatto: **nessuno**. Entrambi i permessi sono `chiuso` e non coprono piu' nulla.

Rimedio: orario **ricostruito** a un minuto prima del permesso, e il record lo **dichiara** nel
campo `nota`. L'orario vero non e' recuperabile — e' stato distrutto dal mio ripristino, e
inventarne un altro sarebbe stato rifare l'errore che ha causato tutto questo. `DRIFT-015`.

**E' la prima volta che un controllo nostro trova un difetto nostro senza che nessuno lo
cercasse.** E' esattamente il mestiere che mancava.

## Limiti dichiarati

- **Il gancio dopo la scrittura non disfa niente.** Il file resta com'e'. Ferma il *risultato*:
  il modello viene avvisato, ma il danno, se c'e', e' gia' fatto. Prevenire e avvisare sono due
  mestieri, e questo fa il secondo.
- **Non e' ancora vivo in questa sessione.** I plugin ESM si caricano una volta per sessione:
  il codice nuovo sara' attivo **dal prossimo riavvio di DSH**. Qui e' provato con il test del
  plugin (33 controlli) e con la passata sui record veri (172 file) — non a runtime. Chi riavvia
  lo verifichi, non lo dia per fatto.
- **Il blocco sui `.md` di radice non ha una via d'uscita immediata**: per creare un documento
  normativo nuovo serve modificare `settings.json` e riprovare. E' voluto — un blocco con una
  scorciatoia non e' un blocco — ma va saputo.
- **I due controlli coprono cio' che ho visto sbagliare.** Non sono una teoria dei guasti: sono
  i tre errori realmente accaduti. Un errore nuovo, di forma nuova, passera' ancora.

## Conseguenze

- `DRIFT-015` chiuso; `DRIFT-014` (le date inventate) ora ha un controllo che lo presidia.
- La passata sui record veri e' una verifica che si puo' ripetere: **172 file, atteso 0 blocchi**.
- Il plugin passa da un gancio a due: impedire dove si puo', avvisare dove non si puo'.

## Metrica

Record che dichiarano un orario futuro: atteso zero — ora e' un blocco, non una speranza.
Marcatori con ordine invertito: atteso zero, oggi zero dopo la ricostruzione.

## Data di revisione

2026-11-09
