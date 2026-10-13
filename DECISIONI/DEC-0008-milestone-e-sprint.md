# DEC-0008 — Milestone e sprint: la storia documentata di ogni progetto

```yaml
id: DEC-0008
stato: approvato
livello: 3
data: 2026-10-08
approver: CEO
supera:
```

## Problema

L'esecuzione di un progetto era una sequenza di richieste. Nessuno strutturava il lavoro in fasi, e nulla conservava **come** una cosa era stata fatta: solo che era stata fatta.

Conseguenze:

1. Un progetto non aveva una storia: chi riprendeva il lavoro dopo mesi ripartiva da zero, senza sapere perché una scelta era stata presa.
2. Non esisteva un punto in cui dire «questo sprint è chiuso»: il lavoro si assottigliava invece di chiudersi.
3. Non c'era modo di sapere se un progetto stesse procedendo verso un prodotto finito o stesse girando a vuoto: nessun obiettivo di fase, nessun criterio di chiusura.
4. Le milestone non esistevano, quindi non si poteva pianificare oltre la prossima richiesta.

La richiesta esplicita del CEO: *prima di partire nella compilazione va analizzato tutto ciò che serve per renderlo ufficiale e prodotto finito integralmente, creando poi una o più milestone con i suoi sprint, dove ogni volta che si passa da uno sprint al successivo deve essere creato un prompt markdown per lo sprint e rilasciato un file markdown per il lavoro eseguito e di come è stato eseguito. Questo ci permette di avere uno storico fatto di documentazione, salvata in una cartella chiamata Milestone 1, Milestone 2 e così via.*

## Opzioni

1. **Milestone e sprint con prompt e report obbligatori**, dentro la cartella del progetto, con controllo deterministico.
2. **Solo una cartella di documentazione**, senza struttura né obblighi: diventa un archivio che nessuno aggiorna.
3. **Report a fine progetto**: la storia si ricostruisce a memoria, e si perde il dettaglio.
4. **Non fare nulla.**

## Evidenze

- Nessun documento del corpus nominava milestone, sprint, prompt di sprint o report di sprint.
- Il piano in `piani/` è per-richiesta e temporaneo: non copre la durata di un progetto.
- `RUNTIME.md` descrive la vita di un'*istanza* (card + contract), non di un progetto: il livello di pianificazione oltre il singolo task era assente.
- L'assenza di un inventario di avvio era già emersa: si costruiva senza sapere cosa mancasse per arrivare a prodotto finito.

## Scelta

**Opzione 1**, su tre elementi.

**Struttura**, dentro la cartella del progetto:

```text
<progetto>/
  Milestone 1/
    REPORT.md          report della milestone, step by step
    Sprint 1/
      PROMPT.md        scritto prima di eseguire
      REPORT.md        rilasciato alla chiusura, con cosa e come
    Sprint 2/
      PROMPT.md
      REPORT.md
  Milestone 2/
    ...
```

**Analisi di avvio**, nuovo passo 8 di `ad-kickoff`: prima di compilare si inventaria tutto ciò che serve per rendere il progetto **ufficiale** e **prodotto finito** — funzioni, contenuti, dati, integrazioni, dominio, hosting, ambienti, privacy, cookie, termini, fatturazione, rischi, dipendenze, e ciò che esplicitamente non farà parte del prodotto. Dall'inventario nascono le milestone.

**Controllo deterministico**, `tools/milestone.py`:

```sh
python3 tools/milestone.py check "<progetto>"
python3 tools/milestone.py new-milestone "<progetto>" --goal "..."
python3 tools/milestone.py new-sprint "<progetto>" 1 --objective "..."
```

`check` esce 1 quando manca un report, manca un prompt, o la numerazione ha un buco. Gli strumenti **si rifiutano di scrivere** in una cartella prodotto non coperta da un contract approvato: le scritture fatte da uno script non passano dall'euristica della shell del plugin, quindi la guardia sta dentro lo strumento.

Modelli in `milestone/`: `_TEMPLATE-MILESTONE.md`, `_TEMPLATE-SPRINT-PROMPT.md`, `_TEMPLATE-SPRINT-REPORT.md`. La procedura è nella skill `ad-milestone`.

## Conseguenze

- Ogni progetto porta con sé la propria **storia documentata**: cosa è stato fatto, in che ordine, e soprattutto **come**.
- Uno sprint senza report **non è chiuso**, e il successivo non parte. Il lavoro si chiude, non si assottiglia.
- La numerazione contigua rende visibile un buco: un buco nella storia è un buco nella responsabilità.
- La milestone è l'unità di pianificazione; il contratto resta l'unità di autorizzazione. Sono due cose distinte e non si sostituiscono.
- Un documento normativo di root è cambiato: snapshot rigenerato.
- La skill `ad-kickoff` è stata riordinata: la sequenza passa da 10 a 12 passi e i titoli delle sezioni sono allineati.
- **Limite dichiarato**: `milestone.py check` verifica che prompt e report **esistano** e che la numerazione sia contigua. Non giudica se un report sia utile o se uno sprint fosse ben tagliato. La qualità della storia resta una responsabilità umana, verificata dal CEO in revisione.
- **Nota di correzione**: la proposta di un artefatto di strategia per progetto — problema, ICP, valore, concorrenza, posizionamento, go-to-market, unit economics — è stata **ritirata**. Il CEO ha chiarito che quella parte si considera già fatta: ciò che serve è l'analisi di avvio tecnica e di business descritta sopra, orientata a rendere il progetto un prodotto finito.

## Metrica

Percentuale di sprint chiusi con un report completo (atteso: 100%) e numero di milestone con `check` pulito. Nella revisione dei 30 giorni si misura anche il tempo fra l'apertura di uno sprint e il suo report.

## Data di revisione

2026-11-07
