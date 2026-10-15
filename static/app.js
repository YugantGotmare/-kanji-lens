const $ = id => document.getElementById(id);
const synth = window.speechSynthesis;
let voices = [], request;
const storageKey = 'kanji-lens-study-v1';
let saved = new Map(), storageReady = true, reviewQueue = [], reviewed = 0;
function persist(next) {
  if (!storageReady) { $('storage-status').textContent = 'Saved data could not be read. Resolve browser storage access before saving.'; return false; }
  try {
    localStorage.setItem(storageKey, JSON.stringify({version: 1, words: [...next.values()]}));
    saved = next; $('saved-count').textContent = saved.size;
    $('storage-status').textContent = '';
    return true;
  } catch { $('storage-status').textContent = 'Could not save your changes. Browser storage may be full or blocked.'; $('status').textContent = $('storage-status').textContent; return false; }
}
function saveButton(word) {
  const button = node('button', saved.has(Study.key(word)) ? '✓ Saved' : '＋ Save word', 'save-word');
  button.type = 'button'; button.dataset.key = Study.key(word);
  button.onclick = () => {
    const key = Study.key(word), next = new Map(saved);
    if (next.has(key)) next.delete(key);
    else {
      if (next.size >= 5000) { $('status').textContent = 'Your collection is full (5,000 words). Export a backup or remove a word first.'; return; }
      next.set(key, Study.clean(word));
    }
    if (persist(next)) document.querySelectorAll('.save-word').forEach(b => {
      b.textContent = saved.has(b.dataset.key) ? '✓ Saved' : '＋ Save word';
      b.setAttribute('aria-pressed', String(saved.has(b.dataset.key)));
    });
  };
  button.setAttribute('aria-pressed', String(saved.has(Study.key(word))));
  return button;
}
function node(tag, text, className) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (className) el.className = className;
  return el;
}
function loadVoices() {
  const selected = $('voice').value;
  voices = synth ? synth.getVoices().filter(v => /^ja(?:-|$)/i.test(v.lang)) : [];
  $('voice').replaceChildren(...voices.map(v => new Option(v.name, v.voiceURI)));
  if (voices.some(v => v.voiceURI === selected)) $('voice').value = selected;
  $('audio-status').textContent = voices.length ? '' : 'Japanese audio unavailable. Enable a Japanese voice on your device or try another browser.';
  document.querySelectorAll('.speak').forEach(b => b.disabled = !voices.length);
}
function audio(text, label) {
  const button = node('button', label, 'speak');
  button.type = 'button';
  button.disabled = !voices.length;
  button.onclick = () => {
    const voice = voices.find(v => v.voiceURI === $('voice').value);
    if (!synth || !voice) return;
    synth.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'ja-JP'; utterance.voice = voice; utterance.rate = Number($('speed').value);
    utterance.onerror = e => { if (!['interrupted', 'canceled'].includes(e.error)) $('audio-status').textContent = 'Audio could not play. Try another Japanese voice.'; };
    synth.speak(utterance);
  };
  return button;
}
function render(entries) {
  $('results').replaceChildren();
  for (const entry of entries) {
    const section = node('section');
    section.append(node('h2', `${entry.literal} · ${entry.meanings}`));
    const grade = entry.grade >= 1 && entry.grade <= 6 ? `School grade ${entry.grade}` : entry.grade === 8 ? 'General-use kanji' : 'Additional kanji';
    section.append(node('p', `${entry.strokes} strokes · ${grade}`, 'muted'));
    for (const group of entry.groups) {
      const block = node('div', undefined, 'group');
      const kind = {on: 'On reading', kun: 'Kun reading', special: 'Set words', other: 'Other reading'}[group.type];
      block.append(node('h3', `${group.title} · ${kind}`));
      if (group.kun_forms) block.append(node('p', group.kun_forms, 'muted'));
      for (const word of group.words) {
        const card = node('article');
        const heading = node('h4');
        const ruby = node('ruby', word.word); ruby.lang = 'ja'; ruby.append(node('rt', word.reading));
        heading.append(ruby); card.append(heading, node('p', word.gloss), audio(word.reading, '▶ Word'), saveButton(word));
        if (!word.sentences.length) card.append(node('p', 'No confident example available for this word.', 'muted'));
        for (const sentence of word.sentences) {
          const example = node('div', undefined, 'example');
          const jp = node('p', sentence.jp, 'japanese'); jp.lang = 'ja';
          const source = node('a', 'Tatoeba · automatic match');
          source.href = `https://tatoeba.org/en/sentences/show/${sentence.id}`;
          source.target = '_blank'; source.rel = 'noopener noreferrer';
          example.append(jp, node('p', sentence.en), audio(sentence.jp, '▶ Sentence'), source);
          card.append(example);
        }
        block.append(card);
      }
      section.append(block);
    }
    if (!entry.groups.length) section.append(node('p', 'No common vocabulary available.'));
    $('results').append(section);
  }
}
$('search').onsubmit = async event => {
  event.preventDefault();
  request?.abort(); request = new AbortController();
  const signal = request.signal;
  showView('explore');
  if (synth) synth.cancel();
  $('status').textContent = 'Looking up vocabulary…'; $('results').replaceChildren();
  try {
    const response = await fetch(`/api/lookup?q=${encodeURIComponent($('query').value)}`, {signal});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Lookup failed.');
    render(data.entries);
    $('status').textContent = data.entries.length ? 'Examples are tokenizer matches; their meaning has not been reviewed.' : 'No matching kanji found. Try 犬, 生, or 行.';
    if (data.entries.length) $('results').scrollIntoView({behavior: 'smooth', block: 'start'});
  } catch (error) { if (error.name !== 'AbortError') $('status').textContent = error.message; }
};
$('stop').onclick = () => synth?.cancel();
if (synth) synth.addEventListener('voiceschanged', loadVoices);
loadVoices();

function showView(view) {
  for (const name of ['explore', 'saved', 'review']) {
    $(`${name}-view`).hidden = name !== view;
    $(`${name}-tab`).setAttribute('aria-pressed', String(name === view));
  }
  $('results').hidden = view !== 'explore'; $('status').hidden = view !== 'explore';
  if (synth) synth.cancel();
  document.querySelectorAll('.save-word').forEach(button => {
    const exists = saved.has(button.dataset.key);
    button.textContent = exists ? '✓ Saved' : '＋ Save word';
    button.setAttribute('aria-pressed', String(exists));
  });
}
function showSaved() {
  showView('saved'); $('saved-list').replaceChildren();
  if (!saved.size) $('saved-list').append(node('p', 'Save a word from an Explore result to start your collection.'));
  for (const word of saved.values()) {
    const card = node('article');
    card.append(node('h3', `${word.word}【${word.reading}】`), node('p', word.gloss), audio(word.reading, '▶ Word'));
    const explore = node('button', 'Explore its kanji'); explore.type = 'button';
    explore.onclick = () => { $('query').value = word.word; $('search').requestSubmit(); };
    card.append(explore);
    const remove = node('button', 'Remove'); remove.type = 'button';
    remove.onclick = () => {
      const next = new Map(saved); next.delete(Study.key(word));
      if (persist(next)) showSaved();
    };
    const due = word.due <= Date.now() ? 'Ready for review' : `Next review: ${new Date(word.due).toLocaleString()}`;
    card.append(remove, node('p', due, 'muted')); $('saved-list').append(card);
  }
}
function reviewCard() {
  const container = $('review-card'); container.replaceChildren();
  $('review-progress').textContent = `${reviewed} reviewed · ${reviewQueue.length} remaining`;
  if (!reviewQueue.length) {
    container.append(node('p', saved.size ? 'You have finished the words currently due. Come back later for more practice.' : 'Save some vocabulary first, then come here to practice.'));
    return;
  }
  const word = saved.get(reviewQueue[0]);
  if (!word) { reviewQueue.shift(); reviewCard(); return; }
  const card = node('article'); card.append(node('h3', word.word), node('p', 'Can you recall the reading and meaning?'));
  const reveal = node('button', 'Show answer'); reveal.type = 'button';
  reveal.onclick = () => {
    reveal.remove(); card.append(node('p', `${word.reading} · ${word.gloss}`, 'japanese'), audio(word.reading, '▶ Word'));
    for (const sentence of word.sentences) card.append(node('p', sentence.jp), node('p', sentence.en), audio(sentence.jp, '▶ Sentence'));
    for (const [label, remembered] of [['Practice again · 10 min', false], ['Remembered · longer interval', true]]) {
      const button = node('button', label); button.type = 'button';
      button.onclick = () => {
        const next = new Map(saved); next.set(Study.key(word), Study.grade(word, remembered));
        if (persist(next)) { reviewed++; reviewQueue.shift(); reviewCard(); }
        else $('review-progress').textContent = 'Progress could not be saved. Check browser storage access.';
      };
      card.append(button);
    }
  };
  card.append(reveal); container.append(card);
}
$('explore-tab').onclick = () => showView('explore');
$('saved-tab').onclick = showSaved;
$('review-tab').onclick = () => {
  showView('review'); reviewed = 0;
  reviewQueue = [...saved.values()].filter(w => w.due <= Date.now()).sort((a, b) => a.due - b.due).map(Study.key);
  reviewCard();
};
$('export-saved').onclick = () => {
  const blob = new Blob([JSON.stringify({version: 1, words: [...saved.values()]}, null, 2)], {type: 'application/json'});
  const url = URL.createObjectURL(blob), link = node('a');
  link.href = url; link.download = 'kanji-lens-vocabulary.json'; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
$('import-saved').onchange = async event => {
  const file = event.target.files[0]; event.target.value = ''; if (!file) return;
  try {
    if (file.size > 10 * 1024 * 1024) throw new Error('Choose a backup smaller than 10 MB.');
    const words = Study.parse(await file.text()), next = new Map(saved);
    for (const word of words) if (!next.has(Study.key(word))) next.set(Study.key(word), word);
    if (next.size > 5000) throw new Error('A collection can contain up to 5,000 words.');
    if (persist(next)) { showSaved(); $('storage-status').textContent = 'Backup imported. Existing words and progress were kept.'; }
  } catch (error) { $('storage-status').textContent = error.message || 'Could not import this backup.'; }
};
try {
  const raw = localStorage.getItem(storageKey);
  if (raw) saved = new Map(Study.parse(raw).map(w => [Study.key(w), w]));
  $('saved-count').textContent = saved.size;
} catch {
  storageReady = false; $('storage-status').textContent = 'Saved words could not be loaded. Existing browser data has been left untouched.';
  $('status').textContent = 'Browser storage is unavailable or unreadable; saved words cannot be changed.';
}
