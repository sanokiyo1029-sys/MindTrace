import demo from './fixtures/demo.json';

// Explicit fictional answer keys for the sample workspace only. The first paper matches demo.insights.
const papers = [
  { ...demo.assessment, marks: [['A', 'C', 'B'], ['B', 'C', 'B'], ['A', 'A', 'C'], ['B', 'C', 'D'], ['A', 'C', 'B']] },
  { id: 'as_demo_followup', title: 'Fractions follow-up', topic: 'fractions', questions: demo.question_bank,
    marks: [['C', 'A'], ['C', 'A'], ['A', 'B'], ['C', 'A'], [null, null]] },
];
const students = demo.roster.map((display_name, i) => ({ id: `sample-${i}`, display_name, roll_no: String(i + 1) }));

function sampleEvidence() {
  const topics = new Map();
  const results = [];
  for (const paper of papers) {
    for (const [i, q] of paper.questions.entries()) {
      if (!topics.has(q.concept)) topics.set(q.concept, { name: q.concept, topic: paper.topic, assessment_ids: [], mistakes: [] });
      const topic = topics.get(q.concept);
      topic.assessment_ids.push(paper.id);
      const counts = new Map();
      for (const [row, student] of students.entries()) {
        const choice = paper.marks[row][i];
        if (!choice) continue;
        counts.set(choice, (counts.get(choice) || 0) + 1);
        results.push({ assessment_id: paper.id, student_id: student.id, concept: q.concept,
          correct: Number(choice === q.answer), answered: 1 });
      }
      for (const [choice, count] of counts) {
        if (choice === q.answer) continue;
        topic.mistakes.push({ question_id: q.id, stem: q.stem, choice: q.options[choice], expected: q.options[q.answer],
          count, answered: paper.marks.filter(row => row[i]).length,
          possible_misconception: q.distractors[choice]?.why });
      }
    }
  }
  for (const concept of topics.values()) concept.mistakes.sort((a, b) => b.count - a.count);
  return { students, concepts: [...topics.values()], results };
}

const samples = sampleEvidence();
export function sampleOverview(subject) {
  const hasSamples = subject === 'mathematics';
  return { assessment_count: hasSamples ? papers.length : 0, student_count: students.length, needs_review: 0,
    topics: hasSamples ? ['fractions'] : [], history: hasSamples ? papers.map(({ id, title }) => ({ id, title })).reverse() : [],
    understanding: hasSamples ? samples : { students, concepts: [], results: [] } };
}
