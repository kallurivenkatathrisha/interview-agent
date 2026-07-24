"""
query_demo.py
Demonstrates retrieving and listing stored interview records from the
database, as required by the challenge deliverables.

Usage:
    python query_demo.py
"""

import db


def line(char="-", n=70):
    print(char * n)


def main():
    print("=" * 70)
    print("QUERY 1: List all stored interviews")
    print("=" * 70)
    interviews = db.list_interviews()
    for i in interviews:
        print(
            f"  #{i['id']:<3} {i['candidate_name']:<18} {i['role']:<22} "
            f"score={i['overall_score']:<5} -> {i['recommendation']}"
        )

    print()
    print("=" * 70)
    print("QUERY 2: Filter interviews by role = 'Backend Developer'")
    print("=" * 70)
    backend = db.list_interviews(role="Backend Developer")
    for i in backend:
        print(f"  #{i['id']} {i['candidate_name']} -> {i['recommendation']} ({i['overall_score']})")

    print()
    print("=" * 70)
    print("QUERY 3: Filter interviews flagged 'Unsure' for human review")
    print("=" * 70)
    unsure = db.list_interviews(recommendation="Unsure")
    for i in unsure:
        print(f"  #{i['id']} {i['candidate_name']} ({i['role']}) -> {i['summary']}")

    print()
    print("=" * 70)
    print("QUERY 4: Full detail (questions + answers + per-answer scores) for interview #1")
    print("=" * 70)
    detail = db.get_interview(1)
    if detail:
        print(f"  Candidate: {detail['candidate_name']}  |  Role: {detail['role']}")
        print(f"  Overall score: {detail['overall_score']}  |  Recommendation: {detail['recommendation']}")
        print(f"  Summary: {detail['summary']}")
        line()
        for ans in detail["answers"]:
            print(f"  Q ({ans['question_type']}): {ans['question_text']}")
            print(f"  A: {ans['answer_text']}")
            print(f"  Score: {ans['score']}/10  |  {ans['rationale']}")
            line()


if __name__ == "__main__":
    main()
