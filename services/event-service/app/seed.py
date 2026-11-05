"""Sample events, so the calendar isn't empty before Event Admins add real ones.

Seeded only while there are no events at all, so editors' work is never
overwritten. Every sample is marked "(sample)". Dates are relative to the
day the database was first set up (Tech Fest matches the home page banner).
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from .models import Event, utcnow

S = " (sample)"
NPT = timedelta(hours=5, minutes=45)


def _at(day: datetime, hour: int, minute: int = 0) -> datetime:
    """A Nepal-time clock time on `day`, stored in UTC."""
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=UTC) - NPT


def _items():
    t = utcnow()
    fest = datetime(2026, 12, 12, tzinfo=UTC)
    if fest < t + timedelta(days=7):
        fest = t + timedelta(days=40)
    d = lambda n: t + timedelta(days=n)
    return [
        Event(slug="ncit-tech-fest-2026", title="NCIT Tech Fest 2026", category="technical", organizer="NCIT Student Council",
              venue="Main campus", start_at=_at(fest, 9), end_at=_at(fest + timedelta(days=2), 17),
              summary="Three days of student projects, a 24-hour hackathon and industry talks." + S,
              body="Project exhibitions from every department, a 24-hour hackathon with teams of up to four, and talks from "
                   "engineers working in Nepal's software, telecom and construction industries.\n\n"
                   "Hackathon teams register here; the exhibition is open to everyone.\n\nThis is a sample event." + S,
              cover="/assets/img/photos/hero-techfest.jpg", cover_alt="Prize winners at the NCIT tech fest",
              registration_open=True, capacity=120, registration_closes_at=_at(fest - timedelta(days=3), 17),
              published=True),
        Event(slug="open-day", title="Open day for prospective students and parents", category="academic",
              organizer="Admissions office", venue="Main campus", start_at=_at(d(9), 10), end_at=_at(d(9), 15),
              summary="Campus tours every hour, lab demonstrations and a question session with HODs." + S,
              body="Meet the Heads of Department, see the labs and ask about programmes, fees and scholarships.\n\nThis is a sample event." + S,
              registration_open=True, capacity=0, published=True),
        Event(slug="workshop-cloud-deployment", title="Workshop: deploying your first web app to the cloud", category="workshop",
              organizer="Department of Computer Engineering", venue="Computer lab 3", start_at=_at(d(16), 13), end_at=_at(d(16), 16),
              summary="Hands-on: containers, a database and a domain name in one afternoon. Bring a laptop." + S,
              body="A hands-on workshop for second- and third-year students.\n\nThis is a sample event." + S,
              registration_open=True, capacity=30, published=True),
        Event(slug="guest-lecture-payments", title="Guest lecture: building payment systems for Nepal", category="seminar",
              organizer="Department of IT", venue="Seminar hall", start_at=_at(d(-4), 14), end_at=_at(d(-4), 16),
              summary="An engineer from a Kathmandu fintech on QR payments, settlement and fraud." + S,
              body="This is a sample event." + S, published=True),
        Event(slug="futsal-quarter-finals", title="Inter-college futsal tournament: quarter-finals", category="sports",
              organizer="Sports Club", venue="College ground", start_at=_at(d(-6), 16), end_at=_at(d(-6), 18),
              summary="NCIT against Kathmandu Engineering College." + S, body="This is a sample event." + S, published=True),
    ]


def seed(session) -> list[str]:
    if session.scalar(select(func.count(Event.id))):
        return []
    items = _items()
    session.add_all(items)
    session.commit()
    return [f"events ({len(items)})"]
