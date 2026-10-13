/**
 * ad-enforce-contract — enforcement di runtime per AD Projects (DEC-0003).
 *
 * Intercetta i tool di scrittura prima del dispatch e chiede a
 * `tools/contract_scope.py` se il percorso e' coperto da un task contract.
 * La regola NON e' reimplementata qui: questo modulo e' un adattatore sottile,
 * l'autorita' e' il codice Python gia' testato.
 *
 * Decisione (PreToolDecision di dsh-tools):
 *   mode: ask   -> { kind: 'ask',  reason }   il default
 *   mode: deny  -> { kind: 'deny', reason }
 *   mode: allow -> passa sempre
 *
 * Con `kind: 'ask'`, dsh-tools interroga il servizio di approvazione: se il
 * servizio manca o l'utente rifiuta, la decisione diventa `deny`. Non esiste un
 * percorso in cui `ask` venga approvato da solo.
 *
 * Fail-open: qualunque errore inatteso di questo plugin lascia passare la
 * chiamata. Un difetto dell'enforcement non deve bloccare il lavoro.
 *
 * Limite noto: le scritture via shell sono coperte solo in parte. Il ramo `bash`
 * riconosce le mutazioni evidenti su un percorso di progetto, ma un comando che
 * cambia directory con `cd` e poi scrive in modo relativo puo' sfuggirgli.
 *
 * Solo import builtin: nessuna dipendenza risolta dal profilo.
 */

import { spawnSync } from 'node:child_process'
import { appendFileSync, existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { basename, dirname, isAbsolute, join, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

export const name = 'ad-enforce-contract'

const HERE = dirname(fileURLToPath(import.meta.url))

/**
 * LA RADICE SI SCOPRE, NON SI SCRIVE.
 *
 * Il 2026-10-13 ho provato a spostare la macchina altrove, e il cancello **non
 * bloccava piu' niente**: la radice era scritta qui dentro, quindi credeva di essere
 * ancora nella vecchia sede. Un percorso assoluto nel codice e' un cancello che
 * funziona in un posto solo — e questo file e' symlinkato in ogni sessione, quindi
 * avrebbe mentito a tutti.
 *
 * `HERE` e' `<radice>/.brain/plugin/enforce-contract`: la radice sono **tre livelli
 * sopra**. Si deriva da dove il file si trova davvero, e funziona ovunque.
 */
const RADICE_SCOPERTA = resolve(HERE, '..', '..', '..')

/** Tool che ricevono un percorso di file e possono modificarlo. */
const PATH_TOOLS = new Set(['write', 'edit', 'str_replace_editor'])

const DEFAULTS = {
  root: RADICE_SCOPERTA,
  checker: 'tools/contract_scope.py',
  python: 'python3',
  mode: 'auto',
  bashGuard: true,
  timeoutMs: 5000,
  debugLog: '',
  // I documenti che possono stare nella radice della super cartella. Un .md
  // nuovo qui fuori e' quasi sempre un errore: la radice tiene la macchina, non
  // le carte. Elenco configurabile: per aggiungerne uno legittimo basta
  // scriverlo in settings.json, senza toccare il codice.
  rootDocs: [
    'GOVERNANCE-AZIENDALE.md',
    'AGENTI-V2.md',
    'AGENT-CARDS-V2.md',
    'AGENT-CARDS-BUSINESS.md',
    'TASK-CONTRACTS.md',
    'RUNTIME.md',
    'QUALITY-GATES.md',
    'SPECIALIZATION.md',
    'COMMUNICATION.md',
    'STRATEGIC-MEMORY.md',
    'MODEL-ROUTING.md',
    'AGENT-PROMPT-TEMPLATE.md',
    'README.md',
  ],
  // Oltre questo scarto, un orario dichiarato e' considerato nel futuro.
  clockSkewMs: 60000,
}

/** Append one diagnostic line when `debugLog` is configured. Never throws. */
function trace(settings, message) {
  if (!settings.debugLog) return
  try {
    appendFileSync(settings.debugLog, `${new Date().toISOString()} ${message}\n`)
  } catch {
    /* la diagnostica non deve mai propagare */
  }
}

function loadSettings() {
  try {
    const parsed = JSON.parse(readFileSync(join(HERE, 'settings.json'), 'utf8'))
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

function insideRoot(target, root) {
  const base = root.endsWith(sep) ? root : root + sep
  return target === root || target.startsWith(base)
}

/** Return the absolute target path of a write call, or null when not applicable. */
function targetOf(exec, root) {
  if (!exec || typeof exec.name !== 'string' || !PATH_TOOLS.has(exec.name)) return null
  const args = exec.arguments
  if (!args || typeof args !== 'object') return null
  const raw = args.file_path
  if (typeof raw !== 'string' || raw.trim() === '') return null
  return isAbsolute(raw) ? raw : resolve(root, raw)
}

/** Ask the Python authority. Returns null on any failure, which means fail-open. */
function runChecker(checker, args, settings) {
  const result = spawnSync(
    settings.python,
    [checker, ...args, '--json', '--root', settings.root],
    {
      encoding: 'utf8',
      timeout: settings.timeoutMs,
      stdio: ['ignore', 'pipe', 'ignore'],
    },
  )
  if (result.error || typeof result.stdout !== 'string' || result.stdout.trim() === '') {
    return null
  }
  try {
    const parsed = JSON.parse(result.stdout)
    return parsed && typeof parsed === 'object' ? parsed : null
  } catch {
    return null
  }
}

/**
 * True only when `ask` can actually reach a human.
 *
 * Con la policy `never` il servizio risponde `rejected` senza mostrare nulla, e
 * il registro sostituisce il nostro motivo con un messaggio generico: in quel
 * caso conviene `deny`, che porta il motivo al modello.
 */
function approvalPossible(ctx, exec) {
  try {
    const approval = ctx.get?.('approval')
    if (!approval) return false
    if (typeof approval.overrideOf === 'function' && exec?.agent?.session) {
      return approval.overrideOf(exec.agent.session) !== 'never'
    }
    return true
  } catch {
    return false
  }
}

function fallbackReason(relative, root) {
  return [
    `Nessun task contract copre "${relative}".`,
    'Ogni lavoro su un prodotto parte da un task contract con write_scope',
    '(GOVERNANCE-AZIENDALE.md, TASK-CONTRACTS.md).',
    `Rimedio: crea ${join(root, 'contratti')}/<task_id>.yaml con task_id, agent e`,
    `write_scope che includa "${relative}", poi ripeti la scrittura.`,
  ].join('\n')
}

// ---------------------------------------------------------------------------
// La meta' che AVVISA (tools/post-execute)
//
// Perche' serve, in una riga: il 2026-10-08 OGNI prova e OGNI marcatore scritti
// quel giorno dichiaravano un orario nel futuro, e nessuno se n'e' accorto
// finche' un revisore non e' passato a guardare. Il gancio pre-execute non
// poteva vederlo: il file non esisteva ancora. Questo lo vede subito.
//
// Limite dichiarato: **non disfa la scrittura**. Il file resta com'e'. Il
// `block` ferma il *risultato*: il modello vede che quella scrittura non e'
// accettabile e deve correggerla. Prevenire e avvisare sono due mestieri
// diversi, e questo fa il secondo.
// ---------------------------------------------------------------------------

/** Un orario dichiarato in un record: ISO 8601, con o senza offset. */
const ORARIO_RE =
  /(?:^|\n)[ \t]*(data|timestamp|aperta|chiusa|chiuso):[ \t]*"?(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:[+-]\d{2}:?\d{2})?)/g

/** Gli orari dichiarati nel testo che non sono ancora arrivati. */
function orariNelFuturo(text, adesso, scarto) {
  const fuori = []
  for (const m of text.matchAll(ORARIO_RE)) {
    const quando = Date.parse(m[2])
    if (Number.isNaN(quando)) continue
    if (quando > adesso + scarto) fuori.push(`${m[1]}: ${m[2]}`)
  }
  return fuori
}

/** Il primo file con questo nome sotto `dir`, entro `profondita` livelli. */
function trovaFile(dir, nome, profondita = 0) {
  if (profondita > 4) return null
  let voci
  try {
    voci = readdirSync(dir, { withFileTypes: true })
  } catch {
    return null
  }
  for (const voce of voci) {
    if (voce.name.startsWith('.')) continue
    const percorso = join(dir, voce.name)
    if (voce.isFile() && voce.name === nome) return percorso
    if (voce.isDirectory()) {
      const trovato = trovaFile(percorso, nome, profondita + 1)
      if (trovato) return trovato
    }
  }
  return null
}

/**
 * Il progetto su cui scrive un permesso, letto dal suo write_scope.
 *
 * Non e' un parser YAML: prende la prima voce di `write_scope` e ne tiene il
 * primo segmento, se e' una cartella numerata. Basta per quello che serve.
 */
function primoProgetto(testo) {
  const blocco = /write_scope:[ \t]*\n((?:[ \t]*-[ \t]*.*\n?)+)/.exec(testo)
  if (!blocco) return null
  for (const riga of blocco[1].split('\n')) {
    const voce = riga.replace(/^[ \t]*-[ \t]*/, '').trim().replace(/^["']|["']$/g, '')
    if (!voce) continue
    const testa = voce.split('/')[0].trim()
    if (/^\d+\./.test(testa)) return testa
  }
  return null
}

/**
 * Cosa non va nel file appena scritto. Elenco vuoto = tutto a posto.
 *
 * Tre controlli, e sono i tre errori che hanno gia' sbagliato una volta:
 *   1. un orario dichiarato nel futuro;
 *   2. un marcatore di approvazione piu' recente del suo permesso — l'ordine
 *      approvazione -> permesso e' cio' che rende verificabile la sequenza;
 *   3. un permesso chiuso mentre il passo che autorizzava non ha il suo rapporto.
 *
 * Non inventiamo altri casi. Un controllo che non ha mai visto fallire il
 * proprio bersaglio non e' un controllo: e' una speranza.
 */
function controllaScritto(percorso, settings) {
  const problemi = []
  let testo
  try {
    testo = readFileSync(percorso, 'utf8')
  } catch {
    return problemi // non e' testo, o non si legge: non e' affar nostro
  }

  const futuri = orariNelFuturo(testo, Date.now(), settings.clockSkewMs)
  if (futuri.length > 0) {
    problemi.push(
      [
        `Il file appena scritto dichiara un orario che non e' ancora arrivato: ${futuri.join(', ')}.`,
        "Un registro di governo con date inventate non ordina piu' niente: serve a",
        'ricostruire chi ha deciso cosa, e quando.',
        "Rimedio: usa l'ora vera (`date -Iseconds`), non una stimata.",
      ].join('\n'),
    )
  }

  if (/(^|[/\\])approvazioni[/\\]/.test(percorso) && percorso.endsWith('.yaml')) {
    const task = basename(percorso, '.yaml')
    const contratto = trovaFile(join(settings.root, 'contratti'), `${task}.yaml`)
    if (contratto) {
      try {
        // L'ORDINE SI LEGGE DALLE DATE DICHIARATE, NON DAGLI ORARI DEI FILE.
        //
        // Il 2026-10-13 ho copiato la macchina altrove per provare la portabilita', e
        // questo controllo e' esploso: la copia azzera gli mtime, e l'ordine fra
        // permesso e approvazione si perdeva. Ma **una copia non e' un caso limite**:
        // e' quello che succede a chiunque cloni il repository. Un controllo che
        // funziona solo nella cartella dove e' nato non e' un controllo.
        //
        // Quindi si confrontano le **date scritte nei documenti**. L'mtime resta come
        // ripiego solo quando una data manca — e li' il ripiego e' fragile, e lo
        // diciamo invece di far finta che vada bene.
        const dichiarata = (file) => {
          try {
            const testo = readFileSync(file, 'utf8')
            const m = testo.match(/^(?:data|aperto|creato):\s*["']?(\d{4}-\d{2}-\d{2})/m)
            return m ? Date.parse(`${m[1]}T00:00:00`) : null
          } catch {
            return null
          }
        }
        const dataContratto = dichiarata(contratto)
        const dataApprovazione = dichiarata(percorso)
        if (dataContratto !== null && dataApprovazione !== null) {
          // Granularita' al giorno: un permesso aperto lo STESSO giorno
          // dell'approvazione va bene — l'ordine sta nella giornata, non nel secondo.
          if (dataContratto > dataApprovazione) {
            problemi.push(
              [
                `L'ordine e' rotto: il permesso "${task}" dichiara di essere stato aperto`,
                `il ${new Date(dataContratto).toISOString().slice(0, 10)}, ma l'approvazione`,
                `e' del ${new Date(dataApprovazione).toISOString().slice(0, 10)}.`,
                "L'ordine e' ricerca -> risposta -> consenso -> permesso: un permesso nato",
                "prima del consenso non copre niente.",
                "Rimedio: correggi la data del permesso, o riapri il consenso.",
              ].join('\n'),
            )
          }
        } else if (statSync(contratto).mtimeMs < statSync(percorso).mtimeMs) {
          problemi.push(
            [
              `L'ordine e' rotto: il permesso "${task}" risulta scritto PRIMA della sua approvazione.`,
              "Nessuno dei due documenti dichiara una data, quindi si legge dagli mtime —",
              "che una copia azzera. Rimedio durevole: dichiara `aperto:` nel permesso.",
              `  touch -d "<orario dichiarato>" "${percorso}"`,
            ].join('\n'),
          )
        }
      } catch {
        /* se lo stat fallisce non blocchiamo niente: fail-open */
      }
    }
  }

  // Chiudere un permesso non chiude il passo.
  //
  // Il 2026-10-08 ho chiuso `ORD-001` e dato per finito il lavoro: i file erano
  // al loro posto, il gate era passato. Ma il rapporto del passo non era mai
  // stato scritto, e la storia del progetto diceva «passo mai chiuso» per due
  // giorni. Guardavo il permesso, non la tappa. Questo controllo guarda la tappa.
  if (/(^|[/\\])contratti[/\\]/.test(percorso) && percorso.endsWith('.yaml')) {
    const stato = (/^status:[ \t]*(\S+)/m.exec(testo) || [])[1]
    if (stato === 'chiuso' || stato === 'closed') {
      const progetto = primoProgetto(testo)
      // Se l'autorita' non c'e', non si blocca niente: fail-open. Un controllo
      // che accusa perche' non riesce a controllare e' peggio di nessun controllo.
      const script = join(settings.root, 'tools', 'milestone.py')
      if (progetto && existsSync(script)) {
        let esito = null
        try {
          esito = spawnSync(
            settings.python,
            [script, 'check', progetto],
            {
              encoding: 'utf8',
              timeout: settings.timeoutMs,
              cwd: settings.root,
              stdio: ['ignore', 'pipe', 'pipe'],
            },
          )
        } catch {
          esito = null
        }
        if (esito && typeof esito.status === 'number' && esito.status !== 0) {
          const dettaglio = (esito.stdout || esito.stderr || '').trim().split('\n').slice(0, 6)
          problemi.push(
            [
              `Stai chiudendo il permesso su "${progetto}", ma la sua storia non e' completa.`,
              'Chiudere il permesso non chiude il passo: la tappa ha ragione lei.',
              ...dettaglio,
              'Rimedio: scrivi il rapporto del passo (`Milestone N/Sprint M/REPORT.md`)',
              'e riprova. Vedi `python3 tools/milestone.py check "<progetto>"`.',
            ].join('\n'),
          )
        }
      }
    }
  }

  return problemi
}

export function apply(ctx, config) {
  const settings = {
    ...DEFAULTS,
    ...loadSettings(),
    ...(config && typeof config === 'object' ? config : {}),
  }
  const checker = isAbsolute(settings.checker)
    ? settings.checker
    : join(settings.root, settings.checker)

  trace(settings, `loaded · root=${settings.root} · mode=${settings.mode} · checker=${checker}`)

  let warned = false
  const warnOnce = (message) => {
    if (warned) return
    warned = true
    try {
      ctx.logger?.warn?.(`[ad-enforce-contract] ${message}`)
    } catch {
      /* il logging non deve mai propagare */
    }
  }

  ctx.on('tools/pre-execute', async (exec, next) => {
    try {
      if (settings.mode === 'allow') return next() // enforcement spento

      const toolName = exec?.name
      let reason = ''
      let relative = ''

      if (PATH_TOOLS.has(toolName)) {
        const target = targetOf(exec, settings.root)
        trace(settings, `pre-execute name=${toolName} target=${target ?? '-'}`)
        if (!target || !insideRoot(target, settings.root)) return next()

        // Un .md NUOVO direttamente nella radice della super cartella.
        //
        // Invariante 15: la radice tiene la macchina, non le carte. Questa e'
        // l'unica meta' in cui si puo' IMPEDIRE invece di avvisare, perche' il
        // file non esiste ancora. E' il caso che il CEO ha dovuto correggere a
        // mano piu' volte, e una regola scritta non basta: una regola si
        // dimentica, un blocco no.
        const docRadiceNuovo =
          exec.name === 'write' &&
          dirname(target) === settings.root &&
          target.endsWith('.md') &&
          !existsSync(target) &&
          !settings.rootDocs.includes(basename(target))
        if (docRadiceNuovo) {
          const text = [
            `Stai per creare "${basename(target)}" nella radice di AD Projects.`,
            'La radice tiene la macchina, non le carte: i documenti normativi, il registro',
            "delle autorizzazioni, gli strumenti. Un file nuovo qui fuori non e' un",
            "documento normativo, e fra sei mesi nessuno sapra' a chi appartiene.",
            'Dove va:',
            '  · se riguarda un progetto  -> <progetto>/Analisi-Prompt-Report/',
            '  · se riguarda il sistema    -> studio/, oppure la cartella tematica giusta',
            "  · se E' un documento normativo nuovo -> aggiungilo a rootDocs in",
            '    .brain/plugin/enforce-contract/settings.json, poi riprova',
          ].join('\n')
          trace(settings, `pre-execute DENY root-doc ${basename(target)}`)
          return { kind: 'deny', reason: text, info: { name: 'AD_ROOT_DOC', code: 'AD_ROOT_DOC', reason: text } }
        }

        const verdict = runChecker(checker, ['check', target], settings)
        if (!verdict) {
          warnOnce(`verifica non disponibile per "${target}": la scrittura procede`)
          return next()
        }
        if (verdict.allowed !== false) return next()
        relative =
          typeof verdict.relative === 'string' && verdict.relative ? verdict.relative : target
        reason = typeof verdict.reason === 'string' ? verdict.reason : ''
      } else if (toolName === 'bash' && settings.bashGuard) {
        const command = exec?.arguments?.command
        if (typeof command !== 'string' || command.trim() === '') return next()
        const cwd =
          exec?.agent?.session?.header?.cwd ??
          (typeof exec?.arguments?.workdir === 'string' && exec.arguments.workdir
            ? exec.arguments.workdir
            : settings.root)
        const verdict = runChecker(
          checker,
          ['check-command', command, '--cwd', String(cwd)],
          settings,
        )
        trace(settings, `pre-execute bash verdict=${verdict ? JSON.stringify(verdict) : 'null'}`)
        if (!verdict) {
          warnOnce('verifica del comando non disponibile: il comando procede')
          return next()
        }
        if (verdict.allowed !== false) return next()
        relative =
          typeof verdict.relative === 'string' && verdict.relative ? verdict.relative : command
        reason = typeof verdict.reason === 'string' ? verdict.reason : ''
      } else {
        return next()
      }

      const text = reason || fallbackReason(relative, settings.root)
      const info = { name: 'AD_CONTRACT_REQUIRED', code: 'AD_CONTRACT_REQUIRED', reason: text }
      if (settings.mode === 'deny') return { kind: 'deny', reason: text, info }
      if (settings.mode === 'ask') {
        return { kind: 'ask', reason: text, displayReason: { en: text, it: text } }
      }
      // auto: chiedi solo se l'approvazione puo' arrivare davvero all'umano,
      // altrimenti nega portando il motivo al modello.
      if (approvalPossible(ctx, exec)) {
        return { kind: 'ask', reason: text, displayReason: { en: text, it: text } }
      }
      return { kind: 'deny', reason: text, info }
    } catch (error) {
      warnOnce(`errore inatteso: ${error?.message ?? error}. La scrittura procede.`)
      return next()
    }
  })

  // -------------------------------------------------------------------------
  // La meta' che AVVISA, dopo la scrittura.
  //
  // Non previene: il file e' gia' li'. Serve a non scoprire l'errore per caso,
  // che e' come l'abbiamo scoperto l'altra volta — un revisore di passaggio.
  // Il `block` ferma il *risultato*: il modello vede che quella scrittura non e'
  // accettabile e la corregge nello stesso momento.
  // -------------------------------------------------------------------------
  ctx.on('tools/post-execute', async (exec, result, next) => {
    try {
      if (settings.mode === 'allow') return next() // enforcement spento

      const target = targetOf(exec, settings.root)
      if (!target || !insideRoot(target, settings.root)) return next()

      const problemi = controllaScritto(target, settings)
      if (problemi.length === 0) return next()

      const testo = problemi.join('\n\n')
      trace(settings, `post-execute BLOCK ${target}: ${problemi.length} problema/i`)
      try {
        ctx.logger?.warn?.(`[ad-enforce-contract] ${testo}`)
      } catch {
        /* il logging non deve mai propagare */
      }
      return { kind: 'block', feedback: [{ type: 'text', text: testo }] }
    } catch (error) {
      warnOnce(`errore inatteso in post-execute: ${error?.message ?? error}. Il risultato passa.`)
      return next()
    }
  })
}
