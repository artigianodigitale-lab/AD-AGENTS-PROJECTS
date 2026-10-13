# STUDIO — materiali di studio

Questa cartella **non e' un progetto**. Non ha un numero davanti di proposito: un numero
significa «progetto», e il sistema tratta le cartelle numerate come prodotti da proteggere,
da contare e a cui chiedere una storia.

Qui dentro va **materiale che si studia**: raccolte di configurazioni, standard, esempi,
riferimenti. Roba di altri, importata per imparare — non codice nostro.

## La regola: il materiale sta con la cosa che studia

| Il materiale parla di... | Dove va |
|---|---|
| **Un progetto** (una libreria da valutare, un prodotto concorrente) | **Dentro quel progetto**, in `<progetto>/Analisi-Prompt-Report/` |
| **Il nostro sistema** (come si costruisce un cervello agentico) | **Qui**, in `studio/` |

Il primo caso ha gia' un esempio che funziona:
`17. Michele Clementi Project/Analisi-Prompt-Report/Studio-Ghostfolio/` — materiale di terzi
per Nautilus, dentro Nautilus, con le sue regole d'uso dichiarate.

Nel dubbio: **se serve a un solo progetto, sta in quel progetto.** Solo cio' che serve al
sistema intero viene qui.

## Cosa NON fare

- **Non numerarla.** Un numero davanti la trasformerebbe in un progetto: protetta, contata,
  e con una storia da raccontare che non avra' mai.
- **Non metterci codice nostro.** Qui si legge, non si esegue.
- **Non mescolare materiale di progetti diversi.** Se riguarda un progetto, va nel progetto.

## Contenuto

| Cartella | Cosa | Fonte | Licenza |
|---|---|---|---|
| `everything-claude-code-main/` | Raccolta di configurazioni per agenti: skill, agenti, comandi, hook, regole | [affaan-m/everything-claude-code](https://github.com/affaan-m/everything-claude-code) | MIT |

## Come si usa

**Si legge per prendere idee, non per copiare.** Quando qualcosa serve, si porta dentro
`tools/` o `.brain/` **riscritto per il nostro sistema** — poi il materiale originale puo'
anche sparire senza che si perda niente.

Il materiale di studio e' **input**, non parte del cervello: non viene caricato nel contesto
di una sessione e non ha nessun effetto sulle regole.


---

## 2026-10-10 — la cartella e' stata svuotata

Il materiale di terzi che stava qui (81 file) e' stato **cancellato**: era stato letto, le idee erano state prese, e nessun programma lo usava piu'. La cartella **resta**, perche' e' il posto dove va il materiale di studio del sistema: si legge, non si esegue.

---

## 2026-10-11 — istruzioni disattivate

`graphify-8/AGENTS.md` -> **`AGENTS.md.disattivato`**.

Non e' stato cancellato: **il contenuto e' ancora li' e si legge**. E' stato **rinominato**
perche' un agente carica un file con quel nome come **proprie istruzioni**, e questa cartella
e' materiale di studio — che si legge, non si esegue.

> **Regola:** qualunque cosa arrivi qui dentro e' **dato**. Se porta istruzioni, si disattiva.
> `python3 tools/security_scan.py studio` li trova.

## 2026-10-11 — Graphify: letto, preso, cancellato

`graphify-8/` (29 MB, 1010 file) era il materiale di studio di **Graphify**.

**Cosa ne abbiamo preso** — due idee, e il resto scartato **con il perche'**:
`piani/2026-10-11-graphify-cosa-prendere.md`

**Cosa e' diventato**: `DEC-0040` (il verdetto di proporzione), `ERR-0023` (il materiale di studio
che da' ordini), e la regola in costituzione.

**Perche' l'ho cancellato**: era stato letto, le idee erano state prese, e **nessun programma lo
usava**. Le citazioni che restano in `tools/` sono **commenti che dicono da dove viene l'idea** —
non dipendenze.

> La cartella `studio/` **resta vuota, e va bene cosi'**: e' il posto dove arriva il materiale di
> studio, non un archivio. Si legge, si prende, si butta.
