// The signed-in student's own dashboard: latest and past assessments, their own released scanned paper,
// teacher-approved feedback (a concept to revisit), assigned practice and progress by topic. All from their records.
import { useEffect, useState } from 'react';
import { api, getServer, mediaUrl, store } from './api.js';
import Icon from './Icon.jsx';
import PaperSurface from './PaperSurface.jsx';
import { VideoLink } from './TeacherAreas.jsx';
import { MyClasses, ProfilePanel } from './Accounts.jsx';
import StudentExams from './StudentExams.jsx';
import StudyTools from './StudyTools.jsx';

const pct = (s) => s?.total ? Math.round(s.correct / s.total * 100) : null;

export default function StudentHome({ token, studentId, onExpired }) {
  const [results, setResults] = useState(null);
  const [practice, setPractice] = useState([]);
  const [error, setError] = useState('');
  async function load() {
    if (!navigator.onLine) { setError('Connect to load your results, practice, and profile.'); return; }
    setError('');
    try {
      const [r, p] = await Promise.all([api.studentResults(token), api.studentPractice(token)]);
      setResults(r); setPractice(p);
    } catch (e) { if (e.status === 401) onExpired(); else setError(e.message); }
  }
  useEffect(() => {
    load();
    window.addEventListener('online', load);
    return () => window.removeEventListener('online', load);
  }, [token]);

  const all = results?.assessments || [];
  const released = all.filter(a => a.status !== 'awaiting_review');
  const waiting = all.filter(a => a.status === 'awaiting_review');
  const latest = released[0];
  const feedback = released.flatMap(a => (a.feedback || []).map(f => ({ ...f, title: a.title, key: `${a.assessment_id}-${f.question_id}` })));
  const byTopic = {};
  for (const a of [...released].reverse()) if (a.score?.total) (byTopic[a.topic] ||= []).push({ title: a.title, pct: pct(a.score) });

  return <>
    <header className="student-home-heading">
      <p className="landing-kicker">Your learning journey</p>
      <h1><span className="marker-text">{results ? `Hello, ${results.student.display_name}!` : 'Your learning'}</span></h1>
      <p>Every answer tells you something new. Here is what your teacher has shared with you.</p>
    </header>
    {results && <nav className="student-section-links" aria-label="Your dashboard">
      <a href="#exams">Exams</a><a href="#study-tools">Study tools</a><a href="#latest">Latest assessment</a><a href="#revisit">Concept to revisit</a><a href="#practice">Practice</a><a href="#progress">Progress</a><a href="#past">Past assessments</a><a href="#classes">My classes</a><a href="#profile">Profile</a>
    </nav>}
    <StudentExams token={token} scope={studentId ? JSON.stringify([getServer() || import.meta.env.VITE_API_URL || '/api', studentId]) : ''}
      onExpired={onExpired} />
    <StudyTools />
    {error && <section className="panel student-result-card" role="alert"><p>{error}</p><button className="button outline" onClick={load}>Try again</button></section>}
    {!results && !error && <p className="list-empty" role="status">Loading your work…</p>}
    {results && <div className="student-home-grid">
      <div className="student-home-results">
        <h2 id="latest">Latest assessment{latest ? `: ${latest.title}` : ''}</h2>
        {latest ? <AssessmentCard a={latest} token={token} open /> : <section className="panel student-result-card"><p>{waiting.length ? 'Your teacher is still checking your latest paper. Your results will appear here once they’re confirmed.' : 'Your results will appear here after your teacher shares them.'}</p></section>}
        {waiting.length > 0 && latest && <p className="awaiting-note"><Icon name="clock" size={15} /> {waiting.map(w => w.title).join(', ')}: awaiting teacher review.</p>}
        <h2 id="past">Past assessments</h2>
        {released.length > 1 ? released.slice(1).map(a => <AssessmentCard key={a.assessment_id} a={a} token={token} />) : <section className="panel student-result-card"><p>Older assessments will be listed here.</p></section>}
      </div>
      <div className="student-home-help">
        <h2 id="revisit">Concept to revisit</h2>
        {feedback.length ? <PaperSurface className="panel student-result-card">{feedback.map(f => <div className="student-answer revisit" key={f.key}>
          <b>{f.concept || 'From your teacher'}</b><small>{f.title}</small><p>{f.text}</p><VideoLink url={f.video_url} title={f.concept} /></div>)}</PaperSurface>
          : <section className="panel student-result-card"><p>When your teacher reviews your answers, their notes about what to try next will show up here.</p></section>}
        <h2 id="practice">Practice from your teacher</h2>
        {practice.length ? practice.map(p => <PracticeCard key={p.assignment_id} item={p} token={token} onDone={x => setPractice(list => list.map(y => y.assignment_id === x.assignment_id ? x : y))} onExpired={onExpired} />)
          : <section className="panel student-result-card"><p>No practice assigned right now.</p></section>}
        <h2 id="progress">Progress by topic</h2>
        <section className="panel student-result-card">{Object.keys(byTopic).length && released.length >= 2 ? <ul className="topic-progress">{Object.entries(byTopic).map(([topic, runs]) => <li key={topic}>
          <b>{topic}</b>{runs.map((r, i) => <span key={i} title={r.title}><i style={{ width: `${r.pct}%` }} />{r.pct}%</span>)}</li>)}</ul>
          : <p>Once you have done two or more checked assessments, you’ll see how each topic is going here. One quiz is just a snapshot, not a label.</p>}</section>
        <h2 id="classes">My classes</h2>
        <MyClasses token={token} onJoined={load} />
        <h2 id="profile">Profile</h2>
        <ProfilePanel token={token} />
      </div>
    </div>}
  </>;
}

function AssessmentCard({ a, token, open = false }) {
  const [imgFailed, setImgFailed] = useState(false);
  return <PaperSurface className="panel student-result-card">
    <h3><span className="hover-marker">{a.title}</span></h3>
    <p className="student-score">{a.score?.max_score ? <><b>{a.score.score} of {a.score.max_score}</b> marks{a.score.to_mark ? ` · ${a.score.to_mark} answer${a.score.to_mark === 1 ? '' : 's'} still being marked` : ''}</> : a.score?.total ? <><b>{a.score.correct} of {a.score.total}</b> multiple-choice answers correct</> : 'Checked by your teacher'} · {a.topic}</p>
    <details open={open}><summary>Your answers</summary>
      {a.answers.map(answer => <div className="student-answer" key={answer.question_id}>
        <b>{answer.stem}</b>
        {(answer.written ?? answer.type === 'descriptive') ? <p>You wrote: “{answer.text || '…'}”</p>
          : <p>Your answer <strong>{answer.chosen === 'blank' || !answer.chosen ? 'Blank' : `${answer.chosen}. ${answer.options?.[answer.chosen] || ''}`}</strong>
            {answer.correct && answer.chosen !== answer.correct && <span>Correct answer {answer.correct}. {answer.options?.[answer.correct]}</span>}</p>}
        {answer.chosen !== answer.correct && !(answer.written ?? answer.type === 'descriptive') && answer.explanation && <small>{answer.explanation}</small>}
        {answer.max_score != null && <small className="answer-mark">{answer.score == null ? 'Still being marked' : `${answer.score} / ${answer.max_score} mark${answer.max_score === 1 ? '' : 's'}`}</small>}
      </div>)}
    </details>
    {a.scan_url && <details><summary>Your scanned paper</summary>{imgFailed ? <p>The photo couldn’t load. Check your connection.</p>
      : <img className="student-scan" src={mediaUrl(a.scan_url, token)} alt={`Your scanned paper for ${a.title}`} loading="lazy" onError={() => setImgFailed(true)} />}</details>}
  </PaperSurface>;
}

function PracticeCard({ item, token, onDone, onExpired }) {
  const key = `mt_practice:${item.assignment_id}`; // unsent answers survive a reload or a dropped connection
  const [answers, setAnswers] = useState(() => { try { return JSON.parse(store.get(key) || '{}'); } catch { return {}; } });
  const [state, setState] = useState(''); const [error, setError] = useState('');
  useEffect(() => { store.set(key, Object.keys(answers).length && item.status !== 'submitted' ? JSON.stringify(answers) : ''); }, [answers]);
  async function submit() {
    setState('sending'); setError('');
    try {
      const r = await api.submitPractice(token, item.assignment_id, { answers: item.questions.map(q => ({ question_id: q.id, ...((q.written ?? q.type === 'descriptive') ? { text: answers[q.id] || '' } : { choice: answers[q.id] || null }) })) });
      store.set(key, ''); onDone(r);
    } catch (e) { if (e.status === 401) onExpired(); else setError(e.offline ? 'You’re offline. Your answers are kept on this device; submit again when you’re back online.' : e.message); }
    finally { setState(''); }
  }
  if (item.status === 'submitted') return <PaperSurface className="panel student-result-card"><h3>{item.title}</h3><p className="student-score"><Icon name="check" size={15} /> Submitted</p>
    {item.result.map((r, i) => { const q = item.questions[i]; return <div className="student-answer" key={r.question_id}><b>{q.stem}</b>
      {(q.written ?? q.type === 'descriptive') ? <p>You wrote: “{r.text || '…'}”</p> : <p>Your answer <strong>{r.chosen || 'Blank'}</strong>{r.correct && r.chosen !== r.correct && <span>Correct answer {r.correct}</span>}</p>}
      {r.chosen !== r.correct && r.explanation && <small>{r.explanation}</small>}
      {r.max_score != null && <small className="answer-mark">{r.score == null ? 'Your teacher marks this one' : `${r.score} / ${r.max_score}`}</small>}</div>; })}</PaperSurface>;
  const ready = item.questions.every(q => answers[q.id]);
  return <PaperSurface className="panel student-result-card"><h3>{item.title}</h3><p className="student-score">Not started · {item.questions.length} question{item.questions.length === 1 ? '' : 's'}</p>
    {item.questions.map((q, i) => <fieldset className="practice-question" key={q.id}><legend>{i + 1}. {q.stem}</legend>
      {q.image_url && <img className="practice-picture" src={mediaUrl(q.image_url, token)} alt={`Picture for question ${i + 1}`} />}{q.code && <pre className="practice-code">{q.code}</pre>}{q.hint?.map(h => <small className="practice-hint" key={h}>{h}</small>)}
      {(q.written ?? q.type === 'descriptive') ? <textarea rows="3" value={answers[q.id] || ''} onChange={e => setAnswers({ ...answers, [q.id]: e.target.value })} aria-label={`Your answer to question ${i + 1}`} />
        : Object.entries(q.options || {}).map(([k, v]) => <label key={k} className="practice-option"><input type="radio" name={q.id} checked={answers[q.id] === k} onChange={() => setAnswers({ ...answers, [q.id]: k })} /> {k}. {v}</label>)}</fieldset>)}
    {error && <p className="field-error" role="alert">{error}</p>}
    <button className="button primary" disabled={!ready || state === 'sending'} onClick={submit}>{state === 'sending' ? 'Submitting…' : 'Submit once'}</button>
  </PaperSurface>;
}
