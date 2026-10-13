# piani — piani di lavoro in attesa del CEO

Un file per richiesta: `piani/<AAAA-MM-GG>-<slug>.md`. E' il **piano di lavoro**
che il Team di Agenti costruisce quando l'utente chiede di lavorare su un
progetto esistente o di crearne uno nuovo.

Il piano viene **prima** dei task contract. E' il documento che il CEO legge e
approva; solo dopo l'approvazione si aprono i contract in `contratti/`, che sono
cio' che sblocca le scritture.

## Perche' esiste

Il plugin `ad-enforce-contract` blocca ogni scrittura dentro le cartelle prodotto
finche' non esiste un contract che la copra. Il contract, pero', non deve nascere
dal nulla: deve discendere da un piano approvato. `piani/` e' quel passaggio.

```text
richiesta del CEO (proposta da verificare, non un ordine)
      |
      v
RICERCA: esiste un modo migliore, piu' scalabile, piu' affidabile?
      |
      v
RISPOSTA al CEO, prima di fare:
  cosa hai chiesto · cosa ho trovato · cosa consiglio · cosa serve da te
      |
      v
CONSENSO del CEO su cosa fare
      |
      v
piani/<data>-<slug>.md      <- il piano operativo dettaglia la scelta approvata
      |
      v
contratti/<TASK_ID>.yaml    <- apre il write_scope, il lavoro puo' partire
```

Il piano comincia con la risposta: le sezioni 1-4 sono *cosa hai chiesto, cosa ho
trovato, cosa consiglio, cosa serve da te*. Solo dopo il consenso si compilano le
sezioni operative.

## Regole

- **La richiesta non e' un ordine.** Vale anche quando arriva dal CEO: prima si verifica
  se esiste un modo migliore, poi si propone.
- **Prima si risponde, poi si decide.** Nessun piano operativo senza la risposta.
- Un piano non assegna lavoro e non autorizza scritture: e' una proposta.
- Senza consenso esplicito del CEO il piano resta in stato `proposto`.
- Silenzio, ambiguita' o "vediamo" non sono consensi. Senza risposta entro
  2 giorni lavorativi la proposta non e' approvata.
- Un piano che richiede una decisione di Livello 2 o 3 si collega a un Decision
  Record in `DECISIONI/`.
- Il piano dichiara il `write_scope` di ogni contract previsto: e' il confine
  reale del lavoro.
- Un piano respinto si conserva. Non si riscrive: se ne produce uno nuovo che lo
  cita.

## Avvio rapido

```sh
cp piani/_TEMPLATE.md "piani/$(date +%F)-<slug>.md"
```

## Indice

Nessun piano aperto.
