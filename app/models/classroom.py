from datetime import datetime, timezone
from app import db


class Classroom(db.Model):
    __tablename__ = "classrooms"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(
        db.String(80),
        unique=True,
        nullable=False
    )

    class_teacher_id = db.Column(
        db.Integer,
        db.ForeignKey("teachers.id", ondelete="SET NULL"),
        nullable=True
    )

    description = db.Column(
        db.String(250),
        nullable=True
    )

    is_active = db.Column(
        db.Boolean,
        default=True,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    class_teacher = db.relationship(
        "Teacher",
        foreign_keys=[class_teacher_id],
        back_populates="classrooms_as_class_teacher"
    )
    students = db.relationship(
        "Student",
        back_populates="classroom",
        passive_deletes=True
    )
    subject_assignments = db.relationship(
        "ClassSubjectAssignment",
        back_populates="classroom",
        cascade="all, delete-orphan"
    )
    attendance_records = db.relationship(
        "Attendance",
        back_populates="classroom",
        cascade="all, delete-orphan"
    )
    exams = db.relationship(
        "Exam",
        back_populates="classroom",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Classroom {self.name}>"
