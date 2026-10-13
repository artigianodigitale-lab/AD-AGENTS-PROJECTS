# DEC-0053 — La ricerca entra nel cervello

```yaml
id: DEC-0053
stato: approvato
livello: 2
data: "2026-10-13"
approver: CEO
supera:
```

## Problema

L'invariante 11 dice che a ogni richiesta il cervello *«cerca anche online»* se al mondo esiste
un modo migliore. **E il cervello non aveva un modo di cercare.** `ricerca.py` leggeva un
indirizzo che gia' conoscevi; la ricerca la faceva **lo strumento** (`web_search` di DSH), non il
sistema. Una capacita' del posto in cui giri **non e' una capacita' tua**: su un'altra macchina,
o in un altro IDE, il cervello non saprebbe cercare.

E la seconda meta': **18 verbali su 52 citavano una fonte, e nessuna era mai stata controllata.**
Un indirizzo citato e' una stringa in un documento. **Un link morto e' peggio di un link
assente**: sembra una prova, e non lo e'.

## Opzioni

1. **Non fare nulla** — la ricerca resta dello strumento. Conseguenza: il sistema **dichiara un
   dovere che non sa compiere**, e chi lo pubblica scopre che la parte «cerca online» funziona
   solo se il posto in cui gira ha quella capacita'. Fonte: e' la stessa forma di `ERR-0011` —
   un controllo dichiarato e assente.
2. **Usare un motore pubblico** — DuckDuckGo, Google, Bing. Conseguenza: zero installazione.
   Costo: **il `robots.txt` di `duckduckgo.com` dice `Disallow: /html`**, e le nostre stesse
   regole dicono *«rispettare robots.txt quando dichiara un divieto»* e *«se la faresti solo
   perche' nessuno ti vede, no»*. Fonte: [robots.txt di duckduckgo.com](https://duckduckgo.com/robots.txt)
   e `python3 tools/ricerca.py regole`. **Tecnicamente funziona e non si fa**: un sistema che
   aggira le proprie regole per comodita' non ha regole.
3. **SearxNG locale** — un motore che gira qui, interroga i motori che **noi dichiariamo
   permessi**, e non profila nessuno. Costo: un contenitore Docker, 106 MB, da aggiornare.
   Rischio: **non rende pulito lo scraping, lo sposta** — se accendi il motore Google, e'
   SearxNG che chiede a Google dal tuo indirizzo. Fonte:
   [SearxNG Search API](https://docs.searxng.org/dev/search_api.html) e
   [searxng/searxng](https://github.com/searxng/searxng).
4. **Brave come motore del web aperto** — l'API e' fatta apposta, quindi **per la via permessa**.
   Costo: una chiave, fascia gratuita. Fonte: [Brave Search API](https://brave.com/search/api/).
   **il CEO ha scelto: opzione pronta e spenta, nessuna chiave per ora.**

## Evidenze

- **SearxNG acceso e funzionante** dal 2026-10-12: 106 MB, `http://localhost:8080`, sopravvive
  al riavvio. **88 risultati** su una domanda vera, da **6 motori** — github 30, crossref 20,
  arxiv 10, semantic scholar 10, openalex 10, pubmed 8
- **Il limite, misurato**:
  ```
  categories=general  ->   0 risultati     nessun motore permesso in quella categoria
  categories=science  ->  40
  categories=it       ->  30
  tutte               ->  88
  ```
  **Il web aperto non c'e'**: blog, aziende, articoli di settore restano fuori. La differenza
  adesso ha un numero invece di una sensazione
- **`verifica` sulla macchina: 27 indirizzi citati, 27 vivi.** E le due che rispondevano 403
  sono state lette **col browser** — `ERR-0045`, il 403 scambiato per «morto»
- **`robots.txt` dentro il tool**: `duckduckgo.com/html` **vietato**, `arxiv.org` permesso.
  La regola non dipende piu' dalla disciplina dell'agente

## Scelta

**Opzione 3 + 4 spenta.** Con le decisioni del CEO del 2026-10-12/13.

- **SearxNG con Docker**, configurato in `~/.searxng/` — **fuori dal repository**, perche' e'
  **infrastruttura**, non memoria dell'azienda
- **`keep_only`**: si accende **solo cio' che e' dichiarato**. Spegnere per nome e' fragile:
  `google` e `google cse` sono due motori diversi, e il 2026-10-12 il secondo ha risposto
  mentre il primo era spento
- **Le categorie si dichiarano**: senza, SearxNG cerca in `general`, dove non abbiamo motori
- **`robots.txt` prima di ogni lettura**, con la risposta **(b)**: la macchina **rifiuta** e
  **passa il link al CEO**, perche' il divieto riguarda un cliente automatico e non una persona
- **`cerca`, `verifica`, `raccogli`** entrano in `ricerca.py`. Il cervello ora cerca da solo
- **Brave**: aggancio documentato e spento

## Conseguenze

- **La ricerca non dipende piu' da dove giri**: SearxNG e' locale, e il tool parla con lui
- **Le fonti si possono controllare**: `python3 tools/ricerca.py verifica` dice quali sono morte,
  quali sono protette e quali vive
- **Il 403 non si confonde piu' con un link morto**, e il browser entra dove la via leggera non
  passa — dentro le regole
- **Una regola e' diventata un controllo**: `robots.txt` letto dal tool, non dall'agente
- Suite: **423 controlli**, dopo le correzioni

## Limiti dichiarati

- **Il web aperto non c'e'.** Senza Brave, `general` non ha motori. E' una scelta, ed e'
  **misurata**: 0 risultati su quella categoria
- **SearxNG non e' nel repository.** La configurazione vive in `~/.searxng/`: per la
  pubblicazione serve **uno script che la ricostruisce**, altrimenti l'installazione non e'
  riproducibile. **Non l'ho fatto**
- **SearxNG va aggiornato e mantenuto.** E' un servizio, non un file
- **`verifica` non dice se una fonte dice quello che le attribuiamo.** Dice che **esiste**. Un
  link vivo che non contiene la frase citata resta un problema, e nessun controllo lo prende
- **Il nome con cui ci presentiamo e' `ad-projects-agent`**, e non fingiamo di essere un browser:
  chi legge i log ci riconosce. E' corretto, e significa che alcuni siti ci tratteranno come bot
- **`ERR-0045`**: avevo etichettato due fonti come morte per un 403. **Ottava volta in quattro
  giorni** che traduco una risposta in un giudizio senza chiedermi cosa significhi

## Metrica

Indirizzi citati con una verifica: da **0 su 27** a **27 su 27**. Motori accesi: **6**, tutti
dichiarati. Motori vietati accesi: **0**, e non per disciplina ma per configurazione.

## Data di revisione

2026-11-09

## Esito misurato

<Da compilare il 2026-11-09: se la chiave Brave e' stata presa, se `verifica` ha trovato un
link morto, e se qualche fonte citata e' stata scoperta dire qualcosa di diverso da quello che
le attribuivamo.>
