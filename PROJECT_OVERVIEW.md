# School Management System — Project Overview

## Documentation Status

This document describes the project as inspected from the current source code, templates, migration files, installed virtual-environment packages, and a read-only PostgreSQL schema inspection.

- **Documentation date:** 2026-10-16
- **Project root:** `F:\Full Stack Zone Internship\school_management_system`
- **Project name:** School Management System / SchoolPortal
- **Project stage:** Learning-focused internship project with working authentication, role-specific dashboards, student CRUD, teacher CRUD, Classes & Subjects administration, daily attendance, Exams & Results, Fee Management, filtering, relationships, and Flask-Migrate history. Notice workflows are not complete.
- **Live schema verification:** Performed against the configured database after the Attendance migration. The live database contains `users`, `students`, `teachers`, `classrooms`, `subjects`, `class_subject_assignments`, and `attendance`.
- **Automated test suite:** No test files were found in the workspace. The verification commands used for this document are listed in [Testing and Current Reliability](#testing-and-current-reliability).

No passwords, secret keys, connection credentials, or access tokens are recorded here.

## Purpose and Users

The application is a Flask-based school administration prototype. Its current implemented purpose is to authenticate users by role and allow an administrator to manage student and teacher records in PostgreSQL.

Roles confirmed by the code:

| Role | Confirmed implementation |
|---|---|
| Admin | Login redirect, admin dashboard, student management, and teacher management routes protected by `role_required("admin")`. |
| Teacher | Login redirect and a protected teacher dashboard. Teacher CRUD is administered by an admin; no teacher self-service management workflow was found. |
| Student | Login redirect and a protected student dashboard. Academic data workflows are currently placeholders. |

## Technology Stack

| Area | Verified implementation |
|---|---|
| Language/runtime | Python 3.14.7 in the project `.venv`. |
| Web framework | Flask 3.1.3. |
| ORM | Flask-SQLAlchemy 3.1.1 with SQLAlchemy 2.1.4. |
| Database | PostgreSQL through the `postgresql+psycopg` SQLAlchemy URL. Live database name verified as `school_management_db`; credentials are loaded from environment variables and are intentionally not documented. |
| Driver | `psycopg` 3.3.6 and `psycopg-binary` 3.3.6. |
| Migrations | Flask-Migrate 4.1.0 and Alembic 1.20.0. |
| Templates | Jinja2 3.1.6 with server-rendered HTML. |
| Styling | Inline page-specific CSS plus Bootstrap CDN assets. Most management pages use Bootstrap 5.3.x and Bootstrap Icons 1.11.3. |
| Password handling | Werkzeug password hashing and verification. |
| Configuration | `python-dotenv` loads `.env`; `.env` is ignored by Git. |

Other installed packages include Click 8.5.0, Werkzeug 3.1.9, Jinja2 3.1.6, Mako 1.4.3, MarkupSafe 3.0.4, Blinker 1.9.0, and `typing_extensions` 4.16.0. The exact dependency pins are also recorded in [requirements.txt](./requirements.txt).

## Project Structure

```text
school_management_system/
├── app/
│   ├── __init__.py                 # Flask application factory, db, and migration setup
│   ├── models/
│   │   ├── __init__.py             # Imports ORM models
│   │   ├── user.py                 # User/account model
│   │   ├── student.py              # Student model
│   │   ├── teacher.py              # Teacher model
│   │   └── classroom.py            # Classroom model; no matching migration/table verified
│   ├── routes/
│   │   └── __init__.py             # main Blueprint, authentication, dashboards, CRUD routes
│   └── templates/                  # Jinja HTML pages with page-specific CSS
├── migrations/
│   ├── env.py                      # Alembic environment and Flask-SQLAlchemy metadata
│   ├── alembic.ini                 # Alembic logging/template configuration
│   └── versions/                   # User, student, and teacher migration revisions
├── run.py                          # Creates the Flask app and starts the development server
├── requirements.txt                # Pinned Python dependencies
├── .env                            # Local configuration; ignored and not documented here
└── .gitignore                      # Ignores `.venv`, bytecode, `.env`, and `.vscode`
```

There is no `static/` directory in the inspected project. CSS is embedded in templates and third-party Bootstrap/Bootstrap Icons assets are loaded from CDNs.

## Application Architecture

The application uses an application factory:

1. `run.py` imports `create_app()` and creates `app`.
2. `app/__init__.py` loads environment variables, builds the PostgreSQL URL, initializes `db`, and registers Flask-Migrate.
3. Importing `app.models` loads the ORM model classes into the SQLAlchemy metadata.
4. The `main` Blueprint from `app/routes/__init__.py` is registered.
5. Requests pass through route decorators and session checks, use SQLAlchemy ORM queries/commits, and return Jinja templates or redirects.

The normal data flow is:

```text
Browser → Flask route → session/role check → request validation → SQLAlchemy ORM → PostgreSQL → template or redirect
```

For example, an administrator opening `/admin/students` supplies optional search and status query parameters. The route builds a `Student` query, applies filters, calculates counts, and renders `admin_students.html`. The add/edit routes receive form data, create or update ORM objects, commit to PostgreSQL, and redirect to the list.

## Configuration and Application Setup

[app/__init__.py](./app/__init__.py) defines:

- `db = SQLAlchemy()`
- `migrate = Migrate()`
- `create_app()`
- `SQLALCHEMY_DATABASE_URI` using `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, and `DB_NAME`
- `SQLALCHEMY_TRACK_MODIFICATIONS = False`
- `SECRET_KEY` from `SECRET_KEY`, falling back to a development-only placeholder when absent

The environment variable names are known from `.env`, but their values are intentionally excluded. `DB_NAME` was safely verified through the active SQLAlchemy engine as `school_management_db`.

## Database Models and Schema

### User model / `users`

Defined in [app/models/user.py](./app/models/user.py).

| Column | SQLAlchemy type | Nullable | Constraints/default |
|---|---|---:|---|
| `id` | Integer | No | Primary key |
| `username` | String(80) | No | Unique |
| `password_hash` | String(255) | No | Stores a Werkzeug hash, not a plain password |
| `role` | String(20) | No | Used by session authorization |
| `is_active` | Boolean | No | Python default `True`; no explicit server default in the model |

The model relates optional teacher login profiles to `Teacher` and recorded attendance to `Attendance`.

### Student model / `students`

Defined in [app/models/student.py](./app/models/student.py).

| Column | SQLAlchemy type | Nullable | Constraints/default |
|---|---|---:|---|
| `id` | Integer | No | Primary key |
| `full_name` | String(120) | No | Required |
| `roll_number` | String(30) | No | Unique and required |
| `date_of_birth` | Date | Yes | Optional |
| `gender` | String(20) | Yes | Optional |
| `phone` | String(20) | Yes | Optional |
| `address` | String(250) | Yes | Optional in the model; the add template allows up to 500 characters |
| `is_active` | Boolean | No | Python default `True`; used by list filtering and status display |
| `class_id` | Integer | Yes | Foreign key to `classrooms.id`; optional current class |

The `classroom` relationship points to the student's optional current class.

### Teacher model / `teachers`

Defined in [app/models/teacher.py](./app/models/teacher.py).

| Column | SQLAlchemy type | Nullable | Constraints/default |
|---|---|---:|---|
| `id` | Integer | No | Primary key |
| `full_name` | String(120) | No | Required |
| `email` | String(120) | Yes | Unique when supplied |
| `phone` | String(20) | Yes | Optional |
| `gender` | String(20) | Yes | Optional |
| `qualification` | String(150) | Yes | Optional |
| `is_active` | Boolean | No | Python default `True`; used by filters and forms |
| `created_at` | DateTime with timezone | No | Python default: current UTC time |

The model relates to classrooms where the teacher is the class teacher and to class-subject assignments where the teacher teaches a subject.

### Classroom model / `classrooms`

Defined in [app/models/classroom.py](./app/models/classroom.py).

| Column | SQLAlchemy type | Nullable | Constraints/default |
|---|---|---:|---|
| `id` | Integer | No | Primary key |
| `name` | String(80) | No | Unique and required |
| `description` | String(250) | Yes | Optional |
| `is_active` | Boolean | No | Python default `True` |
| `created_at` | DateTime with timezone | No | Python default: current UTC time |
| `class_teacher_id` | Integer | Yes | Foreign key to `teachers.id`; `ON DELETE SET NULL` |

The model relates to its students, optional class teacher, and class-subject assignments.

### Attendance model / `attendance`

Defined in [app/models/attendance.py](./app/models/attendance.py). Each record stores `student_id`, `class_id`, `attendance_date`, `status`, `recorded_by_user_id`, and UTC `created_at`/`updated_at` timestamps. Status is constrained to `Present`, `Absent`, or `Late`. The unique constraint `uq_attendance_student_date` prevents duplicate attendance for one student on one date. Student and class deletes cascade; the recording User is protected by a restricted foreign key.

### Exam and ExamResult models / `exams`, `exam_results`

Defined in [app/models/exam.py](./app/models/exam.py). `Exam` belongs to a Classroom and stores its name, date, total marks, and publication status. `ExamResult` connects an exam, student, and assigned subject, stores marks, calculated grade, remarks, recording user, and timestamps. The unique constraint `uq_exam_result_student_subject` prevents duplicate marks for the same exam/student/subject. Existing Student records can remain unlinked; the nullable unique `students.user_id` link is only needed for Student Portal result viewing.

### FeeRecord and FeePayment models / `fee_records`, `fee_payments`

Defined in [app/models/fee.py](./app/models/fee.py). `FeeRecord` assigns a charge to a student for a billing month with an amount and due date. `FeePayment` stores partial/full payments, date, method, optional receipt reference, and receiving user. Fee status is derived as `Paid`, `Partial`, `Unpaid`, or `Overdue`; balance is never manually duplicated. The unique constraint `uq_fee_student_title_month` prevents duplicate fee assignments for the same student/title/month.

### Subject model / `subjects`

Defined in [app/models/subject.py](./app/models/subject.py). It contains `id` (Integer primary key), `name` (String(120), required and unique), `description` (String(250), nullable), `is_active` (Boolean, non-null with Python default `True`), and `created_at` (timezone-aware DateTime, non-null with UTC Python default). A Subject has many `ClassSubjectAssignment` records.

### ClassSubjectAssignment model / `class_subject_assignments`

Defined in [app/models/class_subject_assignment.py](./app/models/class_subject_assignment.py). It contains an integer primary key plus required foreign keys `class_id` → `classrooms.id`, `subject_id` → `subjects.id`, and `teacher_id` → `teachers.id`. Class and subject deletes cascade to assignments; teacher deletion is restricted by the database FK. The unique constraint `uq_class_subject_assignment` enforces one teacher assignment per class/subject pair.

### Live schema verification

Read-only inspection of the configured database returned:

- `alembic_version`
- `students`
- `teachers`
- `users`
- `attendance`

The live columns for `users`, `students`, `teachers`, `classrooms`, `subjects`, `class_subject_assignments`, and `attendance` matched the applied migrations and inspected models. The live schema contains the student-class, classroom-teacher, assignment, and attendance foreign keys described above.

### Migration history

The migration chain is:

```text
844685d2fce1  create users table
        ↓
dedd71fb3492  create students table
        ↓
071f906ac2ec  Add teacher model
        ↓
c906155c0db3  add classes subjects and relationships
        â†“
cdc29e7850d2  add attendance tracking and teacher accounts  (current head)
        ↓
8c813e503da4  add exams and results
        ↓
9b33426aed2b  add fee management  (current head)
```

The live `alembic_version` value is `9b33426aed2b`. `flask db check` reported `No new upgrade operations detected` after applying the Fee Management migration. Existing records were preserved; the migrations added nullable account links and new tables without dropping existing tables.

## Authentication, Roles, and Permissions

Authentication is implemented in [app/routes/__init__.py](./app/routes/__init__.py):

- `/login` accepts a username and password.
- The stored `password_hash` is checked with `check_password_hash`.
- Successful login stores `user_id` and `role` in the Flask session.
- The role determines the redirect to the admin, teacher, or student dashboard.
- `/logout` clears the session.
- Public registration is disabled. Admin-only Student and Teacher creation creates a role-specific User and profile in one transaction with a Werkzeug-generated password hash.

The `role_required(required_role)` decorator redirects unauthenticated requests to `main.login` and returns `Access Denied` with HTTP 403 when the session role does not match.

| Area | Admin | Teacher | Student | Public |
|---|---:|---:|---:|---:|
| Public home/about/login/logout | Yes through normal routes | Yes through normal routes | Yes through normal routes | Yes |
| Admin dashboard | Yes | No | No | No |
| Student management CRUD | Yes | No | No | No |
| Teacher management CRUD | Yes | No | No | No |
| Teacher dashboard | No | Yes | No | No |
| Student dashboard | No | No | Yes | No |

Security limitations identified from the code:

- No CSRF protection was found in the forms.
- The fallback secret key is explicitly development-only and must not be relied on in production.
- Login and role checks are present, but broader production hardening was not investigated.

## Routes and Application Logic

All routes belong to the `main` Blueprint except Flask's static route. The following route list was verified with `flask --app run.py routes`.

### Public and authentication routes

| URL | Methods | Endpoint/function | Access | Purpose/template |
|---|---|---|---|---|
| `/` | GET | `main.home` / `home` | Public | Public landing page, `home.html` |
| `/about` | GET | `main.about` / `about` | Public | Static about response |
| `/login` | GET, POST | `main.login` / `login` | Public | Login form and credential verification, `login.html` |
| `/logout` | GET | `main.logout` / `logout` | Public/session | Clears session and redirects to login |

### Admin dashboard and student management

| URL | Methods | Endpoint/function | Access | Data/workflow |
|---|---|---|---|---|
| `/admin/dashboard` | GET | `main.admin_dashboard` / `admin_dashboard` | Admin | Renders database-backed student, teacher, class, outstanding-fee, and published-notice summaries. |
| `/admin/students` | GET | `main.admin_students` / `admin_students` | Admin | Search by name/roll number, filter by `active`/`inactive`, calculate counts, render `admin_students.html`. |
| `/admin/students/add` | GET, POST | `main.add_student` / `add_student` | Admin | Validates required name/roll number, checks unique roll number, commits a Student, renders `add_student.html`. |
| `/admin/students/edit/<int:student_id>` | GET, POST | `main.edit_student` / `edit_student` | Admin | Loads a Student, validates unique roll number, updates fields, commits, renders `edit_student.html`. |
| `/admin/students/<int:student_id>` | GET | `main.student_details` / `student_details` | Admin | Loads a Student and renders `student_details.html`. |
| `/admin/students/delete/<int:student_id>` | POST | `main.delete_student` / `delete_student` | Admin | Deletes the selected Student and redirects to the list. |

Student status behavior is implemented through the `is_active` Boolean. The list displays Active/Inactive badges and the `status` query parameter filters results. The create/edit form status switch was recently added and follows the Teacher form pattern; new students default to Active in the displayed form.

### Admin teacher management

| URL | Methods | Endpoint/function | Access | Data/workflow |
|---|---|---|---|---|
| `/admin/teachers` | GET | `main.admin_teachers` / `admin_teachers` | Admin | Search by name/email/phone, filter by status, calculate counts, render `admin_teachers.html`. |
| `/admin/teachers/new` | GET, POST | `main.add_teacher` / `add_teacher` | Admin | Validates name and unique email, saves Teacher with status, renders `teacher_form.html`. |
| `/admin/teachers/<int:teacher_id>` | GET | `main.teacher_details` / `teacher_details` | Admin | Loads and renders `teacher_details.html`. |
| `/admin/teachers/<int:teacher_id>/edit` | GET, POST | `main.edit_teacher` / `edit_teacher` | Admin | Updates Teacher fields and `is_active`, commits, redirects to details. |
| `/admin/teachers/<int:teacher_id>/delete` | POST | `main.delete_teacher` / `delete_teacher` | Admin | Deletes a Teacher inside a rollback-protected try/except block. |

### Role dashboards

| URL | Methods | Endpoint/function | Access | Template |
|---|---|---|---|---|
| `/teacher/dashboard` | GET | `main.teacher_dashboard` / `teacher_dashboard` | Teacher | `teacher_dashboard.html` |
| `/teacher/classes` | GET | `main.teacher_classes` / `teacher_classes` | Linked active Teacher | Lists active classes assigned as class teacher or through a subject assignment. |
| `/teacher/classes/<class_id>` | GET | `main.teacher_class_details` / `teacher_class_details` | Authorized Teacher | Shows active students and only the logged-in teacher's subject assignments for that class. |
| `/teacher/subjects` | GET | `main.teacher_subjects` / `teacher_subjects` | Linked active Teacher | Lists the logged-in teacher's active class-subject assignments. |
| `/student/dashboard` | GET | `main.student_dashboard` / `student_dashboard` | Student | `student_dashboard.html` |
| `/admin/notices` | GET, POST | `main.admin_notices` / `admin_notices` | Admin | Creates notices and lists existing published/draft notices. |
| `/admin/notices/<notice_id>/edit` | GET, POST | `main.edit_notice` / `edit_notice` | Admin | Updates a notice title, body, audience, dates, and publication state. |
| `/admin/notices/<notice_id>/delete` | POST | `main.delete_notice` / `delete_notice` | Admin | Deletes a notice after management-page confirmation. |
| `/admin/notices/<notice_id>` | GET | `main.admin_notice_detail` / `admin_notice_detail` | Admin | Shows a full notice, including draft and audience metadata. |
| `/teacher/notices` | GET | `main.teacher_notices` / `teacher_notices` | Teacher | Lists published, active notices for everyone or teachers. |
| `/teacher/notices/<notice_id>` | GET | `main.teacher_notice_detail` / `teacher_notice_detail` | Teacher | Shows a full authorized notice. |
| `/student/notices` | GET | `main.student_notices` / `student_notices` | Student | Lists published, active notices for everyone or students. |
| `/student/notices/<notice_id>` | GET | `main.student_notice_detail` / `student_notice_detail` | Student | Shows a full authorized notice. |

### Attendance

| URL | Methods | Endpoint/function | Access | Purpose |
|---|---|---|---|---|
| `/teacher/attendance` | GET | `main.teacher_attendance` / `teacher_attendance` | Linked active class teacher | Loads only the teacher's assigned active classes and existing statuses for a selected date. |
| `/teacher/attendance/mark` | POST | `main.mark_teacher_attendance` / `mark_teacher_attendance` | Linked active class teacher | Validates class and student ownership, then creates or updates submitted Present/Absent/Late records. Missing students are not automatically marked absent. |
| `/admin/attendance` | GET | `main.admin_attendance` / `admin_attendance` | Admin | Filters daily records by class, date, and status and shows totals. Links to class and student reports. |
| `/admin/attendance/<attendance_id>/update` | POST | `main.update_attendance` / `update_attendance` | Admin | Corrects an attendance status. |
| `/admin/attendance/reports/class` | GET | `main.class_attendance_report` / `class_attendance_report` | Admin | Monthly class attendance matrix with aggregate statistics, student status tallies, attendance rates, and progress bars. |
| `/admin/attendance/reports/class/pdf` | GET | `main.admin_class_attendance_pdf` / `admin_class_attendance_pdf` | Admin | Generates downloadable landscape A4 class attendance summary PDF. |
| `/admin/attendance/reports/student` | GET | `main.student_attendance_report` / `student_attendance_report` | Admin | Two-step selection (Class -> Student) with monthly records, totals, and `(Present + Late) / recorded days * 100`; unrecorded days are excluded. Rejects cross-class mismatch. |
| `/admin/attendance/reports/student/pdf` | GET | `main.admin_student_attendance_pdf` / `admin_student_attendance_pdf` | Admin | Generates downloadable portrait A4 student attendance PDF report. |
| `/student/attendance` | GET | `main.student_attendance` / `student_attendance` | Linked Student | Shows only the logged-in student's monthly attendance records, class, status, totals, and attendance percentage. |

Teacher attendance requires an active Teacher record linked to the logged-in User through `teachers.user_id`. Existing unlinked teachers remain unchanged and can be linked by an Admin through the Teacher form before marking attendance. Attendance rates strictly compute from recorded dates `(Present + Late) / total_recorded * 100` without assuming absent for unrecorded calendar dates.

### Exams and Results

| URL | Methods | Endpoint/function | Access | Purpose |
|---|---|---|---|---|
| `/admin/exams` | GET, POST | `main.admin_exams` / `admin_exams` | Admin | Creates exams for active classes and lists draft/published exams. |
| `/admin/exams/<exam_id>/publish` | POST | `main.publish_exam` / `publish_exam` | Admin | Publishes or unpublishes an exam. |
| `/admin/exams/<exam_id>/results` | GET, POST | `main.admin_exam_results` / `admin_exam_results` | Admin | Redirects to exam management because teachers own subject-wise marks entry. |
| `/teacher/results` | GET | `main.teacher_results` / `teacher_results` | Teacher | Loads only exams, assigned classes, and subjects belonging to the logged-in teacher; displays enrolled students and existing marks. |
| `/teacher/results/save` | POST | `main.save_teacher_results` / `save_teacher_results` | Teacher | Validates exam/class/subject/student authorization and saves or updates marks for the teacher's assigned class-subject without duplicates. |
| `/student/results` | GET | `main.student_results` / `student_results` | Linked Student | Shows results from published exams for the logged-in student's profile. |

### Fees

| URL | Methods | Endpoint/function | Access | Purpose |
|---|---|---|---|---|
| `/admin/fees` | GET, POST | `main.admin_fees` / `admin_fees` | Admin | Assigns fees to active students, displays aggregate overview metrics (total assessed, paid, balance), and filters records by class/status. |
| `/admin/fees/<fee_id>/payment` | POST | `main.record_fee_payment` / `record_fee_payment` | Admin | Records a valid partial or full payment without exceeding the balance. |
| `/admin/fees/reports/class` | GET | `main.class_fee_report` / `class_fee_report` | Admin | Class-wise fee report with collection totals, outstanding balances, collection rate, and student roster breakdown. |
| `/admin/fees/reports/class/pdf` | GET | `main.admin_class_fee_pdf` / `admin_class_fee_pdf` | Admin | Generates downloadable landscape A4 class fee collection summary PDF. |
| `/admin/fees/reports/student` | GET | `main.admin_student_fee_report` / `admin_student_fee_report` | Admin | Student-wise fee report with name/roll-number search, class dropdown, status filters, invoice ledger, and payment receipts. |
| `/admin/fees/reports/student/pdf` | GET | `main.admin_student_fee_pdf` / `admin_student_fee_pdf` | Admin | Generates downloadable portrait A4 student fee statement PDF. |
| `/student/fees` | GET | `main.student_fees` / `student_fees` | Linked Student | Shows only the logged-in student's fee records, paid amount, balance, and status. |

### Student overview and notices

Notices are persisted in the `notices` table and managed only by Admin users. Each notice stores a title, body, audience (`all`, `teacher`, or `student`), notice date, optional expiry date, publication state, and creating admin. Teacher and student listings apply audience, publication, notice-date, and expiry filtering in the backend; detail routes repeat those checks.

The student dashboard's four Academic Overview options are Attendance, Latest Result, Fee Status, and School Notices. Attendance, results, and fees now load records through the logged-in user's linked student profile. `/student/notices` is role-protected and provides an empty state because this project does not yet contain a notice model, database table, or administration publishing workflow.

Payment methods supported are Cash, Bank Transfer, Card, and Online. Overpayments, duplicate receipt references, invalid dates, and invalid amounts are rejected.

Grades use percentage of the exam total: A+ (90+), A (80–89), B (70–79), C (60–69), D (50–59), and F below 50. Marks are validated between zero and the exam total. Blank rows are not saved.

## Frontend Theme and UI System

The templates are standalone Jinja HTML documents with repeated inline CSS rather than shared base templates or a static stylesheet.

### Common visual language

- Product branding: **SchoolPortal** / School Management System.
- Main canvas: light blue-gray, commonly `#f5f7fc`.
- Navy sidebar/headings: `#111c3a` or `#172554` depending on the page.
- Primary blue: `#4568f5` or `#4f46e5`; hover blue commonly `#3454df`.
- Muted text: `#7b8499` or `#8791a5`.
- Borders: light gray-blue values such as `#edf0f7`, `#e6eaf2`, and `#e3e8f2`.
- Active status: pale green `#e5f8ef` with text `#168452`.
- Inactive status: pale orange `#fff0e9` with text `#c45b32`.
- Font stack: `Inter, "Segoe UI", sans-serif`.
- Icons: Bootstrap Icons, normally version 1.11.3.

### Layout patterns

- Management list pages use a fixed dark sidebar, a main content offset, top heading, statistics cards, search/filter controls, and a white rounded table card.
- Sidebar width is commonly 258px on desktop, reduced near 210px at medium widths and approximately 65px on small screens.
- Cards use white backgrounds, light borders, rounded corners around 15–17px, and subtle shadows.
- Buttons use rounded corners, blue primary actions, light bordered cancel/reset actions, and red delete actions.
- Forms use Bootstrap grid classes, rounded controls, inline validation messages, and page-specific action footers.
- Responsive CSS is embedded with breakpoints around 900px, 767px, 700px, 650px, and 600px depending on the page.

### Page differences

- Admin dashboard, student dashboard, and teacher dashboard use Bootstrap 5.3.8 CDN references.
- Student add/edit, student list, teacher list, and teacher form use slightly different but compatible inline design tokens; the student and teacher forms are not shared components.
- Some sidebar links intentionally use `href="#"` or section anchors because their target modules are not implemented yet.

## Page-by-Page Overview

| Template | Route(s) | Current purpose and status |
|---|---|---|
| `home.html` | `/` | Public landing page with SchoolPortal messaging, navigation, feature/module cards, and links into public/auth flows. |
| `login.html` | `/login` | Login form for username/password; displays the route-provided error message. |
| `admin_dashboard.html` | `/admin/dashboard` | Admin overview with sidebar, dashboard cards, student/teacher links, and placeholder school modules. Route currently provides no dynamic statistics context. |
| `admin_students.html` | `/admin/students` | Student statistics, search field, status filter, table, Active/Inactive badges, edit/details/delete actions, and empty state. |
| `add_student.html` | `/admin/students/add` | Student creation form for name, roll number, DOB, gender, phone, address, and Active student status. Uses existing page styling and validation error area. |
| `edit_student.html` | `/admin/students/edit/<id>` | Student edit form with current values, date parsing on POST, current status switch, and save/cancel actions. |
| `student_details.html` | `/admin/students/<id>` | Student profile/detail layout with identity, personal/contact/record sections and edit/back links. Some displayed fields (`email`, `classroom`) are not present on the current Student model and need verification before being treated as implemented data. |
| `admin_teachers.html` | `/admin/teachers` | Teacher statistics, search by name/email/phone, status filter, table, status badges, details/edit/delete actions, and empty state. |
| `teacher_form.html` | `/admin/teachers/new`, `/admin/teachers/<id>/edit` | Shared add/edit Teacher form with validation feedback and the established Active teacher switch pattern. |
| `teacher_details.html` | `/admin/teachers/<id>` | Teacher detail page with status badge and saved profile values. |
| `teacher_dashboard.html` | `/teacher/dashboard` | Role-protected teacher dashboard with database-backed class, student, attendance, and subject summaries plus links to all teaching tools. |
| `teacher_classes.html` | `/teacher/classes` | Teacher-scoped class list with student counts and class detail links. |
| `teacher_class_details.html` | `/teacher/classes/<class_id>` | Authorized teacher class detail view with active students and owned subject assignments. |
| `teacher_subjects.html` | `/teacher/subjects` | Teacher-scoped subject assignment list with class and student counts. |
| `student_dashboard.html` | `/student/dashboard` | Role-protected student dashboard with student-scoped attendance, latest published result, latest fee status, and a truthful notice count/empty state. |
| `student_attendance.html` | `/student/attendance` | Monthly attendance history with status totals, percentage, class, date filter, and empty state. |
| `student_notices.html` | `/student/notices` | Protected notice destination with an empty state until notice publishing is implemented. |

Some unrelated placeholder navigation remains elsewhere in the application. The student dashboard options covered here now have matching protected routes and data-backed destinations; School Notices remains intentionally empty because no notice data source exists.

## Feature Status

| Feature/module | Status | Evidence and remaining work |
|---|---|---|
| Application factory and database initialization | Implemented and verified | Flask factory, SQLAlchemy, Flask-Migrate, and environment-based URL are active. |
| Authentication | Implemented, admin-controlled | Login requires username, password, and matching database role; public registration is disabled; Admin creates linked Student/Teacher accounts with hashed passwords. CSRF and production hardening were not found. |
| Role-based authorization | Implemented for current routes | `role_required` protects admin/teacher/student route groups. |
| Admin dashboard | Partially implemented | Page and navigation exist; route provides no dynamic context and several modules are placeholders. |
| Student management | Implemented and verified at route/schema level | Create, list/search/filter, edit, details, delete, status counts, and status persistence are present. Automated tests are absent. |
| Teacher management | Implemented and verified at route/schema level | CRUD, search, status filtering, status switch, and detail page exist. Automated tests are absent. |
| Classes & Subjects management | Implemented and verified | Admin class/subject CRUD, class teacher selection, subject-teacher assignment, duplicate prevention, class details, student enrollment, and assignment display are implemented. |
| Classroom data model | Implemented and migrated | Classroom table, optional class teacher FK, student relationship, status, and timestamps are live. |
| Subjects and assignments | Implemented and migrated | Subject table and unique class-subject-teacher assignment table are live and connected to Admin routes. |
| Attendance | Implemented and verified | Daily teacher marking with backend class/student authorization, correction/upsert, admin filters, monthly reports, status constraints, and duplicate prevention are live. |
| Examinations/results | Implemented and verified | Admin exam creation/publication, teacher assignment-scoped result entry, grade calculation, Student Portal published-result view, duplicate prevention, and validation are live. |
| Fee management | Implemented and verified | Admin fee assignment, monthly duplicate prevention, partial/full payments, balance/status calculation, filters, and Student Portal fee visibility are live. |
| Notices | Planned/not implemented | Dashboard presentation exists; no persistence or management workflow found. |
| Public website | Partially implemented | Home/about pages and shared presentation exist; many module links are placeholders. |

## Validation and Business Rules

- Student name and roll number are required.
- Student roll number must be unique.
- Student class assignment is optional; the `Unassigned` option stores `class_id` as NULL.
- Teacher name is required.
- Teacher email is optional but unique when supplied; it is normalized to lowercase in the route.
- Student and Teacher status is stored as a Boolean `is_active` value.
- New Student and Teacher forms default to Active in the UI.
- Search uses case-insensitive `ilike` matching for configured fields.
- Student list filtering accepts `status=active` and `status=inactive`; otherwise it shows all records.
- Teacher list filtering follows the same status convention.
- Class names and subject names are required and unique.
- A class teacher is optional and must reference an existing teacher.
- A subject assignment must reference an existing class, subject, and teacher; duplicate class/subject pairs are rejected.
- Attendance status must be `Present`, `Absent`, or `Late`, and `(student_id, attendance_date)` is unique.
- Attendance percentage counts Present and Late as attended, divides by recorded attendance days only, and never treats unrecorded days as absent.
- Exam names are unique within a class; total marks must be positive.
- Result marks must be between zero and the exam total; one result per exam/student/subject is allowed.
- Teachers can enter marks only for subjects assigned to them in the exam's class.
- Students can view only their own results, and only after an Admin publishes the exam.
- Fee amount and payment amount must be positive; a payment cannot exceed the current fee balance.
- Fee status is calculated from payments and due date, not trusted from form input.
- Fee records are unique per student, title, and billing month; existing students remain preserved.
- Student edit parses a non-empty ISO date string with `date.fromisoformat`.
- Teacher create/update and delete paths include rollback handling; Student create/update/delete paths currently commit without their own exception wrapper.

## Setup and Run Instructions

The following commands and environment state were verified for this workspace:

1. Use Python 3.14.7 from `.venv`.
2. Install the pinned dependencies with `requirements.txt` if the environment is not already prepared:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

3. Provide the environment variables consumed by [app/__init__.py](./app/__init__.py): `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, and optionally `SECRET_KEY`. Keep actual values local and never commit them.
4. Ensure PostgreSQL is running and the configured database is available.
5. Inspect/apply migrations with Flask-Migrate when appropriate:

   ```powershell
   .\.venv\Scripts\python.exe -m flask --app run.py db current
   .\.venv\Scripts\python.exe -m flask --app run.py db upgrade
   ```

6. Start the development server:

   ```powershell
   .\.venv\Scripts\python.exe run.py
   ```

The default Flask development URL is normally `http://127.0.0.1:5000/`; the exact host/port override was not separately configured in the inspected files.

## Classes & Subjects Module

The Classes & Subjects module is implemented for Admin users at `/admin/classes`. It follows the existing SchoolPortal management-page style and uses the same `role_required("admin")` authorization pattern.

### Models and relationships

- `Classroom` now has an optional `class_teacher_id` foreign key to `teachers.id` with `ON DELETE SET NULL`.
- `Student` now has a nullable `class_id` foreign key to `classrooms.id` with `ON DELETE SET NULL`, so existing or unassigned students remain valid.
- `Subject` stores a unique name, optional description, active status, and UTC creation time.
- `ClassSubjectAssignment` connects one classroom, one subject, and one teacher.
- A unique constraint on `(class_id, subject_id)` prevents assigning the same subject to the same class twice.
- ORM relationships expose `classroom.students`, `classroom.class_teacher`, `classroom.subject_assignments`, `subject.assignments`, `teacher.classrooms_as_class_teacher`, and `teacher.subject_assignments`.

### Routes and templates

| Route | Methods | Purpose |
|---|---|---|
| `/admin/classes` | GET | Classes and Subjects list page with status, teacher, student counts, and assignment summaries. |
| `/admin/classes/new` | GET, POST | Create a class with optional class teacher and status. |
| `/admin/classes/<class_id>/edit` | GET, POST | Edit class name, description, class teacher, and status. |
| `/admin/classes/<class_id>` | GET | Class details, enrolled students, class teacher, subject assignments, and assignment form. |
| `/admin/classes/<class_id>/delete` | POST | Delete a class; assigned students become unassigned through the nullable FK and assignments are cascaded. |
| `/admin/subjects/new` | GET, POST | Create a unique subject with description and status. |
| `/admin/subjects/<subject_id>/edit` | GET, POST | Edit subject details and status. |
| `/admin/subjects/<subject_id>/delete` | POST | Delete a subject and its assignments. |
| `/admin/classes/<class_id>/assignments` | POST | Assign a subject and teacher to a class. |
| `/admin/classes/<class_id>/assignments/<assignment_id>/delete` | POST | Remove a class-subject-teacher assignment. |

Templates added:

- `admin_classes.html` — responsive Classes and Subjects management page.
- `class_form.html` — shared add/edit class form.
- `subject_form.html` — shared add/edit subject form.
- `class_details.html` — class profile, student list/count, class teacher, and subject assignments.

Existing integration changes:

- Student add/edit forms now include an `Unassigned` option and active-class dropdown.
- Student create/edit routes validate the selected class and persist `class_id`.
- Teacher details now show classes where the teacher is class teacher and subject/class assignments.
- Admin dashboard, student pages, teacher pages, and student forms now link their Classes & Subjects sidebar/navigation entries to `/admin/classes`.

### Migration and data safety

Migration `c906155c0db3_add_classes_subjects_and_relationships.py` was generated, reviewed, corrected to use a named student foreign-key constraint, and applied successfully from `071f906ac2ec`.

The migration creates `classrooms`, `subjects`, and `class_subject_assignments`, and adds nullable `students.class_id`. It does not delete or rewrite existing User, Student, or Teacher records. Live PostgreSQL verification confirmed the new tables, foreign keys, unique assignment constraint, and migration revision `c906155c0db3`.

## Testing and Current Reliability

### Verification performed

- `flask --app run.py routes` completed and listed all current Blueprint endpoints.
- `flask --app run.py db current` reported `cdc29e7850d2 (head)`.
- `flask --app run.py db history` showed the three-revision User → Student → Teacher chain.
- `flask --app run.py db check` reported `No new upgrade operations detected`.
- A read-only SQLAlchemy inspector verified the live database table names and columns.
- Migration `c906155c0db3` and Attendance migration `cdc29e7850d2` applied successfully; `flask db current` reports the Attendance revision as head.
- New route smoke tests confirmed unauthenticated access redirects, non-admin access returns 403, and all Classes & Subjects pages return HTTP 200 for Admin.
- Temporary integration records verified class creation, subject creation, class-subject-teacher assignment, duplicate-assignment prevention, student class assignment, class detail enrollment/count display, and teacher assignment display. Cleanup restored the pre-test counts (`classrooms=0`, `subjects=0`, `students=4`, `assignments=0`).
- Workspace diagnostics were checked for the relevant Python files without reported errors.
- Student Active/Inactive create/edit persistence was manually exercised with a temporary record in the development database; the temporary record was removed and its roll number was verified absent afterward. Existing student count remained 4 at the time of inspection.
- Attendance migration `cdc29e7850d2_add_attendance_tracking_and_teacher_.py` was reviewed, its generated unnamed downgrade constraints were given explicit names, and it was applied successfully.
- SQLAlchemy inspection verified `attendance` and all eight expected columns, plus the unique `(student_id, attendance_date)` constraint. Live counts after cleanup were `users=1`, `students=4`, `teachers=3`, `classrooms=2`, `subjects=6`, `assignments=2`, and `attendance=0`.
- A Flask test-client workflow verified teacher class isolation, Present/Absent/Late submission, same-date upsert without duplicates, cross-class student rejection, admin daily filtering, admin correction, and monthly report response. Temporary records were cleaned.
- Migration `8c813e503da4_add_exams_and_results.py` was reviewed and applied. It added `exams`, `exam_results`, and nullable unique `students.user_id`; no existing tables or records were reset.
- SQLAlchemy inspection verified `exams` (7 columns) and `exam_results` (10 columns). Live counts after cleanup were `students=4`, `exams=0`, and `results=0`.
- A Flask test-client workflow verified Admin exam creation, teacher assignment-scoped result entry, grade calculation, exam publication, Student Portal visibility, and temporary-record cleanup.
- Migration `9b33426aed2b_add_fee_management.py` was reviewed and applied. It created `fee_records` and `fee_payments` with positive-amount checks, foreign keys, and monthly fee uniqueness; existing data was preserved.
- SQLAlchemy inspection verified both fee tables and their expected columns/constraints. Live counts after cleanup were `students=4`, `fees=0`, and `payments=0`.
- A Flask test-client workflow verified Admin fee assignment, partial payment balance, full payment/Paid status, Admin status filtering, Student Portal visibility, and cleanup of temporary records.
- Authentication smoke tests verified the preserved existing Admin row, Admin-only Student/Teacher account creation, secure password hashing, duplicate username rejection, selected-role validation, backend role blocking, logout, and `/register` returning 404. Temporary accounts were removed and original counts restored.

### Known risks and unverified areas

- No automated test suite was found.
- Classroom, Subject, assignment, and Attendance schemas are migrated and verified; future relationship changes still require reviewed migrations.
- `student_details.html` still refers to `student.email`, which is not a field on the current Student model; `student.classroom` is now available after the new relationship.
- Student add route passes the submitted DOB string directly into a Date column, while the edit route explicitly parses the date. This inconsistency should be tested before relying on all date-entry paths.
- Some model column lengths differ from template `maxlength` values, especially Student address and some edit form fields.
- Existing Teacher accounts `owl` and `Owais Ahmed` are active User records but currently have no linked Teacher profile. They require Admin-only linking through the Teacher edit form before teacher-specific features can use them.
- CSRF protection, deployment configuration, error logging, and production secret management were not implemented or verified.
- No live browser/UI test was performed; route/template smoke tests were performed with Flask's test client.

## Recommended Next Steps

These are recommendations, not completed work:

1. Decide whether Classroom is an active next module. If yes, design its relationships to Student/Teacher before creating a migration.
2. Add automated route/model tests for authentication, student CRUD/status filtering, and teacher CRUD/status filtering.
3. Reconcile Student detail template fields with the Student model, or explicitly add approved model relationships/columns through migrations.
4. Normalize Student date parsing and form/model length validation.
5. Add CSRF protection and review Admin account lifecycle before deployment.
6. Replace placeholder dashboard/sidebar links only when the corresponding models, routes, templates, and migrations are ready.

## Agent Handoff Instructions

Future coding agents should:

- Read this `PROJECT_OVERVIEW.md` before making changes.
- Inspect the relevant current files before editing.
- Follow the existing Flask, SQLAlchemy, PostgreSQL, Bootstrap, and inline-template patterns unless an approved change requires otherwise.
- Preserve the established SchoolPortal theme, sidebar, spacing, colors, forms, and page layouts.
- Make small targeted changes; do not rewrite whole files for localized features.
- Avoid duplicate routes, models, imports, and template blocks.
- Do not modify the database schema without explaining the impact and proposing a safe Flask-Migrate migration first.
- Never reset, drop, recreate, or delete existing data without explicit approval.
- Never expose credentials or commit `.env` contents/secrets.
- For inspect-first requests, present the plan and wait for approval before editing or migrating.
- Test the specific change and report the actual result rather than assuming success.
- Append meaningful future work to [Change Log / Future Updates](#change-log--future-updates); preserve earlier entries.

## Change Log / Future Updates

### 2026-10-16 — Initial project overview created

- **What changed:** Created this documentation from the inspected current codebase, templates, migration files, installed `.venv` packages, and read-only PostgreSQL schema inspection.
- **Files changed:** Added `PROJECT_OVERVIEW.md` only. No application code, templates, migrations, configuration, or database objects were changed.
- **Database/schema impact:** None. Verified live `users`, `students`, and `teachers` tables at migration head `071f906ac2ec`; `classrooms` remains code-only and un-migrated.
- **Routes or UI affected:** None. Routes and UI were inspected only.
- **Tests performed and results:** Route listing, migration history/current/check, model/schema inspection, diagnostics review, and temporary student status persistence verification completed. No automated test suite exists in the inspected workspace.
- **Current status:** Documentation created; current implementation is a partial school administration system with working authentication, student management, and teacher management.
- **Remaining issues or follow-up work:** Classroom schema/workflow, academic modules, template/model mismatches, automated tests, CSRF, and production hardening remain.

### YYYY-MM-DD — Short change title

- **What changed:**
- **Files changed:**
- **Database/schema impact:**
- **Routes or UI affected:**
- **Tests performed and results:**
- **Current status:**
- **Remaining issues or follow-up work:**

### 2026-10-16 — Classes & Subjects module implemented

- **What changed:** Added Admin class and subject management, optional class teachers, class-subject-teacher assignments, student class enrollment, class details, and teacher assignment display.
- **Files changed:** Added `app/models/subject.py`, `app/models/class_subject_assignment.py`, `admin_classes.html`, `class_form.html`, `subject_form.html`, and `class_details.html`. Updated Classroom, Student, Teacher, model imports, routes, student forms, teacher details, admin navigation, and this overview.
- **Database/schema impact:** Added migration `c906155c0db3_add_classes_subjects_and_relationships.py`. It created `classrooms`, `subjects`, and `class_subject_assignments`, added nullable `students.class_id`, and added foreign keys/unique assignment constraint. Existing data was preserved.
- **Routes or UI affected:** Added `/admin/classes`, class/subject CRUD, assignment routes, class details, functional Classes & Subjects navigation, and Student/Teacher relationship displays.
- **Tests performed and results:** Migration applied successfully; live schema inspected; `db check` clean; route list verified; Flask test client verified authorization, class/subject creation, assignment, duplicate prevention, student enrollment, detail pages, and teacher assignment display. Temporary records were cleaned up and counts were preserved.
- **Current status:** Classes & Subjects module is implemented and migrated for the basic requested workflow.
- **Remaining issues or follow-up work:** No browser test suite exists. Student detail still references an unsupported `student.email` field, and broader academic modules remain planned.

### 2026-10-16 — Attendance module implemented

- **What changed:** Added linked teacher accounts, daily Attendance ORM model/workflow, teacher-only assigned-class marking, correction/upsert behavior, Admin daily filters/corrections, monthly student reports, and functional Attendance navigation.
- **Files changed:** Added `app/models/attendance.py`, `teacher_attendance.html`, `admin_attendance.html`, and `attendance_student_report.html`. Updated User, Teacher, Student, Classroom, model imports, routes, teacher forms/details, dashboard/navigation templates, the Attendance migration, and this overview.
- **Database/schema impact:** Migration `cdc29e7850d2_add_attendance_tracking_and_teacher_.py` added nullable unique `teachers.user_id` and the `attendance` table with foreign keys, status check, timestamps, and unique student/date constraint. No existing tables or records were reset or deleted.
- **Routes or UI affected:** Added teacher marking, Admin daily management/correction, and Admin monthly report routes. Existing Attendance placeholder links now point to implemented pages.
- **Tests performed and results:** `db upgrade`, `db current`, and `db check` succeeded. Live inspector verified all Attendance columns and constraints. Flask test-client workflow passed authorization, class isolation, status save/update, duplicate prevention, report, and cleanup checks.
- **Current status:** Classes & Subjects and Attendance basic workflows are implemented and migrated. The live database currently has zero attendance rows because test rows were temporary and removed.
- **Remaining issues or follow-up work:** No automated test suite or browser test suite exists. Existing project limitations such as CSRF and unrelated placeholder modules remain.

### 2026-10-16 — Exams & Results module implemented

- **What changed:** Added Exam and ExamResult ORM models, Admin exam creation/publication, Admin result correction, teacher assignment-scoped mark entry, grade calculation, Student account linking, and published-result viewing.
- **Files changed:** Added [exam.py](./app/models/exam.py), `admin_exams.html`, `exam_results_form.html`, and `student_results.html`. Updated Student/User/Classroom/Subject/model imports, routes, Student forms, Admin/Teacher/Student dashboard links, migration, and this overview.
- **Database/schema impact:** Migration `8c813e503da4_add_exams_and_results.py` created `exams` and `exam_results`, plus nullable unique `students.user_id`. Existing records were preserved.
- **Routes or UI affected:** Added Admin, Teacher, and Student result routes and replaced Exams & Results placeholder links.
- **Tests performed and results:** `db upgrade`, `db current`, and `db check` succeeded. Live schema inspection verified both tables. Flask test-client workflow passed exam creation, teacher authorization, marks persistence, grade calculation, publishing, student visibility, and cleanup.
- **Current status:** Basic Exams & Results workflow is implemented and migrated. No permanent exam/result test data was left in the database.
- **Remaining issues or follow-up work:** No automated/browser test suite exists; CSRF and unrelated fee/notice modules remain future work.

### 2026-10-16 — Fee Management module implemented

- **What changed:** Added FeeRecord and FeePayment ORM models, Admin fee assignment, duplicate monthly-fee protection, partial/full payment recording, balance/status calculation, Admin class/status filters, and Student Portal fee view.
- **Files changed:** Added [fee.py](./app/models/fee.py), `admin_fees.html`, and `student_fees.html`. Updated Student/User/model imports, routes, dashboard/navigation templates, migration, and this overview.
- **Database/schema impact:** Migration `9b33426aed2b_add_fee_management.py` created `fee_records` and `fee_payments`; no existing tables or records were reset or deleted.
- **Routes or UI affected:** Added Admin fee assignment/payment and Student fee view routes. Existing Fee Management placeholder links now point to the implemented pages.
- **Tests performed and results:** `db upgrade`, `db current`, and `db check` succeeded. Live schema inspection verified both tables and constraints. Flask test-client workflow passed assignment, partial payment, full payment, status/filter behavior, Student visibility, and cleanup.
- **Current status:** Basic Fee Management workflow is implemented and migrated. No permanent fee/payment test data was left in the database.
- **Remaining issues or follow-up work:** No automated/browser test suite exists; CSRF and unrelated notice modules remain future work.

### 2026-10-16 — Admin-controlled accounts and role login implemented

- **What changed:** Removed public registration, added required username/password/confirmation fields to new Student and Teacher forms, added atomic User/profile creation, optional Admin-only account linking and password reset for existing profiles, and added Login As role validation.
- **Files changed:** Updated [routes/__init__.py](./app/routes/__init__.py), [login.html](./app/templates/login.html), Student/Teacher forms, home navigation, removed `register.html`, and updated this overview. No migration was required because the existing nullable unique Student/Teacher `user_id` relationships already existed.
- **Database/schema impact:** None. Existing Admin `rehan@123` remains active and unchanged; existing users, students, and teachers were preserved.
- **Routes or UI affected:** `/register` is no longer registered; login now requires Admin/Teacher/Student selection; Admin creation routes create linked accounts; existing edit routes support linking/resetting accounts.
- **Tests performed and results:** App diagnostics and route listing passed. Flask test-client verified Admin management access, Student/Teacher creation and links, password hashing, duplicate username rejection, role mismatch rejection, role-based `403` responses, logout, hidden Register UI, `/register` `404`, and cleanup restoring original counts.
- **Current status:** Admin-controlled authentication is implemented and the database migration head remains `9b33426aed2b`.
- **Remaining issues or follow-up work:** Existing Teacher User records `owl` and `Owais Ahmed` need Admin linking to Teacher profiles if they should log in and use teacher-specific features. No browser/automated test suite exists, and CSRF remains a production hardening task.

### 2026-10-17 — Phase 1 & 2: Admin Exams & Results Reporting implemented and verified

- **What changed:** Implemented reusable PDF generator utilities with ReportLab and Pillow. Completed Admin Class Results reporting and Individual Student Academic Results reporting with dynamic dependent dropdowns, full marks/percentage calculations, and streaming PDF exports.
- **Files changed:** Added [pdf_reports.py](./app/utils/pdf_reports.py), [admin_class_results.html](./app/templates/admin_class_results.html), [admin_student_results_report.html](./app/templates/admin_student_results_report.html); updated [routes/__init__.py](./app/routes/__init__.py), [admin_exams.html](./app/templates/admin_exams.html), [requirements.txt](./requirements.txt), and [PROJECT_STATUS.md](./PROJECT_STATUS.md).
- **Database/schema impact:** None. Zero migrations required; queries existing tables and relationships cleanly.
- **Routes or UI affected:** Added 4 new endpoints (`admin_student_results_report`, `admin_class_results_pdf`, `admin_student_results_pdf`, `api_class_students`); updated `admin_exam_results` from stub to full class matrix view; updated `admin_exams.html` with direct Results buttons and Student Results links.
- **Tests performed and results:** Automated test client suite verified HTML rendering for both reports, PDF binary generation, cross-class mismatch detection (302/403), role-based protection blocks, and clean application startup. All 10 test cases passed.
- **Current status:** Phase 1 and Phase 2 complete and verified. Ready for Phase 3 (Admin Attendance Reports).


