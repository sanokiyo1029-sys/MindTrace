import { useEffect, useState } from 'react';
import { api } from './api.js';
import { Button, PageHeading, Panel } from './ui.jsx';

export const statusLabel = { ready: 'Ready to start', in_progress: 'In progress', submitted: 'Submitted', released: 'Results released' };
export const examDetails = exam => `${exam.class_name} · ${exam.duration_minutes} min · ${exam.question_count} questions`;
export const examError = e => e.offline ? 'The server is unreachable. Check your connection and try again.' : e.message;
export const scoreText = (score, max) => `${score} / ${max} marks`;

export function answerText(q, value) {
  if (!value) return 'Blank';
  if (q.style === 'match') return Object.entries(value).map(([i, letter]) => `${q.left[Number(i) - 1]} → ${q.right[letter]}`).join('\n');
  if (Array.isArray(value)) return value.map((v, i) => q.style === 'blanks' ? `${i + 1}. ${v || 'Blank'}` : q.options[v]).join('\n');
  return q.options?.[value] ?? value;
}

export function TeacherExams({ isMock, flash, classes }) {
  const [catalog, setCatalog] = useState(null);
  const [report, setReport] = useState(null);
  const [source, setSource] = useState('');
  const [duration, setDuration] = useState('30');
  const [pending, setPending] = useState('');
  const [error, setError] = useState('');

  async function load() {
    setPending('list'); setError('');
    try {
      const [exams, assessments] = await Promise.all([api.exams(), api.assessments()]);
      setCatalog({ exams, assessments });
    } catch (e) { setError(examError(e)); }
    finally { setPending(''); }
  }

  async function open(id) {
    setPending('report'); setError('');
    try { setReport(await api.examReport(id)); }
    catch (e) { setError(examError(e)); }
    finally { setPending(''); }
  }

  async function publish(event) {
    event.preventDefault();
    setPending('publish'); setError('');
    try {
      const exam = await api.publishExam({ assessment_id: source, duration_minutes: Number(duration) });
      setCatalog(c => ({ ...c, exams: [exam, ...c.exams.filter(row => row.id !== exam.id)] }));
      setSource('');
      flash('Exam published for the class.', 'success');
      await open(exam.id);
    } catch (e) { setError(examError(e)); setPending(''); }
  }

  useEffect(() => { if (!isMock) load(); }, [isMock]);
  const sources = catalog?.assessments.filter(a => a.status === 'approved' && !catalog.exams.some(e => e.id === a.id)) || [];
  return <>
    <PageHeading eyebrow="ONLINE EXAMS" title="Timed exams" description="Publish approved questions, mark submitted work, and release each student’s result." />
    {isMock ? <Panel className="exam-panel"><p>Sign in to publish and mark exams.</p></Panel> : <>
      {error && <p className="field-error" role="alert">{error} {!catalog && <Button variant="outline" onClick={load}>Try again</Button>}</p>}
      {!catalog && pending && <p role="status">Loading exams…</p>}
      {catalog && <div className="exam-workspace">
        <Panel className="exam-panel"><h2>Publish an exam</h2>
          <p>Use a fresh approved assessment. Publishing opens it to enrolled students and locks its questions.</p>
          {sources.length ? <form onSubmit={publish} className="exam-fields">
            <label className="field">Approved assessment<select value={source} onChange={e => setSource(e.target.value)} required>
              <option value="">Choose an assessment</option>
              {sources.map(a => <option value={a.id} key={a.id}>{a.title} · {classes.find(c => c.id === a.class_id)?.name || a.class_id}</option>)}
            </select></label>
            <label className="field">Minutes per attempt<input type="number" min="1" max="180" step="1" required value={duration} onChange={e => setDuration(e.target.value)} /></label>
            <Button type="submit" disabled={!source || !!pending}>{pending === 'publish' ? 'Publishing…' : 'Publish exam'}</Button>
          </form> : <p>Approve a fresh assessment to use it here.</p>}
        </Panel>
        <Panel className="exam-panel"><h2>Published exams</h2>
          {catalog.exams.length ? <ul className="exam-list">{catalog.exams.map(exam =>
            <li key={exam.id}><div><strong>{exam.title}</strong><small>{examDetails(exam)}</small></div>
              <Button variant="outline" onClick={() => open(exam.id)} disabled={!!pending}>Open report</Button></li>)}</ul>
            : <p>No exams published yet.</p>}
        </Panel>
      </div>}
      {pending === 'report' && <p role="status">Loading the report…</p>}
      {report && <Panel className="exam-panel exam-report">
        <div className="exam-row"><div><h2>{report.title}</h2><p>{examDetails(report)}</p></div>
          <Button variant="outline" onClick={() => open(report.id)} disabled={!!pending}>Refresh report</Button></div>
        <p>{report.students.filter(s => s.attempt.status === 'submitted' || s.attempt.status === 'released').length} of {report.students.length} submitted</p>
        {report.students.length ? <ul className="exam-list">{report.students.map(({ student, attempt }) =>
          <li key={student.id}><div><strong>{student.display_name}</strong><small>{student.roll_no} · {statusLabel[attempt.status]}</small></div>
            {['submitted', 'released'].includes(attempt.status) && <ExamMarking key={attempt.id} exam={report} attempt={attempt} onReview={next => {
              setReport(current => current?.id === report.id ? { ...current, students: current.students.map(row =>
                row.attempt.id === next.id ? { ...row, attempt: next } : row) } : current);
            }} />}</li>)}</ul> : <p>Students can start the exam after joining this class.</p>}
      </Panel>}
    </>}
  </>;
}

function ExamMarking({ exam, attempt, onReview }) {
  const [scores, setScores] = useState({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const released = attempt.status === 'released';
  const unmarked = exam.questions.some(q => attempt.scores[q.id] == null && !scores[q.id]);

  async function review(release) {
    setSaving(true); setError('');
    const marks = Object.fromEntries(Object.entries(scores).filter(([, score]) => score !== '').map(([id, score]) => [id, Number(score)]));
    try { onReview(await api.reviewExam(exam.id, attempt.id, { version: attempt.version, scores: marks, release })); setScores({}); }
    catch (e) { setError(examError(e)); }
    finally { setSaving(false); }
  }

  return <details className="exam-marking"><summary>{attempt.to_mark ? `${attempt.to_mark} to mark` : scoreText(attempt.score, attempt.max_score)} · {released ? 'View answers' : 'Review answers'}</summary>
    <form onSubmit={e => { e.preventDefault(); review(e.nativeEvent.submitter?.value === 'release'); }}>
      {exam.questions.map((q, i) => <div className="student-answer" key={q.id}>
        <b>{i + 1}. {q.stem}</b>
        <p className="exam-response">{answerText(q, attempt.answers[q.id])}</p>
        {q.model_answer && !released && <p>Model answer: {q.model_answer}</p>}
        {released ? <small>{scoreText(attempt.scores[q.id], q.marks)}</small> : <label className="field exam-mark">Marks for question {i + 1} (max {q.marks})
          <input type="number" min="0" max={q.marks} step="0.01" value={scores[q.id] ?? attempt.teacher_scores[q.id] ?? ''}
            placeholder={attempt.scores[q.id] ?? 'Needs marking'} onChange={e => setScores({ ...scores, [q.id]: e.target.value })} /></label>}
      </div>)}
      {error && <p className="field-error" role="alert">{error}</p>}
      {!released && <div className="exam-actions"><Button type="submit" value="save" variant="outline" disabled={saving}>Save marks</Button>
        <Button type="submit" value="release" disabled={saving || unmarked}>{saving ? 'Saving…' : 'Release result'}</Button></div>}
    </form>
  </details>;
}
