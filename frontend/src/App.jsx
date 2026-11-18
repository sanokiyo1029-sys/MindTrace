import { useEffect, useRef, useState } from 'react';
import { Link, Navigate, NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { api, demo, getServer, getStudentToken, printUrl, getTeacherId, getTeacherToken, isMock as fixtureMode, isNative, mediaUrl, onBusy, setOnAuthLost, setServer, setStudentToken, setTeacherId, setTeacherToken, store } from './api.js';
import { drop, entry, flush, keepMine, outbox, queue, retryBlocked, subscribe, summary } from './offline.js';
import { Button, PageHeading, Panel } from './ui.jsx';
import { ClassOverview, FeedbackPage, HistoryPage, PracticePanel, RecommendationsPage, StudentReportPage, SUBJECTS, subjectName, SyncBadge } from './TeacherAreas.jsx';
import Auth from './Auth.jsx';
import Landing, { SiteHeader, Wordmark } from './Landing.jsx';
import StudentHome from './StudentHome.jsx';
import AiPage, { copyImage } from './AiPage.jsx';
import PaperSurface from './PaperSurface.jsx';
import Icon from './Icon.jsx';

// The teacher's six areas. Question review, printing, scan review, feedback and student reports open from inside them.
const nav = [
  { to: '/workspace', label: 'Overview', icon: 'grid' }, { to: '/assessment', label: 'Create assessment', icon: 'plus' },
  { to: '/scanner', label: 'Scan papers', icon: 'scan' }, { to: '/insights', label: 'Class insights', icon: 'chart' },
  { to: '/recommendations', label: 'Teaching recommendations', icon: 'book' }, { to: '/history', label: 'History', icon: 'clock' },
  { to: '/ai', label: 'Gemini', icon: 'spark' },
];
// After signing in, go back to the page that asked for it (e.g. /ai). Same-site paths only.
const nextPath = () => { const n = new URLSearchParams(window.location.search).get('next') || ''; return /^\/(?!\/)[\w\-/]*$/.test(n) ? n : ''; };
const subPages = { '/review': 'Question review', '/print': 'Print sheets', '/review-scans': 'Scan review', '/followup': 'Follow-up', '/feedback': 'Student feedback' };

const emptyAssessment = { id: '', class_id: 'cl_7a', title: '', topic: '', concepts_text: '', status: 'draft', questions: [] };
const statusLabel = { draft: 'Draft', approved: 'Approved', printed: 'Printed', scanning: 'Scanning', confirmed: 'Results ready' };
const statusScreen = { draft: '/review', approved: '/print', printed: '/scanner', scanning: '/scanner', confirmed: '/insights' };

function App() {
  const [teacherToken, setTeacherTokenState] = useState(getTeacherToken);
  const [studentSession, setStudentSession] = useState(() => getStudentToken() ? { role: 'student', token: getStudentToken() } : null);
  const [authNote, setAuthNote] = useState('');
  const { pathname } = useLocation();
  // Keep sample deep links available while the public landing page starts signed out.
  const [sample, setSample] = useState(() => fixtureMode && !teacherToken && !studentSession
    && !['/', '/login', '/student'].includes(pathname));
  const navigate = useNavigate();

  useEffect(() => setOnAuthLost(() => { setTeacherTokenState(''); setAuthNote(summary().total ? 'Your session ended. Sign in again: your unsynced changes are kept on this device and will sync.' : 'Your session ended. Please sign in again.'); }), []);

  function startSession(session) {
    setAuthNote('');
    if (session.role === 'student') {
      setStudentToken(session.token);
      setStudentSession(session);
      navigate('/student', { replace: true });
      return;
    }
    setTeacherToken(session.token);
    if (session.teacher?.id) { setTeacherId(session.teacher.id); retryBlocked(); } // changes kept while signed out sync now
    else api.me().then(m => m.teacher && setTeacherId(m.teacher.id)).catch(() => {});
    setTeacherTokenState(session.token);
    setSample(false);
    navigate(nextPath() || '/workspace', { replace: true });
  }

  function signOutTeacher() {
    if (!sample) {
      api.logout().catch(() => {});
      window.google?.accounts?.id?.disableAutoSelect();
      // App: also forget the Google account choice, so the next Continue with Google shows the account picker
      if (isNative) import('@capgo/capacitor-social-login').then(({ SocialLogin }) => SocialLogin.logout({ provider: 'google' })).catch(() => {});
      setTeacherToken('');
      setTeacherTokenState('');
      store.set('mt_assessment', '');
      // unsynced changes stay saved for this teacher (scoped by id) until they sign in again
    }
    setSample(false);
    navigate('/login?role=teacher', { replace: true });
  }

  function signOutStudent(expired) {
    if (!expired) api.logout(studentSession.token).catch(() => {});
    setStudentToken('');
    setStudentSession(null);
    setAuthNote(expired ? 'Your session ended. Please sign in again.' : '');
    navigate('/login?role=student', { replace: true });
  }

  if (pathname === '/') {
    const home = sample || teacherToken ? '/workspace' : studentSession ? '/student' : undefined;
    return <ExperiencePage page="landing" home={home}><Landing home={home} /></ExperiencePage>;
  }
  if (pathname === '/login' || pathname === '/signup') {
    return <ExperiencePage page="login"><Auth
      signup={pathname === '/signup'} onSession={startSession} note={authNote}
      onSample={fixtureMode ? () => { setSample(true); navigate('/workspace'); } : undefined}
      serverField={isNative ? <ServerField /> : null}
      googleSignIn={({ role, signup, studentLink }) => <GoogleButton key={`${role}:${signup}`} role={role}
        studentLink={studentLink} onSession={startSession} />}
    /></ExperiencePage>;
  }
  if (pathname === '/student') {
    return studentSession
      ? <ExperiencePage page="student" onSignOut={() => signOutStudent(false)}><StudentHome token={studentSession.token} onExpired={() => signOutStudent(true)} /></ExperiencePage>
      : <Navigate to="/login?role=student" replace />;
  }
  if (!sample && !teacherToken) return <Navigate to={studentSession ? '/student' : `/login?role=teacher${pathname === '/workspace' ? '' : `&next=${encodeURIComponent(pathname)}`}`} replace />;
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
  const [pdf, setPdf] = useState(null);
  const [capabilities, setCapabilities] = useState(null);
  const location = useLocation();
  const navigate = useNavigate();
  const firstPage = useRef(true);
  const [classes, setClasses] = useState(() => isMock ? [{ id: 'cl_7a', name: '7A' }] : []);
  const [classesState, setClassesState] = useState(isMock ? 'ready' : 'loading');
  const [classId, setClassIdState] = useState(() => isMock ? 'cl_7a' : store.get('mt_class'));
  const [subject, setSubjectState] = useState(() => store.get('mt_subject') || 'mathematics');
  const setClassId = (id) => { setClassIdState(id); store.set('mt_class', id); };
  const setSubject = (s) => { setSubjectState(s); store.set('mt_subject', s); };
  function loadClasses() {
    setClassesState('loading');
    api.classes().then(rows => {
      setClasses(rows);
      if (!rows.some(row => row.id === store.get('mt_class'))) setClassId(rows[0]?.id || '');
      setClassesState('ready');
    }, () => setClassesState('error'));
  }
  useEffect(() => {
    if (isMock) return;
    loadClasses();
    const refreshAccess = () => api.me().then(me => {
      if (me.teacher?.id) setTeacherId(me.teacher.id);
      setCapabilities(me.capabilities || {});
    }, () => setCapabilities({}));
    refreshAccess();
    window.addEventListener('online', refreshAccess);
    return () => window.removeEventListener('online', refreshAccess);
  }, [isMock]);
  // A synced offline edit: pick up the new version so the next edit starts from it.
  function onSynced(e, result) {
    if (e.id.startsWith('question:')) setAssessment(a => ({ ...a, questions: a.questions.map(q => q.id === result.id ? { ...q, version: result.version, validation_errors: result.validation_errors } : q) }));
    if (e.id.startsWith('scan:') && store.get('mt_assessment')) api.scans(store.get('mt_assessment')).then(setScanProgress).catch(() => {});
  }
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
      const local = outbox();
      opened.questions = opened.questions.map(q => { const e = local.find(x => x.id === `question:${q.id}`); return e ? { ...q, ...e.body } : q; });
      setAssessment(opened); setInsights(null); setPdf(null);
      if (go) navigate(typeof go === 'string' ? go : statusScreen[opened.status] || '/workspace');
    } catch (error) { if (!go) store.set('mt_assessment', ''); flash(error.message); }
  }

  async function generate(values) {
    setBusy(true);
    try {
      const result = isMock ? { ...demo.assessment, id: `as_${Date.now()}`, title: `${values.topic} check`, topic: values.topic.toLowerCase(), class_id: values.class_id, concepts_text: values.concepts_text, status: 'draft', questions: [...demo.assessment.questions, ...demo.question_bank].slice(0, values.num_questions).map((q, i) => ({ ...q, id: `q_${Date.now()}_${i}`, status: 'draft', source: 'sample' })) } : await api.generate(values);
      setAssessment(result); setPdf(null); if (result.notes?.length) flash(result.notes.join(' '), 'info'); else flash(`${result.questions.length} questions drafted. Check each one before approving.`, 'success'); setInsights(null); setScanProgress({ total: 0, accepted: 0, needs_review: 0, remaining: 0, scans: [] }); navigate('/review');
    } catch (error) { flash(error.message); }
    finally { setBusy(false); }
  }

  async function approve() {
    if (!assessment?.questions?.length) return flash('Add at least one question before approval.');
    const invalid = assessment.questions.some(q => !q.stem?.trim() || q.type !== 'descriptive' && (Object.values(q.options || {}).some(v => !v?.trim()) || !q.answer || !['A', 'B', 'C', 'D'].includes(q.answer)));
    if (invalid) return flash('Each question needs a prompt; multiple-choice questions also need four options and a correct answer.');
    setBusy(true);
    try {
      if (isMock) { const updated = { ...assessment, status: 'approved', questions: assessment.questions.map(q => ({ ...q, status: 'approved' })) }; setAssessment(updated); navigate('/print'); }
      else {
        await flush(onSynced);
        const left = outbox().filter(e => assessment.questions.some(q => e.id === `question:${q.id}`));
        if (left.length) throw new Error(left.some(e => e.status === 'conflict') ? 'A question was changed somewhere else. Choose which version to keep, then approve.' : left.some(e => e.status === 'pending') ? 'You seem to be offline. Your edits are saved on this device; approve when you are back online.' : left[0].error || 'Some edits were not accepted. Check the questions.');
        const updated = await api.approve(assessment.id); setAssessment(updated); navigate('/print');
      }
    }
    catch (error) {
      if (error.validationErrors) setAssessment(current => ({ ...current, questions: current.questions.map(q => ({ ...q, validation_errors: error.validationErrors[q.id] || [] })) }));
      flash(error.message);
    }
    finally { setBusy(false); }
  }

  async function printSheets() {
    if (isMock) return flash('You are in the sample workspace (fixture data). Choose Exit sample and sign in as a teacher to print real question papers.', 'info');
    // In the Android app the PDF opens in the phone's browser (the WebView can't show PDFs); it signs in with ?token=.
    if (isNative) { window.location.href = printUrl(assessment.id); return; }
    setBusy(true);
    try {
      const blob = await api.printPdf(assessment.id);
      const pages = ((await blob.text()).match(/\/Type\s*\/Page[^s]/g) || []).length;
      if (pdf) URL.revokeObjectURL(pdf.url);
      const next = { url: URL.createObjectURL(blob), name: `MindTrace_${assessment.id}.pdf`, pages };
      setPdf(next);
      Object.assign(document.createElement('a'), { href: next.url, download: next.name }).click();
      setAssessment(await api.assessment(assessment.id));
      flash(`PDF downloaded: ${pages} page${pages === 1 ? '' : 's'}, one per student. Print at 100% on A4.`, 'success');
    } catch (error) { flash(error.offline ? 'Generating the PDF needs a connection to the MindTrace server.' : error.message); }
    finally { setBusy(false); }
  }

  async function upload(file, rollNumber) {
    if (!file) return null;
    if (isMock) { flash('Live scanning requires the MindTrace API. The sample insight below is labelled fixture data.', 'info'); return null; }
    if (!assessment.id) { flash('Open an assessment from the Overview before scanning.'); return null; }
    setBusy(true);
    try {
      const r = await api.uploadScan(assessment.id, file, rollNumber);
      const who = r.student ? `Roll ${r.student.roll_no} · ${r.student.display_name}` : r.roll_number?.read ? `Roll ${r.roll_number.read}` : 'This paper';
      if (r.status === 'duplicate') flash(`${who} already has a confirmed paper. Replace it from the review queue, or ignore this photo.`, 'info');
      else if (!r.student) flash(`${who}: ${(r.warnings.find(w => w.code.startsWith('roll_')) || { message: 'choose the student in the review queue.' }).message}`, 'info');
      else flash(`${who}${r.extracted_by === 'gemini' ? ' read by Gemini' : ''}. Check and confirm it in the review queue.`, 'success');
      setScanProgress(await api.scans(assessment.id));
      return r;
    }
    catch (error) { flash(error.message); return null; }
    finally { setBusy(false); }
  }

  async function loadInsights() {
    if (!assessment?.id) return flash('Create and confirm an assessment before loading insights.');
    if (isMock) return assessment.id===demo.assessment.id?setInsights(demo.insights):flash('No sample scan fixture is linked to this draft.', 'info');
    setBusy(true); try { const data = await api.insights(assessment.id); setInsights(data); } catch (error) { flash(error.message); } finally { setBusy(false); }
  }
  useEffect(() => { if (!isMock && teacherToken && assessment?.id && assessment.status === 'confirmed') loadInsights(); }, [assessment?.id, assessment?.status, teacherToken]);

  // body: {answers, student_id?, roll_number?, confirmed, replace?, discard?}. Returns the scan, or null on error.
  async function reviewScan(scanId, body, okMessage = 'Paper confirmed.', version) {
    const id = `scan:${scanId}`;
    try {
      const r = await api.reviewScan(scanId, version ? { ...body, base_version: entry(id)?.base_version ?? version } : body);
      drop(id); setScanProgress(await api.scans(assessment.id)); if (okMessage) flash(okMessage, 'success'); return r;
    } catch (error) {
      if (version && !body.discard && (error.offline || error.status === 401)) {
        queue({ id, label: 'Scan review', method: 'PATCH', path: `/scans/${scanId}/review`, body, baseVersion: version });
        flash(error.offline ? 'You are offline. This review is saved on this device and will sync when you reconnect.' : 'Saved on this device. Sign in again to sync it.', 'info');
        return null;
      }
      if (error.code === 'conflict') api.scans(assessment.id).then(setScanProgress).catch(() => {});
      flash(error.message); return null;
    }
  }
  async function confirmScans() {
    setBusy(true);
    try { setAssessment(await api.confirm(assessment.id)); flash('Results confirmed. Class insights are ready.', 'success'); navigate('/insights'); }
    catch (error) { flash(error.message); }
    finally { setBusy(false); }
  }

  const sampleTag = isMock && <span className="mode-tag" title="Uses labelled fixture data"><span className="mode-dot" /> Mock mode · sample data, not live</span>;
  const context = { classes, classesState, loadClasses, classId, setClassId, subject, setSubject, onSynced, pdf, assessment, setAssessment, insights, setInsights, scanProgress, setScanProgress, openAssessment, busy, generate, approve, printSheets, upload, loadInsights, reviewScan, confirmScans, flash, navigate, isMock };

  const visibleNav = nav;
  const mobileNav = visibleNav.filter(n => n.to !== '/history'); // History is linked from the Overview on phones
  return <div className="shell workspace-shell">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <div className={`busy-bar ${loading ? 'on' : ''}`} aria-hidden="true" />
    <aside className="sidebar">
      <Link to="/" className="brand" aria-label="MindTrace home"><Wordmark /><span className="brand-mini" aria-hidden="true">M</span></Link>
      <div className="school-label">WORKSPACE</div>
      <nav aria-label="Main navigation" className="side-nav">{visibleNav.map(item => <NavLink key={item.to} to={item.to} end={item.to === '/workspace'} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}><Icon name={item.icon} /><span>{item.label}</span>{item.to === '/assessment' && assessment.id && assessment.status === 'draft' && <i className="nav-pip" />}</NavLink>)}</nav>
      <div className="sidebar-spacer" />
      <div className="privacy-note"><span className="privacy-icon"><Icon name="shield" size={17} /></span><div><strong>Teacher-led insights</strong><p>Patterns are evidence for review, never a diagnosis.</p></div></div>
      <button className="profile-button" onClick={() => navigate('/workspace')}><span className="avatar">{isMock?'AS':'T'}</span><span><b>{isMock?'Alex Morgan':'Teacher'}</b><small>{isMock?'Mathematics teacher':'Connected account'}</small></span><span className="profile-more">···</span></button>
    </aside>
    <div className="main-area">
      <header className="topbar"><button className="mobile-brand" onClick={() => navigate('/')} aria-label="MindTrace home"><Wordmark /></button><div className="crumb"><span>Workspace</span><b>/</b><strong>{visibleNav.find(n => n.to === location.pathname)?.label || subPages[location.pathname] || (location.pathname.startsWith('/students/') ? 'Student report' : 'Overview')}</strong></div><div className="top-actions">{sampleTag}{!isMock && <SyncBadge onSynced={onSynced} />}<span className="teacher-chip"><span className="avatar mini">{isMock?'AM':'T'}</span><span>{isMock?'Alex Morgan':'Teacher'}</span></span><button className="text-button" onClick={onSignOut}>{isMock ? 'Exit sample' : 'Sign out'}</button></div></header>
      <main id="main-content" tabIndex="-1" className="content" aria-busy={loading}><div key={location.pathname} className="page-enter"><Routes>
        <Route path="/workspace" element={<Dashboard {...context} />} />
        <Route path="/assessment" element={<NewAssessment {...context} />} />
        <Route path="/review" element={<ReviewQuestions {...context} />} />
        <Route path="/print" element={<PrintPage {...context} />} />
        <Route path="/scanner" element={<Scanner {...context} />} />
        <Route path="/review-scans" element={<ReviewScans {...context} />} />
        <Route path="/insights" element={<InsightsPage {...context} />} />
        <Route path="/followup" element={<Followup {...context} />} />
        <Route path="/recommendations" element={<RecommendationsPage {...context} />} />
        <Route path="/feedback" element={<FeedbackPage {...context} />} />
        <Route path="/history" element={<HistoryPage {...context} />} />
        <Route path="/ai" element={capabilities === null && !isMock ? <p role="status">Checking your account…</p>
          : <AiPage account={capabilities?.gemini_account} flash={flash} onSignOut={onSignOut} />} />
        <Route path="/students/:id" element={<StudentReportPage />} />
        <Route path="*" element={<Navigate to="/workspace" replace />} />
      </Routes></div></main>
    </div>
    <nav className="mobile-nav" aria-label="Mobile navigation">{mobileNav.map(item => <NavLink key={item.to} to={item.to} end={item.to === '/workspace'} aria-label={item.label} className={({ isActive }) => isActive ? 'mobile-active' : ''}><Icon name={item.icon} size={21} /><span>{{ 'Create assessment': 'Create', 'Teaching recommendations': 'Teach', 'Class insights': 'Insights', 'Scan papers': 'Scan', 'AI assistant': 'AI' }[item.label] || item.label}</span></NavLink>)}</nav>
    {toast && <div key={toast.id} className={`toast toast-${toast.type}`} role={toast.type === 'error' ? 'alert' : 'status'}><span className="toast-badge" aria-hidden="true">{toast.type === 'success' ? <Icon name="check" size={15} /> : toast.type === 'error' ? '!' : 'i'}</span><span className="toast-text">{toast.message}</span><button aria-label="Dismiss notification" onClick={() => setToast(null)}><Icon name="close" size={16} /></button>{toast.type === 'success' && <i className="wedges" aria-hidden="true"><i /></i>}</div>}
  </div>;
}


// "Continue with Google". The server supplies the web client ID and checks every token. Website: Google Identity
// Services popup. Android app: Google blocks its web
// sign-in inside app web views, so the app uses the native account picker (Credential Manager via
// @capgo/capacitor-social-login); its ID token is issued for the same web client ID and goes to the same /auth/google.
const CANCELED = 'Google sign-in was canceled. Choose Continue with Google to try again.';
let gisScript;
const loadGis = () => gisScript ||= new Promise((resolve, reject) => {
  const s = Object.assign(document.createElement('script'), { src: 'https://accounts.google.com/gsi/client', async: true });
  s.onload = resolve; s.onerror = () => { gisScript = null; reject(new Error('Google sign-in could not load.')); };
  document.head.append(s);
});
function GoogleButton({ role, studentLink, onSession }) {
  const slot = useRef(null);
  const active = useRef(false);
  const working = useRef(false);
  const [state, setState] = useState('checking');
  const [clientId, setClientId] = useState(null);
  const [error, setError] = useState('');
  const link = useRef(studentLink);
  link.current = studentLink;
  const clickedAt = useRef(0);
  async function finish(credential) {
    if (!active.current || working.current) return;
    if (link.current && (!link.current.student_code || !link.current.pin)) return;
    working.current = true;
    clickedAt.current = 0; setState('working'); setError('');
    try {
      const r = await api.googleLogin({ credential, role, allow_signup: role === 'teacher', student_link: link.current });
      if (!r.token || !r[role]) throw new Error('This MindTrace server does not support Google sign-in for this role yet.');
      if (active.current) onSession({ ...r, role });
    } catch (e) {
      if (active.current) { setError(e.message); setState('ready'); }
    } finally { working.current = false; }
  }
  useEffect(() => {
    let live = true;
    active.current = true;
    const load = () => api.authConfig().then(({ google_client_id: id }) => {
      if (!live) return;
      if (!id) { setState('off'); return; }
      setClientId(id);
      if (isNative) { setState('ready'); return; }
      return loadGis().then(() => {
        if (!live || !slot.current) return;
        window.google.accounts.id.initialize({ client_id: id, auto_select: false, cancel_on_tap_outside: true, context: 'signin', ux_mode: 'popup',
          callback: ({ credential }) => { if (live) finish(credential); } });
        const width = Math.min(300, slot.current.parentElement.clientWidth);
        slot.current.replaceChildren();
        window.google.accounts.id.renderButton(slot.current, { type: 'standard', theme: 'filled_black', size: 'large', text: 'continue_with', shape: 'rectangular', logo_alignment: 'left', width,
          click_listener: () => { clickedAt.current = Date.now(); setError(''); } });
        setState('ready');
      }, () => live && setState('unavailable'));
    }).catch(() => { if (live) setState('disconnected'); });
    load();
    // Google gives no "popup closed" callback. If the page gets focus back after a click and no credential follows,
    // the user closed the window or cancelled.
    const onFocus = () => { const at = clickedAt.current; if (at && Date.now() - at > 800) setTimeout(() => { if (live && clickedAt.current === at) { clickedAt.current = 0; setError(CANCELED); } }, 1500); };
    addEventListener('focus', onFocus); addEventListener('mt-server', load); // the app's server address was just set
    return () => { live = false; active.current = false; removeEventListener('focus', onFocus); removeEventListener('mt-server', load); };
  }, []);
  async function nativeSignIn() {
    setState('working'); setError('');
    try {
      const { SocialLogin } = await import('@capgo/capacitor-social-login');
      await SocialLogin.initialize({ google: { webClientId: clientId } });
      const { result } = await SocialLogin.login({ provider: 'google', options: { scopes: ['profile', 'email'] } });
      if (!result?.idToken) throw new Error('Google didn’t return a sign-in token. Try again.');
      await finish(result.idToken);
    } catch (e) { if (active.current) { setError(e?.code === 'USER_CANCELLED' ? CANCELED : `Google sign-in didn’t finish: ${e?.message || 'unknown error'}`); setState('ready'); } }
  }
  const ready = (state === 'ready' || state === 'working') && (!studentLink || !!(studentLink.student_code && studentLink.pin));
  return <div className="google-signin"><div className="or-divider"><span>or</span></div>
    {(!ready || isNative) && <button type="button" className="google-provider" disabled={!ready || state === 'working'}
      onClick={isNative ? nativeSignIn : undefined}><GoogleMark /> Continue with Google</button>}
    {!isNative && <div ref={slot} className="google-slot" hidden={!ready} aria-busy={state === 'working'} />}
    {state === 'off' && <p className="google-note" role="status">Google sign-in is not configured on this server.</p>}
    {state === 'disconnected' && <p className="google-note" role="status">Google sign-in needs a connected MindTrace server.</p>}
    {state === 'unavailable' && <p className="google-note" role="status">Google sign-in couldn’t load. Try refreshing the page.</p>}
    {state === 'working' && <p className="busy-hint" role="status">Signing in with Google…</p>}
    {error && <p className="field-error" role="alert">{error}</p>}</div>;
}
// Google's multicolour "G" (brand mark required next to the button text).
const GoogleMark = () => <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true"><path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.6 5.4 2.7 13.3l7.9 6.1C12.5 13.6 17.8 9.5 24 9.5z"/><path fill="#4285F4" d="M46.1 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.4c-.5 2.9-2.2 5.3-4.6 6.9l7.4 5.7c4.3-4 6.9-9.9 6.9-17.1z"/><path fill="#FBBC05" d="M10.6 28.6c-.5-1.4-.8-3-.8-4.6s.3-3.2.8-4.6l-7.9-6.1C1 16.6 0 20.2 0 24s1 7.4 2.7 10.7l7.9-6.1z"/><path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.4-5.7c-2.1 1.4-4.8 2.3-8.5 2.3-6.2 0-11.5-4.1-13.4-9.9l-7.9 6.1C6.6 42.6 14.6 48 24 48z"/></svg>;

function ServerField() {
  const [value, setValue] = useState(getServer);
  return <details className="server-field" open={isNative && !value}><summary>Server address <small>{value || (isNative ? 'not set' : 'this website')}</small></summary><label className="field">Address<input type="url" inputMode="url" autoCapitalize="off" spellCheck="false" placeholder="https://….trycloudflare.com" value={value} onChange={e=>{setValue(e.target.value);setServer(e.target.value);}}/><small>Leave empty on the website. In the Android app, paste the backend's https tunnel address.</small></label></details>;
}

// A new teacher (email or Google sign-up) starts with no classes: set up the first one here.
function FirstClass({ onCreated }) {
  const [name, setName] = useState(''); const [grade, setGrade] = useState(''); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault();
    if (busy) return;
    if (!name.trim()) return setError('Enter a class name, e.g. 7B.');
    setBusy(true); setError('');
    try { const c = await api.createClass({ name: name.trim(), grade: grade.trim() }); onCreated(c.id); }
    catch (err) { setError(err.message); setBusy(false); }
  }
  return <form className="first-class" onSubmit={submit} noValidate>
    <span className="eyebrow">SET UP YOUR WORKSPACE</span>
    <h2>Create your first class</h2>
    <p>Add a class you teach. You can add more classes later.</p>
    <div className="field-row">
      <label className="field">Class name<input value={name} onChange={e => setName(e.target.value)} maxLength={40} placeholder="e.g. 7B" required /></label>
      <label className="field">Grade (optional)<input value={grade} onChange={e => setGrade(e.target.value)} maxLength={20} placeholder="e.g. 7" /></label>
    </div>
    {error && <p className="field-error" role="alert">{error}</p>}
    <Button type="submit" disabled={busy} icon="plus">{busy ? 'Creating…' : 'Create class'}</Button>
  </form>;
}

function Dashboard({ assessment, insights, scanProgress, openAssessment, isMock, classes, classesState, loadClasses, classId, setClassId, subject, setSubject }) {
  const [list, setList] = useState(null); const [results, setResults] = useState([]);
  const shown = Array.isArray(list) ? list.filter(a => a.class_id === classId && (a.subject || 'mathematics') === subject) : [];
  const loadList = () => { setList(null); api.assessments().then(setList).catch(() => setList('error')); };
  useEffect(() => { if (!isMock) loadList(); }, []);
  useEffect(() => { if (!isMock && assessment.id) api.results(assessment.id).then(setResults).catch(() => setResults([])); }, [assessment.id, assessment.status]);
  insights = insights || { papers: { verified: scanProgress.accepted, printed: scanProgress.total }, misconceptions: [], questions: [] };
  return <>
    <div className="welcome-band"><div className="welcome-copy"><span className="welcome-kicker"><span className="live-dot" /> YOUR CLASSROOM, IN FOCUS</span><h1>{isMock?'Good morning, Alex.':'Welcome to your workspace.'}</h1><p>See what your students may be thinking — and where to go next.</p><Link to="/assessment" className="button button-light"><Icon name="plus" size={17} /> Create an assessment <Icon name="arrow" size={17} /></Link></div><div className="welcome-art" aria-hidden="true"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="art-card card-back">⅓ + ⅓<div className="art-lines"/></div><div className="art-card card-front"><span>{isMock?'CLASS SIGNAL':'PAPER → INSIGHT'}</span><b>{isMock?'2/6':'MAP'}</b><i>{isMock?'3 students chose this':'Teacher-led learning'}</i></div><span className="art-spark spark-one"/><span className="art-spark spark-two"/></div></div>
    {classesState === 'ready' && classId ? <ClassOverview key={`${classId}:${subject}`} classes={classes} classId={classId} subject={subject}
      setClassId={setClassId} setSubject={setSubject} isMock={isMock} openAssessment={openAssessment} />
      : <Panel className="class-overview">{classesState === 'error'
        ? <p className="list-empty" role="alert">Couldn’t load your classes. <button className="text-button" onClick={loadClasses}>Try again</button></p>
        : classesState === 'loading' ? <p className="list-empty" role="status">Loading your classes…</p>
          : <FirstClass onCreated={id => { setClassId(id); loadClasses(); }} />}
      </Panel>}
    <div className="dashboard-grid"><Panel className="workflow-panel" interactive><div className="section-heading"><div><span className="eyebrow">YOUR WORKFLOW</span><h2>{assessment.id ? assessment.title : 'Start your first assessment'}</h2><p>{assessment.id ? `Class ${classes.find(c => c.id === assessment.class_id)?.name || ''} · ${subjectName(assessment.subject)} · ${assessment.topic || 'Lesson'}` : 'Create a short check-in from the concepts you just taught.'}</p></div><span className={`status-pill ${assessment.status==='confirmed'?'status-complete':'status-draft'}`}><span/>{assessment.id ? (assessment.status==='confirmed'?'Results ready':assessment.status.replaceAll('_',' ')) : 'Not started'}</span></div>{assessment.id?<div className="stepper">{[{n:'01',label:'Create'},{n:'02',label:'Review'},{n:'03',label:'Print'},{n:'04',label:'Scan'},{n:'05',label:'Understand'}].map((s,i)=>{const stage={draft:1,approved:2,printed:3,scanning:4,confirmed:5}[assessment.status]||1;return <div key={s.label} className={`step ${i<stage?'done':''} ${i===stage?'current':''}`}><span className="step-node">{i<stage?<Icon name="check" size={14}/>:s.n}</span><div className="step-line"/><small>{s.label}</small></div>})}</div>:<Link to="/assessment" className="empty-dashboard-link">Build a check-in from today's lesson <Icon name="arrow" size={16}/></Link>}<div className="progress-footer"><div><span>Scans confirmed</span><strong>{scanProgress.accepted} <small>/ {scanProgress.total}</small></strong></div><div className="progress-track"><span style={{width:`${scanProgress.total ? scanProgress.accepted / scanProgress.total * 100 : 0}%`}}/></div><Link to="/insights" className="text-link">View class insights <Icon name="arrow" size={16}/></Link></div></Panel>
      {insights?.misconceptions?.length?<Panel className="signal-panel"><div className="section-heading"><div><span className="eyebrow">A PATTERN TO EXPLORE</span><h2>{insights.misconceptions[0].label}</h2></div><span className="signal-icon"><Icon name="arrow" size={16}/></span></div><div className="signal-quote"><span className="quote-mark">“</span><p>{assessment.questions.find(q=>q.id===insights.misconceptions[0].evidence[0]?.question_id)?.stem || 'A shared answer pattern appeared.'}</p><div className="answer-line"><span className="answer-chip">{assessment.questions.find(q=>q.id===insights.misconceptions[0].evidence[0]?.question_id)?.options?.[insights.misconceptions[0].evidence[0]?.option] || insights.misconceptions[0].evidence[0]?.option}</span><span className="answer-meter"><i style={{width:`${insights.papers.verified ? insights.misconceptions[0].students_affected/insights.papers.verified*100:0}%`}}/></span><b>{insights.misconceptions[0].students_affected} of {insights.papers.verified}</b></div></div><p className="signal-copy">{insights.misconceptions[0].why_we_think_so}</p><Link to="/insights" className="text-link">Explore the evidence <Icon name="arrow" size={16}/></Link></Panel>:<Panel className="signal-panel"><div className="section-heading"><div><span className="eyebrow">YOUR NEXT STEP</span><h2>See a clearer picture</h2></div><span className="signal-icon"><Icon name="chart" size={16}/></span></div><p className="signal-copy">Once papers are scanned and confirmed, MindTrace will show the response patterns and the evidence behind them here.</p><Link to="/scanner" className="text-link">Open classroom scanner <Icon name="arrow" size={16}/></Link></Panel>}</div>
    {!isMock&&<div className="dashboard-lists">
      <Panel className="list-panel"><div className="section-heading"><div><span className="eyebrow">YOUR ASSESSMENTS</span><h2>Past assessments</h2><p>Class {classes.find(c => c.id === classId)?.name} · {subjectName(subject)}. Newest first. Tap one to open it.</p></div></div>
        {list===null?<p className="list-empty" role="status">Loading your assessments…</p>:list==='error'?<p className="list-empty" role="alert">Couldn’t load your assessments. <button className="text-button" onClick={loadList}>Try again</button></p>:shown.length?<div className="assessment-list">{shown.map(a=><button key={a.id} className={`assessment-row ${a.id===assessment.id?'open':''}`} onClick={()=>openAssessment(a.id,true)}><span><b>{a.title}</b><small>{a.topic} · {new Date(a.created_at).toLocaleDateString()}{a.parent_assessment_id?' · follow-up':''}</small></span><span className={`status-pill ${a.status==='confirmed'?'status-complete':'status-draft'}`}><span/>{statusLabel[a.status]||a.status}</span></button>)}</div>:<p className="list-empty">No assessments yet. <Link to="/assessment" className="text-link">Create one</Link></p>}
      </Panel>
      {assessment.id&&<Panel className="list-panel"><div className="section-heading"><div><span className="eyebrow">STUDENT SHEETS · TEACHER ONLY</span><h2>{assessment.title}</h2><p>One row per printed sheet.</p></div></div>
        {results.length?<table className="results-table"><thead><tr><th>Roll</th><th>Student</th><th>Scan</th><th>Correct</th></tr></thead><tbody>{results.map(r=><tr key={r.short_code}><td>{r.roll_no||'–'}</td><td><Link to={`/students/${r.student.id}`} className="text-link">{r.student.display_name}</Link> <small>{r.student.student_code}</small></td><td>{r.scan_status.replace('_',' ')}</td><td>{r.scan_status==='missing'?'–':`${r.correct}/${r.total}`}</td></tr>)}</tbody></table>:<p className="list-empty">Sheets appear here after printing.</p>}
      </Panel>}
    </div>}
    <div className="bottom-callout"><div className="callout-icon"><Icon name="users" size={20}/></div><div><b>Built around your classroom</b><span>Paper-first assessments keep student devices out of the equation.</span></div><Link to="/history" className="text-link">History <Icon name="arrow" size={16}/></Link></div>
  </>;
}

// Where a question or activity came from: an AI draft, the teacher, or the labelled saved samples.
function SourceTag({ source }) { const label={ai:'AI draft',sample:'Saved sample',teacher:'Edited by you'}[source]; return label?<span className={`source-tag source-${source}`}>{label}</span>:null; }
const aiStatus = { gemini: 'Gemini drafts the questions. You check and approve each one.', 'app.ai': 'The AI module drafts the questions. You check and approve each one.', samples: 'Gemini isn’t set up yet, so you’ll get saved sample questions (clearly labelled).' };

const topicFor = { mathematics: 'Fractions', physics: 'Forces and units', chemistry: 'Stoichiometry', biology: 'Inheritance', engineering: 'Design trade-offs', technology: 'Algorithms' };
function NewAssessment({ generate, busy, isMock, classes, classId, setClassId, subject, setSubject }) {
  const [ai, setAi] = useState(null);
  useEffect(() => { if (!isMock) api.health().then(h => setAi(h.ai_provider)).catch(() => {}); }, []);
  const [topic, setTopic] = useState(topicFor[subject] || 'Fractions'); const [concepts, setConcepts] = useState(subject === 'mathematics' ? 'Adding fractions with the same denominator\nUnderstanding numerators and denominators\nSimplifying fractions' : ''); const [count, setCount] = useState('3'); const [written, setWritten] = useState('0'); const [difficulty, setDifficulty] = useState(''); const [error, setError] = useState('');
  function pickSubject(s) { setSubject(s); setTopic(topicFor[s]); }
  function submit(e) { e.preventDefault(); if (!classId) return setError('Choose a class first.'); if (!concepts.trim()) return setError('Paste at least one concept taught in the lesson.'); setError(''); generate({ class_id: classId, subject, topic: topic.trim() || topicFor[subject], concepts_text: concepts.trim(), num_questions: Number(count), num_descriptive: Math.min(Number(written), Number(count)), ...(difficulty && { difficulty }) }); }
  return <><PageHeading eyebrow="CREATE ASSESSMENT · 01 OF 03" title="Start with the lesson." description="Paste what you covered. MindTrace drafts a short check; you edit and approve every question, then print." action={<span className="quiet-badge"><Icon name="clock" size={15}/> About 3 minutes</span>}/><div className="form-layout"><Panel className="form-panel"><div className="form-intro"><span className="step-bubble">01</span><div><h2>Lesson details</h2><p>Keep the assessment focused on what students have already seen.</p></div></div><form onSubmit={submit} noValidate>
    <div className="field-row"><label className="field">Class<select value={classId} onChange={e=>setClassId(e.target.value)}>{classes.map(c=><option key={c.id} value={c.id}>Class {c.name}</option>)}</select><small>Fictional learners only</small></label><label className="field">Subject<select value={subject} onChange={e=>pickSubject(e.target.value)}>{SUBJECTS.map(([k,v])=><option key={k} value={k}>{v}</option>)}</select></label></div>
    <label className="field">Topic<input value={topic} onChange={e=>setTopic(e.target.value)} required placeholder={`e.g. ${topicFor[subject]}`}/></label>
    <label className="field">Concepts taught<textarea value={concepts} onChange={e=>setConcepts(e.target.value)} rows="6" placeholder="Paste or type concepts from today's lesson" aria-describedby="concept-help" required/><small id="concept-help">One concept per line works well. Include the ideas you want to check.</small></label>
    <div className="field-row bottom-fields"><label className="field">Number of questions<select value={count} onChange={e=>setCount(e.target.value)}>{[1,2,3,4,5].map(n=><option key={n}>{n}</option>)}</select><small>One A4 page holds up to 5.</small></label><label className="field">Written-answer questions<select value={written} onChange={e=>setWritten(e.target.value)}>{[0,1,2].map(n=><option key={n} value={n}>{n===0?'None (all multiple choice)':`${n} of them`}</option>)}</select><small>Students write a few sentences by hand.</small></label></div>
    <label className="field">Difficulty<select value={difficulty} onChange={e=>setDifficulty(e.target.value)}><option value="">Mixed (easiest first)</option><option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option></select></label>
    {error&&<div className="field-error" role="alert">{error}</div>}<div className="form-footer"><span><Icon name="shield" size={15}/> {aiStatus[ai]||'You review and approve every question.'} Drafting needs internet when AI is on.</span><Button type="submit" disabled={busy} aria-busy={busy} icon="arrow">{busy?(ai==='gemini'?'Gemini is drafting…':'Drafting questions…'):'Generate questions'}</Button></div>{busy&&ai==='gemini'&&<p className="busy-hint" role="status">Usually 5–20 seconds. If Gemini is slow or busy, you’ll get labelled sample questions instead.</p>}</form></Panel>
    <aside className="side-explainer"><div className="lesson-note"><div className="note-pin"/><span className="eyebrow">A BETTER KIND OF CHECK-IN</span><h3>Not just whether it’s right. What the answer might tell you.</h3><div className="note-example"><span>⅓ + ⅓</span><Icon name="arrow" size={16}/><b>2/6</b></div><p>A repeated answer can point to a shared way of thinking. Written answers show the reasoning itself; you read them before any feedback reaches a student.</p></div><div className="small-trust"><span className="trust-check"><Icon name="check" size={14}/></span><span><b>Teacher stays in control</b><small>AI drafts. You decide what goes to class.</small></span></div><div className="small-trust"><span className="trust-check"><Icon name="check" size={14}/></span><span><b>Evidence before interpretation</b><small>Every pattern is shown with its supporting answers.</small></span></div></aside></div></>;
}

// Edits are saved on this device first and synced in the background (see offline.js).
let flushTimer;
function useOutboxTick() { const [, set] = useState(0); useEffect(() => subscribe(() => set(x => x + 1)), []); }
const syncWord = { pending: 'Saved on this device · pending sync', conflict: 'Changed somewhere else', blocked: 'Saved on this device · sign in to sync', failed: 'Not accepted by the server' };
function ReviewQuestions({ assessment, setAssessment, approve, busy, generate, isMock, onSynced, flash }) {
  useOutboxTick();
  const [index, setIndex] = useState(0); const q = assessment.questions[index];
  const [adding, setAdding] = useState(false);
  function updateQuestion(patch) {
    const questions = assessment.questions.map((item,i)=>i===index?{...item,...patch}:item); setAssessment({...assessment,questions});
    if (isMock) return;
    const id = `question:${q.id}`;
    queue({ id, label: `Q${index+1}`, method: 'PATCH', path: `/questions/${q.id}`, body: { ...(entry(id)?.body || {}), ...patch }, baseVersion: q.version ?? 1 });
    clearTimeout(flushTimer); flushTimer = setTimeout(() => flush(onSynced), 1200);
  }
  async function addWritten() { setAdding(true); try { const a = await api.addQuestion(assessment.id, { type: 'descriptive', stem: '', concept: '' }); setAssessment(a); setIndex(a.questions.length - 1); } catch (e) { flash(e.message); } finally { setAdding(false); } }
  if (!q) return <><PageHeading eyebrow="QUESTION REVIEW" title="Review your questions" description="Draft an assessment first to see questions here." action={<Link className="button primary" to="/assessment">Create assessment</Link>}/></>;
  const local = entry(`question:${q.id}`);
  const written = q.type === 'descriptive';
  return <><PageHeading eyebrow="CREATE ASSESSMENT · 02 OF 03" title="Give each question a careful look." description="Check the wording, choices and correct answer before students see it." action={<span className="status-pill status-draft"><span/> {assessment.status==='draft'?'Draft · needs your review':statusLabel[assessment.status]}</span>}/>{assessment.notes?.length>0&&<div className="note-banner" role="status"><Icon name="clock" size={17}/><p>{assessment.notes.join(' ')}</p></div>}
    {local?.status==='conflict'&&<div className="note-banner conflict-banner" role="alert"><Icon name="shield" size={17}/><p>Q{index+1} was changed somewhere else after you started editing. The other version has {Object.keys(local.body).map(k=>`${k.replace('_',' ')}: “${typeof local.current?.[k]==='object'?Object.values(local.current[k]||{}).join(' / '):local.current?.[k]??''}”`).join('; ')}.</p><Button variant="outline" onClick={()=>{drop(local.id); setAssessment({...assessment,questions:assessment.questions.map(x=>x.id===q.id?local.current:x)});}}>Use the newer version</Button><Button variant="outline" onClick={()=>{keepMine(local.id, local.current?.version); flush(onSynced);}}>Keep my edit</Button></div>}
    <div className="review-layout"><div className="review-main"><div className="question-tabs" role="tablist" aria-label="Questions">{assessment.questions.map((item,i)=><button role="tab" aria-selected={i===index} className={i===index?'selected':''} onClick={()=>setIndex(i)} key={item.id}><span>Q0{i+1}</span><small>{item.type==='descriptive'?'Written':item.status==='approved'?'Ready':'Draft'}</small></button>)}{assessment.status==='draft'&&!isMock&&assessment.questions.length<5&&<button className="add-question" disabled={adding} onClick={addWritten}><Icon name="plus" size={15}/> {adding?'Adding…':'Written question'}</button>}</div>
    <Panel className="question-editor"><div className="editor-top"><div><span className="eyebrow">QUESTION {String(index+1).padStart(2,'0')} <span className="dot-sep">·</span> {written?'WRITTEN ANSWER':'MULTIPLE CHOICE'} <span className="dot-sep">·</span> {q.concept}</span><SourceTag source={q.source}/>{local&&<span className={`sync-chip sync-${local.status}`}>{syncWord[local.status]}</span>}</div><label className="field stem-field"><span>Question</span><textarea value={q.stem} rows="2" onChange={e=>updateQuestion({stem:e.target.value})}/></label></div>{q.validation_errors?.length>0&&<div className="field-error" role="alert">{q.validation_errors.join(" ")}</div>}
      {written?<><label className="field">Concept<input value={q.concept||''} onChange={e=>updateQuestion({concept:e.target.value})} placeholder="e.g. balanced forces"/></label><div className="question-explanation"><div className="explanation-title"><span className="explain-icon">i</span><b>What a full answer includes</b><small>Only you see this. It guides the AI suggestion.</small></div><textarea aria-label="What a full answer includes" value={q.model_answer||''} rows="3" onChange={e=>updateQuestion({model_answer:e.target.value})}/></div><p className="written-note">Printed with a large lined box. Scanned handwriting is transcribed for you to check; you approve any feedback.</p></>
      :<><div className="option-editor"><div className="option-heading"><b>Answer options</b><span>Choose the correct answer</span></div>{Object.entries(q.options||{}).map(([key,value])=><div className={`option-row ${q.answer===key?'correct-option':''}`} key={key}><button aria-label={`Mark ${key} as correct`} className={`answer-radio ${q.answer===key?'checked':''}`} onClick={()=>updateQuestion({answer:key})}>{q.answer===key&&<span/>}</button><span className="option-key">{key}</span><input aria-label={`Option ${key}`} value={value} onChange={e=>updateQuestion({options:{...q.options,[key]:e.target.value}})}/>{q.answer===key&&<span className="correct-label"><Icon name="check" size={14}/> Correct</span>}</div>)}</div><div className="distractor-tags" aria-label="Possible misconception tags">{Object.entries(q.distractors || {}).map(([option, detail]) => <span className="distractor-tag" key={option}>Option {option} · Possible: {detail.misconception_id} — {detail.why}</span>)}</div><div className="question-explanation"><div className="explanation-title"><span className="explain-icon">i</span><b>Answer explanation</b><small>Shown after review</small></div><textarea aria-label="Answer explanation" value={q.explanation||''} rows="2" onChange={e=>updateQuestion({explanation:e.target.value})}/></div></>}
    </Panel><div className="review-footer"><button className="text-button" disabled={index===0} onClick={()=>setIndex(index-1)}>← Previous question</button><span>{index+1} of {assessment.questions.length} questions</span><button className="text-button" disabled={index===assessment.questions.length-1} onClick={()=>setIndex(index+1)}>Next question →</button></div><div className="approve-footer"><div><b>Ready to approve?</b><span>Approving needs a connection; edits are kept on this device until then.</span></div><Button disabled={busy} onClick={approve} icon="check">{busy?'Saving…':'Approve assessment'}</Button></div></div><aside className="review-aside"><Panel className="review-help"><span className="eyebrow">QUESTION QUALITY</span><h3>Make the thinking visible.</h3><p>Distractors can surface a possible misconception, but they never prove what a student was thinking.</p><div className="quality-item"><span className="quality-dot green"/><span><b>Clear and focused</b><small>One idea at a time</small></span></div><div className="quality-item"><span className="quality-dot amber"/><span><b>Useful distractors</b><small>Wrong options reflect common approaches</small></span></div><div className="review-tagline"><Icon name="shield" size={15}/> Reviewed by you, always</div></Panel>{assessment.status==='draft'&&<button className="regenerate-link" disabled={busy} onClick={()=>generate({class_id:assessment.class_id,subject:assessment.subject,topic:assessment.topic,concepts_text:assessment.concepts_text,num_questions:assessment.questions.length,num_descriptive:assessment.questions.filter(x=>x.type==='descriptive').length})}><Icon name="refresh" size={15} /> {busy?'Drafting…':'Draft new questions'}</button>}</aside></div></>;
}

const paperCode = (id) => (id || '').split('_').slice(1).join('_').toUpperCase() || '—';
function useRoster(classId, isMock) {
  const [roster, setRoster] = useState(null);
  useEffect(() => { if (isMock) { setRoster(demo.roster.map((name, i) => ({ id: `st_0${i + 1}`, display_name: name, roll_no: `0${i + 1}` }))); return; } if (classId) api.students(classId).then(setRoster).catch(() => setRoster([])); }, [classId, isMock]);
  return roster;
}

function PrintPage({ assessment, printSheets, busy, isMock, pdf, flash }) {
  const approved = ['approved', 'printed', 'scanning', 'confirmed'].includes(assessment.status);
  const roster = useRoster(assessment.class_id, isMock);
  return <><PageHeading eyebrow="CREATE ASSESSMENT · 03 OF 03" title="Ready for paper." description="Every copy is the same. Students write their roll number at the top; MindTrace matches it to your class list when you scan." action={<span className={`status-pill ${approved?'status-complete':'status-draft'}`}><span/>{approved?'Approved for print':'Approval required'}</span>}/><div className="print-layout"><div><Panel className="print-preview-panel"><div className="preview-toolbar"><span><Icon name="printer" size={16}/> A4 QUESTION PAPER</span><span>Portrait · 210 × 297 mm</span></div><div className="paper-preview">
    <div className="paper-top"><div><small>ROLL NO.</small><span className="roll-boxes" aria-label="Five boxes for the roll number"><i/><i/><i/><i/><i/></span></div><div><small>CLASS / SECTION</small><span className="class-box"/></div><div className="paper-page"><b>Page 1 of 1</b><small>Paper code</small><code>{paperCode(assessment.id)}</code></div></div>
    <h2>{assessment.title || 'Assessment preview'}</h2><p className="paper-instruction">Write your roll number above. Fill ONE bubble per question with a dark pen, then explain why.</p>
    {assessment.questions.slice(0,3).map((q,i)=><div key={q.id} className="paper-question"><b>{i+1}. {q.stem}</b>{q.type==='descriptive'?<div className="reason-line written-box">Write your answer here.<i/><i/><i/></div>:<><div className="paper-options">{Object.entries(q.options||{}).map(([key,val])=><span key={key}><i/>{key}. {val}</span>)}</div><div className="reason-line">Why did you choose this answer? (working and notes)<i/><i/></div></>}</div>)}
  </div></Panel><div className="print-note"><Icon name="shield" size={16}/><span>No names or codes identify a student on the paper. Each copy is matched by the roll number the student writes.</span></div></div>
  <div className="print-side-stack"><Panel className="print-side"><span className="eyebrow">PRINT PREPARATION</span><h2>Class roster</h2><p>{roster?.length ? `${roster.length} students. The PDF has one page per student.` : 'The PDF has one page per student in the class.'}</p>
    {roster===null?<p className="list-empty" role="status">Loading the class list…</p>:roster.length?<div className="roster-list">{roster.map(s=><div key={s.id}><span className="roster-roll">{s.roll_no||'–'}</span><span>{s.display_name}</span></div>)}</div>:<p className="list-empty">No students found for this class.</p>}
    <div className="print-requirements"><b>Before you print</b><ul><li>Use A4 paper at 100% scale (no “fit to page”)</li><li>Keep the four corner squares visible</li><li>Tell students to write their roll number in the boxes, one character per box</li><li>Ask students to use a dark pen or pencil</li></ul></div><Button className="full-button" disabled={!approved||busy} onClick={printSheets} icon="printer">{busy?'Preparing papers…':'Generate PDF'}</Button>{!approved&&<small className="disabled-hint">Approve the questions before printing.</small>}
    {pdf&&<p className="pdf-ready" role="status"><Icon name="check" size={15}/> PDF ready ({pdf.pages} page{pdf.pages===1?'':'s'}). <a href={pdf.url} target="_blank" rel="noreferrer">Open to print</a> · <a href={pdf.url} download={pdf.name}>Download again</a></p>}
    {approved&&<Link to="/scanner" className="text-link">Next: scan the completed papers <Icon name="arrow" size={15}/></Link>}</Panel>
    <PracticePanel assessment={assessment} flash={flash}/></div></div></>;
}

const stateText = { single: 'Read', blank: 'No mark', multiple: 'More than one mark', ambiguous: 'Unclear mark', unreadable: 'Not readable' };
const sourceText = { gemini: 'Read by Gemini', bubble_reader: 'Read by the bubble reader (Gemini unavailable)', manual: 'Manual entry: Gemini couldn’t read it', qr_legacy: 'Older QR-based scan' };

function cameraProblem(error) {
  if (error.name === 'NotAllowedError' || error.name === 'SecurityError') return isNative ? 'Camera access was denied. Allow the camera for MindTrace in Android Settings › Apps › MindTrace › Permissions, or use Upload photo.' : 'Camera access was blocked. Allow the camera for this site in your browser settings (the camera icon in the address bar), or use Upload photo.';
  if (error.name === 'NotReadableError' || error.name === 'AbortError') return 'The camera is busy in another app. Close it and try again, or use Upload photo.';
  return 'No camera was found. Upload a photo of the sheet to continue.';
}

function Scanner({ assessment, upload, busy, scanProgress, isMock }) {
  const videoRef=useRef(null); const streamRef=useRef(null); const [cameraError,setCameraError]=useState(''); const [started,setStarted]=useState(false); const [capturing,setCapturing]=useState(false); const [roll,setRoll]=useState('');
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
    // Browsers only offer the camera on https (or localhost); on a plain http address mediaDevices is missing.
    if (!navigator.mediaDevices?.getUserMedia) return setCameraError(window.isSecureContext ? 'This browser can’t open the camera. Use Upload photo instead.' : 'The camera only works on a secure (https) address. Open MindTrace through its https address or the Android app, or use Upload photo.');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false });
      if (!mounted.current || streamRef.current) {
        stream.getTracks().forEach(track => track.stop());
        return;
      }
      streamRef.current = stream;
      setStarted(true);
    } catch (error) {
      if (mounted.current) setCameraError(cameraProblem(error));
    }
  }
  function stopCamera() { streamRef.current?.getTracks().forEach(t=>t.stop()); streamRef.current=null; setStarted(false); }
  async function send(file) { if (await upload(file, roll)) setRoll(''); }
  async function capture() { const v=videoRef.current; if(!v?.videoWidth) return; setCapturing(true); const c=document.createElement('canvas'); c.width=v.videoWidth; c.height=v.videoHeight; c.getContext('2d').drawImage(v,0,0); c.toBlob(async blob=>{ if(blob) await send(new File([blob],`mindtrace-scan-${Date.now()}.jpg`,{type:'image/jpeg'})); setCapturing(false); },'image/jpeg',0.9); }
  const recent = (scanProgress.scans || []).slice(0, 5);
  return <><PageHeading eyebrow="CLASSROOM SCANNER" title="Bring the paper back to life." description="Capture or upload a paper, then open the review queue to check answers, read text, or translate it." action={<span className="status-pill status-draft"><span/> {assessment.title || 'No assessment open'}</span>}/>
  <div className="scan-stats"><div><span>Confirmed</span><b>{scanProgress.accepted} <small>/ {scanProgress.total}</small></b></div><div><span>To check</span><b className="amber-text">{scanProgress.needs_review}</b></div><div><span>Not scanned</span><b>{scanProgress.remaining}</b></div><Link to="/review-scans" className="text-link">Review queue <Icon name="arrow" size={16}/></Link></div>
  <div className="scanner-layout"><Panel className="camera-panel"><div className="camera-head"><div><span className="eyebrow">LIVE CAPTURE</span><h2>{assessment.title||'No assessment open'}</h2></div><span className={`camera-state ${started?'camera-on':''}`}><i/>{started?'Camera ready':'Camera off'}</span></div>
    <div className={`camera-view ${started?'has-camera':''}`}>{started?<video ref={videoRef} autoPlay playsInline muted aria-label="Live camera preview of the paper"/>:<div className="camera-placeholder"><div className="camera-frame"><span/><span/><span/><span/><div className="camera-sheet"><div className="sheet-line long"/><div className="sheet-line"/><div className="bubble-row"><i/><i/><i/><i/></div><div className="sheet-line long"/><div className="sheet-line short"/></div></div><b>Fit the whole page in the frame</b><small>Include the roll-number boxes at the top. Flat, well lit, in focus.</small></div>}<div className="guide-frame" aria-hidden="true"><i/><i/><i/><i/></div></div>
    {cameraError&&<div className="field-error" role="alert">{cameraError}</div>}
    <div className="camera-actions">{!started?<Button icon="scan" onClick={startCamera} disabled={busy}>Start camera</Button>:<><Button disabled={busy||capturing} aria-busy={busy||capturing} icon="scan" onClick={capture}>{busy||capturing?'Reading…':'Capture paper'}</Button><Button variant="outline" onClick={stopCamera}>Stop camera</Button></>}<label className={`button outline upload-button ${busy?'is-disabled':''}`}>Upload photo<input type="file" accept="image/*" capture="environment" disabled={busy} onChange={e=>{send(e.target.files?.[0]); e.target.value='';}}/></label></div>
    {busy&&<p className="busy-hint" role="status">Reading the paper… usually 5–20 seconds.</p>}
    <label className="field roll-input">Roll number <small>(optional: type it if the paper is hard to read)</small><input value={roll} onChange={e=>setRoll(e.target.value)} inputMode="text" autoComplete="off" placeholder="e.g. 07" maxLength={12}/></label>
  </Panel>
  <aside className="scanner-aside"><Panel className="scan-tip"><span className="eyebrow">GET A CLEAR SCAN</span><h3>A steady page is a good start.</h3><div className="tip-row"><span>01</span><p>Place the paper on a flat, dark surface.</p></div><div className="tip-row"><span>02</span><p>Fit the whole page, roll-number boxes included.</p></div><div className="tip-row"><span>03</span><p>Avoid glare and shadows.</p></div><div className="scan-honesty"><Icon name="shield" size={16}/><p>Unclear roll numbers and marks are flagged, never guessed. You confirm every paper.</p></div></Panel>
    <Panel className="recent-scans"><div className="recent-heading"><b>Recent papers</b><Link to="/review-scans">Review queue</Link></div>{isMock?<div className="scan-empty"><span className="empty-ring"><Icon name="scan"/></span><b>Sample mode is on</b><p>Live scans appear when the API is connected.</p></div>:recent.length?<ul className="scan-list">{recent.map(s=><li key={s.scan_id}><b>{s.student?`${s.student.roll_no} · ${s.student.display_name}`:`Roll ${s.roll_number?.read||'?'} · not matched`}</b><span className={`status-pill ${s.status==='accepted'?'status-complete':'status-draft'}`}><span/>{s.status==='accepted'?'Confirmed':'To check'}</span></li>)}</ul>:<div className="scan-empty"><span className="empty-ring"><Icon name="clock"/></span><b>Ready for the first paper</b><p>Scanned papers will appear here.</p></div>}</Panel></aside></div></>;
}

function ReviewScans({ scanProgress, assessment, flash, reviewScan, confirmScans, busy, isMock }) {
  const roster = useRoster(assessment.class_id, isMock) || [];
  const waiting = [...(scanProgress.scans || []).filter(s => s.status === 'needs_review'), ...(scanProgress.duplicates || [])];
  const clear = waiting.filter(s => s.status === 'needs_review' && s.student && !s.warnings.length && s.answers.every(a => a.final));
  const [bulk, setBulk] = useState(false);
  async function confirmClear() { setBulk(true); let n = 0; for (const s of clear) if (await reviewScan(s.scan_id, { confirmed: true }, null)) n += 1; setBulk(false); flash(`${n} paper${n === 1 ? '' : 's'} confirmed.`, 'success'); }
  const canConfirm = !isMock && scanProgress.needs_review === 0 && assessment.id;
  return <><PageHeading eyebrow="SCAN REVIEW" title="Check each paper." description="Confirm the student and the answers. Nothing counts towards scores or insights until you do." action={<span className="status-pill status-draft"><span/>{waiting.length} to check</span>}/>
  {clear.length>0&&<div className="note-banner bulk-banner" role="status"><Icon name="check" size={17}/><p>{clear.length} paper{clear.length===1?' has':'s have'} a matched student, no warnings and clear answers.</p><Button variant="outline" disabled={bulk} aria-busy={bulk} onClick={confirmClear}>{bulk?'Confirming…':`Confirm ${clear.length} clear`}</Button></div>}
  {waiting.length ? waiting.map(scan => <ScanReviewCard key={scan.scan_id} scan={scan} reviewScan={reviewScan} assessment={assessment} roster={roster}/>) : <Panel className="empty-review"><span className="empty-ring"><Icon name={isMock?'clock':'check'} size={22}/></span><h2>{isMock?'Sample mode has no live scans.':'Nothing to check.'}</h2><p>{isMock?'Connect the MindTrace API to scan real papers. The class insights shown in sample mode come from the labelled fixture.':'Scanned papers wait here until you confirm the student and answers.'}</p><Link className="button outline" to="/scanner">Back to scanner</Link></Panel>}
  <Panel className="review-policy"><Icon name="shield"/><span><b>You confirm every paper</b><small>Scores and insights use only confirmed answers and your approved answer key.</small></span><Button variant="outline" disabled={!canConfirm||busy} aria-busy={busy} onClick={()=>canConfirm?confirmScans():flash(isMock?'Sample mode does not submit or confirm fixture scans.':'Check every paper before confirming results.', 'info')}>{busy?'Confirming…':'Confirm results'}</Button></Panel></>;
}

const textStateWord = { clear: 'Read clearly', unclear: 'Unclear handwriting: check every word', missing: 'Nothing written', not_read: 'Not read automatically: type it from the photo', teacher: 'Corrected by you' };
function ScanReviewCard({ scan, reviewScan, assessment, roster }) {
  useOutboxTick();
  const saved = entry(`scan:${scan.scan_id}`); // an edit kept on this device (offline, or waiting to sync)
  const fromSaved = (qid, key) => saved?.body?.answers?.find(a => a.question_id === qid)?.[key];
  const [studentId,setStudentId]=useState(saved?.body?.student_id||scan.student?.id||''); const [saving,setSaving]=useState('');
  const [answers,setAnswers]=useState(()=>Object.fromEntries(scan.answers.map(a=>[a.question_id,fromSaved(a.question_id,'final')??a.final??'']))); // unclear = empty: the teacher must choose
  const [texts,setTexts]=useState(()=>Object.fromEntries(scan.answers.map(a=>[a.question_id,fromSaved(a.question_id,'text')??a.text??''])));
  const dup = scan.status === 'duplicate'; const student = roster.find(s=>s.id===studentId);
  const missing = scan.answers.filter(a=>!answers[a.question_id]).length;
  async function act(kind) {
    setSaving(kind);
    const body = kind === 'discard' ? { discard: true } : { confirmed: kind === 'confirm', replace: dup && kind === 'confirm',
      answers: scan.answers.map(a => ({ question_id: a.question_id, ...(answers[a.question_id] && { final: answers[a.question_id] }), ...((texts[a.question_id] || '') !== (a.text || '') && { text: texts[a.question_id] }) })),
      ...(studentId && studentId !== scan.student?.id ? { student_id: studentId } : {}) };
    try { await reviewScan(scan.scan_id, body, kind === 'discard' ? 'Photo discarded.' : kind === 'draft' ? 'Changes saved. The paper still needs your confirmation.' : `${student ? `Roll ${student.roll_no} · ${student.display_name}` : 'Paper'} confirmed.`, scan.version); }
    finally { setSaving(''); }
  }
  return <Panel className="scan-review-card"><div className="scan-review-head"><div><span className="eyebrow">ROLL {scan.roll_number?.read || '—'} · {sourceText[scan.extracted_by] || 'Scanned paper'}</span><h2>{scan.student ? `${scan.student.display_name}` : 'Who is this?'}</h2></div><span className={`status-pill ${dup?'status-fixture':'status-draft'}`}><span/>{dup?'Already confirmed':'To check'}</span></div>
    {saved&&<p className={`sync-chip sync-${saved.status}`} role="status">{syncWord[saved.status]}{saved.status==='conflict'?': this paper was changed elsewhere. Reload the queue to see the newer version, then apply your change.':''}{saved.error&&saved.status!=='conflict'?` (${saved.error})`:''}</p>}
    {scan.warnings.length>0&&<ul className="scan-warnings">{scan.warnings.map(w=><li key={w.code}>{w.message}</li>)}</ul>}
    {scan.image_url && <LensPanel imageUrl={scan.image_url} />}
    <div className="scan-review-body">
      {scan.image_url&&<a className="scan-photo" href={mediaUrl(scan.image_url)} target="_blank" rel="noreferrer"><img src={mediaUrl(scan.image_url)} alt={`Photo of the paper, roll ${scan.roll_number?.read||'unknown'}`} loading="lazy"/><small>Open full photo</small></a>}
      <div className="scan-review-fields">
        <label className="field">Student<select value={studentId} onChange={e=>setStudentId(e.target.value)} aria-invalid={!studentId}><option value="">Choose the student…</option>{roster.map(s=><option key={s.id} value={s.id}>{s.roll_no} · {s.display_name}</option>)}</select></label>
        <div className="scan-answer-review">{scan.answers.map((a,i)=>{const q=assessment.questions.find(item=>item.id===a.question_id); const written=q?.type==='descriptive'||a.type==='descriptive'; const flagged=!a.final||a.text_state==='unclear'; return <div className={`scan-answer-row ${flagged?'flagged':''} ${written?'written-row':''}`} key={a.question_id}>{a.crop_url&&<div className="scan-crop"><img src={mediaUrl(a.crop_url)} alt={`${written?'Written answer':'Answer area'} for question ${i+1}`}/></div>}<div className="scan-answer-info"><b>Q{i+1}. {q?.stem||'Question'}</b>
          {written?<><span>{textStateWord[a.text_state]||''}{a.note?` · ${a.note}`:''}</span><label className="field">Transcription (compare with the photo)<textarea rows="3" value={texts[a.question_id]} onChange={e=>setTexts({...texts,[a.question_id]:e.target.value})} aria-invalid={a.text_state==='unclear'} placeholder="Type what the student wrote"/></label><label className="field">Answer<select value={answers[a.question_id]} aria-invalid={!answers[a.question_id]} onChange={e=>setAnswers({...answers,[a.question_id]:e.target.value})}><option value="">Choose…</option><option value="answered">Answered (transcribed above)</option><option value="blank">Blank (no answer)</option></select></label></>
          :<><span>{stateText[a.state]||a.state}{a.state==='single'?` ${a.detected}`:''}{a.note?` · ${a.note}`:''}</span><label className="field">Answer<select value={answers[a.question_id]} aria-invalid={!answers[a.question_id]} onChange={e=>setAnswers({...answers,[a.question_id]:e.target.value})}><option value="">Choose…</option>{['A','B','C','D','blank'].map(option=><option key={option} value={option}>{option==='blank'?'Blank (no answer)':`${option} · ${q?.options?.[option]||''}`}</option>)}</select></label>
            <details className="reasoning-edit" open={a.text_state==='unclear'}><summary>Reasoning and notes {a.text_state?`· ${textStateWord[a.text_state]||''}`:''}</summary>{a.reasoning_crop_url&&<img src={mediaUrl(a.reasoning_crop_url)} alt={`Handwritten reasoning for question ${i+1}`}/>}<textarea rows="2" value={texts[a.question_id]} onChange={e=>setTexts({...texts,[a.question_id]:e.target.value})} placeholder="Type the student's reasoning, if any"/></details></>}
        </div></div>})}</div>
      </div>
    </div>
    <div className="scan-review-actions"><Button onClick={()=>act('confirm')} disabled={!!saving||!studentId||missing>0} aria-busy={saving==='confirm'} icon="check">{saving==='confirm'?'Confirming…':dup?'Replace confirmed paper':'Confirm paper'}</Button><Button variant="outline" onClick={()=>act('draft')} disabled={!!saving||dup}>{saving==='draft'?'Saving…':'Save changes'}</Button><Button variant="outline" onClick={()=>act('discard')} disabled={!!saving}>{saving==='discard'?'Discarding…':'Discard photo'}</Button>{(!studentId||missing>0)&&<small className="disabled-hint">{!studentId?'Choose the student first.':`Choose ${missing} flagged answer${missing===1?'':'s'}.`}</small>}</div>
  </Panel>;
}

// Google Lens has no public API and refuses uploads from other websites, so MindTrace hands the photo to Lens the
// official ways: phones share it (choose Google Lens), computers copy it and paste it into lens.google.com, and the
// Android app opens Lens's own camera. Lens reads and translates; the teacher copies what they need. Nothing auto-fills.
const isPhone = () => /Android|iPhone|iPad/i.test(navigator.userAgent);
function LensPanel({ imageUrl }) {
  const [msg, setMsg] = useState('');
  const photo = useRef(null);
  const load = () => photo.current ||= fetch(mediaUrl(imageUrl)).then(r => { if (!r.ok) throw new Error('Couldn’t load the photo.'); return r.blob(); });
  useEffect(() => { if (!isNative && isPhone() && navigator.canShare) load().catch(() => {}); }, [imageUrl]); // ready before the tap
  async function lens() {
    setMsg('');
    if (isNative) {
      window.location.href = 'googleapp://lens';
      setMsg('Google Lens opens in the Google app. Point it at the paper, then tap Text to copy or translate it.');
      return;
    }
    if (isPhone() && navigator.canShare) {
      try {
        const blob = await load();
        const file = new File([blob], 'mindtrace-paper.jpg', { type: blob.type || 'image/jpeg' });
        if (navigator.canShare({ files: [file] })) {
          await navigator.share({ files: [file] });
          setMsg('Choose Google Lens (or Google) in the share list, then tap Text to copy or translate.');
          return;
        }
      } catch (e) { if (e.name === 'AbortError') return; }
    }
    const copied = copyImage(load()); // copy inside the click, then open Lens
    window.open('https://lens.google.com/', '_blank', 'noopener');
    copied.then(() => setMsg('Photo copied. In the Google Lens tab press Ctrl+V (⌘V on Mac) to paste it, then choose Text to copy or translate.'),
      () => setMsg('Open the full photo, right-click it and choose “Search with Google Lens” (Chrome), then choose Text.'));
  }
  return <div className="lens-panel">
    <Button variant="outline" icon="scan" onClick={lens}>Read with Google Lens</Button>
    <small>Lens reads and translates the handwriting. Copy what you need into the transcription; nothing is filled in automatically.</small>
    {msg && <p role="status" className="lens-msg">{msg}</p>}
  </div>;
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
