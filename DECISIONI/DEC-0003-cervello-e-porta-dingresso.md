# DEC-0003 — Cervello di AD Projects, porta d'ingresso e enforcement di runtime

```yaml
id: DEC-0003
stato: approvato
livello: 2
data: 2026-10-08
approver: LB-MASTER ORCHESTRATOR (il Lead della sessione), su mandato del CEO
supera: DEC-0002 (che estende senza contraddire)
```

## Problema

Dopo DEC-0002 la catena era eseguibile, ma mancavano tre cose perche' l'idea funzionasse davvero:

1. **Il cervello era sparso.** Costituzione e skill vivevano in `~/.dsh/` e `~/.agents/`, fuori da AD Projects: due posti da tenere allineati, e nessun artefatto versionato con il progetto.
2. **Mancava la porta d'ingresso.** Aprendo una chat e chiedendo di lavorare su un progetto, nulla imponeva la sequenza richiesta: piano, approvazione del CEO, contract. La governance la descriveva come principio, non come procedura eseguibile.
3. **L'enforcement era parziale.** Il plugin copriva `write` ed `edit`, ma non i comandi shell: la via piu' ovvia per toccare un progetto restava aperta.

La specifica del CEO: *un cervello di plugin nella cartella AD Projects, dove aprendo una chat su DSH e chiedendo di lavorare su un progetto preesistente o crearne uno nuovo, il Team di Agenti passando per il CEO inizia a orchestrare il piano di lavoro.*

## Opzioni

1. **Cervello dentro AD Projects con symlink dai ganci globali** — una sola copia, sempre attiva, versionata con il progetto.
2. **Cervello fuori, nei percorsi globali** — funziona, ma resta fuori dal progetto e si duplica.
3. **Copie in entrambi i posti** — due fonti che divergono: scartata.
4. **Non fare nulla** — restano i tre problemi.

## Evidenze

- Verificato che `~/.dsh/AGENTS.md` e' caricato in ogni sessione e in ogni workspace, e che `~/.agents/skills` e' l'unica radice di skill utente condivisa.
- Verificato che entrambi i plugin **seguono i symlink**: la costituzione e le quattro skill, spostate in `.brain/` e collegate con symlink, restano attive. La prova e' nel comportamento osservato: dopo lo spostamento DSH ha emesso gli aggiornamenti delle istruzioni e il catalogo ha continuato a esporre le skill.
- Verificato che una `AGENTS.md` dentro `.brain/` viene caricata **due volte** (globale piu' annidata): il file e' stato rinominato `COSTITUZIONE.md`, e DSH ha emesso la rimozione dell'istruzione duplicata.
- Verificato che HMR ricompone la composizione a caldo: un plugin sonda con effetto collaterale all'import ha scritto il proprio file appena inserito nel patch di profilo.
- Verificato che i moduli ESM restano in cache per URL: una modifica a `index.mjs` non viene ricaricata. Da qui la regola documentata nel README del cervello.
- Verificato che `kind: 'ask'` non viene mai approvato da solo: senza servizio di approvazione, o con policy `never`, diventa `deny`.
- Verificato che il messaggio di `ask` rifiutato e' generico e non riporta il motivo: da qui la modalita' `auto`, che usa `deny` quando l'approvazione non puo' arrivare all'umano.

## Scelta

**Opzione 1**, piu' i due pezzi mancanti.

**Cervello in `.brain/`** con tre ganci che vi puntano: `~/.dsh/AGENTS.md` → `.brain/COSTITUZIONE.md`; `~/.agents/skills/ad-*` → `.brain/skills/ad-*`; `~/.dsh/profiles/web/cordis.patch.yml` → `.brain/plugin/enforce-contract/index.mjs`.

Il terzo gancio sta nel patch di **profilo**, non nel layer di home. Il layer di home e' previsto per valere su ogni profilo, ma una sessione gia' avviata non lo compone se il file non esisteva al momento dell'avvio: verificato, una riga inserita in `~/.dsh/cordis.patch.yml` a sessione avviata non viene importata. Il patch di profilo e' quello composto. Le due posizioni non vanno usate insieme: due righe con lo stesso `id` monterebbero il plugin due volte.

**Porta d'ingresso `ad-kickoff`**: la sequenza `richiesta → classificazione → ricognizione → card → PIANO in piani/ → approvazione del CEO → CONTRACT in contratti/ → esecuzione → evidenze → gate`. Il piano vive in `piani/` ed e' il documento che il CEO legge; il contract, che sblocca le scritture, nasce solo dopo l'approvazione.

**Enforcement esteso alla shell**: `ad_scope.bash_target()` riconosce le mutazioni evidenti. Regola: se il comando nomina un percorso esplicito si controlla quello, altrimenti vale la directory di lavoro; in ogni caso serve un marcatore di mutazione.

## Conseguenze

- Il cervello e' **una sola copia**, dentro il progetto. Modificarlo da `.brain/` cambia il comportamento di ogni chat e ogni workspace.
- La regola "un progetto non si tocca se non e' chiamato" e' ora **imposta**, non solo dichiarata: fino al contract, scritture e comandi mutativi sulle cartelle prodotto vengono bloccati.
- La modalita' predefinita e' `auto`: se l'approvazione puo' arrivare all'umano si chiede, altrimenti si nega **portando il motivo al modello**. Cosi' il blocco e' sempre spiegato.
- 84 controlli Python e 23 controlli del plugin coprono registry, contract, evidenze, ambito e comandi shell, inclusi i casi negativi.
- **Limiti dichiarati, non nascosti**: l'analisi della shell e' un'euristica (un `cd` seguito da una scrittura relativa puo' sfuggirle); i permessi per-card non sono imposti dal plugin ma dal validatore; una modifica al codice del plugin richiede un riavvio di DSH.
- Il `.brain/README.md` documenta mappa, verifica e procedura di modifica.

## Metrica

Percentuale di lavori su progetto aperti con un piano approvato e un contract validato prima della prima scrittura. Atteso: 100%. Si misura ogni 30 giorni.

## Data di revisione

2026-11-07
