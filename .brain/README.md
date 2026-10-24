# .brain — il cervello di AD Projects

Tutto ciò che rende operativa la governance vive qui. Le posizioni globali di DSH
**puntano** a questi file con symlink: si modifica in un posto solo e la modifica
vale in ogni chat e in ogni workspace, senza copie da tenere allineate.

```text
.brain/
  COSTITUZIONE.md          -> symlink da ~/.dsh/AGENTS.md
  skills/
    ad-kickoff/            porta d'ingresso: richiesta -> metodo -> milestone -> CEO -> sprint
    ad-milestone/          milestone e sprint: il prompt prima, il report alla chiusura
    ad-evolution/          dovere di analisi evolutiva: cerca il metodo migliore, propone
    ad-agent-org/          regolamento operativo
    ad-agent-cards/        come si sceglie una card
    ad-task-contract/      come si scrive e valida un contract
    ad-quality-gate/       evidenze e verdetto ACCEPT / REJECT
                           -> symlink da ~/.agents/skills/ad-*
  plugin/
    enforce-contract/      plugin cordis: blocca le scritture non coperte
                           -> montato da ~/.dsh/profiles/web/cordis.patch.yml
```

**Sette skill, e devono restare sette nella costituzione.** Se una skill esiste ma non e'
nominata nel livello che si carica sempre, per un agente nuovo non esiste: e' successo con
`ad-milestone`, che e' rimasta fuori dalla lista per un giorno intero.

## I ganci globali

| File globale | Punta a | Effetto |
|---|---|---|
| `~/.dsh/AGENTS.md` | `.brain/COSTITUZIONE.md` | la costituzione entra in **ogni** sessione, qualunque sia il workspace |
| `~/.agents/skills/ad-*` | `.brain/skills/ad-*` | le skill sono nel catalogo di **ogni** sessione; il corpo si carica a chiamata |
| `~/.dsh/profiles/web/cordis.patch.yml` | `.brain/plugin/enforce-contract/index.mjs` | l'enforcement agisce sulla sessione |

**Perché il plugin è nel patch di profilo e non nel layer di home.** Il layer di home
(`~/.dsh/cordis.patch.yml`) è previsto per valere su ogni profilo, ma una sessione già avviata
non lo compone se il file non esisteva al momento dell'avvio. La riga sta quindi nel patch di
profilo, che è quello composto. Se un giorno il layer di home viene creato **prima** di avviare
DSH, il mount si può spostare lì e togliere da qui — mai in entrambi, perché due righe con lo
stesso `id` monterebbero il plugin due volte.

Perché i symlink e non delle copie: un file duplicato diverge. La governance è
una sola, e questi tre ganci la rendono raggiungibile da fuori senza duplicarla.

**Il nome `COSTITUZIONE.md` è deliberato**: se si chiamasse `AGENTS.md` dentro
`.brain/`, il plugin delle istruzioni lo caricherebbe una seconda volta come
istruzione annidata, raddoppiando il contesto a ogni richiesta.

## Come si usa

Apri una chat DSH e chiedi di lavorare su un progetto, esistente o nuovo. La
skill `ad-kickoff` guida la sequenza:

```text
RICHIESTA        -> proposta da verificare, non un ordine (nemmeno dal CEO)
COMPRENSIONE     -> cosa vuole ottenere davvero
RICERCA          -> esiste un modo migliore, piu' scalabile, piu' affidabile?
CARD             -> python3 tools/cards.py match <task_type>   (nessun match -> STOP)
RISPOSTA         -> si risponde al CEO PRIMA di fare
ANALISI DI AVVIO -> cosa serve, per intero, per arrivare a prodotto finito
MILESTONE        -> l'analisi DIVENTA una milestone con i suoi sprint
CONSENSO         -> il CEO approva le MILESTONE, non "il lavoro"
SPRINT           -> si apre lo sprint 1 (PROMPT.md)
CONTRACT         -> contratti/<task_id>.yaml, con milestone e sprint
ESECUZIONE       -> un esecutore -> evidenze -> gate -> REPORT.md dello sprint
CHIUSURA         -> ACCEPT / REJECT; lo sprint successivo riparte dal passo SPRINT
```

Fino al contract, il plugin **blocca** ogni scrittura nelle cartelle prodotto, negli
artefatti di governance e i comandi shell che le modificano. Il blocco non e' un guasto: e'
la regola «un progetto non si tocca se non e' chiamato».

**L'analisi e' leggere; la milestone e' scrivere.** Un agente puo' leggere un progetto senza
autorizzazione — anzi, deve, perche' l'analisi nasce da li'. Cio' che non puo' fare e'
scriverci: il validatore rifiuta un contract su una cartella prodotto che non dichiari
`milestone` e `sprint`, e rifiuta anche se lo sprint dichiarato non ha il suo `PROMPT.md`
(invariante 13).

## Cosa non è il cervello

- Non è un agente: non parla, non decide, non ha autonomia. È il testo e il
  codice che gli agenti leggono.
- Non sostituisce i 12 documenti normativi della root: li rende eseguibili e li
  tiene a portata di mano.
- Non concede permessi. Card, contract e `write_scope` restano l'unica fonte di
  autorizzazione.

## Verifica

```sh
# i ganci puntano al cervello?
readlink -f ~/.dsh/AGENTS.md
readlink -f ~/.agents/skills/ad-agent-org

# la logica è corretta?
python3 tools/tests/test_ad_org.py
node .brain/plugin/enforce-contract/test.mjs

# il plugin è in composizione?
node <runtime>/node/bin/node <runtime>/node_modules/@deepseek-ai/dsh/lib/bin.js \
  --profile web --dump-config | grep -A2 ad-enforce-contract
```

## Modificare il cervello

Il cervello e gli strumenti sono **artefatti di governance**: protetti come le cartelle
prodotto, ma con un raggio d'azione piu' ampio. `.brain/` e' symlinkato in `~/.dsh/AGENTS.md`
e nelle skill globali, ed e' montato nel profilo DSH: una scrittura qui cambia cosa fanno
**tutti** gli agenti, in **ogni** sessione, anche fuori da AD Projects.

Quindi si modificano come tutto il resto — contract attivo **e** marcatore del CEO in
`approvazioni/`:

```sh
python3 tools/contract_scope.py check "tools/ad_scope.py"   # esce 1 senza contract
```

Restano liberi `contratti/` e `approvazioni/`: sono l'**input** dell'autorizzazione, e
proteggerli impedirebbe di creare il primo contract.

**Il contract che autorizza il lavoro sulla governance non si rinnova da soli.** L'invariante 7
dice che un agente non modifica il proprio permesso di scrittura: se potesse allungarselo,
il permesso sarebbe decorativo. Si apre per una lavorazione e si chiude quando e' finita.

- **Costituzione e skill**: si modificano qui. Le posizioni globali le leggono;
  il catalogo delle skill si aggiorna senza riavvio, le istruzioni alla prima
  richiesta successiva.
- **Plugin**: una modifica a `index.mjs` **non** viene ricaricata a caldo, perché
  Node tiene in cache i moduli ESM per URL. Per attivarla serve un riavvio di
  DSH. I cambi di configurazione e di composizione, invece, si applicano subito.
- Ogni modifica sostanziale al cervello ha un Decision Record in `DECISIONI/`.

## Stato al 2026-10-08

Il sistema e' operativo: enforcement attivo su progetti e governance, marcatore di
approvazione obbligatorio, milestone e sprint imposti dal validatore, registro drift con
nove voci, tre scanner di sicurezza indipendenti in `~/.local/bin`.

In lavorazione: `GOV-000`, il contract che autorizza le modifiche al cervello — scade
l'8 novembre e non si rinnova da solo.
