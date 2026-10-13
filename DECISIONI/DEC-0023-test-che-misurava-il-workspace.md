# DEC-0023 — Il test che misurava il workspace invece del codice

```yaml
id: DEC-0023
stato: approvato
livello: 2
data: 2026-10-08
approver: CEO
supera:
```

## Problema

Il 2026-10-08, aprendo il primo sprint di un progetto vero (`NLT-001` su `17. Michele Clementi Project`), **la suite deterministica si e' interrotta**:

```text
AssertionError: nessun contract apre una cartella prodotto:
  [('GOV-000', ['.brain/', 'tools/']),
   ('NLT-001', ['17. Michele Clementi Project/Milestone 1/', '17. Michele Clementi Project/Studio/']),
   ('NLT-002', ['17. Michele Clementi Project/'])]
```

Il test asseriva che **nessun contract attivo toccasse una cartella prodotto**. Era vero quando l'unico contract attivo era quello di governance — e **contraddice il sistema appena costruito**, che prevede esattamente il contrario: ogni lavoro di progetto vive nella cartella del progetto.

Effetto peggiore del fallimento: `check()` **alza un'eccezione**, quindi la suite si ferma. **Gli ultimi sette gruppi di controlli non venivano piu' eseguiti**, e il conteggio riportato (107) sembrava un test rosso invece di una copertura dimezzata.

## Evidenze

- Il test era in `test_scope()` e leggeva `ad_scope.load_write_scopes(ad_docs.DOCS_ROOT)`: **lo stato del workspace**, non una proprieta' del codice.
- Con zero contract di progetto passava; con uno fallisce. Il suo significato dipendeva dai dati.
- Misurato dall'agente che l'ha scoperto: «1 fallimento su 107 controlli, e gli ultimi 7 gruppi non vengono piu' eseguiti».
- **Trovato da un altro agente**, in una chat separata, mentre apriva il primo sprint. Non da me: l'ho scritto io poche ore prima e non l'ho rimesso in discussione.

## Scelta

Il test ora asserisce **la regola**, non il dato: per ogni contract attivo che tocca una cartella prodotto, i codici `missing-field:milestone`, `missing-field:sprint` e `sprint-not-open` **non devono comparire**.

```text
ok  il contract di progetto NLT-001 dichiara milestone e sprint aperti
ok  il contract di progetto NLT-002 dichiara milestone e sprint aperti
```

Questa asserzione **regge quando i progetti partono** — ed e' il momento in cui deve reggere — e fallisce solo se un contract e' davvero irregolare. Il contrario di prima.

## Conseguenze

- La suite arriva in fondo: **166 controlli**, e ora comprende la verifica dell'invariante 13 sui contract **reali**, non solo su quelli di prova.
- La copertura non puo' piu' dimezzarsi in silenzio per un contract legittimo.
- `DRIFT-011` chiuso.

## Perche' e' successo, ed e' la terza volta oggi

E' la stessa forma di altri due errori di oggi:

| | Cosa misurava | Cosa doveva misurare |
|---|---|---|
| Il conteggio delle etichette | 3.500 occorrenze, di cui 550 erano un valore di prodotto | la disciplina, non il volume |
| La verifica sui segreti | 0 cercate, 0 trovate | che le stringhe fossero assenti |
| **Questo test** | lo stato del workspace | il comportamento del codice |

Tutte e tre **sembravano controlli e non controllavano niente** — o controllavano qualcosa che cambia da solo. In due casi su tre la cosa peggiore non era l'errore, ma il fatto che il controllo **rassicurava**.

## Limite dichiarato

Il test verifica che i contract **dichiarino** milestone e sprint e che lo sprint esista. Non verifica che il lavoro dentro lo sprint sia pertinente, ne' che lo sprint sia ben tagliato. La qualita' della pianificazione resta una responsabilita' umana.

## Metrica

Controlli eseguiti dalla suite: atteso 166 su 166, sempre. Prima di questa correzione il numero dipendeva da quanti contract di progetto erano attivi — cioe' dal lavoro in corso, che e' il modo peggiore di misurare un test.

## Data di revisione

2026-11-07
