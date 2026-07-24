"""
app.py
Streamlit UI for the Interview Screening Agent.

Two views (pick from the sidebar):
  1. "Take Interview"  -- candidate-facing flow: pick a role, answer the
     questions, get scored, record saved to SQLite.
  2. "Recruiter Dashboard" -- lists stored interviews, lets you filter by
     role/recommendation, and drill into a full transcript + scores.

Run locally:
    streamlit run app.py

Deploy: see README.md for Streamlit Community Cloud instructions.
"""

import json
from pathlib import Path
import streamlit as st

import db
from agent import InterviewAgent

st.set_page_config(page_title="Interview Screening Agent", page_icon="🎙️", layout="centered")
db.init_db()

QUESTION_BANK_PATH = Path(__file__).parent / "question_bank.json"


@st.cache_resource
def get_agent():
    # auto-detects ANTHROPIC_API_KEY; falls back to heuristic grader if absent
    return InterviewAgent()


def take_interview_view():
    st.title("🎙️ Candidate Interview")
    agent = get_agent()

    if not agent.use_llm:
        st.info(
            "No ANTHROPIC_API_KEY found — running in **heuristic grading mode** "
            "(keyword/length based scoring). Set the key in your environment or "
            "Streamlit secrets for LLM-graded scoring. See README for details.",
            icon="ℹ️",
        )

    with open(QUESTION_BANK_PATH) as f:
        bank = json.load(f)

    if "interview_started" not in st.session_state:
        st.session_state.interview_started = False

    if not st.session_state.interview_started:
        name = st.text_input("Candidate name")
        role = st.selectbox("Role you're interviewing for", list(bank.keys()))
        if st.button("Start Interview", type="primary", disabled=not name):
            st.session_state.interview_started = True
            st.session_state.candidate_name = name
            st.session_state.role = role
            st.session_state.answers = {}
            st.rerun()
        return

    role = st.session_state.role
    questions = bank[role]
    st.subheader(f"Interviewing {st.session_state.candidate_name} for: {role}")

    with st.form("interview_form"):
        answers = {}
        for q in questions:
            st.markdown(f"**{q['question']}**  \n*({q['type']})*")
            answers[q["id"]] = st.text_area("Your answer", key=q["id"], label_visibility="collapsed")
            st.divider()
        submitted = st.form_submit_button("Submit Interview", type="primary")

    if submitted:
        with st.spinner("Scoring answers..."):
            result = agent.run_interview(st.session_state.candidate_name, role, answers)
        st.session_state.interview_started = False
        st.session_state.last_result = result
        st.rerun()

    if "last_result" in st.session_state and not st.session_state.interview_started:
        r = st.session_state.last_result
        st.success(f"Interview complete — graded by **{r['graded_by']}** grader")
        col1, col2 = st.columns(2)
        col1.metric("Overall score", f"{r['overall_score']} / 10")
        col2.metric("Recommendation", r["recommendation"])
        st.write(r["summary"])
        del st.session_state["last_result"]


def dashboard_view():
    st.title("📋 Recruiter Dashboard")

    with open(QUESTION_BANK_PATH) as f:
        bank = json.load(f)

    col1, col2 = st.columns(2)
    role_filter = col1.selectbox("Filter by role", ["All"] + list(bank.keys()))
    rec_filter = col2.selectbox("Filter by recommendation", ["All", "Strong Hire", "Hire", "Unsure", "No Hire"])

    interviews = db.list_interviews(
        role=None if role_filter == "All" else role_filter,
        recommendation=None if rec_filter == "All" else rec_filter,
    )

    if not interviews:
        st.warning("No interviews match this filter yet.")
        return

    st.write(f"**{len(interviews)}** interview(s) found")

    for i in interviews:
        badge = {"Strong Hire": "🟢", "Hire": "🟡", "Unsure": "🟠", "No Hire": "🔴"}.get(i["recommendation"], "⚪")
        with st.expander(
            f"{badge} #{i['id']} — {i['candidate_name']} ({i['role']}) — "
            f"{i['overall_score']}/10 — {i['recommendation']}"
        ):
            st.write(i["summary"])
            detail = db.get_interview(i["id"])
            for a in detail["answers"]:
                st.markdown(f"**Q ({a['question_type']}):** {a['question_text']}")
                st.markdown(f"*A:* {a['answer_text']}")
                st.caption(f"Score: {a['score']}/10 — {a['rationale']}")
                st.divider()


def main():
    st.sidebar.title("Interview Screening Agent")
    view = st.sidebar.radio("View", ["Take Interview", "Recruiter Dashboard"])
    st.sidebar.divider()
    st.sidebar.caption(
        "Built for the Rooman Technologies 24-Hour AI Agent Challenge. "
        "See README.md for architecture, decision boundary, and limitations."
    )
    if view == "Take Interview":
        take_interview_view()
    else:
        dashboard_view()


if __name__ == "__main__":
    main()
