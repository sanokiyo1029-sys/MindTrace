import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from './api.js';
import Icon from './Icon.jsx';

export default function Auth({ onSession, onSample, googleSignIn, serverField, note }) {
  const [params, setParams] = useSearchParams();
  const role = params.get('role') === 'student' ? 'student' : 'teacher';

  return <div className="login-layout teacher-access unified-access">
    <section className="panel student-panel auth-panel unified-auth">
      <div className="student-login">
        <span className="student-lock"><Icon name="shield" size={25} /></span>
        <h1>Welcome to MindTrace!</h1>
        <p>Choose how you’d like to continue.</p>
        {note && <p className="auth-note" role="status">{note}</p>}
        <div className="role-select" role="group" aria-label="Choose your role">
          <button type="button" aria-pressed={role === 'teacher'}
            onClick={() => setParams(p => { p.set('role', 'teacher'); return p; })}><Icon name="book" /> Teacher</button>
          <button type="button" aria-pressed={role === 'student'}
            onClick={() => setParams(p => { p.set('role', 'student'); return p; })}><Icon name="users" /> Student</button>
        </div>
        <AuthForm key={role} role={role} onSession={onSession} serverField={serverField} />
        {role === 'teacher' && googleSignIn}
        {onSample && role === 'teacher' && <button type="button" className="text-link sample-entry"
          onClick={onSample}>Explore sample workspace <Icon name="arrow" size={16} /></button>}
      </div>
    </section>
  </div>;
}

function AuthForm({ role, onSession, serverField }) {
  const teacher = role === 'teacher';
  const [identifier, setIdentifier] = useState('');
  const [secret, setSecret] = useState('');
  const [showSecret, setShowSecret] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const active = useRef(true);

  useEffect(() => {
    active.current = true;
    return () => { active.current = false; };
  }, []);

  async function submit(event) {
    event.preventDefault();
    if (loading) return;
    setError('');
    const identity = identifier.trim();
    if (!identity || !secret) {
      setError(teacher ? 'Enter your email and password.' : 'Enter your student code and PIN.');
      return;
    }
    setLoading(true);
    try {
      const reply = teacher
        ? await api.login({ email: identity, password: secret })
        : await api.studentLogin({ student_code: identity, pin: secret });
      const { token } = reply;
      if (typeof token !== 'string' || !token.trim()) throw new Error('The server did not return a sign-in session.');
      const session = { role, token, teacher: reply.teacher, student: reply.student };
      if (!active.current) return;
      onSession(session);
    } catch (err) {
      if (active.current) setError(err.message);
    } finally {
      if (active.current) setLoading(false);
    }
  }

  return <>
    <h2 className="auth-role-heading">{teacher ? 'Welcome Back, Teacher!' : 'Welcome Back, Learner!'}</h2>
    {!teacher && <p className="auth-role-description">Your learning journey continues here.</p>}
    <form onSubmit={submit}>
      <label className="field">{teacher ? 'Email' : 'Student code'}
        <input type={teacher ? 'email' : 'text'} autoComplete="username" value={identifier}
          onChange={event => setIdentifier(event.target.value)} required placeholder={teacher ? undefined : 'e.g. 7A-01'} />
      </label>
      <div className="field secret-field">
        <label htmlFor="auth-secret">{teacher ? 'Password' : 'PIN'}</label>
        <div>
          <input id="auth-secret" type={showSecret ? 'text' : 'password'} inputMode={teacher ? undefined : 'numeric'}
            autoComplete="current-password" value={secret} onChange={event => setSecret(event.target.value)}
            required placeholder={teacher ? undefined : 'Enter your class PIN'} />
          <button type="button" aria-label={`${showSecret ? 'Hide' : 'Show'} ${teacher ? 'password' : 'PIN'}`}
            onClick={() => setShowSecret(!showSecret)}>{showSecret ? 'Hide' : 'Show'}</button>
        </div>
      </div>
      {serverField}
      {error && <p className="field-error" role="alert">{error}</p>}
      <button type="submit" className="button primary" disabled={loading}>
        <Icon name="arrow" size={17} /> {loading ? 'Signing in…' : 'Sign In'}
      </button>
    </form>
    <div className="signup-state">
      <button type="button" className="text-button" disabled>{teacher ? 'Create Teacher Account' : 'Create Student Account'}</button>
      <small>{teacher ? 'Account creation is unavailable. Ask your school for a teacher account.' : 'Your teacher provides your student code and PIN.'}</small>
    </div>
  </>;
}
