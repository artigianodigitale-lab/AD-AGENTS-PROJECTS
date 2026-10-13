# DEC-0042 — La supercartella e' un repository

```yaml
id: DEC-0042
stato: approvato
livello: 3
data: "2026-10-11"
approver: CEO
supera:
```

## Problema

La macchina di governance — 12 documenti normativi, `.brain/`, `tools/`, i registri — viveva
**senza controllo di versione**. Nessuna storia, nessun ritorno indietro, nessun modo di sapere
cosa e' cambiato e quando. E i 17 progetti numerati **hanno** i loro repository: la macchina che
li governa era la sola cosa senza memoria.

Il CEO: *«e' arrivato il momento di fare un commit git di AGENT AD PROJECT senza i progetti numerati»*.

## Opzioni

1. **Un repository unico che include anche i 17 progetti.** Conseguenza: una storia sola.
   Costo: i progetti hanno **gia'** i loro repository, con le loro storie e i loro segreti — un
   secondo repository sopra crea due verita' per gli stessi file, e `git status` dentro un
   progetto diventa ambiguo. Fonte: e' il difetto che abbiamo appena passato tre giorni a
   correggere — **una cosa, una verita'**.
2. **Un repository per la macchina, con i progetti esclusi uno per uno.** Conseguenza: la
   macchina ha la sua storia, i progetti la loro, e nessuno tocca l'altro. Costo: i progetti
   restano fuori, quindi la macchina non ha la storia di cosa i progetti hanno prodotto.
   Fonte: [Graphify](https://github.com/Graphify-Labs/graphify), che il 2026-10-11 ci ha dato
   l'idea del verdetto che **misura** invece di esentare — qui: l'elenco esplicito misura una
   decisione invece di nasconderla in un pattern.
3. **Non fare nulla** — la macchina resta senza storia. Conseguenza: ogni modifica e' definitiva
   e non verificabile a posteriori; l'unica memoria e' `DECISIONI/`, che racconta **perche'** ma
   non **cosa**. Il costo si paga il giorno in cui qualcosa si rompe e non si sa cosa era prima.

## Evidenze

- **261 file committati, 0 dei 17 progetti** — verificato con `git ls-files | grep -cE '^[0-9]+\.'`
- **17 progetti esclusi uno per uno** in `.gitignore`, non con un pattern: aggiungerne uno
  dev'essere una decisione, non un effetto collaterale
- **`git rev-parse --show-toplevel`** dentro un progetto risponde **il progetto**, non la
  supercartella: le due storie restano separate
- **La scansione dei segreti sui soli file in stage**: 11 segnali, **tutti deliberati** — le
  stringhe finte con cui `security_scan.py` impara a distinguere un segreto da una somiglianza
- **`ERR-0025`, e non era previsto**: il `git init` ha **spento** un controllo di sicurezza.
  `osv-scanner` rispetta `.gitignore`, ha risalito al repository della supercartella, e ha potato
  tutti i progetti: «nessun file di dipendenze» su un progetto con **910 pacchetti**

## Scelta

**Opzione 2.** Repository `main` sulla supercartella, i 17 progetti esclusi.

- **`.gitignore`** con i 17 progetti elencati uno per uno, e i residui di lavorazione
- **`.gitleaks.toml`** che esenta **i valori**, non le posizioni: le stringhe finte usate per
  provare il filtro, con la ragione scritta dentro il file. Un repository che nasce con allarmi
  permanenti **insegna a ignorarli** — e' il difetto di `ERR-0016`, e non si ricrea qui
- **La prima versione usava `.gitleaksignore`** (`file:regola:riga`) ed **era fragile**. Misurato:
  aggiungendo **una riga** in cima a `security_scan.py`, un'esenzione ha smesso di combaciare
  (segnale riapparso) e l'altra e' finita a coprire **la riga accanto**. Spostare le righe fa
  rumore **e** copre la cosa sbagliata. Sostituita: 0 segnali, prima e dopo lo spostamento
- **`--no-ignore`** su `osv-scanner`, con la ragione nel codice

## Conseguenze

- La macchina ha una storia: `git log`, `git diff`, e la possibilita' di tornare indietro
- **Le due storie restano separate**: 13 progetti con il loro repository, 4 senza, e la
  supercartella non tocca nessuno dei due
- **Un controllo di sicurezza era spento e ora si sa**: il primo commit e' stato seguito dalla
  batteria, ed e' li' che e' emerso

## Limiti dichiarati

- **Il repository non ha un remoto.** E' locale: nessun backup fuori dalla macchina, e un
  `rm -rf` li' cancella la storia. **Va deciso se e dove portarlo.** Non l'ho fatto:
  pubblicare e' un invio esterno, e l'invariante 3 dice che ACCEPT non lo autorizza
- **`.gitleaks.toml` e' una benda**: e' il posto dove un segreto vero puo' nascondersi. Le
  esenzioni sono **cinque valori finti**, tutti ricostruibili a mano. Se un giorno servisse
  esentare un valore che **non** si sa ricostruire, quello e' il momento di fermarsi
- **I 4 progetti senza repository restano senza**: se un giorno ne avranno uno, la loro storia
  comincia da zero
- **`git init` cambia il comportamento di strumenti che leggono `.gitignore`.** Ne ho trovato
  **uno** (`osv-scanner`) perche' un test e' fallito. **Non so quanti altri ce ne siano**, e non
  ho un modo di cercarli

## Metrica

File committati: **261**. File di progetto committati: **0**, atteso. Controlli verdi dopo il
commit: **277 + 36**.

## Data di revisione

2026-11-09

## Esito misurato

<Da compilare il 2026-11-09: se il repository ha un remoto, e se qualcuno ha mai fatto un
`git checkout` per tornare indietro.>
