from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from models import db, User, Goal, GoalImage, SavingsTransaction
import os
import uuid
from PIL import Image

app = Flask(__name__)

app.config['SECRET_KEY'] = 'supersecretkey'  # change later!
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tammuh.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize db with app
db.init_app(app)

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def save_image(file, goal_id):
    if file and allowed_file(file.filename):
        # Generate unique filename
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        
        # Save and resize image
        image = Image.open(file)
        # Resize to max 800x600 while maintaining aspect ratio
        image.thumbnail((800, 600), Image.Resampling.LANCZOS)
        image.save(filepath, optimize=True, quality=85)
        
        return unique_filename
    return None

@app.route('/')
def home():
    return "Hello, Tamuuh!"

# ---------------- AUTHENTICATION ----------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()
        if user:
            flash('Email already exists.')
            return redirect(url_for('signup'))

        new_user = User(
            name=name,
            email=email,
            password=generate_password_hash(password, method='pbkdf2:sha256')
        )
        db.session.add(new_user)
        db.session.commit()
        flash('Account created! Please login.')
        return redirect(url_for('login'))

    return '''
    <form method="POST">
        Name: <input type="text" name="name"><br>
        Email: <input type="email" name="email"><br>
        Password: <input type="password" name="password"><br>
        <input type="submit" value="Sign Up">
    </form>
    '''

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password, password):
            flash('Invalid login.')
            return redirect(url_for('login'))

        login_user(user)
        return redirect(url_for('dashboard'))

    return '''
    <form method="POST">
        Email: <input type="email" name="email"><br>
        Password: <input type="password" name="password"><br>
        <input type="submit" value="Login">
    </form>
    '''

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

# ---------------- DASHBOARD ----------------
@app.route('/dashboard')
@login_required
def dashboard():
    goals = Goal.query.filter_by(user_id=current_user.id).all()
    
    # Calculate stats
    total_savings = sum(goal.saved_amount for goal in goals)
    active_goals = len(goals)
    this_month = sum(
        sum(t.amount for t in goal.transactions if t.transaction_date.month == 9)  # Current month
        for goal in goals
    )
    
    return render_template('dashboard.html', 
                         goals=goals,
                         total_savings=total_savings,
                         active_goals=active_goals,
                         this_month=this_month)

# ---------------- VISION BOARD ----------------
@app.route('/vision_board')
@login_required
def vision_board():
    goals = Goal.query.filter_by(user_id=current_user.id).all()
    return render_template('vision_board.html', goals=goals)

@app.route('/create_dream', methods=['POST'])
@login_required
def create_dream():
    try:
        title = request.form.get('title')
        target_amount = float(request.form.get('target_amount', 0))
        motivational_quote = request.form.get('motivational_quote', '').strip()
        description = request.form.get('description', '').strip()
        
        # Create the goal
        new_goal = Goal(
            title=title,
            target_amount=target_amount,
            motivational_quote=motivational_quote if motivational_quote else None,
            description=description if description else None,
            user_id=current_user.id
        )
        db.session.add(new_goal)
        db.session.flush()  # Get the goal ID
        
        # Handle image uploads (1-3 images)
        uploaded_files = request.files.getlist('images')
        image_count = 0
        
        for i, file in enumerate(uploaded_files):
            if image_count >= 3:  # Limit to 3 images
                break
                
            if file and file.filename:
                filename = save_image(file, new_goal.id)
                if filename:
                    goal_image = GoalImage(
                        goal_id=new_goal.id,
                        filename=filename,
                        original_filename=file.filename,
                        order=i
                    )
                    db.session.add(goal_image)
                    image_count += 1
        
        db.session.commit()
        flash('Dream created successfully!')
        
    except Exception as e:
        db.session.rollback()
        flash('Error creating dream. Please try again.')
        print(f"Error: {e}")
    
    return redirect(url_for('vision_board'))

@app.route('/add_money/<int:goal_id>', methods=['POST'])
@login_required
def add_money(goal_id):
    goal = Goal.query.get_or_404(goal_id)
    
    # Check if goal belongs to current user
    if goal.user_id != current_user.id:
        flash('Access denied.')
        return redirect(url_for('vision_board'))
    
    try:
        amount = float(request.form.get('amount', 0))
        note = request.form.get('note', '').strip()
        
        if amount <= 0:
            flash('Please enter a valid amount.')
            return redirect(url_for('vision_board'))
        
        # Add money to goal
        goal.saved_amount += amount
        
        # Create transaction record
        transaction = SavingsTransaction(
            goal_id=goal.id,
            amount=amount,
            note=note if note else None
        )
        db.session.add(transaction)
        db.session.commit()
        
        flash(f'Added £{amount:.2f} to {goal.title}!')
        
    except Exception as e:
        db.session.rollback()
        flash('Error adding money. Please try again.')
        print(f"Error: {e}")
    
    return redirect(url_for('vision_board'))

@app.route('/update_goal/<int:goal_id>', methods=['POST'])
@login_required
def update_goal(goal_id):
    goal = Goal.query.get_or_404(goal_id)
    
    # Check if goal belongs to current user
    if goal.user_id != current_user.id:
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        field = request.form.get('field')
        value = request.form.get('value', '').strip()
        
        if field == 'motivational_quote':
            goal.motivational_quote = value if value else None
        elif field == 'description':
            goal.description = value if value else None
        else:
            return jsonify({'error': 'Invalid field'}), 400
        
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Update failed'}), 500

@app.route('/delete_goal/<int:goal_id>', methods=['POST'])
@login_required
def delete_goal(goal_id):
    goal = Goal.query.get_or_404(goal_id)
    
    # Check if goal belongs to current user
    if goal.user_id != current_user.id:
        flash('Access denied.')
        return redirect(url_for('vision_board'))
    
    try:
        # Delete associated images from filesystem
        for image in goal.images:
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], image.filename)
            if os.path.exists(image_path):
                os.remove(image_path)
        
        # Delete goal (cascading will handle related records)
        db.session.delete(goal)
        db.session.commit()
        flash('Dream deleted successfully.')
        
    except Exception as e:
        db.session.rollback()
        flash('Error deleting dream.')
        print(f"Error: {e}")
    
    return redirect(url_for('vision_board'))

# --- Run the App ---
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)