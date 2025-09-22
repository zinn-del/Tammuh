from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

# User model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150))
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    goals = db.relationship('Goal', backref='user', lazy=True, cascade='all, delete-orphan')

# Enhanced Goal model with full vision board support
class Goal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    target_amount = db.Column(db.Float, nullable=False)
    saved_amount = db.Column(db.Float, default=0.0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Vision board fields
    motivational_quote = db.Column(db.Text)
    description = db.Column(db.Text)
    
    # Relationships
    images = db.relationship('GoalImage', backref='goal', lazy=True, cascade='all, delete-orphan')
    
    @property
    def progress_percentage(self):
        if self.target_amount <= 0:
            return 0
        return min((self.saved_amount / self.target_amount) * 100, 100)
    
    @property
    def remaining_amount(self):
        return max(self.target_amount - self.saved_amount, 0)

# Goal images model (1-3 images per goal)
class GoalImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    goal_id = db.Column(db.Integer, db.ForeignKey('goal.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255))
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    order = db.Column(db.Integer, default=0)  # For ordering images within a goal

# Savings transactions model (for tracking money additions)
class SavingsTransaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    goal_id = db.Column(db.Integer, db.ForeignKey('goal.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    transaction_date = db.Column(db.DateTime, default=datetime.utcnow)
    note = db.Column(db.String(200))
    
    # Relationship
    goal = db.relationship('Goal', backref='transactions')