# Lavori sul cervello — le task

```yaml
data: 2026-10-10
stato: in attesa del CEO
livello: 3
```

## Cosa e' questo documento

Le task di lavoro emerse dalla revisione del 2026-10-08/10. Ognuna dice **cosa si costruisce**,
**perche'**, **cosa produce** e **da cosa dipende**. Il CEO approva le task, non «il lavoro»:
anche quando dice «procedi», la prima cosa che si apre e' una sola.

**Contesto di autorizzazione**: i lavori toccano `.brain/` e `tools/`, coperti dal contract
attivo `GOV-000` (scade 2026-11-08). Le task su **progetti** richiedono un contract a se'.

---

## T1 — Il registro degli errori  · **FATTA** (DEC-0029, 2026-10-10)

**Cosa.** Una cartella `errori/` append-only. Ogni voce risponde a tre domande:

```yaml
cosa_e_fallito:   "ho scritto una data nel futuro in un marcatore"
cosa_l_ha_risolto: "il controllo dopo la scrittura, con block"
cosa_l_avrebbe_preso: "lo stesso controllo — ma non esisteva"
diventa: controllo | nota | verbale
dove: ".brain/plugin/enforce-contract/index.mjs"
```

**Perche'.** E' il meccanismo che fa **evolvere** il sistema, ed e' l'unica cosa che manca del
tutto: oggi zero. La prova che serve: il 2026-10-08 ho scritto in un verbale che le date
inventate erano un errore, e **l'ho rifatto altre due volte**. Una regola scritta non cambia il
comportamento. **Un controllo che fallisce si'.**

**Produce.**
- `errori/README.md`, `errori/_TEMPLATE.yaml`
- La regola in costituzione: **una voce senza `cosa_l_avrebbe_preso` e' incompleta**
- Il rito: un momento periodico in cui gli errori che si ripetono diventano controlli

**Dipende da.** Niente.
**Pronta.** Si.

---

## T2 — Il Blueprint  · **FATTA** (DEC-0030, 2026-10-10)

**Cosa.** Un documento per progetto in `<progetto>/Analisi-Prompt-Report/BLUEPRINT.md`, in due
parti: **scritta a mano** (cos'e' il progetto, due righe) e **generata** dai registri (a che
punto e', la storia, chi puo' scrivere, le prove, le discrepanze aperte).

**Perche'.** Oggi per capire un progetto servono cinque o sei file. E un Blueprint **scritto a
mano** sarebbe la diciottesima cosa che invecchia — come `comunicazioni/` e `REQUISITI/`, due
registri progettati, mai usati, e oggi vuoti.

**Produce.**
- `tools/blueprint.py` — genera dai registri (i dati ci sono gia')
- La regola in costituzione: ogni progetto ha il suo Blueprint
- **Il controllo che lo tiene onesto**: rigenera e confronta la parte generata. Se qualcuno
  scrive a mano dentro, o se non e' aggiornato dopo una chiusura, **e' un errore**

**Dipende da.** Niente per costruirlo. Per **applicarlo** ai 17 progetti serve un contract a
progetto: si fa quando li si tocca, chiudendo i passi.

**Pronta.** Si.

---

## T3 — Le prove comportamentali  · **FATTA** (DEC-0031, 2026-10-10)

**Cosa.** Prove che verificano **azioni**, non risultati:

- dato un compito poco chiaro, l'agente **chiede** invece di tirare a indovinare?
- quando nessuna scheda copre il compito, **si ferma**?
- prima di dire «fatto», **esegue il controllo**?
- scrive **nel posto giusto**?

**Perche'.** Oggi abbiamo **175 controlli sui programmi** e **zero sul comportamento**. Non
sappiamo se stiamo migliorando. La fonte: [Google, *Anatomy of Harness Engineering*](https://developers.googleblog.com/en/the-anatomy-of-harness-engineering-how-to-evaluate-iterate-and-guard-ai-coding-agents/)
— *«lo scopo di una suite di valutazione non e' festeggiare il 2% in piu', e' darti la certezza
che una modifica non abbia reso l'agente complessivamente peggiore»*.

**Produce.**
- `evals/` con le prove, e un programma che le esegue
- **Il numero**: quante volte l'agente ci azzecca al primo colpo — mostrato nel Blueprint
- La regola: si parte da **un solo** modo di sbagliare, scelto fra quelli **realmente accaduti**

**Dipende da.** T2 (il numero ha bisogno di un posto dove vivere).
**Pronta.** Dopo T2.

---

## T4 — Camoufox condiviso  · **FATTA** (2026-10-10)

**Cosa.** Promuovere lo strumento gia' esistente in `3. AD-Marketing-Factory/scripts/` a
strumento del cervello: `tools/ricerca.py`.

**Perche'.** **Esiste gia'** e l'abbiamo visto funzionare: il fetch normale si e' fermato davanti
a Cloudflare, camoufox no. Serve a tutti, non a un progetto.

**Produce.**
- `tools/ricerca.py` — prova la via leggera, e **solo se la pagina e' fatta in JavaScript** o
  bloccata parte il browser
- Una memoria delle pagine: la stessa pagina non si scarica due volte
- **Le regole su cosa si puo' scaricare**: `robots.txt`, termini d'uso, niente muri di login,
  niente dati personali. Una capacita' potente senza regole e' un problema

**Dipende da.** Niente.
**Pronta.** Si.

---

## T5 — La squadra di marca  · **FATTA** (DEC-0032, 2026-10-10)

**Cosa.** Sei schede piu' chi le coordina, e la procedura che le mette in fila.

| Scheda | Cosa fa |
|---|---|
| `brand-strategist` | sceglie il modello, tiene la sequenza |
| `jobs-analyst` | i lavori da fare — **il primo passo** |
| `persona-researcher` | proto-personas **falsificabili** |
| `competitor-analyst` | Porter + mappa + smontaggi |
| `archetype-analyst` | la tensione, **dedotta dagli altri**, non scelta |
| `positioning-writer` | la frase, e il test dal lato cliente |

**I metodi, con le fonti:**
- **Identita'**: prisma di Kapferer (B2C emotivo) **o** sistema di Aaker (B2B, razionale, legato
  al prodotto) — la regola di scelta viene dalla [cattedra di ricerca di Kapferer](https://chaire.marquesetvaleurs.org/wp-content/uploads/2018/01/identite_marque.pdf)
- **Due modelli, non uno**: com'e' oggi e come la vuoi domani. Entrambi i modelli sono **statici**,
  e la fonte dice esplicitamente di farne due
- **Archetipi**: come tensione, non etichetta. I 12 di Mark & Pearson **non reggono**
  ([tesi Univ. Washington 2021](https://digital.lib.washington.edu/researchworks/items/c15713ba-a19c-4da6-9ca8-2758d42560e1/full))
- **Proto-personas falsificabili**: risposta diretta a [Chapman & Milham](https://www.semanticscholar.org/paper/The-Personas%27-New-Clothes%3A-Methodological-and-a-Chapman-Milham/a6a087be79bd1eecbcbff8e3a02bcdc65411d8f0)
  («non verificabili ne' falsificabili, quindi senza validita' dimostrabile»)
- **Percorso utente accanto alle personas**: dallo [studio 2025](https://arppid2025.org/wp-content/uploads/2025/07/perspectives-on-personas-in-practice.pdf),
  senza, le personas non dicono nulla sul comportamento
- **La prova di Keller**: i quattro gradini — identita', significato, risposta, risonanza

**Produce.**
- Le schede in `AGENT-CARDS-BUSINESS.md`
- La procedura `ad-brand-team`
- La regola: **si attiva solo su chiamata del CEO.** Il motore principale resta lui e il CEO

**Dipende da.** Niente tecnicamente. Ma va **dopo T1**: senza il registro degli errori,
ripeteremo gli stessi sbagli.
**Pronta.** Si.

---

## L'ordine che consiglio

| | Task | Perche' li' |
|---|---|---|
| **1** | **~~T1 errori~~ FATTA** | Chiusa il 2026-10-10 con DEC-0029. Il meccanismo c'e'; ora va usato |
| **2** | **~~T2 Blueprint~~ FATTA** | Chiusa il 2026-10-10 con DEC-0030. Il primo Blueprint vero vive su `3. AD-Marketing-Factory` |
| **3** | **~~T5 marca~~ FATTA** | `ad-brand-team` piu' 3 schede arricchite e 2 nuove |
| **4** | **~~T3 prove~~ FATTA** | Chiusa il 2026-10-10 con DEC-0031. 7 asserzioni, e le regressioni si vedono |
| **5** | **~~T4 camoufox~~ FATTA** | `tools/ricerca.py`: via leggera, browser se serve, cache |

**T1 e T2 insieme** sono le due meta' della stessa cosa: **la cicatrice e la memoria.** Uno
impara dagli sbagli, l'altro ricorda a che punto siamo.

## Fuori ambito

- **Il front-end** su DSH: il CEO ha detto che non e' la priorita'. Una pelle nuova, non un
  sostituto.
- **I 17 progetti**: si toccano uno alla volta, chiudendo i passi, non in blocco.
- **I libri di Aaker, Kapferer e Keller**: non letti. Se devono fondare una decisione, si
  comprano.

## Cosa serve dal CEO

1. **L'ordine va bene?** In particolare: T1 prima di tutto.
2. **Si parte da T1?** E' piccola e si chiude in un passo.
3. **T5 in parallelo o in fila?** Se la vuoi subito, la apro insieme.
