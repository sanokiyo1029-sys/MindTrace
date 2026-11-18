import { useEffect, useMemo, useRef, useState } from 'react';
import { api, isNative, mediaUrl } from './api.js';
import { Button, Panel } from './ui.jsx';
import { answerText, examDetails, examError, scoreText, statusLabel } from './Exams.jsx';
import { deviceDeadline, offlinePapers, writePaper } from './offlineExams.js';

export default function StudentExams({ token, scope, onExpired }) {
  const [exams, setExams] = useState(null);
  const [stored, setStored] = useState(null);
  const [online, setOnline] = useState(navigator.onLine);
  const [shell, setShell] = useState(isNative ? 'ready' : 'preparing');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function load() {
    if (!navigator.onLine) return;
    setLoading(true); setError('');
    try { setExams(await api.studentExams(token)); }
    catch (e) { if (e.status === 401) onExpired(); else setError(examError(e)); }
    finally { setLoading(false); }
  }

  useEffect(() => {
    let active = true;
    if (scope) offlinePapers(scope).then(rows => { if (active) setStored(rows); }, () => { if (active) setStored([]); });
    else setStored([]);
    return () => { active = false; };
  }, [scope]);

  useEffect(() => {
    const connected = () => { setOnline(true); load(); };
    const disconnected = () => setOnline(false);
    load();
    window.addEventListener('online', connected);
    window.addEventListener('offline', disconnected);
    return () => {
      window.removeEventListener('online', connected);
      window.removeEventListener('offline', disconnected);
    };
  }, [token]);

  useEffect(() => {
    if (isNative) return;
    if (!import.meta.env.PROD || !navigator.serviceWorker) { setShell('unavailable'); return; }
    const service = navigator.serviceWorker;
    let active = true;
    let detach = () => {};
    function watch(registration) {
      if (!active) return;
      detach();
      const worker = registration?.active || registration?.installing || registration?.waiting;
      if (!worker) { setShell('unavailable'); return; }
      const check = () => {
        // A document opened at /login isn't controlled after client-side navigation.
        // An activated registration is enough to reopen /student on the next navigation.
        if (active && (worker.state === 'activated' || worker.state === 'redundant')) {
          setShell(worker.state === 'activated' ? 'ready' : 'unavailable');
        }
      };
      worker.addEventListener('statechange', check);
      detach = () => worker.removeEventListener('statechange', check);
      check();
    }
    const unavailable = () => { if (active) setShell('unavailable'); };
    const register = () => service.register('/exam-sw.js', { scope: '/student' }).then(watch, unavailable);
    if (navigator.onLine) register(); else service.getRegistration('/student').then(watch, unavailable);
    window.addEventListener('online', register);
    return () => {
      active = false;
      detach();
      window.removeEventListener('online', register);
    };
  }, []);

  const local = new Map((stored || []).map(row => [row.id, row]));
  const catalog = new Map((exams || []).map(exam => [exam.id, exam]));
  for (const row of local.values()) if (!catalog.has(row.id)) catalog.set(row.id, { ...row.paper, status: row.ended ? 'submitted' : 'in_progress' });
  function updated(id, record) {
    setStored(rows => {
      const other = (rows || []).filter(row => row.id !== id);
      return record ? [...other, record] : other;
    });
  }

  return <section aria-labelledby="exams" className="student-exams">
    <div className="exam-row"><h2 id="exams">Online exams</h2><Button variant="outline" disabled={loading || !online} onClick={load}>Refresh exams</Button></div>
    {!online && <p role="status">Offline. You can reopen exams downloaded on this device.</p>}
    {error && online && <p role="alert" className="field-error">{error}</p>}
    {(loading && !exams || stored === null) && <p role="status">Loading exams…</p>}
    {!catalog.size && stored !== null && !loading && <Panel className="exam-panel"><p>{online ? 'No online exams assigned.' : 'No exams downloaded on this device.'}</p></Panel>}
    {stored !== null && Array.from(catalog.values(), exam =>
      <ExamCard key={scope + exam.id} {...{ exam, token, scope, online, shell, onExpired }} cached={local.get(exam.id)} onCache={record => updated(exam.id, record)} />)}
  </section>;
}

function ExamCard({ exam, cached, scope, token, online, shell, onCache, onExpired }) {
  const [remote, setRemote] = useState(null);
  const [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const paper = remote || cached?.paper;
  const active = !cached?.ended && paper?.attempt.status === 'in_progress';
  const status = active ? 'in_progress' : exam.status === 'released' ? 'released' : cached?.ended ? 'submitted' : remote?.attempt.status || exam.status;

  async function open() {
    if (active) { setVisible(true); return; }
    setBusy(true); setError('');
    try { setRemote(await (status === 'ready' ? api.startExam(token, exam.id) : api.studentExam(token, exam.id))); setVisible(true); }
    catch (e) { if (e.status === 401) onExpired(); else setError(examError(e)); }
    finally { setBusy(false); }
  }

  return <Panel className="exam-panel student-exam">
    <div className="exam-row"><div><h3>{exam.title}</h3><p>{examDetails(exam)}</p></div><span className="status-pill status-draft">{statusLabel[status]}</span></div>
    {status === 'ready' && <p>The timer starts when you select Start exam. Download the paper after starting if you may lose your connection.</p>}
    {error && <p role="alert" className="field-error">{error}</p>}
    {cached?.ended && <details className="exam-marking">
      <summary>View answers that stayed on this device</summary>
      <p>{cached.ended === 'deadline' ? 'The deadline passed before the server received these changes.' : 'This attempt closed before the server received these changes.'}</p>
      {cached.paper.questions.map((q, i) => <div className="student-answer" key={q.id}>
        <b>{i + 1}. {q.stem}</b><p className="exam-response">{answerText(q, cached.answers[q.id])}</p>
      </div>)}
    </details>}
    {remote?.attempt.status === 'released' && <ExamResult paper={remote} />}
    {active && <ExamPlayer key={paper.attempt.id} {...{ paper, cached, scope, token, online, shell, visible, onCache, onExpired }}
      onUpdated={setRemote} />}
    {!(active && visible) && remote?.attempt.status !== 'released' &&
      (status === 'submitted' ? <p>Your teacher will release the result after reviewing your submission.</p>
        : <Button onClick={open} disabled={busy || (!online && !active)}>
          {busy ? 'Opening exam…' : { ready: 'Start exam', in_progress: 'Resume exam', released: 'View result' }[status]}</Button>)}
  </Panel>;
}

function ExamResult({ paper }) {
  const { attempt, questions } = paper;
  return <><p className="student-score">{scoreText(attempt.score, attempt.max_score)}</p>
    <details><summary>Your answers and marks</summary>{questions.map((q, i) => <div className="student-answer" key={q.id}>
      <b>{i + 1}. {q.stem}</b><p className="exam-response">{answerText(q, attempt.answers[q.id])}</p>
      <small>{scoreText(attempt.scores[q.id], q.marks)}</small>
    </div>)}</details></>;
}

const queuedWrite = submit => ({ id: crypto.randomUUID(), submit });

function ExamPlayer({ paper, cached, scope, token, online, shell, visible, onCache, onUpdated, onExpired }) {
  const { attempt } = paper;
  const [answers, setAnswers] = useState(cached?.answers || attempt.answers);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState('');
  const [error, setError] = useState('');
  const [conflict, setConflict] = useState(null);
  const [deviceConflict, setDeviceConflict] = useState(null);
  const [networkError, setNetworkError] = useState(false);
  const record = useRef(cached);
  const latest = useRef(answers);
  const edits = useRef(0);
  const sending = useRef(false);
  const closed = useRef(false);
  const writes = useRef(Promise.resolve());
  const deadline = useMemo(() => cached?.expiresAt || deviceDeadline(attempt), [cached?.expiresAt, attempt.deadline_at, attempt.server_time]);
  const [milliseconds, setMilliseconds] = useState(() => deadline - Date.now());
  const expired = milliseconds <= 0;
  const seconds = Math.max(0, Math.ceil(milliseconds / 1000));
  const pending = cached?.pending;

  useEffect(() => {
    const end = performance.now() + deadline - Date.now();
    const tick = () => setMilliseconds(end - performance.now());
    tick();
    const id = setInterval(tick, 250);
    return () => clearInterval(id);
  }, [deadline]);
  useEffect(() => { if (online && networkError) { setError(''); setNetworkError(false); } }, [online]);

  function replaceAnswers(next) { latest.current = next; setAnswers(next); }

  function persist(update) {
    const job = writes.current.then(async () => {
      const before = record.current;
      const result = await writePaper(scope, paper.id, before?.revision || 0, update(before));
      if (result.conflict) {
        setDeviceConflict(result.current || {});
        throw new Error('The download changed in another tab. Load the device copy before editing again.');
      }
      record.current = result.current;
      onCache(result.current);
      return result.current;
    });
    writes.current = job.catch(() => {});
    return job;
  }

  function change(id, value) {
    if (closed.current) return;
    const revision = ++edits.current;
    const next = { ...latest.current, [id]: value };
    replaceAnswers(next); setDirty(true);
    if (record.current) {
      persist(row => ({ ...row, answers: next, pending: queuedWrite(false) }))
        .then(() => { if (revision === edits.current) setDirty(false); })
        .catch(e => setError(e.message || 'Couldn’t save to this device. Keep this page open.'));
    }
  }

  async function download() {
    if (sending.current) return;
    sending.current = true; setSaving('download'); setError('');
    try {
      const pictures = paper.questions.filter(q => q.image_url);
      const images = Object.fromEntries(await Promise.all(pictures.map(async q => {
        const blob = await api.examImage(token, q.image_url);
        if (!blob.type.startsWith('image/')) throw new Error('A question image did not download.');
        return [q.id, blob];
      })));
      const revision = edits.current;
      const draft = latest.current;
      await persist(() => ({ paper, images, answers: draft, expiresAt: deadline,
        pending: JSON.stringify(draft) === JSON.stringify(attempt.answers) ? null : queuedWrite(false) }));
      if (revision === edits.current) setDirty(false);
    } catch (e) { if (e.status === 401) onExpired(); else setError(e.offline ? 'Reconnect to finish downloading the exam.' : examError(e)); }
    finally { sending.current = false; setSaving(''); }
  }

  async function sync(action) {
    if (sending.current) return;
    sending.current = true; setSaving(action); setError(''); setNetworkError(false);
    const revision = edits.current;
    try {
      let saved = await writes.current.then(() => record.current);
      if (saved && (action === 'submit' || action === 'save' && dirty)) {
        const draft = latest.current;
        saved = await persist(row => ({ ...row, answers: draft, pending: queuedWrite(action === 'submit') }));
        if (revision === edits.current) setDirty(false);
      }
      if (!online) return;
      const operation = saved?.pending;
      const next = operation ? await api.saveExam(token, paper.id, {
        version: saved.paper.attempt.version, answers: saved.answers, submit: operation.submit, write_id: operation.id,
      }) : action === 'check' || saved ? await api.studentExam(token, paper.id)
        : await api.saveExam(token, paper.id, { version: attempt.version, answers: latest.current, submit: action === 'submit' });
      let device;
      const terminal = next.attempt.status !== 'in_progress';
      if (terminal) { closed.current = true; setMilliseconds(0); }
      if (saved) {
        const acked = !operation || operation.id === next.attempt.last_write_id;
        if (!acked && !terminal) throw new Error('The server did not confirm this save. Try syncing again.');
        device = await persist(row => {
          const newer = row.pending?.id !== operation?.id;
          if (terminal) return row.pending && (!acked || newer)
            ? { ...row, pending: null, ended: next.attempt.submission_reason || 'student' } : null;
          return { ...row, paper: next, expiresAt: deviceDeadline(next.attempt),
            answers: newer ? row.answers : next.attempt.answers, pending: newer ? row.pending : null };
        });
      }
      onUpdated(next);
      if (revision === edits.current && next.attempt.status === 'in_progress') {
        replaceAnswers(device?.answers || next.attempt.answers);
        setDirty(false);
      }
    } catch (e) {
      if (e.status === 401) onExpired();
      else {
        if (e.code === 'conflict' && e.current) setConflict(e.current);
        setNetworkError(!!e.offline);
        setError(e.offline ? (record.current ? 'The server is unreachable. Changes stay on this device until you sync.' :
          'The server is unreachable. Keep this page open and retry before the deadline.') : examError(e));
      }
    } finally { sending.current = false; setSaving(''); }
  }

  async function useServerCopy() {
    try {
      if (record.current) await persist(row => ({ ...row, paper: conflict, answers: conflict.attempt.answers,
        expiresAt: deviceDeadline(conflict.attempt), pending: null }));
      replaceAnswers(conflict.attempt.answers); onUpdated(conflict); setDirty(false); setConflict(null); setError('');
    } catch (e) { setError(e.message); }
  }

  function reloadDevice() {
    if (!deviceConflict.revision) { window.location.reload(); return; }
    record.current = deviceConflict;
    onCache(deviceConflict); onUpdated(deviceConflict.paper); replaceAnswers(deviceConflict.answers);
    setDirty(false); setDeviceConflict(null); setError('');
  }

  useEffect(() => {
    if (!online || saving || error || conflict || deviceConflict) return;
    if (!pending && !dirty && !expired) return;
    const action = expired ? pending ? 'sync' : 'check' : dirty ? 'save' : 'sync';
    const id = setTimeout(() => sync(action), expired || pending?.submit ? 0 : 650);
    return () => clearTimeout(id);
  }, [pending, dirty, answers, expired, saving, error, online, conflict, deviceConflict]);

  if (!visible) return error ? <p role="status">Resume the exam to check its sync status.</p>
    : pending?.submit ? <p role="status">Submission queued on this device</p> : null;
  const timer = Math.floor(seconds / 60) + ':' + String(seconds % 60).padStart(2, '0');
  return <>
    <div className="exam-row exam-timer"><b aria-label="Time remaining">{timer} remaining</b>
      <small role="status">{saving === 'download' ? 'Downloading exam…' : saving ? 'Saving…' : pending?.submit ? 'Submission queued on this device' :
        dirty ? 'Changes pending' : pending ? 'Saved on this device · waiting to sync' : expired ? 'Time is up' : 'Answers saved'}</small></div>
    {cached ? <p>Downloaded to this device. Reopen the student page to resume.</p> : scope && <Button variant="outline"
      onClick={download} disabled={!online || shell !== 'ready' || !!saving || expired}>{shell === 'preparing' ? 'Preparing offline access…' : 'Download for offline use'}</Button>}
    {!cached && shell === 'unavailable' && <p>Offline reopening is unavailable in this browser or build.</p>}
    <fieldset className="exam-player" disabled={expired || closed.current || saving === 'submit' || !!pending?.submit || !!conflict || !!deviceConflict}>
      <legend>Exam questions</legend>
      {paper.questions.map((q, index) => <fieldset className="practice-question" key={q.id}>
        <legend>{index + 1}. {q.stem} <small>({q.marks} marks)</small></legend>
        {q.image_url && <ExamPicture q={q} number={index + 1} blob={cached?.images[q.id]} token={token} />}
        {q.code && <pre className="practice-code">{q.code}</pre>}
        <ExamInput q={q} value={answers[q.id]} onChange={value => change(q.id, value)} />
      </fieldset>)}
    </fieldset>
    {error && <p role="alert" className="field-error">{error}</p>}
    <div className="exam-actions">
      {deviceConflict ? <Button variant="outline" onClick={reloadDevice}>Load the device copy</Button>
        : conflict ? <Button variant="outline" onClick={useServerCopy}>Load saved answers from server</Button>
        : expired || pending?.submit ? <Button variant="outline" onClick={() => sync(pending ? 'sync' : 'check')}
          disabled={!online || !!saving}>{pending ? 'Sync now' : 'Check submission'}</Button>
        : <><Button variant="outline" onClick={() => sync(dirty ? 'save' : 'sync')} disabled={!!saving || (!dirty && !pending) || (!online && !cached)}>Save now</Button>
          <Button onClick={() => sync('submit')} disabled={!!saving || (!online && !cached)}>{online ? 'Submit exam' : 'Queue submission'}</Button></>}
    </div>
    <small>The timer keeps running offline. Only changes received by the server before the deadline count toward the result.</small>
  </>;
}

function ExamPicture({ q, number, blob, token }) {
  const [preview, setPreview] = useState(null);
  useEffect(() => {
    if (!blob) { setPreview(null); return; }
    const url = URL.createObjectURL(blob);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [blob]);
  return <img className="practice-picture" src={preview || mediaUrl(q.image_url, token)} alt={'Diagram for question ' + number} />;
}

function ExamInput({ q, value, onChange }) {
  if (q.style === 'choice' || q.style === 'multi') {
    const multi = q.style === 'multi';
    const selected = multi ? value || [] : [];
    return <>
      {Object.entries(q.options).map(([key, label]) => <label key={key} className="practice-option">
        <input type={multi ? 'checkbox' : 'radio'} name={q.id} checked={multi ? selected.includes(key) : value === key}
          onChange={e => onChange(multi ? e.target.checked ? [...selected, key] : selected.filter(item => item !== key) : key)} /> {label}
      </label>)}
      {!multi && value && <button type="button" className="text-button" onClick={() => onChange('')}>Clear response</button>}
    </>;
  }
  if (q.style === 'blanks') return Array.from({ length: q.blank_count }, (_, i) => <label key={i} className="field">Blank {i + 1}
    <input maxLength={300} value={value?.[i] || ''} onChange={e => onChange(Array.from({ length: q.blank_count }, (_, j) => j === i ? e.target.value : value?.[j] || ''))} />
  </label>);
  if (q.style === 'match') return q.left.map((label, i) => <label key={i} className="field">{label}
    <select aria-label={label} value={value?.[i + 1] || ''} onChange={e => {
      const entries = { ...value };
      if (e.target.value) entries[i + 1] = e.target.value; else delete entries[i + 1];
      onChange(entries);
    }}><option value="">Choose a match</option>{Object.entries(q.right).map(([key, right]) => <option value={key} key={key}>{right}</option>)}</select>
  </label>);
  const label = q.unit ? `Your answer (${q.unit})` : 'Your answer';
  return <label className="field">{label}{q.style === 'manual'
    ? <textarea aria-label={label} rows="4" maxLength={5000} value={value || ''} onChange={e => onChange(e.target.value)} />
    : <input aria-label={label} maxLength={300} value={value || ''} onChange={e => onChange(e.target.value)} />}</label>;
}
