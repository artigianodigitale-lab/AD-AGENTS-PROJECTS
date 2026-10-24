---
name: ad-milestone
description: >-
  Milestone e sprint di un progetto AD Projects. Dopo il consenso del CEO il
  lavoro si pianifica in milestone, e ogni milestone in sprint: all'apertura si
  scrive il prompt dello sprint, alla chiusura si rilascia il report di cosa e'
  stato fatto e come. La storia resta documentata dentro il progetto. Usa quando
  un progetto approvato passa all'esecuzione.
whenToUse: >-
  Dopo il consenso del CEO, quando il lavoro di un progetto passa dalla
  pianificazione all'esecuzione, e a ogni apertura o chiusura di sprint.
---

# Milestone e sprint

Root: `/home/luka/Scrivania/AD Projects/`
Modelli: `milestone/`
Strumento: `tools/milestone.py`

## La regola

Un progetto non e' una sequenza di chat. E' una **storia documentata**: milestone,
sprint, prompt e report, tutto dentro la cartella del progetto.

```text
<progetto>/
  Milestone 1/
    REPORT.md          report della milestone, step by step
    Sprint 1/
      PROMPT.md        scritto PRIMA di eseguire
      REPORT.md        rilasciato alla CHIUSURA
    Sprint 2/
      PROMPT.md
      REPORT.md
  Milestone 2/
    ...
```

- **Non si salta.** Uno sprint senza `PROMPT.md` non e' mai stato aperto; senza
  `REPORT.md` non e' chiuso, e il successivo non parte.
- **Un prompt per sprint, un report per sprint.** Il prompt dice cosa deve
  esistere; il report dice cosa e' stato fatto **e come**.
- **Il "come" e' la parte che conta.** Il report non e' un riassunto per il CEO:
  e' la memoria tecnica che serve a chi riprende il lavoro fra sei mesi.
- La numerazione e' **contigua**: `Milestone 1, 2, 3`, e dentro `Sprint 1, 2, 3`.

## Quando si apre una milestone

Dopo il consenso del CEO e dopo l'**analisi di avvio** (vedi `ad-kickoff`):
l'analisi stabilisce cosa serve per arrivare a prodotto finito, e da li' si
decide quante milestone servono. Non prima: le milestone si pianificano su una
richiesta approvata.

## Il ciclo di uno sprint

```text
1 APERTURA   python3 tools/milestone.py new-sprint "<progetto>" <milestone> --objective "..."
             si completa PROMPT.md: contesto, risultato atteso, criteri di
             accettazione, input, vincoli, gate
2 CONTRACT   il contract dello sprint in contratti/, con write_scope sui percorsi
             che lo sprint tocca (serve anche il marcatore in approvazioni/)
3 ESECUZIONE un solo esecutore, poi evidenze
4 CHIUSURA   si scrive Sprint M/REPORT.md dal modello: cosa, come, evidenze,
             scostamenti, cosa passa avanti
5 VERIFICA   python3 tools/milestone.py check "<progetto>"
             solo se non segnala nulla si apre lo sprint successivo
```

## Comandi

```sh
python3 tools/milestone.py check "<progetto>"
python3 tools/milestone.py new-milestone "<progetto>" --goal "..."
python3 tools/milestone.py new-sprint "<progetto>" 1 --objective "..."
```

`check` esce 1 se manca un report, un prompt, o la numerazione ha un buco.

## La guardia

Lo strumento **si rifiuta di scrivere** in una cartella prodotto che nessun
contract approvato copre. Non e' un fastidio: le scritture fatte da uno script non
passano dall'euristica della shell del plugin, quindi il controllo sta dentro lo
strumento. Senza contract e senza il marcatore di approvazione del CEO, `new-milestone`
e `new-sprint` non creano nulla.

## Chiusura di una milestone

Il `REPORT.md` della milestone raccoglie la cronologia step by step e rimanda ai
report degli sprint. La milestone si chiude solo quando:

- ogni sprint ha `PROMPT.md` e `REPORT.md`
- la numerazione e' contigua
- il lavoro e' stato verificato da chi non l'ha prodotto
- le evidenze dei gate richiesti sono depositate
- `milestone.py check` non segnala nulla

Cio' che resta fuori diventa la milestone successiva, o un Decision Record.
