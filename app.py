from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from models import db, User, Student, Attendance, LostFound, Complaint, Message, Note, Teacher, LostFoundImage
import os
from datetime import datetime, date, timedelta
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///college_app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # Increased to 50MB max file size

# Allowed file extensions
ALLOWED_EXTENSIONS = {
    'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 
    'ppt', 'pptx', 'xls', 'xlsx', 'mp4', 'avi', 'mov'
}

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Context processor for all models and utilities
@app.context_processor
def inject_models():
    return {
        'User': User,
        'Student': Student,
        'Attendance': Attendance,
        'LostFound': LostFound,
        'LostFoundImage': LostFoundImage,
        'Complaint': Complaint,
        'Message': Message,
        'Note': Note,
        'Teacher': Teacher,
        'timedelta': timedelta,
        'datetime': datetime,
        'date': date
    }

# Initialize database and create admin user
def init_db():
    with app.app_context():
        print("Dropping all existing tables...")
        db.drop_all()  # ⚠️ This DELETES all existing data
        
        print("Creating new tables with updated schema...")
        db.create_all()  # Creates fresh tables with new columns
        
        # Create admin user if not exists
        admin = User.query.filter_by(role='admin').first()
        if not admin:
            admin = User(
                name='Admin',
                phone='0000000000',
                role='admin'
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("Admin user created!")
        
        # Create upload directories
        upload_dirs = ['lost_found', 'notes', 'messages']
        for dir_name in upload_dirs:
            dir_path = os.path.join(app.config['UPLOAD_FOLDER'], dir_name)
            os.makedirs(dir_path, exist_ok=True)
            print(f"Created directory: {dir_path}")
        
        print("✅ Database successfully recreated with new schema!")
        
        # Create upload directories
        upload_dirs = ['lost_found', 'notes', 'messages']
        for dir_name in upload_dirs:
            dir_path = os.path.join(app.config['UPLOAD_FOLDER'], dir_name)
            os.makedirs(dir_path, exist_ok=True)

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        role = request.form.get('role')
        phone = request.form.get('phone')
        password = request.form.get('password')
        
        if not role or not phone or not password:
            flash('Please fill all required fields', 'danger')
            return redirect(url_for('login'))
        
        if role == 'teacher':
            secret_code = request.form.get('secret_code')
            if secret_code != 'TEACHER123':
                flash('Invalid secret code for teacher login', 'danger')
                return redirect(url_for('login'))
        
        user = User.query.filter_by(phone=phone, role=role).first()
        
        if user and user.check_password(password):
            login_user(user)
            flash(f'Welcome back, {user.name}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('Invalid phone number, password, or role selection', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        branch = request.form.get('branch')
        year = request.form.get('year')
        phone = request.form.get('phone')
        password = request.form.get('password')
        role = request.form.get('role')
        secret_code = request.form.get('secret_code')
        
        # Validate required fields
        if not all([name, branch, phone, password, role]):
            flash('Please fill all required fields', 'danger')
            return redirect(url_for('register'))
        
        # Additional validation for students
        if role == 'student' and not year:
            flash('Year is required for students', 'danger')
            return redirect(url_for('register'))
        
        # Validate teacher secret code
        if role == 'teacher':
            if not secret_code or secret_code != 'TEACHER123':
                flash('Invalid secret code for teacher registration', 'danger')
                return redirect(url_for('register'))
        
        if User.query.filter_by(phone=phone).first():
            flash('Phone number already registered', 'danger')
            return redirect(url_for('register'))
        
        # Create user
        user = User(
            name=name,
            branch=branch,
            year=int(year) if year and role == 'student' else None,
            phone=phone,
            role=role
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    # Add some stats for the dashboard
    stats = {
        'total_students': Student.query.count(),
        'total_teachers': Teacher.query.count(),
        'today_attendance': Attendance.query.filter_by(date=date.today()).count(),
        'pending_complaints': Complaint.query.filter_by(is_resolved=False).count(),
        'recent_lost_found': LostFound.query.filter_by(is_resolved=False).count()
    }
    return render_template('dashboard.html', stats=stats)

@app.route('/attendance', methods=['GET', 'POST'])
@login_required
def attendance():
    if request.method == 'POST':
        if current_user.role not in ['admin', 'teacher']:
            flash('You are not authorized to mark attendance', 'danger')
            return redirect(url_for('attendance'))
        
        student_id = request.form.get('student_id')
        status = request.form.get('status')
        attendance_date_str = request.form.get('date')
        
        # Validate required fields
        if not student_id or not status:
            flash('Please select both student and status', 'danger')
            return redirect(url_for('attendance'))
        
        # Handle date
        try:
            if attendance_date_str:
                attendance_date = datetime.strptime(attendance_date_str, '%Y-%m-%d').date()
            else:
                attendance_date = date.today()
        except ValueError:
            flash('Invalid date format', 'danger')
            return redirect(url_for('attendance'))
        
        # Check if student exists
        student = Student.query.get(student_id)
        if not student:
            flash('Selected student not found', 'danger')
            return redirect(url_for('attendance'))
        
        # Check if attendance already marked for the date
        existing = Attendance.query.filter_by(
            student_id=student_id, 
            date=attendance_date
        ).first()
        
        if existing:
            existing.status = status
            existing.marked_by = current_user.id
            action = 'updated'
        else:
            attendance = Attendance(
                student_id=student_id,
                date=attendance_date,
                status=status,
                marked_by=current_user.id
            )
            db.session.add(attendance)
            action = 'marked'
        
        db.session.commit()
        flash(f'Attendance {action} successfully for {student.name} on {attendance_date}', 'success')
        return redirect(url_for('attendance'))
    
    # GET request - show attendance page
    students = Student.query.order_by(Student.name).all()
    today_attendance = Attendance.query.filter_by(date=date.today()).all()
    
    # Get unique dates for filter (last 30 days)
    thirty_days_ago = date.today() - timedelta(days=30)
    attendance_dates = db.session.query(Attendance.date).filter(
        Attendance.date >= thirty_days_ago
    ).distinct().order_by(Attendance.date.desc()).all()
    
    # Convert to simple list
    attendance_dates = [att_date[0] for att_date in attendance_dates]
    
    return render_template('attendance.html', 
                         students=students, 
                         today_attendance=today_attendance,
                         attendance_dates=attendance_dates,
                         today=date.today())

@app.route('/attendance/date/<string:selected_date>')
@login_required
def attendance_by_date(selected_date):
    """View attendance for a specific date"""
    try:
        selected_date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
        attendance_records = Attendance.query.filter_by(date=selected_date_obj).all()
        students = Student.query.order_by(Student.name).all()
        
        # Get unique dates for filter
        thirty_days_ago = date.today() - timedelta(days=30)
        attendance_dates = db.session.query(Attendance.date).filter(
            Attendance.date >= thirty_days_ago
        ).distinct().order_by(Attendance.date.desc()).all()
        attendance_dates = [att_date[0] for att_date in attendance_dates]
        
        return render_template('attendance.html',
                             students=students,
                             today_attendance=attendance_records,
                             attendance_dates=attendance_dates,
                             selected_date=selected_date_obj,
                             today=date.today())
    except ValueError:
        flash('Invalid date format', 'danger')
        return redirect(url_for('attendance'))

@app.route('/add_student', methods=['POST'])
@login_required
def add_student():
    if current_user.role != 'admin':
        flash('Only admin can add students', 'danger')
        return redirect(url_for('attendance'))
    
    name = request.form.get('name')
    branch = request.form.get('branch')
    year = request.form.get('year')
    roll_number = request.form.get('roll_number')
    
    if not all([name, branch, year, roll_number]):
        flash('Please fill all required fields', 'danger')
        return redirect(url_for('attendance'))
    
    # Check if roll number already exists
    if Student.query.filter_by(roll_number=roll_number).first():
        flash('Roll number already exists', 'danger')
        return redirect(url_for('attendance'))
    
    try:
        student = Student(
            name=name,
            branch=branch,
            year=int(year),
            roll_number=roll_number
        )
        db.session.add(student)
        db.session.commit()
        flash('Student added successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error adding student: ' + str(e), 'danger')
    
    return redirect(url_for('attendance'))

@app.route('/edit_student/<int:student_id>', methods=['GET', 'POST'])
@login_required
def edit_student(student_id):
    if current_user.role != 'admin':
        flash('Only admin can edit students', 'danger')
        return redirect(url_for('attendance'))
    
    student = Student.query.get_or_404(student_id)
    
    if request.method == 'POST':
        student.name = request.form.get('name')
        student.branch = request.form.get('branch')
        student.year = request.form.get('year')
        student.roll_number = request.form.get('roll_number')
        
        db.session.commit()
        flash('Student information updated successfully', 'success')
        return redirect(url_for('attendance'))
    
    return render_template('edit_student.html', student=student)

@app.route('/delete_student/<int:student_id>')
@login_required
def delete_student(student_id):
    if current_user.role != 'admin':
        flash('Only admin can delete students', 'danger')
        return redirect(url_for('attendance'))
    
    student = Student.query.get_or_404(student_id)
    
    try:
        # Also delete attendance records for this student
        Attendance.query.filter_by(student_id=student_id).delete()
        db.session.delete(student)
        db.session.commit()
        flash('Student deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting student: ' + str(e), 'danger')
    
    return redirect(url_for('attendance'))

@app.route('/lost_found')
@login_required
def lost_found():
    posts = LostFound.query.order_by(LostFound.posted_at.desc()).all()
    return render_template('lost_found.html', posts=posts)

@app.route('/post_lost_found', methods=['POST'])
@login_required
def post_lost_found():
    title = request.form.get('title')
    description = request.form.get('description')
    item_type = request.form.get('type')
    contact_info = request.form.get('contact_info')
    location = request.form.get('location')
    date_occurred_str = request.form.get('date_occurred')
    files = request.files.getlist('item_images')
    
    if not title or not description:
        flash('Title and description are required', 'danger')
        return redirect(url_for('lost_found'))
    
    # Parse date_occurred
    date_occurred = None
    if date_occurred_str:
        try:
            date_occurred = datetime.strptime(date_occurred_str, '%Y-%m-%d')
        except ValueError:
            flash('Invalid date format', 'danger')
            return redirect(url_for('lost_found'))
    
    # Create the post
    post = LostFound(
        title=title,
        description=description,
        item_type=item_type,
        posted_by=current_user.id,
        contact_info=contact_info,
        location=location,
        date_occurred=date_occurred
    )
    db.session.add(post)
    db.session.flush()  # Get the post ID without committing
    
    # Handle file uploads
    uploaded_count = 0
    if files and files[0].filename:  # Check if files were uploaded
        lost_found_upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'lost_found')
        os.makedirs(lost_found_upload_dir, exist_ok=True)
        
        for file in files[:3]:  # Limit to 3 files
            if file and file.filename and allowed_file(file.filename):
                # Check file size (5MB max)
                file.seek(0, os.SEEK_END)
                file_length = file.tell()
                file.seek(0)
                
                if file_length > 5 * 1024 * 1024:
                    flash(f'File {file.filename} is too large. Maximum size is 5MB.', 'warning')
                    continue
                
                # Generate secure filename
                filename = secure_filename(file.filename)
                unique_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{post.id}_{filename}"
                file_path = os.path.join(lost_found_upload_dir, unique_filename)
                
                try:
                    file.save(file_path)
                    
                    # Create image record
                    image = LostFoundImage(
                        filename=unique_filename,
                        lost_found_id=post.id
                    )
                    db.session.add(image)
                    uploaded_count += 1
                    
                except Exception as e:
                    flash(f'Error saving file {filename}: {str(e)}', 'warning')
    
    db.session.commit()
    
    if uploaded_count > 0:
        flash(f'Post created successfully with {uploaded_count} image(s)', 'success')
    else:
        flash('Post created successfully', 'success')
    
    return redirect(url_for('lost_found'))

@app.route('/mark_resolved/<int:post_id>')
@login_required
def mark_resolved(post_id):
    post = LostFound.query.get_or_404(post_id)
    if current_user.role == 'admin' or post.posted_by == current_user.id:
        post.is_resolved = not post.is_resolved
        db.session.commit()
        status = "resolved" if post.is_resolved else "unresolved"
        flash(f'Post marked as {status}', 'success')
    else:
        flash('You are not authorized to perform this action', 'danger')
    return redirect(url_for('lost_found'))

@app.route('/delete_lost_found/<int:post_id>')
@login_required
def delete_lost_found(post_id):
    post = LostFound.query.get_or_404(post_id)
    if current_user.role == 'admin' or post.posted_by == current_user.id:
        try:
            # Delete associated images and files
            lost_found_upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'lost_found')
            for image in post.images:
                file_path = os.path.join(lost_found_upload_dir, image.filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
            
            db.session.delete(post)
            db.session.commit()
            flash('Post deleted successfully', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error deleting post: ' + str(e), 'danger')
    else:
        flash('You are not authorized to delete this post', 'danger')
    return redirect(url_for('lost_found'))

@app.route('/uploads/lost_found/<filename>')
@login_required
def lost_found_image(filename):
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], 'lost_found'), filename)

@app.route('/complaints')
@login_required
def complaints():
    complaints_list = Complaint.query.order_by(Complaint.posted_at.desc()).all()
    return render_template('complaints.html', complaints=complaints_list)

@app.route('/post_complaint', methods=['POST'])
@login_required
def post_complaint():
    title = request.form.get('title')
    message = request.form.get('message')
    
    if not title or not message:
        flash('Title and message are required', 'danger')
        return redirect(url_for('complaints'))
    
    complaint = Complaint(
        title=title,
        message=message,
        posted_by=current_user.id
    )
    db.session.add(complaint)
    db.session.commit()
    
    flash('Complaint submitted successfully', 'success')
    return redirect(url_for('complaints'))

@app.route('/mark_complaint_resolved/<int:complaint_id>')
@login_required
def mark_complaint_resolved(complaint_id):
    if current_user.role != 'admin':
        flash('Only admin can resolve complaints', 'danger')
        return redirect(url_for('complaints'))
    
    complaint = Complaint.query.get_or_404(complaint_id)
    complaint.is_resolved = not complaint.is_resolved  # Toggle resolution status
    db.session.commit()
    
    status = "resolved" if complaint.is_resolved else "reopened"
    flash(f'Complaint marked as {status}', 'success')
    return redirect(url_for('complaints'))

# ADD THIS NEW ROUTE FOR DELETING COMPLAINTS
@app.route('/delete_complaint/<int:complaint_id>')
@login_required
def delete_complaint(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)
    if current_user.role == 'admin' or complaint.posted_by == current_user.id:
        try:
            db.session.delete(complaint)
            db.session.commit()
            flash('Complaint deleted successfully', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error deleting complaint: ' + str(e), 'danger')
    else:
        flash('You are not authorized to delete this complaint', 'danger')
    return redirect(url_for('complaints'))

@app.route('/communication')
@login_required
def communication():
    messages = Message.query.order_by(Message.posted_at.desc()).all()
    return render_template('communication.html', messages=messages)

@app.route('/post_message', methods=['POST'])
@login_required
def post_message():
    content = request.form.get('content')
    file = request.files.get('file')
    
    if not content and not file:
        flash('Please enter a message or select a file', 'danger')
        return redirect(url_for('communication'))
    
    file_path = None
    file_type = None
    
    if file and file.filename:
        if allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Add timestamp to avoid filename conflicts
            filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
            file_path = filename  # Store only filename, not full path
            full_path = os.path.join(app.config['UPLOAD_FOLDER'], 'messages', filename)
            file.save(full_path)
            file_type = filename.rsplit('.', 1)[1].lower()
        else:
            flash('File type not allowed', 'danger')
            return redirect(url_for('communication'))
    
    message = Message(
        content=content,
        file_path=file_path,
        file_type=file_type,
        posted_by=current_user.id
    )
    db.session.add(message)
    db.session.commit()
    
    flash('Message posted successfully', 'success')
    return redirect(url_for('communication'))

@app.route('/delete_message/<int:message_id>')
@login_required
def delete_message(message_id):
    message = Message.query.get_or_404(message_id)
    if current_user.role == 'admin' or message.posted_by == current_user.id:
        try:
            if message.file_path:
                full_path = os.path.join(app.config['UPLOAD_FOLDER'], 'messages', message.file_path)
                if os.path.exists(full_path):
                    os.remove(full_path)
            db.session.delete(message)
            db.session.commit()
            flash('Message deleted successfully', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error deleting message: ' + str(e), 'danger')
    else:
        flash('You are not authorized to delete this message', 'danger')
    return redirect(url_for('communication'))

@app.route('/notes')
@login_required
def notes():
    notes_list = Note.query.filter(
        (Note.is_public == True) | (Note.posted_by == current_user.id)
    ).order_by(Note.posted_at.desc()).all()
    return render_template('notes.html', notes=notes_list)

@app.route('/post_note', methods=['POST'])
@login_required
def post_note():
    title = request.form.get('title')
    content = request.form.get('content')
    is_public = request.form.get('is_public') == 'on'
    file = request.files.get('file')
    
    if not title or not content:
        flash('Title and content are required', 'danger')
        return redirect(url_for('notes'))
    
    file_path = None
    file_type = None
    
    if file and file.filename:
        if allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Add timestamp to avoid filename conflicts
            filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
            file_path = filename  # Store only filename, not full path
            full_path = os.path.join(app.config['UPLOAD_FOLDER'], 'notes', filename)
            file.save(full_path)
            file_type = filename.rsplit('.', 1)[1].lower()
        else:
            flash('File type not allowed', 'danger')
            return redirect(url_for('notes'))
    
    note = Note(
        title=title,
        content=content,
        posted_by=current_user.id,
        is_public=is_public,
        file_path=file_path,
        file_type=file_type
    )
    db.session.add(note)
    db.session.commit()
    
    flash('Note posted successfully', 'success')
    return redirect(url_for('notes'))

@app.route('/delete_note/<int:note_id>')
@login_required
def delete_note(note_id):
    note = Note.query.get_or_404(note_id)
    if current_user.role == 'admin' or note.posted_by == current_user.id:
        try:
            # Delete associated file if exists
            if note.file_path:
                full_path = os.path.join(app.config['UPLOAD_FOLDER'], 'notes', note.file_path)
                if os.path.exists(full_path):
                    os.remove(full_path)
            db.session.delete(note)
            db.session.commit()
            flash('Note deleted successfully', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Error deleting note: ' + str(e), 'danger')
    else:
        flash('You are not authorized to delete this note', 'danger')
    return redirect(url_for('notes'))

@app.route('/teachers')
@login_required
def teachers():
    teachers_list = Teacher.query.order_by(Teacher.name).all()
    return render_template('teachers.html', teachers=teachers_list)

@app.route('/add_teacher', methods=['POST'])
@login_required
def add_teacher():
    if current_user.role != 'admin':
        flash('Only admin can add teachers', 'danger')
        return redirect(url_for('teachers'))
    
    name = request.form.get('name')
    phone = request.form.get('phone')
    branch = request.form.get('branch')
    email = request.form.get('email')
    designation = request.form.get('designation')
    
    if not name or not phone or not branch:
        flash('Name, phone, and branch are required', 'danger')
        return redirect(url_for('teachers'))
    
    # Check if phone already exists
    if Teacher.query.filter_by(phone=phone).first():
        flash('Phone number already exists', 'danger')
        return redirect(url_for('teachers'))
    
    teacher = Teacher(
        name=name,
        phone=phone,
        branch=branch,
        email=email,
        designation=designation
    )
    db.session.add(teacher)
    db.session.commit()
    
    flash('Teacher added successfully', 'success')
    return redirect(url_for('teachers'))

@app.route('/edit_teacher/<int:teacher_id>', methods=['GET', 'POST'])
@login_required
def edit_teacher(teacher_id):
    if current_user.role != 'admin':
        flash('Only admin can edit teachers', 'danger')
        return redirect(url_for('teachers'))
    
    teacher = Teacher.query.get_or_404(teacher_id)
    
    if request.method == 'POST':
        teacher.name = request.form.get('name')
        teacher.phone = request.form.get('phone')
        teacher.branch = request.form.get('branch')
        teacher.email = request.form.get('email')
        teacher.designation = request.form.get('designation')
        
        db.session.commit()
        flash('Teacher information updated successfully', 'success')
        return redirect(url_for('teachers'))
    
    return render_template('edit_teacher.html', teacher=teacher)

@app.route('/delete_teacher/<int:teacher_id>')
@login_required
def delete_teacher(teacher_id):
    if current_user.role != 'admin':
        flash('Only admin can delete teachers', 'danger')
        return redirect(url_for('teachers'))
    
    teacher = Teacher.query.get_or_404(teacher_id)
    db.session.delete(teacher)
    db.session.commit()
    
    flash('Teacher deleted successfully', 'success')
    return redirect(url_for('teachers'))

@app.route('/chatbot', methods=['GET', 'POST'])
@login_required
def chatbot():
    if request.method == 'POST':
        user_message = request.form.get('message')
        if not user_message:
            return jsonify({'response': 'Please enter a message.'})
        
        response = get_enhanced_chatbot_response(user_message, current_user)
        return jsonify({'response': response})
    
    return render_template('chatbot.html')

def get_enhanced_chatbot_response(message, current_user):
    message = message.lower().strip()
    
    # Enhanced responses with file upload info
    responses = {
        'hello': f'Hello {current_user.name}! 👋 How can I assist you today in CollegeCompanion?',
        'hi': f'Hi {current_user.name}! 😊 What can I help you with?',
        'help': f'''🤖 **CollegeCompanion AI Assistant - Help Guide**

📊 **ATTENDANCE SYSTEM**
• Mark daily attendance (Teachers/Admin)
• View attendance records by date
• Add/edit students (Admin only)
• Generate attendance reports

🔍 **LOST & FOUND**
• Post lost or found items with images
• Upload up to 3 photos per post
• Browse active posts with image galleries
• Contact item owners
• Mark items as resolved

📝 **COMPLAINT BOX**
• Submit anonymous complaints
• Delete your own complaints
• View all complaints (Admin sees posters)
• Resolve complaints (Admin only)

💬 **COMMUNICATION HUB**
• Send messages to community
• Share files (images, documents, videos)
• Delete your messages

📚 **NOTES SHARING**
• Create public/private notes
• Upload study materials (up to 50MB)
• Download shared resources
• Organize by subjects/topics

👨‍🏫 **TEACHER DIRECTORY**
• View faculty contacts
• See department information
• Contact teachers directly

🎓 **STUDENT MANAGEMENT**
• Student database (Admin)
• Roll number tracking
• Branch-wise organization

**Quick Commands:** Try: "how to mark attendance", "post lost item with images", "share notes", "contact teachers"''',

        'attendance': '''📊 **Attendance Management Guide:**

**For Teachers/Admin:**
✅ Mark attendance for specific dates
✅ View attendance by student or date  
✅ Generate monthly reports
✅ Add new students to system

**For Students:**
✅ View your attendance record
✅ Check attendance statistics

**Commands to try:**
• "Mark attendance for today"
• "View attendance for December"
• "Add new student"
• "Check my attendance"''',

        'lost found': '''🔍 **Lost & Found System:**

**Posting Items:**
✅ Report lost items with detailed descriptions
✅ Post found items with contact information  
✅ Upload up to 3 images per post (JPG, PNG, GIF)
✅ Add location and date information
✅ Maximum file size: 5MB per image

**Finding Items:**
✅ Browse all active posts with image galleries
✅ Search by item type or location
✅ Contact posters directly
✅ Mark items as resolved when found

**Image Upload Features:**
📸 Take clear photos from multiple angles
🏷️ Show distinctive features or damage
📍 Include location context in images
📱 Mobile-friendly upload interface

**Commands to try:**
• "I lost my calculator in the library"
• "Show found electronics items" 
• "How to upload images for lost items"
• "Post found keys with photos"''',

        'upload': '''📁 **File Upload Guide:**

**Lost & Found Images:**
✅ Supported: JPG, PNG, GIF
✅ Maximum: 3 images per post
✅ Size limit: 5MB per image
✅ Automatic image optimization

**Notes & Study Materials:**
✅ Supported: PDF, DOC, PPT, TXT, images, videos
✅ Maximum: 50MB per file
✅ Public/private sharing options
✅ Organized by subjects

**Communication Files:**
✅ All file types supported
✅ 50MB size limit
✅ Instant sharing with community
✅ File type icons and previews

**Best Practices:**
• Use descriptive filenames
• Compress large files when possible
• Check file formats before uploading
• Add clear descriptions with files''',

        'complaint': '''📝 **Complaint System:**

**Submitting Complaints:**
✅ Anonymous submission (name hidden from others)
✅ Categorized complaints
✅ Priority tagging
✅ Track resolution status

**Managing Complaints:**
✅ Delete your own complaints
✅ View complaint status
✅ Admin resolution tracking

**For Admin:**
✅ View all complaints with poster info
✅ See who submitted each complaint
✅ Mark as resolved/reopened
✅ Delete any complaint

**Commands to try:**
• "Submit complaint about WiFi"
• "View pending complaints"
• "Resolve complaint #5"
• "Delete my complaint"''',

        'communication': '''💬 **Communication Center:**

**Features:**
✅ Group messaging for all users
✅ File sharing (images, PDFs, videos)
✅ Real-time updates
✅ Message deletion (own messages)

**File Support:**
📷 Images: JPG, PNG, GIF
📄 Documents: PDF, DOC, TXT
🎬 Videos: MP4, AVI, MOV
📊 Presentations: PPT, PPTX

**Commands to try:**
• "Send message to everyone"
• "Share meeting notes"
• "Upload class material"''',

        'notes': '''📚 **Notes Sharing Platform:**

**Creating Notes:**
✅ Public notes (visible to all)
✅ Private notes (only you)
✅ File attachments (up to 50MB)
✅ Rich text content

**Supported Files:**
📖 Study materials & textbooks
🎥 Lecture recordings
📝 Assignment solutions  
📊 Project presentations

**Commands to try:**
• "Create private note"
• "Share lecture slides"
• "Download math notes"
• "View public notes"''',

        'teacher': '''👨‍🏫 **Teacher Directory:**

**Information Available:**
✅ Full contact details
✅ Department/Branch
✅ Email addresses
✅ Designation/Role

**Features:**
✅ Quick contact access
✅ Department filtering
✅ Search functionality
✅ Admin management

**Commands to try:**
• "Show CS department teachers"
• "Contact Dr. Smith"
• "Add new teacher"''',

        'student': '''👨‍🎓 **Student Management:**

**Admin Features:**
✅ Add new students
✅ Edit student information
✅ Manage roll numbers
✅ Track by branch/year

**Student Profiles:**
✅ Name, branch, year
✅ Unique roll numbers
✅ Attendance tracking
✅ Academic organization

**Commands to try:**
• "Add student to CS branch"
• "Edit student information"
• "View all students"''',

        'features': '''🚀 **CollegeCompanion Features:**

**Core Modules:**
1. **Attendance Tracking** - Digital attendance system
2. **Lost & Found** - Campus item recovery with image uploads
3. **Complaint Box** - Anonymous feedback system
4. **Communication** - Campus-wide messaging
5. **Notes Sharing** - Study material repository
6. **Teacher Directory** - Faculty contact management
7. **Student Management** - Student database

**Advanced Features:**
• File uploads (50MB limit)
• Image galleries for Lost & Found
• Role-based access control
• Real-time notifications
• Mobile-responsive design
• Secure authentication''',

        'commands': '''🎯 **Quick Commands List:**

**Attendance:**
"mark attendance", "view attendance", "add student"

**Lost & Found:**  
"post lost item with images", "browse found", "contact owner"

**Complaints:**
"submit complaint", "view complaints", "resolve issue", "delete complaint"

**Communication:**
"send message", "share file", "chat with everyone"

**Notes:**
"create note", "upload material", "download notes"

**Teachers:**
"show teachers", "contact faculty", "add teacher"

**Students:**
"add student", "edit profile", "view students"

**General:**
"help", "features", "what can you do"''',
        
        'admin': f'''👑 **Admin Privileges - {current_user.name}**

**Full System Access:**
✅ Student management (add/edit/delete)
✅ Teacher directory management  
✅ Attendance system control
✅ Complaint resolution & deletion
✅ Content moderation
✅ User management

**Special Capabilities:**
• Delete any message/note/complaint
• Resolve all complaints
• Access all system data
• Manage user accounts
• System configuration

**You have complete control over the CollegeCompanion platform!**''',

        'profile': f'''👤 **Your Profile - {current_user.name}**

**Role:** {current_user.role.title()}
**Branch:** {current_user.branch or 'Not specified'}
{"**Year:** " + str(current_user.year) if current_user.role == 'student' and current_user.year else ''}
**Phone:** {current_user.phone}

**Permissions:**
{'✅ Full administrative access' if current_user.role == 'admin' else ''}
{'✅ Attendance marking access' if current_user.role in ['admin', 'teacher'] else '✅ View attendance only'}
{'✅ Teacher features enabled' if current_user.role == 'teacher' else ''}
✅ Notes creation & sharing
✅ Communication access
✅ Lost & Found posting with image uploads
✅ Complaint submission & deletion'''
    }
    
    # Enhanced keyword matching with context
    if any(word in message for word in ['present', 'absent', 'mark attendance', 'attendance today']):
        return responses['attendance']
    elif any(word in message for word in ['upload', 'file', 'image', 'photo', 'picture']):
        return responses['upload']
    elif any(word in message for word in ['lost', 'found', 'item', 'missing', 'recover']):
        return responses['lost found']
    elif any(word in message for word in ['complain', 'issue', 'problem', 'report', 'delete complaint']):
        return responses['complaint']
    elif any(word in message for word in ['message', 'chat', 'talk', 'communicate', 'announce']):
        return responses['communication']
    elif any(word in message for word in ['study', 'material', 'note', 'file', 'upload', 'attachment', 'share notes']):
        return responses['notes']
    elif any(word in message for word in ['faculty', 'professor', 'teacher', 'instructor', 'lecturer']):
        return responses['teacher']
    elif any(word in message for word in ['pupil', 'learner', 'student', 'roll number', 'add student']):
        return responses['student']
    elif any(word in message for word in ['feature', 'function', 'capability', 'what can']):
        return responses['features']
    elif any(word in message for word in ['command', 'quick', 'shortcut', 'how to']):
        return responses['commands']
    elif any(word in message for word in ['admin', 'privilege', 'control', 'manage']):
        return responses['admin']
    elif any(word in message for word in ['profile', 'my info', 'who am i', 'my account']):
        return responses['profile']
    elif any(word in message for word in ['thank', 'thanks', 'appreciate']):
        return f"You're welcome, {current_user.name}! 😊 Is there anything else I can help you with?"
    elif any(word in message for word in ['bye', 'goodbye', 'see you', 'exit']):
        return f"Goodbye {current_user.name}! 👋 Have a great day at college!"
    
    # Check for partial matches in responses
    for key in responses:
        if key in message:
            return responses[key]
    
    # Smart fallback response
    return f"""I'm not sure I understand, {current_user.name}. 🤔

Try asking about:
• **Attendance** marking or viewing
• **Lost & Found** items with image uploads
• **Complaint** submission & deletion
• **Communication** with others
• **Notes** sharing
• **Teacher** information

Or type **'help'** for the complete guide!"""

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out successfully', 'info')
    return redirect(url_for('login'))

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    import os
    init_db()
    # Create uploads directory if it doesn't exist
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    # Use Render's dynamic port
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
