"""
seed_data.py
Populates data/interviews.db with a handful of realistic sample interviews
so reviewers can inspect a working database without running a live session.

Uses the heuristic grader by default (no API key required) so this script
runs anywhere out of the box. Set ANTHROPIC_API_KEY before running if you
want the seed data graded by the LLM instead.

Usage:
    python seed_data.py
"""

import db
from agent import InterviewAgent

SAMPLE_CANDIDATES = [
    {
        "name": "Asha Rao",
        "role": "Backend Developer",
        "answers": {
            "bd1": "SQL databases are relational, they enforce a schema and guarantee ACID consistency, "
                   "good for structured data like financial records. NoSQL databases like MongoDB store "
                   "documents, they scale horizontally more easily, for example a system with rapidly "
                   "changing schema or huge write volume would benefit from NoSQL.",
            "bd2": "I'd implement a token bucket algorithm, storing counters in Redis so it works across "
                   "distributed servers. Each user gets a bucket that refills at a fixed rate, and requests "
                   "are throttled once the bucket is empty. For example, 100 requests per minute per API key.",
            "bd3": "We had a production outage last quarter, I checked our monitoring dashboards and logs, "
                   "found the root cause was a bad deploy that skipped a migration, rolled it back within "
                   "10 minutes, and wrote a postmortem for the team with follow-up action items.",
            "bd4": "I disagreed with a teammate about using a queue vs synchronous calls for a notification "
                   "service. We discussed tradeoffs, I pulled latency data showing the queue would reduce "
                   "load spikes, we compromised on a hybrid approach and it worked well in production.",
        },
    },
    {
        "name": "Marcus Chen",
        "role": "Backend Developer",
        "answers": {
            "bd1": "SQL is for structured data, NoSQL is for unstructured data.",
            "bd2": "You could use rate limiting with a cache maybe, not totally sure on specifics.",
            "bd3": "I just fixed it and moved on, don't remember exact steps.",
            "bd4": "We didn't really disagree much, I usually just go with what the team decides.",
        },
    },
    {
        "name": "Priya Nair",
        "role": "Data Analyst",
        "answers": {
            "da1": "I usually check the percentage of missing values first. For small amounts I might use "
                   "median imputation, for large gaps I'd consider dropping the column or flagging the bias "
                   "it might introduce. It really depends on whether the data is missing at random.",
            "da2": "Correlation just means two variables move together, causation means one directly causes "
                   "the other. To test causation I'd run a controlled A/B test or use regression with control "
                   "variables to account for confounders, since correlation alone can't rule those out.",
            "da3": "I presented a churn analysis showing a feature change was hurting retention. Stakeholders "
                   "pushed back initially, so I visualized the cohort data more clearly and we agreed on a "
                   "smaller rollout to validate before a full launch.",
            "da4": "For a messy requirements project I scheduled a clarifying call with stakeholders, wrote "
                   "down explicit assumptions in the doc, and iterated on the first draft with them weekly.",
        },
    },
    {
        "name": "Devon Whitfield",
        "role": "General / Entry-Level",
        "answers": {
            "gen1": "I'm interested because I want to grow my skills and this seems like a good company.",
            "gen2": "I once failed a project deadline because I underestimated the scope, I learned to break "
                    "tasks into smaller pieces and communicate early if I'm behind, for example now I check in "
                    "with my manager weekly.",
            "gen3": "I make a list and prioritize by deadline and importance, and I communicate to my manager "
                    "if I think something urgent will slip so we can re-prioritize together.",
        },
    },
]


def main():
    db.init_db()
    agent = InterviewAgent(use_llm=False)  # heuristic grader, no API key needed

    for candidate in SAMPLE_CANDIDATES:
        result = agent.run_interview(candidate["name"], candidate["role"], candidate["answers"])
        print(
            f"Seeded: {result['candidate_name']} ({result['role']}) "
            f"-> score={result['overall_score']} recommendation={result['recommendation']}"
        )

    print(f"\nDone. Database at: {db.DB_PATH}")


if __name__ == "__main__":
    main()
