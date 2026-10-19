from datetime import datetime, timezone

from app import db


class Exam(db.Model):
    __tablename__ = "exams"
    __table_args__ = (
        db.UniqueConstraint("class_id", "name", name="uq_exam_class_name"),
        db.CheckConstraint("total_marks > 0", name="ck_exam_total_marks_positive"),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    class_id = db.Column(
        db.Integer,
        db.ForeignKey("classrooms.id", ondelete="CASCADE"),
        nullable=False
    )
    exam_date = db.Column(db.Date, nullable=False)
    total_marks = db.Column(db.Integer, nullable=False, default=100)
    is_published = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    classroom = db.relationship("Classroom", back_populates="exams")
    results = db.relationship(
        "ExamResult",
        back_populates="exam",
        cascade="all, delete-orphan"
    )


class ExamResult(db.Model):
    __tablename__ = "exam_results"
    __table_args__ = (
        db.UniqueConstraint(
            "exam_id", "student_id", "subject_id",
            name="uq_exam_result_student_subject"
        ),
        db.CheckConstraint("marks >= 0", name="ck_exam_result_marks_nonnegative"),
    )

    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(
        db.Integer,
        db.ForeignKey("exams.id", ondelete="CASCADE"),
        nullable=False
    )
    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False
    )
    subject_id = db.Column(
        db.Integer,
        db.ForeignKey("subjects.id", ondelete="RESTRICT"),
        nullable=False
    )
    marks = db.Column(db.Numeric(6, 2), nullable=False)
    grade = db.Column(db.String(5), nullable=False)
    remarks = db.Column(db.String(250), nullable=True)
    recorded_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False
    )
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    exam = db.relationship("Exam", back_populates="results")
    student = db.relationship("Student", back_populates="exam_results")
    subject = db.relationship("Subject", back_populates="exam_results")
    recorded_by = db.relationship("User", back_populates="exam_results")
