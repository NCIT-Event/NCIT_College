"""Sample verified alumni for the directory and the home page, marked "(sample)", seeded only while there are none."""

from sqlalchemy import func, select

from .models import AlumniProfile, utcnow

S = " (sample)"
ALUMNI = [
    ("Sample Alumnus A", "BE Computer Engineering", "2012", "Engineering manager", "A software company", "Kathmandu", "/assets/img/photos/alumni-1.jpg"),
    ("Sample Alumna B", "BE Information Technology", "2015", "Founder", "An agritech start-up", "Lalitpur", "/assets/img/photos/alumni-2.jpg"),
    ("Sample Alumnus C", "BE Civil Engineering", "2010", "Structural engineer", "A consulting firm", "Pokhara", "/assets/img/photos/alumni-3.jpg"),
    ("Sample Alumna D", "Master of Computer Information Systems", "2018", "Data analyst", "A bank", "Lalitpur", "/assets/img/photos/alumni-4.jpg"),
]


def seed(session) -> list[str]:
    if session.scalar(select(func.count(AlumniProfile.id))):
        return []
    t = utcnow()
    for n, (name, prog, year, role, org, city, photo) in enumerate(ALUMNI, start=1):
        session.add(AlumniProfile(email=f"sample.alumni{n}@example.com", full_name=name + S, programme=prog, graduation_year=year,
                                  registration_no=f"SAMPLE-{n}", current_role=role, employer=org + S, city=city, photo=photo,
                                  show_in_directory=True, status="verified", featured=True, verified_by="seed",
                                  verified_at=t, submitted_at=t))
    session.commit()
    return [f"alumni ({len(ALUMNI)})"]
