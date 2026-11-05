"""Sample vacancies, marked "(sample)", seeded only while there are none."""

from datetime import timedelta

from sqlalchemy import func, select

from .models import Job, utcnow

S = " (sample)"


def seed(session) -> list[str]:
    if session.scalar(select(func.count(Job.id))):
        return []
    t = utcnow()
    jobs = [
        Job(slug="lecturer-computer-engineering", title="Lecturer, Computer Engineering", department="Department of Computer Engineering",
            kind="faculty", employment="full_time", positions=2,
            summary="Teach undergraduate courses in programming, data structures and computer networks." + S,
            description="Teach two to three undergraduate courses each semester, supervise student projects and take part in curriculum work.\n\nThis is a sample vacancy." + S,
            requirements="ME/MSc in Computer Engineering or a related field.\nAt least two years of teaching or industry experience.\nRegistered with the Nepal Engineering Council." + S,
            closes_at=t + timedelta(days=21), published=True),
        Job(slug="lab-instructor-civil", title="Lab Instructor, Civil Engineering", department="Department of Civil Engineering",
            kind="faculty", employment="full_time", positions=1,
            summary="Run surveying and materials labs for undergraduate students." + S,
            description="This is a sample vacancy." + S, requirements="BE Civil Engineering." + S,
            closes_at=t + timedelta(days=14), published=True),
        Job(slug="it-support-officer", title="IT Support Officer", department="IT Services", kind="staff", employment="full_time",
            positions=1, summary="Keep the campus network, labs and accounts running." + S,
            description="This is a sample vacancy." + S, requirements="Bachelor's in IT or a related field. Networking experience." + S,
            closes_at=t + timedelta(days=10), published=True),
    ]
    session.add_all(jobs)
    session.commit()
    return [f"jobs ({len(jobs)})"]
