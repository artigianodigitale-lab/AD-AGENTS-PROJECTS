# DEC-0019 — Allineare il livello sempre caricato a ciò che il sistema è

```yaml
id: DEC-0019
stato: approvato
livello: 2
data: 2026-10-08
approver: CEO
supera:
```

## Problema

A fine giornata il **livello che ogni agente legge all'avvio** descriveva un sistema che non esisteva più. Tre divergenze, tutte verificate.

1. **`ad-milestone` non era nominata nella costituzione.** La lista diceva sei skill; nel cervello ce ne sono **sette**. La sequenza milestone era stata aggiunta poche ore prima, ma non la skill che spiega *come* si fa: un agente leggeva «apri una milestone» senza sapere che esiste una procedura.
2. **`.brain/README.md` era fermo alle 12:17**, prima di quasi tutto il lavoro: non nominava milestone, invariante 13, `GOV-000`, né la protezione degli artefatti di governance.
3. **`MODEL-ROUTING.md` citava `.cursor/rules/*.mdc`** come superficie attiva, con regole `alwaysApply`. La cartella non esiste e Cursor è stato deprioritizzato (DRIFT-001).

La causa è la stessa di DEC-0018, in forma piu' banale: **si aggiorna il meccanismo e non la descrizione.** Ma il meccanismo e' codice e la descrizione e' l'unica cosa che un agente nuovo possiede.

## Evidenze

- `grep -o "ad-[a-z]*" .brain/COSTITUZIONE.md` → sei nomi di skill, `ad-milestone` assente (`grep -c` = 0).
- `.brain/README.md`, timestamp `ott 8 12:17`; `grep -c "milestone\|invariante 13\|GOV-000"` = 0.
- `ls -d .cursor` → assente.

**Un errore mio, dichiarato.** Nell'audit iniziale avevo concluso che «otto strumenti su quindici non sono documentati». **Falso.** I quindici file sono **otto librerie** (moduli importati) e **sette comandi**, e i sette comandi sono tutti documentati. Avevo confrontato due cose non confrontabili — comandi contro moduli di codice. Il controllo che l'ha smentito e' costato un comando.

## Scelta

1. **Costituzione**: `ad-milestone` entra nella lista delle skill, con la sua funzione in una riga.
2. **`.brain/README.md`**: riscritto nelle parti stantie — albero delle skill, sequenza a 12 passi, sezione sulla protezione degli artefatti di governance, stato al 2026-10-08. E una riga che spiega **perche' le sette skill devono restare sette nella lista**: e' successo con `ad-milestone` e puo' succedere di nuovo.
3. **`MODEL-ROUTING.md`**: DSH e' dichiarata **la superficie operativa**; Cursor e' dichiarato **non in uso**, con la regola che se si riattiva va allineato al cervello invece di duplicarlo. Chiude DRIFT-001.

## Conseguenze

- Un agente nuovo legge una descrizione che corrisponde al sistema.
- `DRIFT-001` chiuso.
- Documento normativo di root cambiato (`MODEL-ROUTING.md`): snapshot rigenerato.
- **Limite dichiarato**: l'allineamento vale al momento della scrittura. Nessun controllo confronta automaticamente il livello sempre caricato con il cervello — il registro drift e' l'unico posto dove una divergenza cosi' viene annotata, e dipende da qualcuno che la cerchi. **Questa e' la prossima cosa da meccanizzare**, se si vuole che non si ripeta una terza volta.

## Metrica

Skill nel cervello contro skill nominate nella costituzione: attesi 7 e 7, oggi 7 e 7. E drift aperti piu' vecchi di 30 giorni: atteso zero.

## Data di revisione

2026-11-07
