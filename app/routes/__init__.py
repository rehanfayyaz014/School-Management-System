
from werkzeug.security import generate_password_hash
from app.models import User
from werkzeug.security import check_password_hash
from app import db
import io
from flask import Blueprint, abort, jsonify, request, send_file
from sqlalchemy import or_

from flask import session,flash, redirect, url_for, render_template
from functools import wraps
from app.models import (
    Attendance,
    ClassSubjectAssignment,
    Classroom,
    Student,
    Subject,
    User,
    Exam,
    ExamResult,
    FeePayment,
    FeeRecord,
    Notice,
)
from app.models.teacher import Teacher
from datetime import date, datetime, timezone
from sqlalchemy.exc import IntegrityError
from decimal import Decimal, InvalidOperation
from app.utils.pdf_reports import (
    generate_class_results_pdf,
    generate_student_results_pdf,
    generate_class_attendance_pdf,
    generate_student_attendance_pdf,
    generate_student_fee_pdf,
    generate_class_fee_pdf,
    generate_student_overall_profile_pdf,
)

main = Blueprint("main", __name__)

def role_required(required_role):
    def decorator(view_function):
        @wraps(view_function)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("main.login"))

            if session.get("role") != required_role:
                return "Access Denied", 403

            return view_function(*args, **kwargs)

        return wrapper
    return decorator


ATTENDANCE_STATUSES = ("Present", "Absent", "Late")
EXAM_GRADES = ((90, "A+"), (80, "A"), (70, "B"), (60, "C"), (50, "D"), (0, "F"))


def _current_teacher():
    if session.get("role") != "teacher":
        return None
    return Teacher.query.filter_by(
        user_id=session.get("user_id"),
        is_active=True
    ).first()


def _attendance_classes_for_current_user():
    if session.get("role") == "admin":  
        return Classroom.query.order_by(Classroom.name.asc()).all()

    teacher = _current_teacher()
    if not teacher:
        return []

    return Classroom.query.filter_by(
        class_teacher_id=teacher.id,
        is_active=True
    ).order_by(Classroom.name.asc()).all()


def _teacher_classes(teacher):
    return Classroom.query.filter(
        Classroom.is_active.is_(True),
        or_(
            Classroom.class_teacher_id == teacher.id,
            Classroom.id.in_(
                db.session.query(ClassSubjectAssignment.class_id).filter_by(
                    teacher_id=teacher.id
                )
            )
        )
    ).order_by(Classroom.name.asc()).all()


def _authorized_teacher_class(class_id):
    teacher = _current_teacher()
    if not teacher:
        abort(403)
    classroom = Classroom.query.filter(
        Classroom.id == class_id,
        Classroom.is_active.is_(True),
        or_(
            Classroom.class_teacher_id == teacher.id,
            Classroom.id.in_(
                db.session.query(ClassSubjectAssignment.class_id).filter_by(
                    teacher_id=teacher.id
                )
            )
        )
    ).first()
    if not classroom:
        abort(404)
    return classroom


def _authorized_attendance_class(class_id):
    classroom = db.session.get(Classroom, class_id)
    if not classroom:
        abort(404)

    if session.get("role") == "admin":
        return classroom

    teacher = _current_teacher()
    if not teacher or classroom.class_teacher_id != teacher.id:
        abort(403)

    return classroom


def _parse_attendance_date(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _grade_for_marks(marks, total_marks):
    percentage = (float(marks) / total_marks) * 100
    for minimum, grade in EXAM_GRADES:
        if percentage >= minimum:
            return grade
    return "F"


def _teacher_assignment_for_exam(exam, subject_id):
    teacher = _current_teacher()
    if not teacher:
        abort(403)
    assignment = ClassSubjectAssignment.query.filter_by(
        class_id=exam.class_id,
        subject_id=subject_id,
        teacher_id=teacher.id
    ).first()
    if not assignment:
        abort(403)
    return assignment


def _exam_subjects(class_id):
    return ClassSubjectAssignment.query.filter_by(
        class_id=class_id
    ).join(Subject).order_by(Subject.name.asc()).all()


# Classes and subjects
@main.route("/admin/classes")
@role_required("admin")
def admin_classes():
    classrooms = Classroom.query.order_by(Classroom.name.asc()).all()
    subjects = Subject.query.order_by(Subject.name.asc()).all()
    teachers = Teacher.query.filter_by(is_active=True).order_by(
        Teacher.full_name.asc()
    ).all()

    return render_template(
        "admin_classes.html",
        classrooms=classrooms,
        subjects=subjects,
        teachers=teachers
    )


def _parse_money(value):
    try:
        amount = Decimal(value)
        return amount if amount > 0 else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def _fee_records_for_student(student_id):
    return FeeRecord.query.filter_by(student_id=student_id).order_by(
        FeeRecord.due_date.desc(), FeeRecord.id.desc()
    ).all()


NOTICE_AUDIENCES = {
    "all": "Everyone",
    "teacher": "Teachers",
    "student": "Students",
}


def _published_notices_for_role(role):
    today = date.today()
    return Notice.query.filter(
        Notice.is_published.is_(True),
        Notice.notice_date <= today,
        db.or_(Notice.expires_on.is_(None), Notice.expires_on >= today),
        Notice.audience.in_(("all", role))
    ).order_by(Notice.notice_date.desc(), Notice.id.desc()).all()


def _parse_notice_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _current_student():
    if session.get("role") != "student":
        return None
    user = db.session.get(User, session.get("user_id"))
    return user.student_profile if user else None


@main.route("/admin/classes/new", methods=["GET", "POST"])
@role_required("admin")
def add_classroom():
    teachers = Teacher.query.filter_by(is_active=True).order_by(
        Teacher.full_name.asc()
    ).all()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip() or None
        class_teacher_id = request.form.get("class_teacher_id", type=int)
        is_active = request.form.get("is_active") == "on"

        if not name:
            flash("Class name is required.", "danger")
        elif Classroom.query.filter_by(name=name).first():
            flash("This class name already exists.", "danger")
        elif class_teacher_id and not db.session.get(Teacher, class_teacher_id):
            flash("Selected class teacher was not found.", "danger")
        else:
            classroom = Classroom(
                name=name,
                description=description,
                class_teacher_id=class_teacher_id,
                is_active=is_active
            )
            try:
                db.session.add(classroom)
                db.session.commit()
                flash("Class added successfully.", "success")
                return redirect(url_for("main.admin_classes"))
            except Exception:
                db.session.rollback()
                flash("Could not save class. Please try again.", "danger")

    return render_template(
        "class_form.html",
        classroom=None,
        teachers=teachers
    )


@main.route("/admin/classes/<int:class_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def edit_classroom(class_id):
    classroom = Classroom.query.get_or_404(class_id)
    teachers = Teacher.query.filter_by(is_active=True).order_by(
        Teacher.full_name.asc()
    ).all()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip() or None
        class_teacher_id = request.form.get("class_teacher_id", type=int)
        is_active = request.form.get("is_active") == "on"

        duplicate = Classroom.query.filter(
            Classroom.name == name,
            Classroom.id != classroom.id
        ).first()

        if not name:
            flash("Class name is required.", "danger")
        elif duplicate:
            flash("This class name already exists.", "danger")
        elif class_teacher_id and not db.session.get(Teacher, class_teacher_id):
            flash("Selected class teacher was not found.", "danger")
        else:
            classroom.name = name
            classroom.description = description
            classroom.class_teacher_id = class_teacher_id
            classroom.is_active = is_active
            try:
                db.session.commit()
                flash("Class updated successfully.", "success")
                return redirect(
                    url_for("main.class_details", class_id=classroom.id)
                )
            except Exception:
                db.session.rollback()
                flash("Could not update class. Please try again.", "danger")

    return render_template(
        "class_form.html",
        classroom=classroom,
        teachers=teachers
    )


@main.route("/admin/classes/<int:class_id>")
@role_required("admin")
def class_details(class_id):
    classroom = Classroom.query.get_or_404(class_id)
    subjects = Subject.query.filter_by(is_active=True).order_by(
        Subject.name.asc()
    ).all()
    teachers = Teacher.query.filter_by(is_active=True).order_by(
        Teacher.full_name.asc()
    ).all()

    return render_template(
        "class_details.html",
        classroom=classroom,
        subjects=subjects,
        teachers=teachers
    )


@main.route("/admin/classes/<int:class_id>/delete", methods=["POST"])
@role_required("admin")
def delete_classroom(class_id):
    classroom = Classroom.query.get_or_404(class_id)

    try:
        db.session.delete(classroom)
        db.session.commit()
        flash("Class deleted successfully.", "success")
    except Exception:
        db.session.rollback()
        flash(
            "Class could not be deleted. Please check its assignments.",
            "danger"
        )

    return redirect(url_for("main.admin_classes"))


@main.route("/admin/subjects/new", methods=["GET", "POST"])
@role_required("admin")
def add_subject():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip() or None
        is_active = request.form.get("is_active") == "on"

        if not name:
            flash("Subject name is required.", "danger")
        elif Subject.query.filter_by(name=name).first():
            flash("This subject name already exists.", "danger")
        else:
            subject = Subject(
                name=name,
                description=description,
                is_active=is_active
            )
            try:
                db.session.add(subject)
                db.session.commit()
                flash("Subject added successfully.", "success")
                return redirect(url_for("main.admin_classes"))
            except Exception:
                db.session.rollback()
                flash("Could not save subject. Please try again.", "danger")

    return render_template("subject_form.html", subject=None)


@main.route("/admin/subjects/<int:subject_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def edit_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip() or None
        is_active = request.form.get("is_active") == "on"
        duplicate = Subject.query.filter(
            Subject.name == name,
            Subject.id != subject.id
        ).first()

        if not name:
            flash("Subject name is required.", "danger")
        elif duplicate:
            flash("This subject name already exists.", "danger")
        else:
            subject.name = name
            subject.description = description
            subject.is_active = is_active
            try:
                db.session.commit()
                flash("Subject updated successfully.", "success")
                return redirect(url_for("main.admin_classes"))
            except Exception:
                db.session.rollback()
                flash("Could not update subject. Please try again.", "danger")

    return render_template("subject_form.html", subject=subject)


@main.route("/admin/subjects/<int:subject_id>/delete", methods=["POST"])
@role_required("admin")
def delete_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)

    try:
        db.session.delete(subject)
        db.session.commit()
        flash("Subject deleted successfully.", "success")
    except Exception:
        db.session.rollback()
        flash("Subject could not be deleted. Please try again.", "danger")

    return redirect(url_for("main.admin_classes"))


@main.route("/admin/classes/<int:class_id>/assignments", methods=["POST"])
@role_required("admin")
def assign_subject(class_id):
    classroom = Classroom.query.get_or_404(class_id)
    subject_id = request.form.get("subject_id", type=int)
    teacher_id = request.form.get("teacher_id", type=int)

    subject = db.session.get(Subject, subject_id) if subject_id else None
    teacher = db.session.get(Teacher, teacher_id) if teacher_id else None

    if not subject or not teacher:
        flash("Please select a valid subject and teacher.", "danger")
    elif ClassSubjectAssignment.query.filter_by(
        class_id=classroom.id,
        subject_id=subject.id
    ).first():
        flash("This subject is already assigned to the class.", "danger")
    else:
        assignment = ClassSubjectAssignment(
            classroom=classroom,
            subject=subject,
            teacher=teacher
        )
        try:
            db.session.add(assignment)
            db.session.commit()
            flash("Subject assigned successfully.", "success")
        except IntegrityError:
            db.session.rollback()
            flash("This class and subject assignment already exists.", "danger")
        except Exception:
            db.session.rollback()
            flash("Could not create assignment. Please try again.", "danger")

    return redirect(url_for("main.class_details", class_id=classroom.id))


@main.route(
    "/admin/classes/<int:class_id>/assignments/<int:assignment_id>/delete",
    methods=["POST"]
)
@role_required("admin")
def delete_assignment(class_id, assignment_id):
    classroom = Classroom.query.get_or_404(class_id)
    assignment = ClassSubjectAssignment.query.filter_by(
        id=assignment_id,
        class_id=classroom.id
    ).first_or_404()

    db.session.delete(assignment)
    db.session.commit()
    flash("Subject assignment removed.", "success")
    return redirect(url_for("main.class_details", class_id=classroom.id))


# Attendance
@main.route("/teacher/attendance", methods=["GET"])
@role_required("teacher")
def teacher_attendance():
    classrooms = _attendance_classes_for_current_user()
    class_id = request.args.get("class_id", type=int)
    selected_date = _parse_attendance_date(
        request.args.get("date", date.today().isoformat())
    )
    error = None

    if selected_date is None:
        selected_date = date.today()
        error = "Please select a valid attendance date."

    classroom = None
    students = []
    existing_statuses = {}

    if class_id:
        classroom = _authorized_attendance_class(class_id)
    elif classrooms:
        classroom = classrooms[0]

    if classroom:
        students = Student.query.filter_by(
            class_id=classroom.id
        ).order_by(Student.full_name.asc()).all()
        existing_statuses = {
            record.student_id: record.status
            for record in Attendance.query.filter_by(
                class_id=classroom.id,
                attendance_date=selected_date
            ).all()
        }

    return render_template(
        "teacher_attendance.html",
        classrooms=classrooms,
        classroom=classroom,
        students=students,
        selected_date=selected_date.isoformat(),
        existing_statuses=existing_statuses,
        error=error
    )


@main.route("/teacher/attendance/mark", methods=["POST"])
@role_required("teacher")
def mark_teacher_attendance():
    class_id = request.form.get("class_id", type=int)
    attendance_date = _parse_attendance_date(
        request.form.get("attendance_date")
    )
    classroom = _authorized_attendance_class(class_id)

    if attendance_date is None:
        flash("Please select a valid attendance date.", "danger")
        return redirect(url_for("main.teacher_attendance", class_id=classroom.id))

    student_ids = request.form.getlist("student_id", type=int)
    students = Student.query.filter(
        Student.id.in_(student_ids),
        Student.class_id == classroom.id
    ).all() if student_ids else []

    if len(students) != len(set(student_ids)):
        flash("One or more submitted students do not belong to this class.", "danger")
        return redirect(url_for(
            "main.teacher_attendance",
            class_id=classroom.id,
            date=attendance_date.isoformat()
        ))

    updates = []
    for student in students:
        status = request.form.get(f"status_{student.id}")
        if not status:
            continue
        if status not in ATTENDANCE_STATUSES:
            flash("An invalid attendance status was submitted.", "danger")
            return redirect(url_for(
                "main.teacher_attendance",
                class_id=classroom.id,
                date=attendance_date.isoformat()
            ))
        updates.append((student, status))

    if not updates:
        flash("No attendance records were submitted.", "warning")
        return redirect(url_for(
            "main.teacher_attendance",
            class_id=classroom.id,
            date=attendance_date.isoformat()
        ))

    now = datetime.now(timezone.utc)
    for student, status in updates:
        record = Attendance.query.filter_by(
            student_id=student.id,
            attendance_date=attendance_date
        ).first()

        if record and record.class_id != classroom.id:
            flash("This student's attendance belongs to another class.", "danger")
            return redirect(url_for(
                "main.teacher_attendance",
                class_id=classroom.id,
                date=attendance_date.isoformat()
            ))

        if record:
            record.status = status
            record.class_id = classroom.id
            record.recorded_by_user_id = session["user_id"]
            record.updated_at = now
        else:
            db.session.add(Attendance(
                student_id=student.id,
                class_id=classroom.id,
                attendance_date=attendance_date,
                status=status,
                recorded_by_user_id=session["user_id"],
                created_at=now,
                updated_at=now
            ))

    try:
        db.session.commit()
        flash("Attendance saved successfully.", "success")
    except IntegrityError:
        db.session.rollback()
        flash("Attendance could not be saved because of a duplicate record.", "danger")
    except Exception:
        db.session.rollback()
        flash("Attendance could not be saved. Please try again.", "danger")

    return redirect(url_for(
        "main.teacher_attendance",
        class_id=classroom.id,
        date=attendance_date.isoformat()
    ))


@main.route("/admin/attendance", methods=["GET"])
@role_required("admin")
def admin_attendance():
    classrooms = Classroom.query.order_by(Classroom.name.asc()).all()
    class_id = request.args.get("class_id", type=int)
    status = request.args.get("status", "all")
    date_value = request.args.get("date", date.today().isoformat())
    selected_date = _parse_attendance_date(date_value)
    date_error = None

    if selected_date is None:
        selected_date = date.today()
        date_error = "The selected date was invalid, so today is shown."

    query = Attendance.query.join(Student).join(Classroom).filter(
        Attendance.attendance_date == selected_date
    )
    if class_id:
        query = query.filter(Attendance.class_id == class_id)
    if status in ATTENDANCE_STATUSES:
        query = query.filter(Attendance.status == status)

    records = query.order_by(Student.full_name.asc()).all()
    counts = {}
    for value in ATTENDANCE_STATUSES:
        count_query = Attendance.query.filter(
            Attendance.attendance_date == selected_date,
            Attendance.status == value
        )
        if class_id:
            count_query = count_query.filter(Attendance.class_id == class_id)
        counts[value] = count_query.count()

    return render_template(
        "admin_attendance.html",
        classrooms=classrooms,
        records=records,
        class_id=class_id,
        status=status,
        selected_date=selected_date.isoformat(),
        date_error=date_error,
        counts=counts
    )


@main.route("/admin/attendance/<int:attendance_id>/update", methods=["POST"])
@role_required("admin")
def update_attendance(attendance_id):
    record = Attendance.query.get_or_404(attendance_id)
    status = request.form.get("status")

    if status not in ATTENDANCE_STATUSES:
        flash("Please select a valid attendance status.", "danger")
    else:
        record.status = status
        record.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        flash("Attendance updated successfully.", "success")

    return redirect(url_for(
        "main.admin_attendance",
        class_id=request.form.get("class_id", type=int),
        date=request.form.get("date"),
        status=request.form.get("filter_status", "all")
    ))


@main.route("/admin/attendance/reports/student", methods=["GET"])
@role_required("admin")
def student_attendance_report():
    """Admin individual student attendance report with class selection first."""
    classrooms = Classroom.query.order_by(Classroom.name.asc()).all()
    class_id = request.args.get("class_id", type=int)
    student_id = request.args.get("student_id", type=int)
    month = request.args.get("month", date.today().strftime("%Y-%m"))
    month_start = None
    month_error = None

    try:
        month_start = datetime.strptime(month, "%Y-%m").date()
    except (TypeError, ValueError):
        month = date.today().strftime("%Y-%m")
        month_start = datetime.strptime(month, "%Y-%m").date()
        month_error = "The selected month was invalid, so the current month is shown."

    if month_start.month == 12:
        month_end = date(month_start.year + 1, 1, 1)
    else:
        month_end = date(month_start.year, month_start.month + 1, 1)

    classroom = None
    students_in_class = []
    student = None
    records = []
    totals = {value: 0 for value in ATTENDANCE_STATUSES}

    if class_id:
        classroom = db.session.get(Classroom, class_id)
        if not classroom:
            flash("The selected class was not found.", "danger")
            return redirect(url_for("main.student_attendance_report"))

        students_in_class = (
            Student.query
            .filter_by(class_id=class_id, is_active=True)
            .order_by(Student.full_name.asc())
            .all()
        )

        if student_id:
            # Backend security: student must strictly belong to the selected class
            student = Student.query.filter_by(id=student_id, class_id=class_id).first()
            if not student:
                flash("The selected student does not belong to this class.", "danger")
                return redirect(url_for("main.student_attendance_report", class_id=class_id, month=month))

            records = (
                Attendance.query
                .filter(
                    Attendance.student_id == student.id,
                    Attendance.attendance_date >= month_start,
                    Attendance.attendance_date < month_end
                )
                .order_by(Attendance.attendance_date.asc())
                .all()
            )
            for record in records:
                if record.status in totals:
                    totals[record.status] += 1

    total_days = sum(totals.values())
    attendance_percentage = (
        ((totals["Present"] + totals["Late"]) / total_days) * 100
        if total_days else 0
    )

    return render_template(
        "attendance_student_report.html",
        classrooms=classrooms,
        classroom=classroom,
        class_id=class_id,
        students_in_class=students_in_class,
        student=student,
        student_id=student_id,
        month=month,
        month_error=month_error,
        records=records,
        totals=totals,
        total_days=total_days,
        attendance_percentage=attendance_percentage,
    )


@main.route("/admin/attendance/reports/student/pdf", methods=["GET"])
@role_required("admin")
def admin_student_attendance_pdf():
    """Generate and stream a monthly student attendance PDF report."""
    class_id = request.args.get("class_id", type=int)
    student_id = request.args.get("student_id", type=int)
    month = request.args.get("month", date.today().strftime("%Y-%m"))

    if not class_id or not student_id:
        flash("Select a class and student before downloading the PDF.", "danger")
        return redirect(url_for("main.student_attendance_report"))

    classroom = db.session.get(Classroom, class_id)
    if not classroom:
        abort(404)

    student = Student.query.filter_by(id=student_id, class_id=class_id).first()
    if not student:
        abort(403)

    try:
        month_start = datetime.strptime(month, "%Y-%m").date()
    except (TypeError, ValueError):
        month = date.today().strftime("%Y-%m")
        month_start = datetime.strptime(month, "%Y-%m").date()

    if month_start.month == 12:
        month_end = date(month_start.year + 1, 1, 1)
    else:
        month_end = date(month_start.year, month_start.month + 1, 1)

    records = (
        Attendance.query
        .filter(
            Attendance.student_id == student.id,
            Attendance.attendance_date >= month_start,
            Attendance.attendance_date < month_end
        )
        .order_by(Attendance.attendance_date.asc())
        .all()
    )
    totals = {value: 0 for value in ATTENDANCE_STATUSES}
    for record in records:
        if record.status in totals:
            totals[record.status] += 1

    total_days = sum(totals.values())
    attendance_percentage = (
        ((totals["Present"] + totals["Late"]) / total_days) * 100
        if total_days else 0
    )

    buffer = generate_student_attendance_pdf(
        student, classroom, month, records, totals, total_days, attendance_percentage
    )
    safe_name = student.full_name.replace(" ", "_")[:30]
    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="Student_Attendance_{}_{}.pdf".format(safe_name, month),
    )


@main.route("/admin/attendance/reports/class", methods=["GET"])
@role_required("admin")
def class_attendance_report():
    """Admin class-wise monthly attendance report."""
    classrooms = Classroom.query.order_by(Classroom.name.asc()).all()
    class_id = request.args.get("class_id", type=int)
    month = request.args.get("month", date.today().strftime("%Y-%m"))
    month_start = None
    month_error = None

    try:
        month_start = datetime.strptime(month, "%Y-%m").date()
    except (TypeError, ValueError):
        month = date.today().strftime("%Y-%m")
        month_start = datetime.strptime(month, "%Y-%m").date()
        month_error = "The selected month was invalid, so the current month is shown."

    if month_start.month == 12:
        month_end = date(month_start.year + 1, 1, 1)
    else:
        month_end = date(month_start.year, month_start.month + 1, 1)

    classroom = None
    students = []
    student_summaries = {}
    class_summary = {}

    if class_id:
        classroom = db.session.get(Classroom, class_id)
        if not classroom:
            flash("The selected class was not found.", "danger")
            return redirect(url_for("main.class_attendance_report"))

        students = (
            Student.query
            .filter_by(class_id=class_id, is_active=True)
            .order_by(Student.full_name.asc())
            .all()
        )

        records = (
            Attendance.query
            .filter(
                Attendance.class_id == class_id,
                Attendance.attendance_date >= month_start,
                Attendance.attendance_date < month_end
            )
            .order_by(Attendance.attendance_date.asc())
            .all()
        )

        rec_by_student = {}
        for r in records:
            rec_by_student.setdefault(r.student_id, []).append(r)

        for st in students:
            s_recs = rec_by_student.get(st.id, [])
            s_totals = {v: 0 for v in ATTENDANCE_STATUSES}
            for r in s_recs:
                if r.status in s_totals:
                    s_totals[r.status] += 1
            s_days = sum(s_totals.values())
            s_pct = (((s_totals["Present"] + s_totals["Late"]) / s_days) * 100) if s_days else None
            student_summaries[st.id] = {
                **s_totals,
                "total_days": s_days,
                "percentage": s_pct,
            }

        distinct_dates = {r.attendance_date for r in records}
        students_with_records = sum(
            1 for st in students if student_summaries[st.id]["total_days"] > 0
        )
        class_pct = (
            sum(student_summaries[st.id]["percentage"] for st in students if student_summaries[st.id]["percentage"] is not None) / students_with_records
            if students_with_records else None
        )
        class_summary = {
            "total_students": len(students),
            "total_sessions": len(distinct_dates),
            "students_with_records": students_with_records,
            "class_attendance_percentage": class_pct,
        }

    return render_template(
        "attendance_class_report.html",
        classrooms=classrooms,
        classroom=classroom,
        class_id=class_id,
        month=month,
        month_error=month_error,
        students=students,
        student_summaries=student_summaries,
        class_summary=class_summary,
    )


@main.route("/admin/attendance/reports/class/pdf", methods=["GET"])
@role_required("admin")
def admin_class_attendance_pdf():
    """Generate and stream a monthly class attendance PDF report."""
    class_id = request.args.get("class_id", type=int)
    month = request.args.get("month", date.today().strftime("%Y-%m"))

    if not class_id:
        flash("Select a class before downloading the PDF.", "danger")
        return redirect(url_for("main.class_attendance_report"))

    classroom = db.session.get(Classroom, class_id)
    if not classroom:
        abort(404)

    try:
        month_start = datetime.strptime(month, "%Y-%m").date()
    except (TypeError, ValueError):
        month = date.today().strftime("%Y-%m")
        month_start = datetime.strptime(month, "%Y-%m").date()

    if month_start.month == 12:
        month_end = date(month_start.year + 1, 1, 1)
    else:
        month_end = date(month_start.year, month_start.month + 1, 1)

    students = (
        Student.query
        .filter_by(class_id=class_id, is_active=True)
        .order_by(Student.full_name.asc())
        .all()
    )

    records = (
        Attendance.query
        .filter(
            Attendance.class_id == class_id,
            Attendance.attendance_date >= month_start,
            Attendance.attendance_date < month_end
        )
        .order_by(Attendance.attendance_date.asc())
        .all()
    )

    rec_by_student = {}
    for r in records:
        rec_by_student.setdefault(r.student_id, []).append(r)

    student_summaries = {}
    for st in students:
        s_recs = rec_by_student.get(st.id, [])
        s_totals = {v: 0 for v in ATTENDANCE_STATUSES}
        for r in s_recs:
            if r.status in s_totals:
                s_totals[r.status] += 1
        s_days = sum(s_totals.values())
        s_pct = (((s_totals["Present"] + s_totals["Late"]) / s_days) * 100) if s_days else None
        student_summaries[st.id] = {
            **s_totals,
            "total_days": s_days,
            "percentage": s_pct,
        }

    distinct_dates = {r.attendance_date for r in records}
    students_with_records = sum(
        1 for st in students if student_summaries[st.id]["total_days"] > 0
    )
    class_pct = (
        sum(student_summaries[st.id]["percentage"] for st in students if student_summaries[st.id]["percentage"] is not None) / students_with_records
        if students_with_records else None
    )
    class_summary = {
        "total_students": len(students),
        "total_sessions": len(distinct_dates),
        "students_with_records": students_with_records,
        "class_attendance_percentage": class_pct,
    }

    buffer = generate_class_attendance_pdf(
        classroom, month, students, student_summaries, class_summary
    )
    safe_class = classroom.name.replace(" ", "_")[:25]
    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="Class_Attendance_{}_{}.pdf".format(safe_class, month),
    )

# Fees
@main.route("/admin/fees", methods=["GET", "POST"])
@role_required("admin")
def admin_fees():
    students = Student.query.filter_by(is_active=True).order_by(
        Student.full_name.asc()
    ).all()

    if request.method == "POST":
        student_id = request.form.get("student_id", type=int)
        title = request.form.get("title", "").strip()
        billing_month_value = request.form.get("billing_month", "")
        amount = _parse_money(request.form.get("amount"))
        due_date = _parse_attendance_date(request.form.get("due_date"))
        notes = request.form.get("notes", "").strip() or None
        try:
            billing_month = date.fromisoformat(f"{billing_month_value}-01")
        except (TypeError, ValueError):
            billing_month = None

        student = db.session.get(Student, student_id) if student_id else None
        if not student or not student.is_active:
            flash("Please select an active student.", "danger")
        elif not title or not billing_month or not due_date or not amount:
            flash("Student, title, billing month, amount, and due date are required.", "danger")
        elif FeeRecord.query.filter_by(
            student_id=student.id, title=title, billing_month=billing_month
        ).first():
            flash("This fee already exists for the student and billing month.", "danger")
        else:
            db.session.add(FeeRecord(
                student_id=student.id,
                title=title,
                billing_month=billing_month,
                amount=amount,
                due_date=due_date,
                notes=notes,
                created_by_user_id=session["user_id"]
            ))
            try:
                db.session.commit()
                flash("Fee assigned successfully.", "success")
                return redirect(url_for("main.admin_fees"))
            except Exception:
                db.session.rollback()
                flash("Could not save fee. Please try again.", "danger")

    class_id = request.args.get("class_id", type=int)
    status = request.args.get("status", "all")
    fee_query = FeeRecord.query.join(Student)
    if class_id:
        fee_query = fee_query.filter(Student.class_id == class_id)
    fees = fee_query.order_by(FeeRecord.due_date.desc(), FeeRecord.id.desc()).all()
    if status in {"Paid", "Partial", "Unpaid", "Overdue"}:
        fees = [fee for fee in fees if fee.status == status]
    classrooms = Classroom.query.order_by(Classroom.name.asc()).all()

    all_fee_records = FeeRecord.query.all()
    overview = {
        "total_assessed": sum((Decimal(str(f.amount)) for f in all_fee_records), Decimal("0.00")),
        "total_paid": sum((Decimal(str(f.paid_amount)) for f in all_fee_records), Decimal("0.00")),
        "total_balance": sum((Decimal(str(f.balance)) for f in all_fee_records), Decimal("0.00")),
        "total_records": len(all_fee_records),
    }

    return render_template(
        "admin_fees.html",
        students=students,
        fees=fees,
        classrooms=classrooms,
        class_id=class_id,
        status=status,
        today=date.today().isoformat(),
        overview=overview,
    )


@main.route("/admin/fees/reports/class", methods=["GET"])
@role_required("admin")
def class_fee_report():
    """Admin class-wise fee collection report."""
    classrooms = Classroom.query.order_by(Classroom.name.asc()).all()
    class_id = request.args.get("class_id", type=int)
    status = request.args.get("status", "all")
    billing_month = request.args.get("billing_month", "").strip()

    classroom = None
    student_fee_data = []
    class_summary = {}

    if class_id:
        classroom = db.session.get(Classroom, class_id)
        if not classroom:
            flash("The selected class was not found.", "danger")
            return redirect(url_for("main.class_fee_report"))

        students = (
            Student.query
            .filter_by(class_id=class_id, is_active=True)
            .order_by(Student.full_name.asc())
            .all()
        )

        fee_query = FeeRecord.query.join(Student).filter(Student.class_id == class_id)
        if billing_month:
            try:
                bm_date = date.fromisoformat(f"{billing_month}-01")
                fee_query = fee_query.filter(FeeRecord.billing_month == bm_date)
            except (TypeError, ValueError):
                billing_month = ""

        all_class_fees = fee_query.all()
        fees_by_student = {}
        for f in all_class_fees:
            fees_by_student.setdefault(f.student_id, []).append(f)

        for st in students:
            s_fees = fees_by_student.get(st.id, [])
            s_assessed = sum((Decimal(str(f.amount)) for f in s_fees), Decimal("0.00"))
            s_paid = sum((Decimal(str(f.paid_amount)) for f in s_fees), Decimal("0.00"))
            s_balance = sum((Decimal(str(f.balance)) for f in s_fees), Decimal("0.00"))

            if not s_fees:
                st_status = "No Fees"
            elif s_balance <= Decimal("0.00"):
                st_status = "Paid"
            elif any(f.status == "Overdue" for f in s_fees):
                st_status = "Overdue"
            elif s_paid > Decimal("0.00"):
                st_status = "Partial"
            else:
                st_status = "Unpaid"

            if status != "all":
                if status == "Paid" and st_status != "Paid":
                    continue
                elif status == "Partial" and st_status != "Partial":
                    continue
                elif status == "Unpaid" and st_status != "Unpaid":
                    continue
                elif status == "Overdue" and st_status != "Overdue":
                    continue

            student_fee_data.append({
                "student": st,
                "invoices_count": len(s_fees),
                "total_assessed": s_assessed,
                "total_paid": s_paid,
                "total_balance": s_balance,
                "status": st_status,
                "fees": s_fees,
            })

        tot_assessed = sum((item["total_assessed"] for item in student_fee_data), Decimal("0.00"))
        tot_paid = sum((item["total_paid"] for item in student_fee_data), Decimal("0.00"))
        tot_balance = sum((item["total_balance"] for item in student_fee_data), Decimal("0.00"))
        tot_invoices = sum(item["invoices_count"] for item in student_fee_data)
        coll_rate = (float(tot_paid) / float(tot_assessed) * 100) if tot_assessed > Decimal("0.00") else 0.0

        class_summary = {
            "total_students": len(students),
            "matching_students": len(student_fee_data),
            "total_invoices": tot_invoices,
            "total_assessed": tot_assessed,
            "total_paid": tot_paid,
            "total_balance": tot_balance,
            "collection_rate": coll_rate,
        }

    return render_template(
        "fee_class_report.html",
        classrooms=classrooms,
        classroom=classroom,
        class_id=class_id,
        status=status,
        billing_month=billing_month,
        student_fee_data=student_fee_data,
        class_summary=class_summary,
    )


@main.route("/admin/fees/reports/class/pdf", methods=["GET"])
@role_required("admin")
def admin_class_fee_pdf():
    """Generate and stream a downloadable class fee summary PDF."""
    class_id = request.args.get("class_id", type=int)
    billing_month = request.args.get("billing_month", "").strip()

    if not class_id:
        flash("Select a class before downloading the PDF.", "danger")
        return redirect(url_for("main.class_fee_report"))

    classroom = db.session.get(Classroom, class_id)
    if not classroom:
        abort(404)

    students = (
        Student.query
        .filter_by(class_id=class_id, is_active=True)
        .order_by(Student.full_name.asc())
        .all()
    )

    fee_query = FeeRecord.query.join(Student).filter(Student.class_id == class_id)
    if billing_month:
        try:
            bm_date = date.fromisoformat(f"{billing_month}-01")
            fee_query = fee_query.filter(FeeRecord.billing_month == bm_date)
        except (TypeError, ValueError):
            pass

    all_class_fees = fee_query.all()
    fees_by_student = {}
    for f in all_class_fees:
        fees_by_student.setdefault(f.student_id, []).append(f)

    student_fee_data = []
    for st in students:
        s_fees = fees_by_student.get(st.id, [])
        s_assessed = sum((Decimal(str(f.amount)) for f in s_fees), Decimal("0.00"))
        s_paid = sum((Decimal(str(f.paid_amount)) for f in s_fees), Decimal("0.00"))
        s_balance = sum((Decimal(str(f.balance)) for f in s_fees), Decimal("0.00"))

        if not s_fees:
            st_status = "No Fees"
        elif s_balance <= Decimal("0.00"):
            st_status = "Paid"
        elif any(f.status == "Overdue" for f in s_fees):
            st_status = "Overdue"
        elif s_paid > Decimal("0.00"):
            st_status = "Partial"
        else:
            st_status = "Unpaid"

        student_fee_data.append({
            "student": st,
            "invoices_count": len(s_fees),
            "total_assessed": s_assessed,
            "total_paid": s_paid,
            "total_balance": s_balance,
            "status": st_status,
        })

    tot_assessed = sum((item["total_assessed"] for item in student_fee_data), Decimal("0.00"))
    tot_paid = sum((item["total_paid"] for item in student_fee_data), Decimal("0.00"))
    tot_balance = sum((item["total_balance"] for item in student_fee_data), Decimal("0.00"))
    tot_invoices = sum(item["invoices_count"] for item in student_fee_data)
    coll_rate = (float(tot_paid) / float(tot_assessed) * 100) if tot_assessed > Decimal("0.00") else 0.0

    class_summary = {
        "total_students": len(students),
        "total_invoices": tot_invoices,
        "total_assessed": tot_assessed,
        "total_paid": tot_paid,
        "total_balance": tot_balance,
        "collection_rate": coll_rate,
    }

    buffer = generate_class_fee_pdf(classroom, student_fee_data, class_summary)
    safe_class = classroom.name.replace(" ", "_")[:25]
    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="Class_Fee_Report_{}.pdf".format(safe_class),
    )


@main.route("/admin/fees/reports/student", methods=["GET"])
@role_required("admin")
def admin_student_fee_report():
    """Admin individual and searchable student fee report."""
    classrooms = Classroom.query.order_by(Classroom.name.asc()).all()
    class_id = request.args.get("class_id", type=int)
    student_id = request.args.get("student_id", type=int)
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "all")

    classroom = None
    students_in_class = []
    student = None
    fee_records = []
    payments = []
    student_summary = {}
    search_results = []

    if class_id:
        classroom = db.session.get(Classroom, class_id)
        if not classroom:
            flash("The selected class was not found.", "danger")
            return redirect(url_for("main.admin_student_fee_report"))

        students_in_class = (
            Student.query
            .filter_by(class_id=class_id, is_active=True)
            .order_by(Student.full_name.asc())
            .all()
        )

    if student_id:
        if class_id:
            # Backend cross-class security check
            student = Student.query.filter_by(id=student_id, class_id=class_id).first()
            if not student:
                flash("The selected student does not belong to this class.", "danger")
                return redirect(url_for("main.admin_student_fee_report", class_id=class_id))
        else:
            student = db.session.get(Student, student_id)
            if student and student.class_id:
                classroom = db.session.get(Classroom, student.class_id)
                class_id = student.class_id

        if student:
            all_student_fees = FeeRecord.query.filter_by(student_id=student.id).order_by(
                FeeRecord.due_date.desc(), FeeRecord.id.desc()
            ).all()

            if status in {"Paid", "Partial", "Unpaid", "Overdue"}:
                fee_records = [f for f in all_student_fees if f.status == status]
            else:
                fee_records = all_student_fees

            payments = (
                FeePayment.query
                .join(FeeRecord)
                .filter(FeeRecord.student_id == student.id)
                .order_by(FeePayment.payment_date.desc(), FeePayment.id.desc())
                .all()
            )

            tot_assessed = sum((Decimal(str(f.amount)) for f in all_student_fees), Decimal("0.00"))
            tot_paid = sum((Decimal(str(f.paid_amount)) for f in all_student_fees), Decimal("0.00"))
            tot_balance = sum((Decimal(str(f.balance)) for f in all_student_fees), Decimal("0.00"))

            if not all_student_fees:
                st_status = "No Fees"
            elif tot_balance <= Decimal("0.00"):
                st_status = "Paid"
            elif any(f.status == "Overdue" for f in all_student_fees):
                st_status = "Overdue"
            elif tot_paid > Decimal("0.00"):
                st_status = "Partial"
            else:
                st_status = "Unpaid"

            student_summary = {
                "total_assessed": tot_assessed,
                "total_paid": tot_paid,
                "total_balance": tot_balance,
                "status": st_status,
                "invoices_count": len(all_student_fees),
                "payments_count": len(payments),
            }

    elif search:
        # Multi-student search results table
        query = Student.query.filter(
            db.or_(
                Student.full_name.ilike(f"%{search}%"),
                Student.roll_number.ilike(f"%{search}%")
            )
        )
        if class_id:
            query = query.filter(Student.class_id == class_id)

        matched_students = query.order_by(Student.full_name.asc()).all()
        for ms in matched_students:
            m_fees = FeeRecord.query.filter_by(student_id=ms.id).all()
            m_assessed = sum((Decimal(str(f.amount)) for f in m_fees), Decimal("0.00"))
            m_paid = sum((Decimal(str(f.paid_amount)) for f in m_fees), Decimal("0.00"))
            m_balance = sum((Decimal(str(f.balance)) for f in m_fees), Decimal("0.00"))

            if not m_fees:
                m_status = "No Fees"
            elif m_balance <= Decimal("0.00"):
                m_status = "Paid"
            elif any(f.status == "Overdue" for f in m_fees):
                m_status = "Overdue"
            elif m_paid > Decimal("0.00"):
                m_status = "Partial"
            else:
                m_status = "Unpaid"

            if status != "all":
                if status == "Paid" and m_status != "Paid":
                    continue
                elif status == "Partial" and m_status != "Partial":
                    continue
                elif status == "Unpaid" and m_status != "Unpaid":
                    continue
                elif status == "Overdue" and m_status != "Overdue":
                    continue

            search_results.append({
                "student": ms,
                "classroom": ms.classroom,
                "invoices_count": len(m_fees),
                "total_assessed": m_assessed,
                "total_paid": m_paid,
                "total_balance": m_balance,
                "status": m_status,
            })

    return render_template(
        "fee_student_report.html",
        classrooms=classrooms,
        classroom=classroom,
        class_id=class_id,
        students_in_class=students_in_class,
        student=student,
        student_id=student_id,
        fee_records=fee_records,
        payments=payments,
        student_summary=student_summary,
        search=search,
        search_results=search_results,
        status=status,
    )


@main.route("/admin/fees/reports/student/pdf", methods=["GET"])
@role_required("admin")
def admin_student_fee_pdf():
    """Generate and stream a student fee statement PDF."""
    class_id = request.args.get("class_id", type=int)
    student_id = request.args.get("student_id", type=int)

    if not student_id:
        flash("Select a student before downloading the fee statement PDF.", "danger")
        return redirect(url_for("main.admin_student_fee_report", class_id=class_id))

    if class_id:
        student = Student.query.filter_by(id=student_id, class_id=class_id).first()
        if not student:
            abort(403)
        classroom = db.session.get(Classroom, class_id)
    else:
        student = db.session.get(Student, student_id)
        if not student:
            abort(404)
        classroom = db.session.get(Classroom, student.class_id) if student.class_id else None

    fee_records = FeeRecord.query.filter_by(student_id=student.id).order_by(
        FeeRecord.due_date.asc(), FeeRecord.id.asc()
    ).all()

    payments = (
        FeePayment.query
        .join(FeeRecord)
        .filter(FeeRecord.student_id == student.id)
        .order_by(FeePayment.payment_date.asc(), FeePayment.id.asc())
        .all()
    )

    tot_assessed = sum((Decimal(str(f.amount)) for f in fee_records), Decimal("0.00"))
    tot_paid = sum((Decimal(str(f.paid_amount)) for f in fee_records), Decimal("0.00"))
    tot_balance = sum((Decimal(str(f.balance)) for f in fee_records), Decimal("0.00"))

    if not fee_records:
        st_status = "No Fees"
    elif tot_balance <= Decimal("0.00"):
        st_status = "Paid"
    elif any(f.status == "Overdue" for f in fee_records):
        st_status = "Overdue"
    elif tot_paid > Decimal("0.00"):
        st_status = "Partial"
    else:
        st_status = "Unpaid"

    summary = {
        "total_assessed": tot_assessed,
        "total_paid": tot_paid,
        "total_balance": tot_balance,
        "status": st_status,
    }

    buffer = generate_student_fee_pdf(student, classroom, fee_records, payments, summary)
    safe_name = student.full_name.replace(" ", "_")[:35]
    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="Fee_Statement_{}.pdf".format(safe_name),
    )


@main.route("/admin/fees/<int:fee_id>/payment", methods=["POST"])
@role_required("admin")
def record_fee_payment(fee_id):
    fee = FeeRecord.query.get_or_404(fee_id)
    amount = _parse_money(request.form.get("amount"))
    payment_date = _parse_attendance_date(request.form.get("payment_date"))
    payment_method = request.form.get("payment_method", "Cash").strip()
    receipt_reference = request.form.get("receipt_reference", "").strip() or None
    notes = request.form.get("notes", "").strip() or None

    if not amount or not payment_date or payment_method not in {"Cash", "Bank Transfer", "Card", "Online"}:
        flash("Valid amount, date, and payment method are required.", "danger")
    elif amount > fee.balance:
        flash(f"Payment cannot exceed the remaining balance ({fee.balance}).", "danger")
    elif receipt_reference and FeePayment.query.filter_by(receipt_reference=receipt_reference).first():
        flash("This receipt reference already exists.", "danger")
    else:
        db.session.add(FeePayment(
            fee_record_id=fee.id,
            amount=amount,
            payment_date=payment_date,
            payment_method=payment_method,
            receipt_reference=receipt_reference,
            notes=notes,
            received_by_user_id=session["user_id"]
        ))
        try:
            db.session.commit()
            flash("Payment recorded successfully.", "success")
        except Exception:
            db.session.rollback()
            flash("Could not record payment. Please try again.", "danger")
    return redirect(url_for("main.admin_fees"))


@main.route("/student/fees")
@role_required("student")
def student_fees():
    student = _current_student()
    fees = _fee_records_for_student(student.id) if student else []
    return render_template("student_fees.html", student=student, fees=fees)


@main.route("/student/attendance")
@role_required("student")
def student_attendance():
    student = _current_student()
    month = request.args.get("month", date.today().strftime("%Y-%m"))
    month_error = None

    try:
        month_start = datetime.strptime(month, "%Y-%m").date()
    except (TypeError, ValueError):
        month = date.today().strftime("%Y-%m")
        month_start = datetime.strptime(month, "%Y-%m").date()
        month_error = "The selected month was invalid, so the current month is shown."

    if month_start.month == 12:
        month_end = date(month_start.year + 1, 1, 1)
    else:
        month_end = date(month_start.year, month_start.month + 1, 1)

    records = []
    totals = {value: 0 for value in ATTENDANCE_STATUSES}
    if student:
        records = Attendance.query.filter(
            Attendance.student_id == student.id,
            Attendance.attendance_date >= month_start,
            Attendance.attendance_date < month_end
        ).order_by(
            Attendance.attendance_date.desc(),
            Attendance.id.desc()
        ).all()
        for record in records:
            totals[record.status] += 1

    total_classes = sum(totals.values())
    attendance_percentage = (
        ((totals["Present"] + totals["Late"]) / total_classes) * 100
        if total_classes else 0
    )

    return render_template(
        "student_attendance.html",
        student=student,
        month=month,
        month_error=month_error,
        records=records,
        totals=totals,
        total_classes=total_classes,
        attendance_percentage=attendance_percentage
    )


# Exams and results
@main.route("/admin/exams", methods=["GET", "POST"])
@role_required("admin")
def admin_exams():
    classrooms = Classroom.query.filter_by(is_active=True).order_by(
        Classroom.name.asc()
    ).all()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        class_id = request.form.get("class_id", type=int)
        exam_date = _parse_attendance_date(request.form.get("exam_date"))
        total_marks = request.form.get("total_marks", type=int)

        if not name or not class_id or not exam_date or not total_marks:
            flash("Exam name, class, date, and total marks are required.", "danger")
        elif total_marks <= 0:
            flash("Total marks must be greater than zero.", "danger")
        elif not db.session.get(Classroom, class_id):
            flash("The selected class was not found.", "danger")
        elif Exam.query.filter_by(class_id=class_id, name=name).first():
            flash("This exam already exists for the selected class.", "danger")
        else:
            db.session.add(Exam(
                name=name,
                class_id=class_id,
                exam_date=exam_date,
                total_marks=total_marks
            ))
            try:
                db.session.commit()
                flash("Exam created successfully.", "success")
                return redirect(url_for("main.admin_exams"))
            except Exception:
                db.session.rollback()
                flash("Could not create exam. Please try again.", "danger")

    exams = Exam.query.join(Classroom).order_by(
        Exam.exam_date.desc(), Exam.id.desc()
    ).all()
    return render_template(
        "admin_exams.html",
        classrooms=classrooms,
        exams=exams
    )


@main.route("/admin/exams/<int:exam_id>/publish", methods=["POST"])
@role_required("admin")
def publish_exam(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    exam.is_published = not exam.is_published
    db.session.commit()
    flash("Exam publication status updated.", "success")
    return redirect(url_for("main.admin_exams"))


@main.route("/admin/exams/<int:exam_id>/results", methods=["GET"])
@role_required("admin")
def admin_exam_results(exam_id):
    """Admin class results view — shows every student's marks for one exam."""
    exam = Exam.query.get_or_404(exam_id)

    # Subjects assigned to this class
    assignments = (
        ClassSubjectAssignment.query
        .filter_by(class_id=exam.class_id)
        .join(Subject)
        .order_by(Subject.name.asc())
        .all()
    )
    subjects = [a.subject for a in assignments]

    # Active students enrolled in the class
    students = (
        Student.query
        .filter_by(class_id=exam.class_id, is_active=True)
        .order_by(Student.full_name.asc())
        .all()
    )

    # All ExamResult rows for this exam
    all_results = ExamResult.query.filter_by(exam_id=exam.id).all()

    # Build {student_id: {subject_id: ExamResult}}
    result_map = {}
    for r in all_results:
        result_map.setdefault(r.student_id, {})[r.subject_id] = r

    # Build per-student display data
    student_rows = []
    for student in students:
        s_res = result_map.get(student.id, {})
        cells = []
        total_obtained = 0.0
        subjects_recorded = 0
        for subject in subjects:
            result = s_res.get(subject.id)
            cells.append(result)
            if result is not None:
                total_obtained += float(result.marks)
                subjects_recorded += 1
        has_results = subjects_recorded > 0
        max_marks = subjects_recorded * exam.total_marks if has_results else None
        percentage = (total_obtained / max_marks * 100) if max_marks else None
        student_rows.append({
            "student": student,
            "cells": cells,
            "total_obtained": total_obtained if has_results else None,
            "max_marks": max_marks,
            "percentage": percentage,
            "has_results": has_results,
        })

    students_with_results = sum(1 for row in student_rows if row["has_results"])
    students_without_results = len(student_rows) - students_with_results

    # Class average: mean percentage across students who have at least 1 result
    class_average = (
        sum(row["percentage"] for row in student_rows if row["has_results"])
        / students_with_results
        if students_with_results > 0 else None
    )

    return render_template(
        "admin_class_results.html",
        exam=exam,
        subjects=subjects,
        student_rows=student_rows,
        total_students=len(students),
        students_with_results=students_with_results,
        students_without_results=students_without_results,
        class_average=class_average,
    )


@main.route("/admin/reports/student-results", methods=["GET"])
@role_required("admin")
def admin_student_results_report():
    """Admin individual student results: select class then student."""
    classrooms = (
        Classroom.query
        .filter_by(is_active=True)
        .order_by(Classroom.name.asc())
        .all()
    )
    class_id   = request.args.get("class_id",  type=int)
    student_id = request.args.get("student_id", type=int)

    classroom         = None
    student           = None
    students_in_class = []
    exams_data        = []

    if class_id:
        classroom = db.session.get(Classroom, class_id)
        if not classroom:
            flash("The selected class was not found.", "danger")
            return redirect(url_for("main.admin_student_results_report"))
        students_in_class = (
            Student.query
            .filter_by(class_id=class_id, is_active=True)
            .order_by(Student.full_name.asc())
            .all()
        )
        if student_id:
            # Backend security: student must belong to the selected class
            student = Student.query.filter_by(id=student_id, class_id=class_id).first()
            if not student:
                flash("The selected student does not belong to this class.", "danger")
                return redirect(
                    url_for("main.admin_student_results_report", class_id=class_id)
                )
            exams = (
                Exam.query
                .filter_by(class_id=class_id)
                .order_by(Exam.exam_date.desc(), Exam.id.desc())
                .all()
            )
            for exam in exams:
                assignments = (
                    ClassSubjectAssignment.query
                    .filter_by(class_id=class_id)
                    .join(Subject)
                    .order_by(Subject.name.asc())
                    .all()
                )
                subjects = [a.subject for a in assignments]
                results = ExamResult.query.filter_by(
                    exam_id=exam.id, student_id=student.id
                ).all()
                res_map = {r.subject_id: r for r in results}
                subject_rows = []
                total_obtained = 0.0
                max_marks_total = 0
                for subject in subjects:
                    r = res_map.get(subject.id)
                    subject_rows.append({"subject": subject, "result": r})
                    if r is not None:
                        total_obtained  += float(r.marks)
                        max_marks_total += exam.total_marks
                has_any = len(results) > 0
                exams_data.append({
                    "exam":           exam,
                    "subject_rows":   subject_rows,
                    "total_obtained": total_obtained if has_any else None,
                    "max_marks":      max_marks_total if has_any else None,
                    "percentage":     (
                        total_obtained / max_marks_total * 100
                        if max_marks_total > 0 else None
                    ),
                    "has_results":    has_any,
                })

    return render_template(
        "admin_student_results_report.html",
        classrooms=classrooms,
        classroom=classroom,
        students_in_class=students_in_class,
        student=student,
        class_id=class_id,
        student_id=student_id,
        exams_data=exams_data,
    )


@main.route("/admin/exams/<int:exam_id>/results/pdf", methods=["GET"])
@role_required("admin")
def admin_class_results_pdf(exam_id):
    """Generate and stream a class results PDF for one exam."""
    exam = Exam.query.get_or_404(exam_id)
    assignments = (
        ClassSubjectAssignment.query
        .filter_by(class_id=exam.class_id)
        .join(Subject)
        .order_by(Subject.name.asc())
        .all()
    )
    subjects = [a.subject for a in assignments]
    students = (
        Student.query
        .filter_by(class_id=exam.class_id, is_active=True)
        .order_by(Student.full_name.asc())
        .all()
    )
    all_results = ExamResult.query.filter_by(exam_id=exam.id).all()
    result_map = {}
    for r in all_results:
        result_map.setdefault(r.student_id, {})[r.subject_id] = r

    # Compute summary stats for PDF banner
    rows_meta = []
    for student in students:
        s_res = result_map.get(student.id, {})
        subs_rec = sum(1 for subject in subjects if s_res.get(subject.id) is not None)
        if subs_rec > 0:
            total_obt = sum(
                float(s_res[sub.id].marks)
                for sub in subjects if s_res.get(sub.id) is not None
            )
            max_m = subs_rec * exam.total_marks
            pct   = total_obt / max_m * 100
        else:
            pct = None
        rows_meta.append({"has_results": subs_rec > 0, "percentage": pct})

    students_with_results = sum(1 for m in rows_meta if m["has_results"])
    class_average = (
        sum(m["percentage"] for m in rows_meta if m["has_results"]) / students_with_results
        if students_with_results > 0 else None
    )
    summary = {
        "total_students":        len(students),
        "students_with_results": students_with_results,
        "class_average":         class_average,
    }

    buffer = generate_class_results_pdf(exam, students, subjects, result_map, summary)
    safe_exam  = exam.name.replace(" ", "_")[:30]
    safe_class = exam.classroom.name.replace(" ", "_")[:20]
    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="Class_Results_{}_{}.pdf".format(safe_class, safe_exam),
    )


@main.route("/admin/reports/student-results/pdf", methods=["GET"])
@role_required("admin")
def admin_student_results_pdf():
    """Generate and stream an individual student results PDF."""
    class_id   = request.args.get("class_id",  type=int)
    student_id = request.args.get("student_id", type=int)
    if not class_id or not student_id:
        flash("Select a class and student before downloading the PDF.", "danger")
        return redirect(url_for("main.admin_student_results_report"))
    classroom = db.session.get(Classroom, class_id)
    if not classroom:
        abort(404)
    # Backend security: student must belong to the class
    student = Student.query.filter_by(id=student_id, class_id=class_id).first()
    if not student:
        abort(403)
    exams = (
        Exam.query
        .filter_by(class_id=class_id)
        .order_by(Exam.exam_date.desc(), Exam.id.desc())
        .all()
    )
    exams_data = []
    for exam in exams:
        assignments = (
            ClassSubjectAssignment.query
            .filter_by(class_id=class_id)
            .join(Subject)
            .order_by(Subject.name.asc())
            .all()
        )
        subjects = [a.subject for a in assignments]
        results  = ExamResult.query.filter_by(
            exam_id=exam.id, student_id=student.id
        ).all()
        res_map = {r.subject_id: r for r in results}
        subject_rows = []
        total_obtained = 0.0
        max_marks_total = 0
        for subject in subjects:
            r = res_map.get(subject.id)
            subject_rows.append({"subject": subject, "result": r})
            if r is not None:
                total_obtained  += float(r.marks)
                max_marks_total += exam.total_marks
        has_any = len(results) > 0
        exams_data.append({
            "exam":           exam,
            "subject_rows":   subject_rows,
            "total_obtained": total_obtained if has_any else None,
            "max_marks":      max_marks_total if has_any else None,
            "percentage":     (
                total_obtained / max_marks_total * 100
                if max_marks_total > 0 else None
            ),
            "has_results":    has_any,
        })
    buffer    = generate_student_results_pdf(student, exams_data)
    safe_name = student.full_name.replace(" ", "_")[:40]
    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="Student_Results_{}.pdf".format(safe_name),
    )


@main.route("/api/classes/<int:class_id>/students", methods=["GET"])
@role_required("admin")
def api_class_students(class_id):
    """JSON: active students for a class — used by the dynamic student selector."""
    classroom = db.session.get(Classroom, class_id)
    if not classroom:
        return jsonify({"error": "Class not found"}), 404
    students = (
        Student.query
        .filter_by(class_id=class_id, is_active=True)
        .order_by(Student.full_name.asc())
        .all()
    )
    return jsonify([
        {"id": s.id, "full_name": s.full_name, "roll_number": s.roll_number}
        for s in students
    ])



@main.route("/teacher/results", methods=["GET"])
@role_required("teacher")
def teacher_results():
    teacher = _current_teacher()
    if not teacher:
        abort(403)
    classrooms = _teacher_classes(teacher)
    exams = Exam.query.join(
        ClassSubjectAssignment,
        ClassSubjectAssignment.class_id == Exam.class_id
    ).filter(
        ClassSubjectAssignment.teacher_id == teacher.id
    ).distinct().order_by(Exam.exam_date.desc()).all()
    exam_id = request.args.get("exam_id", type=int)
    class_id = request.args.get("class_id", type=int)
    subject_id = request.args.get("subject_id", type=int)
    exam = db.session.get(Exam, exam_id) if exam_id else None
    assignments = []
    assignment = None
    students = []
    existing_results = {}
    selection_error = None

    if exam:
        if class_id is None:
            class_id = exam.class_id
        if class_id != exam.class_id:
            abort(403)
        _authorized_teacher_class(class_id)
        assignments = ClassSubjectAssignment.query.filter_by(
            class_id=class_id,
            teacher_id=teacher.id
        ).join(Subject).order_by(Subject.name.asc()).all()
        if subject_id:
            assignment = _teacher_assignment_for_exam(exam, subject_id)
            students = Student.query.filter_by(
                class_id=class_id,
                is_active=True
            ).order_by(Student.full_name.asc()).all()
            existing_results = {
                result.student_id: result
                for result in ExamResult.query.filter_by(
                    exam_id=exam.id,
                    subject_id=assignment.subject_id
                ).all()
            }
        elif not assignments:
            selection_error = "No subjects are assigned to you for this class."
    elif exam_id:
        abort(404)

    return render_template(
        "exam_results_form.html",
        exam=exam,
        exams=exams,
        classrooms=classrooms,
        class_id=class_id,
        assignments=assignments,
        assignment=assignment,
        students=students,
        existing_results=existing_results,
        selection_error=selection_error,
        role="teacher"
    )


@main.route("/teacher/results/save", methods=["POST"])
@role_required("teacher")
def save_teacher_results():
    exam = Exam.query.get_or_404(request.form.get("exam_id", type=int))
    class_id = request.form.get("class_id", type=int)
    if class_id != exam.class_id:
        abort(403)
    classroom = _authorized_teacher_class(class_id)
    subject_id = request.form.get("subject_id", type=int)
    assignment = _teacher_assignment_for_exam(exam, subject_id)
    student_ids = request.form.getlist("student_id", type=int)
    students = Student.query.filter(
        Student.id.in_(student_ids),
        Student.class_id == classroom.id,
        Student.is_active.is_(True)
    ).all() if student_ids else []
    if len(students) != len(set(student_ids)):
        abort(403)
    now = datetime.now(timezone.utc)
    for student in students:
        raw_marks = request.form.get(f"marks_{student.id}", "").strip()
        if not raw_marks:
            continue
        try:
            marks = float(raw_marks)
        except ValueError:
            flash("Marks must be valid numbers.", "danger")
            return redirect(url_for(
                "main.teacher_results",
                exam_id=exam.id,
                class_id=classroom.id,
                subject_id=subject_id
            ))
        if marks < 0 or marks > exam.total_marks:
            flash(f"Marks must be between 0 and {exam.total_marks}.", "danger")
            return redirect(url_for(
                "main.teacher_results",
                exam_id=exam.id,
                class_id=classroom.id,
                subject_id=subject_id
            ))
        result = ExamResult.query.filter_by(
            exam_id=exam.id, student_id=student.id, subject_id=subject_id
        ).first()
        if not result:
            result = ExamResult(
                exam_id=exam.id,
                student_id=student.id,
                subject_id=subject_id,
                recorded_by_user_id=session["user_id"]
            )
            db.session.add(result)
        result.marks = marks
        result.grade = _grade_for_marks(marks, exam.total_marks)
        result.remarks = request.form.get(f"remarks_{student.id}", "").strip() or None
        result.updated_at = now
    db.session.commit()
    flash("Results saved successfully.", "success")
    return redirect(url_for(
        "main.teacher_results",
        exam_id=exam.id,
        class_id=classroom.id,
        subject_id=subject_id
    ))


@main.route("/student/results")
@role_required("student")
def student_results():
    student = _current_student()
    results = ExamResult.query.join(Exam).filter(
        Exam.is_published.is_(True),
        ExamResult.student_id == student.id
    ).order_by(Exam.exam_date.desc(), ExamResult.subject_id.asc()).all() if student else []
    return render_template("student_results.html", student=student, results=results)


@main.route("/student/notices")
@role_required("student")
def student_notices():
    return render_template(
        "portal_notices.html",
        notices=_published_notices_for_role("student"),
        portal="Student",
        detail_endpoint="main.student_notice_detail"
    )


@main.route("/student/notices/<int:notice_id>")
@role_required("student")
def student_notice_detail(notice_id):
    notice = Notice.query.filter(
        Notice.id == notice_id,
        Notice.audience.in_(("all", "student")),
        Notice.is_published.is_(True),
        Notice.notice_date <= date.today(),
        db.or_(Notice.expires_on.is_(None), Notice.expires_on >= date.today())
    ).first_or_404()
    return render_template(
        "notice_detail.html",
        notice=notice,
        portal="Student",
        back_endpoint="main.student_notices"
    )


@main.route("/teacher/notices")
@role_required("teacher")
def teacher_notices():
    return render_template(
        "portal_notices.html",
        notices=_published_notices_for_role("teacher"),
        portal="Teacher",
        detail_endpoint="main.teacher_notice_detail"
    )


@main.route("/teacher/notices/<int:notice_id>")
@role_required("teacher")
def teacher_notice_detail(notice_id):
    notice = Notice.query.filter(
        Notice.id == notice_id,
        Notice.audience.in_(("all", "teacher")),
        Notice.is_published.is_(True),
        Notice.notice_date <= date.today(),
        db.or_(Notice.expires_on.is_(None), Notice.expires_on >= date.today())
    ).first_or_404()
    return render_template(
        "notice_detail.html",
        notice=notice,
        portal="Teacher",
        back_endpoint="main.teacher_notices"
    )


@main.route("/admin/notices/<int:notice_id>")
@role_required("admin")
def admin_notice_detail(notice_id):
    notice = Notice.query.get_or_404(notice_id)
    return render_template(
        "notice_detail.html",
        notice=notice,
        portal="Admin",
        back_endpoint="main.admin_notices",
        admin_view=True
    )


# 1. READ: List and search teachers

@main.route("/admin/teachers")
@role_required("admin")
def admin_teachers():
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "all")

    # Overall statistics — search/filter se independent
    total_teachers = Teacher.query.count()
    active_teachers = Teacher.query.filter_by(is_active=True).count()
    inactive_teachers = Teacher.query.filter_by(is_active=False).count()

    query = Teacher.query

    if search:
        query = query.filter(
            or_(
                Teacher.full_name.ilike(f"%{search}%"),
                Teacher.email.ilike(f"%{search}%"),
                Teacher.phone.ilike(f"%{search}%")
            )
        )

    if status == "active":
        query = query.filter_by(is_active=True)
    elif status == "inactive":
        query = query.filter_by(is_active=False)

    teachers = query.order_by(Teacher.id.desc()).all()

    return render_template(
        "admin_teachers.html",
        teachers=teachers,
        search=search,
        status=status,
        total_teachers=total_teachers,
        active_teachers=active_teachers,
        inactive_teachers=inactive_teachers
    )

# 2. CREATE: Add teacher
@main.route("/admin/teachers/new", methods=["GET", "POST"])
@role_required("admin")
def add_teacher():
    users = User.query.filter_by(
        role="teacher",
        is_active=True
    ).order_by(User.username.asc()).all()

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        email = request.form.get("email", "").strip().lower() or None
        phone = request.form.get("phone", "").strip() or None
        gender = request.form.get("gender", "").strip() or None
        qualification = (
            request.form.get("qualification", "").strip() or None
        )
        is_active = request.form.get("is_active") == "on"

        if not full_name or not username or not password or not confirm_password:
            flash("Teacher name, username, password, and confirmation are required.", "danger")
            return render_template("teacher_form.html", teacher=None, users=users)

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("teacher_form.html", teacher=None, users=users)

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "danger")
            return render_template("teacher_form.html", teacher=None, users=users)

        if User.query.filter_by(username=username).first():
            flash("This username is already in use.", "danger")
            return render_template("teacher_form.html", teacher=None, users=users)

        if email and Teacher.query.filter_by(email=email).first():
            flash("This email is already registered.", "danger")
            return render_template("teacher_form.html", teacher=None, users=users)

        try:
            user = User(
                username=username,
                password_hash=generate_password_hash(password),
                role="teacher",
                is_active=True
            )
            db.session.add(user)
            db.session.flush()
            teacher = Teacher(
                user_id=user.id,
                full_name=full_name,
                email=email,
                phone=phone,
                gender=gender,
                qualification=qualification,
                is_active=is_active
            )
            db.session.add(teacher)
            db.session.commit()
            flash("Teacher added successfully.", "success")
            return redirect(url_for("main.admin_teachers"))

        except Exception:
            db.session.rollback()
            flash("Could not save teacher. Please try again.", "danger")

    return render_template("teacher_form.html", teacher=None, users=users)


# 3. READ: View one teacher
@main.route("/admin/teachers/<int:teacher_id>")
@role_required("admin")
def teacher_details(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)

    return render_template(
        "teacher_details.html",
        teacher=teacher
    )


# 4. UPDATE: Edit teacher
@main.route("/admin/teachers/<int:teacher_id>/edit",
            methods=["GET", "POST"])
@role_required("admin")
def edit_teacher(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    users = User.query.filter_by(
        role="teacher",
        is_active=True
    ).order_by(User.username.asc()).all()

    if request.method == "POST":
        user_id = request.form.get("user_id", type=int)
        new_username = request.form.get("new_username", "").strip()
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower() or None
        phone = request.form.get("phone", "").strip() or None
        gender = request.form.get("gender", "").strip() or None
        qualification = (
            request.form.get("qualification", "").strip() or None
        )
        is_active = request.form.get("is_active") == "on"

        linked_user = db.session.get(User, user_id) if user_id else None
        linked_teacher = Teacher.query.filter(
            Teacher.user_id == user_id,
            Teacher.id != teacher.id
        ).first() if user_id else None

        if user_id and (
            not linked_user or linked_user.role != "teacher" or linked_teacher
        ):
            flash("Selected teacher account is invalid or already linked.", "danger")
            return render_template("teacher_form.html", teacher=teacher, users=users)

        if new_username and teacher.user_id:
            flash("A linked teacher account can only have its password reset here.", "danger")
            return render_template("teacher_form.html", teacher=teacher, users=users)

        if new_username and User.query.filter_by(username=new_username).first():
            flash("This username is already in use.", "danger")
            return render_template("teacher_form.html", teacher=teacher, users=users)

        if new_username and (not new_password or new_password != confirm_password):
            flash("New username requires matching password and confirmation.", "danger")
            return render_template("teacher_form.html", teacher=teacher, users=users)

        if new_password and new_password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("teacher_form.html", teacher=teacher, users=users)

        if new_password and len(new_password) < 8:
            flash("Password must be at least 8 characters.", "danger")
            return render_template("teacher_form.html", teacher=teacher, users=users)

        if not full_name:
            flash("Teacher name is required.", "danger")
            return render_template("teacher_form.html", teacher=teacher, users=users)

        if email and Teacher.query.filter(
            Teacher.email == email,
            Teacher.id != teacher.id
        ).first():
            flash("This email belongs to another teacher.", "danger")
            return render_template("teacher_form.html", teacher=teacher, users=users)

        if new_username:
            new_user = User(
                username=new_username,
                password_hash=generate_password_hash(new_password),
                role="teacher",
                is_active=True
            )
            db.session.add(new_user)
            db.session.flush()
            teacher.user_id = new_user.id
        else:
            teacher.user_id = user_id
            if new_password and teacher.user:
                teacher.user.password_hash = generate_password_hash(new_password)
        teacher.full_name = full_name
        teacher.email = email
        teacher.phone = phone
        teacher.gender = gender
        teacher.qualification = qualification
        teacher.is_active = is_active

        try:
            db.session.commit()
            flash("Teacher updated successfully.", "success")
            return redirect(
                url_for("main.teacher_details", teacher_id=teacher.id)
            )

        except Exception:
            db.session.rollback()
            flash("Could not update teacher. Please try again.", "danger")

    return render_template("teacher_form.html", teacher=teacher, users=users)


# 5. DELETE: Permanently delete teacher
@main.route("/admin/teachers/<int:teacher_id>/delete",
            methods=["POST"])
@role_required("admin")
def delete_teacher(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)

    try:
        db.session.delete(teacher)
        db.session.commit()
        flash("Teacher deleted successfully.", "success")

    except Exception:
        db.session.rollback()
        flash(
            "Teacher could not be deleted. Check related records.",
            "danger"
        )

    return redirect(url_for("main.admin_teachers"))

@main.route("/admin/dashboard")
@role_required("admin")
def admin_dashboard():
    fee_records = FeeRecord.query.all()
    total_balance = sum((fee.balance for fee in fee_records), Decimal("0"))
    return render_template(
        "admin_dashboard.html",
        total_students=Student.query.count(),
        total_teachers=Teacher.query.count(),
        total_classes=Classroom.query.count(),
        fee_balance=total_balance,
        notice_count=Notice.query.filter_by(is_published=True).count()
    )


@main.route("/admin/notices", methods=["GET", "POST"])
@role_required("admin")
def admin_notices():
    notice = None
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        audience = request.form.get("audience", "")
        notice_date = _parse_notice_date(request.form.get("notice_date"))
        expires_on = _parse_notice_date(request.form.get("expires_on"))
        is_published = request.form.get("is_published") == "on"

        if not title or not body or audience not in NOTICE_AUDIENCES:
            flash("Title, message, and a valid audience are required.", "danger")
        elif not notice_date:
            flash("Please provide a valid notice date.", "danger")
        elif expires_on and expires_on < notice_date:
            flash("Expiry date cannot be before the notice date.", "danger")
        else:
            db.session.add(Notice(
                title=title,
                body=body,
                audience=audience,
                notice_date=notice_date,
                expires_on=expires_on,
                is_published=is_published,
                created_by_user_id=session["user_id"]
            ))
            try:
                db.session.commit()
                flash("Notice created successfully.", "success")
                return redirect(url_for("main.admin_notices"))
            except Exception:
                db.session.rollback()
                flash("Could not create notice. Please try again.", "danger")

    return render_template(
        "admin_notices.html",
        notices=Notice.query.order_by(
            Notice.notice_date.desc(), Notice.id.desc()
        ).all(),
        notice=notice,
        audiences=NOTICE_AUDIENCES,
        today=date.today().isoformat()
    )


@main.route("/admin/notices/<int:notice_id>/edit", methods=["GET", "POST"])
@role_required("admin")
def edit_notice(notice_id):
    notice = Notice.query.get_or_404(notice_id)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        audience = request.form.get("audience", "")
        notice_date = _parse_notice_date(request.form.get("notice_date"))
        expires_on = _parse_notice_date(request.form.get("expires_on"))

        if not title or not body or audience not in NOTICE_AUDIENCES or not notice_date:
            flash("Title, message, audience, and a valid notice date are required.", "danger")
        elif expires_on and expires_on < notice_date:
            flash("Expiry date cannot be before the notice date.", "danger")
        else:
            notice.title = title
            notice.body = body
            notice.audience = audience
            notice.notice_date = notice_date
            notice.expires_on = expires_on
            notice.is_published = request.form.get("is_published") == "on"
            try:
                db.session.commit()
                flash("Notice updated successfully.", "success")
                return redirect(url_for("main.admin_notices"))
            except Exception:
                db.session.rollback()
                flash("Could not update notice. Please try again.", "danger")

    return render_template(
        "admin_notices.html",
        notices=Notice.query.order_by(
            Notice.notice_date.desc(), Notice.id.desc()
        ).all(),
        notice=notice,
        audiences=NOTICE_AUDIENCES,
        today=date.today().isoformat()
    )


@main.route("/admin/notices/<int:notice_id>/delete", methods=["POST"])
@role_required("admin")
def delete_notice(notice_id):
    notice = Notice.query.get_or_404(notice_id)
    try:
        db.session.delete(notice)
        db.session.commit()
        flash("Notice deleted successfully.", "success")
    except Exception:
        db.session.rollback()
        flash("Notice could not be deleted. Please try again.", "danger")
    return redirect(url_for("main.admin_notices"))

@main.route("/admin/students")
@role_required("admin")
def admin_students():
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "all")

    query = Student.query

    if search:
        query = query.filter(
            db.or_(
                Student.full_name.ilike(f"%{search}%"),
                Student.roll_number.ilike(f"%{search}%")
            )
        )

    if status == "active":
        query = query.filter_by(is_active=True)
    elif status == "inactive":
        query = query.filter_by(is_active=False)

    students = query.order_by(Student.id.desc()).all()

    total_students = Student.query.count()
    active_students = Student.query.filter_by(is_active=True).count()
    inactive_students = Student.query.filter_by(is_active=False).count()

    return render_template(
        "admin_students.html",
        students=students,
        total_students=total_students,
        active_students=active_students,
        inactive_students=inactive_students,
        search=search,
        status=status
    )

@main.route("/admin/students/add", methods=["GET", "POST"])
@role_required("admin")
def add_student():
    error = None
    classrooms = Classroom.query.filter_by(is_active=True).order_by(
        Classroom.name.asc()
    ).all()
    users = User.query.filter_by(role="student", is_active=True).order_by(
        User.username.asc()
    ).all()

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        roll_number = request.form.get("roll_number", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        class_id = request.form.get("class_id", type=int)
        date_of_birth = request.form.get("date_of_birth", "")
        gender = request.form.get("gender", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        is_active = request.form.get("is_active") == "on"

        if not full_name or not roll_number or not username or not password or not confirm_password:
            error = "Name, roll number, username, password, and confirmation are required."

        elif password != confirm_password:
            error = "Passwords do not match."

        elif len(password) < 8:
            error = "Password must be at least 8 characters."

        elif Student.query.filter_by(roll_number=roll_number).first():
            error = "This roll number already exists."

        elif class_id and not db.session.get(Classroom, class_id):
            error = "The selected class was not found."

        elif User.query.filter_by(username=username).first():
            error = "This username is already in use."

        else:
            try:
                user = User(
                    username=username,
                    password_hash=generate_password_hash(password),
                    role="student",
                    is_active=True
                )
                db.session.add(user)
                db.session.flush()
                student = Student(
                    full_name=full_name,
                    roll_number=roll_number,
                    class_id=class_id,
                    user_id=user.id,
                    date_of_birth=(date.fromisoformat(date_of_birth) if date_of_birth else None),
                    gender=gender or None,
                    phone=phone or None,
                    address=address or None,
                    is_active=is_active,
                )
                db.session.add(student)
                db.session.commit()
                return redirect(url_for("main.admin_students"))
            except Exception:
                db.session.rollback()
                error = "Could not create student account. Please try again."

    return render_template(
        "add_student.html",
        error=error,
        classrooms=classrooms,
        users=users
    )


@main.route("/admin/students/edit/<int:student_id>", methods=["GET", "POST"])
@role_required("admin")
def edit_student(student_id):
    student = Student.query.get_or_404(student_id)
    error = None
    classrooms = Classroom.query.filter_by(is_active=True).order_by(
        Classroom.name.asc()
    ).all()
    users = User.query.filter_by(role="student", is_active=True).order_by(
        User.username.asc()
    ).all()

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        roll_number = request.form.get("roll_number", "").strip()
        user_id = request.form.get("user_id", type=int)
        new_username = request.form.get("new_username", "").strip()
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")
        class_id = request.form.get("class_id", type=int)
        date_of_birth = request.form.get("date_of_birth", "")
        gender = request.form.get("gender", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        is_active = request.form.get("is_active") == "on"

        if not full_name or not roll_number:
            error = "Full name and roll number are required."

        elif Student.query.filter(
            Student.roll_number == roll_number,
            Student.id != student.id
        ).first():
            error = "This roll number already belongs to another student."

        elif class_id and not db.session.get(Classroom, class_id):
            error = "The selected class was not found."

        elif user_id and (not db.session.get(User, user_id) or User.query.filter_by(id=user_id, role="student", is_active=True).first() is None):
            error = "The selected student account was not found."

        elif user_id and Student.query.filter(Student.user_id == user_id, Student.id != student.id).first():
            error = "This student account is already linked to another student."

        elif new_username and student.user_id:
            error = "A linked student account can only have its password reset here."

        elif new_username and User.query.filter_by(username=new_username).first():
            error = "This username is already in use."

        elif new_username and (not new_password or new_password != confirm_password):
            error = "New username requires matching password and confirmation."

        elif new_password and new_password != confirm_password:
            error = "Passwords do not match."

        elif new_password and len(new_password) < 8:
            error = "Password must be at least 8 characters."

        else:
            from datetime import date

            student.full_name = full_name
            student.roll_number = roll_number
            student.class_id = class_id
            if new_username:
                new_user = User(
                    username=new_username,
                    password_hash=generate_password_hash(new_password),
                    role="student",
                    is_active=True
                )
                db.session.add(new_user)
                db.session.flush()
                student.user_id = new_user.id
            else:
                student.user_id = user_id
                if new_password and student.user:
                    student.user.password_hash = generate_password_hash(new_password)
            student.date_of_birth = (
                date.fromisoformat(date_of_birth)
                if date_of_birth else None
            )
            student.gender = gender or None
            student.phone = phone or None
            student.address = address or None
            student.is_active = is_active

            db.session.commit()

            return redirect(url_for("main.admin_students"))

    return render_template(
        "edit_student.html",
        student=student,
        error=error,
        classrooms=classrooms,
        users=users
    )


@main.route("/admin/students/<int:student_id>")
@role_required("admin")
def student_details(student_id):
    student = Student.query.get_or_404(student_id)

    return render_template(
        "student_details.html",
        student=student
    )


@main.route("/admin/students/delete/<int:student_id>", methods=["POST"])
@role_required("admin")
def delete_student(student_id):
    student = Student.query.get_or_404(student_id)

    db.session.delete(student)
    db.session.commit()

    return redirect(url_for("main.admin_students"))


def _build_student_report_data(student):
    """Compile all data sections for a student's overall report. Returns a dict."""
    # ── Attendance ──────────────────────────────────────────────────────────
    all_attendance = (
        Attendance.query
        .filter_by(student_id=student.id)
        .order_by(Attendance.attendance_date.desc())
        .all()
    )
    att_totals = {s: 0 for s in ATTENDANCE_STATUSES}
    for rec in all_attendance:
        if rec.status in att_totals:
            att_totals[rec.status] += 1
    total_att_days = len(all_attendance)
    att_percentage = (
        ((att_totals["Present"] + att_totals["Late"]) / total_att_days) * 100
        if total_att_days else 0
    )
    recent_attendance = all_attendance[:20]   # latest 20 records

    # Monthly breakdown
    monthly_map = {}
    for rec in all_attendance:
        key = rec.attendance_date.strftime("%Y-%m")
        if key not in monthly_map:
            monthly_map[key] = {s: 0 for s in ATTENDANCE_STATUSES}
        if rec.status in monthly_map[key]:
            monthly_map[key][rec.status] += 1
    monthly_summary = [
        {
            "month": k,
            "label": datetime.strptime(k, "%Y-%m").strftime("%B %Y"),
            "totals": v,
            "total_days": sum(v.values()),
        }
        for k, v in sorted(monthly_map.items(), reverse=True)
    ]

    attendance_summary = {
        "total_days": total_att_days,
        "Present": att_totals["Present"],
        "Absent": att_totals["Absent"],
        "Late": att_totals["Late"],
        "percentage": att_percentage,
        "recent": recent_attendance,
        "monthly": monthly_summary,
    }

    # ── Exams & Results ─────────────────────────────────────────────────────
    # Fetch all results for this student, ordered by exam date desc
    all_results = (
        ExamResult.query
        .join(Exam)
        .filter(ExamResult.student_id == student.id)
        .order_by(Exam.exam_date.desc(), ExamResult.id.asc())
        .all()
    )

    # Group by exam
    exam_map = {}
    for res in all_results:
        exam = res.exam
        if exam.id not in exam_map:
            exam_map[exam.id] = {"exam": exam, "subject_rows": []}
        percentage = (float(res.marks) / exam.total_marks * 100) if exam.total_marks else 0
        exam_map[exam.id]["subject_rows"].append({
            "subject": res.subject,
            "result": res,
            "percentage": round(percentage, 1),
            "grade": res.grade,
        })

    exams_data = []
    total_obtained = Decimal("0.00")
    total_max = Decimal("0.00")
    for exam_id, ed in exam_map.items():
        ed["has_results"] = bool(ed["subject_rows"])
        for sr in ed["subject_rows"]:
            total_obtained += Decimal(str(sr["result"].marks))
            total_max += Decimal(str(sr["result"].exam.total_marks))
        exams_data.append(ed)

    overall_pct = (
        float(total_obtained / total_max * 100) if total_max else None
    )
    overall_grade = None
    if overall_pct is not None:
        overall_grade = _grade_for_marks(total_obtained, float(total_max))

    exam_summary = {
        "exams_data": exams_data,
        "total_obtained": total_obtained,
        "total_max": total_max,
        "overall_pct": round(overall_pct, 1) if overall_pct is not None else None,
        "overall_grade": overall_grade,
        "has_results": bool(all_results),
    }

    # ── Fees ─────────────────────────────────────────────────────────────────
    fee_records = _fee_records_for_student(student.id)
    total_assessed = sum((Decimal(str(f.amount)) for f in fee_records), Decimal("0.00"))
    total_paid = sum((Decimal(str(f.paid_amount)) for f in fee_records), Decimal("0.00"))
    total_balance = sum((Decimal(str(f.balance)) for f in fee_records), Decimal("0.00"))

    if not fee_records:
        st_status = "No Fees"
    elif total_balance <= Decimal("0.00"):
        st_status = "Paid"
    elif any(f.status == "Overdue" for f in fee_records):
        st_status = "Overdue"
    elif total_paid > Decimal("0.00"):
        st_status = "Partial"
    else:
        st_status = "Unpaid"

    fee_summary = {
        "fee_records": fee_records,
        "total_assessed": total_assessed,
        "total_paid": total_paid,
        "total_balance": total_balance,
        "invoices_count": len(fee_records),
        "status": st_status,
    }

    # ── Notices ──────────────────────────────────────────────────────────────
    notices = _published_notices_for_role("student")

    return {
        "attendance": attendance_summary,
        "exams": exam_summary,
        "fees": fee_summary,
        "notices": notices,
    }


@main.route("/admin/students/<int:student_id>/report")
@role_required("admin")
def student_overall_report(student_id):
    """Admin: complete student academic profile report."""
    student = Student.query.get_or_404(student_id)
    data = _build_student_report_data(student)
    return render_template(
        "student_overall_report.html",
        student=student,
        attendance=data["attendance"],
        exams=data["exams"],
        fees=data["fees"],
        notices=data["notices"],
    )


@main.route("/admin/students/<int:student_id>/report/pdf")
@role_required("admin")
def student_overall_report_pdf(student_id):
    """Admin: download PDF of the student's overall profile."""
    student = Student.query.get_or_404(student_id)
    data = _build_student_report_data(student)

    # Build attendance_summary dict expected by the PDF generator
    att = data["attendance"]
    attendance_summary = {
        "total_days": att["total_days"],
        "Present": att["Present"],
        "Absent": att["Absent"],
        "Late": att["Late"],
        "percentage": att["percentage"],
    }

    buf = generate_student_overall_profile_pdf(
        student=student,
        attendance_summary=attendance_summary,
        exams_data=data["exams"]["exams_data"],
        fee_summary={
            "invoices_count": data["fees"]["invoices_count"],
            "total_assessed": data["fees"]["total_assessed"],
            "total_paid": data["fees"]["total_paid"],
            "total_balance": data["fees"]["total_balance"],
            "status": data["fees"]["status"],
        },
    )
    safe_name = student.full_name.replace(" ", "_")[:30]
    return send_file(
        buf,
        mimetype="application/pdf",
        as_attachment=True,
        download_name="Student_Profile_{}_{}.pdf".format(
            student.roll_number, safe_name
        ),
    )


@main.route("/teacher/dashboard")
@role_required("teacher")
def teacher_dashboard():
    teacher = _current_teacher()
    if not teacher:
        return render_template(
            "teacher_dashboard.html",
            classrooms=[],
            assignments=[],
            student_count=0,
            attendance_counts={status: 0 for status in ATTENDANCE_STATUSES},
            attendance_total=0,
            notices=_published_notices_for_role("teacher"),
            profile_missing=True
        )

    classrooms = _teacher_classes(teacher)
    class_ids = [classroom.id for classroom in classrooms]
    assignments = ClassSubjectAssignment.query.filter_by(
        teacher_id=teacher.id
    ).join(Classroom).join(Subject).filter(
        Classroom.is_active.is_(True),
        Subject.is_active.is_(True)
    ).order_by(Classroom.name.asc(), Subject.name.asc()).all()
    students = Student.query.filter(
        Student.class_id.in_(class_ids),
        Student.is_active.is_(True)
    ).all() if class_ids else []
    attendance = Attendance.query.filter(
        Attendance.class_id.in_(
            [classroom.id for classroom in _attendance_classes_for_current_user()]
        )
    ).all()
    attendance_counts = {status: 0 for status in ATTENDANCE_STATUSES}
    for record in attendance:
        attendance_counts[record.status] += 1

    return render_template(
        "teacher_dashboard.html",
        classrooms=classrooms,
        assignments=assignments,
        student_count=len(students),
        attendance_counts=attendance_counts,
        attendance_total=sum(attendance_counts.values()),
        notices=_published_notices_for_role("teacher")
    )


@main.route("/teacher/classes")
@role_required("teacher")
def teacher_classes():
    teacher = _current_teacher()
    if not teacher:
        return render_template(
            "teacher_classes.html",
            classrooms=[],
            subject_counts={},
            profile_missing=True
        )
    classrooms = _teacher_classes(teacher)
    subject_counts = {
        classroom.id: sum(
            assignment.teacher_id == teacher.id
            for assignment in classroom.subject_assignments
        )
        for classroom in classrooms
    }
    return render_template(
        "teacher_classes.html",
        classrooms=classrooms,
        subject_counts=subject_counts
    )


@main.route("/teacher/classes/<int:class_id>")
@role_required("teacher")
def teacher_class_details(class_id):
    classroom = _authorized_teacher_class(class_id)
    teacher = _current_teacher()
    assignments = ClassSubjectAssignment.query.filter_by(
        class_id=classroom.id,
        teacher_id=teacher.id
    ).join(Subject).order_by(Subject.name.asc()).all()
    students = Student.query.filter_by(
        class_id=classroom.id,
        is_active=True
    ).order_by(Student.full_name.asc()).all()
    return render_template(
        "teacher_class_details.html",
        classroom=classroom,
        assignments=assignments,
        students=students
    )


@main.route("/teacher/subjects")
@role_required("teacher")
def teacher_subjects():
    teacher = _current_teacher()
    if not teacher:
        return render_template(
            "teacher_subjects.html",
            assignments=[],
            profile_missing=True
        )
    assignments = ClassSubjectAssignment.query.filter_by(
        teacher_id=teacher.id
    ).join(Classroom).join(Subject).filter(
        Classroom.is_active.is_(True),
        Subject.is_active.is_(True)
    ).order_by(Classroom.name.asc(), Subject.name.asc()).all()
    return render_template("teacher_subjects.html", assignments=assignments)


@main.route("/student/dashboard")
@role_required("student")
def student_dashboard():
    student = _current_student()
    attendance_totals = {value: 0 for value in ATTENDANCE_STATUSES}
    latest_result = None
    fees = []

    if student:
        attendance_records = Attendance.query.filter_by(
            student_id=student.id
        ).all()
        for record in attendance_records:
            attendance_totals[record.status] += 1

        latest_result = ExamResult.query.join(Exam).filter(
            Exam.is_published.is_(True),
            ExamResult.student_id == student.id
        ).order_by(Exam.exam_date.desc(), ExamResult.id.desc()).first()
        fees = _fee_records_for_student(student.id)

    total_classes = sum(attendance_totals.values())
    attendance_percentage = (
        ((attendance_totals["Present"] + attendance_totals["Late"]) / total_classes) * 100
        if total_classes else 0
    )

    return render_template(
        "student_dashboard.html",
        student=student,
        attendance_totals=attendance_totals,
        total_classes=total_classes,
        attendance_percentage=attendance_percentage,
        latest_result=latest_result,
        latest_fee=fees[0] if fees else None,
        notice_count=len(_published_notices_for_role("student")),
        notices=_published_notices_for_role("student")
    )



@main.route("/")
def home():
    return render_template("home.html")


@main.route("/about")
def about():
    return "School Management System - About Page"

@main.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        selected_role = request.form.get("role", "").strip()

        user = User.query.filter_by(username=username).first()

        if (
            user
            and user.is_active
            and check_password_hash(user.password_hash, password)
            and selected_role == user.role
        ):
            session.clear()
            session["user_id"] = user.id
            session["role"] = user.role

            if user.role == "admin":
                return redirect(url_for("main.admin_dashboard"))
            elif user.role == "teacher":
                return redirect(url_for("main.teacher_dashboard"))
            elif user.role == "student":
                return redirect(url_for("main.student_dashboard"))

        error = "Invalid username, password, or selected role."

    return render_template("login.html", error=error)
    
@main.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.login"))
