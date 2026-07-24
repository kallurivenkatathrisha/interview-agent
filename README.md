# Interview Screening Agent

A text-based agent that conducts a structured candidate screening interview,
scores each answer, produces a hire/no-hire recommendation, and stores every
interview as a queryable record in SQLite. Built for the Rooman Technologies
24-Hour AI Agent Challenge.

**Live workflow:** candidate picks a role → answers a fixed question set →
agent scores each answer (LLM-graded if an API key is present, otherwise a
deterministic heuristic grader) → overall score + recommendation is computed
→ everything is written to `data/interviews.db` → a recruiter dashboard
lists and filters past interviews.

---

## 1. Quickstart (local)

```bash
git clone <your-repo-url>
cd interview-agent
pip install -r requirements.txt

# Optional but recommended for real use — without it the agent runs in
# heuristic (non-LLM) grading mode automatically:
cp .env.example .env
# edit .env and add your ANTHROPIC_API_KEY, then:
export $(cat .env | xargs)

# The repo ships with a pre-populated demo database. To regenerate it:
python seed_data.py

# See the required "query demonstrating stored records" deliverable:
python query_demo.py

# Run the app:
streamlit run app.py
```

Open the local URL Streamlit prints (usually `http://localhost:8501`).
Use the sidebar to switch between **Take Interview** (candidate flow) and
**Recruiter Dashboard** (browse/filter stored interviews).

No API key? The app still works end-to-end — it just tells you it's using
the heuristic grader instead of the LLM grader.

---

## 2. Architecture

```
question_bank.json   -- fixed question sets per role (technical + behavioral)
db.py                 -- SQLite schema + CRUD (interviews, answers tables)
agent.py              -- InterviewAgent: question flow, scoring, recommendation
seed_data.py           -- populates a demo database with sample candidates
query_demo.py           -- required deliverable: demonstrates listing/filtering
app.py                 -- Streamlit UI (candidate flow + recruiter dashboard)
sample_transcripts/     -- required deliverable: readable interview transcript
```

**Why SQLite:** zero setup, single file, matches the challenge's "SQLite is
sufficient" guidance, and is trivial to inspect (`sqlite3 data/interviews.db`).

**Why a fixed question bank instead of LLM-generated questions:** it keeps
every candidate for a given role directly comparable, and it means the
recruiter dashboard can show consistent columns/scores across candidates.
An LLM could generate follow-up questions on top of this in a future
iteration (see Limitations).

**Grading has two modes, same interface:**
- **LLM grader** (`agent._llm_score`): sends the question, the "ideal answer
  points," and the candidate's answer to Claude, asks for a 0–10 score and a
  one-sentence rationale as JSON. Used automatically when `ANTHROPIC_API_KEY`
  is set.
- **Heuristic grader** (`agent._heuristic_score`): deterministic, no API
  call — scores on answer length/effort, keyword overlap with expected
  concepts, and concreteness signals (examples, numbers, first-person
  experience). This exists so the whole project **runs and can be graded by
  reviewers with zero API key setup**, and it's what populates the seeded
  demo database.
- If the LLM call fails for any reason (rate limit, network, bad JSON), the
  agent automatically falls back to the heuristic grader for that answer
  rather than crashing the interview.

---

## 3. Decision Boundary (how routing/recommendation is decided)

After every question is scored, the agent computes:

1. **Overall score** = simple average of per-question scores (0–10).
2. **Spread** = max score − min score across questions.

Recommendation logic (in `agent.py::InterviewAgent.recommend`):

| Condition                                          | Recommendation |
|-----------------------------------------------------|-----------------|
| Spread > 3.0 points                                  | **Unsure** (flag for human review — inconsistent answers are a signal that a single average is misleading, e.g. one great technical answer and one empty behavioral answer) |
| Overall ≥ 8.0                                         | **Strong Hire** |
| Overall ≥ 6.5                                         | **Hire** |
| Overall ≥ 5.0                                         | **Unsure** (mixed/shallow, needs a human follow-up) |
| Overall < 5.0                                         | **No Hire** |

**Why check spread before the score thresholds:** a candidate who aces the
technical questions but leaves a behavioral question blank could still
average into "Hire" territory, which would hide a real gap. Checking
consistency first routes borderline/inconsistent cases to a human instead
of letting the agent make a confident-looking call on thin evidence — this
mirrors the "flag unsure cases for human review" requirement from the
support-ticket-triage-style spec.

**Why these specific thresholds:** they're a starting heuristic, not a
validated hiring bar — tune them by scoring hires/rejects from real
historical interviews once labeled outcomes exist. This is a deliberate,
documented simplification (see Limitations).

---

## 4. Deliverables checklist

- ✅ Sample interviews (text-based, since this build targets text — see
  README §6 for the voice tradeoff note): `seed_data.py` + `sample_transcripts/`
- ✅ Populated database: `data/interviews.db` (run `python seed_data.py` to
  regenerate)
- ✅ Query demonstrating stored records: `python query_demo.py`
- ✅ This note explaining the decision boundary: §3 above

---

## 5. Deployment (Streamlit Community Cloud)

Recommended because it's free, requires no server management, and Streamlit
apps deploy directly from a GitHub repo in a few minutes.

1. Push this folder to a public (or private, on a paid plan) GitHub repo.
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with
   GitHub.
3. Click **New app**, pick your repo/branch, and set **Main file path** to
   `app.py`.
4. Under **Advanced settings → Secrets**, add:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   ```
   (Skip this if you want the deployed app to run in heuristic mode.)
5. Click **Deploy**. Streamlit Cloud installs `requirements.txt`
   automatically.

**Important caveat about the database on Streamlit Cloud:** the filesystem
on Community Cloud is ephemeral — it resets on redeploys and can reset on
restarts. For a real deployment, swap `db.py`'s SQLite connection for a
hosted Postgres (e.g. Supabase/Neon free tier) using the same function
signatures; the rest of the app doesn't need to change. This repo keeps
SQLite because the challenge explicitly says "SQLite is sufficient," but
it's not durable in that specific hosting environment — flagging this
honestly rather than hiding it.

**Alternative:** Render or Railway with a Docker deployment give you a
persistent disk, so SQLite would survive restarts there. A minimal
`Dockerfile` would be:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0"]
```

---

## 6. Design tradeoffs & honest limitations

- **Text, not voice.** This build is text-based end-to-end (typed answers).
  Voice input could be added by transcribing audio client-side (e.g.
  browser `MediaRecorder` → Whisper/Claude audio) and feeding the
  transcript into the same `run_interview()` function — the scoring/storage
  layer doesn't care where the text came from. Cut for scope in 24 hours.
- **Fixed question bank, no adaptive follow-ups.** The agent doesn't yet ask
  dynamic follow-up questions based on a weak answer. That's a natural next
  step once the base loop is solid.
- **Heuristic grader is intentionally simple.** It's a keyword/length
  proxy, not real language understanding — good enough to prove the
  pipeline end-to-end without an API key, but it will misjudge answers that
  are well-phrased without hitting the exact expected keywords, or vice
  versa. The LLM grader is the one intended for real screening decisions.
- **Decision thresholds are unvalidated.** They're a documented starting
  point (§3), not derived from real labeled outcomes.
- **No authentication.** Anyone with the deployed link can take an
  interview or view the dashboard. Fine for a challenge demo; a real
  deployment needs auth (e.g. recruiter login) before going further.
- **SQLite on ephemeral hosting.** Covered in the deployment section above.

---

## 7. Environment variables

| Variable             | Required? | Purpose                                      |
|-----------------------|-----------|-----------------------------------------------|
| `ANTHROPIC_API_KEY`   | No        | Enables LLM-graded answer scoring. Without it, the agent uses the heuristic grader automatically. |
