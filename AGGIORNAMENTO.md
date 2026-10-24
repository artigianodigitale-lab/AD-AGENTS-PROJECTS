# Aggiornamento

**Per un agente che trova due cartelle: una vecchia (in uso) e una nuova (appena scaricata).**

> **Leggi questo prima di toccare qualsiasi cosa.** Questa cartella è la versione **nuova**.
> Da qualche parte accanto c'è una versione **vecchia**, con dentro il lavoro di una persona.

---

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
