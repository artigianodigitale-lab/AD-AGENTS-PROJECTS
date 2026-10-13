# Piano — La ricerca: il cervello impara a cercare

**Stato: APPROVED WITH CONSTRAINTS** (il CEO, 2026-10-12/13).
**Permesso**: `contratti/societa/GOV-002.yaml`.

## Perche'

L'invariante 11 dice che a ogni richiesta il cervello *«cerca anche online»* se al mondo esiste un
modo migliore. **E non ha un modo di cercare**: `ricerca.py` legge un indirizzo che gia' conosci.
La ricerca la fa **lo strumento** (`web_search` di DSH), non il cervello — quindi non e' una
capacita' del sistema, e' una capacita' del posto in cui gira.

Misurato il 2026-10-12: **18 verbali su 52 citano una fonte**. E **nessuna fonte era mai stata
controllata**: un indirizzo citato e' una stringa in un documento.

## Le decisioni del CEO

| | |
|---|---|
| **SearxNG** | si, con Docker. *«un pochino di scraping in piu' ce lo metterei, tu lo hai grazie a Camoufox»* |
| **Brave** | **opzione pronta e spenta, niente chiave per ora** |
| **Licenza** | **Apache-2.0** |
| **`robots.txt` vietato** | **(b)** — il tool rifiuta **e passa il link al CEO**, perche' il divieto riguarda un cliente automatico, non una persona |

## Cosa c'e' gia', e cosa manca

| Cosa serve | Stato |
|---|---|
| **Cercare** | mancava. **SearxNG acceso e funzionante** dal 2026-10-12 |
| **Leggere** | c'e' ✓ via leggera, browser se serve, cache |
| **Ricordare** | una stringa in un documento |
| **Verificare** | **manca**: nessuno controlla che una fonte citata esista ancora |

## I passi

| # | Cosa | Perche' qui |
|---|---|---|
| 1 | **`verifica`** — controlla gli indirizzi gia' citati | **prima di aggiungere fonti, assicuriamoci di saperle controllare.** Altrimenti si moltiplica il problema |
| 2 | **Il controllo `robots.txt` dentro il tool** | con la risposta (b): rifiuta **e mostra il link** |
| 3 | **`cerca`** su SearxNG, con le categorie dichiarate | l'ultimo: ha bisogno dei primi due |
| 4 | **Brave come opzione** | aggancio pronto, spento, documentato |

## SearxNG — com'e' configurato

`~/.searxng/` (fuori dal repository: e' **infrastruttura**, non memoria dell'azienda).

- **`settings.yml`** — `use_default_settings` con **`keep_only`**: si accende **solo cio' che e'
  dichiarato**. Spegnere per nome e' fragile: `google` e `google cse` sono due motori diversi, e il
  2026-10-12 il secondo ha risposto mentre il primo era spento
- **`limiter.toml`** — la rete dei contenitori in `pass_ip`. **Non** in `trusted_proxies`: quella
  lista e' per chi **inoltra**, e metterla li' fa pretendere `X-Forwarded-For` a ogni richiesta
- **Motori accesi**: arxiv, crossref, openalex, pubmed, semantic scholar, github

### Il limite, misurato

```text
categories=general   ->   0 risultati     nessun motore permesso in quella categoria
categories=science   ->  40
categories=it        ->  30
tutte                ->  88
```

**Il web aperto non c'e'.** Blog, aziende, articoli di settore: fuori. Quello che abbiamo e'
**scienza e tecnica** — che per un sistema che fonda le decisioni su fonti verificabili e' la
parte che conta, ma **non e' «il web intero»**, e la differenza adesso ha un numero.

## Fuori ambito

- **La chiave Brave** (spenta per scelta)
- **La portabilita'** e **la pubblicazione**: tappe successive
- **I 17 progetti**: non si toccano
- **Accendere i motori vietati**: Google, Bing, DuckDuckGo e le loro varianti restano spenti
