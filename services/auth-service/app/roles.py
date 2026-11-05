"""Role catalogue and scope rules.

Department scopes live here until academics-service (Phase 3) owns the
department list; then auth-service reads them from its events instead.
"""

ROLES = {
    "super_admin": {"name": "Super Admin", "scope": None},
    "content_admin": {"name": "Content Admin", "scope": None},
    "event_admin": {"name": "Event Admin", "scope": None},
    "eca_admin": {"name": "ECA Admin", "scope": None},
    "hod": {"name": "Head of Department", "scope": "dept"},
    "admission_officer": {"name": "Admission Officer", "scope": None},
    "hr_officer": {"name": "HR Officer", "scope": None},
    "alumni_coordinator": {"name": "Alumni Coordinator", "scope": None},
    "teacher": {"name": "Teacher", "scope": None},
    "student": {"name": "Student", "scope": None},
}

# With DEV_LOGIN, `flask bootstrap` creates these demo accounts (<name>@<domain>) for local testing only.
DEMO_ADMINS = {"content_admin": "content.admin", "event_admin": "event.admin", "eca_admin": "eca.admin",
               "admission_officer": "admissions.officer", "hr_officer": "hr.officer",
               "alumni_coordinator": "alumni.coordinator"}

# Roles that outside accounts (applicants, alumni) get by signing in with an emailed code.
# They are never granted from the dashboard and never give access to it.
EXTERNAL_ROLES = {"applicant": "Applicant", "alumni": "Alumni"}

DEPARTMENTS = {
    "computer": "Computer Engineering",
    "it": "Information Technology",
    "software": "Software Engineering",
    "ice": "Information & Communication",
    "civil": "Civil Engineering",
    "architecture": "Architecture",
    "bca": "Computer Applications & Science",
    "management": "Management",
}


def normalise_scope(role: str, scope: str | None) -> str:
    """Return the stored scope for a grant, or raise ValueError with a message for the user."""
    spec = ROLES.get(role)
    if spec is None:
        raise ValueError("Choose a role from the list.")
    if spec["scope"] == "dept":
        key = (scope or "").removeprefix("dept:")
        if key not in DEPARTMENTS:
            raise ValueError("Choose the department this Head of Department manages.")
        return f"dept:{key}"
    return "*"


def scope_label(scope: str) -> str:
    if scope.startswith("dept:"):
        return DEPARTMENTS.get(scope[5:], scope[5:])
    return ""


def catalogue() -> dict:
    return {
        "roles": [{"code": k, "name": v["name"], "scoped": v["scope"]} for k, v in ROLES.items()],
        "departments": [{"code": k, "name": v} for k, v in DEPARTMENTS.items()],
    }
