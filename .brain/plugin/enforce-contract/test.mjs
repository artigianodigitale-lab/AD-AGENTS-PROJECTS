#!/usr/bin/env node
/**
 * Test del plugin ad-enforce-contract con un contesto finto.
 *
 * Non richiede DSH: verifica che apply() registri il listener su
 * `tools/pre-execute` e che la decisione sia quella giusta in ogni caso.
 * E' l'unico modo di provare la logica senza dipendere dal caricamento nel
 * profilo vivo.
 *
 *   node tools/dsh-plugin/enforce-contract/test.mjs
 *
 * Esito: 0 tutti i controlli passano, 1 altrimenti.
 */

import { mkdirSync, mkdtempSync, rmSync, utimesSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { apply } from './index.mjs'

const HERE = dirname(fileURLToPath(import.meta.url))
// .brain/plugin/enforce-contract -> .brain -> AD Projects -> tools/contract_scope.py
const CHECKER = join(HERE, '..', '..', '..', 'tools', 'contract_scope.py')

let passed = 0

function check(label, condition, detail = '') {
  if (condition) {
    passed += 1
    console.log(`  ok   ${label}`)
    return
  }
  console.error(`  FAIL ${label}${detail ? `: ${detail}` : ''}`)
  process.exitCode = 1
}

/** Minimal cordis-like context that records the listeners a plugin registers. */
function fakeCtx() {
  const listeners = new Map()
  return {
    listeners,
    on(name, handler) {
      listeners.set(name, handler)
    },
    logger: { warn() {} },
  }
}

async function decide(ctx, name, filePath) {
  const handler = ctx.listeners.get('tools/pre-execute')
  if (!handler) throw new Error('listener tools/pre-execute non registrato')
  const exec = { name, arguments: { file_path: filePath } }
  const next = async () => ({ kind: 'allow' })
  return handler(exec, next)
}

const root = mkdtempSync(join(tmpdir(), 'ad-enforce-'))
mkdirSync(join(root, 'contratti'), { recursive: true })
mkdirSync(join(root, 'approvazioni'), { recursive: true })
mkdirSync(join(root, '9. Prova', 'src'), { recursive: true })
mkdirSync(join(root, '9. Prova', 'altro'), { recursive: true })
mkdirSync(join(root, 'tools'), { recursive: true })

const adesso = Date.now() / 1000
const prima = adesso - 100

// T-1: il consenso precede il contract, quindi copre.
writeFileSync(
  join(root, 'approvazioni', 'T-1.yaml'),
  ['task_id: T-1', 'approvato_da: CEO', "data: '2026-10-08T13:00:00+02:00'"].join('\n'),
)
writeFileSync(
  join(root, 'contratti', 'T-1.yaml'),
  ['task_id: T-1', 'agent: backend', 'status: active', 'write_scope:', '  - "9. Prova/src"'].join('\n'),
)
utimesSync(join(root, 'approvazioni', 'T-1.yaml'), prima, prima)
utimesSync(join(root, 'contratti', 'T-1.yaml'), adesso, adesso)

// T-2: contract approvato ma scaduto, non copre.
writeFileSync(
  join(root, 'approvazioni', 'T-scaduto.yaml'),
  ['task_id: T-scaduto', 'approvato_da: CEO', "data: '2026-10-08T13:00:00+02:00'"].join('\n'),
)
writeFileSync(
  join(root, 'contratti', 'T-scaduto.yaml'),
  [
    'task_id: T-scaduto',
    'status: active',
    'expires: "2020-01-01T00:00:00+00:00"',
    'write_scope:',
    '  - "9. Prova/altro"',
  ].join('\n'),
)

const covered = join(root, '9. Prova', 'src', 'api.ts')
const uncovered = join(root, '9. Prova', 'altro', 'x.ts')
const notProtected = join(root, 'piani', 'x.md')
const governance = join(root, 'tools', 'x.py')
const outside = join(tmpdir(), 'altrove.txt')

console.log('modalita deny')
const denyCtx = fakeCtx()
apply(denyCtx, { root, checker: CHECKER, mode: 'deny', debugLog: '' })
check('registra tools/pre-execute', denyCtx.listeners.has('tools/pre-execute'))

check('tool non di scrittura -> allow', (await decide(denyCtx, 'read', uncovered)).kind === 'allow')
check('percorso fuori root -> allow', (await decide(denyCtx, 'write', outside)).kind === 'allow')
check(
  'percorso non protetto -> allow',
  (await decide(denyCtx, 'write', notProtected)).kind === 'allow',
)

const deniedGovernance = await decide(denyCtx, 'write', governance)
check(
  'artefatto di governance non coperto -> deny',
  deniedGovernance.kind === 'deny',
  JSON.stringify(deniedGovernance),
)
check(
  'il blocco nomina la governance',
  /GOVERNANCE/.test(deniedGovernance.reason ?? ''),
  deniedGovernance.reason,
)

const denied = await decide(denyCtx, 'write', uncovered)
check('cartella prodotto non coperta -> deny', denied.kind === 'deny', JSON.stringify(denied))
check(
  'il motivo e actionabile',
  typeof denied.reason === 'string' && denied.reason.includes('write_scope'),
  denied.reason,
)
check(
  'un contract copre il percorso -> allow',
  (await decide(denyCtx, 'edit', covered)).kind === 'allow',
)
check(
  'un contract scaduto non copre',
  (await decide(denyCtx, 'write', join(root, '9. Prova', 'altro', 'y.ts'))).kind === 'deny',
)

console.log('modalita ask')
const askCtx = fakeCtx()
apply(askCtx, { root, checker: CHECKER, mode: 'ask', debugLog: '' })
const asked = await decide(askCtx, 'write', uncovered)
check('percorso non coperto -> ask', asked.kind === 'ask', JSON.stringify(asked))
check('ask porta il motivo', typeof asked.reason === 'string' && asked.reason.length > 0)
check(
  'ask dichiara la lingua di visualizzazione',
  asked.displayReason && typeof asked.displayReason.en === 'string',
)
check('percorso coperto -> allow', (await decide(askCtx, 'write', covered)).kind === 'allow')

console.log('modalita allow e fail-open')
const allowCtx = fakeCtx()
apply(allowCtx, { root, checker: CHECKER, mode: 'allow', debugLog: '' })
check(
  'mode allow non blocca mai',
  (await decide(allowCtx, 'write', uncovered)).kind === 'allow',
)

const autoCtx = fakeCtx()
apply(autoCtx, { root, checker: CHECKER, mode: 'auto', debugLog: '' })
const autoDecision = await decide(autoCtx, 'write', uncovered)
check(
  'auto senza canale di approvazione -> deny (motivo visibile)',
  autoDecision.kind === 'deny',
  JSON.stringify(autoDecision),
)
check(
  'deny porta un codice macchina',
  autoDecision.info && autoDecision.info.code === 'AD_CONTRACT_REQUIRED',
  JSON.stringify(autoDecision.info),
)
check(
  'auto lascia passare un percorso coperto',
  (await decide(autoCtx, 'write', covered)).kind === 'allow',
)

const brokenCtx = fakeCtx()
apply(brokenCtx, { root, checker: join(root, 'inesistente.py'), mode: 'deny', debugLog: '' })
check(
  'checker assente -> fail-open',
  (await decide(brokenCtx, 'write', uncovered)).kind === 'allow',
)

const emptyCtx = fakeCtx()
apply(emptyCtx, { root: join(root, 'root-inesistente'), checker: CHECKER, mode: 'deny', debugLog: '' })
check(
  'root inesistente -> allow (fuori ambito)',
  (await decide(emptyCtx, 'write', uncovered)).kind === 'allow',
)

async function decideBash(ctx, command, cwd) {
  const handler = ctx.listeners.get('tools/pre-execute')
  const exec = { name: 'bash', arguments: { command }, agent: { session: { header: { cwd } } } }
  const next = async () => ({ kind: 'allow' })
  return handler(exec, next)
}

console.log('guardia sui comandi shell')
const bashCtx = fakeCtx()
apply(bashCtx, { root, checker: CHECKER, mode: 'deny', bashGuard: true, debugLog: '' })
check(
  'comando di sola lettura sul progetto -> allow',
  (await decideBash(bashCtx, `grep -rn TODO "${join(root, '9. Prova')}/"`, root)).kind === 'allow',
)
check(
  'rm su un percorso del progetto -> deny',
  (await decideBash(bashCtx, `rm -rf "${join(root, '9. Prova', 'src')}"`, root)).kind === 'deny',
)
check(
  'mutazione implicita con cwd nel progetto -> deny',
  (await decideBash(bashCtx, 'rm -rf build', join(root, '9. Prova'))).kind === 'deny',
)
check(
  'scrittura assoluta fuori dal progetto -> allow',
  (await decideBash(bashCtx, 'echo ciao > /tmp/ad-enforce-probe.txt', join(root, '9. Prova'))).kind ===
    'allow',
)
const bashOff = fakeCtx()
apply(bashOff, { root, checker: CHECKER, mode: 'deny', bashGuard: false, debugLog: '' })
check(
  'bashGuard disattivato -> allow',
  (await decideBash(bashOff, 'rm -rf build', join(root, '9. Prova'))).kind === 'allow',
)

// ---------------------------------------------------------------------------
// La meta' che IMPEDISCE: un documento nuovo nella radice.
//
// Nasce da un caso vero: il CEO ha dovuto spostare a mano, piu' volte, file che
// un agente aveva creato nella super cartella. Una regola scritta non era
// bastata; il blocco e' l'unico momento in cui si puo' impedire.
// ---------------------------------------------------------------------------
console.log('documenti nuovi nella radice')

const radiceCtx = fakeCtx()
apply(radiceCtx, { root, checker: CHECKER, mode: 'deny', bashGuard: true, debugLog: '' })

check(
  'un .md NUOVO nella radice -> deny (invariante 15)',
  (await decide(radiceCtx, 'write', join(root, 'NOTE-SPARSI.md'))).kind === 'deny',
)
writeFileSync(join(root, 'RUNTIME.md'), '# documento normativo\n')
check(
  'un documento normativo esistente -> allow',
  (await decide(radiceCtx, 'write', join(root, 'RUNTIME.md'))).kind !== 'deny',
)
check(
  'un .md dentro una cartella tematica -> allow',
  (await decide(radiceCtx, 'write', join(root, 'piani', 'x.md'))).kind !== 'deny',
)

// ---------------------------------------------------------------------------
// La meta' che AVVISA: dopo la scrittura.
//
// Nasce da un caso vero: il 2026-10-08 ogni prova e ogni marcatore scritti quel
// giorno dichiaravano un orario nel futuro, e nessuno se n'e' accorto finche'
// un revisore non e' passato a guardare.
// ---------------------------------------------------------------------------
console.log('controllo dopo la scrittura')

async function dopoLaScrittura(ctx, filePath) {
  const handler = ctx.listeners.get('tools/post-execute')
  if (!handler) throw new Error('listener tools/post-execute non registrato')
  const exec = { name: 'write', arguments: { file_path: filePath } }
  const next = async () => ({ kind: 'accept' })
  return handler(exec, {}, next)
}

const postCtx = fakeCtx()
apply(postCtx, { root, checker: CHECKER, mode: 'deny', debugLog: '' })
check('registra tools/post-execute', postCtx.listeners.has('tools/post-execute'))

const conDataFutura = join(root, 'prova-futura.yaml')
writeFileSync(conDataFutura, 'task_id: X\ntimestamp: "2099-01-01T10:00:00+02:00"\n')
check(
  'una data nel futuro -> block',
  (await dopoLaScrittura(postCtx, conDataFutura)).kind === 'block',
)

const conDataPassata = join(root, 'prova-passata.yaml')
writeFileSync(conDataPassata, 'task_id: X\ntimestamp: "2020-01-01T10:00:00+02:00"\n')
check(
  'una data passata -> accept',
  (await dopoLaScrittura(postCtx, conDataPassata)).kind !== 'block',
)

const conScadenza = join(root, 'contratti', 'T-scad.yaml')
writeFileSync(conScadenza, 'task_id: T-scad\nexpires: "2099-01-01T10:00:00+02:00"\n')
check(
  "una SCADENZA nel futuro non e' un errore: deve esserlo per forza",
  (await dopoLaScrittura(postCtx, conScadenza)).kind !== 'block',
)

// L'ordine rotto: riscrivere il marcatore lo rende piu' recente del permesso.
const marcatoreRiscritto = join(root, 'approvazioni', 'T-1.yaml')
writeFileSync(
  marcatoreRiscritto,
  ['task_id: T-1', 'approvato_da: CEO', "data: '2020-01-01T13:00:00+02:00'"].join('\n'),
)
check(
  "un marcatore riscritto dopo il suo permesso -> block (ordine rotto)",
  (await dopoLaScrittura(postCtx, marcatoreRiscritto)).kind === 'block',
)

// Chiudere un permesso non chiude il passo: la tappa ha ragione lei.
mkdirSync(join(root, 'tools'), { recursive: true })
writeFileSync(join(root, 'tools', 'milestone.py'), 'import sys\nsys.exit(1)\n')
const contrattoChiuso = join(root, 'contratti', 'T-chiuso.yaml')
writeFileSync(
  contrattoChiuso,
  ['task_id: T-chiuso', 'status: chiuso', 'write_scope:', '  - "9. Prova/"'].join('\n'),
)
const bloccoChiusura = await dopoLaScrittura(postCtx, contrattoChiuso)
check(
  'un permesso chiuso con la storia incompleta -> block',
  bloccoChiusura.kind === 'block',
)
check(
  'e il motivo dice che la tappa ha ragione lei',
  (bloccoChiusura.feedback?.[0]?.text || '').includes('la tappa ha ragione'),
)

writeFileSync(join(root, 'tools', 'milestone.py'), 'import sys\nsys.exit(0)\n')
check(
  'storia completa -> nessun blocco',
  (await dopoLaScrittura(postCtx, contrattoChiuso)).kind !== 'block',
)

rmSync(root, { recursive: true, force: true })

if (process.exitCode) {
  console.error(`\nFALLITO — ${passed} controlli passati`)
} else {
  console.log(`\nPASS — ${passed} controlli`)
}
