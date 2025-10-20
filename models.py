from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    branch = db.Column(db.String(50))
    year = db.Column(db.Integer, nullable=True)  # Explicitly allow NULL for teachers
    phone = db.Column(db.String(15), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # student, teacher, admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    branch = db.Column(db.String(50), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    roll_number = db.Column(db.String(20), unique=True, nullable=False)  # Added nullable=False

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(10), nullable=False)  # Present/Absent
    marked_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    student = db.relationship('Student', backref='attendance_records')
    marker = db.relationship('User', backref='marked_attendance')  # Added relationship

class LostFoundImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    lost_found_id = db.Column(db.Integer, db.ForeignKey('lost_found.id'), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    lost_found = db.relationship('LostFound', backref=db.backref('images', lazy=True, cascade='all, delete-orphan'))

class LostFound(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    item_type = db.Column(db.String(20), nullable=False)  # lost or found
    posted_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    posted_at = db.Column(db.DateTime, default=datetime.utcnow)
    contact_info = db.Column(db.String(100))
    is_resolved = db.Column(db.Boolean, default=False)
    location = db.Column(db.String(100))  # New field for location
    date_occurred = db.Column(db.DateTime)  # New field for when item was lost/found
    
    poster = db.relationship('User', backref='lost_found_posts')

class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    posted_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    posted_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_resolved = db.Column(db.Boolean, default=False)
    
    poster = db.relationship('User', backref='complaints')

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text)
    file_path = db.Column(db.String(300))
    file_type = db.Column(db.String(50))  # image, video, document, etc.
    posted_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    posted_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    poster = db.relationship('User', backref='messages')

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    posted_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    posted_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_public = db.Column(db.Boolean, default=True)
    file_path = db.Column(db.String(300))  # Added for file uploads
    file_type = db.Column(db.String(50))   # Added for file type detection
    
    poster = db.relationship('User', backref='notes')

class Teacher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15), unique=True, nullable=False)  # Added unique constraint
    branch = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100))
    designation = db.Column(db.String(100))

    def update(self, name, phone, branch, email, designation):
        self.name = name
        self.phone = phone
        self.branch = branch
        self.email = email
        self.designation = designation
        db.session.commit()