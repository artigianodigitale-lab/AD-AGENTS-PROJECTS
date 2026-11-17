# CRAWLING — cosa si puo' scaricare, e cosa no

> **Cosa e' questo documento.** La policy di lettura del web del motore. E' normativa: e'
> sotto snapshot, si cambia con un Decision Record. Riferimento: `DECISIONI/DEC-0113-m3-scraping.md`;
> strumento: `tools/crawler.py`; regole di lettura di una pagina: `python3 tools/ricerca.py regole`.

## 1 · La regola in una frase

**Si legge il web come lo leggerebbe una persona con un browser; non si fa quello che una
persona non farebbe.**

## 2 · Cosa si puo' fare

| Si puo' | Come |
|---|---|
| Leggere **pagine pubbliche** | HTTP prima; browser headless solo se la pagina senza JavaScript resta vuota |
| Seguire i link dentro lo **stesso sito** (o i domini dichiarati) | coda BFS, `--dominio`, `--max-pagine`, `--max-profondita'` |
| Rispettare **robots.txt** | letto e applicato dallo strumento; un divieto non si aggira |
| Rispettare i **limiti del sito** | rate limit per dominio, `Crawl-delay` se dichiarato, backoff su 429/503 |
| **Conservare la provenienza** | ogni pagina: URL canonico, sha256 del corpo, status HTTP, data, profondita' |
| **Non riscaricare cio' che si ha gia'** | con `--cache` la pagina gia' presa (entro il TTL) viene dalla cache di M4, e il manifesto dice `via: cache`; scaduta, si riscarica |
| **Cancellare** | la cartella di uno scarico si cancella con il comando; nessun dato personale va conservato |

## 3 · Cosa non si fa

- **Superare un muro di pagamento.** Se il contenuto e' a pagamento, si legge l'abstract
  pubblico e basta.
- **Entrare in un'area riservata**, anche con credenziali nostre, se i termini lo vietano.
- **Raccogliere dati personali in massa**: nomi, contatti, profili, foto di persone.
- **Scaricare in massa un sito** senza limiti: la coda, le pause e i tetti esistono per questo.
- **Scaricare i risultati di un motore di ricerca in massa** (SERP): e' il caso che nel
  2025-2026 ha prodotto le cause piu' costose (DMCA §1201).
- **Aggirare una protezione tecnica** o un blocco: se il sito dice no, la risposta e' no.
- **Usare un browser per aggirare un divieto**: il browser serve a leggere JavaScript, non a
  scavalcare.
- **Toccare la rete interna.** Reti private, loopback, link-local e metadata cloud
  (`169.254.169.254`) sono **rifiutate per default**; `--consenti-loopback` esiste solo per le
  prove locali e lo dichiara.

## 4 · Il rischio legale, dichiarato

Il quadro 2025-2026 non e' piu' il CFAA ma il **DMCA §1201** (elusione di misure di
protezione): Google v. SerpApi (dic. 2025) e Reddit v. SerpApi/Perplexity/Oxylabs (ott. 2025),
con danni statutari indicati in **200-2.500 $ per atto**. `robots.txt` **non** e' legalmente
vincolante (Ziff Davis v. OpenAI, dic. 2025), ma il motore lo rispetta lo stesso: non e' una
questione di legge, e' la differenza fra un crawler e un abuso. Fonte: scraping-wiki,
*legal landscape*, consultata il 2026-11-15.

**La domanda giusta non e' «e' legale?» ma «quanto rischio sto comprando?».** Per questo il
crawler rifiuta per default tutto cio' che non e' una pagina pubblica, e l'uso su un sito
richiede di dichiarare il dominio.

## 5 · Dati personali e conservazione

- **Minimizzazione**: si conserva cio' che serve alla domanda, non «tutto il sito».
- **Nessun dato personale** in massa: se una pagina contiene dati di persone, non e' materiale
  da scaricare in un corpus.
- **Gli scarichi stanno fuori dal repository** (cache locale): non si versionano, non si
  pubblicano, non si passano a servizi esterni.
- **Cancellazione**: la cartella di uno scarico si elimina; se un titolare chiede la rimozione,
  si cancella e si annota la richiesta in `errori/` o in un verbale, secondo il caso.

## 6 · Come si comporta lo strumento

`tools/crawler.py` implementa questa policy, e la sua baseline la controlla:

| Promessa | Dove si vede |
|---|---|
| robots prima di ogni pagina | `robots.txt` scaricato e applicato; se non si legge (5xx), il sito si **disabilita** |
| limite per dominio | pausa fra richieste; `Crawl-delay` rispettato; backoff su 429/503 |
| niente rete interna | guardia SSRF, con `--consenti-loopback` solo per le prove |
| cache dichiarata | con `--cache`: TTL e provenienza; robots e rate limit vengono **prima** della cache, non dopo |
| niente schemi pericolosi | solo `http`/`https` |
| provenance | manifesto per pagina: URL, sha256, status, data, profondita' |
| tetto | `--max-pagine`, `--max-profondita'`, `--max-secondi` |

**Limiti dichiarati:**

- **Nessuna estrazione con LLM.** M3 estrae in modo deterministico (titolo, meta, titoli,
  JSON-LD, link, testo, campi dichiarati). L'estrazione «schema in linguaggio naturale ->
  modello» non c'e': costa per pagina, e si aggiunge quando c'e' un'eval che ne misuri il
  valore (M6).
- **Il browser non passa dalla guardia SSRF.** Con `--browser` la guardia controlla l'URL di
  partenza, ma il browser segue redirect e sotto-risorse per conto suo (`--no-sandbox`):
  usalo su siti fidati o dentro `tools/sandbox.py --rete`.
- **La guardia SSRF controlla l'IP risolto una volta** (DNS rebinding non coperto: si
  collega all'host, non all'IP).
- **Nessuna autenticazione**, e non deve esserci: un'area riservata non e' materiale da
  scaricare.
- **Il crawler non esegue JavaScript** se non con `--browser`, che gira headless e senza la
  sandbox di sistema.
