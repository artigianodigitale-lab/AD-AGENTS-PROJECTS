// Il ponte di Code Mode: passa all'agente SOLO `strumenti`, e stampa un risultato JSON.
//
// Lo script dell'agente e' un modulo ES:
//     export default async function (strumenti) { ... return risultato; }
//
// `strumenti.<nome>(argomenti)` chiama il server MCP via CLI: le stesse validazioni dei tool,
// nessuna autorita' in piu'. Il risultato intermedio NON esce da qui: torna al modello solo
// cio' che lo script restituisce (o stampa).
//
// Confinamento: questo file gira DENTRO tools/sandbox.py (bubblewrap): rete spenta,
// filesystem in sola lettura, ambiente azzerato. Limite dichiarato: non e' un isolate V8.

import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const [, , scriptPath, argomentiPath, serverPath, pythonPath, consentitiPath] = process.argv;
const TETTO = 200_000;
const consentiti = new Set(leggiJson(consentitiPath, []));

function leggiJson(percorso, vuoto) {
  try {
    return JSON.parse(readFileSync(percorso, "utf8"));
  } catch {
    return vuoto;
  }
}

function chiamaTool(nome, argomenti) {
  try {
    const uscita = execFileSync(
      pythonPath ?? "python3",
      [serverPath, "--tool", nome, "--argomenti", JSON.stringify(argomenti ?? {})],
      { encoding: "utf8", timeout: 30_000, maxBuffer: 5_000_000 },
    );
    return JSON.parse(uscita);
  } catch (errore) {
    const dettaglio = String(errore?.stderr ?? errore?.message ?? errore).slice(0, 800);
    throw new Error(`tool ${nome} fallito: ${dettaglio}`);
  }
}

const strumenti = new Proxy(
  {},
  {
    get(_bersaglio, nome) {
      if (typeof nome !== "string" || nome.startsWith("_")) return undefined;
      // Solo i tool in sola lettura. NON e' un confine: il JS puo' importare
      // child_process e chiamare il server per conto suo. La difesa e' la sandbox.
      if (!consentiti.has(nome)) {
        return () => {
          throw new Error(`tool non consentito in modalita' codice (sola lettura): ${nome}`);
        };
      }
      return (argomenti) => chiamaTool(nome, argomenti);
    },
  },
);

const argomenti = argomentiPath ? leggiJson(argomentiPath, {}) : {};

let risultato;
try {
  const modulo = await import(pathToFileURL(scriptPath).href);
  if (typeof modulo.default !== "function") {
    throw new Error("lo script deve esportare default async function (strumenti)");
  }
  risultato = await modulo.default(strumenti, argomenti);
} catch (errore) {
  console.log(JSON.stringify({ ok: false, errore: String(errore?.message ?? errore) }));
  process.exit(0);
}

let testo;
try {
  testo = JSON.stringify({ ok: true, risultato });
} catch {
  testo = JSON.stringify({ ok: false, errore: "il risultato non e' serializzabile in JSON" });
}
if (testo.length > TETTO) {
  testo = JSON.stringify({
    ok: true,
    troncato: true,
    byte: testo.length,
    anteprima: testo.slice(0, 1200),
  });
}
console.log(testo);
