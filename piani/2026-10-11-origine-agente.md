# Piano — «Origine: nomeagente (ai)» — cosa c'è oggi, cosa serve, cosa decidere

```yaml
id: PIANO-2026-10-11-origine-agente
stato: approvato            # proposto | approvato | corretto | respinto
data: 2026-10-11
progetto: "3. AD-Marketing-Factory"
dominio: business           # cosa si firma e perche' e' una scelta di prodotto
richiesta: >
  "sull'origine va scritto il nome dell'agente che l'ha costruito, nella forma
  `nomeagente (ai)`" (il CEO, 2026-10-11)
esito_ricerca: da completare — e' una scelta di prodotto, non un metodo da cercare
decision_record: ""        # obbligatorio: tocca una regola di approvazione
```

## 1. Cosa hai chiesto

Che sull'origine di un contenuto sia scritto **il nome dell'agente che l'ha costruito**, nella
forma `nomeagente (ai)`. E, in una risposta successiva, che i nomi siano **i ruoli interni
dell'app** — `Creator`, `Strategist` — «più leggibili per chi guarda l'interfaccia», non le card
dell'organizzazione AD.

**Definizione di chiuso:** ogni contenuto mostra chi l'ha prodotto, con un nome che si può
verificare, e il nome viene da un elenco unico — non da stringhe sparse nel codice.

## 2. Cosa ho trovato

Ho letto il codice, non la memoria. Cinque fatti, ognuno con la sua prova.

### Fatto 1 — il campo esiste ed è una **stringa libera**

Il contenuto vive in `ContentVariant`, e il campo è (da `prisma/schema.prisma`):

```prisma
model ContentVariant {
  provenance       String?
```

Stringa **nullable e libera**: nessun elenco chiuso, nessun vincolo nel database. È il posto in cui
scrivere un nome — e anche il motivo per cui oggi nessuno lo fa.

### Fatto 2 — la validazione ammette **due** valori, il database ne contiene **sette**

`lib/content/provenance.ts` è il modulo che comanda, e dice:

```ts
export const VARIANT_PROVENANCE_VALUES = ["USER_EDITED", "AI_GENERATED"] as const;
```

e la sua `assertApprovalAllowed` **rifiuta l'approvazione** se il valore è un altro. Ma nel codice
girano, e finiscono nel database:

| Valore | Dove nasce |
|---|---|
| `AI_GENERATED` · `USER_EDITED` | i due canonici (`lib/content/provenance.ts`) |
| `AI` · `USER` | default del database e di `lib/sandbox/seed.ts` |
| `DETERMINISTIC` | `lib/trends/engine.ts` (4 punti), `lib/sandbox/seed.ts` (2) |
| `CATALOG_SEED` | `lib/sandbox/seed.ts` |
| `WEBSITE` | fatti di business (`lib/brand-intelligence/enrich.ts`) |

**Conseguenza diretta sul tuo requisito:** scrivere `Creator` dentro `provenance` farebbe
**fallire l'approvazione** di quel contenuto, perché `assertApprovalAllowed` ammette solo i due
valori canonici. Non è un dettaglio da sistemare dopo: è la prima cosa da decidere.

### Fatto 3 — chi mostra l'etichetta traduce solo quattro valori, e ne stampa altri grezzi

`lib/ux/status.ts`:

```ts
if (value === "USER_EDITED" || value === "USER" || value === "USER_CONFIRMED") return "Origine: il CEO (utente)";
if (value === "AI_GENERATED" || value === "AI")                          return "Origine: AI";
if (value === "")                                                         return "Origine: non dichiarata";
if (value === "DETERMINISTIC")                                           return "Origine: sistema (nessuna AI)";
return `Origine: ${provenance}`;   // <- qualunque altro valore esce GREZZO
```

L'ultima riga è il difetto da chiudere: `CATALOG_SEED` e `WEBSITE` finiscono a schermo **così come
sono**, in maiuscolo tecnico. E il tuo `nomeagente (ai)` esisterebbe solo se il nome **esiste nel
dato** — non si può inventare in etichetta.

Si vede in `app/(dashboard)/library/page.tsx`, riga 408: la Libreria prende le origini delle
varianti di un'idea e le rende uniche. È **l'unico posto** dove l'etichetta arriva a schermo.

### Fatto 4 — i nomi che mi avevi dato non esistono come ruoli dell'app

Avevi indicato `Creator` e `Strategist` come esempi di ruoli interni. Verificato nel codice:

| Nome | Esiste? | Dove |
|---|---|---|
| `Creator` | **sì** | `lib/assistant/system-prompt.ts:71` — «Conversational Creator: descrivi cosa vuoi» |
| `Strategist` | **no** | zero occorrenze in `lib/` e `app/` |
| `Stratega AI` | **sì** | stesso file — ma è un'**area**, non chi scrive il contenuto |
| `Content Studio` | **sì** | «Area operativa sul contenuto già salvato: … crea varianti piattaforma» |
| `Pilota automatico` · `BrightBean Studio` · `Brand DNA` | **sì** | aree dell'app |

E **non esiste un registro degli agenti**: nessun elenco di nomi nel codice. Quello che esiste sono i
**moduli che generano** — `lib/content/creator/generate.ts`, `lib/content/studio/run.ts`,
`lib/ai/strategist.ts`, `lib/autopilot/autonomous-engine.ts`, `lib/campaigns/builder.ts` — e le
**aree dell'interfaccia** che l'utente vede.

**Quindi «enumera i ruoli dal codice» non è un comando: è una scelta.** Va deciso *quale* insieme di
nomi usare, perché il codice ne offre due, e sono diversi:

- i **moduli che generano** (7-8 nomi tecnici): preciso, ma in interfaccia si legge male;
- le **aree dell'app** (Creator, Content Studio, Pilota automatico, …): leggibile, ed è quello che
  avevi in mente — ma alcune aree non generano contenuto, e vanno escluse.

### Fatto 5 — e una correzione al piano della milestone

Il piano diceva: «un `DETERMINISTIC` che il dominio non ammette ancora». **È falso**, e l'ho
verificato: `lib/ux/status.ts` lo gestisce già, con l'etichetta «Origine: sistema (nessuna AI)».
Il valore che il dominio non ammette è un altro: è **qualunque valore diverso dai due canonici di
`provenance.ts`**, e riguarda anche gli altri cinque. La frase va corretta nel piano della milestone.

## 3. Cosa consiglio

**Un campo nuovo per il nome, e `provenance` che resta quello che è.**

1. **Non toccare `provenance`.** È il campo su cui poggia la regola «non si approva un contenuto di
   cui non si sa l'origine» (`AMF-01`, un controllo di sicurezza, non un'etichetta). Allargarlo per
   farci entrare un nome **indebolisce un cancello**.
2. **Aggiungere `generatedBy String?`** a `ContentVariant`: il nome dell'agente, **nullable**, perché
   il contenuto vecchio non ce l'ha e non si inventa. L'etichetta diventa:
   - `generatedBy` valorizzato → `Origine: Creator (ai)`;
   - `provenance = USER_EDITED` → `Origine: il CEO Bolognini (utente)` (come hai confermato);
   - `provenance = AI_GENERATED` **senza** nome → `Origine: AI` (onesto: non si sa quale);
   - nessuno dei due → `Origine: non dichiarata`.
3. **I nomi vengono da una costante unica**, in un file solo — come `VARIANT_PROVENANCE_VALUES` fa
   per la provenienza. Chi genera **dichiara** chi è; non si deduce a posteriori.
4. **I valori grezzi si traducono**: `CATALOG_SEED` e `WEBSITE` oggi escono così come sono. Vanno
   mappati, o dichiarati «Origine: non dichiarata» — mai stampati in chiaro.

## 4. Cosa serve da te

Quattro risposte. La (1) è la più importante, perché decide se si tocca un cancello.

---

## Le quattro decisioni

### (1) Dove vive il nome dell'agente

- **(a) Campo nuovo `generatedBy`** — `provenance` resta la regola di approvazione, il nome è dato
  in più. *Consigliata.* Costa una migrazione e un campo da riempire dove si genera.
- **(b) Dentro `provenance`** — `Creator`, `Content Studio`… come valori. Semplice, ma
  `assertApprovalAllowed` va allargato, e **ogni valore nuovo diventa approvabile**: il cancello si
  indebolisce.
- **(c) Una tabella degli agenti** — i nomi in una tabella a parte, referenziata. Più rigoroso, più
  lavoro, e oggi non c'è nessun registro da cui popolarla.

### (2) Quali nomi

- **(a) Le aree dell'app che generano contenuto** — `Creator`, `Content Studio`, `Pilota
  automatico`, e le altre verificate. *Consigliata*: è quello che hai chiesto, si legge in
  interfaccia, e ogni nome ha un posto nel codice che lo dimostra.
- **(b) I moduli che generano** — nomi tecnici, precisi, illeggibili per chi guarda.
- **(c) Un elenco nuovo** — si inventano nomi di ruolo. Non consigliata: sarebbero nomi senza
  codice dietro, e fra sei mesi nessuno saprebbe più chi è chi.

### (3) Il contenuto vecchio

- **(a) `Origine: non dichiarata`** — onesto, e la funzione lo già sa fare. *Consigliata.*
- **(b) Si riempie a posteriori** da una regola (per esempio: `AI_GENERATED` → `Creator`).
  **Sconsigliata**: sarebbe un nome inventato dal sistema su un contenuto di cui non sa l'autore —
  esattamente il difetto che `AMF-103` ha corretto il 7 ottobre.

### (4) Il formato del contenuto scritto da te

Confermato: resta `il CEO Bolognini (utente)` (la tua risposta dell'11 ottobre).

---

## Obiettivo

Che ogni contenuto mostri **chi l'ha prodotto**, con un nome verificabile; e che i nomi vengano da un
**elenco unico** nel codice, non da stringhe sparse.

## Ambito

```text
write_scope previsto:
  - 3. AD-Marketing-Factory/prisma/          (la migrazione)
  - 3. AD-Marketing-Factory/lib/content/     (il generatore e la costante dei nomi)
  - 3. AD-Marketing-Factory/lib/ux/          (l'etichetta)
  - 3. AD-Marketing-Factory/app/             (la Libreria)
```

## Card coinvolte

| Card | Perche' | Task type |
|---|---|---|
| `lb-brand-identity` | decide **quali** nomi si mostrano al cliente: è identità di marca | `identity` |
| `backend` | il campo, la migrazione, il generatore | `business_logic` |
| `frontend` | l'etichetta e la Libreria | `frontend_implementation` |
| `qa` · `review` | i gate, indipendenti da chi scrive | — |

## Gate e indipendenza

| Gate | Owner dell'evidenza |
|---|---|
| Code Review | `review` |
| QA | `qa` |
| Brand | `lb-brand-identity` — i nomi visibili al cliente sono una scelta di marca |

## Decisioni richieste al CEO

Le quattro qui sopra. La (1) e la (2) sono di **Livello 3**: toccano la regola di approvazione e
l'identità di ciò che si mostra a un cliente. Servono **Decision Record**.

## Rischi e dipendenze

- **Toccare `provenance` indebolisce un cancello** (`AMF-01`): è il rischio principale, ed è il
  motivo del consiglio (1a).
- **Il nome va scritto dove il contenuto nasce**, e i punti di generazione sono **almeno otto**: se
  se ne dimentica uno, quel contenuto resta senza nome — e l'etichetta dirà «AI», che è onesto ma
  incompleto.
- Dipende dallo **sprint 5** della milestone 3 (decisioni di prodotto): prima si sa cosa vende, poi
  come si firma.

## Costo previsto

Fascia deterministica. Una migrazione, una costante, una funzione di etichetta, gli otto punti di
generazione. Nessuna spesa, nessuna ricerca esterna.

## Fuori scope

- le **altre** tre decisioni di prodotto (il punteggio non nullable, i due percorsi paralleli, la
  terza etichetta): restano nello sprint 5;
- **non** si tocca la regola di approvazione: se si sceglie (1b), è una decisione con il suo verbale,
  non una conseguenza.

## Decisione ricevuta dal CEO — 2026-10-11

**Decise tutte e tre le domande, cosi':**

1. **(1a) Campo nuovo `generatedBy`** — `provenance` resta la regola di approvazione, il nome e' un
   dato in piu'. Il cancello `AMF-01` **non si allarga**.
2. **(2a) Le aree dell'app che generano contenuto** — `Creator`, `Content Studio`, `Pilota
   automatico` e le altre verificate nel codice: nomi leggibili, ognuno con un posto nel codice che
   lo dimostra.
3. **(3a) Il contenuto vecchio resta `Origine: non dichiarata`** — non si inventa un autore a
   posteriori: sarebbe il difetto che `AMF-103` ha corretto il 7 ottobre.
4. **(4) Il contenuto scritto dal CEO resta `il CEO Bolognini (utente)`** — confermato.

**Cosa manca per eseguirle.** Lo **sprint 6** della milestone 3 (decisioni di prodotto), e un
`Decision Record`: la (1) tocca la regola di approvazione e la (2) decide cosa si mostra a un
cliente — sono di **Livello 3**. La migrazione del database e' il primo atto.

**E una conseguenza da dire.** Il campo `generatedBy` va riempito **dove il contenuto nasce**, e i
punti di generazione sono **almeno otto** (verificati: `lib/content/creator/generate.ts`,
`lib/content/studio/run.ts`, `lib/ai/strategist.ts`, `lib/autopilot/autonomous-engine.ts`,
`lib/campaigns/builder.ts`, `lib/marketing-intelligence/persist.ts`,
`lib/marketing-health/recommendations.ts`, `lib/sandbox/seed.ts`). Se se ne dimentica uno, quel
contenuto resta senza nome — e l'etichetta dira' `Origine: AI`, che e' onesto ma incompleto. **Il
controllo che lo rende eseguibile**: una prova che fallisce se un percorso di generazione scrive un
contenuto senza dichiarare chi e'.

---

## Approvazione

```yaml
approvato_da: CEO
data_approvazione: "2026-10-11"
note: "Campo nuovo `generatedBy`; nomi dalle aree dell'app che generano; contenuto vecchio «non dichiarata»; il testo del CEO resta `il CEO Bolognini (utente)`."
```
