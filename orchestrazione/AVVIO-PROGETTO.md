# Cosa dire a qualsiasi AI che inizia un progetto

Testo pronto da incollare. Vale per ogni AI, in ogni programma, su questa macchina.

---

**Questa macchina e' AD-AGENTS-PROJECTS: un motore di governance, non un progetto.** La
cartella del motore **non si tocca**: si legge e si usa, non si modifica. Tu lavori **dentro la
cartella del progetto** (`<numero>. <Nome>/`), e da li' dentro fai tutto.

Regole che devi seguire, in ordine:

1. **Entra nella cartella del progetto e lavora da li'.** Non scrivere in `AD-AGENTS-PROJECTS/`:
   niente `contratti/` di root, niente `DECISIONI/`, `errori/`, `drift/`, `.brain/`, `tools/`.
   Se pensi che serva una modifica al motore, **fermati e chiedila al CEO**: e' un incarico a
   parte, non il tuo.
2. **Importa cio' che ti serve, non copiare il motore.** I modelli si copiano nel progetto:
   `contratti/_TEMPLATE.yaml` e `approvazioni/_TEMPLATE.yaml` in `<progetto>/governance/`;
   `milestone/_TEMPLATE-*.md` nella cartella del progetto. Le skill e i comandi del motore si
   usano dalla loro installazione, non si duplicano.
3. **Il registro del progetto sta nel progetto**: `<progetto>/governance/contratti/<gruppo>/` e
   `<progetto>/governance/approvazioni/<gruppo>/`, ed e' versionato nel repository del progetto.
   Il collegamento che dalla root del motore rende visibile il registro lo crea la macchina
   (`python3 tools/progetto.py registro "<progetto>"`): tu scrivi solo i file veri, dentro il
   progetto, e chiedi alla macchina di collegarli.
4. **La macchina resta intatta e coerente**: non rinominare, non spostare, non "aggiustare" file
   del motore. Se qualcosa non torna, **registralo e segnalalo** con i fatti (comando + numero),
   senza correggerlo.
5. **La sequenza non si salta**: richiesta -> comprensione -> ricerca -> card
   (`python3 tools/cards.py match <task_type>`) -> risposta al CEO -> milestone approvata ->
   contract -> sprint aperto -> **un solo esecutore** -> evidenze -> gate indipendente ->
   rapporto in `<progetto>/Analisi-Prompt-Report/Milestone N/Sprint M/REPORT.md`.
6. **Senza il consenso del CEO sulle milestone non parte niente.** La richiesta del CEO non e'
   un ordine: e' una proposta da verificare; se trovi un metodo migliore, proponilo con fonti,
   costi e rischi.
7. **Una chat per passo, e non toccare i progetti degli altri.** Se due sessioni lavorano
   insieme, ognuna sta nel suo progetto; i registri della macchina li scrive solo chi ne ha
   l'incarico. Alla chiusura di un passo, il CEO lancia
   `python3 tools/milestone.py consegna "<progetto>"`: scrive `CONSEGNA.md` accanto a
   `PROMPT.md` e `REPORT.md`. La chat **nuova** legge **tre file** — `CONSEGNA.md`, il
   `PROMPT.md` del passo nuovo, il `REPORT.md` di quello chiuso — e non rilegge la storia
   vecchia. Una conversazione lunga rallenta e peggiora il lavoro: il taglio sta al confine del
   passo, dove il lavoro e' verificato (DEC-0089).
8. **Le prove si misurano, non si dichiarano.** "Controlli verdi" senza un file in `evidenze/` e
   un verdetto non e' un lavoro chiuso. Chi produce l'artefatto non valida il proprio gate.
9. **Gli id non si scelgono: si prenotano** (`errori.py nuovo`, `verbali.py nuovo`). E se una
   regola non c'e', non te la inventi: chiedi.
10. **Gli orari si leggono in UTC, e il fuso e' un dato.** Un orario scritto in un marcatore,
    in un'evidenza o in un rapporto e' **UTC** con l'offset dichiarato (`2026-11-17T07:15:00+01:00`),
    non l'ora locale "presunta": la macchina puo' girare in un fuso diverso, e un orario senza
    offset non e' confrontabile. Un orario nel futuro e' un errore, non un dettaglio
    (`ERR-0079`, `ERR-0073`): chi scrive un marcatore scrive l'ora vera in cui il CEO ha
    approvato, non l'ora prevista del passo.

Se segui queste regole, il motore non si rompe e il progetto resta autonomo. Se hai un dubbio su
un confine: **fermati e chiedi**, invece di scegliere.

---

Riferimenti (per chi vuole i dettagli): `DEC-0081` (la regola), `DEC-0080` (il registro nei
progetti), `DEC-0089` (la consegna fra passi), `orchestrazione/PROTOCOLLO-MULTI-SESSIONE.md`
(piu' chat in parallelo).
