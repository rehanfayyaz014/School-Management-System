from datetime import datetime, timezone
from app import db


class Teacher(db.Model):
    __tablename__ = "teachers"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        unique=True,
        nullable=True
    )

    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    gender = db.Column(db.String(20), nullable=True)
    qualification = db.Column(db.String(150), nullable=True)

    is_active = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    classrooms_as_class_teacher = db.relationship(
        "Classroom",
        foreign_keys="Classroom.class_teacher_id",
        back_populates="class_teacher"
    )
    subject_assignments = db.relationship(
        "ClassSubjectAssignment",
        back_populates="teacher"
    )
    user = db.relationship("User", back_populates="teacher_profile")

    def __repr__(self):
        return f"<Teacher {self.full_name}>"
