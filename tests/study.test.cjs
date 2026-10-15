const {test} = require('node:test');
const assert = require('node:assert/strict');
const Study = require('../static/study.js');
const word = {word: '生物', reading: 'せいぶつ', gloss: 'organism', sentences: [], due: 0, interval: 0};
test('different readings of one spelling are distinct saved words', () => {
  assert.notEqual(Study.key(word), Study.key({...word, reading: 'なまもの'}));
  const loaded = Study.parse(JSON.stringify({version: 1, words: [word, word, {...word, reading: 'なまもの'}]}));
  assert.equal(loaded.length, 2);
});
test('backup restores progress and only accepts supported, bounded data', () => {
  const reviewed = Study.grade(word, true, 1000);
  assert.deepEqual(Study.parse(JSON.stringify({version: 1, words: [reviewed]})), [reviewed]);
  assert.throws(() => Study.parse('invalid'));
  assert.throws(() => Study.parse(JSON.stringify({version: 3, words: []})));
  assert.throws(() => Study.parse(JSON.stringify({version: 1, words: [{word: 123}]})));
  assert.throws(() => Study.parse(JSON.stringify({version: 1, words: Array(5001).fill(word)})));
});
test('review schedules retry and increasing intervals without exceeding a year', () => {
  assert.equal(Study.grade(word, false, 1000).due, 601000);
  const first = Study.grade(word, true, 1000);
  assert.equal(first.due, 86401000);
  assert.equal(Study.grade(first, true, 1000).interval, 2);
  assert.equal(Study.grade({...word, interval: 300}, true, 0).interval, 365);
  assert.equal(Study.grade(first, false, 0).interval, 0);
});
test('OCR choices preserve order, skip kana and remove repeated kanji', () => {
  assert.deepEqual(Study.kanji('犬と生き物と犬'), ['犬', '生', '物']);
  assert.deepEqual(Study.kanji('かな ABC 123'), []);
});
