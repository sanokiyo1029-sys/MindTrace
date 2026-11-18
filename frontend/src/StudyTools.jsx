import { useState } from 'react';
import { isNative } from './api.js';
import { lensUrl, openLens } from './lens.js';
import { Button, Panel } from './ui.jsx';

const studyMode = {
  hints: 'Give me one hint at a time. Wait for my attempt before showing a solution.',
  explain: 'Explain the idea in simple steps with a short example, then ask me to try a similar one.',
  practice: 'Give me one similar practice question. Wait for my answer before checking it.',
};

export default function StudyTools() {
  const [text, setText] = useState('');
  const [mode, setMode] = useState('hints');
  const [message, setMessage] = useState('');
  const [copyFailed, setCopyFailed] = useState(false);
  const studyText = text.trim();
  const prompt = import.meta.env.MODE === 'android' ? studyText
    : `Help me study the question below. ${studyMode[mode]}\n\n${studyText}`;

  async function lens() {
    try {
      const { mode: opened } = await openLens();
      setMessage(opened === 'camera' ? 'Choose Text in Lens, copy the question, then return here and paste it.'
        : 'Upload your photo in Lens, choose Text, then copy and paste the question below.');
    } catch (e) { setMessage(e.message || 'Couldn’t open Google Lens.'); }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(prompt);
      setCopyFailed(false);
      setMessage(import.meta.env.MODE === 'android' ? 'Study text copied.' : 'Study prompt copied. Open Gemini and paste it there.');
    } catch {
      setCopyFailed(true);
      setMessage('Select and copy the text below.');
    }
  }

  return <Panel className="student-result-card exam-panel study-tools">
    <h2 id="study-tools">Study tools</h2>
    <p>Use Lens to photograph a study question. Copy the recognized text from Lens, then paste it here and check it.</p>
    {isNative ? <Button type="button" variant="outline" icon="scan" onClick={lens}>Open Google Lens</Button>
      : <a className="button outline" href={lensUrl} target="_blank" rel="noopener noreferrer">Open Google Lens</a>}
    <label className="field">Study question<textarea rows="3" maxLength={2500} value={text}
      placeholder="Paste text from Lens or type your question" onChange={e => { setText(e.target.value); setMessage(''); setCopyFailed(false); }} /></label>
    {import.meta.env.MODE !== 'android' && <label className="field">How would you like help?
      <select value={mode} onChange={e => { setMode(e.target.value); setMessage(''); }}>
        <option value="hints">One hint at a time</option><option value="explain">Step-by-step explanation</option><option value="practice">A similar practice question</option>
      </select>
    </label>}
    <div className="exam-actions">
      <Button type="button" variant="outline" icon="copy" disabled={!studyText} onClick={copy}>
        {import.meta.env.MODE === 'android' ? 'Copy study text' : 'Copy study prompt'}
      </Button>
      {import.meta.env.MODE !== 'android' && studyText &&
        <a className="button primary" href="https://gemini.google.com/app" target="_blank" rel="noopener noreferrer">Open Gemini</a>}
    </div>
    {import.meta.env.MODE !== 'android' && <small>Paste the prompt into Gemini using an account your school or parent allows. Leave out names and other private details.</small>}
    {message && <p role="status">{message}</p>}
    {copyFailed && <label className="field">Text to copy<textarea rows="4" readOnly value={prompt} /></label>}
  </Panel>;
}
