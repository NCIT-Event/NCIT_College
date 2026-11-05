"""A sample intake with the programmes NCIT offers, so the Admissions page isn't empty.

Seeded only while there are no intakes, so the office's work is never
overwritten. Seats, dates and eligibility text are samples, marked "(sample)".
"""

from datetime import timedelta

from sqlalchemy import func, select

from .models import Intake, Offering, utcnow

S = " (sample)"
BE = "Passed +2 Science (or equivalent) with Physics and Mathematics, minimum C+ in each, and the Pokhara University entrance test."
PROGRAMMES = [
    ("BE Computer Engineering", "computer", 48, BE),
    ("BE Information Technology", "it", 48, BE),
    ("BE Software Engineering", "software", 48, BE),
    ("BE Information & Communication Engineering", "ice", 48, BE),
    ("BE Civil Engineering", "civil", 48, BE),
    ("Bachelor of Architecture", "architecture", 24, BE),
    ("Bachelor of Computer Applications", "bca", 36, "Passed +2 in any stream with at least a C grade in each subject."),
    ("Bachelor of Business Administration", "management", 48, "Passed +2 in any stream with at least a C grade in each subject."),
]


def seed(session) -> list[str]:
    if session.scalar(select(func.count(Intake.id))):
        return []
    t = utcnow()
    intake = Intake(slug="fall-2026", name="Fall 2026", opens_at=t - timedelta(days=7), closes_at=t + timedelta(days=43),
                    intro="Apply online for the Fall 2026 intake. Keep your +2 transcript (PDF) and a passport-size photo ready. "
                          "You can save your application and come back to it before you send it." + S,
                    published=True)
    session.add(intake)
    session.flush()
    for n, (name, dept, seats, rule) in enumerate(PROGRAMMES, start=1):
        session.add(Offering(intake_id=intake.id, programme=name, department=dept, level="bachelor", seats=seats,
                             eligibility=rule + S, fee_note="See the fee structure from the admissions office." + S,
                             published=True, sort_order=n))
    session.commit()
    return ["intakes (1)", f"offerings ({len(PROGRAMMES)})"]
