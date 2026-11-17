import { useEffect, useRef, useState } from 'react';
import { Link, Navigate, NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { api, demo, getServer, getTeacherToken, isMock as fixtureMode, isNative, mediaUrl, onBusy, printUrl, setOnAuthLost, setServer, setTeacherToken, store } from './api.js';
import Auth from './Auth.jsx';
import Landing, { SiteHeader, Wordmark } from './Landing.jsx';
import StudentHome from './StudentHome.jsx';
import PaperSurface from './PaperSurface.jsx';
import Icon from './Icon.jsx';

const nav = [
  { to: '/workspace', label: 'Overview', icon: 'grid' }, { to: '/assessment', label: 'New assessment', icon: 'plus' },
  { to: '/review', label: 'Question review', icon: 'book' }, { to: '/print', label: 'Print sheets', icon: 'printer' },
  { to: '/scanner', label: 'Scan papers', icon: 'scan' }, { to: '/insights', label: 'Class insights', icon: 'chart' },
];

const emptyAssessment = { id: '', class_id: 'cl_7a', title: '', topic: '', concepts_text: '', status: 'draft', questions: [] };
const statusLabel = { draft: 'Draft', approved: 'Approved', printed: 'Printed', scanning: 'Scanning', confirmed: 'Results ready' };
const statusScreen = { draft: '/review', approved: '/print', printed: '/scanner', scanning: '/scanner', confirmed: '/insights' };

function App() {
  const [teacherToken, setTeacherTokenState] = useState(getTeacherToken);
  const [studentSession, setStudentSession] = useState(null);
  const [sample, setSample] = useState(fixtureMode);
  const [googleError, setGoogleError] = useState('');
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const previewAvailable = import.meta.env.VITE_MOCK !== 'false';

  useEffect(() => setOnAuthLost(() => setTeacherTokenState('')), []);

  function startSession(session) {
    if (session.role === 'student') {
      setStudentSession(session);
      navigate('/student', { replace: true });
      return;
    }
    setTeacherToken(session.token);
    setTeacherTokenState(session.token);
    setSample(false);
    navigate('/workspace', { replace: true });
  }

  function signOutTeacher() {
    if (!sample) {
      api.logout().catch(() => {});
      window.google?.accounts?.id?.disableAutoSelect();
      setTeacherToken('');
      setTeacherTokenState('');
      store.set('mt_assessment', '');
    }
    setSample(false);
    navigate('/login?role=teacher', { replace: true });
  }

  function signOutStudent() {
    api.logout(studentSession.token).catch(() => {});
    setStudentSession(null);
    navigate('/login?role=student', { replace: true });
  }

  if (pathname === '/') {
    const home = sample || teacherToken ? '/workspace' : studentSession ? '/student' : undefined;
    return <ExperiencePage page="landing" home={home}><Landing home={home} /></ExperiencePage>;
  }
  if (pathname === '/login') {
    return <ExperiencePage page="login"><Auth
      onSession={startSession}
      onSample={previewAvailable ? () => { setSample(true); navigate('/workspace'); } : undefined}
      serverField={isNative ? <ServerField /> : null}
      googleSignIn={<>
        <GoogleButton onToken={token => startSession({ role: 'teacher', token })} onError={setGoogleError} />
        {googleError && <p className="field-error" role="alert">{googleError}</p>}
      </>}
    /></ExperiencePage>;
  }
  if (pathname === '/student') {
    return studentSession
      ? <ExperiencePage page="student" onSignOut={signOutStudent}><StudentHome results={studentSession.results} /></ExperiencePage>
      : <Navigate to="/login?role=student" replace />;
  }
  if (!sample && !teacherToken) return <Navigate to="/login?role=teacher" replace />;
  return <TeacherWorkspace key={sample ? 'sample' : teacherToken} isMock={sample} teacherToken={teacherToken} onSignOut={signOutTeacher} />;
}

function ExperiencePage({ page, home, onSignOut, children }) {
  const mainRef = useRef(null);
  const contentClass = { landing: 'landing-content', login: 'auth-content', student: 'student-home' }[page];
  useEffect(() => {
    window.scrollTo(0, 0);
    const heading = mainRef.current?.querySelector('h1');
    if (heading) {
      heading.tabIndex = -1;
      heading.focus({ preventScroll: true });
    }
  }, [page]);

  return <div className="shell public-shell">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <div className="public-area">
      <SiteHeader page={page} home={home} onSignOut={onSignOut} />
      <main key={page} ref={mainRef} id="main-content" tabIndex={-1} className={`paper-route ${contentClass}`}>
        {children}
      </main>
    </div>
  </div>;
}

function TeacherWorkspace({ isMock, teacherToken, onSignOut }) {
  const [assessment, setAssessment] = useState(() => isMock ? demo.assessment : emptyAssessment);
  const [insights, setInsights] = useState(() => isMock ? demo.insights : null);
  const [scanProgress, setScanProgress] = useState(() => isMock ? demo.scans : { total: 0, accepted: 0, needs_review: 0, remaining: 0, scans: [] });
  const [toast, setToast] = useState(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const firstPage = useRef(true);
  // type: success | info | error. Errors stay longer and are announced right away.
  const flash = (message, type = 'error') => { const id = Date.now(); setToast({ id, message, type }); window.setTimeout(() => setToast(t => t?.id === id ? null : t), type === 'error' ? 8000 : 4500); };

  useEffect(() => {
    window.scrollTo(0, 0);
    if (firstPage.current) { firstPage.current = false; return; }
    document.getElementById('main-content')?.focus({ preventScroll: true }); // keyboard users land on the new page
  }, [location.pathname]);
  useEffect(() => onBusy(setLoading), []);
  // After a refresh: reopen the assessment the teacher had open.
  useEffect(() => { const id = store.get('mt_assessment'); if (!isMock && teacherToken && id && !assessment.id) openAssessment(id); }, [teacherToken]);
  useEffect(() => { if (!isMock && assessment.id) store.set('mt_assessment', assessment.id); }, [assessment.id]);
  useEffect(() => {
    if (!isMock && teacherToken && assessment?.id) api.scans(assessment.id).then(setScanProgress).catch(() => {});
  }, [assessment?.id, teacherToken]);

  async function openAssessment(id, go = false) {
    try {
      const opened = await api.assessment(id);
      setAssessment(opened); setInsights(null);
      if (go) navigate(statusScreen[opened.status] || '/workspace');
    } catch (error) { if (!go) store.set('mt_assessment', ''); flash(error.message); }
  }

  async function generate(values) {
    setBusy(true);
    try {
      const result = isMock ? { ...demo.assessment, id: `as_${Date.now()}`, title: `${values.topic} check`, topic: values.topic.toLowerCase(), class_id: values.class_id, concepts_text: values.concepts_text, status: 'draft', questions: [...demo.assessment.questions, ...demo.question_bank].slice(0, values.num_questions).map((q, i) => ({ ...q, id: `q_${Date.now()}_${i}`, status: 'draft', source: 'sample' })) } : await api.generate(values);
      setAssessment(result); if (result.notes?.length) flash(result.notes.join(' '), 'info'); else flash(`${result.questions.length} questions drafted. Check each one before approving.`, 'success'); setInsights(null); setScanProgress({ total: 0, accepted: 0, needs_review: 0, remaining: 0, scans: [] }); navigate('/review');
    } catch (error) { flash(error.message); }
    finally { setBusy(false); }
  }

  async function approve() {
    if (!assessment?.questions?.length) return flash('Add at least one question before approval.');
    const invalid = assessment.questions.some(q => !q.stem?.trim() || Object.values(q.options || {}).some(v => !v?.trim()) || !q.answer || !['A', 'B', 'C', 'D'].includes(q.answer));
    if (invalid) return flash('Each question needs a prompt, four options and a correct answer.');
    setBusy(true);
    try {
      if (isMock) { const updated = { ...assessment, status: 'approved', questions: assessment.questions.map(q => ({ ...q, status: 'approved' })) }; setAssessment(updated); navigate('/print'); }
      else { for (const q of assessment.questions) await api.editQuestion(q.id, q); const updated = await api.approve(assessment.id); setAssessment(updated); navigate('/print'); }
    }
    catch (error) {
      if (error.validationErrors) setAssessment(current => ({ ...current, questions: current.questions.map(q => ({ ...q, validation_errors: error.validationErrors[q.id] || [] })) }));
      flash(error.message);
    }
    finally { setBusy(false); }
  }

  function printSheets() {
    if (isMock) return flash('PDF printing needs the MindTrace API. Sample mode does not generate QR sheets.', 'info');
    // In the Android app an outside link opens in the phone's browser; on the web it opens a new tab.
    if (isNative) window.location.href = printUrl(assessment.id);
    else if (!window.open(printUrl(assessment.id), '_blank')) return flash('Allow pop-ups to open the generated PDF, then try again.');
    if (assessment.status === 'approved') setAssessment({ ...assessment, status: 'printed' });
  }

  async function upload(file) {
    if (!file) return;
    if (isMock) return flash('Live scanning requires the MindTrace API. The sample insight below is labelled fixture data.', 'info');
    if (!assessment.id) return flash('Open an assessment from the Overview before scanning.');
    setBusy(true);
    try {
      const result = await api.uploadScan(assessment.id, file); const who = result.student?.display_name || 'Sheet';
      if (result.status === 'rejected') flash(`Couldn't read that photo: ${(result.reject_reason || 'unclear image').replaceAll('_', ' ')}. Try again with the whole page in view.`);
      else if (result.status === 'needs_review') flash(`${who}: some marks are unclear. Check them in the review queue.`, 'info');
      else if (result.status === 'duplicate') flash(`${who}'s sheet was already scanned.`, 'info');
      else flash(`${who}'s sheet is scanned.`, 'success');
      setScanProgress(await api.scans(assessment.id));
    }
    catch (error) { flash(error.message); }
    finally { setBusy(false); }
  }

  async function loadInsights() {
    if (!assessment?.id) return flash('Create and confirm an assessment before loading insights.');
    if (isMock) return assessment.id===demo.assessment.id?setInsights(demo.insights):flash('No sample scan fixture is linked to this draft.', 'info');
    setBusy(true); try { const data = await api.insights(assessment.id); setInsights(data); } catch (error) { flash(error.message); } finally { setBusy(false); }
  }
  useEffect(() => { if (!isMock && teacherToken && assessment?.id && assessment.status === 'confirmed') loadInsights(); }, [assessment?.id, assessment?.status, teacherToken]);

  async function reviewScan(scanId, answers) {
    try { await api.reviewScan(scanId, { answers, confirmed: true }); setScanProgress(await api.scans(assessment.id)); flash('Reviewed answers saved.', 'success'); }
    catch (error) { flash(error.message); }
  }
  async function confirmScans() {
    setBusy(true);
    try { setAssessment(await api.confirm(assessment.id)); flash('Results confirmed. Class insights are ready.', 'success'); navigate('/insights'); }
    catch (error) { flash(error.message); }
    finally { setBusy(false); }
  }

  const sampleTag = isMock && <span className="mode-tag" title="Uses labelled fixture data"><span className="mode-dot" /> Mock mode · sample data, not live</span>;
  const context = { assessment, setAssessment, insights, setInsights, scanProgress, setScanProgress, openAssessment, busy, generate, approve, printSheets, upload, loadInsights, reviewScan, confirmScans, flash, navigate, isMock };

  const mobileNav = [nav[0], nav[1], nav[3], nav[4], nav[5]];
  return <div className="shell workspace-shell">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <div className={`busy-bar ${loading ? 'on' : ''}`} aria-hidden="true" />
    <aside className="sidebar">
      <Link to="/" className="brand" aria-label="MindTrace home"><Wordmark /><span className="brand-mini" aria-hidden="true">M</span></Link>
      <div className="school-label">WORKSPACE</div>
      <nav aria-label="Main navigation" className="side-nav">{nav.map(item => <NavLink key={item.to} to={item.to} end={item.to === '/workspace'} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}><Icon name={item.icon} /><span>{item.label}</span>{item.to === '/review' && assessment.status === 'draft' && <i className="nav-pip" />}</NavLink>)}</nav>
      <div className="sidebar-spacer" />
      <div className="privacy-note"><span className="privacy-icon"><Icon name="shield" size={17} /></span><div><strong>Teacher-led insights</strong><p>Patterns are evidence for review, never a diagnosis.</p></div></div>
      <button className="profile-button" onClick={() => navigate('/student')}><span className="avatar">{isMock?'AS':'T'}</span><span><b>{isMock?'Alex Morgan':'Teacher'}</b><small>{isMock?'Mathematics teacher':'Connected account'}</small></span><span className="profile-more">···</span></button>
    </aside>
    <div className="main-area">
      <header className="topbar"><button className="mobile-brand" onClick={() => navigate('/')} aria-label="MindTrace home"><Wordmark /></button><div className="crumb"><span>Workspace</span><b>/</b><strong>{nav.find(n => n.to === location.pathname)?.label || 'Student results'}</strong></div><div className="top-actions">{sampleTag}<span className="teacher-chip"><span className="avatar mini">{isMock?'AM':'T'}</span><span>{isMock?'Alex Morgan':'Teacher'}</span></span><button className="text-button" onClick={onSignOut}>{isMock ? 'Exit sample' : 'Sign out'}</button></div></header>
      <main id="main-content" tabIndex="-1" className="content" aria-busy={loading}><div key={location.pathname} className="page-enter"><Routes>
        <Route path="/workspace" element={<Dashboard {...context} />} />
        <Route path="/assessment" element={<NewAssessment {...context} />} />
        <Route path="/review" element={<ReviewQuestions {...context} />} />
        <Route path="/print" element={<PrintPage {...context} />} />
        <Route path="/scanner" element={<Scanner {...context} />} />
        <Route path="/review-scans" element={<ReviewScans {...context} />} />
        <Route path="/insights" element={<InsightsPage {...context} />} />
        <Route path="/followup" element={<Followup {...context} />} />
        <Route path="*" element={<Navigate to="/workspace" replace />} />
      </Routes></div></main>
    </div>
    <nav className="mobile-nav" aria-label="Mobile navigation">{mobileNav.map(item => <NavLink key={item.to} to={item.to} end={item.to === '/workspace'} aria-label={item.label} className={({ isActive }) => isActive ? 'mobile-active' : ''}><Icon name={item.icon} size={21} /><span>{item.label.split(' ')[0]}</span></NavLink>)}</nav>
    {toast && <div key={toast.id} className={`toast toast-${toast.type}`} role={toast.type === 'error' ? 'alert' : 'status'}><span className="toast-badge" aria-hidden="true">{toast.type === 'success' ? <Icon name="check" size={15} /> : toast.type === 'error' ? '!' : 'i'}</span><span className="toast-text">{toast.message}</span><button aria-label="Dismiss notification" onClick={() => setToast(null)}><Icon name="close" size={16} /></button>{toast.type === 'success' && <i className="wedges" aria-hidden="true"><i /></i>}</div>}
  </div>;
}

function PageHeading({ eyebrow, title, description, action }) { return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div>{action}</div>; }
function Button({ children, variant = 'primary', icon, className = '', ...props }) { return <button className={`button ${variant} ${className}`} {...props}>{icon && <Icon name={icon} size={17} />}{children}</button>; }
function Panel({ children, className = '', interactive = false }) {
  if (interactive) return <PaperSurface className={`panel ${className}`}>{children}</PaperSurface>;
  return <section className={`panel ${className}`}>{children}</section>;
}

// "Continue with Google" (Google Identity Services). Shown only when the server has a Google client ID, and not
// in the Android app: Google blocks sign-in inside app web views (a native sign-in can post to /auth/google later).
// The backend checks the token and allows linked teacher accounts only; closing Google's window just does nothing.
let gisScript;
const loadGis = () => gisScript ||= new Promise((resolve, reject) => {
  const s = Object.assign(document.createElement('script'), { src: 'https://accounts.google.com/gsi/client', async: true });
  s.onload = resolve; s.onerror = () => { gisScript = null; reject(new Error('Google sign-in could not load.')); };
  document.head.append(s);
});
function GoogleButton({ onToken, onError }) {
  const slot = useRef(null); const [state, setState] = useState('off'); // off | ready | working | unavailable
  useEffect(() => {
    if (isNative) return;
    let live = true;
    api.authConfig().then(({ google_client_id: clientId }) => {
      if (!clientId || !live) return;
      return loadGis().then(() => {
        if (!live) return;
        window.google.accounts.id.initialize({ client_id: clientId, auto_select: false, cancel_on_tap_outside: true, context: 'signin', ux_mode: 'popup',
          callback: async ({ credential }) => { setState('working'); onError(''); try { onToken((await api.googleLogin({ credential })).token); } catch (e) { onError(e.message); setState('ready'); } } });
        window.google.accounts.id.renderButton(slot.current, { type: 'standard', theme: 'outline', size: 'large', text: 'continue_with', shape: 'rectangular', logo_alignment: 'left', width: 300 });
        setState('ready');
      }, () => live && setState('unavailable'));
    }).catch(() => {}); // server unreachable: the password form shows that error on submit
    return () => { live = false; };
  }, []);
  if (state === 'unavailable') return <p className="google-note">Google sign-in couldn’t load. Use your email and password.</p>;
  return <div className="google-signin" hidden={state === 'off'}><div className="or-divider"><span>or</span></div><div ref={slot} className="google-slot"/>{state === 'working' && <p className="busy-hint" role="status">Signing in with Google…</p>}</div>;
}

function ServerField() {
  const [value, setValue] = useState(getServer);
  return <details className="server-field" open={isNative && !value}><summary>Server address <small>{value || (isNative ? 'not set' : 'this website')}</small></summary><label className="field">Address<input type="url" inputMode="url" autoCapitalize="off" spellCheck="false" placeholder="https://….trycloudflare.com" value={value} onChange={e=>{setValue(e.target.value);setServer(e.target.value);}}/><small>Leave empty on the website. In the Android app, paste the backend's https tunnel address.</small></label></details>;
}

function Dashboard({ assessment, insights, scanProgress, openAssessment, isMock }) {
  const [list, setList] = useState(null); const [results, setResults] = useState([]);
  const loadList = () => { setList(null); api.assessments().then(setList).catch(() => setList('error')); };
  useEffect(() => { if (!isMock) loadList(); }, []);
  useEffect(() => { if (!isMock && assessment.id) api.results(assessment.id).then(setResults).catch(() => setResults([])); }, [assessment.id, assessment.status]);
  insights = insights || { papers: { verified: scanProgress.accepted, printed: scanProgress.total }, misconceptions: [], questions: [] };
  const metrics = [
    { label: 'Papers checked', value: insights.papers.verified, note: `of ${insights.papers.printed} distributed`, icon: 'book' },
    { label: 'Questions', value: assessment.questions.length, note: assessment.status==='draft'?'draft for review':'teacher approved', icon: 'check' },
    { label: 'Patterns to review', value: insights.misconceptions.length, note: 'possible misconceptions', icon: 'chart' },
  ];
  return <>
    <div className="welcome-band"><div className="welcome-copy"><span className="welcome-kicker"><span className="live-dot" /> YOUR CLASSROOM, IN FOCUS</span><h1>{isMock?'Good morning, Alex.':'Welcome to your workspace.'}</h1><p>See what your students may be thinking — and where to go next.</p><Link to="/assessment" className="button button-light"><Icon name="plus" size={17} /> Create an assessment <Icon name="arrow" size={17} /></Link></div><div className="welcome-art" aria-hidden="true"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="art-card card-back">⅓ + ⅓<div className="art-lines"/></div><div className="art-card card-front"><span>{isMock?'CLASS SIGNAL':'PAPER → INSIGHT'}</span><b>{isMock?'2/6':'MAP'}</b><i>{isMock?'3 students chose this':'Teacher-led learning'}</i></div><span className="art-spark spark-one"/><span className="art-spark spark-two"/></div></div>
    <div className="metric-grid">{metrics.map((m, i) => <Panel key={m.label} className="metric"><div className={`metric-icon tone-${i}`}><Icon name={m.icon} /></div><div><span className="metric-label">{m.label}</span><strong>{m.value}</strong><small>{m.note}</small></div><span className="metric-index">0{i + 1}</span></Panel>)}</div>
    <div className="dashboard-grid"><Panel className="workflow-panel" interactive><div className="section-heading"><div><span className="eyebrow">YOUR WORKFLOW</span><h2>{assessment.id ? assessment.title : 'Start your first assessment'}</h2><p>{assessment.id ? `Class 7A · ${assessment.topic || 'Lesson'} · Updated today` : 'Create a short check-in from the concepts you just taught.'}</p></div><span className={`status-pill ${assessment.status==='confirmed'?'status-complete':'status-draft'}`}><span/>{assessment.id ? (assessment.status==='confirmed'?'Results ready':assessment.status.replaceAll('_',' ')) : 'Not started'}</span></div>{assessment.id?<div className="stepper">{[{n:'01',label:'Create'},{n:'02',label:'Review'},{n:'03',label:'Print'},{n:'04',label:'Scan'},{n:'05',label:'Understand'}].map((s,i)=>{const stage={draft:1,approved:2,printed:3,scanning:4,confirmed:5}[assessment.status]||1;return <div key={s.label} className={`step ${i<stage?'done':''} ${i===stage?'current':''}`}><span className="step-node">{i<stage?<Icon name="check" size={14}/>:s.n}</span><div className="step-line"/><small>{s.label}</small></div>})}</div>:<Link to="/assessment" className="empty-dashboard-link">Build a check-in from today's lesson <Icon name="arrow" size={16}/></Link>}<div className="progress-footer"><div><span>Scans confirmed</span><strong>{scanProgress.accepted} <small>/ {scanProgress.total}</small></strong></div><div className="progress-track"><span style={{width:`${scanProgress.total ? scanProgress.accepted / scanProgress.total * 100 : 0}%`}}/></div><Link to="/insights" className="text-link">View class insights <Icon name="arrow" size={16}/></Link></div></Panel>
      {insights?.misconceptions?.length?<Panel className="signal-panel"><div className="section-heading"><div><span className="eyebrow">A PATTERN TO EXPLORE</span><h2>{insights.misconceptions[0].label}</h2></div><span className="signal-icon"><Icon name="arrow" size={16}/></span></div><div className="signal-quote"><span className="quote-mark">“</span><p>{assessment.questions.find(q=>q.id===insights.misconceptions[0].evidence[0]?.question_id)?.stem || 'A shared answer pattern appeared.'}</p><div className="answer-line"><span className="answer-chip">{assessment.questions.find(q=>q.id===insights.misconceptions[0].evidence[0]?.question_id)?.options?.[insights.misconceptions[0].evidence[0]?.option] || insights.misconceptions[0].evidence[0]?.option}</span><span className="answer-meter"><i style={{width:`${insights.papers.verified ? insights.misconceptions[0].students_affected/insights.papers.verified*100:0}%`}}/></span><b>{insights.misconceptions[0].students_affected} of {insights.papers.verified}</b></div></div><p className="signal-copy">{insights.misconceptions[0].why_we_think_so}</p><Link to="/insights" className="text-link">Explore the evidence <Icon name="arrow" size={16}/></Link></Panel>:<Panel className="signal-panel"><div className="section-heading"><div><span className="eyebrow">YOUR NEXT STEP</span><h2>See a clearer picture</h2></div><span className="signal-icon"><Icon name="chart" size={16}/></span></div><p className="signal-copy">Once papers are scanned and confirmed, MindTrace will show the response patterns and the evidence behind them here.</p><Link to="/scanner" className="text-link">Open classroom scanner <Icon name="arrow" size={16}/></Link></Panel>}</div>
    {!isMock&&<div className="dashboard-lists">
      <Panel className="list-panel"><div className="section-heading"><div><span className="eyebrow">YOUR ASSESSMENTS</span><h2>Past assessments</h2><p>Newest first. Tap one to open it.</p></div></div>
        {list===null?<p className="list-empty" role="status">Loading your assessments…</p>:list==='error'?<p className="list-empty" role="alert">Couldn’t load your assessments. <button className="text-button" onClick={loadList}>Try again</button></p>:list.length?<div className="assessment-list">{list.map(a=><button key={a.id} className={`assessment-row ${a.id===assessment.id?'open':''}`} onClick={()=>openAssessment(a.id,true)}><span><b>{a.title}</b><small>{a.topic} · {new Date(a.created_at).toLocaleDateString()}{a.parent_assessment_id?' · follow-up':''}</small></span><span className={`status-pill ${a.status==='confirmed'?'status-complete':'status-draft'}`}><span/>{statusLabel[a.status]||a.status}</span></button>)}</div>:<p className="list-empty">No assessments yet. <Link to="/assessment" className="text-link">Create one</Link></p>}
      </Panel>
      {assessment.id&&<Panel className="list-panel"><div className="section-heading"><div><span className="eyebrow">STUDENT SHEETS · TEACHER ONLY</span><h2>{assessment.title}</h2><p>One row per printed sheet.</p></div></div>
        {results.length?<table className="results-table"><thead><tr><th>Student</th><th>Sheet</th><th>Scan</th><th>Correct</th></tr></thead><tbody>{results.map(r=><tr key={r.short_code}><td>{r.student.display_name} <small>{r.student.student_code}</small></td><td>{r.short_code}</td><td>{r.scan_status.replace('_',' ')}</td><td>{r.scan_status==='missing'?'–':`${r.correct}/${r.total}`}</td></tr>)}</tbody></table>:<p className="list-empty">Sheets appear here after printing.</p>}
      </Panel>}
    </div>}
    <div className="bottom-callout"><div className="callout-icon"><Icon name="users" size={20}/></div><div><b>Built around your classroom</b><span>Paper-first assessments keep student devices out of the equation.</span></div><Link to="/student" className="text-link">Student view <Icon name="arrow" size={16}/></Link></div>
  </>;
}

// Where a question or activity came from: an AI draft, the teacher, or the labelled saved samples.
function SourceTag({ source }) { const label={ai:'AI draft',sample:'Saved sample',teacher:'Edited by you'}[source]; return label?<span className={`source-tag source-${source}`}>{label}</span>:null; }
const aiStatus = { gemini: 'Gemini drafts the questions. You check and approve each one.', 'app.ai': 'The AI module drafts the questions. You check and approve each one.', samples: 'Gemini isn’t set up yet, so you’ll get saved sample questions (clearly labelled).' };

function NewAssessment({ generate, busy, isMock }) {
  const [ai, setAi] = useState(null);
  useEffect(() => { if (!isMock) api.health().then(h => setAi(h.ai_provider)).catch(() => {}); }, []);
  const [topic, setTopic] = useState('Fractions'); const [concepts, setConcepts] = useState('Adding fractions with the same denominator\nUnderstanding numerators and denominators\nSimplifying fractions'); const [count, setCount] = useState('3'); const [error, setError] = useState('');
  function submit(e) { e.preventDefault(); if (!concepts.trim()) return setError('Add at least one concept taught in the lesson.'); setError(''); generate({ class_id: 'cl_7a', topic: topic.trim(), concepts_text: concepts.trim(), num_questions: Number(count) }); }
  return <><PageHeading eyebrow="ASSESSMENT BUILDER · 01 OF 04" title="Start with the lesson." description="Tell MindTrace what you covered. It will draft a short check for understanding." action={<span className="quiet-badge"><Icon name="clock" size={15}/> About 3 minutes</span>}/><div className="form-layout"><Panel className="form-panel"><div className="form-intro"><span className="step-bubble">01</span><div><h2>Lesson details</h2><p>Keep the assessment focused on what students have already seen.</p></div></div><form onSubmit={submit} noValidate><div className="field-row"><label className="field">Class<select defaultValue="cl_7a"><option value="cl_7a">Class 7A</option></select><small>5 fictional learners in this demo class</small></label><label className="field">Subject<input value="Mathematics" readOnly aria-label="Subject, Mathematics"/></label></div><label className="field">Topic<input value={topic} onChange={e=>setTopic(e.target.value)} required placeholder="e.g. Fractions"/></label><label className="field">Concepts taught<textarea value={concepts} onChange={e=>setConcepts(e.target.value)} rows="6" placeholder="Paste or type concepts from today's lesson" aria-describedby="concept-help" required/><small id="concept-help">One concept per line works well. Include the ideas you want to check.</small></label><div className="field-row bottom-fields"><label className="field">Number of questions<select value={count} onChange={e=>setCount(e.target.value)}>{[1,2,3,4,5].map(n=><option key={n}>{n}</option>)}</select></label><div className="field helper-field"><span>Question format</span><div className="format-choice"><span className="format-icon">A<span>·</span></span><div><b>Multiple choice</b><small>4 options per question</small></div><Icon name="check" size={17}/></div></div></div>{error&&<div className="field-error" role="alert">{error}</div>}<div className="form-footer"><span><Icon name="shield" size={15}/> {aiStatus[ai]||'You review and approve every question.'}</span><Button type="submit" disabled={busy} aria-busy={busy} icon="arrow">{busy?(ai==='gemini'?'Gemini is drafting…':'Drafting questions…'):'Generate questions'}</Button></div>{busy&&ai==='gemini'&&<p className="busy-hint" role="status">Usually 5–20 seconds. If Gemini is slow or busy, you’ll get labelled sample questions instead.</p>}</form></Panel><aside className="side-explainer"><div className="lesson-note"><div className="note-pin"/><span className="eyebrow">A BETTER KIND OF CHECK-IN</span><h3>Not just whether it’s right. What the answer might tell you.</h3><div className="note-example"><span>⅓ + ⅓</span><Icon name="arrow" size={16}/><b>2/6</b></div><p>A repeated answer can point to a shared way of thinking. MindTrace helps you notice the pattern, with evidence.</p></div><div className="small-trust"><span className="trust-check"><Icon name="check" size={14}/></span><span><b>Teacher stays in control</b><small>AI drafts. You decide what goes to class.</small></span></div><div className="small-trust"><span className="trust-check"><Icon name="check" size={14}/></span><span><b>Evidence before interpretation</b><small>Every pattern is shown with its supporting answers.</small></span></div></aside></div></>;
}

function ReviewQuestions({ assessment, setAssessment, approve, busy, generate }) {
  const [index, setIndex] = useState(0); const q = assessment.questions[index];
  function updateQuestion(patch) { const questions = assessment.questions.map((item,i)=>i===index?{...item,...patch}:item); setAssessment({...assessment,questions}); }
  if (!q) return <><PageHeading eyebrow="QUESTION REVIEW" title="Review your questions" description="Draft an assessment first to see questions here." action={<Link className="button primary" to="/assessment">Create assessment</Link>}/></>;
  return <><PageHeading eyebrow="ASSESSMENT BUILDER · 02 OF 04" title="Give each question a careful look." description="Check the wording, choices and correct answer before students see it." action={<span className="status-pill status-draft"><span/> {assessment.status==='draft'?'Draft · needs your review':statusLabel[assessment.status]}</span>}/>{assessment.notes?.length>0&&<div className="note-banner" role="status"><Icon name="clock" size={17}/><p>{assessment.notes.join(' ')}</p></div>}<div className="review-layout"><div className="review-main"><div className="question-tabs" role="tablist" aria-label="Questions">{assessment.questions.map((item,i)=><button role="tab" aria-selected={i===index} className={i===index?'selected':''} onClick={()=>setIndex(i)} key={item.id}><span>Q0{i+1}</span><small>{item.status==='approved'?'Ready':'Draft'}</small></button>)}</div><Panel className="question-editor"><div className="editor-top"><div><span className="eyebrow">QUESTION {String(index+1).padStart(2,'0')} <span className="dot-sep">·</span> {q.concept}</span><SourceTag source={q.source}/></div><label className="field stem-field"><span>Question</span><textarea value={q.stem} rows="2" onChange={e=>updateQuestion({stem:e.target.value})}/></label></div>{q.validation_errors?.length>0&&<div className="field-error" role="alert">{q.validation_errors.join(" ")}</div>}<div className="option-editor"><div className="option-heading"><b>Answer options</b><span>Choose the correct answer</span></div>{Object.entries(q.options).map(([key,value])=><div className={`option-row ${q.answer===key?'correct-option':''}`} key={key}><button aria-label={`Mark ${key} as correct`} className={`answer-radio ${q.answer===key?'checked':''}`} onClick={()=>updateQuestion({answer:key})}>{q.answer===key&&<span/>}</button><span className="option-key">{key}</span><input aria-label={`Option ${key}`} value={value} onChange={e=>updateQuestion({options:{...q.options,[key]:e.target.value}})}/>{q.answer===key&&<span className="correct-label"><Icon name="check" size={14}/> Correct</span>}</div>)}</div><div className="distractor-tags" aria-label="Possible misconception tags">{Object.entries(q.distractors || {}).map(([option, detail]) => <span className="distractor-tag" key={option}>Option {option} · Possible: {detail.misconception_id} — {detail.why}</span>)}</div><div className="question-explanation"><div className="explanation-title"><span className="explain-icon">i</span><b>Answer explanation</b><small>Shown after review</small></div><textarea aria-label="Answer explanation" value={q.explanation} rows="2" onChange={e=>updateQuestion({explanation:e.target.value})}/></div></Panel><div className="review-footer"><button className="text-button" disabled={index===0} onClick={()=>setIndex(index-1)}>← Previous question</button><span>{index+1} of {assessment.questions.length} questions</span><button className="text-button" disabled={index===assessment.questions.length-1} onClick={()=>setIndex(index+1)}>Next question →</button></div><div className="approve-footer"><div><b>Ready to approve?</b><span>You can print once all questions are approved.</span></div><Button disabled={busy} onClick={approve} icon="check">{busy?'Saving…':'Approve assessment'}</Button></div></div><aside className="review-aside"><Panel className="review-help"><span className="eyebrow">QUESTION QUALITY</span><h3>Make the thinking visible.</h3><p>Distractors can surface a possible misconception, but they never prove what a student was thinking.</p><div className="quality-item"><span className="quality-dot green"/><span><b>Clear and focused</b><small>One idea at a time</small></span></div><div className="quality-item"><span className="quality-dot amber"/><span><b>Useful distractors</b><small>Wrong options reflect common approaches</small></span></div><div className="review-tagline"><Icon name="shield" size={15}/> Reviewed by you, always</div></Panel>{assessment.status==='draft'&&<button className="regenerate-link" disabled={busy} onClick={()=>generate({class_id:assessment.class_id,topic:assessment.topic,concepts_text:assessment.concepts_text,num_questions:assessment.questions.length})}><Icon name="refresh" size={15} /> {busy?'Drafting…':'Draft new questions'}</button>}</aside></div></>;
}

function PrintPage({ assessment, printSheets, busy, isMock }) {
  const approved = assessment.status==='approved' || assessment.status==='printed' || assessment.status==='scanning' || assessment.status==='confirmed';
  return <><PageHeading eyebrow="ASSESSMENT BUILDER · 03 OF 04" title="Ready for paper." description="Each learner gets a personal sheet with a private QR code and room to show their thinking." action={<span className={`status-pill ${approved?'status-complete':'status-draft'}`}><span/>{approved?'Approved for print':'Approval required'}</span>}/><div className="print-layout"><div><Panel className="print-preview-panel"><div className="preview-toolbar"><span><Icon name="printer" size={16}/> A4 QUESTION SHEET</span><span>Portrait · 210 × 297 mm</span></div><div className="paper-preview"><div className="paper-brand"><span className="brand-mark small">m</span><span>MINDTRACE <small>CLASSROOM CHECK-IN</small></span><span className="paper-chip">{assessment.topic || 'Assessment'}</span></div><h2>{assessment.title || 'Assessment preview'}</h2><div className="paper-meta"><span>Class 7A · Mathematics</span><span>Name <i/></span></div><p className="paper-instruction">Choose one answer for each question. Show your thinking in the space provided.</p>{assessment.questions.slice(0,2).map((q,i)=><div key={q.id} className="paper-question"><b>{i+1}. {q.stem}</b><div className="paper-options">{Object.entries(q.options).map(([key,val])=><span key={key}><i/>{key}. {val}</span>)}</div><div className="reason-line">My thinking:<i/><i/></div></div>)}<div className="paper-footer"><span>Write clearly. One bubble per question.</span><div className="qr-placeholder" aria-label="QR code is generated by the backend when sheets are created">QR</div></div></div></Panel><div className="print-note"><Icon name="shield" size={16}/><span>QR codes contain a random sheet ID only. Student names stay outside the code.</span></div></div><Panel className="print-side"><span className="eyebrow">PRINT PREPARATION</span><h2>{isMock?'Five sample learners':'Your class roster'}</h2><p>{isMock?'This fictional roster illustrates how individual sheets are prepared.':'The backend creates a private sheet for each student in the selected class.'}</p>{isMock?<div className="roster-list">{demo.roster.map((name,i)=><div key={name}><span className="roster-avatar">{name[0]}</span><span>{name}</span><small>7A-0{i+1}</small></div>)}</div>:<div className="roster-list roster-message">Class roster is attached to the backend. The generated PDF will contain its individual student sheets.</div>}<div className="print-requirements"><b>Before you print</b><ul><li>Use A4 paper at 100% scale</li><li>Keep all four corner markers visible</li><li>Ask students to use a dark pen or pencil</li></ul></div><Button className="full-button" disabled={!approved||busy} onClick={printSheets} icon="printer">{busy?'Preparing sheets…':'Generate & open PDF'}</Button>{!approved&&<small className="disabled-hint">Approve the questions before printing.</small>}</Panel></div></>;
}

function Scanner({ assessment, upload, busy, scanProgress, isMock }) {
  const videoRef=useRef(null); const streamRef=useRef(null); const [cameraError,setCameraError]=useState(''); const [started,setStarted]=useState(false); const [capturing,setCapturing]=useState(false);
  const mounted = useRef(false);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      streamRef.current?.getTracks().forEach(track => track.stop());
    };
  }, []);
  useEffect(() => {
    if (started && videoRef.current) videoRef.current.srcObject = streamRef.current;
  }, [started]);
  async function startCamera() {
    setCameraError('');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false });
      if (!mounted.current || streamRef.current) {
        stream.getTracks().forEach(track => track.stop());
        return;
      }
      streamRef.current = stream;
      setStarted(true);
    } catch (error) {
      if (mounted.current) setCameraError(error.name === 'NotAllowedError' ? 'Camera access was blocked. Allow access in your browser settings, or upload a photo.' : 'No camera was found. Upload a photo of the sheet to continue.');
    }
  }
  function stopCamera() { streamRef.current?.getTracks().forEach(t=>t.stop()); streamRef.current=null; setStarted(false); }
  async function capture() { const v=videoRef.current; if(!v?.videoWidth) return; setCapturing(true); const c=document.createElement('canvas'); c.width=v.videoWidth; c.height=v.videoHeight; c.getContext('2d').drawImage(v,0,0); c.toBlob(async blob=>{ if(blob) await upload(new File([blob],`mindtrace-scan-${Date.now()}.jpg`,{type:'image/jpeg'})); setCapturing(false); },'image/jpeg',0.88); }
  return <><PageHeading eyebrow="CLASSROOM SCANNER" title="Bring the paper back to life." description="Scan one sheet at a time. Unclear marks stay in your review queue." action={<span className="status-pill status-draft"><span/> {assessment.title}</span>}/><div className="scan-stats"><div><span>Scanned</span><b>{scanProgress.accepted} <small>/ {scanProgress.total}</small></b></div><div><span>Needs review</span><b className="amber-text">{scanProgress.needs_review}</b></div><div><span>Remaining</span><b>{scanProgress.remaining}</b></div><Link to="/review-scans" className="text-link">Review queue <Icon name="arrow" size={16}/></Link></div><div className="scanner-layout"><Panel className="camera-panel"><div className="camera-head"><div><span className="eyebrow">LIVE CAPTURE</span><h2>{assessment.title||'No assessment open'}</h2></div><span className={`camera-state ${started?'camera-on':''}`}><i/>{started?'Camera ready':'Camera off'}</span></div><div className={`camera-view ${started?'has-camera':''}`}>{started?<video ref={videoRef} autoPlay playsInline muted aria-label="Live camera preview of assessment sheet"/>:<div className="camera-placeholder"><div className="camera-frame"><span/><span/><span/><span/><div className="camera-sheet"><div className="sheet-line long"/><div className="sheet-line"/><div className="bubble-row"><i/><i/><i/><i/></div><div className="sheet-line long"/><div className="sheet-line short"/></div></div><b>Position one sheet inside the frame</b><small>Keep the page flat, well lit and in focus.</small></div>}<div className="guide-frame" aria-hidden="true"><i/><i/><i/><i/></div></div>{cameraError&&<div className="field-error" role="alert">{cameraError}</div>}<div className="camera-actions">{!started?<Button icon="scan" onClick={startCamera}>Start camera</Button>:<><Button disabled={busy||capturing} icon="scan" onClick={capture}>{capturing?'Capturing…':'Capture sheet'}</Button><Button variant="outline" onClick={stopCamera}>Stop camera</Button></>}<label className="button outline upload-button">Upload image<input type="file" accept="image/*" capture="environment" disabled={busy} onChange={e=>upload(e.target.files?.[0])}/></label></div><p className="camera-hint">Camera works on localhost or HTTPS. Image processing requires the connected MindTrace API.</p></Panel><aside className="scanner-aside"><Panel className="scan-tip"><span className="eyebrow">GET A CLEAR SCAN</span><h3>A steady page is a good start.</h3><div className="tip-row"><span>01</span><p>Place the sheet on a flat, dark surface.</p></div><div className="tip-row"><span>02</span><p>Fit all four page corners inside the guide.</p></div><div className="tip-row"><span>03</span><p>Check for glare and keep the page well lit.</p></div><div className="scan-honesty"><Icon name="shield" size={16}/><p>Blurry or ambiguous answers go to review. MindTrace won't guess.</p></div></Panel><Panel className="recent-scans"><div className="recent-heading"><b>Recent scans</b><Link to="/review-scans">See queue</Link></div>{isMock?<div className="scan-empty"><span className="empty-ring"><Icon name="scan"/></span><b>Sample mode is on</b><p>Live scan totals appear when the API is connected.</p></div>:<div className="scan-empty"><span className="empty-ring"><Icon name="clock"/></span><b>Ready for the first paper</b><p>Scanned sheets will appear here.</p></div>}</Panel></aside></div></>;
}

function ReviewScans({ scanProgress, assessment, flash, reviewScan, confirmScans, busy, isMock }) {
  const waiting = (scanProgress.scans || []).filter(scan => ['needs_review', 'rejected'].includes(scan.status));
  const canConfirm = !isMock && scanProgress.needs_review === 0 && assessment.id;
  return <><PageHeading eyebrow="SCAN REVIEW" title="A careful look at the marks." description="Review uncertain answers before confirming the class results." action={<span className="status-pill status-draft"><span/>{scanProgress.needs_review} to review</span>}/>{waiting.length ? waiting.map(scan => <ScanReviewCard key={scan.scan_id} scan={scan} reviewScan={reviewScan} assessment={assessment}/>) : <Panel className="empty-review"><span className="empty-ring"><Icon name={isMock?'clock':'check'} size={22}/></span><h2>{isMock?'Sample mode has no live scans.':'No papers need a second look.'}</h2><p>{isMock?'Connect the MindTrace API to capture and review actual student sheets. The class insights shown in sample mode come from the labelled fixture.':'Unclear marks appear here with a crop and answer picker. Confirm results after you have reviewed each one.'}</p><Link className="button outline" to="/scanner">Back to scanner</Link></Panel>}<Panel className="review-policy"><Icon name="shield"/><span><b>Teacher confirmation matters</b><small>Blank, multiple or ambiguous marks stay out of insights until reviewed.</small></span><Button variant="outline" disabled={!canConfirm||busy} aria-busy={busy} onClick={()=>canConfirm?confirmScans():flash(isMock?'Sample mode does not submit or confirm fixture scans.':'Review all uncertain scans before confirming results.', 'info')}>{busy?'Confirming…':'Confirm results'}</Button></Panel></>;
}

function ScanReviewCard({ scan, reviewScan, assessment }) {
  const [answers,setAnswers]=useState(()=>Object.fromEntries(scan.answers.map(a=>[a.question_id,a.final||a.detected||'blank']))); const [saving,setSaving]=useState(false);
  const save=async()=>{setSaving(true);try{await reviewScan(scan.scan_id,scan.answers.map(a=>({question_id:a.question_id,final:answers[a.question_id]})));}finally{setSaving(false);}};
  return <Panel className="scan-review-card"><div className="scan-review-head"><div><span className="eyebrow">SHEET {scan.short_code || scan.sheet_id}</span><h2>{scan.student?.display_name || 'Student sheet'}</h2></div><span className={`status-pill ${scan.status==='rejected'?'status-draft':'status-fixture'}`}><span/>{scan.status.replace('_',' ')}</span></div>{scan.status==='rejected'?<><p className="scan-reject-reason">This sheet could not be read: {(scan.reject_reason||'please check the image and try again').replaceAll('_',' ')}.</p><Link to="/scanner" className="button outline">Rescan this paper</Link></>:<><div className="scan-answer-review">{scan.answers.map((a,i)=>{const q=assessment.questions.find(item=>item.id===a.question_id);return <div className="scan-answer-row" key={a.question_id}><div className="scan-crop">{a.crop_url?<img src={mediaUrl(a.crop_url)} alt={`Detected answer area for question ${i+1}`}/>:<span>Answer crop unavailable</span>}</div><div className="scan-answer-info"><b>Q{i+1}. {q?.stem||'Answer mark'}</b><span>{a.state==='single'?`Detected ${a.detected||'no answer'} · ${Math.round((a.confidence||0)*100)}% confidence`:`Mark needs a teacher decision · ${a.state}`}</span><label className="field">Confirmed answer<select value={answers[a.question_id]} onChange={e=>setAnswers({...answers,[a.question_id]:e.target.value})}>{['A','B','C','D','blank'].map(option=><option key={option} value={option}>{option==='blank'?'Blank':`${option} · ${q?.options?.[option]||''}`}</option>)}</select></label></div></div>})}</div><Button onClick={save} disabled={saving} aria-busy={saving} icon="check">{saving?'Saving…':'Save reviewed answers'}</Button></>}</Panel>;
}

function InsightsPage({ assessment, insights, loadInsights, busy, isMock }) {
  if (!insights) return <><PageHeading eyebrow="CLASS INSIGHTS" title="Your class patterns will appear here." description="Insights are available after the papers have been scanned and all uncertain marks confirmed."/><Panel className="empty-review"><span className="empty-ring"><Icon name="chart" size={21}/></span><h2>{assessment.id?'Waiting for confirmed results':'Create an assessment first'}</h2><p>{assessment.id?'Confirm the scans before MindTrace summarizes the class response patterns.':'Start from a lesson concept, approve the questions and print the assessment sheets.'}</p>{assessment.id?<Button onClick={loadInsights} disabled={busy}>{busy?'Loading results…':'Refresh insights'}</Button>:<Link to="/assessment" className="button primary">Create assessment</Link>}</Panel></>;
  return <><PageHeading eyebrow="CLASS INSIGHTS" title="What might the answers be saying?" description="Look at the response pattern, consider the evidence, then choose what to teach next." action={<span className={`status-pill ${insights.generated_by==='fixture'?'status-fixture':'status-complete'}`}><span/>{insights.generated_by==='fixture'?'Sample fixture':'Verified results'}</span>}/><div className="insights-banner"><Icon name="shield"/><p><b>Possible misconception, not a conclusion.</b> A selected option shows an answer pattern. It cannot tell us exactly what a student was thinking.</p><button onClick={loadInsights} disabled={busy}>{busy?'Refreshing…':'Refresh'}</button></div><div className="insight-summary"><Panel className="summary-card"><span className="eyebrow">PAPERS VERIFIED</span><strong>{insights.papers.verified}<small> / {insights.papers.printed}</small></strong><div className="mini-track"><i style={{width:`${insights.papers.printed?insights.papers.verified/insights.papers.printed*100:0}%`}}/></div><span>{insights.papers.needs_review} need review <span className="dot-sep">·</span> {insights.papers.missing} missing</span></Panel><Panel className="summary-card summary-score"><span className="eyebrow">CLASS CORRECT</span><strong>{insights.questions.length?Math.round(insights.questions.reduce((a,q)=>a+q.correct,0)/insights.questions.reduce((a,q)=>a+q.total,0)*100):0}<small>%</small></strong><span>Across {insights.questions.length} questions</span></Panel><Panel className="summary-card summary-pattern"><span className="eyebrow">PATTERNS TO EXPLORE</span><strong>{insights.misconceptions.length}<small> possible</small></strong><span>Teacher review recommended</span></Panel></div><div className="insight-columns"><div className="question-breakdown"><div className="section-heading compact"><div><span className="eyebrow">ANSWER DISTRIBUTION</span><h2>Question by question</h2></div></div>{insights.questions.map((q,i)=>{const question=assessment.questions.find(x=>x.id===q.question_id)||(isMock?demo.assessment.questions[i]:null); return <Panel className="breakdown-card" key={q.question_id}><div className="breakdown-head"><span className="question-number">Q{i+1}</span><b>{question?.stem||'Question response pattern'}</b><span className="correct-count">{q.correct}/{q.total} correct</span></div><div className="bar-chart" aria-label={`Answer distribution for question ${i+1}`}>{Object.entries(q.distribution).filter(([k])=>k!=='blank').map(([option,count])=><div className="bar-column" key={option}><span className="bar-value">{count}</span><div className={`bar ${question?.answer===option?'bar-correct':''} ${insights.misconceptions.some(m=>m.evidence.some(e=>e.question_id===q.question_id&&e.option===option))?'bar-pattern':''}`} style={{height:`${Math.max(5,count/q.total*100)}%`}}/><small>{option}{question?.answer===option?' · correct':''}</small></div>)}</div><p className="breakdown-caption">{q.total} student responses <span>·</span> {question?.concept||'Class response'}</p></Panel>; })}</div><aside className="misconception-column"><div className="section-heading compact"><div><span className="eyebrow">EVIDENCE-LED</span><h2>Possible misconceptions</h2></div></div>{insights.misconceptions.map(m=><Panel className="misconception-card" key={m.misconception_id}><div className="misconception-head"><span className="possible-badge">Possible</span><span className="affected">{m.students_affected} student{m.students_affected===1?'':'s'}</span></div><h3>{m.label}</h3><div className="evidence-box"><span className="eyebrow">SUPPORTING EVIDENCE</span><p>{m.why_we_think_so}</p><span className="evidence-count"><b>{m.evidence.reduce((n,e)=>n+e.count,0)} of {insights.papers.verified}</b> chose <strong>{m.evidence.map(e=>assessment.questions.find(q=>q.id===e.question_id)?.options?.[e.option]||e.option).join(', ')}</strong></span></div><p className="uncertainty"><Icon name="shield" size={15}/>{m.uncertainty}</p>{m.teaching_action?<><div className="activity-card"><span className="activity-mark">{m.teaching_action.minutes}<span>min</span></span><div><span className="eyebrow">TRY THIS NEXT</span><b>{m.teaching_action.title}</b><SourceTag source={m.teaching_action.source}/></div></div><ol className="activity-steps">{m.teaching_action.steps.map((s,i)=><li key={s}><span>{i+1}</span>{s}</li>)}</ol></>:<p className="uncertainty">No suggested activity for this pattern yet.</p>}{m.followup_question&&<div className="followup-preview"><span className="eyebrow">CHECK AGAIN</span><b>{m.followup_question.stem}</b><small>Follow-up question</small></div>}<Link to="/followup" className="button primary full-button">Create follow-up quiz <Icon name="arrow" size={16}/></Link></Panel>)}</aside></div><div className="caveats"><Icon name="shield" size={16}/><div><b>Read these results in context.</b><p>{insights.caveats.join(' ')}</p></div></div></>;
}

function Followup({ assessment, setAssessment, setInsights, setScanProgress, insights, navigate, flash, isMock }) {
  const misconception=insights?.misconceptions?.find(m=>m.teaching_action); const q=misconception?.followup_question;
  if(!misconception) return <><PageHeading eyebrow="TEACHING ACTION · RETEST" title="Retest after a teaching activity." description="Class insights need to be loaded before creating a follow-up quiz."/><Panel className="empty-review"><p>Confirm your scan results and open Class insights to see supported follow-up questions.</p><Link to="/insights" className="button outline">View class insights</Link></Panel></>;
  function create() { if(isMock) { const fixtureQuestion=demo.assessment.questions[0];setAssessment({...assessment,id:`as_followup_${Date.now()}`,title:'Fractions follow-up',status:'draft',parent_assessment_id:assessment.id,questions:[{...fixtureQuestion,id:`q_followup_${Date.now()}`,concept:'adding fractions with equal denominators',stem:q.stem||fixtureQuestion.stem,options:{A:'2/5',B:'3/10',C:'3/5',D:'2/10'},answer:'C',explanation:'Keep the denominator and add the numerators: 2/5 + 1/5 = 3/5.',status:'draft',source:'sample'}]});setInsights(null);setScanProgress({total:0,accepted:0,needs_review:0,remaining:0,scans:[]});flash('Sample follow-up draft created. Review it before printing.', 'success');navigate('/review');return; } api.followup(assessment.id,{misconception_ids:insights.misconceptions.map(m=>m.misconception_id)}).then(x=>{setAssessment(x);setInsights(null);navigate('/review');}).catch(e=>flash(e.message)); }
  return <><PageHeading eyebrow="TEACHING ACTION · RETEST" title="A quick check for what comes next." description="Use a follow-up question after a teaching activity to see what may have shifted."/><div className="followup-layout"><Panel className="followup-card"><div className="followup-top"><span className="activity-mark large">{misconception.teaching_action.minutes}<span>min</span></span><span className="possible-badge">Teacher-led activity</span></div><span className="eyebrow">{misconception.teaching_action.title}</span><h2>Try a short visual explanation.</h2><ol className="followup-steps">{misconception.teaching_action.steps.map((s,i)=><li key={s}><span>{String(i+1).padStart(2,'0')}</span>{s}</li>)}</ol><div className="followup-question"><span className="eyebrow">FOLLOW-UP QUESTION</span><b>{q?.stem || q}</b></div><Button onClick={create} icon="arrow">Create follow-up quiz</Button></Panel><aside className="followup-note"><div className="eyebrow">CLOSE THE LOOP</div><h3>Assessment → evidence → teaching → retest</h3><p>One small follow-up can help you notice whether the activity gave students a new way to see the idea.</p><div className="loop-steps">{['Notice a shared answer','Try a visual activity','Check understanding again'].map((s,i)=><span key={s}><i>{i+1}</i>{s}</span>)}</div></aside></div></>;
}

export default App;
