# STATO OPERATIVO

Vista umana dello stato. Non viene caricata automaticamente nel contesto del modello.

**La parte sopra il marcatore la scrive una persona. La parte sotto la genera
`tools/stato.py` leggendo i registri**, e il controllo la rigenera e confronta: dice
**aggiornato**, **indietro** (autentica ma di registri piu' vecchi) o **manomesso**.

<!-- generato:inizio -->
> **Vista generata dai registri.** impronta: `b8544dafa33c`
> Il controllo la rigenera e confronta. **Autentica non vuol dire giusta**: il sigillo protegge dall'alterazione, non dall'errore.

## Permessi attivi

| Permesso | Su cosa | Chi | Scade |
|---|---|---|---|
| `ADMF-008` | tools/README.md, .brain/ | `platform` | 2027-01-11 (89 gg) |
| `GOV-008` | tools/ad_docs.py, tools/ad_scope.py, tools/ad_milestone.py, tools/ad_coherence.py, tools/blueprint.py, tools/comportamento.py, tools/stato.py, tools/setup.py, tools/tests/test_ad_org.py, README.md, sede.yaml, orchestrazione/stato.md | `platform` | 2026-11-08 (25 gg) |
| `GOV-009` | .brain/COSTITUZIONE.md, .brain/skills/ad-avvio/SKILL.md, .brain/skills/ad-kickoff/SKILL.md | `platform` | 2026-11-08 (25 gg) |

## L'agente si comporta come deve?

| | |
|---|---|
| Prove comportamentali | **7/7** |
| Errori registrati | 46 |
| Trovati da un **controllo** | 6 |
| Trovati per **fortuna** | 27 |

*stiamo avendo FORTUNA: la maggioranza degli errori l'ha trovata una persona*

## Cosa aspetta una decisione

- Discrepanza aperta **DRIFT-002** (MEDIUM) — Il campo `product` elenca 3 prodotti, le cartelle numerate sono 17
- Discrepanza aperta **DRIFT-003** (LOW) — Il pack dichiara «CI assenti», la CI esiste
- Discrepanza aperta **DRIFT-004** (MEDIUM) — `middleware.ts` non esiste: il file e' `proxy.ts`
- Discrepanza aperta **DRIFT-005** (LOW) — I contatori del pack sono superati
- Discrepanza aperta **DRIFT-009** (LOW) — I contract del 2026-10-08 non soddisfano l'invariante 13
- Discrepanza aperta **DRIFT-013** (MEDIUM) — Un permesso resta attivo dopo che la sua tappa e' chiusa
- Discrepanza aperta **DRIFT-016** (LOW) — Un rapporto di progetto nomina un registro che non c'e' piu'
- Discrepanza aperta **DRIFT-017** (LOW) — La scheda del modulo di Modelbel rimanda a un'evidenza superata
- Discrepanza aperta **DRIFT-018** (HIGH) — Cinque permessi sullo stesso percorso: un percorso senza titolare
- Discrepanza aperta **DRIFT-019** (LOW) — Un permesso scaduto resta scritto come attivo
- Errore aperto **ERR-0018** — Al revisore indipendente del gate QA ho passato come «fonte» la trascrizione delle risposte di Michele, e dentro quella 
- Errore aperto **ERR-0019** — Ho aperto un passo con `milestone.py new-sprint ... 2`, indicando la tappa 2 — ma la tappa 2 era stata **aperta e chiusa
- Errore aperto **ERR-0020** — Il registro dei requisiti diceva che la parte a pagamento era «il modello di ricavo del Prof. Clementi»; il documento pr
- Errore aperto **ERR-0021** — Dalla frase di Michele «il cliente può avere più conti e di conseguenza minus su conti diversi che deve recuperare» ho d
- Errore aperto **ERR-0022** — Il revisore indipendente del gate Brand ha scritto nella prova `NLT-006-brand.yaml` l'orario **09:26**, mentre il file e
- Errore aperto **ERR-0028** — Mentre i due gate verificavano il report dello sprint 1 di Marketing Factory, **io ho modificato quel report**: ho aggiu
- Errore aperto **ERR-0029** — `tools/ricerca.py`, riga 256: `print(esito.get("testo", "")[:4000])`. La via a riga di comando **tronca in silenzio il t
- Errore aperto **ERR-0031** — `tools/stato.py` **non può quasi mai rispondere AGGIORNATO**, per costruzione, e la causa e' che il **corpo sigillato co
- Errore aperto **ERR-0032** — L'inventario di avvio (`ADMF-010`) ha misurato le 18 caselle del criterio di «prodotto finito» e ne ha trovate **11 aper
- Errore aperto **ERR-0033** — `misure.py` decide se una misura e' di sola lettura guardando **la forma del comando**, e fra le forme che rifiuta c'e' 
- Errore aperto **ERR-0034** — `.brain/COSTITUZIONE.md`, riga 124, dice: «**I 193 controlli** provano i programmi. Le prove comportamentali provano l'a
- Errore aperto **ERR-0035** — Il report delle domande per Michele si apriva con «Per ognuna trovi tre cose: perché conta, cosa abbiamo oggi, cosa sblo
- Errore aperto **ERR-0036** — Il report delle domande per Michele era intestato «**Per: il CEO Bolognini**» mentre il corpo conteneva domande rivolte a 
- Errore aperto **ERR-0038** — **Tre artefatti diversi, un difetto solo**: un valore **dipendente dall'ora** e' finito dentro un testo che si dichiara 
- Errore aperto **ERR-0042** — Il gate del modulo di raccolta dati di Modelbel ha respinto il documento per un difetto di **resa**, non di contenuto: l
- Errore aperto **ERR-0043** — Il modulo di raccolta dati di Modelbel diceva: «Se lo compilate a video, il PDF ha campi scrivibili». Il PDF **non ha ne
- Errore aperto **ERR-0044** — Il Blueprint appena generato per Modelbel dice «**Tappa 1 · Passo 1** — aperto, senza rapporto» e nella tabella dei pass
- Il permesso `GOV-008` **scade fra 25 giorni** (2026-11-08T00:00:00+01:00). Un agente non puo' rinnovare il proprio permesso (invariante 7)
- Il permesso `GOV-009` **scade fra 25 giorni** (2026-11-08T00:00:00+01:00). Un agente non puo' rinnovare il proprio permesso (invariante 7)

## Gli ultimi lavori chiusi

Nessun passo chiuso in nessun progetto.

## I numeri

| Cosa | Quanti |
|---|---|
| Verbali (Decision Record) | 55 |
| Discrepanze registrate | 19 |
| Errori registrati | 46 |
| Skill del cervello | 9 |
| Comandi nella fascia deterministica | 19 |
| Progetti | 0 |

Generato da `tools/stato.py`. **Non si modifica a mano**: il controllo rigenera e confronta, e un testo che non corrisponde al proprio sigillo e' **manomesso**.
<!-- generato:fine -->
