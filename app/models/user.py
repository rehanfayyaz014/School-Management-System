from app import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    teacher_profile = db.relationship(
        "Teacher",
        back_populates="user",
        uselist=False
    )
    student_profile = db.relationship(
        "Student",
        back_populates="user",
        uselist=False
    )
    attendance_records = db.relationship(
        "Attendance",
        back_populates="recorded_by"
    )
    exam_results = db.relationship("ExamResult", back_populates="recorded_by")
    created_fee_records = db.relationship("FeeRecord", back_populates="created_by")
    received_fee_payments = db.relationship("FeePayment", back_populates="received_by")
    notices = db.relationship("Notice", back_populates="created_by")
