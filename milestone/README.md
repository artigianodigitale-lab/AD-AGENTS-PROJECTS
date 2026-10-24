# milestone — la storia documentata di un progetto

Ogni progetto si esegue in **milestone**, e ogni milestone in **sprint**. La storia vive dentro la cartella del progetto:

```text
<progetto>/
  Milestone 1/
    REPORT.md              report della milestone, step by step
    Sprint 1/
      PROMPT.md            scritto PRIMA di eseguire lo sprint
      REPORT.md            rilasciato alla CHIUSURA dello sprint
    Sprint 2/
      PROMPT.md
      REPORT.md
  Milestone 2/
    REPORT.md
    Sprint 1/
      PROMPT.md
      REPORT.md
```

Il nome e' `Milestone 1`, `Milestone 2`, con lo spazio: e' una cartella che leggi tu.

## La regola

- **Una milestone per volta.** Si apre con un obiettivo e si chiude con un `REPORT.md` che racconta come e' andata, passo per passo.
- **Uno sprint per volta.** All'apertura si scrive il `PROMPT.md`: cosa deve esistere alla fine, criteri di accettazione, input, vincoli, gate.
- **Al passaggio allo sprint successivo** si rilascia il `REPORT.md` dello sprint: cosa e' stato fatto, **come**, con quali evidenze, e cosa passa avanti.
- **Non si salta.** Uno sprint senza `PROMPT.md` non e' mai stato aperto; senza `REPORT.md` non e' chiuso, e il successivo non parte.
- **La numerazione e' contigua.** `Milestone 1, 2, 3`, e dentro `Sprint 1, 2, 3`. Un buco si vede subito.
- Il report non e' un riassunto per il CEO: e' la memoria tecnica del progetto. Serve a chi riprende il lavoro fra sei mesi.

## Perche' esiste

Senza questa struttura un progetto e' una sequenza di chat: il lavoro si perde, le decisioni non hanno contesto, e nessuno sa **come** una cosa e' stata fatta — solo che e' stata fatta. Con questa struttura ogni progetto porta con se' la propria storia, verificabile.

## Quando si crea

Dopo il consenso del CEO e l'**analisi di avvio**: si decide quante milestone servono per arrivare a prodotto finito, e si apre la prima. Non prima: le milestone si pianificano su una richiesta approvata, non su un'idea.

## Comandi

```sh
# apri la prossima milestone
python3 tools/milestone.py new-milestone "<progetto>" --goal "primo prodotto utilizzabile"

# apri il prossimo sprint della milestone 1
python3 tools/milestone.py new-sprint "<progetto>" 1 --objective "autenticazione"

# la storia e' completa?
python3 tools/milestone.py check "<progetto>"
```

`check` esce 1 quando manca un report, un prompt, o la numerazione ha un buco.

## Modelli

- [`_TEMPLATE-MILESTONE.md`](_TEMPLATE-MILESTONE.md) — report della milestone
- [`_TEMPLATE-SPRINT-PROMPT.md`](_TEMPLATE-SPRINT-PROMPT.md) — prompt dello sprint
- [`_TEMPLATE-SPRINT-REPORT.md`](_TEMPLATE-SPRINT-REPORT.md) — report dello sprint

I modelli sono usati da `tools/milestone.py` per aprire milestone e sprint: non si scrivono a mano.
