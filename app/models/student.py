from app import db


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    roll_number = db.Column(db.String(30), unique=True, nullable=False)
    class_id = db.Column(
        db.Integer,
        db.ForeignKey("classrooms.id", ondelete="SET NULL"),
        nullable=True
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        unique=True,
        nullable=True
    )
    date_of_birth = db.Column(db.Date, nullable=True)
    gender = db.Column(db.String(20), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.String(250), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    classroom = db.relationship("Classroom", back_populates="students")
    attendance_records = db.relationship(
        "Attendance",
        back_populates="student",
        cascade="all, delete-orphan"
    )
    user = db.relationship("User", back_populates="student_profile")
    exam_results = db.relationship(
        "ExamResult",
        back_populates="student",
        cascade="all, delete-orphan"
    )
    fee_records = db.relationship(
        "FeeRecord",
        back_populates="student",
        cascade="all, delete-orphan"
    )
