"""JSON shapes for the public page and the editor."""

from itertools import groupby


def _num(value) -> float:
    number = float(value)
    return int(number) if number.is_integer() else number


def course(c) -> dict:
    return {"id": c.id, "semester": c.semester, "code": c.code, "title": c.title, "credits": _num(c.credits)}


def programme(p) -> dict:
    semesters = []
    for number, items in groupby(sorted(p.courses, key=lambda c: (c.semester, c.sort_order)), key=lambda c: c.semester):
        items = list(items)
        semesters.append({"semester": number, "courses": [course(c) for c in items],
                          "total_credits": _num(sum(float(c.credits) for c in items))})
    return {
        "id": p.id, "name": p.name, "level": p.level, "duration_years": p.duration_years,
        "semester_count": p.duration_years * 2, "affiliation": p.affiliation, "eligibility": p.eligibility,
        "description": p.description, "syllabus_url": p.syllabus_url, "semesters": semesters,
    }


def faculty(f) -> dict:
    return {"id": f.id, "name": f.name, "designation": f.designation, "specialization": f.specialization,
            "email": f.email, "photo": f.photo}


def lab(x) -> dict:
    return {"id": x.id, "name": x.name, "description": x.description, "photo": x.photo}


def testimonial(t) -> dict:
    return {"id": t.id, "student_name": t.student_name, "programme_label": t.programme_label,
            "quote": t.quote, "photo": t.photo, "approved": t.approved}


CHILD_SERIALIZERS = {"programmes": programme, "faculty": faculty, "labs": lab, "testimonials": testimonial}


def summary(d) -> dict:
    return {"slug": d.slug, "name": d.name, "tagline": d.tagline, "published": d.published,
            "programmes": [p.name for p in d.programmes], "updated_at": d.updated_at.isoformat()}


def department(d, *, public: bool) -> dict:
    data = {
        "slug": d.slug, "name": d.name, "tagline": d.tagline, "overview": d.overview, "hero_photo": d.hero_photo,
        "contact": {"email": d.contact_email, "phone": d.contact_phone, "office": d.office},
        "hod": {"name": d.hod_name, "title": d.hod_title, "message": d.hod_message, "photo": d.hod_photo},
        "programmes": [programme(p) for p in d.programmes],
        "faculty": [faculty(f) for f in d.faculty],
        "labs": [lab(x) for x in d.labs],
        "testimonials": [testimonial(t) for t in d.testimonials if t.approved or not public],
        "updated_at": d.updated_at.isoformat(),
    }
    if public:
        for t in data["testimonials"]:
            t.pop("approved")
    else:
        data.update(published=d.published, updated_by=d.updated_by)
    return data
