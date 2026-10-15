/* Pure study logic, also executable by the Node regression tests. */
(function (root) {
  const key = word => JSON.stringify([word.word, word.reading]);
  function clean(item) {
    if (!item || typeof item.word !== 'string' || !item.word.length || item.word.length > 100 ||
        typeof item.reading !== 'string' || !item.reading.length || item.reading.length > 200 ||
        typeof item.gloss !== 'string' || item.gloss.length > 4000) throw new Error('Invalid vocabulary backup.');
    return {word: item.word, reading: item.reading, gloss: item.gloss,
      sentences: Array.isArray(item.sentences) ? item.sentences.slice(0, 2).filter(s =>
        s && Number.isSafeInteger(s.id) && s.id > 0 && typeof s.jp === 'string' && s.jp.length <= 1000 &&
        typeof s.en === 'string' && s.en.length <= 2000).map(s => ({id: s.id, jp: s.jp, en: s.en})) : [],
      due: Number.isFinite(item.due) && item.due >= 0 && item.due <= 8640000000000000 ? item.due : 0,
      interval: Number.isFinite(item.interval) && item.interval >= 0 ? Math.min(item.interval, 365) : 0};
  }
  function parse(text) {
    let data;
    try { data = JSON.parse(text); } catch { throw new Error('This file is not a valid Kanji Lens backup.'); }
    if (!data || data.version !== 1 || !Array.isArray(data.words) || data.words.length > 5000) throw new Error('Unsupported vocabulary backup.');
    return [...new Map(data.words.map(clean).map(w => [key(w), w])).values()];
  }
  function grade(word, remembered, now = Date.now()) {
    const interval = remembered ? Math.min(365, Math.max(1, word.interval * 2)) : 0;
    return {...word, interval, due: now + (remembered ? interval * 86400000 : 600000)};
  }
  function kanji(text) { return [...new Set(Array.from(text).filter(c => /[\u3400-\u4dbf\u4e00-\u9fff]/u.test(c)))]; }
  const api = {key, clean, parse, grade, kanji};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.Study = api;
})(typeof window === 'undefined' ? globalThis : window);
