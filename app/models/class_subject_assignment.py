from app import db


class ClassSubjectAssignment(db.Model):
    __tablename__ = "class_subject_assignments"
    __table_args__ = (
        db.UniqueConstraint(
            "class_id",
            "subject_id",
            name="uq_class_subject_assignment"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(
        db.Integer,
        db.ForeignKey("classrooms.id", ondelete="CASCADE"),
        nullable=False
    )
    subject_id = db.Column(
        db.Integer,
        db.ForeignKey("subjects.id", ondelete="CASCADE"),
        nullable=False
    )
    teacher_id = db.Column(
        db.Integer,
        db.ForeignKey("teachers.id", ondelete="RESTRICT"),
        nullable=False
    )

    classroom = db.relationship(
        "Classroom",
        back_populates="subject_assignments"
    )
    subject = db.relationship(
        "Subject",
        back_populates="assignments"
    )
    teacher = db.relationship(
        "Teacher",
        back_populates="subject_assignments"
    )
