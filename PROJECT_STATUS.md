# School Management System — Project Status & Reporting Architecture Audit

## 1. Documentation & Environment Status

- **Audit Date:** 2026-10-17
- **Project Root:** `F:\Full Stack Zone Internship\school_management_system - Copy (2)`
- **Runtime & Environment:**
  - Python 3.14.7 in local virtualenv (`.venv`)
  - Flask 3.1.3, SQLAlchemy 2.1.4, Flask-SQLAlchemy 3.1.1, Flask-Migrate 4.1.0, Werkzeug 3.1.9, Jinja2 3.1.6
  - ReportLab 5.0.1, Pillow 13.0.0, Charset-Normalizer 3.5.2 (verified installed in active `.venv`)
  - PostgreSQL with `psycopg 3.3.6` (database: `school_management_db`)
  - Alembic Migration Head: `2f3a8d1c4b6e` (`2f3a8d1c4b6e_add_notices.py`)
- **Live Database Inspection (Read-Only Verification):**
  - `classrooms`: 3 rows (Class 2: ICS, Class 3: Statistics, Class 9: Medical)
  - `students`: 6 rows (all assigned to classes, 0 unassigned; linked student user accounts: Ahmed Bhinder, Maaz, Abdullah)
  - `teachers`: 6 rows (Owais Ahmad, Imran, Zameer Butt, Mr Junaid, Hassan Ahmed, Gulam Rasool; linked user accounts: zameer@123, junaid@123, hassan@123, gulam@123)
  - `class_subject_assignments`: 11 rows (linking teachers to classes and subjects)
  - `subjects`: 7 rows (Physics, Computer, English, Urdu, Maths, Statistics, Biology)
  - `attendance`: 4 rows (real records for 2026-10-17)
  - `exams`: 3 rows (Exam 2: QB01, Exam 3: Mid Term ICS, Exam 4: Mid Term Medical)
  - `exam_results`: 6 rows (real marks and grades for exams 3 and 4)
  - `fee_records`: 2 rows (Ahmed Bhinder: 50,000 paid; Ali: 80,000 unpaid)
  - `fee_payments`: 1 row (50,000 via Bank Transfer for Ahmed Bhinder)
  - `notices`: 1 row
  - `users`: 10 rows (1 admin: `rehan@123`, 6 teachers, 3 students)
- **Current Route Surface:** 65 registered endpoints in `main` Blueprint (`app/routes/__init__.py`).
- **Implementation Status:** Phase 1 (Core PDF Engine), Phase 2 (Admin Exams & Results Reporting), Phase 3 (Admin Attendance Reports), and Phase 4 (Admin Fee Reports) are **COMPLETED AND VERIFIED**. Database records and schema remain strictly unmodified.

---

## 2. Detailed Audit of Requested Reporting Features

### 2.1 Admin Exams & Results (COMPLETED & VERIFIED)

#### Implementation Summary
- **Route:** `main.admin_exams` (`/admin/exams`, GET/POST)
  - Allows Admin to create an Exam for an active class (`name`, `class_id`, `exam_date`, `total_marks`).
  - Lists existing exams with a table and toggles publication (`main.publish_exam`, POST `/admin/exams/<int:exam_id>/publish`).
  - **Updated:** Now includes a direct "Results" action button for every exam and an "Individual Student Results" quick navigation link.
- **Route:** `main.admin_exam_results` (`/admin/exams/<int:exam_id>/results`, GET)
  - Full class-results matrix view rendered via `app/templates/admin_class_results.html`.
  - Displays all active students enrolled in the class, subject-wise marks, total marks obtained, max marks, and calculated percentage.
  - Clearly distinguishes between unrecorded marks (`None` / `"—"`) and recorded scores (including zero).
  - Displays 4-stat class summary banner: total enrolled, students with results, students without results, and class average percentage.
- **Route:** `main.admin_class_results_pdf` (`/admin/exams/<int:exam_id>/results/pdf`, GET)
  - Generates and streams a downloadable landscape A4 PDF report matching the SchoolPortal Navy/Blue brand design.
  - Implemented in `app/utils/pdf_reports.py` via `generate_class_results_pdf()`.
- **Route:** `main.admin_student_results_report` (`/admin/reports/student-results`, GET)
  - Two-step dependent selection: select Class -> select Student -> view complete examination record.
  - Backend validation verifies that the selected student strictly belongs to the selected class (redirects with alert on mismatch).
  - Displays student header card with avatar and metrics, plus exam-by-exam cards containing subject breakdowns, marks, percentages, grades, and teacher remarks.
  - Template: `app/templates/admin_student_results_report.html`.
- **Route:** `main.admin_student_results_pdf` (`/admin/reports/student-results/pdf`, GET)
  - Generates and streams a portrait A4 student academic report card PDF.
  - Strictly validates student class membership (aborts 403 on mismatch).
  - Column width calculations mathematically calibrated to printable A4 width (`usable_w = 18.0 cm`).
- **API Endpoint:** `main.api_class_students` (`/api/classes/<int:class_id>/students`, GET)
  - Role-protected JSON endpoint returning active students for dynamic frontend dropdown population without page reloads.

---

### 2.2 Admin Attendance Reports (COMPLETED & VERIFIED)

#### Implementation Summary
- **Route:** `main.admin_attendance` (`/admin/attendance`, GET)
  - Daily attendance overview. Filters by `class_id`, single `date`, and `status`. Displays status summary count cards and allows updating individual records (`main.update_attendance`).
  - **Updated:** Header and sidebar navigation now provide direct links to both "Class attendance report" and "Monthly student report".
- **Route:** `main.student_attendance_report` (`/admin/attendance/reports/student`, GET)
  - Two-step dependent selection: select Classroom -> dynamically load enrolled students via `/api/classes/<id>/students` -> select Student -> Month picker.
  - Server-side cross-class validation: rejects requests where `student.class_id != class_id` with flash warning redirect.
  - Attendance rate calculation: strictly counts recorded sessions `(Present + Late) / total_recorded_days * 100`, never inventing missing days.
  - Modern SchoolPortal design matching other reporting views with summary cards and session breakdown table.
  - Template: `app/templates/attendance_student_report.html`.
- **Route:** `main.admin_student_attendance_pdf` (`/admin/attendance/reports/student/pdf`, GET)
  - Generates and streams a downloadable portrait A4 PDF report matching the SchoolPortal Navy/Blue brand design.
  - Returns 403 Forbidden on cross-class student tampering.
  - Usable width: exactly 18.0 cm (`A4[0] - 3.0 * cm`).
  - Generator: `generate_student_attendance_pdf()` in `app/utils/pdf_reports.py`.
- **Route:** `main.class_attendance_report` (`/admin/attendance/reports/class`, GET)
  - Class-wise monthly attendance report for an entire classroom.
  - Aggregates enrolled students, overall sessions held, class average attendance rate, and counts for Present, Absent, and Late.
  - Student roster table displaying each student's roll number, name, status tallies, attendance rate with color-coded progress bars, and direct link to their individual report.
  - Template: `app/templates/attendance_class_report.html`.
- **Route:** `main.admin_class_attendance_pdf` (`/admin/attendance/reports/class/pdf`, GET)
  - Generates and streams a downloadable landscape A4 PDF report.
  - Usable width: exactly 26.7 cm (`landscape(A4)[0] - 3.0 * cm`).
  - Table widths fit within printable area without cutoff or overlap.
  - Generator: `generate_class_attendance_pdf()` in `app/utils/pdf_reports.py`.

---

### 2.3 Admin Fee Reports (COMPLETED & VERIFIED)

#### Implementation Summary
- **Route:** `main.admin_fees` (`/admin/fees`, GET/POST)
  - POST assigns a fee to a student (`student_id`, `title`, `billing_month`, `amount`, `due_date`, `notes`).
  - GET displays fee records filtered by optional `class_id` and `status` (`Paid`, `Partial`, `Unpaid`, `Overdue`).
  - Contains an inline payment form invoking `main.record_fee_payment` (`/admin/fees/<int:fee_id>/payment`, POST).
  - **Updated:** Now computes aggregate overview metrics across the system using accurate `Decimal` arithmetic (Total Assessed, Total Collected, Outstanding Balance, Collection Rate) and provides direct navigation buttons to both Class Fee Report and Student Fee Report in the topbar and sidebar.
- **Route:** `main.class_fee_report` (`/admin/fees/reports/class`, GET)
  - Class-wise monthly fee collection report.
  - Allows selecting classroom, target billing month, and status filters (`Paid`, `Partial`, `Unpaid`, `Overdue`).
  - Summary metrics card row: Enrolled Students, Total Assessed, Total Collected, Outstanding Balance, and Collection Rate progress bar.
  - Student fee breakdown table: Full Name, Roll Number, Invoices count, Total Assessed, Total Paid, Balance Due, Clearance Status badge, and direct links to individual student statement and PDF download.
  - Template: `app/templates/fee_class_report.html`.
- **Route:** `main.admin_class_fee_pdf` (`/admin/fees/reports/class/pdf`, GET)
  - Generates and streams a downloadable landscape A4 class fee summary PDF.
  - Usable width: exactly 26.7 cm (`landscape(A4)[0] - 3.0 * cm`).
  - Table widths fit within printable area without cutoff or overlap.
  - Generator: `generate_class_fee_pdf()` in `app/utils/pdf_reports.py`.
- **Route:** `main.admin_student_fee_report` (`/admin/fees/reports/student`, GET)
  - Dual lookup mode:
    1. Two-step dependent selection: select Classroom -> dynamically load students via `/api/classes/<class_id>/students` -> select Student -> view complete statement ledger.
    2. Student search: instant search by student name or roll number (`search`) returning matching students with fee totals and statement links.
  - Status filters (`Paid`, `Partial`, `Unpaid`, `Overdue`).
  - Cross-class security validation: rejects mismatched student/class requests with flash warning redirect.
  - Complete statement ledger: Student header card, metric cards (Assessed, Paid, Balance, Payment Ratio), Invoices & Charges table with quick pay action, and Payment Transactions & Receipts table.
  - Template: `app/templates/fee_student_report.html`.
- **Route:** `main.admin_student_fee_pdf` (`/admin/fees/reports/student/pdf`, GET)
  - Generates and streams a downloadable portrait A4 student fee statement PDF.
  - Usable width: exactly 18.0 cm (`A4[0] - 3.0 * cm`).
  - Strict authorization and cross-class validation (aborts 403 on mismatch).
  - Generator: `generate_student_fee_pdf()` in `app/utils/pdf_reports.py`.

---

### 2.4 Admin Student Management & Complete Student Report

#### Existing Implementation
- **Route:** `main.admin_students` (`/admin/students`, GET)
  - Lists students with text search (`full_name`, `roll_number`) and status filter (`active`, `inactive`).
  - Does NOT allow filtering by `class_id`.
- **Route:** `main.student_details` (`/admin/students/<int:student_id>`, GET)
  - Loads a `Student` and renders `student_details.html`.
- **Template:** `student_details.html`
  - High-quality visual layout, but displays ONLY personal demographic fields: Full Name, Roll Number, Phone, Date of Birth, Gender, Address, and Class Name.
  - Displays a broken reference to `student.email` (which does not exist on the `Student` model).
  - Completely omits the student's attendance records, examination results, and fee balances.

#### Missing Functionality
1. **Class Filter in Student Management:**
   - Admin cannot filter `/admin/students` by class.
2. **Complete Individual Student Academic Report:**
   - The student detail page needs to integrate all existing academic records:
     - **Basic Info & Status:** Full name, roll number, class assignment, contact details, active status.
     - **Attendance Summary:** Recorded days, Present, Absent, Late counts, and attendance rate percentage.
     - **Academic Results:** All published and recorded exams, subjects, marks obtained, total marks, grades, and remarks.
     - **Financial Status:** Invoiced fees, total paid, outstanding balance, and fee records breakdown.
3. **Complete Student Report PDF:**
   - Ability for Admin (and Student for their own profile) to download a comprehensive multi-section Academic Profile PDF.

#### Root Cause
- `student_details.html` was designed in an earlier phase before the Attendance, Exams, and Fee modules were migrated. It was never enhanced to pull from the ORM relationships (`student.attendance_records`, `student.exam_results`, `student.fee_records`).

---

### 2.5 PDF Report System

#### Current Environment Inspection
- Running Python 3.14.7 on Windows x64.
- No PDF generation packages are currently installed in `.venv`.
- Tested package resolution via `pip install --dry-run reportlab`:
  ```text
  Collecting reportlab
    Downloading reportlab-5.0.1-py3-none-any.whl.metadata (1.6 kB)
  Collecting pillow>=9.0.0 (from reportlab)
    Downloading pillow-13.0.0-cp314-cp314-win_amd64.whl.metadata (9.3 kB)
  Collecting charset-normalizer (from reportlab)
    Using cached charset_normalizer-3.5.2-cp314-cp314-win_amd64.whl.metadata (47 kB)
  Would install charset-normalizer-3.5.2 pillow-13.0.0 reportlab-5.0.1
  ```
- **Library Evaluation:**
  - `weasyprint`: Requires native GTK3+, Pango, and Cairo system DLLs on Windows. These are not present on the host OS and installation would fail or require complex non-Python binaries.
  - `pdfkit` / `wkhtmltopdf`: Depends on external deprecated `wkhtmltopdf.exe` binary.
  - `reportlab`:
    - **Recommended Solution.**
    - Has official wheels for `cp314-win_amd64`.
    - Zero external system DLLs or binaries required.
    - Standard Platypus architecture (`SimpleDocTemplate`, `Table`, `TableStyle`, `Paragraph`, `Spacer`, `colors`) enables clean, pixel-perfect, branded PDF layouts.
    - In-memory generation using `io.BytesIO()` streamed via `flask.send_file(..., as_attachment=True)`.

#### Required PDF Documents (7 Total)
1. **Individual Student Attendance Report:** Student details, selected month/range, status counts, attendance %, daily table.
2. **Class-Wide Attendance Report:** Class details, class teacher, period, class attendance rate, student-by-student summary table.
3. **Individual Student Result Report (Report Card):** Student details, exam title, exam date, subject-wise marks, max marks, percentages, grades, remarks, overall GPA/grade.
4. **Class-Wide Result Report:** Class details, exam title, subject columns, student marks matrix, class average, pass/fail metrics.
5. **Individual Student Fee Statement:** Student details, total invoiced, total paid, total balance, fee breakdown, payment history with receipt references.
6. **Class-Wide Fee Report:** Class details, total fees assigned, total collected, total outstanding, collection %, student payment roster.
7. **Complete Individual Student Academic Report:** Multi-page comprehensive dossier (Demographics + Attendance Record + Exam Performance + Fee Status).

---

### 2.6 Teacher and Student Portals

#### Role-Based Access Boundary Audit

| Area / Report | Admin | Teacher | Student |
|---|:---:|:---:|:---:|
| **Class Attendance Report** | All classes | Only assigned classes (where user is Class Teacher) | Denied (403) |
| **Student Attendance Report** | All students | Only students in assigned classes | Only their own record |
| **Class Exam Results Report** | All classes | Only assigned classes / assigned subjects | Denied (403) |
| **Student Exam Result Report** | All students | Only students in assigned classes | Only their own published results |
| **Class Fee Report** | All classes | **STRICTLY DENIED** (No fee access) | Denied (403) |
| **Student Fee Report** | All students | **STRICTLY DENIED** (No fee access) | Only their own fee records |
| **Complete Student Academic Report** | All students | Only students in assigned classes (excluding fee section) | Only their own record |
| **PDF Downloads** | All 7 reports | Permitted attendance & result reports only | Permitted personal reports only |

#### Security Checks in Existing Code
- `_current_teacher()` validates that the logged-in user is an active teacher.
- `_authorized_teacher_class(class_id)` verifies that the teacher is either the class teacher or teaches an active subject in that class.
- `_authorized_attendance_class(class_id)` restricts daily attendance marking to the class teacher.
- `_current_student()` binds strictly to `session["user_id"]` via `user.student_profile`.
- **Identified Gap:** Existing routes do not yet provide reporting views for teachers or students. When implemented, backend validation must prevent any teacher from querying unassigned classes/students, and students must never be allowed to pass a custom `student_id` parameter.

---

### 2.7 Security, Parameter Validation & Data Integrity

1. **Backend Parameter Validation:**
   - Any route accepting `class_id` and `student_id` must verify that the student actually belongs to that class:
     ```python
     student = Student.query.filter_by(id=student_id, class_id=class_id).first_or_404()
     ```
   - Manually modified query parameters or form fields will trigger a `404` or `403` rather than exposing unassociated records.
2. **Dynamic Dropdown Implementation:**
   - To provide the required "Select Class -> Load Students -> Select Student" workflow cleanly:
     - Provide an authenticated JSON endpoint: `GET /api/classes/<int:class_id>/students`.
     - Validates role permissions: Admin gets all active students in the class; Teacher gets students only if authorized for that class; Student gets 403.
     - Returns: `[{"id": 1, "full_name": "...", "roll_number": "..."}]`.
     - Vanilla JavaScript dynamically populates the Student dropdown upon Class selection.
     - Graceful fallback: If accessed via standard GET query parameters (`?class_id=...&student_id=...`), the server renders the pre-filtered student list directly.
3. **Database Schema Compatibility:**
   - **Crucial Finding:** The existing PostgreSQL database schema and SQLAlchemy ORM models ALREADY contain all necessary tables, columns, foreign keys, unique constraints, and relationships.
   - **NO database migrations or schema alterations are required.**
   - All reports will query real database rows directly.

---

## 3. Implementation Sequence & Progress

### Phase 1: PDF Generation Engine & Core Infrastructure [COMPLETED & VERIFIED]
- Added `reportlab==5.0.1`, `pillow==13.0.0`, and `charset-normalizer==3.5.2` to `requirements.txt` (clean UTF-8) and verified installed in local `.venv`.
- Created `app/utils/pdf_reports.py`:
  - `_NumberedCanvas` with confidential footer and "Page X of Y" dynamic pagination.
  - SchoolPortal branding styles (Navy `#111c3a`, Blue `#4568f5`, Blue Light `#edf1ff`, Muted `#7b8499`).
  - Standalone generator functions returning `io.BytesIO`: `generate_class_results_pdf` and `generate_student_results_pdf`.
  - Mathematically verified column width allocations conforming to printable A4 dimensions.
- Created dynamic dropdown helper endpoint:
  - `GET /api/classes/<int:class_id>/students` (role-protected for admin, returns active class students JSON).

### Phase 2: Admin Exams & Results Reporting [COMPLETED & VERIFIED]
- Updated `main.admin_exams` and created dedicated results routes:
  - `main.admin_exam_results` (`/admin/exams/<int:exam_id>/results`): Displays overall class results matrix, student marks, grades, class average, and distinction of missing marks vs zero.
  - `main.admin_class_results_pdf` (`/admin/exams/<int:exam_id>/results/pdf`): Streams landscape A4 class results matrix PDF.
  - `main.admin_student_results_report` (`/admin/reports/student-results`): Two-step selection (Class -> Student) with individual exam results breakdown.
  - `main.admin_student_results_pdf` (`/admin/reports/student-results/pdf`): Streams portrait A4 student report card PDF.
- Updated `admin_exams.html` to add direct "Results" table action buttons and "Individual Student Results" navigation links.
- Created `admin_class_results.html` and `admin_student_results_report.html` (with dynamic JavaScript dropdown population via `/api/classes/<id>/students`).
- All 10 end-to-end test cases passed via Flask test-client (HTML views, PDF binary validity, cross-class security checks, and role protection).

### Phase 3: Admin Attendance Reports [COMPLETED & VERIFIED]
- Enhanced `main.student_attendance_report` (`/admin/attendance/reports/student`):
  - Added Classroom selector and dynamic student loader via `/api/classes/<class_id>/students`.
  - Enforced server-side cross-class validation (rejects student mismatch with flash warning redirect).
  - Calculated attendance percentage strictly from recorded attendance `(Present + Late) / total_recorded_days * 100` without inventing missing records.
  - Added PDF download route: `main.admin_student_attendance_pdf` (`/admin/attendance/reports/student/pdf`).
- Implemented `main.class_attendance_report` (`/admin/attendance/reports/class`):
  - Allows selecting class and target month.
  - Aggregates enrolled students, overall sessions, class average attendance rate, and counts for Present, Absent, and Late.
  - Student roster table with status counts, rates, progress bars, and link to individual reports.
  - Added PDF download route: `main.admin_class_attendance_pdf` (`/admin/attendance/reports/class/pdf`).
- Created ReportLab PDF generators: `generate_student_attendance_pdf` (portrait A4, 18.0 cm width) and `generate_class_attendance_pdf` (landscape A4, 26.7 cm width).
- Updated `admin_attendance.html` with navigation links to both reports; updated `attendance_student_report.html` and created `attendance_class_report.html`.
- Executed comprehensive non-destructive test suite (`test_phase3_attendance.py`) verifying:
  - Role-based authorization: unauthenticated and student users blocked (302/403).
  - Admin HTML views for both class and student reports with empty-state handling.
  - PDF binary validity (`%PDF-`, >1000 bytes) for both reports.
  - Cross-class security validation (302 on HTML, 403 on PDF).
  - Attendance percentage accuracy (never dividing by 31 days).
  - Teacher attendance marking regression check.
  - Database row count preservation across all 12 tables.

### Phase 4: Admin Fee Reports [COMPLETED & VERIFIED]
- Enhanced `main.admin_fees` (`/admin/fees`):
  - Added overall fee collection statistics cards (Total Assessed, Total Collected, Outstanding Balance, Collection Rate) using accurate `Decimal` arithmetic.
  - Added action buttons and sidebar navigation links to Class Fee Report and Student Fee Report.
- Implemented `main.class_fee_report` (`/admin/fees/reports/class`):
  - Classroom selector, target billing month filter, and status filters (`Paid`, `Partial`, `Unpaid`, `Overdue`).
  - Class summary metrics cards and student fee roster table.
  - Added PDF download route: `main.admin_class_fee_pdf` (`/admin/fees/reports/class/pdf`).
- Implemented `main.admin_student_fee_report` (`/admin/fees/reports/student`):
  - Dual lookup: Class selector + dynamic dependent student dropdown via `/api/classes/<class_id>/students`, plus search bar for student name / roll number.
  - Status filters (`Paid`, `Partial`, `Unpaid`, `Overdue`).
  - Server-side cross-class validation (rejects student mismatch with flash warning redirect).
  - Complete statement ledger: Student header card, stat cards, Fee Invoices & Charges table with quick payment action, and Payment Transactions & Receipts table.
  - Added PDF download route: `main.admin_student_fee_pdf` (`/admin/fees/reports/student/pdf`).
- Created ReportLab PDF generators: `generate_student_fee_pdf` (portrait A4, 18.0 cm width) and `generate_class_fee_pdf` (landscape A4, 26.7 cm width).
- Created modern SchoolPortal templates: `fee_class_report.html` and `fee_student_report.html`.
- Executed comprehensive non-destructive test suite (`test_phase4_fees.py`) verifying:
  - Role-based authorization: unauthenticated, student, and teacher users blocked (302/403).
  - Admin HTML views for overview, class report, and student report with empty/prompt states.
  - Multi-student name/roll-number search functionality.
  - PDF binary validity (`%PDF-`, >1000 bytes) for both reports.
  - Cross-class security validation (302 on HTML, 403 on PDF).
  - Accurate `Decimal` arithmetic (`Assessed == Paid + Balance`).
  - Full regression checks on Phase 2 (Exams & Results) and Phase 3 (Attendance).
  - Database row count preservation across all tables.

### Phase 5: Admin Student Management & Complete Academic Report [PENDING]
- Update `main.admin_students` (`/admin/students`):
  - Add Class filter dropdown alongside existing search and active/inactive status.
- Enhance `main.student_details` (`/admin/students/<int:student_id>`):
  - Upgrade `student_details.html` to a complete academic dossier:
    - Personal info (correcting the invalid `student.email` reference).
    - Attendance summary and recent records.
    - Exam results, subject marks, and grades.
    - Fee status, billed amounts, paid amounts, balance.
  - Add Complete Academic Report PDF export:
    - Route: `/admin/students/<int:student_id>/report/pdf`.

### Phase 6: Teacher Portal Reporting Features [PENDING]
- Provide authorized reporting in Teacher Portal:
  - Class attendance report & PDF download for classes where the teacher is Class Teacher (`/teacher/reports/attendance/class/<int:class_id>`).
  - Class exam results report & PDF download for assigned classes/subjects (`/teacher/reports/results/class/<int:class_id>`).
  - Ensure zero access to fee reports or unassigned classes.
- Update `teacher_dashboard.html` and `teacher_class_details.html` with authorized report links.

### Phase 7: Student Portal Reporting Features [PENDING]
- Provide student-scoped PDF downloads:
  - `main.student_attendance_pdf` (`/student/attendance/pdf`): Student downloads their own attendance report.
  - `main.student_results_pdf` (`/student/results/pdf`): Student downloads their published report card.
  - `main.student_fees_pdf` (`/student/fees/pdf`): Student downloads their fee statement.
  - `main.student_profile_pdf` (`/student/profile/pdf`): Student downloads their academic profile.
- Update `student_attendance.html`, `student_results.html`, `student_fees.html`, and `student_dashboard.html` with download buttons.

### Phase 8: Comprehensive End-to-End Testing & Verification [PENDING]
- Automated regression suite exercising all cross-portal reporting endpoints, PDF binary generation, and security boundaries.

---

## 4. Exact Next Step to Implement

**Begin Phase 5 (Admin Student Management & Complete Academic Report):**
1. Audit student profile fields and relationships (`Student`, `Classroom`, `Attendance`, `ExamResult`, `FeeRecord`).
2. Add class filter to `main.admin_students`.
3. Upgrade `student_details.html` to comprehensive student dossier with PDF generation.
