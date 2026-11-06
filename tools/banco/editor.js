/**
 * L'editor «clicca il testo» del banco — uno solo, per tutti i progetti.
 *
 * Perche' esiste: correggere una frase non deve voler dire aprire il JSON, cercare
 * la chiave giusta e rischiare di rompere le virgole. Il banco avvia il sito e
 * questo file; il progetto dichiara solo *quali* testi sono modificabili, mettendo
 * `data-scritta="home.eroe.titolo"` sugli elementi (l'helper `segna()` dei
 * progetti fa questo).
 *
 * Cosa fa:
 *  - un indicatore discreto in basso a destra («Modifica in pagina») con un
 *    interruttore, che spegne l'editor senza ricaricare la pagina;
 *  - passando il mouse su un testo modificabile compare un contorno leggero;
 *  - al clic si apre una casella ancorata all'elemento con il valore attuale letto
 *    dal file dei contenuti — non dal DOM, cosi' i testi composti si modificano
 *    interi;
 *  - Invio o «Salva» scrive il valore tramite il banco, Esc annulla, poi la pagina
 *    si ricarica;
 *  - se il banco non risponde, il messaggio dice cosa lanciare. Nessuna eccezione
 *    arriva alla pagina.
 *
 * Da dove prende l'indirizzo del banco: dal proprio `src`. Cosi' se la porta 4320
 * e' occupata e il banco sceglie la 4321, l'editor lo segue senza configurazione.
 *
 * Niente framework, niente dipendenze, niente font esterni. Il foglio di stile e'
 * `editor.css`, servito dallo stesso banco e agganciato qui sotto.
 */
(() => {
	'use strict';

	if (window.__bancoAvviato) return;
	window.__bancoAvviato = true;

	/* `document.currentScript` vale per uno script classico; con `type="module"`
	   e' null. In quel caso si cerca il tag che ha caricato questo file: l'origine
	   del banco e' la stessa, e l'editor non deve indovinare la porta. */
	const script =
		document.currentScript ||
		[...document.querySelectorAll('script[src]')].find((tag) =>
			/\/editor\.js(?:\?|$)/.test(tag.src)
		);
	const BASE = (() => {
		try {
			return new URL(script ? script.src : 'http://127.0.0.1:4320/editor.js', location.href).origin;
		} catch {
			return 'http://127.0.0.1:4320';
		}
	})();
	const COMANDO = 'python3 tools/banco.py "<progetto>"';
	const CHIAVE_ATTIVA = 'banco:attiva';

	/** Lo stato dell'editor. `dati` e' il file dei contenuti, non il DOM. */
	let attiva = true;
	let raggiungibile = false;
	let dati = null;
	let campi = {};
	let indicatore = null;
	let pannello = null;
	let elementoAperto = null;
	let percorsoAperto = '';
	let valoreAperto = null;
	let tipoAperto = 'testo';
	let salvando = false;
	/* Le immagini gia' presenti nel progetto: il banco le elenca, l'editor le
	   propone. Il banco non carica file: qui si sceglie un percorso, non un'immagine. */
	let immagini = [];
	let fotiAperte = [];

	/* ---------------------------------------------------------------- */
	/* Stili                                                             */
	/* ---------------------------------------------------------------- */

	function iniettaStili() {
		if (document.getElementById('banco-stili')) return;
		const collegamento = document.createElement('link');
		collegamento.id = 'banco-stili';
		collegamento.rel = 'stylesheet';
		collegamento.href = `${BASE}/editor.css`;
		document.head.appendChild(collegamento);
	}

	/* ---------------------------------------------------------------- */
	/* Lettura del JSON                                                  */
	/* ---------------------------------------------------------------- */

	function leggi(percorso) {
		if (!dati) return undefined;
		let valore = dati;
		for (const chiave of percorso.split('.')) {
			if (valore === null || typeof valore !== 'object') return undefined;
			valore = valore[chiave];
		}
		return valore;
	}

	function scriviNeiDati(percorso, valore) {
		if (!dati) return;
		const chiavi = percorso.split('.');
		let nodo = dati;
		for (const chiave of chiavi.slice(0, -1)) {
			if (nodo === null || typeof nodo !== 'object') return;
			nodo = nodo[chiave];
		}
		if (nodo !== null && typeof nodo === 'object') {
			nodo[chiavi[chiavi.length - 1]] = valore;
		}
	}

	/* ---------------------------------------------------------------- */
	/* Indicatore e avvisi                                               */
	/* ---------------------------------------------------------------- */

	function creaIndicatore() {
		const scatola = document.createElement('div');
		scatola.className = 'banco-indicatore';
		scatola.setAttribute('role', 'group');
		scatola.setAttribute('aria-label', 'Editor dei testi in pagina');

		const pallino = document.createElement('span');
		pallino.className = 'banco-pallino';
		pallino.setAttribute('aria-hidden', 'true');

		const testo = document.createElement('span');
		testo.className = 'banco-testo';
		testo.textContent = 'Modifica in pagina';

		const etichetta = document.createElement('label');
		etichetta.className = 'banco-interruttore';
		etichetta.title = 'Spegne o accende l’editor dei testi';

		const casella = document.createElement('input');
		casella.type = 'checkbox';
		casella.checked = attiva;
		casella.setAttribute('role', 'switch');
		casella.setAttribute('aria-label', 'Modifica in pagina');
		casella.addEventListener('change', () => impostaAttiva(casella.checked));

		const cursore = document.createElement('span');
		etichetta.append(casella, cursore);

		scatola.append(pallino, testo, etichetta);
		document.body.appendChild(scatola);
		indicatore = scatola;
		aggiornaIndicatore();
	}

	function aggiornaIndicatore() {
		if (!indicatore) return;
		const casella = indicatore.querySelector('input');
		if (casella) {
			casella.checked = attiva;
			casella.setAttribute('aria-checked', attiva ? 'true' : 'false');
		}
		indicatore.classList.toggle('banco-spento', !attiva);
		indicatore.classList.toggle('banco-guasto', attiva && !raggiungibile);
		indicatore.title = !attiva
			? 'Editor spento: i testi non si modificano.'
			: raggiungibile
				? 'I testi si modificano con un clic.'
				: `Il banco non risponde su ${BASE}. Lancialo con: ${COMANDO}`;
	}

	function avvisa(messaggio) {
		const vecchio = document.querySelector('.banco-avviso');
		if (vecchio) vecchio.remove();
		const scatola = document.createElement('div');
		scatola.className = 'banco-avviso';
		scatola.setAttribute('role', 'status');
		scatola.textContent = messaggio;
		scatola.addEventListener('click', () => scatola.remove());
		document.body.appendChild(scatola);
		window.setTimeout(() => scatola.remove(), 12000);
	}

	function impostaAttiva(valore) {
		attiva = valore;
		try {
			localStorage.setItem(CHIAVE_ATTIVA, valore ? '1' : '0');
		} catch {
			/* localStorage negato: l'editor funziona lo stesso, non ricorda nulla. */
		}
		document.documentElement.classList.toggle('banco-attiva', attiva);
		if (!attiva) chiudi();
		aggiornaIndicatore();
	}

	/* ---------------------------------------------------------------- */
	/* Caricamento dei dati                                              */
	/* ---------------------------------------------------------------- */

	async function caricaTutto() {
		try {
			const [stato, contenuti] = await Promise.all([
				fetch(`${BASE}/api/stato`, { headers: { Accept: 'application/json' } }),
				fetch(`${BASE}/api/contenuti`, { headers: { Accept: 'application/json' } }),
			]);
			if (!stato.ok || !contenuti.ok) throw new Error('risposta non valida');
			const corpoStato = await stato.json();
			dati = await contenuti.json();
			campi = (corpoStato && corpoStato.campi) || {};
			raggiungibile = true;
		} catch {
			dati = null;
			campi = {};
			raggiungibile = false;
		}
		aggiornaIndicatore();
	}

	/** Le immagini del progetto, per il menu del campo «foto». Non blocca mai. */
	async function caricaImmagini() {
		try {
			const risposta = await fetch(`${BASE}/api/immagini`, {
				headers: { Accept: 'application/json' },
			});
			if (!risposta.ok) return;
			const corpo = await risposta.json();
			immagini = Array.isArray(corpo && corpo.immagini) ? corpo.immagini : [];
		} catch {
			immagini = [];
		}
	}

	/* ---------------------------------------------------------------- */
	/* Pannello                                                          */
	/* ---------------------------------------------------------------- */

	function messaggio(testo, tipo) {
		const nodo = pannello && pannello.querySelector('.banco-messaggio');
		if (!nodo) return;
		nodo.textContent = testo;
		nodo.className = 'banco-messaggio' + (tipo ? ` banco-${tipo}` : '');
	}

	function posiziona() {
		if (!pannello || !elementoAperto) return;
		const rettangolo = elementoAperto.getBoundingClientRect();
		const larghezza = pannello.offsetWidth;
		const altezza = pannello.offsetHeight;
		const margine = 10;
		const sinistra = Math.min(
			Math.max(margine, rettangolo.left),
			window.innerWidth - larghezza - margine
		);
		let sopra = rettangolo.bottom + 8;
		if (sopra + altezza > window.innerHeight - margine && rettangolo.top - altezza - 8 > margine) {
			sopra = rettangolo.top - altezza - 8;
		}
		sopra = Math.min(Math.max(margine, sopra), window.innerHeight - altezza - margine);
		pannello.style.left = `${Math.round(sinistra)}px`;
		pannello.style.top = `${Math.round(sopra)}px`;
	}

	function chiudi() {
		if (!pannello) return;
		pannello.remove();
		pannello = null;
		if (elementoAperto) elementoAperto.classList.remove('banco-scelto');
		elementoAperto = null;
		percorsoAperto = '';
		valoreAperto = null;
		salvando = false;
	}

	async function salva() {
		if (!pannello || !percorsoAperto || salvando) return;
		const casella = pannello.querySelector('.banco-casella');
		const campoFoto = pannello.querySelector('.banco-foto-percorso');
		if (!casella && !campoFoto) return;

		let valore;
		if (tipoAperto === 'foto') {
			valore = campoFoto ? campoFoto.value.trim() : '';
			if (!valore) {
				messaggio('Scegli un\'immagine dal menu, o scrivi il percorso.', 'errore');
				if (campoFoto) campoFoto.focus();
				return;
			}
		} else if (tipoAperto === 'elenco') {
			valore = casella.value
				.split('\n')
				.map((riga) => riga.trim())
				.filter((riga) => riga.length > 0);
			if (valore.length === 0) {
				messaggio('Serve almeno una riga.', 'errore');
				casella.focus();
				return;
			}
		} else {
			valore = casella.value;
		}

		salvando = true;
		const bottone = pannello.querySelector('.banco-salva');
		if (bottone) bottone.disabled = true;
		messaggio('Salvataggio…');

		try {
			const risposta = await fetch(`${BASE}/api/salva`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				credentials: 'omit',
				body: JSON.stringify({ percorso: percorsoAperto, valore }),
			});
			const corpo = await risposta.json().catch(() => ({}));
			if (!risposta.ok) {
				throw new Error(corpo.errore || `Il banco ha risposto ${risposta.status}.`);
			}
			scriviNeiDati(percorsoAperto, valore);
			raggiungibile = true;
			aggiornaIndicatore();
			messaggio('Salvato. La pagina si aggiorna…', 'ok');
			window.setTimeout(chiudi, 400);
			window.setTimeout(() => location.reload(), 800);
		} catch (errore) {
			salvando = false;
			if (bottone) {
				bottone.disabled = false;
				bottone.textContent = 'Invia';
			}
			const rete = errore instanceof TypeError;
			raggiungibile = !rete;
			aggiornaIndicatore();
			if (rete) {
				messaggio(
					`Il banco non risponde su ${BASE}. Apri un terminale e lancia: ${COMANDO}`,
					'errore'
				);
			} else {
				messaggio(errore instanceof Error ? errore.message : 'Salvataggio non riuscito.', 'errore');
			}
		}
	}

	async function apri(elemento) {
		const percorso = elemento.getAttribute('data-scritta');
		if (!percorso) return;
		if (!dati) {
			/* Il banco puo' essere partito dopo la pagina: si riprova, cosi' non
			   serve ricaricare. Se ancora non risponde, si dice cosa lanciare. */
			await caricaTutto();
		}
		if (!dati) {
			avvisa(
				`Il banco non risponde su ${BASE}. Apri un terminale nella cartella del motore e lancia «${COMANDO}».`
			);
			return;
		}
		const configurazione = campi[percorso] || {};
		const valore = leggi(percorso);
		const eFoto = configurazione.tipo === 'foto';
		if (!eFoto && typeof valore !== 'string' && !Array.isArray(valore)) {
			avvisa(`Nessun testo trovato per «${percorso}» nel file dei contenuti.`);
			return;
		}
		if (eFoto && immagini.length === 0) await caricaImmagini();
		tipoAperto = eFoto ? 'foto' : Array.isArray(valore) ? 'elenco' : configurazione.tipo || 'testo';

		chiudi();
		percorsoAperto = percorso;
		valoreAperto = valore;
		elementoAperto = elemento;
		elemento.classList.add('banco-scelto');

		const scatola = document.createElement('div');
		scatola.className = 'banco-pannello';
		scatola.setAttribute('role', 'dialog');
		scatola.setAttribute('aria-label', `Modifica: ${percorso}`);

		const testa = document.createElement('div');
		testa.className = 'banco-testa';
		const descrizione = document.createElement('div');
		descrizione.className = 'banco-descrizione';
		const etichetta = document.createElement('span');
		etichetta.className = 'banco-etichetta';
		etichetta.textContent = configurazione.etichetta || percorso;
		const codice = document.createElement('code');
		codice.className = 'banco-percorso';
		codice.textContent = percorso;
		descrizione.append(etichetta, codice);
		const chiudiBottone = document.createElement('button');
		chiudiBottone.type = 'button';
		chiudiBottone.className = 'banco-chiudi';
		chiudiBottone.setAttribute('aria-label', 'Chiudi');
		chiudiBottone.textContent = '×';
		chiudiBottone.addEventListener('click', chiudi);
		testa.append(descrizione, chiudiBottone);

		const corpo = document.createElement('div');
		corpo.className = 'banco-corpo';

		let casella = null;
		let campoFoto = null;
		if (tipoAperto === 'foto') {
			const { scelta, percorso } = costruisciFoto(String(valore || ''));
			corpo.append(scelta);
			campoFoto = percorso;
		} else {
			casella = document.createElement('textarea');
			casella.className = 'banco-casella';
			casella.spellcheck = false;
			casella.value = Array.isArray(valore) ? valore.join('\n') : String(valore);
			casella.rows = Math.min(10, Math.max(2, casella.value.split('\n').length));
			casella.addEventListener('keydown', (evento) => {
				if (evento.key === 'Escape') {
					evento.preventDefault();
					chiudi();
					return;
				}
				if (evento.key === 'Enter' && !evento.shiftKey && !evento.isComposing) {
					evento.preventDefault();
					void salva();
				}
			});
			corpo.append(casella);
		}

		const aiuto = document.createElement('p');
		aiuto.className = 'banco-aiuto';
		aiuto.textContent =
			tipoAperto === 'foto'
				? 'Scegli un\'immagine gia\' presente nel progetto, o scrivi il percorso. ' +
					'Il banco non carica file: le foto le metti tu nella cartella.'
				: tipoAperto === 'elenco'
					? 'Una riga per voce. Invio salva · Maiusc+Invio va a capo · Esc annulla.'
					: 'Invio salva · Maiusc+Invio va a capo · Esc annulla.';

		const piede = document.createElement('div');
		piede.className = 'banco-piede';
		const stato = document.createElement('span');
		stato.className = 'banco-messaggio';
		const aiBottone = document.createElement('button');
		aiBottone.type = 'button';
		aiBottone.className = 'banco-ai';
		aiBottone.textContent = 'Chiedi all\'AI';
		aiBottone.title =
			'Scrivi cosa vuoi cambiare: la richiesta diventa un file in ' +
			'Analisi-Prompt-Report/Richieste/ e l\'agente propone la modifica. ' +
			'Il contenuto non viene toccato finche\' non approvi.';
		aiBottone.addEventListener('click', () => apriRichiestaAI());
		const salvaBottone = document.createElement('button');
		salvaBottone.type = 'button';
		salvaBottone.className = 'banco-salva';
		salvaBottone.textContent = tipoAperto === 'foto' ? 'Usa questa foto' : 'Salva';
		salvaBottone.addEventListener('click', () => void salva());
		piede.append(stato, aiBottone, salvaBottone);

		scatola.append(testa, corpo, aiuto, piede);
		document.body.appendChild(scatola);
		pannello = scatola;
		posiziona();

		const fuoco = casella || campoFoto;
		if (fuoco) {
			fuoco.focus();
			if (fuoco.setSelectionRange) {
				const fine = fuoco.value.length;
				fuoco.setSelectionRange(fine, fine);
			}
		}
	}

	/** Il selettore di una foto: menu delle immagini presenti + percorso a mano. */
	function costruisciFoto(valoreAttuale) {
		const blocco = document.createElement('div');
		blocco.className = 'banco-foto';

		const anteprima = document.createElement('img');
		anteprima.className = 'banco-foto-anteprima';
		anteprima.alt = 'Anteprima della foto scelta';
		anteprima.hidden = true;

		const scelta = document.createElement('select');
		scelta.className = 'banco-foto-scelta';
		const vuota = document.createElement('option');
		vuota.value = '';
		vuota.textContent = immagini.length
			? `— scegli fra ${immagini.length} immagini del progetto —`
			: '— nessuna immagine trovata nel progetto —';
		scelta.append(vuota);
		for (const percorso of immagini) {
			const opzione = document.createElement('option');
			opzione.value = percorso;
			opzione.textContent = percorso;
			scelta.append(opzione);
		}

		const percorso = document.createElement('input');
		percorso.type = 'text';
		percorso.className = 'banco-foto-percorso';
		percorso.spellcheck = false;
		percorso.placeholder = '/immagini/team.jpg';
		percorso.value = valoreAttuale;

		const mostra = (indirizzo) => {
			const testo = String(indirizzo || '').trim();
			if (!testo) {
				anteprima.hidden = true;
				anteprima.removeAttribute('src');
				return;
			}
			/* Il percorso e' relativo al sito: l'anteprima la serve il sito stesso,
			   quindi si risolve sull'origine della pagina, non su quella del banco. */
			try {
				anteprima.src = new URL(testo, location.origin).href;
				anteprima.hidden = false;
			} catch {
				anteprima.hidden = true;
			}
		};

		scelta.addEventListener('change', () => {
			if (!scelta.value) return;
			percorso.value = scelta.value;
			mostra(scelta.value);
			percorso.focus();
		});
		percorso.addEventListener('input', () => mostra(percorso.value));
		percorso.addEventListener('keydown', (evento) => {
			if (evento.key === 'Escape') {
				evento.preventDefault();
				chiudi();
			}
		});
		anteprima.addEventListener('error', () => {
			anteprima.hidden = true;
		});

		if (valoreAttuale) {
			const trovata = immagini.includes(valoreAttuale);
			if (trovata) scelta.value = valoreAttuale;
			mostra(valoreAttuale);
		}

		const etichettaFoglio = document.createElement('label');
		etichettaFoglio.className = 'banco-foto-etichetta';
		etichettaFoglio.textContent = 'Percorso nel progetto';
		etichettaFoglio.append(percorso);

		blocco.append(anteprima, scelta, etichettaFoglio);
		return { scelta: blocco, percorso };
	}

	/** Il pannello «chiedi all'AI»: registra una richiesta, non modifica niente. */
	function apriRichiestaAI() {
		if (!pannello || !percorsoAperto) return;
		if (pannello.querySelector('.banco-ai-pannello')) {
			pannello.querySelector('.banco-ai-pannello').remove();
			return;
		}
		const scatola = document.createElement('div');
		scatola.className = 'banco-ai-pannello';

		const testo = document.createElement('p');
		testo.className = 'banco-ai-testo';
		testo.textContent =
			'Cosa vuoi cambiare? La richiesta viene salvata come file e l\'agente ' +
			'propone la modifica: qui non si tocca niente.';

		const istruzione = document.createElement('textarea');
		istruzione.className = 'banco-ai-istruzione';
		istruzione.rows = 3;
		istruzione.spellcheck = true;
		istruzione.placeholder = 'Es.: rendi il titolo piu\' corto e diretto';
		istruzione.addEventListener('keydown', (evento) => {
			if (evento.key === 'Escape') {
				evento.preventDefault();
				scatola.remove();
			}
			/* Invio manda, come in una chat. Shift+Invio va a capo. */
			if (evento.key === 'Enter' && !evento.shiftKey) {
				evento.preventDefault();
				void inviaRichiesta(istruzione.value, fotoScelte.value, invia, scatola);
			}
		});

		const fotoScelte = document.createElement('input');
		fotoScelte.type = 'text';
		fotoScelte.className = 'banco-ai-foto';
		fotoScelte.spellcheck = false;
		fotoScelte.placeholder = 'Foto (facoltativo): /immagini/team.jpg';

		const invia = document.createElement('button');
		invia.type = 'button';
		invia.className = 'banco-ai-invia';
		invia.textContent = 'Invia';
		invia.addEventListener('click', () => void inviaRichiesta(istruzione.value, fotoScelte.value, invia, scatola));

		scatola.append(testo, istruzione, fotoScelte, invia);
		pannello.append(scatola);
		istruzione.focus();
	}

	async function inviaRichiesta(istruzione, fotoTesto, bottone, scatola) {
		const testo = String(istruzione || '').trim();
		if (!testo) {
			messaggio('Scrivi cosa vuoi cambiare.', 'errore');
			return;
		}
		const foto = String(fotoTesto || '')
			.split(',')
			.map((voce) => voce.trim())
			.filter((voce) => voce.length > 0);
		if (bottone) {
			bottone.disabled = true;
			bottone.textContent = 'Invio…';
		}
		messaggio('Invio la richiesta…');
		try {
			const risposta = await fetch(`${BASE}/api/richieste`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				credentials: 'omit',
				body: JSON.stringify({ percorso: percorsoAperto, istruzione: testo, foto }),
			});
			const corpo = await risposta.json().catch(() => ({}));
			if (!risposta.ok) {
				throw new Error(corpo.errore || `Il banco ha risposto ${risposta.status}.`);
			}
			/* La richiesta e' partita. Il pannello resta aperto e mostra cosa manca:
			   l'agente non e' un servizio che risponde in un secondo, e' la sessione
			   in cui si lavora. Dire la verita' e' meglio che far aspettare a vuoto. */
			const conferma = document.createElement('div');
			conferma.className = 'banco-ai-conferma';
			conferma.innerHTML =
				'<strong>Richiesta inviata.</strong><br>' +
				`<code>${corpo.richiesta || ''}</code><br>` +
				'L’agente la legge appena torni nella chat e applica la modifica. ' +
				'Qui vedrai il testo nuovo: ricarica la pagina per vederlo.';
			scatola.querySelector('.banco-ai-conferma')?.remove();
			scatola.append(conferma);
			messaggio(`Inviata: ${corpo.richiesta}`, 'ok');
			if (bottone) {
				bottone.disabled = false;
				bottone.textContent = 'Invia';
			}
			if (istruzione) istruzione.value = '';
		} catch (errore) {
			if (bottone) {
				bottone.disabled = false;
				bottone.textContent = 'Invia';
			}
			const rete = errore instanceof TypeError;
			messaggio(
				rete
					? `Il banco non risponde su ${BASE}. Apri un terminale e lancia: ${COMANDO}`
					: errore instanceof Error
						? errore.message
						: 'Richiesta non registrata.',
				'errore'
			);
		}
	}

	/* ---------------------------------------------------------------- */
	/* Eventi                                                            */
	/* ---------------------------------------------------------------- */

	function dentroPannello(evento) {
		return evento.target instanceof Node && !!pannello && pannello.contains(evento.target);
	}

	function collegaEventi() {
		document.addEventListener(
			'click',
			(evento) => {
				if (!attiva) return;
				if (dentroPannello(evento)) return;
				const bersaglio = evento.target;
				if (!(bersaglio instanceof Element)) return;
				const elemento = bersaglio.closest('[data-scritta]');
				if (!elemento) return;
				evento.preventDefault();
				evento.stopPropagation();
				void apri(elemento);
			},
			true
		);

		document.addEventListener(
			'keydown',
			(evento) => {
				if (evento.key === 'Escape' && pannello) {
					evento.preventDefault();
					chiudi();
				}
			},
			true
		);

		document.addEventListener('mousedown', (evento) => {
			if (!pannello || dentroPannello(evento)) return;
			const bersaglio = evento.target;
			if (bersaglio instanceof Element && bersaglio.closest('[data-scritta]')) return;
			chiudi();
		});

		const riposiziona = () => {
			if (!pannello) return;
			window.requestAnimationFrame(posiziona);
		};
		window.addEventListener('scroll', riposiziona, { passive: true });
		window.addEventListener('resize', riposiziona);
	}

	/* ---------------------------------------------------------------- */
	/* Avvio                                                             */
	/* ---------------------------------------------------------------- */

	function avvia() {
		if (!document.body) return;
		try {
			if (localStorage.getItem(CHIAVE_ATTIVA) === '0') attiva = false;
		} catch {
			/* localStorage negato: l'editor parte acceso. */
		}
		iniettaStili();
		creaIndicatore();
		document.documentElement.classList.toggle('banco-attiva', attiva);
		collegaEventi();
		void caricaTutto();
	}

	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', avvia, { once: true });
	} else {
		avvia();
	}
})();
