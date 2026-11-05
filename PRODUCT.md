# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

HTML, Tailwind CSS, vanilla JavaScript (ES modules) on the front end; Flask microservices behind an Nginx API gateway; PostgreSQL (one database per service); Google OAuth 2.0 / OpenID Connect with JWT sessions. Fixed by the client. No front-end framework.

## Users

- **Prospective students and parents** (largely on phones, often on mobile data in Nepal): deciding whether NCIT is right, comparing programmes, checking fees, dates and eligibility, then applying.
- **Current students and teachers** (`@ncit.edu.np` accounts): checking notices, events, clubs, department information.
- **Content owners** working in dashboards: Super Admin, Event Admin, ECA Admin, HODs (one department each), Admission Officer, HR Officer, Alumni Coordinator. Weekly-to-daily use on laptops in college offices.
- **Alumni** registering and updating their profile; **job seekers** applying to vacancies at the college.

## Product Purpose

The official website and content platform of Nepal College of Information Technology. It publishes accurate college information (leadership messages, facilities, departments, programmes, semester-wise courses, faculty, events, ECA/clubs, news, notices), runs online admission applications, staff recruitment and alumni registration, and lets each content owner edit only their own area without IT help. Success: a prospective student finds the programme, fees and deadline and applies in one visit; an HOD updates their department in minutes; the Super Admin grants or revokes any role from one screen.

## Positioning

NCIT is an IT-and-engineering college in Balkumari, Lalitpur, affiliated with Pokhara University (founded 2001, per public directories). The site should read as a technology institution that runs itself well: every department, event and club is maintained by its own owner, so information is current rather than stale.

## Operating Context

- Built as independent microservices; new features (results, LMS, fee payment, library) are added later as new services without touching existing ones.
- Public pages are open to everyone. Sign-in and dashboards are limited to Google accounts on `@ncit.edu.np`. Applicants and alumni without an NCIT email use email one-time codes with access only to their own records.
- Roles are scoped (e.g. HOD of one department). Super Admin grants and revokes roles, with audit logging.
- Development runs in reviewed phases (0 to 6); each phase is demoed on staging and signed off by the college.

## Capabilities and Constraints

- Release 1 sections: Home, About (with messages from the Executive Director, Director and Principal), Academics (departments → programmes → semesters → courses, faculty, student testimonials at the end of each department), Faculty directory, Campus life (facilities, events, ECA and clubs), Admissions, Careers, Alumni, News and notices, Contact.
- Banner-type ads and announcements are managed by the Super Admin with scheduling.
- Programmes listed publicly by third-party directories (to be confirmed by the college): BE Computer, BE IT (Information Technology), BE Electronics & Communication, BE Civil, BE Software, BCA, BBA; MCIS, ME Computer, MSc CS.
- Must be responsive and mobile-first; must perform well on mid-range Android phones and slower connections.
- Undecided: final brand colours and logo files (the client asked to match NCIT's current colours; the site was unreachable from the build environment, so a provisional palette is used in one token file until the client supplies hex codes and the logo).

## Brand Commitments

- Name: Nepal College of Information Technology (NCIT). Domain `ncit.edu.np`.
- Colours must match NCIT's current brand. The client supplied the official logo (image in chat, file not yet in the repo): a royal-blue six-pointed star framing a blue-and-green globe, a red Om at the top apex, an open book and a lamp in the lower points, rainbow lightning bolts on both sides, the name in royal-blue capitals arched over the star, and a light-blue ribbon reading "2001". Brand colours are taken from it: royal blue (dominant), red (Om), sky blue (globe and ribbon), green (landmass). Exact hex codes are estimated from the image until the client confirms them.
- The emblem is used as supplied, never redrawn or restyled. Its file goes at `frontend/public/assets/img/ncit-logo.png`.

## Evidence on Hand

- No photography, logo files, leadership names, faculty names, statistics, testimonials or event data have been supplied. All such content on built pages is labelled sample data and must be replaced. Do not present invented figures (placement rates, rankings, student counts) as fact.
- Publicly known facts usable: location Balkumari, Lalitpur; Pokhara University affiliation; programme names above (to be confirmed).

## Product Principles

1. Current over complete: every block shows who owns it and when it was updated; stale content is a bug.
2. The applicant's path is the spine of the public site: programme → fees and dates → apply, reachable from any page in two taps on a phone.
3. Each owner sees only their own area; dashboards favour clarity and familiar patterns over expression.
4. Add, don't modify: new features arrive as new services and new menu entries, never as rewrites.
5. Honest content: real facts or clearly labelled samples, never invented claims.

## Accessibility & Inclusion

WCAG 2.1 AA. Many visitors are on phones with variable connectivity; keep pages light. English first; a Nepali toggle is a later option.

## Visual Direction Preference

The client chose the classic university website, played straight (decision in Phase 0): a photography-led hero, clear menus with mega-menus, news and event cards, quick links. harvard.edu and mit.edu set the craft level. This is a standing preference, not a placeholder.
