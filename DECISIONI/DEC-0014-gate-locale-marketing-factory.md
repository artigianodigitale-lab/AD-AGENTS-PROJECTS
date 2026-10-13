# DEC-0014 — Riparazione del gate di verifica locale di AD-Marketing-Factory

```yaml
id: DEC-0014
stato: approvato
livello: 2
data: 2026-10-08
approver: CEO
supera:
```

## Problema

Il gate di verifica del progetto, `npm run verify`, **e' rosso sulla macchina di chi ci lavora e verde in CI**. Misurato prima di qualunque intervento (DRIFT-007, DRIFT-008):

```text
typecheck exit=0
lint      exit=1   2343 errori
build     exit=1   TurbopackInternalError
test:all  exit=1   main.Project does not exist
```

Le conseguenze non sono di comodita':

- **Nessun agente e nessuna persona puo' verificare una modifica prima di consegnarla.** La validazione avviene solo dopo il push, quindi un errore costa un ciclo intero prima di emergere.
- Il progetto dipende da questo gate: la sua stessa configurazione lo dice (`check-node.mjs`, la nota AMF-38 sull'episodio di ESLint in OOM su `.wrangler`).
- Un gate che non si puo' eseguire **non e' un gate**. E' un'istruzione a pushare e sperare.

## Evidenze

- `camoufox-env/` e' un virtualenv Python gitignorato (`.gitignore:34`) con **318 file JS su 5.607 file**. `eslint .` non lo esclude: `eslint.config.mjs` ignora `.next`, `out`, `build`, `.open-next`, `.wrangler`, `node_modules`.
- `lib/discovery/browser-engine.ts:34` — ``const PYTHON = `${ROOT}/camoufox-env/bin/python`;`` — e la catena e' `python -> python3 -> /usr/bin/python3 -> /usr/bin/python3.12`.
- Turbopack: *«Symlink [project]/camoufox-env/bin/python is invalid, it points out of the filesystem root»*, in `MiddlewareEndpoint::node_chunk`.
- In CI il venv non esiste, perche' e' gitignorato: **il gate passa la' e fallisce qui**. Nessuno dei due ambienti vede il problema dell'altro.
- La configurazione del progetto conosce gia' questa classe di guasto: la nota AMF-38 aggiunse `.wrangler/**` agli ignore perche' ESLint andava in OOM su un bundle da 17 MB generato dal preview.

## Scelta

Riparare in tre passi, tenuti distinti perche' hanno certezza diversa:

1. **Ignore ESLint per `camoufox-env/**`.** Fix certa: stesso principio di AMF-38, applicato a una directory che non esisteva ancora quando quella nota fu scritta.
2. **Panic Turbopack.** La causa e' un symlink che esce dal progetto. La fix viene **scelta dopo la prova**, non dedotta: le candidate hanno rischi diversi e non intendo indovinare. Se la prima non funziona, si torna indietro e si prova la successiva — ogni tentativo lascia l'albero in stato pulito.
3. **Database di test.** Prima la diagnosi, poi la fix. Registrare un sintomo come se fosse una causa e' esattamente l'errore che il registro drift esiste per intercettare.

**Vincolo assoluto: nessun cambio di dipendenze.** Il gate e' rotto per una directory, non per un pacchetto. Mescolare le due cose renderebbe impossibile attribuire qualunque effetto.

## Conseguenze

- Chi lavora al progetto torna a poter verificare **prima** di consegnare.
- Il progetto smette di dipendere dalla sola CI per la propria correttezza.
- DRIFT-007 si chiude con questo record; DRIFT-008 solo se la diagnosi produce una causa verificata.
- La stessa classe di problema puo' colpire gli altri 16 progetti: una directory generata e gitignorata dentro un repository. Il ritrovamento va cercato, non atteso.
- **Limite dichiarato**: riparare il gate non rende il progetto corretto. Rende **verificabile** cio' che prima non lo era, ed e' una condizione necessaria, non sufficiente.

## Metrica

`npm run verify` eseguibile e verde in locale. E, su tutti i progetti, numero di directory generate e gitignorate che il loro gate non esclude: atteso zero.

## Data di revisione

2026-11-07
