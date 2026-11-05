"""The emails the website sends. Plain text, short, and in the college's voice.

Each template is fn(data) -> (subject, body). Services queue a template name
plus data (ncit_common.mail); nothing else decides what an email says.
"""

SITE = "https://ncit.edu.np"
SIGN_OFF = "\n\nNepal College of Information Technology\nBalkumari, Lalitpur · 01-5186354\n\nThis email was sent by the NCIT website. Please don't reply to it."

PURPOSE = {"applicant": "your application", "alumni": "the alumni network"}

ADMISSION_STATUS = {
    "under_review": ("Your application is being reviewed",
                     "The admissions office has started reviewing your application. We'll email you when there's news."),
    "documents_requested": ("We need more from you",
                            "The admissions office needs something more before it can continue. Sign in to see what's needed and update your application."),
    "accepted": ("Congratulations: you've been offered a place",
                 "We're delighted to offer you a place. Sign in to see the next steps, including fee payment and enrolment dates."),
    "waitlisted": ("You're on the waiting list",
                   "Your application is on the waiting list. If a place becomes available we'll email you straight away."),
    "rejected": ("About your application",
                 "Thank you for applying. We're sorry we can't offer you a place this time."),
}

JOB_STATUS = {
    "shortlisted": ("You've been shortlisted", "Your application has been shortlisted. We'll contact you about the next step."),
    "interview": ("Interview invitation", "We'd like to invite you to an interview. Details are below and in your application page."),
    "offered": ("Job offer", "We're pleased to offer you the position. Sign in to see the details."),
    "rejected": ("About your application", "Thank you for applying. We won't be taking your application further this time."),
}


def _hello(data):
    return f"Dear {data.get('name') or 'applicant'},\n\n"


def _note(data):
    note = (data.get("message") or "").strip()
    return f"\n\nMessage from the college:\n{note}" if note else ""


def sign_in_code(d):
    return (f"Your NCIT sign-in code: {d['code']}",
            f"Your sign-in code for {PURPOSE.get(d.get('purpose'), 'the NCIT website')} is:\n\n    {d['code']}\n\n"
            f"It works once, for {d.get('minutes', 10)} minutes. If you didn't ask for it, you can ignore this email." + SIGN_OFF)


def application_submitted(d):
    return (f"Application received: {d['reference']}",
            _hello(d) + f"We've received your application for {d['programme']} ({d['intake']}).\n\n"
            f"Your reference number is {d['reference']}. Keep it for any questions.\n\n"
            f"Track your application at {SITE}/apply" + SIGN_OFF)


def application_status(d):
    subject, text = ADMISSION_STATUS.get(d["status"], ("Your application has been updated", "Your application status has changed."))
    return (f"{subject} ({d['reference']})",
            _hello(d) + f"{text}\n\nProgramme: {d['programme']}\nReference: {d['reference']}" + _note(d)
            + f"\n\nSee your application at {SITE}/apply" + SIGN_OFF)


def job_application_received(d):
    return (f"Application received: {d['job']}",
            _hello(d) + f"Thank you for applying for {d['job']}. We've received your application and will be in touch.\n\n"
            f"Follow its progress at {SITE}/careers" + SIGN_OFF)


def job_application_status(d):
    subject, text = JOB_STATUS.get(d["status"], ("Your application has been updated", "Your application status has changed."))
    return (f"{subject}: {d['job']}", _hello(d) + text + _note(d) + f"\n\nSee your application at {SITE}/careers" + SIGN_OFF)


def alumni_status(d):
    if d["status"] == "verified":
        return ("You're verified as NCIT alumni",
                _hello(d) + "Welcome back. Your alumni profile has been verified"
                + (" and now appears in the alumni directory." if d.get("listed") else ".")
                + f"\n\nUpdate it any time at {SITE}/alumni/join" + SIGN_OFF)
    return ("About your alumni registration",
            _hello(d) + "We couldn't verify your alumni registration from our records." + _note(d)
            + f"\n\nYou can correct your details and send it again at {SITE}/alumni/join" + SIGN_OFF)


def contact_message(d):
    return (f"Website enquiry ({d['topic']}): {d['name']}",
            f"A message from the Contact page of the website.\n\nFrom: {d['name']} <{d['email']}>\n"
            + (f"Phone: {d['phone']}\n" if d.get("phone") else "") + f"Topic: {d['topic']}\n\n{d['message']}\n\n"
            f"Reply to {d['email']} directly; this address can't receive replies." + SIGN_OFF)


TEMPLATES = {
    "contact_message": contact_message,
    "sign_in_code": sign_in_code,
    "application_submitted": application_submitted,
    "application_status": application_status,
    "job_application_received": job_application_received,
    "job_application_status": job_application_status,
    "alumni_status": alumni_status,
}


def render(template: str, data: dict) -> tuple[str, str]:
    if template not in TEMPLATES:
        raise KeyError(f"unknown email template {template!r}")
    subject, body = TEMPLATES[template](data)
    # A subject is one line. Text people typed (a name on the Contact form) can contain line breaks,
    # which would otherwise make the email fail to send; collapse all control characters to spaces.
    subject = " ".join("".join(" " if ord(c) < 32 or ord(c) == 127 else c for c in subject).split())[:200]
    return subject, body
