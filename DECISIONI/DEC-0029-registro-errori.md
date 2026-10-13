# DEC-0029 — Il registro delle cicatrici

```yaml
id: DEC-0029
stato: approvato
livello: 2
data: 2026-10-10
approver: CEO
supera:
```

## Problema

Il sistema aveva un archivio e nessuna memoria: **niente registrava gli errori.** Zero.

E la conseguenza era misurabile: il 2026-10-08 ho scritto in un verbale (`DEC-0027`) che le date
inventate erano un errore — e **l'ho rifatto altre due volte**, la terza proprio mentre chiudevo
quel lavoro.

**Una regola scritta non cambia il comportamento.** Quello che l'ha cambiato è stato il controllo
che mi ha bloccato: `tools/post-execute`, aggiunto lo stesso giorno.

## Scelta

Un registro `errori/`, append-only, dove ogni voce risponde a **tre domande**:

| Campo | Domanda |
|---|---|
| `cosa_e_fallito` | Che cosa è andato storto |
| `cosa_l_ha_risolto` | Come è stato riparato |
| **`cosa_l_avrebbe_preso`** | **Cosa avrebbe fermato l'errore prima** |

E poi `diventa`: **`controllo`** (diventa impossibile, non «sconsigliato»), **`nota`** (una riga
nella procedura giusta), **`verbale`** (una scelta).

**Una voce senza la terza risposta è incompleta.** Senza quella non è apprendimento: è memoria
di un dispiacere.

## Il campo che conta più di tutti: `trovato_da`

Non è burocrazia. È **la misura di quanto siamo ancora fortunati**:

| Valore | Significato |
|---|---|
| `controllo` | il sistema se n'è accorto da solo — **è quello che vogliamo** |
| `revisore` | l'ha preso un agente indipendente — va bene, ma costa |
| `altro-agente` | l'ha preso qualcuno che passava — **fortuna** |
| `io` | me ne sono accorto da solo — **fortuna** |

E il verdetto sulle otto voci con cui il registro nasce è **scomodo**:

```text
voci: 8
trovate da un controllo: 2
trovate per fortuna:     4
ancora aperte:           0

equilibrio: meta' controlli, meta' fortuna
```

**Su otto errori, quattro li ha trovati il caso.** È il numero che giustifica l'esistenza di
questo registro, ed è il numero da guardare per sapere se stiamo migliorando.

## Cosa impedisce al registro di morire

Due registri esistono già e sono **vuoti**: `comunicazioni/` (0 file) e `REQUISITI/` (0 file).
Progettati, mai usati. **La struttura senza contenuto è la prova che una cosa progettata e mai
usata non serve.**

Quindi il registro nasce con tre difese contro la propria morte:

1. **Nasce pieno**: otto errori veri, con le loro difese e i loro collegamenti.
2. **`tools/errori.py check`** verifica che ogni voce sia completa **e che la difesa dichiarata
   esista davvero** — una voce che promette un controllo inesistente è peggio di una voce
   assente, perché *sembra* una difesa.
3. **Entra nel passo 12 della sequenza**: alla chiusura, gli errori si registrano. Non è un
   documento fra tanti: è un passo del ciclo.

## Conseguenze

- `tools/errori.py` con `check`, `list`, `stats`; **183 controlli** nella suite (erano 175).
- La regola in costituzione, la cartella nella mappa, il comando nel vocabolario.
- Il registro dice di sé **quanto è utile**: se la maggioranza resta `io`/`altro-agente`, non
  stiamo imparando.
- **Limite dichiarato**: **niente obbliga a scrivere una voce.** Il controllo verifica che le
  voci esistenti siano oneste, non che ce ne siano. Un errore non registrato resta invisibile —
  ed è la stessa classe di problema che `DRIFT-013` descrive per i permessi.
- **Limite dichiarato**: due errori su otto non sono meccanizzabili (`ERR-0002`, `ERR-0007`).
  Restano `nota`, e **possono ripetersi**. È scritto nel registro perché è vero, non perché sia
  comodo.

## Metrica

Errori trovati da un controllo sul totale: **oggi 2 su 8**. L'obiettivo non è «zero errori» —
è che **la maggioranza li trovi il sistema, non la fortuna.**

## Data di revisione

2026-11-09
