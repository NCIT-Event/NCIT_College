"""Starting data: the eight departments, their programmes and starter content.

Every department starts with the same kind of content as Computer Engineering
(introduction, overview, HOD message, semester-1 courses, faculty, labs and a
testimonial) so all pages look complete from day one. Starter text is marked
"(sample)"; each HOD replaces it from the dashboard.

Rules that keep HOD work safe:
- `seed()` creates missing departments with starter content and never touches
  an existing one.
- `fill_starter_content()` (the `--starter-content` option) adds starter
  content to existing departments only if nobody has edited them yet
  (updated_by is still "seed") and only to sections that are empty.
"""

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .models import Course, Department, Faculty, Lab, Programme, Testimonial

SAMPLE = " (sample)"

DEPARTMENTS = [
    ("computer", "Computer Engineering", [("BE Computer Engineering", "bachelor", 4), ("ME Computer Engineering", "master", 2)],
     {"hod_name": "Er. Amit Kumar Shrivastava", "hod_title": "Head of Department, Computer Engineering",
      "hod_photo": "/assets/img/photos/hod-computer.jpg"}),
    ("it", "Information Technology", [("BE Information Technology", "bachelor", 4),
                                      ("Master of Computer Information Systems", "master", 2)], {}),
    ("software", "Software Engineering", [("BE Software Engineering", "bachelor", 4)], {}),
    ("ice", "Information & Communication", [("BE Information & Communication Engineering", "bachelor", 4)], {}),
    ("civil", "Civil Engineering", [("BE Civil Engineering", "bachelor", 4)], {}),
    ("architecture", "Architecture", [("Bachelor of Architecture", "bachelor", 5)], {}),
    ("bca", "Computer Applications & Science", [("Bachelor of Computer Applications", "bachelor", 4),
                                                ("MSc Computer Science", "master", 2)], {}),
    ("management", "Management", [("Bachelor of Business Administration", "bachelor", 4)], {}),
]

ENGINEERING_SEM1 = [("Engineering Mathematics I", 3), ("Engineering Physics", 4), ("Programming in C", 3),
                    ("Basic Electrical Engineering", 3), ("Engineering Drawing", 2)]

# What differs between departments: the subject focus, two labs and semester-1 courses.
STARTER = {
    "computer": ("hardware, software and the systems that connect them",
                 "programming, digital logic, microprocessors, computer networks and embedded systems",
                 [("Microprocessor & embedded lab", "Trainer kits, microcontroller boards and measurement equipment."),
                  ("Computer networks lab", "Routers and switches for configuration and routing practicals.")],
                 ENGINEERING_SEM1),
    "it": ("information systems that organisations run on",
           "programming, databases, web technologies, networking and information security",
           [("Programming & database lab", "Workstations for programming, database and web development practicals."),
            ("Networking & security lab", "Network equipment and tools for security and administration practicals.")],
           ENGINEERING_SEM1),
    "software": ("designing, building and maintaining reliable software",
                 "programming, software design, testing, project management and team projects",
                 [("Software development lab", "Workstations with development tools for coursework and team projects."),
                  ("Project studio", "Space for team projects, reviews and demonstrations.")],
                 ENGINEERING_SEM1),
    "ice": ("communication systems and the information they carry",
            "electronics, signals, communication systems, networking and information processing",
            [("Electronics lab", "Oscilloscopes, signal generators and components for circuit practicals."),
             ("Communication systems lab", "Trainer kits for analogue and digital communication practicals.")],
            [("Engineering Mathematics I", 3), ("Engineering Physics", 4), ("Programming in C", 3),
             ("Basic Electronics", 3), ("Engineering Drawing", 2)]),
    "civil": ("planning, designing and building the infrastructure people rely on",
              "structures, surveying, materials, construction and water resources",
              [("Surveying lab", "Total stations, levels and theodolites for field practicals."),
               ("Materials & soil lab", "Equipment for testing concrete, aggregates and soil.")],
              [("Engineering Mathematics I", 3), ("Engineering Physics", 4), ("Engineering Mechanics", 3),
               ("Engineering Drawing", 2), ("Workshop Technology", 2)]),
    "architecture": ("designing buildings and spaces for people and their communities",
                     "architectural design studios, drawing, building technology, history and planning",
                     [("Design studio", "Studio space for design projects, models and reviews."),
                      ("Model-making workshop", "Tools and materials for physical models.")],
                     [("Architectural Design I", 6), ("Graphics & Drawing I", 3), ("History of Architecture I", 2),
                      ("Building Materials", 3), ("Mathematics for Architects", 2)]),
    "bca": ("computing and software for the real world",
            "programming, databases, web development, networking and software projects",
            [("Computer lab", "Workstations for programming and database practicals."),
             ("Project lab", "Space and equipment for student software projects.")],
            [("Computer Fundamentals & Applications", 3), ("Mathematics I", 3), ("Programming in C", 3),
             ("Digital Logic", 3), ("English I", 3)]),
    "management": ("business, management and entrepreneurship",
                   "accounting, finance, marketing, management, business communication and case studies",
                   [("Business computing lab", "Workstations with accounting and productivity software."),
                    ("Case study room", "Seminar room for discussions, presentations and case studies.")],
                   [("Principles of Management", 3), ("Business Mathematics I", 3), ("Financial Accounting I", 3),
                    ("Microeconomics", 3), ("Business Communication", 3)]),
}


def _starter_fields(slug: str, name: str) -> dict:
    focus, topics, _labs, _courses = STARTER.get(slug, STARTER["computer"])
    return {
        "tagline": f"{focus[0].upper()}{focus[1:]}.{SAMPLE}",
        "overview": (f"The Department of {name} teaches {focus} through lectures, labs and project work, "
                     f"following the Pokhara University curriculum. Coursework covers {topics}.\n\n"
                     "In the final year, students complete a project with a supervisor from the department. "
                     "(Sample text: the Head of Department replaces it from the dashboard.)"),
        "hod_name": "HOD name" + SAMPLE,
        "hod_title": f"Head of Department, {name}",
        "hod_message": (f"Welcome to the Department of {name}. We want every student to leave able to apply what "
                        f"they learn to real problems in Nepal and beyond.{SAMPLE}"),
    }


def _add_starter_content(d: Department, *, only_empty: bool) -> None:
    _focus, _topics, labs, courses = STARTER.get(d.slug, STARTER["computer"])
    for field, value in _starter_fields(d.slug, d.name).items():
        if not only_empty or not getattr(d, field):
            setattr(d, field, value)
    first = d.programmes[0] if d.programmes else None
    if first is not None and not first.courses:
        for i, (title, credits) in enumerate(courses, start=1):
            first.courses.append(Course(semester=1, code="", title=title + SAMPLE, credits=credits, sort_order=i))
    if not d.faculty:
        d.faculty.append(Faculty(name="Faculty member" + SAMPLE, designation="Associate Professor", sort_order=1))
        d.faculty.append(Faculty(name="Faculty member" + SAMPLE, designation="Lecturer", sort_order=2))
    if not d.labs:
        for i, (lab_name, desc) in enumerate(labs, start=1):
            d.labs.append(Lab(name=lab_name + SAMPLE, description=desc, sort_order=i))
    if not d.testimonials:
        d.testimonials.append(Testimonial(
            student_name="Student name" + SAMPLE, programme_label=f"{first.name if first else d.name}, final year",
            quote="The labs and the teachers' support made the difference for me." + SAMPLE,
            approved=True, sort_order=1))


def seed(session) -> list[str]:
    """Create missing departments (with starter content). Existing departments are untouched."""
    created = []
    for order, (slug, name, programmes, extra) in enumerate(DEPARTMENTS, start=1):
        if session.scalar(select(Department.id).where(Department.slug == slug)):
            continue
        d = Department(slug=slug, name=name, sort_order=order, published=True, updated_by="seed", **extra)
        for p_order, (p_name, level, years) in enumerate(programmes, start=1):
            d.programmes.append(Programme(name=p_name, level=level, duration_years=years, sort_order=p_order))
        _add_starter_content(d, only_empty=True)
        session.add(d)
        created.append(slug)
    session.commit()
    return created


def fill_starter_content(session) -> list[str]:
    """Add starter content to departments nobody has edited yet, in empty sections only."""
    filled = []
    rows = session.scalars(select(Department).options(
        selectinload(Department.programmes).selectinload(Programme.courses), selectinload(Department.faculty),
        selectinload(Department.labs), selectinload(Department.testimonials))).all()
    for d in rows:
        if d.updated_by != "seed":
            continue
        _add_starter_content(d, only_empty=True)
        filled.append(d.slug)
    session.commit()
    return filled
