"""Starting content: what the home page showed before it became editable.

Each collection is seeded only while it is completely empty, so editors'
work is never overwritten. Invented items are marked "(sample)"; the
leadership names are the real ones supplied by the college.
"""

from datetime import timedelta

from sqlalchemy import func, select

from .models import Banner, Facility, LeadershipMessage, NewsArticle, Notice, utcnow

S = " (sample)"


def _items():
    t = utcnow()
    return {
        "banners": [
            Banner(title="Build what Nepal needs next.",
                   subtitle="Engineering, IT and management programmes affiliated to Pokhara University, taught in Balkumari, Lalitpur since 2001.",
                   image="/assets/img/photos/hero-campus.jpg", image_alt="NCIT main building in Balkumari, Lalitpur",
                   cta_label="Explore programmes", cta_url="/#departments", cta2_label="How to apply", cta2_url="/#apply",
                   published=True, sort_order=1),
            Banner(title="Admissions for Fall 2026 are open.",
                   subtitle="Applications for BE, BCA and BBA programmes close on 15 December 2026." + S,
                   image="/assets/img/photos/hero-admissions.jpg", image_alt="Students working together on a lab project",
                   cta_label="Start your application", cta_url="/#apply", cta2_label="Important dates", cta2_url="/notices",
                   published=True, sort_order=2),
            Banner(title="NCIT Tech Fest 2026",
                   subtitle="Three days of student projects, a 24-hour hackathon and industry talks, 12–14 December on campus." + S,
                   image="/assets/img/photos/hero-techfest.jpg", image_alt="Prize winners at the NCIT tech fest",
                   cta_label="See the programme", cta_url="/#events", published=True, sort_order=3),
        ],
        "leadership": [
            LeadershipMessage(position="executive_director", person_name="Mr. Bijuli Prasad Rana", role_title="Executive Director",
                              excerpt="We want every student who walks through our gate to leave able to build something useful for the people around them." + S,
                              message="The full message from the Executive Director will appear here once it is supplied." + S,
                              photo="/assets/img/photos/executive-director.jpg", published=True, sort_order=1),
            LeadershipMessage(position="director", person_name="Dr. Krishna Chandra Poudel", role_title="Director",
                              excerpt="Our labs stay open late because the best learning happens when students chase their own problems." + S,
                              message="The full message from the Director will appear here once it is supplied." + S,
                              photo="/assets/img/photos/director.jpg", published=True, sort_order=2),
            LeadershipMessage(position="principal", person_name="Er. Niranjan Khakurel", role_title="Principal",
                              excerpt="Discipline in the classroom and curiosity outside it: that is the balance we ask of every student." + S,
                              message="The full message from the Principal will appear here once it is supplied." + S,
                              photo="/assets/img/photos/principal.jpg", published=True, sort_order=3),
        ],
        "news": [
            NewsArticle(slug="robotics-club-irrigation-sensor", category="Student life",
                        title="Robotics club builds a low-cost irrigation sensor for farms in Kavre" + S,
                        summary="Six second-year students designed a soil-moisture sensor that texts farmers when fields need water.",
                        body="Six second-year students designed a soil-moisture sensor that costs less than a mobile recharge card and texts farmers when fields need water.\n\nThis is a sample article. Content Admins replace it from the dashboard.",
                        cover="/assets/img/photos/news-robotics.jpg", published=True, publish_at=t - timedelta(days=14)),
            NewsArticle(slug="convocation-2022-batch", category="Academics",
                        title="Graduates of the 2022 batch receive degrees at Pokhara University convocation" + S,
                        summary="Sample news item.", body="This is a sample article.", cover="/assets/img/photos/news-convocation.jpg",
                        published=True, publish_at=t - timedelta(days=22)),
            NewsArticle(slug="internship-partnership", category="Partnerships",
                        title="New internship partnership with a Kathmandu software company" + S,
                        summary="Sample news item.", body="This is a sample article.", cover="/assets/img/photos/news-mou.jpg",
                        published=True, publish_at=t - timedelta(days=30)),
            NewsArticle(slug="electronics-lab-upgrade", category="Campus",
                        title="Electronics lab upgraded with new oscilloscopes and FPGA boards" + S,
                        summary="Sample news item.", body="This is a sample article.", cover="/assets/img/photos/news-lab.jpg",
                        published=True, publish_at=t - timedelta(days=38)),
        ],
        "notices": [
            Notice(title="Internal examination routine, Fall semester (all BE programmes)" + S, category="exam",
                   published=True, publish_at=t - timedelta(days=2)),
            Notice(title="Entrance preparation classes begin 3 November" + S, category="admission",
                   published=True, publish_at=t - timedelta(days=5)),
            Notice(title="College closed for Tihar, 8–12 November" + S, category="holiday",
                   published=True, publish_at=t - timedelta(days=11)),
            Notice(title="Spring semester board results published by Pokhara University" + S, category="result",
                   link_url="https://pu.edu.np", published=True, publish_at=t - timedelta(days=17)),
        ],
        "facilities": [
            Facility(name="Library", icon="library", published=True, sort_order=1),
            Facility(name="Computer labs", icon="monitor", published=True, sort_order=2),
            Facility(name="Electronics labs", icon="cpu", published=True, sort_order=3),
            Facility(name="Engineering labs", icon="flask-conical", published=True, sort_order=4),
            Facility(name="Canteen", icon="utensils", published=True, sort_order=5),
            Facility(name="Transport", icon="bus", published=True, sort_order=6),
        ],
    }


def seed(session) -> list[str]:
    created = []
    for name, items in _items().items():
        model = type(items[0])
        if session.scalar(select(func.count()).select_from(model)):
            continue
        for item in items:
            item.updated_by = "seed"
            session.add(item)
        created.append(name)
    session.commit()
    return created
