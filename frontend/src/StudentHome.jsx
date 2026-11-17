import Icon from './Icon.jsx';
import PaperSurface from './PaperSurface.jsx';

export default function StudentHome({ results }) {
  const assessments = results.assessments || [];
  const answers = assessments.flatMap(assessment => assessment.answers.map(answer => ({
    ...answer, key: `${assessment.assessment_id}-${answer.question_id}`,
  })));
  const improvements = answers.filter(answer => answer.maybe);
  const practice = answers.filter(answer => answer.correct && answer.chosen !== answer.correct && answer.explanation);
  const feedback = answers.filter(answer => answer.explanation);

  return <>
    <header className="student-home-heading">
      <p className="landing-kicker">Welcome, {results.student.display_name}</p>
      <h1><span className="marker-text">Your Learning Journey</span></h1>
      <p>Every mistake is a chance to understand something new.</p>
    </header>
    <nav className="student-section-links" aria-label="Your results">
      <a href="#my-results">My Results</a>
      {feedback.length > 0 && <a href="#feedback">Assessment Feedback</a>}
      {improvements.length > 0 && <a href="#improve">What I Can Improve</a>}
      {practice.length > 0 && <a href="#practice">Suggested Practice</a>}
    </nav>
    <div className="student-home-grid">
      <div id="my-results" className="student-home-results">
        <h2>My Results</h2>
        {assessments.length === 0 && <section className="panel student-result-card">
          <p>Your results will appear here after your teacher shares them.</p>
        </section>}
        {assessments.map(assessment => <PaperSurface key={assessment.assessment_id} className="panel student-result-card">
          <h3><span className="hover-marker">{assessment.title}</span></h3>
          {assessment.answers.map(answer => <div className="student-answer" key={answer.question_id}>
            <b>{answer.stem}</b>
            <p>Your answer <strong>{answer.chosen || 'Blank'}</strong>
              {answer.correct && <span>Correct answer {answer.correct}</span>}
            </p>
          </div>)}
        </PaperSurface>)}
      </div>
      <div className="student-home-help">
        {feedback.length > 0 && <div id="feedback">
          <h2>Assessment Feedback</h2>
          <PaperSurface className="panel student-result-card">
            {feedback.map(answer => <div className="student-answer" key={answer.key}><b>{answer.stem}</b><p>{answer.explanation}</p></div>)}
          </PaperSurface>
        </div>}
        {improvements.length > 0 && <div id="improve">
          <h2>What I Can Improve</h2>
          <PaperSurface className="panel student-result-card">
            {improvements.map(answer => <div className="student-answer" key={answer.key}><b>{answer.stem}</b><p>{answer.maybe}</p></div>)}
          </PaperSurface>
        </div>}
        {practice.length > 0 && <div id="practice">
          <h2>Suggested Practice</h2>
          <PaperSurface className="panel student-result-card">
            <p><Icon name="book" size={17} /> Try these questions again before checking the explanations.</p>
            {practice.map(answer => <details className="student-practice" key={answer.key}>
              <summary>{answer.stem}</summary><p>{answer.explanation}</p>
            </details>)}
          </PaperSurface>
        </div>}
      </div>
    </div>
  </>;
}
