# DEC-0026 — Via il repository annidato, e i permessi che restano aperti

```yaml
id: DEC-0026
stato: approvato
livello: 2
data: 2026-10-08
approver: CEO
supera:
```

## Problema

Due cose storte, trovate controllando il lavoro sulla chat di Michele Clementi.

**1. Un repository annidato dentro i materiali di studio.** `Studio-Ghostfolio/Ghostfolio/`
porta con se' il `.git` della copia di studio: **12 MB su 42**. E' l'unico `.git` annidato **fra le directory** — gli altri **13 progetti hanno il loro `.git` alla radice**, ed e'
giusto cosi': e' il repository del progetto.

Il progetto `17. Michele Clementi Project` **non ha un repository suo**. Quel `.git` e' solo
quello dei materiali importati, e serve a poco: la storia di Ghostfolio non aggiunge niente a
chi studia il codice.

**2. Due permessi aperti su una tappa chiusa.** `NLT-001` e `NLT-002` sono ancora `active`,
mentre la loro tappa e i loro passi sono **chiusi** e i gate superati. Un permesso che resta
aperto tiene il progetto scrivibile per sempre — e la tappa chiusa dice che non c'e' piu' nulla
da scrivere.

Il secondo problema non e' pericoloso (i permessi erano approvati e limitati al progetto), ma e'
la stessa classe di cose che il CEO ha chiesto di sistemare: **cio' che non serve piu' va chiuso.**

## Evidenze

- `find` su tutta la super cartella: 14 `.git`, **13 alla radice** dei progetti e **1 annidato**
  (quello di Ghostfolio). Distinzione verificata prima di toccare qualunque cosa.
- Il `.git` annidato pesa 12 MB; la cartella che lo contiene 42 MB; **nessuna dipendenza
  installata** dentro (0 `node_modules`).
- `git -C "17. Michele Clementi Project" rev-parse` non risolve: il progetto non ha un repository.
- `NLT-001` e `NLT-002`: `status: active`; `Milestone 1/REPORT.md` e i due `Sprint N/REPORT.md`:
  `stato: chiuso`.

## Scelta

1. **Togliere il `.git` annidato**, tenendo il codice. Il materiale di studio resta quello che e':
   codice da leggere, con le regole d'uso (licenza AGPL) dichiarate nel suo `README.md`.
2. **Chiudere `NLT-001` e `NLT-002`.**
3. **Non toccare nient'altro.** I 13 repository dei progetti restano dove sono: sono loro, e
   cancellarli sarebbe un disastro.

## Conseguenze

- I materiali di studio di Ghostfolio scendono da 42 a 30 MB e non portano piu' un repository
  dentro un altro.
- Il progetto torna **non scrivibile** appena il riordino e' chiuso: la tappa chiusa e i permessi
  chiusi dicono la stessa cosa.
- La storia delle tappe resta intatta: `Milestone 1` chiusa con due passi, `Milestone 2` aperta
  con il passo di riordino.
- **Limite dichiarato**: togliere un `.git` toglie la possibilita' di aggiornare la copia di
  studio con `git pull`. Se serve aggiornarla, si riscarica. E' il prezzo, ed e' basso.
- **Limite dichiarato**: il controllo non impedisce da solo a un permesso di restare aperto. Oggi
  l'ho notato perche' ho guardato; **serve un promemoria** — un permesso la cui tappa e' chiusa
  dovrebbe comparire come divergenza. Non l'ho implementato, e lo dichiaro.

## Metrica

Repository annidati nella super cartella: atteso zero, oggi zero dopo questo riordino. Permessi
attivi la cui tappa e' chiusa: atteso zero, oggi due — chiusi da questo riordino.

## Data di revisione

2026-11-07
