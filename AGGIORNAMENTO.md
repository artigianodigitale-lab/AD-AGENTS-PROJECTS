# Aggiornamento

**Per un agente che trova due cartelle: una vecchia (in uso) e una nuova (appena scaricata).**

> **Leggi questo prima di toccare qualsiasi cosa.** Questa cartella è la versione **nuova**.
> Da qualche parte accanto c'è una versione **vecchia**, con dentro il lavoro di una persona.

---

## Italiano

### La regola che non si viola

```text
IL MOTORE si aggiorna.        I DATI non si toccano MAI.
```

**Un permesso che qualcuno ha scritto ieri non deve sparire perché oggi è uscita una versione.**
Un contratto, un'approvazione, una cicatrice, un verbale: sono il **lavoro** di chi usa questo
motore. Se li sovrascrivi, hai distrutto mesi in un secondo — e la persona non se ne accorge
finché non è tardi.

### Cosa si aggiorna

```
.brain/          le regole, le skill, il plugin
tools/           i comandi
VERSION          la versione
*.md (in root)   i documenti: README, GLOSSARY, COMMUNITY, CONTRIBUTING...
LICENSE NOTICE   licenza e attribuzione
sede.example.yaml  .env.example
```

### Cosa NON si tocca, mai

```
sede.yaml         chi è il CEO, e dove sono i progetti
contratti/        i permessi scritti
approvazioni/     i sì dati
errori/           le cicatrici
DECISIONI/        i verbali
piani/  drift/  evidenze/  REQUISITI/  comunicazioni/
contributi/  evals/  orchestrazione/  studio/
le cartelle numerate        i progetti
```

**Nessuna eccezione. Nemmeno «per allinearli».**

### La procedura, in sei passi

```text
1  GUARDA LE DUE VERSIONI
   Leggi `VERSION` in entrambe le cartelle. Quella nuova è più alta:
   stai per aggiornare. Se sono uguali, fermati e chiedi.

2  CHIEDI CONFERMA ALLA PERSONA
   Di' cosa stai per fare, in due righe: quante cose cambiano nel motore,
   e che i dati non si toccano. **Aspetta un sì.**

3  FA' UN BACKUP
   Copia la cartella vecchia da qualche parte (o almeno `.brain/` e `tools/`).
   Un aggiornamento senza via di ritorno non si fa.

4  CONFRONTA, FILE PER FILE
   Per ogni file del motore: è DIVERSO fra le due versioni?
     - diverso, e la persona NON l'ha modificato  -> prendi quello nuovo
     - diverso, e la persona l'ha modificato      -> NON sovrascrivere
     - uguale                                     -> lascia stare

5  I FILE CHE LA PERSONA HA MODIFICATO
   Non li toccare. **Mostraglieli**, e per ognuno di' in una riga cosa è cambiato
   fra le due versioni. Poi chiedi: «vuoi prenderlo nuovo, tenere il tuo, o
   fonderli?». **La fusione la fai tu**, guardando entrambi — ed è l'unica parte
   di questo lavoro che richiede di capire, non di copiare.

6  DI' COSA HAI FATTO, E COSA RESTA
   Elenca i file aggiornati, quelli lasciati stare, e le domande aperte.
   **La cartella nuova si può cancellare**: ha finito il suo lavoro.
```

### In una riga

> **Il motore si sostituisce, i dati si tengono, e quello che non si può sostituire lo si
> chiede a una persona.**

### Se c'è git

Se la cartella vecchia è un `git clone`, c'è un comando che fa i passi 1, 3, 4 e 6 da solo —
**e non fa mai il passo 5**, perché la fusione è un lavoro da agente:

```bash
python3 tools/aggiorna.py check      # c'e' una versione nuova?
python3 tools/aggiorna.py mostra     # cosa cambierebbe, file per file
python3 tools/aggiorna.py applica    # aggiorna il motore, backup incluso
```

**Se il comando non c'è** (stai aggiornando da una cartella scaricata, e il tuo motore è
vecchio), **questa pagina È la procedura**: segui i sei passi.

---

## English

**For an agent that finds two folders: an old one (in use) and a new one (just downloaded).**

> **Read this before touching anything.** This folder is the **new** version. Somewhere next to
> it there is an **old** version, with a person's work inside.

### The rule that is never broken

```text
THE ENGINE is updated.     THE DATA is NEVER touched.
```

**A permission someone wrote yesterday must not disappear because a version came out today.**
A contract, an approval, a scar, a record: they are the **work** of whoever uses this engine. If
you overwrite them, you have destroyed months in a second — and the person will not notice until
it is too late.

### What is updated

```
.brain/          the rules, the skills, the plugin
tools/           the commands
VERSION          the version
*.md (in root)   the documents: README, GLOSSARY, COMMUNITY, CONTRIBUTING...
LICENSE NOTICE   licence and attribution
sede.example.yaml  .env.example
```

### What is NEVER touched

```
sede.yaml         who the CEO is, and where the projects are
contratti/        the written permissions
approvazioni/     the given yeses
errori/           the scars
DECISIONI/        the records
piani/  drift/  evidenze/  REQUISITI/  comunicazioni/
contributi/  evals/  orchestrazione/  studio/
the numbered folders        the projects
```

**No exceptions. Not even "to line them up".**

### The procedure, in six steps

```text
1  LOOK AT BOTH VERSIONS
   Read `VERSION` in both folders. The new one is higher: you are about to
   update. If they are the same, stop and ask.

2  ASK THE PERSON TO CONFIRM
   Say what you are about to do, in two lines: how much changes in the engine,
   and that the data is not touched. **Wait for a yes.**

3  MAKE A BACKUP
   Copy the old folder somewhere (or at least `.brain/` and `tools/`).
   An update with no way back is not done.

4  COMPARE, FILE BY FILE
   For every engine file: is it DIFFERENT between the two versions?
     - different, and the person did NOT modify it  -> take the new one
     - different, and the person DID modify it      -> do NOT overwrite
     - the same                                     -> leave it alone

5  THE FILES THE PERSON MODIFIED
   Do not touch them. **Show them**, and for each one say in a line what changed
   between the two versions. Then ask: "do you want the new one, to keep yours,
   or to merge them?". **You do the merge**, looking at both — and it is the only
   part of this work that requires understanding, not copying.

6  SAY WHAT YOU DID, AND WHAT REMAINS
   List the files updated, the ones left alone, and the open questions.
   **The new folder can be deleted**: its job is done.
```

### In one line

> **The engine is replaced, the data is kept, and what cannot be replaced is asked of a person.**

### If you have git

If the old folder is a `git clone`, a command does steps 1, 3, 4 and 6 by itself — **and never
does step 5**, because merging is an agent's work:

```bash
python3 tools/aggiorna.py check      # is there a new version?
python3 tools/aggiorna.py mostra     # what would change, file by file
python3 tools/aggiorna.py applica    # updates the engine, backup included
```

**If the command is not there** (you are updating from a downloaded folder, and your engine is
old), **this page IS the procedure**: follow the six steps.
