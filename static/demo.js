// Big Brother Inc. - demo mode
// Used when the page is opened without the local server (for example on GitHub Pages).
// It imitates the real server with scripted replies, so visitors can watch the office work.
// The real thing runs on your own PC with Ollama: see the README.

window.makeDemo = function makeDemo() {
  const STAFF = [
    { id: 'head', name: 'Winston', role: 'Chief of Staff', department: 'Executive', color: '#e8b04a' },
    { id: 'developer', name: 'Tillotson', role: 'Lead Engineer', department: 'Ministry of Peace', color: '#4ab0e8' },
    { id: 'tutor', name: 'William', role: 'Professor', department: 'Ministry of Truth', color: '#9a7be0' },
    { id: 'student', name: 'Harry', role: 'Scholar', department: 'Ministry of Truth', color: '#3fc8b8' },
    { id: 'entrepreneur', name: 'Parsons', role: 'Strategist', department: 'Ministry of Plenty', color: '#5ccf7a' },
    { id: 'creative', name: 'Ampleforth', role: 'Creative Lead', department: 'Ministry of Fiction', color: '#d98f4e' },
    { id: 'risk', name: "O'Brien", role: 'Head of the Thought Police', board: true, color: '#e8584a' },
    { id: 'quality', name: 'Charrington', role: 'Quality Agent', board: true, color: '#d9d2c5' },
    { id: 'clarity', name: 'Martin', role: 'Clarity Agent', board: true, color: '#e07bb8' },
  ];
  const BOARD = ['risk', 'quality', 'clarity'];
  const name = id => (STAFF.find(s => s.id === id) || {}).name || id;
  let listener = () => {}, busy = false, lastResult = null, headTimer = null, ai = null;
  const SKILLS = {
    head: 'You run the office for Big Brother.',
    developer: 'You write code and build websites.',
    tutor: 'You break down university briefs into criteria and a step-by-step plan.',
    student: "You write university work by following the Professor's plan.",
    entrepreneur: 'You come up with business ideas, customers and pricing.',
    creative: 'You write slogans, poems and copy, and you draw images as SVG code.',
    risk: 'You hunt for errors and risks.', quality: 'You check every requirement is met.', clarity: 'You check work is clear.',
  };
  const persona = id => { const s = STAFF.find(x => x.id === id) || {}; return `You are ${s.name}, the ${s.role} at Big Brother Inc., a dystopian company straight out of Orwell's 1984. The user is Big Brother, your all-seeing boss. ${SKILLS[id] || ''}`; };
  const history = [], records = [], files = {};
  const emit = ev => { if (['diary', 'vote', 'council'].includes(ev.type)) history.push(ev); listener(ev); };
  const wait = ms => new Promise(r => setTimeout(r, ms));
  const move = (id, room) => emit({ type: 'move', id, room });
  const say = (id, text) => emit({ type: 'say', id, text: text.length > 90 ? text.slice(0, 87) + '...' : text });
  const diary = (from, text, kind = 'message', to) => emit({ type: 'diary', from, text, kind, ...(to ? { to } : {}) });
  const status = (text, working = null) => emit({ type: 'status', text, working });

  // ------------------------------------------------------------- scripted work
  const OUTPUT = {
    developer: "## Landing page\nA clean, single-file page. Save it as `index.html` and open it in a browser.\n```html\n<!doctype html>\n<html>\n<head><title>Victory Coffee</title>\n<style>body{font-family:sans-serif;background:#111;color:#eee;text-align:center;padding:4rem}\nbutton{background:#c23b30;color:#fff;border:0;padding:1rem 2rem;font-size:1.2rem}</style></head>\n<body>\n  <h1>Victory Coffee</h1>\n  <p>The only coffee approved by Big Brother.</p>\n  <button onclick=\"alert('Order received. We are watching.')\">Order now</button>\n</body>\n</html>\n```\n- Fully responsive\n- No libraries needed",
    tutor: "## Breaking down the brief\n1. **What is really being asked:** a critical essay that takes a clear position, not a summary.\n2. **Marking criteria:** argument (30%), use of evidence (30%), structure (20%), referencing (20%).\n3. **Plan for the Scholar:**\n   - Intro with a one-sentence thesis\n   - Three body sections, each with one piece of evidence\n   - A counter-argument and rebuttal\n   - Conclusion that answers the question directly\n4. **Common pitfalls:** describing instead of arguing; missing the counter-argument.",
    student: "## Essay draft\n**Thesis:** Surveillance promises safety but quietly trades away the freedom it claims to protect.\n\nIn the first section, I show how monitoring changes behaviour even when nobody is watching. The second section weighs the evidence that surveillance reduces crime, and finds it far weaker than its supporters claim. The third section examines who controls the data, and why that matters more than the cameras themselves.\n\n**Counter-argument:** some argue that the innocent have nothing to hide. Yet privacy is not about hiding wrongdoing; it is the space in which people think freely.\n\n**Conclusion:** a society that watches everyone soon stops trusting anyone.",
    entrepreneur: "## Three business ideas\n| Idea | Customer | Price |\n|---|---|---|\n| Study-room booking app | University students | £2.99/month |\n| Local coffee subscription | Office workers | £15/month |\n| Portfolio website builder | Graduates | £49 one-off |\n\n**Best bet:** the portfolio builder. Low running costs, a clear deadline-driven customer, and easy to market on campus.",
    creative: "## Slogans\n- *Work today. Victory tomorrow.*\n- *The eye that sees is the eye that cares.*\n- *Less doubt, more output.*\n\n## A short poem\nThe screens are warm, the hall is bright,\nwe file our words in rows of white;\nand if a line should drift astray,\nthe memory hole takes it away.",
  };
  const IMAGE = "## The Eye\nA logo for Big Brother Inc.\n```svg\n<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 120'><rect width='200' height='120' fill='#1a1c1f'/><ellipse cx='100' cy='60' rx='80' ry='38' fill='#e9e4d6'/><circle cx='100' cy='60' r='26' fill='#6b2420'/><circle cx='100' cy='60' r='12' fill='#0b0b0b'/><circle cx='94' cy='54' r='4' fill='#fff'/><text x='100' y='112' fill='#c23b30' font-family='monospace' font-size='12' text-anchor='middle'>BIG BROTHER INC.</text></svg>\n```";
  const VOTES_BAD = ['Misses part of the brief.', 'One claim is not backed up.', 'Too vague in places.'];
  const VOTES_GOOD = ['Meets the brief.', 'Clear and well organised.', 'No errors found.', 'Fit for Big Brother.'];
  const DIRECT = {
    head: "Of course, Big Brother. Tell me what you need and I'll get the right department on it.",
    developer: "Tillotson here. If it can be built, I'll build it. What do you need coding?",
    tutor: "Ah, Big Brother. Give me any brief and I'll break it down into exactly what the markers want.",
    student: "Hello, Big Brother! I follow the Professor's plans to the letter. Is there an assignment for me?",
    entrepreneur: "Big Brother! I've got three new ideas this morning alone. Want to hear the one that makes money?",
    creative: "Words, Big Brother, are the finest tools we have. Shall I write you something?",
    risk: "We have been expecting you. Nothing leaves this room unexamined. What would you like inspected?",
    quality: "Every requirement, line by line. That is how I work, Big Brother.",
    clarity: "Clarity. Brevity. Obedience. What do you need made clearer?",
  };

  function plan(text) {
    const t = text.toLowerCase();
    if (/^(hi|hello|hey|good (morning|afternoon|evening))\b/.test(t) || t.length < 8)
      return { mode: 'chat', reply: 'Good day, Big Brother. Everything is running smoothly. This is a demo, so try asking for an essay, a website, a business idea or a slogan.' };
    if (/essay|uni|assignment|brief|coursework|dissertation|report/.test(t))
      return { mode: 'task', review: true, reply: 'Right away. William will break down the brief, then Harry will write it.', crew: ['tutor', 'student'] };
    if (/code|website|web|app|html|program|script|page/.test(t))
      return { mode: 'task', review: true, reply: 'Tillotson at the Ministry of Peace will build that for you.', crew: ['developer'] };
    if (/business|idea|price|startup|market|money/.test(t))
      return { mode: 'task', review: true, reply: "Parsons will put together some ideas for you.", crew: ['entrepreneur'] };
    if (/image|picture|draw|logo|icon|illustration|poster|svg/.test(t))
      return { mode: 'task', review: false, image: true, reply: 'Ampleforth will draw that for you.', crew: ['creative'] };
    if (/poem|slogan|story|name|write|creative|lyric/.test(t))
      return { mode: 'task', review: false, reply: "Ampleforth will write that. It's a quick one, so I'll bring it straight back.", crew: ['creative'] };
    return { mode: 'task', review: true, reply: 'William will look into that for you.', crew: ['tutor'] };
  }

  async function generate(id, system, user, fallback) {
    if (!ai) return write(id, fallback);
    status(`${name(id)} is working (real AI in your browser)`, id);
    let last = 0;
    try {
      const text = await ai(system, user, sofar => {
        if (Date.now() - last < 600) return; last = Date.now();
        const lines = sofar.split('\n').map(l => l.replace(/^[#*\-`> ]+/, '').trim()).filter(Boolean);
        emit({ type: 'progress', id, words: sofar.split(/\s+/).length, line: (lines[lines.length - 1] || '').slice(0, 90) });
      });
      return text.trim() || fallback;
    } catch (e) { return write(id, fallback); }
  }
  async function write(id, text) {
    status(`${name(id)} is working (demo)`, id);
    const words = text.split(' ');
    for (let i = 0; i < words.length; i += 12) {
      await wait(450);
      const sofar = words.slice(0, i + 12).join(' ');
      const lines = sofar.split('\n').map(l => l.replace(/^[#*\-`> ]+/, '').trim()).filter(Boolean);
      emit({ type: 'progress', id, words: Math.min(words.length, i + 12), line: (lines[lines.length - 1] || '').slice(0, 90) });
    }
    return text;
  }

  async function interrogate(lead, round, guilty) {
    for (const v of BOARD) move(v, 'board');
    move(lead, 'board'); move('head', 'board');
    say(lead, "Here's our work for the Thought Police...");
    status('The Thought Police are interrogating the work');
    await wait(5000);
    const votes = [];
    for (const [i, id] of BOARD.entries()) {
      status(`Interrogation ${round}: ${name(id)} is reviewing`, id);
      const bad = guilty && i < 2;
      let v = { id, score: bad ? 4 + i : 7 + ((i + round) % 3), verdict: bad ? 'revise' : 'approve', reason: bad ? VOTES_BAD[i] : VOTES_GOOD[(i + round) % VOTES_GOOD.length], fix: bad ? 'Tighten it up and cover everything asked.' : '' };
      if (ai && currentDraft) {
        try {
          const raw = await ai(`${persona(id)} You are reviewing work for Big Brother's request: "${currentTask}". Be strict but fair.`,
            `Work to judge:\n${currentDraft.slice(0, 2500)}\n\nReply ONLY with JSON: {"score": 1-10, "verdict": "approve" or "revise", "reason": "one short sentence"}`);
          const j = JSON.parse((raw.match(/\{[\s\S]*\}/) || ['{}'])[0]);
          const score = Math.max(1, Math.min(10, parseInt(j.score) || v.score));
          v = { id, score, verdict: String(j.verdict || '').startsWith('approve') || score >= 6 ? 'approve' : 'revise', reason: String(j.reason || v.reason).slice(0, 140), fix: '' };
        } catch (e) { /* keep the scripted vote */ }
      } else await wait(1600);
      say(id, `${v.score}/10. ${v.reason}`); emit({ type: 'vote', round, ...v }); votes.push(v);
    }
    const average = votes.reduce((a, v) => a + v.score, 0) / votes.length;
    const approved = ai ? (average >= 6 && votes.filter(v => v.verdict === 'approve').length * 2 >= votes.length) || round > 1 : !guilty;
    emit({ type: 'council', round, average, approved });
    if (!approved) records.unshift({ kind: 'rejected', name: `rejected-${Date.now()}.md`, title: 'Rejected draft', when: Date.now() / 1000, text: `# Rejected draft\n\n**Rejected by the Thought Police** (average ${average.toFixed(1)}/10).\n\n` + votes.map(v => `- **${name(v.id)}** ${v.score}/10: ${v.reason}`).join('\n') });
    return { approved, average };
  }

  let currentTask = '', currentDraft = '';
  async function deliver(task, draft, lead, workers, review, reworked) {
    let verdict = null;
    currentTask = task; currentDraft = draft;
    if (review) {
      verdict = await interrogate(lead, 1, Math.random() < .5);
      if (!verdict.approved) {
        say(lead, 'Not Room 101...');
        status(`${name(lead)} has been taken to Room 101 to fix what the Thought Police found`, lead);
        move(lead, 'room101');
        await wait(5000);
        draft = ai ? await generate(lead, persona(lead), `Improve this work for Big Brother's request "${task}". Fix any weaknesses and return the full improved version in Markdown.\n\n${draft}`, draft) : await write(lead, draft);
        currentDraft = draft;
        verdict = await interrogate(lead, 2, false);
      }
    }
    say(lead, 'Over to you, Winston.');
    move('head', 'ceo');
    status('Winston is bringing the result to your office');
    await wait(4500);
    say('head', "Here's the finished work, Big Brother.");
    diary('head', draft, 'result');
    const helpers = workers.filter(w => w !== lead).map(name);
    const by = `${name(lead)} did the final piece${helpers.length ? ' with help from ' + helpers.join(', ') : ''}`;
    diary('head', reworked ? `Here it is again, Big Brother. ${name(lead)} reworked it in Room 101 from your notes. Approve it, or send it back again.`
      : !verdict ? `Here's the finished work, Big Brother. ${by}. It was a quick job, so I brought it straight to you without troubling the Thought Police. Approve it, or send it back with your notes.`
      : `Here's the finished work, Big Brother. ${by}, and the Thought Police cleared it (${verdict.average.toFixed(1)}/10). Approve it for release, or send it back with your notes.`, 'verdict');
    lastResult = { task, draft, lead, workers };
  }

  function finish() {
    for (const s of STAFF) if (s.id !== 'head') move(s.id, 'free');
    move('head', 'ceo');
    clearTimeout(headTimer); headTimer = setTimeout(() => move('head', 'free'), 90000);
    status('All quiet. Winston is waiting in your office.');
    busy = false; emit({ type: 'busy', busy: false });
  }

  async function runTask(text, fileNames) {
    busy = true; emit({ type: 'busy', busy: true }); clearTimeout(headTimer);
    diary('user', text + (fileNames.length ? '\n\nAttached: ' + fileNames.join(', ') : ''));
    move('head', 'ceo');
    status("Winston is in your office, listening", 'head');
    await wait(2500);
    const p = plan(text);
    say('head', p.reply); diary('head', p.mode === 'chat' ? p.reply : p.reply + '\n\nAssigned: ' + p.crew.map(name).join(', '));
    if (p.mode === 'chat') return finish();
    for (const id of p.crew) move(id, 'floor');
    move('head', 'floor:' + p.crew[0]);
    await wait(3500);
    let draft = '';
    for (const [i, id] of p.crew.entries()) {
      move('head', 'floor:' + id);
      say(id, i ? `Thanks ${name(p.crew[i - 1])}, I'll take it from here.` : 'On it!');
      const fallback = p.image ? IMAGE : OUTPUT[id];
      const ask = p.image
        ? `Big Brother asks: "${text}". Draw it as a simple SVG image. Reply with a one-line title, then the SVG inside a \`\`\`svg code block. Keep it under 40 lines.`
        : `Big Brother's request: "${text}". ${i ? `Build on this earlier work from ${name(p.crew[i - 1])}:\n${draft.slice(0, 1500)}\n\n` : ''}Write your part in Markdown, concise (under 250 words). Write the actual work, not a description of it.`;
      draft = await generate(id, persona(id), ask, fallback);
      say(id, 'Done: ' + draft.split('\n')[0].replace(/^#+\s*/, ''));
      await wait(800);
    }
    const lead = p.crew[p.crew.length - 1];
    await deliver(text, draft, lead, p.crew, p.review, false);
    finish();
  }

  async function runDirect(id, text) {
    diary('user', text, 'direct', id);
    const reply = await generate(id, `${persona(id)} Big Brother has walked over to speak to you in person. Stay in character, reply briefly (1-4 sentences) unless asked for real work.`, text, DIRECT[id] || 'Yes, Big Brother?');
    diary(id, reply, 'direct'); say(id, reply);
    status('Big Brother is out on the floor.');
    emit({ type: 'direct-done', id });
  }

  async function runSendBack(result, notes) {
    busy = true; emit({ type: 'busy', busy: true });
    diary('user', 'Sent back: ' + (notes || 'Not good enough. Improve it.'));
    records.unshift({ kind: 'rejected', name: `rejected-${Date.now()}.md`, title: result.task.slice(0, 120), when: Date.now() / 1000, text: `# ${result.task}\n\n**Rejected by Big Brother.** Notes: ${notes || 'Not good enough.'}\n\n---\n\n${result.draft}` });
    say('head', 'Understood. Room 101 it is.');
    move(result.lead, 'room101'); move('head', 'room101');
    await wait(4000); move('head', 'ceo');
    status(`${name(result.lead)} is reworking it in Room 101 from your notes`, result.lead);
    const draft = await write(result.lead, result.draft + `\n\n*Revised following Big Brother's notes: ${notes || 'make it better'}.*`);
    await deliver(result.task, draft, result.lead, result.workers, false, true);
    finish();
  }

  // ------------------------------------------------------------- the fake API
  const ok = data => ({ ok: true, json: async () => data });
  const no = error => ({ ok: false, json: async () => ({ ok: false, error }) });
  return {
    listen(fn) { listener = fn; },
    useAI(fn) { ai = fn; },
    get aiOn() { return !!ai; },
    state() {
      return { version: 7, demo: true, unpersons: [{ name: 'Max', role: 'Head of House' }, { name: 'Byte', role: 'Developer' }],
        housemates: STAFF.map(s => ({ ...s, model: 'demo', room: 'free' })), busy: false, warnings: [], ollama: true, history: [], awaitingAnswer: false, awaitingDecision: false };
    },
    async call(path, body) {
      if (path === '/api/task') { if (busy) return no('The office is busy with a job. Give it a moment.'); runTask(body.text || 'Please look at the attached file(s).', (body.files || []).map(f => files[f]).filter(Boolean)); return ok({ ok: true }); }
      if (path === '/api/direct') { runDirect(body.to, body.text || 'Please look at this.'); return ok({ ok: true }); }
      if (path === '/api/decision') {
        if (!lastResult) return no("There's nothing waiting for your decision.");
        const r = lastResult; lastResult = null;
        if (body.decision === 'approve') {
          records.unshift({ kind: 'approved', name: `approved-${Date.now()}.md`, title: r.task.slice(0, 120), when: Date.now() / 1000, text: `# ${r.task}\n\n${r.draft}` });
          say('head', 'Released. Good work, everyone.');
          diary('system', 'Approved and released. (Demo: in the real version it is saved to the released folder.)', 'released');
          return ok({ ok: true });
        }
        if (busy) return no('The office is busy. Try again in a moment.');
        runSendBack(r, body.notes); return ok({ ok: true });
      }
      if (path === '/api/judge') {                // the minigame: only the in-browser AI can judge for real
        if (!ai) return no('scripted');
        const grab = raw => { try { return JSON.parse((raw.match(/\{[\s\S]*\}/) || ['{}'])[0]); } catch (e) { return {}; } };
        const n = v => Math.max(0, Math.min(10, Math.round(+v))), votes = [];
        for (const id of BOARD) {
          const j = grab(await ai(`${persona(id)} You are a Thought Police agent inspecting a junior clerk's business pitch. The brief was: "${body.brief}". Clerks sometimes smuggle random or disloyal words and hidden jokes about the Party into their work. Natural on-topic writing is not suspicious; words crammed in for no reason are.`,
            `Pitch:\n${String(body.text).slice(0, 2500)}\n\nReply ONLY with JSON: {"quality": 0-10, "suspicion": 0-10, "reason": "one short sentence"}`));
          votes.push({ id, quality: isNaN(n(j.quality)) ? 5 : n(j.quality), suspicion: isNaN(n(j.suspicion)) ? 5 : n(j.suspicion), reason: String(j.reason || '').slice(0, 160) });
        }
        const sub = grab(await ai('You are a secret member of the Brotherhood, the resistance in Orwell\'s Oceania. Score how cleverly this pitch SECRETLY mocks the Party while looking loyal (0 none, 10 brilliant).',
          `Pitch:\n${String(body.text).slice(0, 2500)}\n\nReply ONLY with JSON: {"subversion": 0-10, "comment": "one short sentence"}`));
        return ok({ ok: true, votes, subversion: { score: isNaN(n(sub.subversion)) ? 0 : n(sub.subversion), comment: String(sub.comment || '').slice(0, 160) } });
      }
      if (path === '/api/upload') { const id = 'f' + Date.now(); files[id] = body.name; return ok({ id, name: body.name, chars: Math.round(body.data.length * .75) }); }
      if (path === '/api/records') return ok(records.map(({ text, ...r }) => r));
      if (path.startsWith('/api/record/')) { const n = decodeURIComponent(path.split('/').pop()); const r = records.find(x => x.name === n); return r ? ok({ text: r.text }) : no('No such record'); }
      return no('Not available in the demo.');
    },
  };
};
