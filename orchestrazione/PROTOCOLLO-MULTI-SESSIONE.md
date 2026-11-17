# Lavorare con piu' chat in parallelo

Tre chat, tre progetti, un solo motore. **E' fattibile** — e questa pagina dice come, perche'
il cancello protegge **i percorsi**, non e' un lucchetto di macchina: due sessioni che scrivono
nello stesso posto nello stesso momento non vengono fermate da niente.

Il lavoro sui progetti e' separato (ogni progetto ha i suoi contratti, la sua storia, le sue
evidenze). Le cose **in comune** sono:

| In comune | Perche' e' pericoloso | Regola |
|---|---|---|
| `contratti/`, `approvazioni/` | due sessioni sullo stesso percorso: la seconda non copre, la prima resta senza titolare | una chat = un progetto; **mai due chat sullo stesso progetto** nello stesso momento |
| `errori/`, `DECISIONI/`, `drift/` | due sessioni scelgono lo stesso id (e' successo il 2026-10-11) | id **solo** con `python3 tools/errori.py nuovo` / `verbali.py nuovo`: prenotano in modo atomico |
| `stato.md`, `BLUEPRINT.md` | chi renderizza per ultimo vince; «indietro» e' normale fra una chiusura e l'altra | render solo ai propri momenti di chiusura; **non** da tre chat insieme |
| `tests/ci.py --full` | guarda tutta la macchina: puo' essere rosso per lo sprint a meta' di un'altra chat | si guarda **dove** e' il rosso; non si «aggiusta» un progetto che non e' il tuo |
| git | due scrittori sullo stesso repo si bloccano (`.git/index.lock`) | un solo scrittore git per repo alla volta; `git status` e' innocuo |
| `.brain/`, `tools/` | cambiarli cambia il comportamento di **tutte** le chat a meta' volo | solo da una chat «macchina», con le altre ferme |

## Il confine nuovo: la macchina non si tocca

La cartella del motore (`AD-AGENTS-PROJECTS`) si legge e si usa, **non si modifica**. Chi lavora a
un progetto entra nella cartella del progetto, ci tiene il suo registro (`<progetto>/governance/`)
e importa i modelli che gli servono. Un intervento sulla macchina (regole, strumenti, controlli) e'
un incarico a se', con il suo contract e il suo gate (`DEC-0081`).

## Le sette regole

1. **Una chat, un progetto.** Se due chat devono lavorare sullo stesso progetto, una scrive e
   l'altra legge. Due contratti attivi sullo stesso percorso vengono rifiutati dal validatore:
   e' la regola «un percorso, un titolare» (`DEC-0054`).
2. **Gli id si prenotano, non si scelgono.** `errori.py nuovo`, `verbali.py nuovo`. E il
   `task_id` di un contract si sceglie con il prefisso del progetto, dopo aver guardato che non
   esista (`grep -r "task_id: <id>" contratti/`).
3. **Le viste generate non si rincorrono.** `stato.py render` e `blueprint.py render` sono
   fotografie: se un'altra chat e' a meta' sprint, la fotografia invecchia subito. Renderizza
   alla **tua** chiusura, non in contemporanea. «indietro» non e' manomissione.
4. **La suite e' globale.** Un rosso puo' essere il lavoro in corso di un'altra chat (sprint
   aperto senza report, contratto attivo senza evidenza). Prima di toccare qualcosa, leggi il
   messaggio: se parla di un progetto che non e' il tuo, **non e' tuo**.
5. **L'artefatto non si muove sotto il gate.** Mentre un gate verifica, nessuna chat modifica
   quel file (`ERR-0028`, `ERR-0057`). Vale anche fra chat diverse.
6. **La macchina si cambia da una chat sola.** `.brain/` e `tools/` valgono per tutte le
   sessioni: una modifica a meta' lavoro delle altre le fa comportare in due modi diversi.
7. **Il permesso si chiude quando il passo chiude.** Un contract `active` su un passo che ha
   gia' il `REPORT.md` e' un permesso appeso; uno scaduto e' peggio. Controllo:
   `python3 tools/permessi.py check`.

## Prima di aprire un lavoro, in ogni chat

```sh
python3 tools/progetto.py elenca              # quali progetti ci sono, e quali numeri
python3 tools/permessi.py check               # c'e' un permesso appeso o scaduto?
python3 tools/stato.py show                   # cosa e' aperto, in parole comprensibili
```

Se il progetto su cui vuoi lavorare ha gia' un contract attivo che non e' il tuo, **fermati**:
o lo chiude chi lo ha aperto, o si aspetta.

## Se una regola viene violata

- **Non correggere i file di un'altra chat.** Si scrive in `drift/` (la divergenza si registra,
  non si sanziona in silenzio) e si dice al CEO: chi ha scritto quel file lo corregge.
- **Non chiudere permessi che non sono tuoi.** La chiusura e' del CEO, come l'apertura.
- **Se il rosso e' di un altro progetto**, si dice dov'e' e si continua il proprio lavoro.

## Perche' AAP regge

Il contratto ha **un solo esecutore**; il cancello decide **per percorso**; gli id si prenotano
in modo atomico; la storia e' per progetto. Tre progetti in parallelo sono tre storie separate
che si incontrano solo nei registri della macchina — e i registri hanno un controllo
(`tools/permessi.py`) che dice quando mentono.

Decisione: `DECISIONI/DEC-0075-protocollo-multi-chat-e-permessi-appesi.md`.
