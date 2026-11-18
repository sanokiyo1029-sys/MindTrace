import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Panel } from './ui.jsx';
import './class-understanding.css';

const levels = [
  ['strong', 'Understood'], ['practicing', 'Still practicing'],
  ['support', 'Needs help'], ['unassessed', 'Not assessed'],
];
const byRoll = new Intl.Collator(undefined, { numeric: true }).compare;
const accuracy = (score) => score?.answered ? Math.round(100 * score.correct / score.answered) : null;
const level = (score) => {
  const pct = accuracy(score);
  return levels[pct === null ? 3 : pct >= 80 ? 0 : pct >= 50 ? 1 : 2];
};

function indexEvidence({ concepts, results }) {
  const byConcept = new Map(concepts.map(c => [c.name, {
    ...c, correct: 0, answered: 0, students: new Map(), assessments: new Map(),
  }]));
  for (const record of results) {
    const concept = byConcept.get(record.concept);
    if (!concept) continue;
    if (!concept.students.has(record.student_id)) {
      concept.students.set(record.student_id, { correct: 0, answered: 0, history: new Map() });
    }
    const student = concept.students.get(record.student_id);
    if (!concept.assessments.has(record.assessment_id)) concept.assessments.set(record.assessment_id, { correct: 0, answered: 0 });
    student.history.set(record.assessment_id, record);
    for (const score of [concept, student, concept.assessments.get(record.assessment_id)]) {
      score.correct += record.correct;
      score.answered += record.answered;
    }
  }
  return [...byConcept.values()];
}

export default function ClassUnderstanding({ data, history, isMock, openAssessment }) {
  const concepts = useMemo(() => indexEvidence(data), [data]);
  const [selection, setSelection] = useState(null);
  const topics = new Map();
  for (const concept of concepts) {
    if (!topics.has(concept.topic)) topics.set(concept.topic, []);
    topics.get(concept.topic).push(concept);
  }
  const selected = concepts.find(c => c.name === selection?.concept)
    || [...concepts].sort((a, b) => (accuracy(a) ?? 101) - (accuracy(b) ?? 101))[0];
  const student = data.students.find(s => s.id === selection?.student);
  const students = [...data.students].sort((a, b) => byRoll(a.roll_no || a.display_name, b.roll_no || b.display_name));
  const select = (concept, studentId = null) => setSelection({ concept, student: studentId });

  return <div className="understanding-grid">
    <Panel className="understanding-panel concept-map">
      <h3>Concept understanding map</h3>
      <p>Class accuracy by concept, grouped by topic.</p>
      {!concepts.length && <p className="understanding-empty">Concepts appear once an assessment is approved.</p>}
      <ul className="concept-topics">{[...topics].map(([topic, group]) => <li key={topic}>
        <span className="concept-topic">{topic}</span>
        <ul>{group.map(concept => <li key={concept.name}>
          <button type="button" aria-pressed={selected === concept && !student} aria-controls="understanding-evidence"
            onClick={() => select(concept.name)} title={level(concept)[1]}>
            <b className={`understanding-mark ${level(concept)[0]}`}>{accuracy(concept) === null ? '—' : `${accuracy(concept)}%`}</b>
            <span>{concept.name}{level(concept)[0] === 'support' && <small>Needs attention</small>}</span>
          </button>
        </li>)}</ul>
      </li>)}</ul>
    </Panel>

    <Panel className="understanding-panel understanding-heatmap">
      <h3>Student understanding heatmap</h3>
      <p>Select a cell to see the answers behind it. <a href="#understanding-evidence">View evidence</a></p>
      {students.length === 0 ? <p className="understanding-empty">No students in this class yet.</p> :
        !concepts.length ? <div className="understanding-empty">
          <p>There are no approved concepts for this subject yet.</p>
          {!isMock && <div className="roster-links">{students.map(s => <Link key={s.id} to={`/students/${s.id}`}>{s.display_name}</Link>)}</div>}
        </div> : <div className="understanding-scroll" tabIndex={0} role="region" aria-label="Scrollable student heatmap">
          <table>
            <caption className="sr-only">Correct answers out of reviewed multiple-choice answers by student and concept</caption>
            <thead><tr><th scope="col">Student</th>{concepts.map(c => <th key={c.name} scope="col">
              <button type="button" onClick={() => select(c.name)} aria-pressed={selected === c && !student}
                aria-controls="understanding-evidence">{c.name}</button>
            </th>)}</tr></thead>
            <tbody>{students.map(s => <tr key={s.id}>
              <th scope="row">{s.display_name}{s.roll_no && <small>Roll {s.roll_no}</small>}</th>
              {concepts.map(c => {
                const score = c.students.get(s.id);
                const [tone, label] = level(score);
                const fraction = score ? `${score.correct}/${score.answered}` : '—';
                const description = `${s.display_name}, ${c.name}: ${label}${score ? `, ${score.correct} of ${score.answered} correct` : ''}`;
                return <td key={c.name}><button type="button" className={`understanding-mark ${tone}`}
                  aria-label={description} title={description} aria-pressed={selected === c && student?.id === s.id}
                  aria-controls="understanding-evidence" onClick={() => select(c.name, s.id)}>{fraction}</button></td>;
              })}
            </tr>)}</tbody>
          </table>
        </div>}
      <ul className="understanding-legend" aria-label="Heatmap legend">{levels.map(([tone, label]) =>
        <li key={tone}><span className={`understanding-mark ${tone}`} aria-hidden="true" />{label}</li>)}</ul>
      {concepts.length > 0 && <p className="understanding-method">Based on confirmed multiple-choice answers. Written answers are reviewed separately.</p>}
    </Panel>

    <Panel className="understanding-panel understanding-evidence">
      <div id="understanding-evidence" tabIndex={-1}>
        <h3>Evidence & next steps</h3>
        {selected ? <ConceptEvidence concept={selected} student={student} history={history}
          isMock={isMock} openAssessment={openAssessment} /> :
          <p className="understanding-empty">Approve an assessment and confirm its scans to see class evidence here.</p>}
      </div>
    </Panel>
  </div>;
}

function ConceptEvidence({ concept, student, history, isMock, openAssessment }) {
  const score = student ? concept.students.get(student.id) : concept;
  const pct = accuracy(score);
  const runs = history.filter(a => concept.assessment_ids.includes(a.id));
  return <>
    <div className="evidence-selection" aria-live="polite">
      <h4>{concept.name}</h4>
      <p>{student?.display_name || 'Class performance'}</p>
      <div className="evidence-score"><strong>{pct === null ? '—' : `${pct}%`}</strong>
        <span>{pct === null ? 'No confirmed scores' : `${score.correct} of ${score.answered} correct`}
          {!student && pct !== null && <small>{concept.students.size} students assessed</small>}
          {student && score?.answered === 1 && <small>One answer so far</small>}</span></div>
    </div>
    <h4>Assessment history</h4>
    <ul className="evidence-history">{runs.map(a => {
      const entry = student ? score?.history.get(a.id) : concept.assessments.get(a.id);
      const result = accuracy(entry);
      return <li key={a.id}><span>{isMock ? a.title : <button type="button" onClick={() => openAssessment(a.id, true)}>{a.title}</button>}
        {a.created_at && <small>{new Date(a.created_at).toLocaleDateString()}</small>}</span>
        <b>{result === null ? 'No score' : `${result}%`}</b></li>;
    })}</ul>
    <h4>Common class mistakes</h4>
    {concept.mistakes.length ? <ul className="evidence-mistakes">{concept.mistakes.map(m =>
      <li key={`${m.question_id}-${m.choice}`}><b>{m.choice} <span>· {m.count} of {m.answered}</span></b>
        <span>{m.stem}</span><small>Expected answer: {m.expected}</small>
        {m.possible_misconception && <small>Possible misconception: {m.possible_misconception}</small>}</li>)}</ul>
      : <p className="understanding-empty">{concept.answered ? 'No wrong answers recorded for this concept.' : 'Mistakes appear after scored answers are confirmed.'}</p>}
    <div className="evidence-actions">
      {student && !isMock && <Link to={`/students/${student.id}`} className="text-link">Open student report →</Link>}
      {!isMock && runs.some(a => a.status === 'confirmed') && <button className="text-button" type="button"
        onClick={() => openAssessment(runs.find(a => a.status === 'confirmed').id, '/recommendations')}>Plan what to teach next →</button>}
      {isMock && <Link to="/recommendations" className="text-link">Teaching recommendations →</Link>}
    </div>
  </>;
}
