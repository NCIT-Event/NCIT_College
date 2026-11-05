"""What editors may change, with limits and friendly validation messages."""

from functools import partial

from ncit_common.fields import Field as _Field
from ncit_common.fields import apply  # noqa: F401  (re-exported for the routes)

from .models import Faculty, Lab, Programme, Testimonial

# Uploaded photos live under /media/academics/
Field = partial(_Field, media_root="academics")


DEPARTMENT_FIELDS = {
    "name": Field("Department name", max_len=120, required=True),
    "tagline": Field("Short introduction", max_len=300),
    "overview": Field("Overview", "text", max_len=6000),
    "hero_photo": Field("Department photo", "media", max_len=300),
    "contact_email": Field("Contact email", "email", max_len=254),
    "contact_phone": Field("Contact phone", max_len=60),
    "office": Field("Office location", max_len=200),
    "hod_name": Field("HOD name", max_len=120),
    "hod_title": Field("HOD title", max_len=160),
    "hod_message": Field("HOD message", "text", max_len=4000),
    "hod_photo": Field("HOD photo", "media", max_len=300),
    "published": Field("Published", "bool"),
}
# Only a Super Admin renames a department or changes its place in the list.
SUPER_ONLY = {"name", "sort_order"}

CHILDREN = {
    "programmes": (Programme, {
        "name": Field("Programme name", max_len=160, required=True),
        "level": Field("Level", max_len=20, choices=("bachelor", "master")),
        "duration_years": Field("Duration", "int", lo=1, hi=6),
        "affiliation": Field("Affiliation", max_len=120),
        "eligibility": Field("Eligibility", "text", max_len=2000),
        "description": Field("Description", "text", max_len=4000),
        "syllabus_url": Field("Syllabus link", "url", max_len=300),
    }),
    "faculty": (Faculty, {
        "name": Field("Name", max_len=120, required=True),
        "designation": Field("Designation", max_len=120),
        "specialization": Field("Subjects or research", max_len=200),
        "email": Field("Email", "email", max_len=254),
        "photo": Field("Photo", "media", max_len=300),
    }),
    "labs": (Lab, {
        "name": Field("Lab name", max_len=160, required=True),
        "description": Field("Description", "text", max_len=2000),
        "photo": Field("Photo", "media", max_len=300),
    }),
    "testimonials": (Testimonial, {
        "student_name": Field("Student name", max_len=120, required=True),
        "programme_label": Field("Programme and year", max_len=160),
        "quote": Field("Quote", "text", max_len=1200, required=True),
        "photo": Field("Photo", "media", max_len=300),
        "approved": Field("Show on the page", "bool"),
    }),
}

COURSE_FIELDS = {
    "code": Field("Course code", max_len=20),
    "title": Field("Course title", max_len=200, required=True),
    "credits": Field("Credits", "num", lo=0, hi=12),
}

