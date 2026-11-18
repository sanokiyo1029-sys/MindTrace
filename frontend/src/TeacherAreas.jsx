// Teacher areas added around the original workflow: class overview, history, student reports, teaching
// recommendations, student feedback review, assigned practice and the save/sync status. All counts are live.
import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, mediaUrl } from './api.js';
import { flush, outbox, retryBlocked, subscribe, summary } from './offline.js';
import Icon from './Icon.jsx';
import { Button, PageHeading, Panel } from './ui.jsx';
import ClassUnderstanding from './ClassUnderstanding.jsx';
import { sampleOverview } from './sampleUnderstanding.js';

export const SUBJECTS = [['mathematics', 'Mathematics'], ['physics', 'Physics'], ['chemistry', 'Chemistry'],
  ['biology', 'Biology'], ['engineering', 'Engineering'], ['technology', 'Technology']];
export const subjectName = (s) => (SUBJECTS.find(([k]) => k === s) || [, 'Mathematics'])[1];

// loads once per key; returns [data | null | 'error', reload]
function useLoad(fn, deps) {
  const [data, setData] = useState(null);
  const load = () => { setData(null); fn().then(setData, () => setData('error')); };
  useEffect(load, deps);
  return [data, load];
}
const Loading = ({ what }) => <p className="list-empty" role="status">Loading {what}…</p>;
const Failed = ({ what, retry }) => <p className="list-empty" role="alert">Couldn’t load {what}. <button className="text-button" onClick={retry}>Try again</button></p>;

// ------------------------------------------------------------------ class + subject picker and overview
export function ClassOverview({ classes, classId, subject, setClassId, setSubject, isMock, openAssessment }) {
  const [ov, reload] = useLoad(() => isMock ? Promise.resolve(sampleOverview(subject)) : api.overview(classId, subject, true), [classId, subject, isMock]);
  const cls = classes.find(c => c.id === classId);
  return <section className="class-overview">
    <div className="section-heading"><div><span className="eyebrow">{isMock ? 'CLASS OVERVIEW · SAMPLE DATA' : 'CLASS OVERVIEW'}</span>
      <h2>Class {cls?.name || '…'} · {subjectName(subject)}</h2></div>
      <div className="class-picker">
        <label className="field">Class<select value={classId} onChange={e => setClassId(e.target.value)}>{classes.map(c => <option key={c.id} value={c.id}>Class {c.name}</option>)}</select></label>
        <label className="field">Subject<select value={subject} onChange={e => setSubject(e.target.value)}>{SUBJECTS.map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
      </div></div>
    {ov === null ? <Loading what="this class" /> : ov === 'error' ? <Failed what="this class" retry={reload} /> : <>
      <div className="overview-counts">
        <div><b>{ov.assessment_count}</b><span>assessments</span></div>
        <div><b>{ov.topics.length}</b><span>topics covered</span></div>
        <div><b>{ov.student_count}</b><span>students</span></div>
        <div className={ov.needs_review ? 'needs' : ''}><b>{ov.needs_review}</b><span>papers to review</span>{ov.needs_review > 0 && <Link to="/review-scans" className="text-link">Review</Link>}</div>
      </div>
      {ov.understanding ? <ClassUnderstanding data={ov.understanding} history={ov.history}
        isMock={isMock} openAssessment={openAssessment} /> : <p className="list-empty">Concept evidence is unavailable on this server.</p>}
    </>}
  </section>;
}

// ------------------------------------------------------------------ history
export function HistoryPage({ classes, classId, subject, setClassId, setSubject, openAssessment }) {
  const [ov, reload] = useLoad(() => api.overview(classId, subject), [classId, subject]);
  const cls = classes.find(c => c.id === classId);
  const concepts = ov && ov !== 'error' ? [...new Set(ov.history.flatMap(h => Object.keys(h.concepts)))] : [];
  const scored = ov && ov !== 'error' ? [...ov.history].reverse().filter(h => Object.keys(h.concepts).length) : [];
  return <><PageHeading eyebrow="HISTORY" title="What has this class worked on?" description={`Class ${cls?.name || ''} · ${subjectName(subject)}. Scores use confirmed papers only.`}
    action={<div className="class-picker"><select aria-label="Class" value={classId} onChange={e => setClassId(e.target.value)}>{classes.map(c => <option key={c.id} value={c.id}>Class {c.name}</option>)}</select><select aria-label="Subject" value={subject} onChange={e => setSubject(e.target.value)}>{SUBJECTS.map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></div>} />
    {ov === null ? <Loading what="history" /> : ov === 'error' ? <Failed what="history" retry={reload} /> : !ov.history.length ?
      <Panel className="empty-review"><h2>No assessments yet</h2><p>Past assessments for this class and subject will be listed here.</p><Link to="/assessment" className="button primary">Create assessment</Link></Panel> : <>
      <Panel className="list-panel"><div className="assessment-list">{ov.history.map(h => <button key={h.id} className="assessment-row" onClick={() => openAssessment(h.id, true)}>
        <span><b>{h.title}</b><small>{h.topic} · {new Date(h.created_at).toLocaleDateString()}{h.parent_assessment_id ? ' · follow-up' : ''} · {h.verified} paper{h.verified === 1 ? '' : 's'} confirmed</small></span>
        <span className="history-score">{h.score_pct === null ? '–' : `${h.score_pct}%`}<small>{h.status}</small></span></button>)}</div></Panel>
      <Panel className="list-panel"><span className="eyebrow">CONCEPT TRENDS</span><h2>Class % correct by concept, oldest first</h2>
        {scored.length < 2 ? <p className="list-empty">Trends appear once two or more assessments have confirmed papers on the same concepts.</p> :
          <div className="table-scroll"><table className="results-table"><thead><tr><th>Concept</th>{scored.map(h => <th key={h.id}>{h.title}</th>)}</tr></thead>
            <tbody>{concepts.map(c => <tr key={c}><td>{c}</td>{scored.map(h => <td key={h.id}>{h.concepts[c] ?? '–'}{h.concepts[c] !== undefined && '%'}</td>)}</tr>)}</tbody></table></div>}
      </Panel></>}
  </>;
}

// ------------------------------------------------------------------ one student's report (teacher only)
export function StudentReportPage() {
  const { id } = useParams();
  const [rep, reload] = useLoad(() => api.studentReport(id), [id]);
  if (rep === null) return <Loading what="the student report" />;
  if (rep === 'error') return <><PageHeading eyebrow="STUDENT REPORT" title="Report unavailable" description="This student isn't in one of your classes, or the report couldn't load." /><Button variant="outline" onClick={reload}>Try again</Button></>;
  return <><PageHeading eyebrow={`STUDENT REPORT · ROLL ${rep.student.roll_no} · TEACHER ONLY`} title={rep.student.display_name} description="Each paper as you confirmed it. A wrong answer is evidence about one question, not a label for the student." />
    {!rep.assessments.length && <Panel className="empty-review"><p>No papers for this student yet.</p></Panel>}
    {rep.assessments.map(a => <Panel key={a.assessment_id} className="report-card"><div className="section-heading"><div><span className="eyebrow">{subjectName(a.subject)} · {a.topic}</span><h2>{a.title}</h2></div>
      <span className="status-pill status-draft"><span />{a.scan_status === 'accepted' ? `${a.correct}/${a.total} correct` : a.scan_status.replace('_', ' ')}</span></div>
      {a.image_url && <a className="report-photo" href={mediaUrl(a.image_url)} target="_blank" rel="noreferrer">Open the scanned paper</a>}
      <ul className="report-answers">{a.answers.map((x, i) => <li key={x.question_id}><b>Q{i + 1}. {x.stem}</b>
        <span>{x.type === 'descriptive' ? (x.text ? `“${x.text}”` : x.final === 'blank' ? 'Left blank' : 'Not transcribed') : `Answer ${x.final || '–'}${x.correct_answer ? ` · key ${x.correct_answer}` : ''}`}</span>
        {x.feedback && <small>Feedback ({x.feedback.status}): {x.feedback.text || '—'}</small>}</li>)}</ul></Panel>)}
  </>;
}

// ------------------------------------------------------------------ video link (YouTube, a video file, or a plain link)
export function VideoLink({ url, title = 'Video' }) {
  const [failed, setFailed] = useState(false);
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => { const on = () => setOnline(true), off = () => setOnline(false); addEventListener('online', on); addEventListener('offline', off); return () => { removeEventListener('online', on); removeEventListener('offline', off); }; }, []);
  if (!url) return null;
  const yt = url.match(/(?:youtube\.com\/(?:watch\?v=|embed\/|shorts\/)|youtu\.be\/)([\w-]{11})/);
  const file = /\.(mp4|webm|ogg)(\?|#|$)/i.test(url);
  const link = <a href={url} target="_blank" rel="noreferrer" className="text-link">Open the video <Icon name="arrow" size={14} /></a>;
  if (!online) return <p className="video-note">The video needs an internet connection. {link}</p>;
  if (failed || (!yt && !file)) return <p className="video-note">{failed ? 'The video couldn’t play here. ' : ''}{link}</p>;
  return <div className="video-box">{yt
    ? <iframe src={`https://www.youtube-nocookie.com/embed/${yt[1]}`} title={title} allow="encrypted-media; picture-in-picture" allowFullScreen loading="lazy" />
    : <video src={url} controls preload="metadata" onError={() => setFailed(true)} aria-label={title} />}</div>;
}

// ------------------------------------------------------------------ teaching recommendations
function PlanCard({ card, plan, assessmentId, onSaved, flash }) {
  const base = plan || card.teaching_action || { title: '', minutes: 5, steps: [] };
  const [title, setTitle] = useState(base.title); const [minutes, setMinutes] = useState(base.minutes || 5);
  const [steps, setSteps] = useState((base.steps || []).join('\n')); const [video, setVideo] = useState(plan?.video_url || '');
  const [saving, setSaving] = useState(false);
  async function save(status) {
    setSaving(true);
    try { onSaved(await api.editPlan(assessmentId, card.misconception_id, { title, minutes: Number(minutes) || 5, steps: steps.split('\n'), video_url: video, status })); flash(status === 'dismissed' ? 'Recommendation set aside.' : 'Teaching plan saved.', 'success'); }
    catch (e) { flash(e.message); } finally { setSaving(false); }
  }
  return <Panel className={`plan-card ${plan?.status === 'dismissed' ? 'dismissed' : ''}`}>
    <div className="misconception-head"><span className="possible-badge">Possible</span><span className="affected">{card.students_affected} student{card.students_affected === 1 ? '' : 's'}</span>{plan && <span className="source-tag source-teacher">{plan.status === 'dismissed' ? 'Set aside' : 'Edited by you'}</span>}</div>
    <h3>{card.label}</h3><p className="uncertainty">{card.why_we_think_so}</p>
    <label className="field">Activity<input value={title} onChange={e => setTitle(e.target.value)} /></label>
    <label className="field">Minutes<input type="number" min="1" max="60" value={minutes} onChange={e => setMinutes(e.target.value)} /></label>
    <label className="field">Steps (one per line)<textarea rows="4" value={steps} onChange={e => setSteps(e.target.value)} /></label>
    <label className="field">Video link (optional)<input type="url" inputMode="url" placeholder="https://www.youtube.com/watch?v=…" value={video} onChange={e => setVideo(e.target.value)} /><small>Shown with this concept to students whose feedback you approve. Needs internet to play.</small></label>
    <VideoLink url={plan?.video_url} title={title} />
    {card.followup_question && <div className="followup-preview"><span className="eyebrow">SUGGESTED RETEST</span><b>{card.followup_question.stem}</b></div>}
    <div className="plan-actions"><Button disabled={saving} onClick={() => save('planned')} icon="check">{saving ? 'Saving…' : 'Save plan'}</Button><Button variant="outline" disabled={saving} onClick={() => save('dismissed')}>Set aside</Button></div>
  </Panel>;
}

export function RecommendationsPage({ assessment, setAssessment, insights, loadInsights, busy, flash }) {
  if (!insights) return <><PageHeading eyebrow="TEACHING RECOMMENDATIONS" title="Plan what to teach next." description="Recommendations come from confirmed results. You edit them and decide what is used or assigned." />
    <Panel className="empty-review"><h2>{assessment.status === 'confirmed' ? 'Load the class insights first' : 'Confirm the scanned papers first'}</h2><p>Open an assessment with confirmed results to see suggested explanations, activities and retests.</p>
      {assessment.status === 'confirmed' ? <Button onClick={loadInsights} disabled={busy}>Load insights</Button> : <Link to="/workspace" className="button outline">Choose an assessment</Link>}</Panel></>;
  const plan = assessment.plan || {};
  return <><PageHeading eyebrow="TEACHING RECOMMENDATIONS" title="Your plan, your call." description={`${assessment.title}: suggestions are hypotheses from the answer pattern. Edit, set aside, then create a retest or approve student feedback.`}
    action={<div className="plan-links"><Link to="/feedback" className="button outline">Student feedback</Link><Link to="/followup" className="button primary">Create retest</Link></div>} />
    {!insights.misconceptions.length && <Panel className="empty-review"><p>No wrong-answer pattern matched a known misconception. Review individual answers under Student feedback.</p></Panel>}
    <div className="plan-grid">{insights.misconceptions.map(m => <PlanCard key={m.misconception_id} card={m} plan={plan[m.misconception_id]} assessmentId={assessment.id} flash={flash}
      onSaved={p => setAssessment(a => ({ ...a, plan: p }))} />)}</div></>;
}

// ------------------------------------------------------------------ teacher-verified student feedback
const suggestionText = { ok: null, not_requested: 'No AI suggestion yet.', unavailable: null, too_unclear: null };
function FeedbackCard({ item, onSaved, flash }) {
  const [text, setText] = useState(item.text); const [concept, setConcept] = useState(item.concept); const [video, setVideo] = useState(item.video_url || '');
  const [saving, setSaving] = useState('');
  useEffect(() => { setText(item.text); }, [item.text]);
  const s = item.suggestion || {};
  async function save(status) {
    setSaving(status || 'save');
    try { onSaved(await api.editFeedback(item.id, { text, concept, video_url: video, ...(status && { status }), base_version: item.version })); flash(status === 'approved' ? `Feedback for ${item.student.display_name} approved. They can see it once results are confirmed.` : 'Saved.', 'success'); }
    catch (e) { if (e.current) onSaved(e.current); flash(e.message); } finally { setSaving(''); }
  }
  const r = item.response;
  return <Panel className={`feedback-card status-${item.status}`}>
    <div className="section-heading"><div><span className="eyebrow">ROLL {item.student.roll_no} · {item.question_type === 'descriptive' ? 'WRITTEN ANSWER' : 'BUBBLE ANSWER'}</span><h3>{item.student.display_name}: {item.stem}</h3></div>
      <span className={`status-pill ${item.status === 'approved' ? 'status-complete' : 'status-draft'}`}><span />{{ pending: 'Not shared', approved: 'Approved', dismissed: 'Dismissed' }[item.status]}</span></div>
    <div className="feedback-evidence">
      {r.crop_url && <img src={mediaUrl(r.crop_url)} alt={`${item.student.display_name}'s handwriting for this question`} loading="lazy" />}
      <div>{item.question_type === 'descriptive' ? <><b>Transcription</b><p className={r.text_state === 'unclear' ? 'unclear' : ''}>{r.text || 'Not transcribed yet.'}</p>{r.text_state === 'unclear' && <small>Some words were unclear. Correct the transcription in Scan review.</small>}{item.model_answer && <small>Your notes: {item.model_answer}</small>}</>
        : <><b>Chose {r.final}{r.option_text ? ` (${r.option_text})` : ''}; key {item.correct_answer}</b>{r.text && <p>Reasoning: “{r.text}”</p>}</>}</div>
    </div>
    <div className={`suggestion suggestion-${s.state}`}><span className="eyebrow">{s.source === 'ai' ? 'AI SUGGESTION · CHECK IT' : s.source === 'library' ? 'SUGGESTION FROM THE ANSWER PATTERN' : 'SUGGESTION'}</span>
      {s.state === 'ok' ? <><b>Possible: {s.label || 'no misconception found'}</b><p>{s.text}</p></> : <p>{s.message || suggestionText[s.state] || 'No suggestion.'}</p>}</div>
    <label className="field">Concept to revisit<input value={concept} onChange={e => setConcept(e.target.value)} /></label>
    <label className="field">Feedback the student will read<textarea rows="3" value={text} onChange={e => setText(e.target.value)} placeholder="Specific to this answer, e.g. Try drawing two quarters and counting how many quarters you have." /></label>
    <label className="field">Video link (optional)<input type="url" value={video} onChange={e => setVideo(e.target.value)} placeholder="https://…" /></label>
    <div className="plan-actions"><Button disabled={!!saving || !text.trim()} onClick={() => save('approved')} icon="check">{saving === 'approved' ? 'Approving…' : 'Approve for student'}</Button>
      <Button variant="outline" disabled={!!saving} onClick={() => save()}>Save draft</Button>
      <Button variant="outline" disabled={!!saving} onClick={() => save(item.status === 'dismissed' ? 'pending' : 'dismissed')}>{item.status === 'dismissed' ? 'Restore' : 'Dismiss'}</Button></div>
  </Panel>;
}

export function FeedbackPage({ assessment, flash }) {
  const [data, reload] = useLoad(() => assessment.id ? api.feedback(assessment.id) : Promise.resolve({ items: [] }), [assessment.id]);
  const [asking, setAsking] = useState(false);
  const [items, setItems] = useState([]);
  useEffect(() => { if (data && data !== 'error') setItems(data.items); }, [data]);
  async function ask() { setAsking(true); try { setItems((await api.suggestFeedback(assessment.id)).items); } catch (e) { flash(e.message); } finally { setAsking(false); } }
  const waiting = items.filter(i => i.question_type === 'descriptive' && i.suggestion?.state !== 'ok' && i.status === 'pending').length;
  return <><PageHeading eyebrow="STUDENT FEEDBACK · TEACHER APPROVAL" title="Feedback students can learn from." description="Compare each answer with the suggestion, edit it, and approve it. Students only ever see what you approve, after you confirm the results." />
    {!assessment.id ? <Panel className="empty-review"><p>Open an assessment first.</p></Panel> : data === null ? <Loading what="answers" /> : data === 'error' ? <Failed what="answers" retry={reload} /> : <>
      <div className="note-banner" role="status"><Icon name="shield" size={17} /><p>{data.ai_available ? 'AI suggestions need an internet connection. Unclear handwriting is never sent; transcribe it first.' : 'AI isn’t set up on this server, so write the feedback yourself. Everything else works.'}</p>
        {data.ai_available && <Button variant="outline" disabled={asking || !waiting} onClick={ask}>{asking ? 'Asking…' : `Suggest for ${waiting} written answer${waiting === 1 ? '' : 's'}`}</Button>}</div>
      {!items.length && <Panel className="empty-review"><h2>Nothing to review</h2><p>Written answers and wrong bubble answers from confirmed papers appear here.</p><Link to="/review-scans" className="button outline">Scan review</Link></Panel>}
      {items.map(i => <FeedbackCard key={i.id} item={i} flash={flash} onSaved={x => setItems(list => list.map(y => y.id === x.id ? x : y))} />)}</>}
  </>;
}

// ------------------------------------------------------------------ assigned practice (on the print page)
export function PracticePanel({ assessment, flash }) {
  const [st, setSt] = useState(null);
  useEffect(() => { if (assessment.id && assessment.status !== 'draft') api.practiceStatus(assessment.id).then(setSt, () => setSt(null)); }, [assessment.id, assessment.status]);
  if (!assessment.id || assessment.status === 'draft') return null;
  async function assign() { try { setSt(await api.assign(assessment.id)); flash('Assigned. Students see it under Practice on their dashboard.', 'success'); } catch (e) { flash(e.message); } }
  const done = st?.students?.filter(s => s.status === 'submitted').length || 0;
  return <Panel className="practice-panel"><span className="eyebrow">OPTIONAL · ONLINE PRACTICE</span><h3>{st?.assigned ? `Assigned · ${done} of ${st.students.length} submitted` : 'Assign as practice'}</h3>
    <p>{st?.assigned ? 'Students answer on their own dashboard, once each.' : 'You decide: students can also try these questions on their dashboard (needs internet).'}</p>
    {st?.assigned ? <ul className="practice-status">{st.students.map(s => <li key={s.student.id}>{s.student.roll_no} · {s.student.display_name}<span>{s.status === 'submitted' ? 'Submitted' : 'Not started'}</span></li>)}</ul>
      : <Button variant="outline" onClick={assign} icon="users">Assign to the class</Button>}</Panel>;
}

// ------------------------------------------------------------------ save / sync status (top bar)
export function SyncBadge({ onSynced }) {
  const [items, setItems] = useState(outbox);
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => {
    const unsub = subscribe(setItems);
    const on = () => { setOnline(true); flush(onSynced); }, off = () => setOnline(false);
    addEventListener('online', on); addEventListener('offline', off);
    flush(onSynced); // anything left from before a reload or a sign-in
    return () => { unsub(); removeEventListener('online', on); removeEventListener('offline', off); };
  }, []);
  const s = summary(items);
  const label = s.blocked ? `${s.blocked} change${s.blocked === 1 ? '' : 's'} blocked: sign in again`
    : s.conflict ? `${s.conflict} change${s.conflict === 1 ? '' : 's'} need${s.conflict === 1 ? 's' : ''} a look (edited elsewhere)`
      : s.failed ? `${s.failed} change${s.failed === 1 ? '' : 's'} not accepted` : s.pending ? `${s.pending} saved on this device · ${online ? 'syncing' : 'pending sync'}`
        : online ? 'All changes synced' : 'Offline · edits are saved on this device';
  const tone = s.blocked || s.conflict || s.failed ? 'sync-bad' : s.pending || !online ? 'sync-wait' : 'sync-ok';
  return <span className={`sync-badge ${tone}`} role="status" title="Question edits and scan reviews are saved on this device first. Scanning, AI and videos need internet.">
    <i />{label}{(s.blocked || s.failed) > 0 && <button className="text-button" onClick={() => { retryBlocked(); flush(onSynced); }}>Retry</button>}</span>;
}
