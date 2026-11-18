// Phase 2 question types (backend: app/marking.py). The teacher edits each type's answer key here; marking happens on
// the server. Plain multiple choice keeps its original editor in App.jsx.
import { useState } from 'react';
import { api, mediaUrl } from './api.js';
import Icon from './Icon.jsx';

export const TYPE_LABELS = {
  mcq: 'Multiple choice', multi_select: 'Multiple select', true_false: 'True / False', fill_blank: 'Fill in the blanks',
  match: 'Match the following', assertion_reason: 'Assertion and reason', one_word: 'One-word answer',
  short: 'Short answer', long: 'Long answer', essay: 'Essay', maths: 'Mathematical problem',
  numerical: 'Numerical problem', diagram: 'Diagram-based', image: 'Image-based', programming: 'Programming',
  code: 'Code-based', graph: 'Graph interpretation', descriptive: 'Written answer',
};
const FIXED = {
  true_false: { A: 'True', B: 'False' },
  assertion_reason: { A: 'Both true; R explains A', B: 'Both true; R doesn’t explain A', C: 'A true, R false', D: 'A false, R true' },
};
const FLEX = ['maths', 'diagram', 'image', 'code', 'graph'];
const HELP = {
  multi_select: 'Students tick every correct option. A wrong tick cancels a right one; never below zero.',
  fill_blank: 'Type ___ (three underscores) for each gap. Each blank earns its share of the marks.',
  match: 'Students see the right-hand items shuffled and lettered. Each correct pair earns its share.',
  assertion_reason: 'Write “Assertion: … Reason: …” as the question. The four standard choices are printed for you.',
  short: 'You mark this one (partial marks allowed).', long: 'You mark this one (partial marks allowed).',
  essay: 'You mark this one (partial marks allowed).',
  programming: 'You mark this one. MindTrace never runs student code.',
  diagram: 'Students draw in the answer box. Usually you mark it; add an answer key only for a short final answer.',
};

// Empty answer keys for a new question, so the editor shows the right rows straight away.
export const STARTERS = {
  multi_select: { options: { A: '', B: '', C: '', D: '' }, answers: [] }, fill_blank: { stem: '___', blanks: [['']] },
  match: { pairs: [['', ''], ['', ''], ['', '']] }, one_word: { accepted: [''] }, numerical: { value: '' }, short: { marks: 2 },
  long: { marks: 5 }, essay: { marks: 10 }, programming: { marks: 4 }, diagram: { marks: 3 },
};

const flexKind = (q) => q.options ? 'choice' : q.value != null ? 'number' : q.accepted ? 'words' : 'manual';

/** Bubbles on paper, or a written box: mirrors marking.paper_kind on the server. */
export function isWritten(q) {
  const t = q?.type || 'mcq';
  if (['mcq', 'true_false', 'assertion_reason'].includes(t)) return false;
  return !(FLEX.includes(t) && q.options);
}

export const optionsOf = (q) => FIXED[q?.type] || q?.options || {};

export function AddQuestion({ onAdd, adding }) {
  const [type, setType] = useState('short');
  return <span className="add-question-picker">
    <select aria-label="New question type" value={type} onChange={e => setType(e.target.value)}>
      {Object.entries(TYPE_LABELS).filter(([k]) => !['mcq', 'descriptive'].includes(k)).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
    </select>
    <button className="add-question" disabled={adding} onClick={() => onAdd(type)}><Icon name="plus" size={15} /> {adding ? 'Adding…' : 'Add'}</button>
  </span>;
}

const Bar = (list) => (list || []).join('|');
const unBar = (text) => text.split('|');

function Options({ q, update, multi }) {
  const opts = q.options || {};
  const keys = Object.keys(opts);
  const right = multi ? (q.answers || []) : [q.answer];
  const toggle = (k) => multi ? update({ answers: right.includes(k) ? right.filter(x => x !== k) : [...right, k].sort() }) : update({ answer: k });
  const resize = (n) => update({ options: Object.fromEntries('ABCD'.slice(0, n).split('').map(k => [k, opts[k] || ''])),
    ...(multi ? { answers: right.filter(k => 'ABCD'.slice(0, n).includes(k)) } : !'ABCD'.slice(0, n).includes(q.answer) && { answer: null }) });
  return <div className="option-editor"><div className="option-heading"><b>Options</b><span>{multi ? 'Tick every correct option' : 'Choose the correct answer'}</span></div>
    {keys.map(k => <div className={`option-row ${right.includes(k) ? 'correct-option' : ''}`} key={k}>
      <button type="button" aria-label={`Mark ${k} as correct`} aria-pressed={right.includes(k)} className={`answer-radio ${right.includes(k) ? 'checked' : ''}`} onClick={() => toggle(k)}>{right.includes(k) && <span />}</button>
      <span className="option-key">{k}</span>
      <input aria-label={`Option ${k}`} value={opts[k]} maxLength={60} onChange={e => update({ options: { ...opts, [k]: e.target.value } })} />
      {right.includes(k) && <span className="correct-label"><Icon name="check" size={14} /> Correct</span>}</div>)}
    <div className="type-row-actions">{keys.length < 4 && <button type="button" className="text-button" onClick={() => resize(keys.length + 1)}>+ Option</button>}
      {keys.length > 2 && <button type="button" className="text-button" onClick={() => resize(keys.length - 1)}>Remove last option</button>}</div>
  </div>;
}

function Fixed({ q, update }) {
  return <div className="option-editor"><div className="option-heading"><b>Answer</b><span>Choose the correct one</span></div>
    {Object.entries(FIXED[q.type]).map(([k, v]) => <div className={`option-row ${q.answer === k ? 'correct-option' : ''}`} key={k}>
      <button type="button" aria-label={`Mark ${k} as correct`} className={`answer-radio ${q.answer === k ? 'checked' : ''}`} onClick={() => update({ answer: k })}>{q.answer === k && <span />}</button>
      <span className="option-key">{k}</span><span className="fixed-option">{v}</span>
      {q.answer === k && <span className="correct-label"><Icon name="check" size={14} /> Correct</span>}</div>)}</div>;
}

function NumberKey({ q, update }) {
  return <div className="field-row type-fields">
    <label className="field">Correct answer<input value={q.value ?? ''} onChange={e => update({ value: e.target.value })} placeholder="e.g. 12.5 or 7/8" /></label>
    <label className="field">Allowed error (±)<input value={q.tolerance ?? ''} onChange={e => update({ tolerance: e.target.value })} placeholder="0" /><small>e.g. 0.1 accepts 12.4 to 12.6</small></label>
    <label className="field">Unit (optional)<input value={q.unit || ''} onChange={e => update({ unit: e.target.value })} placeholder="e.g. m/s" /></label>
  </div>;
}

function WordsKey({ q, update }) {
  return <label className="field type-fields">Accepted answers<input value={Bar(q.accepted)} onChange={e => update({ accepted: unBar(e.target.value) })} placeholder="mitochondria | mitochondrion" />
    <small>Separate alternatives with |. Capitals, spaces and a final full stop don’t matter.</small></label>;
}

function Picture({ q, onReplace, prepare, flash }) {
  const [busy, setBusy] = useState(false);
  async function run(fn) { setBusy(true); try { await prepare?.(); onReplace(await fn()); } catch (e) { flash(e.message); } finally { setBusy(false); } }
  return <div className="field type-fields picture-field"><span>Picture (optional)</span>
    {q.image_url && <img src={mediaUrl(q.image_url)} alt="Picture for this question" />}
    <span className="type-row-actions">
      <label className="button outline small-button">{busy ? 'Uploading…' : q.image_url ? 'Replace picture' : 'Add picture'}
        <input type="file" accept="image/png,image/jpeg" hidden disabled={busy} onChange={e => { const f = e.target.files[0]; e.target.value = ''; if (f) run(() => api.questionImage(q.id, f)); }} /></label>
      {q.image_url && <button type="button" className="text-button" disabled={busy} onClick={() => run(() => api.removeQuestionImage(q.id))}>Remove</button>}
    </span><small>Printed beside the question. Needs a connection.</small></div>;
}

/** Answer-key editor for every type except plain multiple choice and the original written answer. */
export function TypeFields({ q, update, onReplace, prepare, flash }) {
  const t = q.type;
  const kind = FLEX.includes(t) ? flexKind(q) : null;
  const setKind = (k) => update({ options: k === 'choice' ? { A: '', B: '' } : null, answer: null, value: k === 'number' ? '' : null,
    tolerance: null, accepted: k === 'words' ? [''] : null });
  const blanks = q.blanks || [];
  const gaps = (q.stem || '').split('___').length - 1;
  const pairs = q.pairs || [['', ''], ['', '']];
  return <div className="type-editor">
    {HELP[t] && <p className="written-note">{HELP[t]}</p>}
    <div className="field-row type-fields">
      <label className="field">Marks<input type="number" min="0.5" max="20" step="0.5" value={q.marks ?? 1} onChange={e => update({ marks: e.target.value === '' ? 1 : Number(e.target.value) })} /></label>
      <label className="field">Concept<input value={q.concept || ''} onChange={e => update({ concept: e.target.value })} placeholder="e.g. Newton’s second law" /></label>
    </div>
    {(t === 'code' || t === 'programming') && <label className="field type-fields">{t === 'code' ? 'Code students read' : 'Starter code (optional)'}<textarea className="code-input" rows="5" value={q.code || ''} onChange={e => update({ code: e.target.value })} spellCheck="false" /></label>}
    {kind && <label className="field type-fields">How is it marked?<select value={kind} onChange={e => setKind(e.target.value)}>
      <option value="manual">I mark it (working, drawing or explanation)</option><option value="choice">Students choose an option (bubbles)</option>
      <option value="number">A number, within an allowed error</option><option value="words">A word or short phrase</option></select></label>}
    {(t === 'multi_select' || kind === 'choice') && <Options q={q} update={update} multi={t === 'multi_select'} />}
    {FIXED[t] && <Fixed q={q} update={update} />}
    {(t === 'numerical' || kind === 'number') && <NumberKey q={q} update={update} />}
    {(t === 'one_word' || kind === 'words') && <WordsKey q={q} update={update} />}
    {t === 'fill_blank' && <div className="type-fields"><b className="type-sub">Answers for each blank</b>{gaps !== blanks.length && <small className="type-warn">The question has {gaps} gap{gaps === 1 ? '' : 's'} (___) and {blanks.length} answer{blanks.length === 1 ? '' : 's'}.</small>}
      {blanks.map((b, i) => <label className="field" key={i}>Blank {i + 1}<input value={Bar(b)} onChange={e => update({ blanks: blanks.map((x, j) => j === i ? unBar(e.target.value) : x) })} placeholder="answer | another accepted spelling" /></label>)}
      <span className="type-row-actions"><button type="button" className="text-button" onClick={() => update({ blanks: [...blanks, ['']] })}>+ Blank</button>{blanks.length > 1 && <button type="button" className="text-button" onClick={() => update({ blanks: blanks.slice(0, -1) })}>Remove last</button>}</span></div>}
    {t === 'match' && <div className="type-fields"><b className="type-sub">Pairs (left matches right)</b>
      {pairs.map((p, i) => <div className="field-row match-row" key={i}><input aria-label={`Left item ${i + 1}`} value={p[0]} onChange={e => update({ pairs: pairs.map((x, j) => j === i ? [e.target.value, x[1]] : x) })} placeholder={`Item ${i + 1}`} />
        <input aria-label={`Right item ${i + 1}`} value={p[1]} onChange={e => update({ pairs: pairs.map((x, j) => j === i ? [x[0], e.target.value] : x) })} placeholder="Its match" /></div>)}
      <span className="type-row-actions">{pairs.length < 6 && <button type="button" className="text-button" onClick={() => update({ pairs: [...pairs, ['', '']] })}>+ Pair</button>}{pairs.length > 2 && <button type="button" className="text-button" onClick={() => update({ pairs: pairs.slice(0, -1) })}>Remove last</button>}</span></div>}
    <Picture q={q} onReplace={onReplace} prepare={prepare} flash={flash} />
    <div className="question-explanation"><div className="explanation-title"><span className="explain-icon">i</span><b>Marking notes</b><small>Only you see this: what earns the marks.</small></div>
      <textarea aria-label="Marking notes" value={q.model_answer || ''} rows="3" onChange={e => update({ model_answer: e.target.value })} /></div>
  </div>;
}

/** Score shown on a scanned answer, with the teacher's own mark (partial credit) for written answers. */
export function MarkField({ answer, value, onChange }) {
  const auto = answer.scored_by === 'auto';
  return <label className="field mark-field">Mark (out of {answer.max_score ?? 1})
    <input type="number" min="0" max={answer.max_score ?? 1} step="0.25" value={value} onChange={e => onChange(e.target.value)}
      placeholder={answer.score != null && auto ? `Auto: ${answer.score}` : 'To mark'} />
    <small>{value !== '' ? 'Your mark.' : answer.score != null && auto ? `Auto-marked ${answer.score}. Type a mark to change it.` : 'Needs your mark.'}</small></label>;
}
