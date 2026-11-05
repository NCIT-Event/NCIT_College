"""Sample clubs (the ones the home page listed) and a few activities.

Seeded only while there are no clubs at all, so editors' work is never
overwritten. Every sample is marked "(sample)".
"""

from datetime import timedelta

from sqlalchemy import func, select

from .models import Activity, Club, utcnow

S = " (sample)"

CLUBS = [
    ("robotics-club", "Robotics Club", "technical", "Build robots, drones and sensors; compete at national robotics events.",
     "Fridays 15:00 · Electronics lab", "/assets/img/photos/news-robotics.jpg", "Robotics club members testing a line-following robot"),
    ("coding-club", "Coding Club", "technical", "Weekly problem solving, open-source sprints and the campus hackathon.",
     "Wednesdays 16:00 · Computer lab 3", "", ""),
    ("sports-club", "Sports Club", "sports", "Futsal, basketball, table tennis and chess, with inter-college tournaments.",
     "Daily 16:00 · College ground", "/assets/img/photos/campus-sports.jpg", "Students playing futsal"),
    ("music-cultural-club", "Music & Cultural Club", "cultural", "Music, dance and drama; organises Teej, Tihar and annual-day programmes.",
     "Thursdays 15:30 · Auditorium", "", ""),
    ("photography-club", "Photography Club", "arts", "Photo walks around the valley, editing workshops and the yearly exhibition.",
     "Saturdays (monthly) · Meets at the main gate", "", ""),
]


def seed(session) -> list[str]:
    if session.scalar(select(func.count(Club.id))):
        return []
    t = utcnow()
    clubs = []
    for n, (slug, name, category, tagline, meets, photo, alt) in enumerate(CLUBS, start=1):
        clubs.append(Club(slug=slug, name=name, category=category, tagline=tagline + S,
                          about=f"{tagline}\n\nThis is a sample club description. ECA Admins replace it from the dashboard." + S,
                          meeting_info=meets, photo=photo, photo_alt=alt, coordinator_name="Staff coordinator (sample)",
                          join_open=True, published=True, sort_order=n))
    session.add_all(clubs)
    session.flush()
    robotics, coding, sports = clubs[0], clubs[1], clubs[2]
    activities = [
        Activity(club_id=robotics.id, title="Soil-moisture sensor tested with farmers in Kavre" + S, happened_on=t - timedelta(days=14),
                 body="Members took the prototype to three farms and collected a week of readings." + S,
                 photo="/assets/img/photos/news-robotics.jpg", photo_alt="Robotics club members testing a sensor", published=True),
        Activity(club_id=coding.id, title="Open-source sprint: 14 pull requests merged" + S, happened_on=t - timedelta(days=9),
                 body="A Saturday sprint on Nepali-language tooling." + S, published=True),
        Activity(club_id=sports.id, title="Futsal team reaches the inter-college quarter-finals" + S, happened_on=t - timedelta(days=6),
                 body="See the events calendar for the match." + S, published=True),
    ]
    session.add_all(activities)
    session.commit()
    return [f"clubs ({len(clubs)})", f"activities ({len(activities)})"]
