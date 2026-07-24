"""
agent.py
Core logic for the Interview Screening Agent.

Design
------
- `InterviewAgent` runs a fixed question set per role (from question_bank.json).
- Each answer is scored 0-10 with a short rationale.
- Scoring uses the Anthropic API when ANTHROPIC_API_KEY is set (LLM-graded,
  higher quality). If no key is present, it falls back to a deterministic
  keyword/heuristic grader so the whole pipeline still runs end-to-end
  with zero external dependencies -- this is what the seeded demo data uses.
- After all questions, the agent computes an overall score and a
  recommendation using a fixed decision boundary (see README for the
  rationale) and writes everything to SQLite via db.py.
"""

import os
import json
import re
from pathlib import Path

import db

QUESTION_BANK_PATH = Path(__file__).parent / "question_bank.json"

# ---------------------------------------------------------------------------
# Decision boundary constants (see README "Decision Boundary" section for why)
# ---------------------------------------------------------------------------
STRONG_HIRE_THRESHOLD = 8.0
HIRE_THRESHOLD = 6.5
UNSURE_THRESHOLD = 5.0
# below UNSURE_THRESHOLD -> "No Hire"

LOW_CONFIDENCE_SPREAD = 3.0  # if per-question scores vary by more than this, flag "Unsure" for human review


def load_questions(role: str):
    with open(QUESTION_BANK_PATH) as f:
        bank = json.load(f)
    if role not in bank:
        role = "General / Entry-Level"
    return bank[role]


def _heuristic_score(answer_text: str, question: dict):
    """
    Deterministic fallback grader (no API key required).
    Scores 0-10 based on:
      - length / effort (very short answers score low)
      - keyword overlap with the question's expected keywords
      - presence of concrete examples ("for example", "I", "we", numbers)
    This is intentionally simple and transparent -- it exists so the
    end-to-end pipeline is fully runnable and demoable without any
    external API key. It is NOT a substitute for the LLM grader for
    real screening decisions (see README limitations).
    """
    text = answer_text.lower().strip()
    if len(text) < 15:
        return 1.0, "Answer is too short to demonstrate understanding."

    word_count = len(text.split())
    length_score = min(word_count / 60.0, 1.0) * 4.0  # up to 4 points for depth

    keywords = question.get("keywords", [])
    hits = sum(1 for kw in keywords if kw.lower() in text)
    keyword_score = min(hits / max(len(keywords), 1), 1.0) * 4.0  # up to 4 points

    concreteness_bonus = 0.0
    if re.search(r"\bfor example\b|\be\.g\.\b|\bfor instance\b", text):
        concreteness_bonus += 1.0
    if re.search(r"\d", text):
        concreteness_bonus += 0.5
    if re.search(r"\bi\b|\bwe\b", text):
        concreteness_bonus += 0.5

    score = round(min(length_score + keyword_score + concreteness_bonus, 10.0), 1)
    rationale = (
        f"[heuristic grader] length≈{word_count} words, "
        f"matched {hits}/{len(keywords)} expected concepts, "
        f"concreteness bonus={concreteness_bonus}"
    )
    return score, rationale


def _llm_score(answer_text: str, question: dict, client):
    """LLM-graded scoring via the Anthropic API. Requires `client` (anthropic.Anthropic)."""
    ideal_points = question.get("ideal_points", [])
    prompt = f"""You are grading a candidate's interview answer for a {question.get('type', 'general')} question.

Question: {question['question']}

What a strong answer would cover:
- {chr(10).join('- ' + p for p in ideal_points)}

Candidate's answer:
\"\"\"{answer_text}\"\"\"

Score the answer from 0 to 10 (10 = excellent, demonstrates strong understanding and concrete experience;
0 = no relevant content). Respond ONLY with valid JSON, no other text, in this exact format:
{{"score": <number 0-10>, "rationale": "<one sentence explaining the score>"}}"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in response.content if getattr(block, "type", "") == "text")
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    parsed = json.loads(text)
    return float(parsed["score"]), parsed["rationale"]


class InterviewAgent:
    def __init__(self, use_llm: bool = None):
        """
        use_llm: True forces LLM grading (errors if no key), False forces heuristic,
                 None (default) auto-detects based on ANTHROPIC_API_KEY.
        """
        self.client = None
        api_key = os.environ.get("ANTHROPIC_API_KEY")

        if use_llm is None:
            use_llm = bool(api_key)

        if use_llm:
            if not api_key:
                raise RuntimeError("use_llm=True but ANTHROPIC_API_KEY is not set.")
            import anthropic
            self.client = anthropic.Anthropic(api_key=api_key)

        self.use_llm = use_llm

    def get_questions(self, role: str):
        return load_questions(role)

    def score_answer(self, answer_text: str, question: dict):
        if self.use_llm:
            try:
                return _llm_score(answer_text, question, self.client)
            except Exception as e:
                # graceful fallback: never let a single API hiccup kill the interview
                fallback_score, fallback_rationale = _heuristic_score(answer_text, question)
                return fallback_score, f"{fallback_rationale} (LLM grading failed: {e})"
        return _heuristic_score(answer_text, question)

    def recommend(self, overall_score: float, per_question_scores: list):
        spread = max(per_question_scores) - min(per_question_scores) if per_question_scores else 0
        if spread > LOW_CONFIDENCE_SPREAD:
            return "Unsure", (
                f"Flagged for human review: answer quality was inconsistent "
                f"(scores ranged from {min(per_question_scores)} to {max(per_question_scores)})."
            )
        if overall_score >= STRONG_HIRE_THRESHOLD:
            return "Strong Hire", "Consistently strong, concrete answers across technical and behavioral questions."
        if overall_score >= HIRE_THRESHOLD:
            return "Hire", "Solid answers overall, meets the bar for the role."
        if overall_score >= UNSURE_THRESHOLD:
            return "Unsure", "Mixed or shallow answers; recommend a human follow-up interview."
        return "No Hire", "Answers did not demonstrate the expected knowledge or experience."

    def run_interview(self, candidate_name: str, role: str, answers: dict):
        """
        answers: dict of {question_id: answer_text}, e.g. from a CLI/Streamlit session.
        Runs scoring for every question, writes the full record to SQLite,
        and returns a summary dict.
        """
        questions = self.get_questions(role)
        interview_id = db.create_interview(candidate_name, role)

        scores = []
        for q in questions:
            answer_text = answers.get(q["id"], "").strip()
            if not answer_text:
                answer_text = "(no answer provided)"
            score, rationale = self.score_answer(answer_text, q)
            db.add_answer(interview_id, q, answer_text, score, rationale)
            scores.append(score)

        overall_score = round(sum(scores) / len(scores), 1) if scores else 0.0
        recommendation, summary = self.recommend(overall_score, scores)
        db.finish_interview(interview_id, overall_score, recommendation, summary)

        return {
            "interview_id": interview_id,
            "candidate_name": candidate_name,
            "role": role,
            "overall_score": overall_score,
            "recommendation": recommendation,
            "summary": summary,
            "graded_by": "LLM" if self.use_llm else "heuristic",
        }
