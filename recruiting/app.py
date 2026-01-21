from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import os
import zipfile
import csv
import io
import threading
import time
from datetime import datetime, timedelta
from textblob import TextBlob
from dotenv import load_dotenv
from facebook_business import FacebookAdsApi
from facebook_business.adobjects.ad import Ad
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.campaign import Campaign
from facebook_business.adobjects.adset import AdSet
import requests
import secrets
import hashlib
import hmac
from functools import wraps
from sqlalchemy import text

load_dotenv()

app = Flask(__name__)

# Security Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_hex(32))
app.config['SESSION_COOKIE_SECURE'] = True  # HTTPS only
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent XSS
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection

# CORS Configuration - Restrict to your domain
CORS(app, origins=[
    'https://recruit.coloradocareassist.com',
    'https://tracker.coloradocareassist.com',
    'https://portal.coloradocareassist.com',
    'http://localhost:5000'  # For development
])

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.session_protection = "strong"

# Facebook API Configuration
FACEBOOK_APP_ID = os.getenv('FACEBOOK_APP_ID', '1826010391596353')
FACEBOOK_APP_SECRET = os.getenv('FACEBOOK_APP_SECRET')
FACEBOOK_ACCESS_TOKEN = os.getenv('FACEBOOK_ACCESS_TOKEN')
FACEBOOK_AD_ACCOUNT_ID = os.getenv('FACEBOOK_AD_ACCOUNT_ID', '2228418524061660')

# Initialize Facebook API
FacebookAdsApi.init(FACEBOOK_APP_ID, FACEBOOK_APP_SECRET, FACEBOOK_ACCESS_TOKEN)

# Database configuration
if os.getenv('DATABASE_URL'):
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL').replace('postgres://', 'postgresql://')
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///leads.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Flask-Login user loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Import portal auth middleware
from portal_auth_middleware import check_portal_auth, get_portal_user as get_portal_user_middleware

# Portal authentication check (now uses middleware)
# This function is kept for backward compatibility
def check_portal_auth_legacy():
    """Legacy function - use portal_auth_middleware.check_portal_auth() instead"""
    return check_portal_auth()

# Authentication decorator - uses portal auth middleware
def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # SECURITY: Verify request is from portal or has valid auth
        if not check_portal_auth():
            # Allow if in development mode with explicit bypass
            if os.getenv("ALLOW_UNAUTHENTICATED", "false").lower() == "true":
                return f(*args, **kwargs)
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated_function

# Admin-only decorator - uses portal auth middleware
def require_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # SECURITY: Verify request is from portal or has valid auth
        if not check_portal_auth():
            if os.getenv("ALLOW_UNAUTHENTICATED", "false").lower() == "true":
                return f(*args, **kwargs)
            return jsonify({"error": "Admin authentication required"}), 401
        return f(*args, **kwargs)
    return decorated_function

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    assigned_leads = db.relationship('Lead', backref='assigned_user', lazy=True)
    
    def get_id(self):
        return str(self.id)

class Lead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default='new')
    priority = db.Column(db.String(20), default='medium')
    # date_received = db.Column(db.DateTime, nullable=True)  # Will add back after fixing database
    assigned_to = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    source = db.Column(db.String(50), default='manual')
    facebook_lead_id = db.Column(db.String(64), unique=True, index=True)

class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('lead.id'), nullable=False)
    activity_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AlertRule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    condition = db.Column(db.String(100), nullable=False)
    recipients = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class FacebookCampaign(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    region = db.Column(db.String(50), nullable=False)  # 'denver_boulder' or 'colorado_springs_pueblo'
    status = db.Column(db.String(20), nullable=False)  # 'active', 'paused', 'deleted'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AdMetrics(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.String(50), nullable=False)
    date = db.Column(db.Date, nullable=False)
    spend = db.Column(db.Float, default=0.0)
    impressions = db.Column(db.Integer, default=0)
    clicks = db.Column(db.Integer, default=0)
    leads = db.Column(db.Integer, default=0)
    conversions = db.Column(db.Integer, default=0)
    cpa = db.Column(db.Float, default=0.0)  # Cost Per Acquisition
    roas = db.Column(db.Float, default=0.0)  # Return on Ad Spend
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def create_tables():
    """Create database tables and add default users"""
    db.create_all()
    
    # Add date_received column if it doesn't exist
    try:
        db.engine.execute(text("ALTER TABLE lead ADD COLUMN date_received TIMESTAMP"))
        print("Added date_received column to lead table")
    except Exception as e:
        print(f"Column date_received may already exist: {e}")
    
    # Add source column if it doesn't exist
    try:
        db.engine.execute(text("ALTER TABLE lead ADD COLUMN source VARCHAR(50) DEFAULT 'manual'"))
        print("Added source column to lead table")
    except Exception as e:
        print(f"Column source may already exist: {e}")

    # Add facebook_lead_id column if it doesn't exist
    try:
        db.engine.execute(text("ALTER TABLE lead ADD COLUMN facebook_lead_id VARCHAR(64)"))
        print("Added facebook_lead_id column to lead table")
        db.engine.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS lead_facebook_lead_id_idx ON lead(facebook_lead_id)"))
    except Exception as e:
        print(f"Column facebook_lead_id may already exist: {e}")
    
    # Add default users if they don't exist
    if User.query.count() == 0:
        default_users = [
            User(name='Israt Jahan', email='israt@colorcareassist.com'),
            User(name='Florisa Capones', email='florisa@coloradocareassist.com'),
            User(name='Cynthia Pointe', email='cynthia@coloradocareassist.com'),
            User(name='Jason Shulman', email='jason@coloradocareassist.com')
        ]
        
        for user in default_users:
            db.session.add(user)
        
        db.session.commit()
        print("Default users created!")
    
    # Add default alert rules
    if AlertRule.query.count() == 0:
        default_rule = AlertRule(
            name='High Priority Leads',
            condition='priority=high',
            recipients='israt@colorcareassist.com,florisa@coloradocareassist.com,cynthia@coloradocareassist.com,jason@coloradocareassist.com'
        )
        db.session.add(default_rule)
        db.session.commit()
        print("Default alert rules created!")

# Routes
@app.route('/')
def index():
    # No authentication required - portal handles auth
    # Just render the dashboard directly
    try:
        print("Rendering Recruiter Dashboard (no auth required)")
        
        # Show main dashboard
        return '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Caregiver Recruiter Dashboard</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                background: #0f172a;
                min-height: 100vh;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                color: #e2e8f0;
            }
            .main-container {
                background: #0f172a;
                margin: 0;
                padding: 16px;
                min-height: 100vh;
            }
            .header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 16px;
                padding-bottom: 12px;
                border-bottom: 1px solid #334155;
            }
            .header h1 {
                color: #f1f5f9;
                font-weight: 700;
                margin: 0;
                font-size: 1.5rem;
            }
            .header p {
                color: #94a3b8;
                margin: 2px 0 0 0;
                font-size: 0.8rem;
            }
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
                gap: 12px;
                margin-bottom: 16px;
            }
            .stat-card {
                background: #1e293b;
                border: 1px solid #334155;
                padding: 12px 16px;
                border-radius: 8px;
                text-align: center;
                transition: all 0.2s ease;
            }
            .stat-card:hover {
                border-color: #475569;
                transform: translateY(-1px);
            }
            .stat-number {
                font-size: 1.75rem;
                font-weight: 800;
                color: #f1f5f9;
                margin-bottom: 4px;
                line-height: 1.2;
            }
            .stat-label {
                font-size: 0.75rem;
                color: #94a3b8;
                font-weight: 500;
            }
            .leads-section {
                background: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 16px;
            }
            .section-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 12px;
            }
            .section-title {
                color: #f1f5f9;
                font-weight: 700;
                margin: 0;
                font-size: 1rem;
            }
            .upload-btn {
                background: #3b82f6;
                border: none;
                color: white;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 500;
                font-size: 0.8rem;
                transition: all 0.2s ease;
                cursor: pointer;
            }
            .upload-btn:hover {
                background: #2563eb;
                transform: translateY(-1px);
                color: white;
            }
            .leads-table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 8px;
                font-size: 0.8rem;
                color: #e2e8f0;
            }
            .leads-table th {
                background: #0f172a;
                padding: 8px 6px;
                text-align: left;
                font-weight: 600;
                color: #94a3b8;
                border-bottom: 1px solid #334155;
                font-size: 0.7rem;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                white-space: nowrap;
            }
            .leads-table th.date-col {
                min-width: 90px;
                width: 90px;
            }
            .leads-table th.name-col {
                min-width: 150px;
                max-width: 200px;
            }
            .leads-table th.email-col {
                min-width: 180px;
                max-width: 220px;
            }
            .leads-table th.phone-col {
                min-width: 140px;
                max-width: 160px;
            }
            .leads-table th.status-col {
                min-width: 110px;
                max-width: 130px;
            }
            .leads-table th.notes-col {
                min-width: 200px;
                max-width: 300px;
            }
            .leads-table th {
                cursor: pointer;
                user-select: none;
                position: relative;
            }
            .leads-table th:hover {
                background: #1e293b;
            }
            .leads-table th.sortable::after {
                content: ' ↕';
                opacity: 0.5;
                font-size: 0.8em;
            }
            .leads-table th.sort-asc::after {
                content: ' ↑';
                opacity: 1;
            }
            .leads-table th.sort-desc::after {
                content: ' ↓';
                opacity: 1;
            }
            .leads-table td {
                padding: 6px 6px;
                border-bottom: 1px solid #334155;
                vertical-align: middle;
                font-size: 0.8rem;
                line-height: 1.4;
            }
            .leads-table td.date-col {
                min-width: 90px;
                width: 90px;
                white-space: nowrap;
                font-size: 0.75rem;
            }
            .leads-table td.name-col {
                min-width: 150px;
                max-width: 200px;
                font-weight: 500;
            }
            .leads-table td.email-col {
                min-width: 180px;
                max-width: 220px;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }
            .leads-table td.phone-col {
                min-width: 140px;
                max-width: 160px;
                white-space: nowrap;
            }
            .leads-table td.status-col {
                min-width: 110px;
                max-width: 130px;
            }
            .phone-actions {
                display: inline-flex;
                gap: 6px;
                align-items: center;
            }
            .phone-icon, .text-icon, .email-icon, .goformz-icon {
                cursor: pointer;
                color: #3b82f6;
                font-size: 0.9rem;
                transition: color 0.2s;
            }
            .phone-icon:hover {
                color: #10b981;
            }
            .text-icon:hover {
                color: #06b6d4;
            }
            .goformz-icon {
                color: #f59e0b;
            }
            .goformz-icon:hover {
                color: #d97706;
            }
            .email-icon:hover {
                color: #8b5cf6;
            }
            .leads-table tr:hover {
                background: #334155;
            }
            .leads-table tr.wants-work {
                background-color: rgba(16, 185, 129, 0.15);
                border-left: 4px solid #10b981;
            }
            .leads-table tr.current-caregiver {
                background-color: rgba(16, 185, 129, 0.15);
                border-left: 4px solid #10b981;
            }
            .leads-table tr.rejected {
                background-color: rgba(239, 68, 68, 0.15);
                border-left: 4px solid #ef4444;
            }
            .form-select-sm {
                padding: 4px 8px;
                font-size: 0.75rem;
                border-radius: 4px;
                border: 1px solid #334155;
                background: #0f172a;
                color: #e2e8f0;
                min-width: 100px;
            }
            .form-select-sm:focus {
                outline: none;
                border-color: #3b82f6;
                box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
            }
            .notes-display {
                cursor: pointer;
                padding: 4px 6px;
                border-radius: 4px;
                transition: background 0.2s;
                color: #cbd5e1;
                font-size: 0.75rem;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                max-width: 300px;
            }
            .notes-display:hover {
                background: #334155;
            }
            .notes-display.editing {
                display: none !important;
            }
            .notes-textarea {
                display: none;
                width: 100%;
                min-height: 60px;
                padding: 6px;
                background: #1e293b;
                border: 2px solid #3b82f6;
                border-radius: 4px;
                color: #f1f5f9;
                font-family: inherit;
                font-size: 0.75rem;
                resize: vertical;
            }
            .notes-textarea.active {
                display: block !important;
            }
            .notes-textarea:focus {
                outline: none;
                border-color: #3b82f6;
                box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
            }
            /* Compact table row height */
            .leads-table tr {
                height: auto;
                min-height: 36px;
            }
            .leads-table td {
                max-height: 48px;
                overflow: hidden;
            }
            .leads-table td.notes-col {
                max-height: none;
                overflow: visible !important;
                position: relative;
            }
            .notes-textarea {
                width: 100%;
                min-height: 50px;
                padding: 8px;
                border: 1px solid #334155;
                border-radius: 4px;
                font-size: 0.8rem;
                background: #0f172a;
                color: #e2e8f0;
                font-family: inherit;
            }
            .notes-textarea:focus {
                outline: none;
                border-color: #3b82f6;
                box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);
            }
            .notes-col {
                max-width: 300px;
                position: relative;
            }
            .metric-card {
                background: #f8f9fa;
                border-radius: 8px;
                padding: 15px;
                text-align: center;
                margin-bottom: 10px;
            }
            .metric-value {
                font-size: 1.5rem;
                font-weight: bold;
                color: #007bff;
            }
            .metric-label {
                font-size: 0.85rem;
                color: #6c757d;
                margin-top: 5px;
            }
            .campaign-item {
                background: #f8f9fa;
                border-radius: 6px;
                padding: 10px;
                margin-bottom: 8px;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .campaign-status {
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 0.8rem;
                font-weight: bold;
            }
            .status-active {
                background: #d4edda;
                color: #155724;
            }
            .status-paused {
                background: #fff3cd;
                color: #856404;
            }
            .btn-primary {
                background: #3b82f6;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: 500;
                color: white;
                cursor: pointer;
                transition: all 0.2s ease;
            }
            .btn-primary:hover {
                background: #2563eb;
                transform: translateY(-1px);
            }
            .loading {
                text-align: center;
                padding: 40px;
                color: #94a3b8;
            }
            .form-select {
                background: #0f172a;
                border: 1px solid #334155;
                color: #e2e8f0;
                padding: 8px 12px;
                border-radius: 6px;
            }
            .form-select:focus {
                outline: none;
                border-color: #3b82f6;
                box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
            }
            .form-select option {
                background: #1e293b;
                color: #e2e8f0;
            }
            .spinner {
                display: inline-block;
                width: 20px;
                height: 20px;
                border: 3px solid #f3f3f3;
                border-top: 3px solid #667eea;
                border-radius: 50%;
                animation: spin 1s linear infinite;
            }
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            .modal-overlay {
                display: none;
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.7);
                z-index: 1000;
                align-items: center;
                justify-content: center;
            }
            .modal-overlay.show {
                display: flex;
            }
            .custom-modal {
                background: #1e293b;
                border: 1px solid #334155;
                border-radius: 12px;
                padding: 24px;
                min-width: 400px;
                max-width: 500px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.5);
                animation: slideIn 0.3s ease;
            }
            @keyframes slideIn {
                from {
                    opacity: 0;
                    transform: translateY(-20px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
            .modal-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 20px;
                padding-bottom: 16px;
                border-bottom: 1px solid #334155;
            }
            .modal-title {
                font-size: 1.25rem;
                font-weight: 700;
                color: #f1f5f9;
                margin: 0;
            }
            .modal-close {
                background: none;
                border: none;
                font-size: 1.5rem;
                color: #64748b;
                cursor: pointer;
                padding: 0;
                width: 30px;
                height: 30px;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: color 0.2s;
            }
            .modal-close:hover {
                color: #e2e8f0;
            }
            .modal-body {
                margin-bottom: 20px;
            }
            .form-group {
                margin-bottom: 16px;
            }
            .form-label {
                display: block;
                margin-bottom: 8px;
                font-weight: 500;
                color: #94a3b8;
                font-size: 0.875rem;
            }
            .form-control {
                width: 100%;
                padding: 10px 12px;
                border: 1px solid #334155;
                border-radius: 6px;
                font-size: 0.9rem;
                box-sizing: border-box;
                background: #0f172a;
                color: #e2e8f0;
            }
            .form-control::placeholder {
                color: #64748b;
            }
            .form-control:focus {
                outline: none;
                border-color: #3b82f6;
                box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
            }
            .modal-footer {
                display: flex;
                justify-content: flex-end;
                gap: 10px;
            }
            .btn-secondary {
                background: #475569;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                cursor: pointer;
                font-size: 0.875rem;
                font-weight: 500;
                transition: all 0.2s ease;
            }
            .btn-secondary:hover {
                background: #334155;
                transform: translateY(-1px);
            }
            .btn-success {
                background: #10b981;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                cursor: pointer;
                font-size: 0.875rem;
                font-weight: 500;
                transition: all 0.2s ease;
            }
            .btn-success:hover {
                background: #059669;
                transform: translateY(-1px);
            }
            .btn-outline-danger {
                background: transparent;
                color: #ef4444;
                border: 1px solid #ef4444;
                padding: 10px 20px;
                border-radius: 8px;
                cursor: pointer;
                font-size: 0.875rem;
                font-weight: 500;
                transition: all 0.2s ease;
                text-decoration: none;
                display: inline-block;
            }
            .btn-outline-danger:hover {
                background: #ef4444;
                color: white;
                transform: translateY(-1px);
            }
            textarea.form-control {
                min-height: 100px;
                resize: vertical;
            }
        </style>
    </head>
    <body>
        <div class="main-container">
            <div class="header">
                <div>
                    <h1><i class="fas fa-users"></i> Caregiver Recruiter Dashboard</h1>
                    <p>Manage your lead pipeline and track recruitment success</p>
                </div>
                <div class="d-flex gap-2">
                    <button class="btn upload-btn" id="addLeadBtn">
                        <i class="fas fa-plus"></i> Add Lead
                    </button>
                    <button class="btn upload-btn" id="uploadBtn">
                        <i class="fas fa-upload"></i> Upload New Leads
                    </button>
                    <a href="/logout" class="btn btn-outline-danger">
                        <i class="fas fa-sign-out-alt"></i> Logout
                    </a>
                </div>
            </div>

            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number" id="totalLeads">0</div>
                    <div class="stat-label">Total Leads</div>
                    <div class="stat-cost" id="totalLeadsCost" style="font-size: 0.8em; opacity: 0.8; margin-top: 4px;">$0.00 per lead</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="newLeads">0</div>
                    <div class="stat-label">New Leads (Today)</div>
                    <div class="stat-cost" id="newLeadsCost" style="font-size: 0.8em; opacity: 0.8; margin-top: 4px;">$0.00 per lead</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="contactedLeads">0</div>
                    <div class="stat-label">Contacted</div>
                    <div class="stat-cost" id="contactedLeadsCost" style="font-size: 0.8em; opacity: 0.8; margin-top: 4px;">$0.00 per contact</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="wantsWorkLeads">0</div>
                    <div class="stat-label">Wants Work</div>
                    <div class="stat-cost" id="wantsWorkLeadsCost" style="font-size: 0.8em; opacity: 0.8; margin-top: 4px;">$0.00 per candidate</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="currentCaregivers">0</div>
                    <div class="stat-label">Current Caregivers</div>
                    <div class="stat-cost" id="currentCaregiversCost" style="font-size: 0.8em; opacity: 0.8; margin-top: 4px;">$0.00 per hire</div>
                </div>
            </div>

            <div class="leads-section">
                <div class="section-header">
                    <h2 class="section-title"><i class="fas fa-list"></i> All Leads</h2>
                    <div style="display: flex; gap: 10px; align-items: center;">
                        <input 
                            type="text" 
                            id="searchInput" 
                            class="form-control" 
                            placeholder="Search by name, email, or phone..." 
                            onkeyup="filterLeads()"
                            style="width: 300px;"
                        />
                        <select class="form-select" id="statusFilter" onchange="filterLeads()" style="width: auto;">
                            <option value="">All Status</option>
                            <option value="new">New</option>
                            <option value="contacted">Contacted</option>
                            <option value="interested">Interested</option>
                            <option value="hired">Hired</option>
                            <option value="not_interested">Not Interested</option>
                        </select>
                        <button class="btn btn-primary" id="refreshBtn">
                            <i class="fas fa-sync"></i> Refresh
                        </button>
                    </div>
                </div>
                
                <div id="leadsContainer" class="loading">
                    <div class="spinner"></div>
                    <div>Loading leads...</div>
                </div>
                
                <div id="paginationContainer" style="display: none;">
                    <nav>
                        <ul id="pagination" class="pagination justify-content-center mt-4"></ul>
                    </nav>
                </div>
            </div>
        </div>


        <!-- Text Message Modal -->
        <div class="modal-overlay" id="textModalOverlay" onclick="if(event.target === this) closeTextModal()">
            <div class="custom-modal" onclick="event.stopPropagation()">
                <div class="modal-header">
                    <h3 class="modal-title">Send Text Message</h3>
                    <button class="modal-close" onclick="closeTextModal()">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="form-group">
                        <label class="form-label">To:</label>
                        <div id="textRecipientInfo" style="padding: 12px; background: #0f172a; border: 1px solid #334155; border-radius: 6px; font-weight: 600; color: #f1f5f9; font-size: 1rem;"></div>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Message:</label>
                        <textarea class="form-control" id="textMessageInput" placeholder="Enter your message here..." onkeydown="if(event.key === 'Enter' && event.ctrlKey) sendTextFromModal()"></textarea>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn-secondary" onclick="closeTextModal()">Cancel</button>
                    <button class="btn-success" onclick="sendTextFromModal()">
                        <i class="fas fa-paper-plane"></i> Send
                    </button>
                </div>
            </div>
        </div>

        <!-- Add Lead Modal -->
        <div class="modal-overlay" id="addLeadModalOverlay" onclick="if(event.target === this) closeAddLeadModal()">
            <div class="custom-modal" onclick="event.stopPropagation()">
                <div class="modal-header">
                    <h3 class="modal-title">Add New Lead</h3>
                    <button class="modal-close" onclick="closeAddLeadModal()">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="form-group">
                        <label class="form-label">Name *</label>
                        <input type="text" class="form-control" id="addLeadName" placeholder="Full name" required>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Phone *</label>
                        <input type="tel" class="form-control" id="addLeadPhone" placeholder="+17191234567" required>
                    </div>
                    <div class="form-group">
                        <label class="form-label">Email</label>
                        <input type="email" class="form-control" id="addLeadEmail" placeholder="email@example.com">
                    </div>
                    <div class="form-group">
                        <label class="form-label">Notes</label>
                        <textarea class="form-control" id="addLeadNotes" placeholder="Optional notes"></textarea>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn-secondary" onclick="closeAddLeadModal()">Cancel</button>
                    <button class="btn-success" onclick="saveNewLead()">
                        <i class="fas fa-save"></i> Add Lead
                    </button>
                </div>
            </div>
        </div>

        <!-- Upload Modal -->
        <div class="modal fade" id="uploadModal" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Upload New Leads</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div id="uploadArea" style="border: 2px dashed #667eea; border-radius: 10px; padding: 40px; text-align: center; background: rgba(102, 126, 234, 0.05);">
                            <div style="font-size: 3rem; color: #667eea; margin-bottom: 20px;">
                                <i class="fas fa-cloud-upload-alt"></i>
                            </div>
                            <h6>Upload Facebook Ads Leads</h6>
                            <p>Drag and drop your CSV files here or click to browse</p>
                            <input type="file" id="fileInput" accept=".csv,.zip" style="display: none;">
                            <button class="btn btn-primary" id="fileSelectBtn">
                                <i class="fas fa-upload"></i> Choose File
                            </button>
                        </div>
                        <div id="uploadStatus" class="mt-3" style="display: none;"></div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Facebook Campaign Controls -->
        <div class="container mt-4">
            <div class="row">
                <div class="col-12">
                    <div class="card">
                        <div class="card-header">
                            <h5 class="mb-0">
                                <i class="fab fa-facebook"></i> Facebook Campaign Management
                            </h5>
                        </div>
                        <div class="card-body">
                            <div class="row">
                                <div class="col-md-6">
                                    <h6>Campaign Controls</h6>
                                    <div class="d-flex gap-2 flex-wrap mb-2">
                                        <button class="btn btn-outline-primary btn-sm" id="syncCampaignsBtn">
                                            <i class="fas fa-sync"></i> Sync Campaigns
                                        </button>
                                        <button class="btn btn-outline-success btn-sm" id="refreshMetricsBtn">
                                            <i class="fas fa-chart-line"></i> Refresh Metrics
                                        </button>
                                        <button class="btn btn-outline-warning btn-sm" id="pullLeadsBtn">
                                            <i class="fas fa-cloud-download-alt"></i> Pull Leads
                                        </button>
                                    </div>
                                    <div class="text-muted small mb-3" id="pullLeadsStatus">
                                        Connects to Facebook Lead Ads and drops new submissions into the board.
                                    </div>
                                    <div id="campaignsList" class="mb-3">
                                        <div class="text-muted">Loading campaigns...</div>
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <h6>Campaign Metrics</h6>
                                    <div class="btn-group mb-3" role="group">
                                        <input type="radio" class="btn-check" name="timePeriod" id="last7days" value="7" checked>
                                        <label class="btn btn-outline-primary btn-sm" for="last7days" onclick="document.getElementById('last7days').checked = true; document.getElementById('last7days').dispatchEvent(new Event('change'));">Last 7 Days</label>
                                        
                                        <input type="radio" class="btn-check" name="timePeriod" id="alltime" value="all">
                                        <label class="btn btn-outline-primary btn-sm" for="alltime" onclick="document.getElementById('alltime').checked = true; document.getElementById('alltime').dispatchEvent(new Event('change'));">All Time</label>
                                    </div>
                                    <div id="campaignMetrics" class="row">
                                        <div class="col-6">
                                            <div class="metric-card">
                                                <div class="metric-value" id="totalSpend">$0</div>
                                                <div class="metric-label">Total Spend</div>
                                            </div>
                                        </div>
                                        <div class="col-6">
                                            <div class="metric-card">
                                                <div class="metric-value" id="facebookLeads">0</div>
                                                <div class="metric-label">Facebook Leads</div>
                                            </div>
                                        </div>
                                        <div class="col-6">
                                            <div class="metric-card">
                                                <div class="metric-value" id="avgCPA">$0</div>
                                                <div class="metric-label">Avg CPA</div>
                                            </div>
                                        </div>
                                        <div class="col-6">
                                            <div class="metric-card">
                                                <div class="metric-value" id="avgROAS">0%</div>
                                                <div class="metric-label">Avg ROAS</div>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            let currentPage = 1;
            let currentFilter = '';
            let selectedTimePeriod = 7; // Track selected time period
            let usersList = []; // Store users for dropdown
            
            // Load users first
            function loadUsers() {
                return fetch('/recruiting/api/users', {
                    credentials: 'include'
                })
                    .then(response => response.json())
                    .then(users => {
                        usersList = users;
                        console.log('Loaded users:', usersList);
                        return users;
                    })
                    .catch(error => {
                        console.error('Error loading users:', error);
                        return [];
                    });
            }
            
            // Load initial data
            loadUsers();
            loadStats();
            loadLeads();
            loadFacebookCampaigns();
            
            // Add Lead button
            document.getElementById('addLeadBtn').addEventListener('click', function() {
                document.getElementById('addLeadModalOverlay').classList.add('show');
                document.getElementById('addLeadName').focus();
            });

            function closeAddLeadModal() {
                document.getElementById('addLeadModalOverlay').classList.remove('show');
                // Clear form
                document.getElementById('addLeadName').value = '';
                document.getElementById('addLeadPhone').value = '';
                document.getElementById('addLeadEmail').value = '';
                document.getElementById('addLeadNotes').value = '';
            }

            function saveNewLead() {
                const name = document.getElementById('addLeadName').value.trim();
                const phone = document.getElementById('addLeadPhone').value.trim();
                const email = document.getElementById('addLeadEmail').value.trim();
                const notes = document.getElementById('addLeadNotes').value.trim();

                if (!name || !phone) {
                    alert('Name and Phone are required');
                    return;
                }

                fetch('/recruiting/api/leads', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    credentials: 'include',
                    body: JSON.stringify({
                        name: name,
                        phone: phone,
                        email: email || '',
                        notes: notes || '',
                        status: 'new',
                        priority: 'medium'
                    })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        closeAddLeadModal();
                        loadStats();
                        loadLeads();
                        
                        // Show success message
                        const successMsg = document.createElement('div');
                        successMsg.className = 'alert alert-success';
                        successMsg.style.position = 'fixed';
                        successMsg.style.top = '20px';
                        successMsg.style.right = '20px';
                        successMsg.style.zIndex = '2000';
                        successMsg.style.padding = '12px 20px';
                        successMsg.style.borderRadius = '8px';
                        successMsg.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
                        successMsg.innerHTML = '<i class="fas fa-check-circle"></i> Lead added successfully!';
                        document.body.appendChild(successMsg);
                        
                        setTimeout(() => {
                            successMsg.remove();
                        }, 3000);
                    } else {
                        alert('Error adding lead: ' + (data.error || 'Unknown error'));
                    }
                })
                .catch(error => {
                    console.error('Error adding lead:', error);
                    alert('Error adding lead: ' + error.message);
                });
            }

            // File upload handling
            document.getElementById('fileInput').addEventListener('change', handleFileUpload);
            
            // Facebook button event listeners
            document.getElementById('syncCampaignsBtn').addEventListener('click', syncFacebookCampaigns);
            document.getElementById('refreshMetricsBtn').addEventListener('click', refreshCampaignMetrics);
            const pullLeadsBtn = document.getElementById('pullLeadsBtn');
            if (pullLeadsBtn) {
                pullLeadsBtn.addEventListener('click', pullFacebookLeads);
            }
            
            
            // Function to set up time period toggle event listeners
            function setupTimePeriodListeners() {
                const radios = document.querySelectorAll('input[name="timePeriod"]');
                console.log('Found', radios.length, 'time period radio buttons');
                
                radios.forEach(radio => {
                    console.log('Setting up event listener for radio:', radio.value);
                    radio.addEventListener('change', function() {
                        console.log('Time period changed to:', this.value);
                        if (this.checked) {
                            // Update the global time period variable
                            selectedTimePeriod = this.value === 'all' ? 365 : parseInt(this.value);
                            console.log('Updated selectedTimePeriod to:', selectedTimePeriod);
                            
                            // Refresh metrics with new time period immediately
                            console.log('Refreshing metrics with selectedTimePeriod:', selectedTimePeriod);
                            fetch('/api/facebook/campaigns')
                                .then(response => response.json())
                                .then(campaigns => {
                                    console.log('Loading metrics with time period:', selectedTimePeriod);
                                    loadCampaignMetrics(campaigns, selectedTimePeriod);
                                })
                                .catch(error => console.error('Error loading metrics:', error));
                        }
                    });
                });
            }
            
            // Set up time period listeners immediately and also after page loads
            setupTimePeriodListeners();
            document.addEventListener('DOMContentLoaded', setupTimePeriodListeners);
            
            // Other button event listeners
            document.getElementById('uploadBtn').addEventListener('click', showUploadModal);
            document.getElementById('refreshBtn').addEventListener('click', function() { loadLeads(); });
            document.getElementById('fileSelectBtn').addEventListener('click', function() { 
                document.getElementById('fileInput').click(); 
            });
            
            // Drag and drop
            const uploadArea = document.getElementById('uploadArea');
            uploadArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadArea.style.background = 'rgba(102, 126, 234, 0.2)';
            });
            
            uploadArea.addEventListener('dragleave', (e) => {
                e.preventDefault();
                uploadArea.style.background = 'rgba(102, 126, 234, 0.05)';
            });
            
            uploadArea.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadArea.style.background = 'rgba(102, 126, 234, 0.05)';
                const files = e.dataTransfer.files;
                if (files.length > 0) {
                    uploadFile(files[0]);
                }
            });

            function showUploadModal() {
                const modal = new bootstrap.Modal(document.getElementById('uploadModal'));
                modal.show();
            }

            function handleFileUpload(event) {
                const file = event.target.files[0];
                if (file) {
                    uploadFile(file);
                }
            }

            function uploadFile(file) {
                const formData = new FormData();
                formData.append('file', file);
                
                const statusDiv = document.getElementById('uploadStatus');
                statusDiv.style.display = 'block';
                statusDiv.innerHTML = '<div class="alert alert-info"><i class="fas fa-spinner fa-spin"></i> Uploading...</div>';
                
                fetch('/recruiting/api/leads/upload', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        const successDiv = document.createElement('div');
                        successDiv.className = 'alert alert-success';
                        const icon = document.createElement('i');
                        icon.className = 'fas fa-check';
                        successDiv.appendChild(icon);
                        successDiv.appendChild(document.createTextNode(' Successfully uploaded ' + data.leads_added + ' leads!'));
                        statusDiv.innerHTML = '';
                        statusDiv.appendChild(successDiv);
                        loadStats();
                        loadLeads();
                        setTimeout(() => {
                            const modal = bootstrap.Modal.getInstance(document.getElementById('uploadModal'));
                            modal.hide();
                        }, 2000);
                    } else {
                        const errorDiv = document.createElement('div');
                        errorDiv.className = 'alert alert-danger';
                        const icon = document.createElement('i');
                        icon.className = 'fas fa-exclamation-triangle';
                        errorDiv.appendChild(icon);
                        errorDiv.appendChild(document.createTextNode(' Error: ' + data.error));
                        statusDiv.innerHTML = '';
                        statusDiv.appendChild(errorDiv);
                    }
                })
                .catch(error => {
                    const errorDiv = document.createElement('div');
                    errorDiv.className = 'alert alert-danger';
                    const icon = document.createElement('i');
                    icon.className = 'fas fa-exclamation-triangle';
                    errorDiv.appendChild(icon);
                    errorDiv.appendChild(document.createTextNode(' Upload failed: ' + error.message));
                    statusDiv.innerHTML = '';
                    statusDiv.appendChild(errorDiv);
                });
            }

            function loadStats() {
                fetch('/recruiting/api/stats')
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('totalLeads').textContent = data.total_leads;
                        document.getElementById('newLeads').textContent = data.new_leads;
                        document.getElementById('contactedLeads').textContent = data.contacted_leads;
                        document.getElementById('wantsWorkLeads').textContent = data.wants_work_leads;
                        document.getElementById('currentCaregivers').textContent = data.current_caregivers;
                        
                        // Calculate and update cost per metrics using all-time spend
                        updateCostPerMetrics(data);
                    })
                    .catch(error => console.error('Error loading stats:', error));
            }
            
            function updateCostPerMetrics(statsData) {
                // Get all-time spend from Facebook campaigns
                fetch('/recruiting/api/facebook/campaigns')
                    .then(response => response.json())
                    .then(campaigns => {
                        let totalSpend = 0;
                        const promises = campaigns.map(campaign => {
                            return fetch('/recruiting/api/facebook/campaigns/' + campaign.campaign_id + '/metrics')
                                .then(response => response.json())
                                .then(metrics => {
                                    if (metrics && metrics.spend !== undefined) {
                                        totalSpend += metrics.spend;
                                    }
                                })
                                .catch(error => console.error('Error loading campaign metrics:', error));
                        });
                        
                        Promise.all(promises).then(() => {
                            // Calculate cost per metrics
                            const totalLeadsCost = statsData.total_leads > 0 ? (totalSpend / statsData.total_leads) : 0;
                            const newLeadsCost = statsData.new_leads > 0 ? (totalSpend / statsData.new_leads) : 0;
                            const contactedLeadsCost = statsData.contacted_leads > 0 ? (totalSpend / statsData.contacted_leads) : 0;
                            const wantsWorkLeadsCost = statsData.wants_work_leads > 0 ? (totalSpend / statsData.wants_work_leads) : 0;
                            const currentCaregiversCost = statsData.current_caregivers > 0 ? (totalSpend / statsData.current_caregivers) : 0;
                            
                            // Update cost per displays
                            document.getElementById('totalLeadsCost').textContent = '$' + totalLeadsCost.toFixed(2) + ' per lead';
                            document.getElementById('newLeadsCost').textContent = '$' + newLeadsCost.toFixed(2) + ' per lead';
                            document.getElementById('contactedLeadsCost').textContent = '$' + contactedLeadsCost.toFixed(2) + ' per contact';
                            document.getElementById('wantsWorkLeadsCost').textContent = '$' + wantsWorkLeadsCost.toFixed(2) + ' per candidate';
                            document.getElementById('currentCaregiversCost').textContent = '$' + currentCaregiversCost.toFixed(2) + ' per hire';
                        });
                    })
                    .catch(error => console.error('Error loading Facebook campaigns:', error));
            }

            function loadLeads() {
                const url = '/recruiting/api/leads?page=' + currentPage + '&per_page=100' + (currentFilter ? '&status=' + currentFilter : '');
                
                fetch(url, {
                    credentials: 'include'
                })
                    .then(response => response.json())
                    .then(data => {
                        // Ensure users are loaded before displaying leads
                        if (usersList.length === 0) {
                            loadUsers().then(() => {
                                displayLeads(data.leads, currentSortColumn, currentSortDirection);
                                updatePagination(data.pages, data.current_page);
                            });
                        } else {
                            displayLeads(data.leads, currentSortColumn, currentSortDirection);
                            updatePagination(data.pages, data.current_page);
                        }
                    })
                    .catch(error => console.error('Error loading leads:', error));
            }

            let currentSortColumn = null;
            let currentSortDirection = 'asc';

            function sortLeads(leads, column, direction) {
                const sortedLeads = [...leads];
                
                sortedLeads.sort((a, b) => {
                    let aVal, bVal;
                    
                    switch(column) {
                        case 'Date':
                            // Extract date from notes
                            aVal = '';
                            bVal = '';
                            if (a.notes && a.notes.includes('Date:')) {
                                const match = a.notes.match(/Date: ([^|]+)/);
                                if (match) aVal = match[1].trim();
                            }
                            if (b.notes && b.notes.includes('Date:')) {
                                const match = b.notes.match(/Date: ([^|]+)/);
                                if (match) bVal = match[1].trim();
                            }
                            // Parse MM/DD/YYYY format
                            if (aVal && bVal) {
                                const aParts = aVal.split('/');
                                const bParts = bVal.split('/');
                                if (aParts.length === 3 && bParts.length === 3) {
                                    aVal = new Date(aParts[2], aParts[0] - 1, aParts[1]);
                                    bVal = new Date(bParts[2], bParts[0] - 1, bParts[1]);
                                }
                            }
                            break;
                        case 'Name':
                            aVal = (a.name || '').toLowerCase();
                            bVal = (b.name || '').toLowerCase();
                            break;
                        case 'Email':
                            aVal = (a.email || '').toLowerCase();
                            bVal = (b.email || '').toLowerCase();
                            break;
                        case 'Phone':
                            aVal = (a.phone || '').toLowerCase();
                            bVal = (b.phone || '').toLowerCase();
                            break;
                        case 'Status':
                            aVal = (a.status || '').toLowerCase();
                            bVal = (b.status || '').toLowerCase();
                            break;
                        case 'Notes':
                            aVal = (a.notes || '').toLowerCase();
                            bVal = (b.notes || '').toLowerCase();
                            break;
                        default:
                            return 0;
                    }
                    
                    if (aVal < bVal) return direction === 'asc' ? -1 : 1;
                    if (aVal > bVal) return direction === 'asc' ? 1 : -1;
                    return 0;
                });
                
                return sortedLeads;
            }

            function handleSort(column) {
                if (currentSortColumn === column) {
                    // Toggle direction
                    currentSortDirection = currentSortDirection === 'asc' ? 'desc' : 'asc';
                } else {
                    currentSortColumn = column;
                    currentSortDirection = 'asc';
                }
                
                // Reload and display leads with sorting
                const url = '/recruiting/api/leads?page=' + currentPage + '&per_page=100' + (currentFilter ? '&status=' + currentFilter : '');
                
                fetch(url, {
                    credentials: 'include'
                })
                    .then(response => response.json())
                    .then(data => {
                        const sortedLeads = sortLeads(data.leads, currentSortColumn, currentSortDirection);
                        displayLeads(sortedLeads, currentSortColumn, currentSortDirection);
                        updatePagination(data.pages, data.current_page);
                    })
                    .catch(error => console.error('Error loading leads:', error));
            }

            function displayLeads(leads, sortColumn = null, sortDirection = 'asc') {
                const container = document.getElementById('leadsContainer');
                
                if (leads.length === 0) {
                    container.innerHTML = '<div class="text-center py-4 text-muted">No leads found</div>';
                    return;
                }
                
                // Sort if needed
                if (sortColumn) {
                    leads = sortLeads(leads, sortColumn, sortDirection);
                } else {
                    // Default: reverse order so newest leads appear first
                    leads.reverse();
                }
                
                // Apply search filter
                const searchTerm = document.getElementById('searchInput').value;
                leads = searchLeads(leads, searchTerm);
                
                // Show message if no results
                if (leads.length === 0 && searchTerm) {
                    container.innerHTML = '<div style="text-align: center; padding: 40px; color: #94a3b8;">No leads found matching "' + searchTerm + '"</div>';
                    return;
                }
                
                // Create table element
                const table = document.createElement('table');
                table.className = 'leads-table';
                
                // Create table header
                const thead = document.createElement('thead');
                const headerRow = document.createElement('tr');
                const headers = [
                    { text: 'Date', class: 'date-col' },
                    { text: 'Name', class: 'name-col' },
                    { text: 'Email', class: 'email-col' },
                    { text: 'Phone', class: 'phone-col' },
                    { text: 'Status', class: 'status-col' },
                    { text: 'Notes', class: 'notes-col' }
                ];
                headers.forEach(header => {
                    const th = document.createElement('th');
                    th.textContent = header.text;
                    th.className = 'sortable ' + header.class;
                    if (sortColumn === header.text) {
                        th.className += sortDirection === 'asc' ? ' sort-asc' : ' sort-desc';
                    }
                    th.addEventListener('click', () => handleSort(header.text));
                    headerRow.appendChild(th);
                });
                thead.appendChild(headerRow);
                table.appendChild(thead);
                
                // Create table body
                const tbody = document.createElement('tbody');
                
                leads.forEach(lead => {
                    const assignedName = lead.assigned_to || 'Unassigned';
                    const notes = lead.notes || 'Click to add notes';
                    
                    // Determine row class based on status and notes
                    let rowClass = '';
                    if (lead.status === 'hired') {
                        rowClass = 'current-caregiver';
                    } else if (lead.status === 'not_interested') {
                        rowClass = 'rejected';
                    } else if (notes.toLowerCase().includes('sent application') || 
                               notes.toLowerCase().includes('ft') || 
                               notes.toLowerCase().includes('pt') || 
                               notes.toLowerCase().includes('cna') || 
                               notes.toLowerCase().includes('qmap')) {
                        rowClass = 'wants-work';
                    }
                    
                    const row = document.createElement('tr');
                    if (rowClass) row.className = rowClass;
                    
                    // Date - use created_at or extract from notes as fallback
                    let dateText = '';
                    if (lead.created_at) {
                        const date = new Date(lead.created_at);
                        dateText = date.toLocaleDateString('en-US', { month: '2-digit', day: '2-digit', year: 'numeric' });
                    } else if (lead.notes && lead.notes.includes('Date:')) {
                        const dateMatch = lead.notes.match(/Date: ([^|]+)/);
                        if (dateMatch) {
                            dateText = dateMatch[1].trim();
                        }
                    }
                    
                    // Date
                    const dateCell = document.createElement('td');
                    dateCell.className = 'date-col';
                    dateCell.textContent = dateText;
                    row.appendChild(dateCell);
                    
                    // Name
                    const nameCell = document.createElement('td');
                    nameCell.className = 'name-col';
                    nameCell.textContent = lead.name;
                    row.appendChild(nameCell);
                    
                    // Email with icon
                    const emailCell = document.createElement('td');
                    emailCell.className = 'email-col';
                    if (lead.email && lead.email !== 'N/A') {
                        const emailContainer = document.createElement('div');
                        emailContainer.className = 'phone-actions';
                        
                        // Email text
                        const emailText = document.createElement('span');
                        emailText.textContent = lead.email;
                        emailContainer.appendChild(emailText);
                        
                        // Email icon
                        const emailIcon = document.createElement('i');
                        emailIcon.className = 'fas fa-envelope email-icon';
                        emailIcon.title = 'Send email to ' + lead.email;
                        emailIcon.style.marginLeft = '8px';
                        emailIcon.addEventListener('click', function(e) {
                            e.stopPropagation();
                            window.location.href = 'mailto:' + lead.email;
                        });
                        emailContainer.appendChild(emailIcon);
                        
                        emailCell.appendChild(emailContainer);
                    } else {
                        emailCell.textContent = 'N/A';
                    }
                    row.appendChild(emailCell);
                    
                    // Phone with action icons
                    const phoneCell = document.createElement('td');
                    phoneCell.className = 'phone-col';
                    const phoneContainer = document.createElement('div');
                    phoneContainer.className = 'phone-actions';
                    
                    // Phone number text
                    const phoneText = document.createElement('span');
                    phoneText.textContent = lead.phone;
                    phoneContainer.appendChild(phoneText);
                    
                    // Phone icon
                    if (lead.phone) {
                        const phoneIcon = document.createElement('i');
                        phoneIcon.className = 'fas fa-phone phone-icon';
                        phoneIcon.title = 'Call ' + lead.phone;
                        phoneIcon.style.marginLeft = '8px';
                        phoneIcon.addEventListener('click', function(e) {
                            e.stopPropagation();
                            window.location.href = 'tel:' + lead.phone.replace(/[^0-9+]/g, '');
                        });
                        phoneContainer.appendChild(phoneIcon);
                        
                        // Text icon
                        const textIcon = document.createElement('i');
                        textIcon.className = 'fas fa-sms text-icon';
                        textIcon.title = 'Send text to ' + lead.phone;
                        textIcon.addEventListener('click', function(e) {
                            e.stopPropagation();
                            showTextModal(lead.id, lead.name, lead.phone);
                        });
                        phoneContainer.appendChild(textIcon);
                    }
                    
                    // GoFormz icon (always show, not just when phone exists)
                    const goformzIcon = document.createElement('i');
                    goformzIcon.className = 'fas fa-file-alt goformz-icon';
                    goformzIcon.title = 'Send to GoFormz Employee Packet';
                    goformzIcon.style.marginLeft = lead.phone ? '0' : '8px';
                    goformzIcon.addEventListener('click', function(e) {
                        e.stopPropagation();
                        sendToGoFormz(lead.id, lead.name);
                    });
                    phoneContainer.appendChild(goformzIcon);
                    
                    phoneCell.appendChild(phoneContainer);
                    row.appendChild(phoneCell);
                    
                    // Status dropdown
                    const statusCell = document.createElement('td');
                    statusCell.className = 'status-col';
                    const statusSelect = document.createElement('select');
                    statusSelect.className = 'form-select-sm';
                    statusSelect.addEventListener('change', function() {
                        updateStatus(lead.id, this.value);
                    });
                    
                    const statusOptions = [
                        { value: 'new', text: 'New' },
                        { value: 'contacted', text: 'Contacted' },
                        { value: 'interested', text: 'Interested' },
                        { value: 'hired', text: 'Hired' },
                        { value: 'not_interested', text: 'Not Interested' }
                    ];
                    
                    statusOptions.forEach(option => {
                        const optionElement = document.createElement('option');
                        optionElement.value = option.value;
                        optionElement.textContent = option.text;
                        if (lead.status === option.value) {
                            optionElement.selected = true;
                        }
                        statusSelect.appendChild(optionElement);
                    });
                    
                    statusCell.appendChild(statusSelect);
                    row.appendChild(statusCell);
                    
                    // Notes - Simple inline edit
                    const notesCell = document.createElement('td');
                    notesCell.className = 'notes-col';
                    
                    const notesDisplay = document.createElement('div');
                    notesDisplay.className = 'notes-display';
                    notesDisplay.title = 'Click to edit notes';
                    const maxPreviewLength = 40;
                    if (notes && notes.length > maxPreviewLength) {
                        notesDisplay.textContent = notes.substring(0, maxPreviewLength) + '...';
                    } else {
                        notesDisplay.textContent = notes || 'Click to add notes';
                    }
                    
                    const notesTextarea = document.createElement('textarea');
                    notesTextarea.className = 'notes-textarea';
                    notesTextarea.value = notes || '';
                    notesTextarea.placeholder = 'Enter notes here...';
                    
                    // Click display to edit
                    notesDisplay.addEventListener('click', function() {
                        notesDisplay.classList.add('editing');
                        notesTextarea.classList.add('active');
                        notesTextarea.focus();
                    });
                    
                    // Save on blur (click away)
                    notesTextarea.addEventListener('blur', function() {
                        const newNotes = notesTextarea.value.trim();
                        saveNotes(lead.id, notesTextarea, function(success) {
                            if (success) {
                                // Update display
                                if (newNotes && newNotes.length > maxPreviewLength) {
                                    notesDisplay.textContent = newNotes.substring(0, maxPreviewLength) + '...';
                                } else {
                                    notesDisplay.textContent = newNotes || 'Click to add notes';
                                }
                            }
                            notesDisplay.classList.remove('editing');
                            notesTextarea.classList.remove('active');
                        });
                    });
                    
                    // Save on Ctrl/Cmd+Enter, Cancel on Escape
                    notesTextarea.addEventListener('keydown', function(e) {
                        if (e.key === 'Escape') {
                            notesTextarea.value = notes || '';
                            notesTextarea.blur();
                        } else if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                            notesTextarea.blur();
                        }
                    });
                    
                    notesCell.appendChild(notesDisplay);
                    notesCell.appendChild(notesTextarea);
                    row.appendChild(notesCell);
                    
                    tbody.appendChild(row);
                });
                
                table.appendChild(tbody);
                container.innerHTML = '';
                container.appendChild(table);
            }

            function updatePagination(totalPages, currentPage) {
                const container = document.getElementById('paginationContainer');
                const pagination = document.getElementById('pagination');
                
                if (totalPages <= 1) {
                    container.style.display = 'none';
                    return;
                }
                
                container.style.display = 'block';
                
                // Clear existing pagination
                pagination.innerHTML = '';
                
                // Create Previous button
                if (currentPage > 1) {
                    const prevLi = document.createElement('li');
                    prevLi.className = 'page-item';
                    const prevLink = document.createElement('a');
                    prevLink.className = 'page-link';
                    prevLink.href = '#';
                    prevLink.textContent = 'Previous';
                    prevLink.addEventListener('click', function(e) {
                        e.preventDefault();
                        goToPage(currentPage - 1);
                    });
                    prevLi.appendChild(prevLink);
                    pagination.appendChild(prevLi);
                }
                
                // Create page number buttons
                for (let i = 1; i <= totalPages; i++) {
                    const li = document.createElement('li');
                    li.className = i === currentPage ? 'page-item active' : 'page-item';
                    const link = document.createElement('a');
                    link.className = 'page-link';
                    link.href = '#';
                    link.textContent = i;
                    link.addEventListener('click', function(e) {
                        e.preventDefault();
                        goToPage(i);
                    });
                    li.appendChild(link);
                    pagination.appendChild(li);
                }
                
                // Create Next button
                if (currentPage < totalPages) {
                    const nextLi = document.createElement('li');
                    nextLi.className = 'page-item';
                    const nextLink = document.createElement('a');
                    nextLink.className = 'page-link';
                    nextLink.href = '#';
                    nextLink.textContent = 'Next';
                    nextLink.addEventListener('click', function(e) {
                        e.preventDefault();
                        goToPage(currentPage + 1);
                    });
                    nextLi.appendChild(nextLink);
                    pagination.appendChild(nextLi);
                }
            }

            function goToPage(page) {
                currentPage = page;
                loadLeads();
            }
            
            function filterLeads() {
                currentFilter = document.getElementById('statusFilter').value;
                currentPage = 1;
                loadLeads();
            }
            
            function searchLeads(leads, searchTerm) {
                if (!searchTerm || searchTerm.trim() === '') {
                    return leads;
                }
                
                const term = searchTerm.toLowerCase().trim();
                return leads.filter(lead => {
                    const name = (lead.name || '').toLowerCase();
                    const email = (lead.email || '').toLowerCase();
                    const phone = (lead.phone || '').replace(/\D/g, ''); // Remove non-digits
                    const searchPhone = term.replace(/\D/g, '');
                    
                    return name.includes(term) || 
                           email.includes(term) || 
                           (searchPhone && phone.includes(searchPhone));
                });
            }

            function saveNotes(leadId, textarea, callback) {
                const notes = textarea.value;
                
                fetch('/recruiting/api/leads/' + leadId, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ notes: notes })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        loadStats();
                        if (callback) callback(true);
                    } else {
                        alert('Error updating notes: ' + data.error);
                        if (callback) callback(false);
                    }
                })
                .catch(error => {
                    console.error('Error updating notes:', error);
                    alert('Error updating notes: ' + error.message);
                    if (callback) callback(false);
                });
            }

            function showTextModal(leadId, leadName, phoneNumber) {
                const overlay = document.getElementById('textModalOverlay');
                const messageInput = document.getElementById('textMessageInput');
                const recipientInfo = document.getElementById('textRecipientInfo');
                
                recipientInfo.textContent = `${leadName} (${phoneNumber})`;
                messageInput.value = '';
                messageInput.dataset.leadId = leadId;
                messageInput.dataset.phoneNumber = phoneNumber;
                
                overlay.classList.add('show');
                messageInput.focus();
            }

            function closeTextModal() {
                document.getElementById('textModalOverlay').classList.remove('show');
            }

            function sendTextFromModal() {
                const messageInput = document.getElementById('textMessageInput');
                const message = messageInput.value.trim();
                const leadId = messageInput.dataset.leadId;
                const phoneNumber = messageInput.dataset.phoneNumber;
                
                if (!message) {
                    alert('Please enter a message');
                    return;
                }
                
                closeTextModal();
                sendTextMessage(leadId, phoneNumber, message);
            }

            function sendTextMessage(leadId, phoneNumber, message) {
                fetch('/recruiting/api/beetexting/send', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    credentials: 'include',
                    body: JSON.stringify({
                        lead_id: leadId,
                        phone: phoneNumber,
                        message: message
                    })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Show success message
                        const successMsg = document.createElement('div');
                        successMsg.className = 'alert alert-success';
                        successMsg.style.position = 'fixed';
                        successMsg.style.top = '20px';
                        successMsg.style.right = '20px';
                        successMsg.style.zIndex = '2000';
                        successMsg.style.padding = '12px 20px';
                        successMsg.style.borderRadius = '8px';
                        successMsg.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
                        successMsg.innerHTML = '<i class="fas fa-check-circle"></i> Text message sent successfully!';
                        document.body.appendChild(successMsg);
                        
                        setTimeout(() => {
                            successMsg.remove();
                        }, 3000);
                        
                        loadLeads(); // Refresh to show updated notes
                    } else {
                        alert('Error sending text: ' + (data.error || 'Unknown error'));
                    }
                })
                .catch(error => {
                    console.error('Error sending text:', error);
                    alert('Error sending text: ' + error.message);
                });
            }

            function sendToGoFormz(leadId, leadName) {
                if (!confirm(`Send ${leadName} to GoFormz Employee Packet?`)) {
                    return;
                }
                
                fetch('/recruiting/api/goformz/send-lead', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    credentials: 'include',
                    body: JSON.stringify({ lead_id: leadId })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Show success message
                        const successMsg = document.createElement('div');
                        successMsg.className = 'alert alert-success';
                        successMsg.style.position = 'fixed';
                        successMsg.style.top = '20px';
                        successMsg.style.right = '20px';
                        successMsg.style.zIndex = '2000';
                        successMsg.style.padding = '12px 20px';
                        successMsg.style.borderRadius = '8px';
                        successMsg.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
                        successMsg.style.background = '#10b981';
                        successMsg.style.color = 'white';
                        successMsg.innerHTML = '<i class="fas fa-check-circle"></i> Successfully sent to GoFormz!';
                        document.body.appendChild(successMsg);
                        
                        setTimeout(() => {
                            successMsg.remove();
                        }, 3000);
                        
                        loadLeads(); // Refresh to show updated notes
                    } else {
                        alert('Error sending to GoFormz: ' + (data.error || 'Unknown error'));
                    }
                })
                .catch(error => {
                    console.error('Error sending to GoFormz:', error);
                    alert('Error sending to GoFormz: ' + error.message);
                });
            }

            function updateStatus(leadId, status) {
                fetch('/recruiting/api/leads/' + leadId, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ status: status })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        loadStats();
                    } else {
                        alert('Error updating status: ' + data.error);
                    }
                })
                .catch(error => {
                    console.error('Error updating status:', error);
                    alert('Error updating status: ' + error.message);
                });
            }

            // Facebook Campaign Functions
            function loadFacebookCampaigns() {
                console.log('loadFacebookCampaigns called');
                fetch('/recruiting/api/facebook/campaigns')
                    .then(response => response.json())
                    .then(campaigns => {
                        displayCampaigns(campaigns);
                        // Use the global selectedTimePeriod variable
                        console.log('loadFacebookCampaigns - using selectedTimePeriod:', selectedTimePeriod);
                        loadCampaignMetrics(campaigns, selectedTimePeriod);
                    })
                    .catch(error => {
                        console.error('Error loading Facebook campaigns:', error);
                        document.getElementById('campaignsList').innerHTML = '<div class="text-danger">Error loading campaigns</div>';
                    });
            }

            function pullFacebookLeads() {
                const pullBtn = document.getElementById('pullLeadsBtn');
                const statusEl = document.getElementById('pullLeadsStatus');

                if (!pullBtn || !statusEl) {
                    console.warn('Pull leads UI elements missing');
                    return;
                }

                const originalLabel = pullBtn.innerHTML;
                statusEl.classList.remove('text-danger', 'text-success');
                statusEl.textContent = 'Contacting Facebook...';
                pullBtn.disabled = true;
                pullBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Pulling...';

                fetch('/recruiting/api/facebook/fetch-leads', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    credentials: 'include'
                })
                    .then(response => {
                        if (!response.ok) {
                            throw new Error('Server responded with ' + response.status);
                        }
                        return response.json();
                    })
                    .then(data => {
                        if (!data.success) {
                            throw new Error(data.error || 'Unknown error');
                        }
                        const count = data.leads_added || 0;
                        const now = new Date().toLocaleTimeString();
                        statusEl.classList.add('text-success');
                        statusEl.textContent = `Pulled ${count} lead${count === 1 ? '' : 's'} at ${now}`;
                        loadLeads();
                        loadStats();
                    })
                    .catch(error => {
                        console.error('Error pulling Facebook leads:', error);
                        statusEl.classList.add('text-danger');
                        statusEl.textContent = 'Error pulling leads: ' + error.message;
                    })
                    .finally(() => {
                        pullBtn.disabled = false;
                        pullBtn.innerHTML = originalLabel;
                        setTimeout(() => statusEl.classList.remove('text-danger', 'text-success'), 4000);
                    });
            }
            
            // Prevent multiple simultaneous calls
            let isLoadingMetrics = false;

            function displayCampaigns(campaigns) {
                const container = document.getElementById('campaignsList');
                
                if (campaigns.length === 0) {
                    const noCampaignsDiv = document.createElement('div');
                    noCampaignsDiv.className = 'text-muted';
                    noCampaignsDiv.textContent = 'No campaigns found. Click "Sync Campaigns" to load from Facebook.';
                    container.innerHTML = '';
                    container.appendChild(noCampaignsDiv);
                    return;
                }
                
                container.innerHTML = '';
                
                campaigns.forEach(campaign => {
                    const statusClass = campaign.status === 'active' ? 'status-active' : 'status-paused';
                    const toggleText = campaign.status === 'active' ? 'Pause' : 'Start';
                    const toggleClass = campaign.status === 'active' ? 'btn-warning' : 'btn-success';
                    
                    const campaignItem = document.createElement('div');
                    campaignItem.className = 'campaign-item';
                    
                    const leftDiv = document.createElement('div');
                    const nameStrong = document.createElement('strong');
                    nameStrong.textContent = campaign.name;
                    leftDiv.appendChild(nameStrong);
                    leftDiv.appendChild(document.createElement('br'));
                    
                    const regionSmall = document.createElement('small');
                    regionSmall.className = 'text-muted';
                    regionSmall.textContent = campaign.region.replace('_', ' ').toUpperCase();
                    leftDiv.appendChild(regionSmall);
                    
                    const rightDiv = document.createElement('div');
                    rightDiv.className = 'd-flex align-items-center gap-2';
                    
                    const statusSpan = document.createElement('span');
                    statusSpan.className = 'campaign-status ' + statusClass;
                    statusSpan.textContent = campaign.status.toUpperCase();
                    
                    const toggleBtn = document.createElement('button');
                    toggleBtn.className = 'btn btn-sm ' + toggleClass;
                    toggleBtn.textContent = toggleText;
                    toggleBtn.addEventListener('click', function() {
                        toggleCampaign(campaign.campaign_id, campaign.status === 'active' ? 'paused' : 'active');
                    });
                    
                    rightDiv.appendChild(statusSpan);
                    rightDiv.appendChild(toggleBtn);
                    
                    campaignItem.appendChild(leftDiv);
                    campaignItem.appendChild(rightDiv);
                    
                    container.appendChild(campaignItem);
                });
            }

            function loadCampaignMetrics(campaigns, timePeriod = 7) {
                // Prevent multiple simultaneous calls
                if (isLoadingMetrics) {
                    console.log('Already loading metrics, skipping...');
                    return;
                }
                isLoadingMetrics = true;
                
                let totalSpend = 0;
                let totalLeads = 0;
                let campaignCount = 0;
                
                console.log('Loading metrics for', campaigns.length, 'campaigns, time period:', timePeriod);
                
                const promises = campaigns.map(campaign => {
                    const url = timePeriod >= 365 ? 
                        '/recruiting/api/facebook/campaigns/' + campaign.campaign_id + '/metrics' : 
                        '/recruiting/api/facebook/campaigns/' + campaign.campaign_id + '/metrics?days=' + timePeriod;
                    console.log('Making API call to:', url);
                    return fetch(url)
                        .then(response => {
                            console.log('Response for campaign', campaign.campaign_id, ':', response.status);
                            return response.json();
                        })
                        .then(metrics => {
                            console.log('Metrics for campaign', campaign.campaign_id, ':', metrics);
                            console.log('Raw spend value:', metrics.spend, 'Raw leads value:', metrics.leads);
                            if (metrics && metrics.spend !== undefined) {
                                totalSpend += metrics.spend;
                                totalLeads += metrics.leads;
                                campaignCount++;
                                console.log('Updated totals - Spend:', totalSpend, 'Leads:', totalLeads);
                            }
                        })
                        .catch(error => {
                            console.error('Error loading metrics for campaign', campaign.campaign_id, error);
                        });
                });
                
                Promise.all(promises).then(() => {
                    console.log('Final totals - Spend:', totalSpend, 'Leads:', totalLeads);
                    document.getElementById('totalSpend').textContent = '$' + totalSpend.toFixed(2);
                    document.getElementById('facebookLeads').textContent = totalLeads;
                    
                    // Calculate weighted average CPA
                    const avgCPA = totalLeads > 0 ? (totalSpend / totalLeads) : 0;
                    document.getElementById('avgCPA').textContent = '$' + avgCPA.toFixed(2);
                    
                    // Calculate weighted average ROAS (assuming $100 value per lead)
                    const avgROAS = totalSpend > 0 ? ((totalLeads * 100) / totalSpend) : 0;
                    document.getElementById('avgROAS').textContent = avgROAS.toFixed(1) + '%';
                    
                    // Reset the loading flag
                    isLoadingMetrics = false;
                }).catch(error => {
                    console.error('Error in Promise.all:', error);
                    isLoadingMetrics = false;
                });
            }

            function syncFacebookCampaigns() {
                const button = event.target;
                const originalText = button.innerHTML;
                button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Syncing...';
                button.disabled = true;
                
                fetch('/recruiting/api/facebook/sync-campaigns')
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            alert('Successfully synced ' + data.synced_count + ' campaigns from Facebook!');
                            loadFacebookCampaigns();
                        } else {
                            alert('Error syncing campaigns: ' + data.error);
                        }
                    })
                    .catch(error => {
                        console.error('Error syncing campaigns:', error);
                        alert('Error syncing campaigns. Please try again.');
                    })
                    .finally(() => {
                        button.innerHTML = originalText;
                        button.disabled = false;
                    });
            }

            function refreshCampaignMetrics() {
                const button = event.target;
                const originalText = button.innerHTML;
                button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Refreshing...';
                button.disabled = true;
                
                // Get selected time period
                const selectedPeriod = document.querySelector('input[name="timePeriod"]:checked').value;
                const timePeriod = selectedPeriod === 'all' ? 365 : parseInt(selectedPeriod);
                
                fetch('/recruiting/api/facebook/campaigns')
                    .then(response => response.json())
                    .then(campaigns => {
                        loadCampaignMetrics(campaigns, timePeriod);
                    })
                    .catch(error => console.error('Error refreshing metrics:', error))
                    .finally(() => {
                        button.innerHTML = originalText;
                        button.disabled = false;
                    });
            }


            function toggleCampaign(campaignId, newStatus) {
                fetch('/recruiting/api/facebook/campaigns/' + campaignId + '/toggle', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ status: newStatus })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('Campaign status updated successfully!');
                        loadFacebookCampaigns();
                    } else {
                        alert('Error updating campaign: ' + data.error);
                    }
                })
                .catch(error => {
                    console.error('Error toggling campaign:', error);
                    alert('Error updating campaign. Please try again.');
                });
            }
        </script>
    </body>
    </html>
    '''
    except Exception as e:
        print(f"Error rendering dashboard: {e}")
        import traceback
        traceback.print_exc()
        return f"<h1>Error</h1><p>{str(e)}</p>", 500

# OAuth Authentication Routes
# Google OAuth routes removed - no authentication required
# Portal handles authentication, dashboard is embedded in portal

@app.route('/logout')
def logout():
    # No auth required - just redirect to home
    return redirect('/')

@app.route('/api/stats')
@require_auth
def get_stats():
    total_leads = Lead.query.count()
    
    # New leads = leads added since today (baseline reset)
    from datetime import timedelta
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    new_leads = Lead.query.filter(Lead.created_at >= today_start).count()
    
    contacted_leads = Lead.query.filter_by(status='contacted').count()
    
    # Calculate "Wants Work" - leads with positive indicators in notes
    wants_work_query = Lead.query.filter(
        db.or_(
            Lead.notes.contains('sent application'),
            Lead.notes.contains('FT'),
            Lead.notes.contains('PT'),
            Lead.notes.contains('CNA'),
            Lead.notes.contains('QMAP'),
            Lead.notes.contains('full time'),
            Lead.notes.contains('part time')
        )
    )
    wants_work_leads = wants_work_query.count()
    
    # Current Caregivers - leads marked as hired (still employed)
    current_caregivers = Lead.query.filter_by(status='hired').count()
    
    return jsonify({
        'total_leads': total_leads,
        'new_leads': new_leads,
        'contacted_leads': contacted_leads,
        'wants_work_leads': wants_work_leads,
        'current_caregivers': current_caregivers
    })

# Facebook API Functions
def get_facebook_campaigns():
    """Fetch campaigns from Facebook Ads API"""
    try:
        account = AdAccount(f'act_{FACEBOOK_AD_ACCOUNT_ID}')
        campaigns = account.get_campaigns(fields=['id', 'name', 'status', 'created_time'])
        return campaigns
    except Exception as e:
        print(f"Error fetching Facebook campaigns: {e}")
        return []

def sync_facebook_campaigns():
    """Sync Facebook campaigns with local database"""
    campaigns = get_facebook_campaigns()
    synced_count = 0
    
    # Clear existing campaigns first
    FacebookCampaign.query.delete()
    
    for campaign in campaigns:
        # Only sync "Caregiver Recruitment" campaigns
        campaign_name = campaign.get('name', '')
        if "Caregiver Recruitment" not in campaign_name:
            continue
            
        # Determine region based on campaign name
        campaign_name_lower = campaign_name.lower()
        if 'denver' in campaign_name_lower or 'boulder' in campaign_name_lower:
            region = 'denver_boulder'
        elif 'colorado springs' in campaign_name_lower or 'pueblo' in campaign_name_lower or 'cos' in campaign_name_lower:
            region = 'colorado_springs_pueblo'
        else:
            region = 'unknown'
        
        # Create new campaign
        new_campaign = FacebookCampaign(
            campaign_id=campaign['id'],
            name=campaign['name'],
            region=region,
            status=campaign['status']
        )
        db.session.add(new_campaign)
        synced_count += 1
    
    db.session.commit()
    return synced_count

def get_campaign_metrics(campaign_id, days=7):
    """Fetch ad metrics for a campaign"""
    try:
        account = AdAccount(f'act_{FACEBOOK_AD_ACCOUNT_ID}')
        campaign = Campaign(campaign_id)
        
        # Get insights for the specified time period
        if days >= 365:  # All time
            # For all time, use a very wide date range (from campaign start to now)
            print(f"Campaign {campaign_id} - Fetching ALL TIME metrics (wide date range)")
            end_time = datetime.now()
            start_time = datetime(2025, 1, 1)  # Start from beginning of 2025
            
            try:
                insights = campaign.get_insights(
                    fields=['spend', 'impressions', 'clicks', 'actions', 'action_values'],
                    params={
                        'time_range': {
                            'since': start_time.strftime('%Y-%m-%d'),
                            'until': end_time.strftime('%Y-%m-%d')
                        },
                        'level': 'campaign'
                    }
                )
            except Exception as api_error:
                print(f"Facebook API error for campaign {campaign_id}: {api_error}")
                import traceback
                traceback.print_exc()
                return None
        else:
            # For specific time periods, set the date range
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)
            print(f"Campaign {campaign_id} - Fetching {days} DAY metrics from {start_time.strftime('%Y-%m-%d')} to {end_time.strftime('%Y-%m-%d')}")
            
            try:
                insights = campaign.get_insights(
                    fields=['spend', 'impressions', 'clicks', 'actions', 'action_values'],
                    params={
                        'time_range': {
                            'since': start_time.strftime('%Y-%m-%d'),
                            'until': end_time.strftime('%Y-%m-%d')
                        },
                        'level': 'campaign'
                    }
                )
            except Exception as api_error:
                print(f"Facebook API error for campaign {campaign_id}: {api_error}")
                import traceback
                traceback.print_exc()
                return None
        
        if insights:
            insight = insights[0]
            print(f"Campaign {campaign_id} - Raw Facebook API response: {insight}")
            spend = float(insight.get('spend', 0))
            impressions = int(insight.get('impressions', 0))
            clicks = int(insight.get('clicks', 0))
            print(f"Campaign {campaign_id} - Parsed spend: {spend}, impressions: {impressions}, clicks: {clicks}")
            
            # Count leads from actions - prioritize the most accurate lead action type
            actions = insight.get('actions', [])
            leads = 0
            
            print(f"Campaign {campaign_id} actions: {actions}")  # Debug log
            
            # Look for the most specific Meta Leads action type first
            for action in actions:
                action_type = action.get('action_type', '').lower()
                action_value = int(float(action.get('value', 0)))
                
                # Prioritize Meta Leads specific actions
                if 'offsite_complete_registration_add_meta_leads' in action_type:
                    leads = action_value  # Use this as the primary lead count
                    print(f"Using Meta Leads from offsite_complete_registration: {action_value}")
                    break
                elif action_type == 'lead':
                    leads = action_value  # Fallback to generic lead
                    print(f"Using generic lead count: {action_value}")
                    break
            
            # If still no leads, try other Meta Leads variations
            if leads == 0:
                for action in actions:
                    action_type = action.get('action_type', '').lower()
                    action_value = int(float(action.get('value', 0)))
                    
                    if any(lead_type in action_type for lead_type in ['meta_leads', 'leadgen', 'form']):
                        leads = action_value
                        print(f"Found {action_value} leads from action type: {action_type}")
                        break
            
            # Calculate CPA and ROAS
            cpa = spend / leads if leads > 0 else 0
            roas = (leads * 100) / spend if spend > 0 else 0  # Assuming $100 value per lead
            
            print(f"Campaign {campaign_id} metrics: spend=${spend}, leads={leads}, cpa=${cpa}")
            
            return {
                'spend': spend,
                'impressions': impressions,
                'clicks': clicks,
                'leads': leads,
                'cpa': cpa,
                'roas': roas
            }
        else:
            print(f"Campaign {campaign_id} - No insights returned from Facebook API")
            return None
    except Exception as e:
        print(f"Error fetching campaign metrics for campaign {campaign_id}: {e}")
        import traceback
        traceback.print_exc()
        return None

def toggle_campaign_status(campaign_id, status):
    """Toggle campaign on/off"""
    try:
        campaign = Campaign(campaign_id)
        campaign.api_update(params={'status': status})
        
        # Update local database
        local_campaign = FacebookCampaign.query.filter_by(campaign_id=campaign_id).first()
        if local_campaign:
            local_campaign.status = status
            local_campaign.updated_at = datetime.utcnow()
            db.session.commit()
        
        return True
    except Exception as e:
        print(f"Error toggling campaign status: {e}")
        return False

def fetch_facebook_leads():
    """Fetch new leads from Facebook Lead Ads campaigns using leads_retrieval permission"""
    try:
        account = AdAccount(f'act_{FACEBOOK_AD_ACCOUNT_ID}')
        leads_added = 0
        
        # Get all campaigns
        campaigns = account.get_campaigns(fields=['id', 'name', 'status'])
        print(f"Found {len(campaigns)} total campaigns")
        
        for campaign in campaigns:
            print(f"Campaign: {campaign['name']} ({campaign['id']}) - Status: {campaign['status']}")
            if campaign['status'] == 'ACTIVE':
                print(f"Processing active campaign: {campaign['name']}")
                
                # Get ad sets for this campaign
                ad_sets = Campaign(campaign['id']).get_ad_sets(fields=['id', 'name'])
                print(f"Found {len(ad_sets)} ad sets in campaign {campaign['name']}")
                
                for ad_set in ad_sets:
                    print(f"Processing ad set: {ad_set['name']} ({ad_set['id']})")
                    # Get ads for this ad set
                    ads = AdSet(ad_set['id']).get_ads(fields=['id', 'name'])
                    print(f"Found {len(ads)} ads in ad set {ad_set['name']}")
                    
                    for ad in ads:
                        print(f"Processing ad: {ad['name']} ({ad['id']})")
                        try:
                            # Get leads for this ad using leads_retrieval permission
                            leads = Ad(ad['id']).get_leads(fields=['id', 'created_time', 'field_data'])
                            print(f"Found {len(leads)} leads in ad {ad['name']}")
                            
                            for lead in leads:
                                # Process each lead
                                if process_facebook_lead(lead, campaign['name']):
                                    leads_added += 1
                        except Exception as ad_error:
                            print(f"Error getting leads from ad {ad['id']}: {ad_error}")
                                
        print(f"Successfully added {leads_added} new leads from Facebook")
        return leads_added
        
    except Exception as e:
        print(f"Error fetching Facebook leads: {e}")
        return 0

def fetch_facebook_leads_enhanced():
    """Enhanced Facebook lead fetching with better error handling and filtering"""
    try:
        account = AdAccount(f'act_{FACEBOOK_AD_ACCOUNT_ID}')
        leads_added = 0
        
        # Get campaigns with lead generation objectives
        campaigns = account.get_campaigns(fields=['id', 'name', 'status', 'objective'])
        print(f"Found {len(campaigns)} total campaigns")
        
        for campaign in campaigns:
            print(f"Campaign: {campaign['name']} ({campaign['id']}) - Status: {campaign['status']} - Objective: {campaign.get('objective', 'Unknown')}")
            
            # Only process active campaigns with lead generation objectives
            if campaign['status'] == 'ACTIVE' and campaign.get('objective') in ['LEAD_GENERATION', 'MESSAGES']:
                print(f"Processing active lead generation campaign: {campaign['name']}")
                
                # Get ad sets for this campaign
                ad_sets = Campaign(campaign['id']).get_ad_sets(fields=['id', 'name'])
                print(f"Found {len(ad_sets)} ad sets in campaign {campaign['name']}")
                
                for ad_set in ad_sets:
                    print(f"Processing ad set: {ad_set['name']} ({ad_set['id']})")
                    # Get ads for this ad set
                    ads = AdSet(ad_set['id']).get_ads(fields=['id', 'name'])
                    print(f"Found {len(ads)} ads in ad set {ad_set['name']}")
                    
                    for ad in ads:
                        print(f"Processing ad: {ad['name']} ({ad['id']})")
                        try:
                            # Get leads for this ad with enhanced fields
                            leads = Ad(ad['id']).get_leads(fields=[
                                'id', 
                                'created_time', 
                                'field_data',
                                'ad_id',
                                'adset_id',
                                'campaign_id'
                            ])
                            print(f"Found {len(leads)} leads in ad {ad['name']}")
                            
                            for lead in leads:
                                # Process each lead with enhanced data
                                if process_facebook_lead_enhanced(lead, campaign['name'], ad['name']):
                                    leads_added += 1
                        except Exception as ad_error:
                            print(f"Error getting leads from ad {ad['id']}: {ad_error}")
                                
        print(f"Successfully added {leads_added} new leads from Facebook")
        return leads_added
        
    except Exception as e:
        print(f"Error fetching Facebook leads: {e}")
        return 0

def process_facebook_lead_enhanced(lead_data, campaign_name, ad_name):
    """Enhanced processing of a single Facebook lead with better data extraction"""
    try:
        facebook_lead_id = lead_data.get('id')

        if facebook_lead_id:
            existing_by_fb = Lead.query.filter_by(facebook_lead_id=facebook_lead_id).first()
            if existing_by_fb:
                print(f"Lead {facebook_lead_id} already ingested — skipping")
                return False

        # Extract lead information from field_data
        field_data = lead_data.get('field_data', [])
        lead_info = {}
        
        for field in field_data:
            field_name = field.get('name', '').lower()
            field_value = field.get('values', [''])[0] if field.get('values') else ''
            
            if 'full_name' in field_name or 'name' in field_name:
                lead_info['name'] = field_value
            elif 'email' in field_name:
                lead_info['email'] = field_value
            elif 'phone' in field_name or 'phone_number' in field_name:
                lead_info['phone'] = field_value
            elif 'message' in field_name or 'notes' in field_name or 'comments' in field_name:
                lead_info['notes'] = field_value
            elif 'job_title' in field_name or 'position' in field_name:
                lead_info['job_title'] = field_value
            elif 'company' in field_name:
                lead_info['company'] = field_value
        
        # Get lead creation time
        created_time = lead_data.get('created_time', '')
        if created_time:
            try:
                # Parse Facebook timestamp
                from datetime import datetime
                lead_date = datetime.strptime(created_time, '%Y-%m-%dT%H:%M:%S%z')
                lead_info['created_time'] = lead_date
            except:
                lead_info['created_time'] = datetime.utcnow()
        else:
            lead_info['created_time'] = datetime.utcnow()
        
        # Check if lead already exists (by email, phone, or name)
        existing_lead = None
        if lead_info.get('email'):
            existing_lead = Lead.query.filter_by(email=lead_info['email']).first()
        elif lead_info.get('phone'):
            existing_lead = Lead.query.filter_by(phone=lead_info['phone']).first()
        elif lead_info.get('name'):
            existing_lead = Lead.query.filter(
                db.func.lower(Lead.name) == lead_info['name'].lower()
            ).first()
        
        if existing_lead:
            # Backfill facebook id/source if we just matched on email/phone/name
            if facebook_lead_id and not existing_lead.facebook_lead_id:
                existing_lead.facebook_lead_id = facebook_lead_id
                if existing_lead.source == 'manual':
                    existing_lead.source = 'facebook'
                db.session.commit()
            print(f"Lead already exists: {lead_info.get('name', 'Unknown')}")
            return False
        
        # Don't add campaign info to notes - notes should be blank for new leads
        # Only include actual message/notes from the lead if they provided one
        notes = lead_info.get('notes', '') if lead_info.get('notes') else ''
        
        # Create new lead
        new_lead = Lead(
            name=lead_info.get('name', 'Facebook Lead'),
            email=lead_info.get('email', ''),
            phone=lead_info.get('phone', ''),
            notes=notes,
            status='new',
            priority='medium',
            created_at=lead_info['created_time'],
            source='facebook',
            facebook_lead_id=facebook_lead_id
        )
        
        db.session.add(new_lead)
        db.session.commit()
        
        print(f"Added new Facebook lead: {new_lead.name} from {campaign_name}")
        return True
        
    except Exception as e:
        print(f"Error processing Facebook lead: {e}")
        return False

# Facebook API Endpoints
@app.route('/api/facebook/sync-campaigns')
@require_auth
def sync_campaigns():
    """Sync Facebook campaigns with database"""
    try:
        synced_count = sync_facebook_campaigns()
        return jsonify({'success': True, 'synced_count': synced_count})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/facebook/campaigns')
@require_auth
def get_campaigns():
    """Get all Facebook campaigns"""
    campaigns = FacebookCampaign.query.all()
    return jsonify([{
        'id': c.id,
        'campaign_id': c.campaign_id,
        'name': c.name,
        'region': c.region,
        'status': c.status,
        'created_at': c.created_at.isoformat()
    } for c in campaigns])

@app.route('/api/facebook/campaigns/<campaign_id>/toggle', methods=['POST'])
@require_auth
def toggle_campaign(campaign_id):
    """Toggle campaign on/off"""
    data = request.get_json()
    new_status = data.get('status', 'paused')
    
    if toggle_campaign_status(campaign_id, new_status):
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Failed to toggle campaign'}), 500

@app.route('/api/facebook/campaigns/<campaign_id>/metrics')
@require_auth
def get_campaign_metrics_endpoint(campaign_id):
    """Get metrics for a specific campaign"""
    try:
        days_param = request.args.get('days')
        if days_param is None:
            # No days parameter means "All Time"
            days = 365
            print(f"API ENDPOINT: Campaign {campaign_id} requested with NO days parameter (All Time)")
        else:
            days = int(days_param)
            print(f"API ENDPOINT: Campaign {campaign_id} requested with days={days}")
        
        metrics = get_campaign_metrics(campaign_id, days)
        if metrics:
            return jsonify(metrics)
        else:
            # Return zero values instead of 500 error to prevent frontend crashes
            return jsonify({
                'spend': 0,
                'impressions': 0,
                'clicks': 0,
                'leads': 0,
                'cpa': 0,
                'roas': 0
            })
    except Exception as e:
        print(f"Error in get_campaign_metrics_endpoint for campaign {campaign_id}: {e}")
        # Return zero values instead of 500 error to prevent frontend crashes
        return jsonify({
            'spend': 0,
            'impressions': 0,
            'clicks': 0,
            'leads': 0,
            'cpa': 0,
            'roas': 0
        })

@app.route('/api/facebook/leads')
@require_auth
def get_facebook_leads():
    """Get recent leads from Facebook campaigns"""
    try:
        # This would typically use Facebook's Lead Ads API
        # For now, we'll return a placeholder
        return jsonify({
            'message': 'Facebook leads integration coming soon',
            'leads': []
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/facebook/fetch-leads', methods=['POST'])
@require_auth
def fetch_leads_endpoint():
    """Manually trigger Facebook lead fetching using enhanced method"""
    try:
        leads_added = fetch_facebook_leads_enhanced()
        return jsonify({
            'success': True, 
            'leads_added': leads_added,
            'message': f'Successfully added {leads_added} new leads from Facebook'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/facebook/auto-fetch-leads', methods=['POST'])
@require_auth
def auto_fetch_leads_endpoint():
    """Automatically fetch Facebook leads (for scheduled tasks)"""
    try:
        leads_added = fetch_facebook_leads_enhanced()
        print(f"AUTO-FETCH: Added {leads_added} new leads from Facebook")
        return jsonify({
            'success': True,
            'leads_added': leads_added,
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        print(f"AUTO-FETCH ERROR: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/leads/update-dates', methods=['POST'])
@require_auth
def update_lead_dates():
    """Update existing leads with dates from CSV data"""
    try:
        # Sample CSV data for matching
        csv_data = [
            {"name": "Frances Mayfield-Bunch", "date": "10/23/2025"},
            {"name": "Selamawit Gebre", "date": "10/23/2025"},
            {"name": "Birdie Inthapatha", "date": "10/23/2025"},
            {"name": "Felicia Carbajal", "date": "10/23/2025"},
            {"name": "Tristan Wilson", "date": "10/23/2025"},
            {"name": "Pat Shorty-Reyez", "date": "10/23/2025"},
            {"name": "Felicia ledoux", "date": "10/22/2025"},
            {"name": "Desiree Baker- Perkins", "date": "10/22/2025"},
            {"name": "Sue Fisher", "date": "10/22/2025"},
            {"name": "Louise Carr", "date": "10/22/2025"},
            {"name": "PA Diaab", "date": "10/22/2025"},
            {"name": "Rickee Garcia", "date": "10/22/2025"},
            {"name": "Patricia Crim", "date": "10/22/2025"},
            {"name": "Gizachew Tiku", "date": "10/22/2025"},
            {"name": "Nancy Fitzgerald", "date": "10/22/2025"},
            {"name": "Melissa Craig", "date": "10/22/2025"},
            {"name": "Scott Patrick Selvage", "date": "10/22/2025"},
            {"name": "Barbara Romero", "date": "10/22/2025"},
            {"name": "Courtney McGruder", "date": "10/22/2025"},
            {"name": "Jonathan Martinez", "date": "10/22/2025"},
            {"name": "Ursula Martinez", "date": "10/22/2025"},
            {"name": "Chenelle Lenae Sandoval", "date": "10/22/2025"},
            {"name": "Veronica Contreras", "date": "10/22/2025"},
            {"name": "Conrad Sims Sims", "date": "10/22/2025"},
            {"name": "Ayantu muleta", "date": "10/22/2025"},
            {"name": "Zu Hussien", "date": "10/22/2025"},
            {"name": "Mary Ann Medina", "date": "10/22/2025"},
            {"name": "Charlotte Suomie", "date": "10/22/2025"},
            {"name": "Yah Freeman", "date": "10/22/2025"},
            {"name": "maucanda rengei", "date": "10/22/2025"},
            {"name": "Junie British", "date": "10/22/2025"},
            {"name": "Emma Hodo", "date": "10/22/2025"},
            {"name": "Rolivie Cuaresma Peralta", "date": "10/22/2025"},
            {"name": "Chuck Valenzuela Sr.", "date": "10/22/2025"},
            {"name": "Georgia Mena", "date": "10/22/2025"},
            {"name": "Earlene M. Payne", "date": "10/22/2025"},
            {"name": "Jerry Davis", "date": "10/22/2025"},
            {"name": "Lyes ouagued", "date": "10/22/2025"},
            {"name": "Sherri A Smith", "date": "10/22/2025"},
            {"name": "Fredrick Ezeani", "date": "10/22/2025"},
            {"name": "Tseten", "date": "10/22/2025"},
            {"name": "Donna S Green", "date": "10/22/2025"},
            {"name": "Christie Cole Phonville", "date": "10/22/2025"},
            {"name": "Philip Vigil", "date": "10/22/2025"},
            {"name": "Lisa Jo", "date": "10/22/2025"},
            {"name": "j  Bowers", "date": "10/22/2025"},
            {"name": "Leslie Mercado Gomez", "date": "10/22/2025"},
            {"name": "Kristopher Dee Koetting", "date": "10/22/2025"},
            {"name": "Kimberly Bashaw", "date": "10/22/2025"},
            {"name": "Kelly Trevino", "date": "10/22/2025"},
            {"name": "Tonya Gonzales", "date": "10/22/2025"},
            {"name": "Georgina Garcia", "date": "10/22/2025"},
            {"name": "Maria del Carmen Chavez", "date": "10/22/2025"},
            {"name": "Les Dorn", "date": "10/22/2025"},
            {"name": "Chris Marez", "date": "10/22/2025"},
            {"name": "Maura Morris", "date": "10/22/2025"},
            {"name": "Daniel Damien Peralta", "date": "10/22/2025"},
            {"name": "Steifi Otup", "date": "10/22/2025"},
            {"name": "Katherine Warner", "date": "10/22/2025"},
            {"name": "Eva Vedia", "date": "10/22/2025"},
            {"name": "Crystal Gonzales", "date": "10/22/2025"},
            {"name": "Brian Santistevan", "date": "10/22/2025"},
            {"name": "ashley ruiz", "date": "10/22/2025"},
            {"name": "Serena Guardado", "date": "10/21/2025"},
            {"name": "Louie Velasquez", "date": "10/21/2025"},
            {"name": "Cecille Ong", "date": "10/21/2025"},
            {"name": "Ellen Mills", "date": "10/21/2025"},
            {"name": "Ryan Wagner", "date": "10/21/2025"},
            {"name": "Anita Herrera", "date": "10/21/2025"},
            {"name": "Tammy Abbott", "date": "10/21/2025"},
            {"name": "Santanna Hughey", "date": "10/21/2025"},
            {"name": "Debbie Morre", "date": "10/04/2025"},
            {"name": "Valarie Medina", "date": "10/02/2025"},
            {"name": "Beth Purvis Parker", "date": "10/02/2025"},
            {"name": "Francisco", "date": "10/02/2025"},
            {"name": "Kibrom Eritrawi", "date": "10/02/2025"},
            {"name": "Martha L Jeffrey", "date": "10/02/2025"},
            {"name": "Jonette Hindi", "date": "10/01/2025"},
            {"name": "Timothy Lee Gatuma", "date": "10/01/2025"},
            {"name": "Randy de la nuez", "date": "10/01/2025"},
            {"name": "Grace Boutiqe", "date": "10/01/2025"},
            {"name": "LalañMenace Rivera Rivera", "date": "10/01/2025"},
            {"name": "Lauren Ostoich", "date": "10/01/2025"},
            {"name": "Renee Sanchez", "date": "10/01/2025"},
            {"name": "Tom A Mekan", "date": "10/01/2025"},
            {"name": "Linda Walker", "date": "10/01/2025"},
            {"name": "Kim Conner", "date": "10/01/2025"},
            {"name": "Angela Atteberry", "date": "10/01/2025"},
            {"name": "Nyima", "date": "10/01/2025"},
            {"name": "Leslie Seidenstricker", "date": "10/01/2025"},
            {"name": "patricia", "date": "10/01/2025"},
            {"name": "Joetta Martinez", "date": "10/01/2025"},
            {"name": "Carla Clay", "date": "10/01/2025"},
            {"name": "Christy Ann", "date": "10/01/2025"},
            {"name": "Loalee Fifita", "date": "10/01/2025"},
            {"name": "Wayne Sims", "date": "10/01/2025"},
            {"name": "Racheal Wambui", "date": "09/10/2025"},
            {"name": "Lashanda Brown", "date": "09/10/2025"},
            {"name": "Michelle Schnapp", "date": "09/10/2025"},
            {"name": "Elyssa Justine Pounds", "date": "09/10/2025"},
            {"name": "Jass Quintero", "date": "09/10/2025"},
            {"name": "Michelle Broome-Sammons", "date": "09/10/2025"},
            {"name": "Sandra Hargrove", "date": "09/09/2025"},
            {"name": "Meryl Somera Vaughan", "date": "09/09/2025"},
            {"name": "Andrea Garcia", "date": "09/09/2025"},
            {"name": "Marilyn Pyles", "date": "09/09/2025"},
            {"name": "Candice Martinez", "date": "09/09/2025"},
            {"name": "Debbie Garner", "date": "09/09/2025"},
            {"name": "Patti Franklin", "date": "09/09/2025"},
            {"name": "Saffie Sanyang", "date": "09/09/2025"},
            {"name": "Mellissa Forbes", "date": "09/09/2025"},
            {"name": "Jennifer Crouch", "date": "09/09/2025"},
            {"name": "Edward Duane Jaramillo", "date": "09/09/2025"},
            {"name": "Jennifer Atchison Hunter", "date": "09/09/2025"},
            {"name": "Amanda Greene", "date": "09/09/2025"},
            {"name": "Maria Elena Mirador", "date": "09/09/2025"},
            {"name": "Leanne Blackburn", "date": "09/09/2025"},
            {"name": "Monique Archibald", "date": "09/09/2025"},
            {"name": "Tracy Godinez Martinez", "date": "09/09/2025"},
            {"name": "Florence Gallegos", "date": "09/09/2025"},
            {"name": "Vicki Garcia", "date": "09/09/2025"},
            {"name": "Lois schroeder", "date": "09/09/2025"},
            {"name": "trudi coker", "date": "09/09/2025"},
            {"name": "Sonya Blake", "date": "09/09/2025"},
            {"name": "Christina Swetman", "date": "09/09/2025"},
            {"name": "Michelle Pahnke-Kearney", "date": "09/09/2025"},
            {"name": "Ashley James", "date": "09/09/2025"},
            {"name": "Pilista Koech", "date": "09/09/2025"},
            {"name": "Claudia Wright", "date": "09/09/2025"},
            {"name": "Rebecca Herzog", "date": "09/09/2025"},
            {"name": "Kimberlina Lira", "date": "09/09/2025"},
            {"name": "Leslie Williams", "date": "09/09/2025"},
            {"name": "Phyllis Masoni", "date": "09/08/2025"},
            {"name": "Chi Pedigo", "date": "09/08/2025"},
            {"name": "Angie Dee Stone", "date": "09/08/2025"},
            {"name": "Ida VigilCruz", "date": "09/08/2025"},
            {"name": "Shirley Smith", "date": "09/08/2025"},
            {"name": "Amber Rucker", "date": "09/08/2025"},
            {"name": "Lorena powers", "date": "09/08/2025"},
            {"name": "Justin Barke", "date": "09/08/2025"},
            {"name": "Francesca Leon", "date": "09/08/2025"},
            {"name": "Chrissy Kay", "date": "08/18/2025"},
            {"name": "Monica Diaz", "date": "08/18/2025"},
            {"name": "Julie Singletary", "date": "08/18/2025"},
            {"name": "Nicole Shelhammer", "date": "08/18/2025"},
            {"name": "Layna Simms", "date": "08/18/2025"},
            {"name": "Lacee Barna-Bessette", "date": "08/18/2025"},
            {"name": "Karina Rivera Castel", "date": "08/18/2025"},
            {"name": "Christine Wagers", "date": "08/18/2025"},
            {"name": "Maria Gonzalez", "date": "08/18/2025"},
            {"name": "Muzette Garcia", "date": "08/18/2025"},
            {"name": "Noma Sibanda", "date": "08/18/2025"},
            {"name": "Elizabeth A. Armstrong", "date": "08/18/2025"},
            {"name": "Leticia Cota Esparza", "date": "08/18/2025"},
            {"name": "Daphanie Gurule", "date": "08/18/2025"},
            {"name": "Aeris Mobley-Jackson", "date": "08/18/2025"},
            {"name": "ladonna damron", "date": "08/18/2025"},
            {"name": "Angelica Puch", "date": "08/18/2025"},
            {"name": "Joann Slayden", "date": "08/17/2025"},
            {"name": "Lizbeth Ortiz vila", "date": "08/17/2025"},
            {"name": "Reed Arin", "date": "08/17/2025"},
            {"name": "Antonio Dersno", "date": "08/17/2025"},
            {"name": "Manda Dawn Packard", "date": "08/17/2025"},
            {"name": "Jason Beagley", "date": "08/17/2025"},
            {"name": "beatrix millek", "date": "08/17/2025"},
            {"name": "Brandy Edwards", "date": "08/17/2025"},
            {"name": "Alana Espinoza", "date": "08/17/2025"},
            {"name": "Angelica Frederick", "date": "08/17/2025"},
            {"name": "Wendy Skog", "date": "08/17/2025"},
            {"name": "Ruben Soto III", "date": "08/17/2025"},
            {"name": "Luzelena Bustos", "date": "08/17/2025"},
            {"name": "Jessica A Rothermund", "date": "08/17/2025"},
            {"name": "Sarah Roscow Trujillo", "date": "08/17/2025"},
            {"name": "Dawn michelle Barker", "date": "08/17/2025"},
            {"name": "Kelly lopez", "date": "08/17/2025"},
            {"name": "Roberta", "date": "08/17/2025"},
            {"name": "Carol Jean Martinez", "date": "08/17/2025"},
            {"name": "Kaylee Victoria Wolf", "date": "08/17/2025"},
            {"name": "Mandie Wine", "date": "08/17/2025"},
            {"name": "Jennifer Deal Bates", "date": "08/17/2025"},
            {"name": "Shalonda Andrews", "date": "08/17/2025"},
            {"name": "Rachael Bautzmann", "date": "08/17/2025"},
            {"name": "Angel Adams", "date": "08/17/2025"},
            {"name": "Joe Barrera", "date": "08/16/2025"},
            {"name": "Christina Abila", "date": "08/15/2025"},
            {"name": "Rosie Hendricks", "date": "08/15/2025"},
            {"name": "Melissa Ortiz", "date": "08/15/2025"},
            {"name": "Kimberly Holbert", "date": "08/15/2025"},
            {"name": "Gina Valdez", "date": "08/15/2025"},
            {"name": "Kimberlee D Kennedy", "date": "08/15/2025"},
            {"name": "Lola Marable", "date": "08/15/2025"},
            {"name": "Daniel Galindo", "date": "08/15/2025"},
            {"name": "Jrocc Vince", "date": "08/15/2025"},
            {"name": "shalonda Crowder", "date": "08/15/2025"},
            {"name": "Beverly Thomas", "date": "08/15/2025"},
            {"name": "Amanda Maloof", "date": "08/15/2025"},
            {"name": "Angela Weiss Howard", "date": "08/15/2025"},
            {"name": "Jikyla Harris", "date": "08/15/2025"},
            {"name": "Jeremy Richard Turney", "date": "08/15/2025"},
            {"name": "Samantha Spirit", "date": "08/14/2025"},
            {"name": "Anneliese Mann Martin", "date": "08/14/2025"},
            {"name": "Chelsie Brentlinger", "date": "08/14/2025"},
            {"name": "Desiree Atencio", "date": "08/14/2025"},
            {"name": "Brooke Nicole", "date": "08/14/2025"},
            {"name": "Jill Jantzen", "date": "08/14/2025"},
            {"name": "Sample Lead", "date": "06/17/2025"}
        ]
        
        updated_count = 0
        
        for csv_entry in csv_data:
            # Find matching lead by name (case-insensitive)
            lead = Lead.query.filter(
                db.func.lower(Lead.name) == csv_entry["name"].lower()
            ).first()
            
            if lead:
                # Add date to notes if not already present
                if not lead.notes or "Date:" not in lead.notes:
                    if lead.notes:
                        lead.notes = f"Date: {csv_entry['date']} | {lead.notes}"
                    else:
                        lead.notes = f"Date: {csv_entry['date']}"
                    updated_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'updated_count': updated_count,
            'message': f'Successfully updated {updated_count} leads with dates'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/leads', methods=['POST'])
@require_auth
def create_lead():
    """Create a new lead"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('name') or not data.get('phone'):
            return jsonify({'success': False, 'error': 'Name and phone are required'}), 400
        
        # Check for duplicates
        existing_lead = Lead.query.filter_by(phone=data['phone']).first()
        if not existing_lead:
            existing_lead = Lead.query.filter(
                db.func.lower(Lead.name) == data['name'].lower()
            ).first()
        
        if existing_lead:
            return jsonify({
                'success': False,
                'error': 'A lead with this phone number or name already exists'
            }), 400
        
        # Create new lead
        lead = Lead(
            name=data['name'],
            phone=data['phone'],
            email=data.get('email', ''),
            notes=data.get('notes', ''),
            status=data.get('status', 'new'),
            priority=data.get('priority', 'medium'),
            assigned_to=None
        )
        
        db.session.add(lead)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'lead_id': lead.id,
            'message': 'Lead created successfully'
        })
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Error creating lead: {str(e)}'
        }), 500

@app.route('/api/leads')
@require_auth
def get_leads():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    status_filter = request.args.get('status')
    assigned_filter = request.args.get('assigned_to')
    
    query = Lead.query
    
    if status_filter:
        query = query.filter(Lead.status == status_filter)
    if assigned_filter:
        query = query.filter(Lead.assigned_to == assigned_filter)
    
    leads = query.order_by(Lead.id.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'leads': [{
            'id': lead.id,
            'name': lead.name,
            'email': lead.email,
            'phone': lead.phone,
            'notes': lead.notes,
            'status': lead.status,
            'priority': lead.priority,
            'assigned_to': lead.assigned_user.name if lead.assigned_user else None,
            'assigned_to_id': lead.assigned_to,
            'created_at': lead.created_at.isoformat(),
            'updated_at': lead.updated_at.isoformat()
        } for lead in leads.items],
        'total': leads.total,
        'pages': leads.pages,
        'current_page': leads.page
    })

@app.route('/api/leads/<int:lead_id>', methods=['PUT'])
@require_auth
def update_lead(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    data = request.get_json()
    
    if 'notes' in data:
        lead.notes = data['notes']
    if 'status' in data:
        lead.status = data['status']
    if 'assigned_to' in data:
        lead.assigned_to = data['assigned_to']
    
    lead.updated_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'success': True})

# One-time notes population from CSV (column D)
@app.route('/api/admin/populate-notes-once', methods=['POST'])
@require_auth
def populate_notes_once():
    """One-time endpoint to populate notes from CSV column D"""
    try:
        # Step 1: Clear all notes
        print("Clearing all notes...")
        leads = Lead.query.all()
        for lead in leads:
            lead.notes = ''
        db.session.commit()
        print(f"Cleared notes for {len(leads)} leads")
        
        # Step 2: Process CSV data from the uploaded CSV file
        # Read the CSV file that was uploaded
        csv_file_path = '/tmp/caregiver_leads.csv'
        
        # Try to read from a known location or use embedded data
        # For now, we'll process the embedded CSV data
        # CSV format: Name, Email, Phone, Notes (column D)
        csv_data = [
            {"name": "Jrocc Vince", "email": "jroccvince@gmail.com", "phone": "+17192018374", "notes": "called and texted - FC"},
            {"name": "shalonda Crowder", "email": "lashawn.crowder1993@gmail.com", "phone": "+17193545582", "notes": "called and texted - FC, L/M 9/2 CP"},
            {"name": "Beverly Thomas", "email": "beverlyv66@gmail.com", "phone": "+17193067807", "notes": "called and texted - FC, (will call back at 330p CP 9/2)"},
            {"name": "Amanda Maloof", "email": "1love1life.4cdef@gmail.com", "phone": "+17197663382", "notes": "called and texted - FC, L/M 9/2 CP"},
            {"name": "Angela Weiss Howard", "email": "angelalivelovelaugh@gmail.com", "phone": "+12392894909", "notes": "called and texted - FC, L/M 9/2 CP"},
            {"name": "Jikyla Harris", "email": "jikylah1089@gmail.com", "phone": "+17162569421", "notes": "She has open availability except Saturday 8am-4pm, has car and DL, located in Pueblo, has 3 years caregiver of her grandmother. L/M 9/2 CP"},
            {"name": "Jeremy Richard Turney", "email": "jeremyturney5150@gmail.com", "phone": "+17193629534", "notes": "called and texted - FC, Sent application (looking for PT, took care of family member for years-9/2 CP)"},
            {"name": "Samantha Spirit", "email": "sjdani2006@gmail.com", "phone": "+17198675309", "notes": "called and texted - FC, L/M 9/2 CP"},
            {"name": "Anneliese Mann Martin", "email": "anneliesemartin@usa.net", "phone": "+17192905876", "notes": "HIRED 08/18, Quit"},
            {"name": "Edward Duane Jaramillo", "email": "duanejaramillo1@gmail.com", "phone": "+17193203142", "notes": "called and texted - FC, lives in Pueble, not interested in commute"},
            {"name": "Debbie Garner", "email": "garnerdebbie@ymail.com", "phone": "+17199949280", "notes": "called and texted - FC, L/M 9/2 CP Sent application, Exp CG, Overnights, Pueblo 9/2 CP)"},
            {"name": "Chelsie Brentlinger", "email": "Chelsiebrentlinger@gmail.com", "phone": "+17196887932", "notes": "called and texted - FC, L/M 9/2 CP voicemail says Jennett"},
            {"name": "Desiree Atencio", "email": "may61desi.com@gmail.com", "phone": "+17194824467", "notes": "called and texted - FC, L/M 9/2 CP"},
            {"name": "Brooke Nicole", "email": "bkelley000046@gmail.com", "phone": "+16064001544", "notes": "called and texted - FC, L/M 9/2 CP"},
            {"name": "Jill Jantzen", "email": "Jilljantzen@gmail.com", "phone": "+17195940678", "notes": "called and texted - FC, Sent application (looking for PT, took care of family member for years-9/2 CP)"},
            {"name": "Gina Valdez", "email": "valdezgina305@gmail.com", "phone": "+17197161091", "notes": "Replied but didn't received the call -IJ, L/M 9/2 CP"},
            {"name": "Kimberlee D Kennedy", "email": "kimkennedy284@gmail.com", "phone": "+17196272578", "notes": "Texted and called - IJ, L/M 9/2 CP"},
            {"name": "Lola Marable", "email": "lolamarable9@gmail.com", "phone": "+18508966003", "notes": "Texted and called - IJ, L/M 9/2 CP, sent application, EXP caregiver 9/2 CP"},
            {"name": "Daniel Galindo", "email": "danielgalindo032@gmail.com", "phone": "+12108478755", "notes": "not interested in private company"},
            {"name": "Kimberly Holbert", "email": "kimberly_holbert@yahoo.com", "phone": "17194660974", "notes": "Texted and called - IJ, Sent application, Exp CG, will work Denver and COS 9/2  CP"},
            {"name": "Jerry Salazar", "email": "jrtoronto2007@msn.com", "phone": "17192896350", "notes": "not comfortable with personal care and housekeeping."},
            {"name": "Sheila Vanzandt", "email": "1nyer4ever@gmail.com", "phone": "13033564156", "notes": "responded. She's going out of State for an extended period soon. She will contact when she return."},
            {"name": "Melissa Ortiz", "email": "mellyeli57@gmail.com", "phone": "17194963132", "notes": "HIRED 08/18: Terminated 08/20 NO DL"},
            {"name": "Rosie Hendricks", "email": "hendricks_rosie@yahoo.com", "phone": "17193702473", "notes": "Texted and called - IJ, L/M 9/2 CP"},
            {"name": "Christina Abila", "email": "Christinabila64@gmail.com", "phone": "17193009695", "notes": "Texted and called - IJ, Sent app, Exp CG and QMAP, part time, COS 9/2 CP"},
            {"name": "Joann Slayden", "email": "jslayden89@gmail.com", "phone": "+13109445329", "notes": "called and texted - FC, L/M 9/2 "},
            {"name": "Lizbeth Ortiz vila", "email": "lortizvila@gmail.com", "phone": "+17193444459", "notes": "called and texted - FC, Hung up?....9/2 CP"},
            {"name": "Reed Arin", "email": "arinreed.83@gmail.com", "phone": "+17196210606", "notes": "called and texted - FC, L/M 9/3 CP"},
            {"name": "Antonio Dersno", "email": "antoniodersno107@gmail.com", "phone": "+17196445840", "notes": "Works FT for trash co, took care of his mother, wants PT, $20/h, asked for some time to think it over 9/3 CP"},
            {"name": "Manda Dawn Packard", "email": "mandapackard75@gmail.com", "phone": "+17196519344", "notes": "called and texted - FC, voicemail not set up 9/3 CP"},
            {"name": "Jason Beagley", "email": "beagley69@gmail.com", "phone": "+15033809709", "notes": "not interested"},
            {"name": "beatrix millek", "email": "Bmillek@yahoo.com", "phone": "+13373537070", "notes": "Will call us back - FC, L/M 9/3 CP"},
            {"name": "Brandy Edwards", "email": "brandymedwards360@gmail.com", "phone": "+15399950611", "notes": "She has open availabilty, has car and DL, she prefers to work in COS, has 15 years caregiving experience, ok between $19-$20"},
            {"name": "Alana Espinoza", "email": "alana.moni_17@outlook.com", "phone": "+17197716711", "notes": "She's not inrerested. - FC"},
            {"name": "Angelica Frederick", "email": "angelica.fernandez0816@yahoo.com", "phone": "+17197287820", "notes": "PT (sunday 8a-5p, mon 10a-3p, tues 10a-3p), COS, 6+y exp, CNA &QMAP, wants $20-$25, L/M 9/3 CP"},
            {"name": "Wendy Skog", "email": "tickywench@gmail.com", "phone": "+17194391324", "notes": "called and texted - FC, L/M 9/3 CP"},
            {"name": "Ruben Soto III", "email": "rubensnewemail77@gmail.com", "phone": "+17192290120", "notes": "called and texted - FC, L/M 9/3 CP"},
            {"name": "Angie Dee Stone", "email": "angstone57@gmail.com", "phone": "+17196718707", "notes": "NIS"},
            {"name": "Luzelena Bustos", "email": "luzi.bustos@gmail.com", "phone": "+17192919781", "notes": "NIS"},
            {"name": "Kandis Keys", "email": "gingerredd78@gmail.com", "phone": "+17192179264", "notes": "HIRED 08/18"},
            {"name": "Elyssa Justine Pounds", "email": "eyousey011@gmail.com", "phone": "+16205184495", "notes": "Takes care of grandmother who has medicaid, wanted to sign up so she can get paid"},
            {"name": "Jessica A Rothermund", "email": "Jrother0823@gmail.com", "phone": "+17196661225", "notes": "HIRED 08/18"},
            {"name": "Sarah Roscow Trujillo", "email": "trujillo1971@gmail.com", "phone": "+16189751604", "notes": "HIRED 09/04"},
            {"name": "Dawn michelle Barker", "email": "dawnbarker97@gmail.com", "phone": "+17192443418", "notes": "called and texted - FC, L/M 9/3 CP"},
            {"name": "Philip Vigil", "email": "philipvigil1978@gmail.com", "phone": "+17193419725", "notes": "called and texted - FC, L/M 9/3 CP"},
            {"name": "Kelly lopez", "email": "kelly.lopez81@outlook.com", "phone": "+13607427833", "notes": "called and texted - FC, L/M 9/3 CP"},
            {"name": "Roberta", "email": "bervec@gmail.com", "phone": "+17197289071", "notes": "wrong number - FC"},
            {"name": "Carol Jean Martinez", "email": "carol.martinez101@icloud.com", "phone": "+14059060440", "notes": "called and texted - FC, L/M 9/3 CP"},
            {"name": "Kaylee Victoria Wolf", "email": "babyg82102@gmail.com", "phone": "+17197226871", "notes": "called and texted - FC, L/M 9/3 CP"},
            {"name": "Shirley Smith", "email": "shirleychreene891@gmail.com", "phone": "+19182919252", "notes": "Lives in Pueblo. Exp CG, currently working with another agency"},
            {"name": "Mandie Wine", "email": "mandawine7@gmail.com", "phone": "+17193097807", "notes": "called and texted - FC, L/M 9/3 CP"},
            {"name": "Jennifer Deal Bates", "email": "jennabl2@yahoo.com", "phone": "+18636086447", "notes": "called and texted - FC, L/M 9/3 CP"},
            {"name": "Shalonda Andrews", "email": "shay19800308@gmail.com", "phone": "+17195571651", "notes": "She has open availabilty, has car and DL, she prefers to work in COS, has 18 years caregiving experience, she preferred to work in COS, at least $20-21, can START ASAP"},
            {"name": "Rachael Bautzmann", "email": "bautzmannrachael9@gmail.com", "phone": "+16039578939", "notes": "Hired"},
            {"name": "Angel Adams", "email": "sikkle53@gmail.com", "phone": "+17193326915", "notes": "IJ - Replied message that she's in Church right now. She'll available for phone screening on Monday after 1pm., 9/3 will cb after 2:30p"},
            {"name": "Joe Barrera", "email": "jjbarr46@gmail.com", "phone": "+17194327247", "notes": "Not intrested - IJ"},
            {"name": "Chrissy Kay", "email": "Christalkay52@gmail.com", "phone": "+17205278731", "notes": "IJ -She's not available today 8/24. She'll be available for a phone conversation tomorrow 8/25 at noon. L/M 9/3 CP"},
            {"name": "Monica Diaz", "email": "nanibooboo23@gmail.com", "phone": "+17195691884", "notes": "Not intrested - IJ"},
            {"name": "Julie Singletary", "email": "julzd12c@gmail.com", "phone": "+17196296958", "notes": "Texted and called -IJ, L/M 9/3 CP"},
            {"name": "Nicole Shelhammer", "email": "shelhammer14@gmail.com", "phone": "+17193200388", "notes": "IJ- availability Full time, Weekend and Holiday. She volunteered at nursing homes and willing to learn taking care of seniors. She's ok with personal care task. Have reliable transportation, a valid driver's license, Prefer COS. The candidate confirmed they could pass a background check but had a DUI in 2022, which is now resolved. She can start as early as possible."},
            {"name": "Layna Simms", "email": "ladyjane01sim11lay@yahoo.com", "phone": "+17194596642", "notes": "CNA trained, FT, in chool for psychiatry, quoted $20/hr, sent application 9/3 CP"},
            {"name": "Lacee Barna-Bessette", "email": "lp.ny327@aol.com", "phone": "+15188219082", "notes": "IJ- She can do Full time, weekend, holiday, location COS, have DL, 12 years of working with seniors  no certificate, she can take care of the seniors and also housekeeping but can't lift them.."},
            {"name": "Karina Rivera Castel", "email": "karcas2006@gmail.com", "phone": "+17192167318", "notes": "Texted and called -IJ, L/M 9/3 CP"},
            {"name": "Christine Wagers", "email": "missyb622@yahoo.com", "phone": "+17205195041", "notes": " She can do full time, also available to work holidays and weekends, has reliable transportation, a valid driver's license, and is comfortable working in Colorado Springs. Ok with Personal care task.. William to learn.. have personal experience with a family member who has Alzheimer's and also has diabetes. Sent her the Application."},
            {"name": "Maria Gonzalez", "email": "mgpeglezc08@outlook.com", "phone": "+17193695191", "notes": "IJ- She's looking for full time can only work morning, day time, don't work at weekend and holiday, have DL, Can pass background, have CNA training but didn't get the certificate that time she was pregnant, ok with personal care, Right not she's working as caregiver's."},
            {"name": "Muzette Garcia", "email": "garciamuzette3@gmail.com", "phone": "+17196459088", "notes": "texted and called -IJ, 9/3 Disconnected? CP"},
            {"name": "Noma Sibanda", "email": "nomanyabadza123@gmail.com", "phone": "7192332421", "notes": "Texted and called -IJ, L/M 9/3 CP"},
            {"name": "Elizabeth A. Armstrong", "email": "lizzybikes47@gmail.com", "phone": "+14793919283", "notes": "She joined other company.."},
            {"name": "Leticia Cota Esparza", "email": "lae0929@gmail.com", "phone": "+14085618220", "notes": "Texted and called -IJ, L/M 9/3 CP"},
            {"name": "Daphanie Gurule", "email": "daphanieg3@gmail.com", "phone": "+17194370152", "notes": ""},
            {"name": "Aeris Mobley-Jackson", "email": "Aerisv@yahoo.com", "phone": "+13146963632", "notes": "FT, 20y CNA Exp Sent application 09/3 CP"},
            {"name": "ladonna damron", "email": "ladonna1989johnson@gmail.com", "phone": "+17197176698", "notes": "IJ -She's available for full time, she can do weekend and holiday, she prefer COS, She can pass background check, have DL, Ok with personal care also have experience in Morning star Facility for 3years... "},
            {"name": "Jerry Davis", "email": "Jedavis7500@gmail.com", "phone": "+17193084167", "notes": "Texted and called -IJ"},
            {"name": "Angelica Puch", "email": "puchangieap@gmail.c", "phone": "+14062107486", "notes": "Sent application: Took care of mother stage 4 cancer and grandmother"},
            {"name": "Ivy Streans", "email": "ivystearns2001@gmail.com", "phone": "(719) 421-9524", "notes": "IJ - She can work full time, weekend, holiday, no DL but her sister can drive her to the shift, no experience..can pass the background, ok with personal care..prefer COS."},
            {"name": "Alison Leigh", "email": "AlisonTisdal@gmail.com", "phone": "(719) 323-3389", "notes": "IJ - Alison Leigh (mentioned she's former CG with Colorado CareAssist) Availability: 2 PM – 6 PM, 3–4 days a week (Tues–Fri), not weekends, some holidays.. CNA, 14 years' experience, has driver's license, prefers to work only in COS. Pay Rate Request: $21/hr → informed her COS rates start at $19 and can go up to $23 based on experience; final discussion with management after application.. Sent her the application form."},
            {"name": "Ashley James", "email": "Honeymustard0554@gmail.com", "phone": "p:+17197745443", "notes": "L/M 09/09 CP"},
            {"name": "Pilista Koech", "email": "Pilistakoech@yahoo.com", "phone": "p:+17196512653", "notes": "Try again later, caller is unavailable 09/09 CP"},
            {"name": "Claudia Wright", "email": "cwclaudiaaz@gmail.com", "phone": "p:+16195523855", "notes": "Wrong #"},
            {"name": "Rebecca Herzog", "email": "rherzog79@gmail.com", "phone": "p:+17198226366", "notes": "MB is full 09/09 CP"},
            {"name": "Kimberlina Lira", "email": "kimberlina060599@gmail.com", "phone": "p:+17192421920", "notes": "L/M 09/09 CP"},
            {"name": "Leslie Williams", "email": "lthwilliams@gmail.com", "phone": "p:+17192462261", "notes": "Will CB, just sat in for a movie 09/09 CP"},
            {"name": "Phyllis Masoni", "email": "masoniphyllis2@gmail.com", "phone": "p:+17192525333", "notes": "Not interested"},
            {"name": "Chi Pedigo", "email": "chi.pedigo88@gmail.com", "phone": "p:+17193189944", "notes": "Rang and then disconnected 09/09 CP"},
            {"name": "Ida Vigil Cruz", "email": "vigilelaine7@gmail.com", "phone": "p:+17192899214", "notes": "CNA trained, 20+y exp, FT, has car but no DL, told her I would call her back at the end of the week after reviewing candidates CP"},
            {"name": "Amber Rucker", "email": "dawnamber@gmail.com", "phone": "p:+17196217149", "notes": "L/M 09/09 CP"},
            {"name": "Lorena powers", "email": "Lorenalori.powers@gmail.com", "phone": "p:+17192255316", "notes": "L/M 09/09 CP"},
            {"name": "Justin Barke", "email": "justinbarke1977@gmail.com", "phone": "p:+17202879002", "notes": "Not intrested - IJ 9/26"},
            {"name": "Michelle Schnapp", "email": "mrschnapp1981@gmail.com", "phone": "+17198226468", "notes": "IJ - called and texted, She's at the hospital right now expecting a call at 4pm,, Later called her several times no response yet."},
            {"name": "Meryl Somera Vaughan", "email": "somera.csab@gmail.com", "phone": "+19733427746", "notes": "called and texted no response yet - IJ. 9/26 no response"},
            {"name": "Andrea Garcia", "email": "andrearicketts87@gmail.com", "phone": "+17192467417", "notes": "Hired"},
            {"name": "Marilyn Pyles", "email": "msc0822@gmail.com", "phone": "+15409351083", "notes": "IJ - She is available for full-time caregiving after 2 PM on weekdays, all day on Saturdays, and after 2 PM on Sundays. She is comfortable working weekends and holidays, but cannot take overnight shifts due to morning "},
            {"name": "Candice Martinez", "email": "oterocollegeuser06@gmail.com", "phone": "+17192816397", "notes": "IJ - She's can do full time able to work weekends and holidays as well, Have DL and transport, prefer COS, can do personal care, Candace stated they have over 15 years of experience in healthcare and caregiving, and possess a CNA certification, although not licensed because she got covid at that time.. I sent her the Application."},
            {"name": "Patti Franklin", "email": "pattipannell08@gmail.com", "phone": "+17193309881", "notes": "IJ - Texted and called no response. 9/26 no response"},
            {"name": "Saffie Sanyang", "email": "sanyangsaffiek@yahoo.com", "phone": "+12067391725", "notes": "IJ- Availability Part-time, including holidays and weekends. The candidate has reliable transportation, a driver's license, and a CNA certification. and is open to working in Colorado. The candidate is comfortable with personal care tasks and confident about passing a background check. I sent her the application."},
            {"name": "Mellissa Forbes", "email": "mellissaforbes2@gmail.com", "phone": "+14193893063", "notes": "IJ - Texted and called no response. 9/26 no response"},
            {"name": "Jennifer Crouch", "email": "jsncrouch@yahoo.com", "phone": "+17192994798", "notes": "IJ - texted and called no response. 9/26 no response"},
            {"name": "Jennifer Atchison Hunter", "email": "thebirdtree@hotmail.com", "phone": "+17197178309", "notes": "IJ - Texted and called went on VM. Called 9/26 Payrate is not enough for her."},
            {"name": "Amanda Greene", "email": "mntmom8404@outlook.com", "phone": "+17192137728", "notes": "IJ- Availability Mon-Fri,  has reliable transportation and a valid driver's license, and is open to working in Colorado. They have experience with seniors at Right at Home in Colorado Springs, are CPR certified, and are working on their RVP for disabled children. The candidate is comfortable with personal care tasks and confident about passing a background check. I sent her the application."},
            {"name": "Maria Elena Mirador", "email": "mariaelena_mirador@yahoo.com", "phone": "+19092633728", "notes": "IJ- she confirmed she have CNA and DL. She said live in Pueblo. I informed her we give service in Boulder, Denver and Springs if she can give service there she can apply. She asked for the application form. I have sent her."},
            {"name": "Leanne Blackburn", "email": "leannelblackburn@yahoo.com", "phone": "+17199940629", "notes": "IJ - Texted and called several times, went on VM. called 9/26 no response."},
            {"name": "Monique Archibald", "email": "archibaldmonique@gmail.com", "phone": "+17196649871", "notes": "IJ- Availability full time also can do weekend and Holiday, have transportation and DL, have no certificate but personal experience working with seniors, ok with personal care task, prefer COS."},
            {"name": "Tracy Godinez Martinez", "email": "tracyanngm@gmail.com", "phone": "+17196886643", "notes": "IJ - Texted, & Called several times, didn't respond, and the mailbox is full. Called 9/26 no response."},
            {"name": "Florence Gallegos", "email": "florencegallegosbcffl@gmail.com", "phone": "+17192526824", "notes": "IJ- Called and texted, she's not able to work at COS"},
            {"name": "Vicki Garcia", "email": "Vickiloehr80@gmail.com", "phone": "+17192175730", "notes": "IJ- her availability is Mon, tues, Wednesday, she can work 3 to 7 hours a day, and on some weekends she can do holidays. She's CNA certified for 20 years, okay with personal care, has DL, and transportation. I sent her the application"},
            {"name": "Lois schroeder", "email": "Loiss1015@yahoo.com", "phone": "+14022903144", "notes": "IJ- Texted and called, went on VM. called 9/26 no response."},
            {"name": "trudi coker", "email": "trudiann2odayz@gmail.com", "phone": "+17196515324", "notes": "Received an inbound call from Candidate Trudi Coker (719) 651-5324: She is available for part-time morning shifts (around 4 hours/day), including holidays. She has experience working with seniors, holds a valid driver's license with transportation, and is comfortable with personal care tasks, but cannot lift over 50 lbs. She does not hold a CNA certificate."},
            {"name": "Sonya Blake", "email": "Bratface3237@gmail.com", "phone": "+17192587892", "notes": "IJ- Called and texted, responded. Will call her again later.. Called 9/26 no response."},
            {"name": "Christina Swetman", "email": "Steeninabean@Gmail.com", "phone": "+17193219764", "notes": "IJ- Called and texted no respond yet. later called several times no response. called 9/26 no response,"},
            {"name": "Michelle Pahnke-Kearney", "email": "michellekearney72@gmail.com", "phone": "+14235390510", "notes": "Called 10/17.. IJ - She prefers a part-time, on any day. She is available on weekends and holidays, prefers Colorado Springs, and can start on October 17th. She has her own transportation and a driver's license. Michelle has prior caregiving experience in a nursing home and home health and is comfortable performing personal care tasks. The application link will be sent to her, and she will notify us once it is submitted."},
            {"name": "Beth Purvis Parker", "email": "mlparkersmom@aol.com", "phone": "p:+12524528040", "notes": "IJ - Texted and called: She is available four days a week from 9 AM to 3 PM, including holidays, and has reliable transportation with a driver's license. They live in Colorado Springs and are comfortable working in COS, not Denver. The candidate is CNA certified, experienced in personal care task, and can pass a background check. "},
            {"name": "Francisco", "email": "bubbles915808@gmail.com", "phone": "p:+13037258628", "notes": "IJ - Texted and called: No response yet. 10/3 Called again, no response yet 10/4. Called again, no response yet 10/5.  Called again no response, 10/09"},
            {"name": "Kibrom Eritrawi", "email": "ykibrom13@yahoo.com", "phone": "p:+17202996083", "notes": "IJ - Texted and called: the candidate declined the position after receiving a higher offer of $23.50 and 25$ from another company.. "},
            {"name": "Martha L Jeffrey", "email": "mamasgirl201045@gmail.com", "phone": "p:+17209344383", "notes": "IJ - Texted and called: no response yet. 10/3 Called again no response yet 10/4 Called again no response yet 10/5.  Called again no response, 10/09"},
            {"name": "Veronica Reyes", "email": "wonkabarson@gmail.com", "phone": "p:+17192892910", "notes": "IJ - Texted and called: Right now she's out of availability like 1 or 2 days a week, she'll reach out to us in a few weeks, she said.. But not now."},
            {"name": "Jonette Hindi", "email": "heyu_3000@yahoo.com", "phone": "p:+17199300360", "notes": "IJ - Texted and called: She is available Monday–Friday from 8 AM to 4 PM while her child is in school, with occasional weekend availability but not for holidays or overnight shifts. They have reliable transportation, a valid driver's license, can work in COS, not Denver, and are comfortable with personal care tasks. "},
            {"name": "Timothy Lee Gatuma", "email": "tgatuma@gmail.com", "phone": "p:+17203384209", "notes": "IJ - Texted and called: He is available part-time Monday–Friday (12 PM–8 PM) and some weekends, with flexibility to work in Denver weekdays and Colorado Springs in weekends. he has caregiving experience with both younger and older individuals but lack CNA/HHA certification. The candidate has transportation, a driver's license, is comfortable with personal care, and can pass a background check. I sent him the application."},
            {"name": "Randy de la nuez", "email": "randyzaragoza85@gmail.com", "phone": "p:+17195658651", "notes": "IJ - Texted and called: no response yet. 10/3, 10/4 Called again no response yet 10/5.  Called again no response, 10/09."},
            {"name": "Grace Boutiqe", "email": "greisye@yahoo.com", "phone": "p:+19092526313", "notes": "IJ - Texted and called: no response yet. 10/3 Called again no response yet 10/5.  Called again no response, 10/09"},
            {"name": "LalañMenace Rivera Rivera", "email": "garza.lavaughn@gmail.com", "phone": "p:+17208823622", "notes": "IJ - Texted and called: She is available for Mon - Fri, with 18 years of caregiving experience, expressed interest in part-time weekday work in Denver, has reliable transportation, and can assist with personal care. They no longer hold a CNA license right now, cannot do overnights, but can pass a background check. i have sent her the application."},
            {"name": "Lauren Ostoich", "email": "Ostoichlauren@rocketmail.com", "phone": "p:+17192382013", "notes": "IJ - Texted and called: no response yet.  10/3, called again, no response yet. 10/5. Called again no response, 10/09"},
            {"name": "Renee Sanchez", "email": "reneesanchez25@gmail.com", "phone": "p:+17192144657", "notes": "IJ - Texted and called: She can't work in Denver and COS. "},
            {"name": "Tom A Mekan", "email": "mekandoit@gmail.com", "phone": "p:+17203241998", "notes": "IJ - Texted and called: He is available Monday through Friday, including holidays, and confirmed having reliable transportation and a valid driver's license. While they prefer working in Denver. The candidate has around 15 years of caregiving experience, primarily with personal care for family members with serious health issues, though they do not hold formal CNA or HHA certification. They are comfortable assisting with personal care task and confirmed they can pass a background check. I have sent him application."},
            {"name": "Linda Walker", "email": "lindamw_lynnw@yahoo.com", "phone": "p:+13315511029", "notes": "IJ - Texted and called: no response yet. 10/3, Called again no response 10/5.  Called again no response, 10/09"},
            {"name": "Kim Conner", "email": "kimm03.kc@gmail.com", "phone": "p:+17205396537", "notes": "IJ - Texted and called: no response yet. 10/3, Called again no response 10/5, Called again no response, 10/09"},
            {"name": "Angela Atteberry", "email": "Atteberry1981@icloud.com", "phone": "p:+18173176791", "notes": "Hired"},
            {"name": "Nyima", "email": "Nyima54@yahoo.com", "phone": "p:+16129919853", "notes": "IJ - Texted and called : no response yet. 10/3, called again no response 10/5. called again no response, 10/09."},
            {"name": "Leslie Seidenstricker", "email": "leslieseidenstricker@gmail.com", "phone": "p:+17196405409", "notes": "IJ - She is available for part-time overnight shifts on Sundays, Tuesdays, and Fridays, including holidays. Leslie has 5 years of experience, no certificate, but mentioned she knows CNA duties. She is familiar with catheters, catheter bags, gait belts, checking blood pressure, and managing oxygen tanks. She is comfortable with personal care, has a valid driver's license and car, and can work in both Denver and Colorado Springs."},
            {"name": "Patricia Segura", "email": "patsysegura16@gmail.com", "phone": "p:+17193734781", "notes": "IJ - Texted and called: She is available for a full-time weekday morning schedule. She mentioned previously that she worked for Colorado Careassist, and she used to work for Susan.. She stated she has reliable transportation, a valid driver's license, and is comfortable with personal care tasks, though she does not hold a CNA certificate but has 20 years of experience. The caregiver also confirmed she can pass a background check. I have sent her the application."},
            {"name": "Joetta Martinez", "email": "joettamartinez783@gmail.com", "phone": "p:+17195068713", "notes": "IJ - Texted and called: no response yet. 10/5. Called again no response, 10/9. No response 10/17."},
            {"name": "Carla Clay", "email": "carlaclay778@gmail.com", "phone": "p:+17194667024", "notes": "IJ - Texted abd Received an inbound call from Carla Clay,  She shared her availability as part-time, 2 to 3 days a week, Monday through Friday, and mentioned she is also available on holidays. She stated that while she does not drive herself, she has reliable transportation through her husband. Carla expressed a preference for working in Colorado Springs over Denver. She has 35 years of experience as a Certified Nursing Assistant (CNA) and also holds a QMAP certification. Carla confirmed she is comfortable with personal care tasks and can pass a background check..."},
            {"name": "Christy Ann", "email": "annbenavides409@gmail.com", "phone": "p:+17858211916", "notes": "IJ - Texted and called: no response yet. 10/5. Called again no response, 10/9. no response 10/17."},
            {"name": "Loalee Fifita", "email": "aloha.fifita@yahoo.com", "phone": "p:+17204298227", "notes": "IJ - Texted and called : no response yet. 10/5. Called again no response 10/9. called no response 10/12. no response 10/17"},
            {"name": "Desiree Baker- Perkins", "email": "dapbkl3@gmail.com", "phone": "p:+19703085079", "notes": "IJ - Texted and called: She cannot work in Denver and COS. "},
            {"name": "Sue Fisher", "email": "lilbit771@gmail.com", "phone": "p:+17192335278", "notes": "IJ - Texted and called: no response went on vm. no response 10/29"},
            {"name": "Louise Carr", "email": "Louisecarr88@gmail.com", "phone": "p:+17196394493", "notes": "IJ - Texted and called: no response, went on vm."},
            {"name": "PA Diaab", "email": "Digdug1786@gmail.com", "phone": "p:+19702034560", "notes": "IJ - Texted and called: no response went on vm."},
            {"name": "Rickee Garcia", "email": "rickeegarcia8@gmail.com", "phone": "p:+17203269614", "notes": "IJ - Texted and called: no response went on vm."},
            {"name": "Patricia Crim", "email": "patriciacrim116@gmail.com", "phone": "", "notes": "No number"},
            {"name": "Gizachew Tiku", "email": "patriciacrim116@gmail.com", "phone": "p:+17204346528", "notes": "IJ - Texted and called, he said he needs to think he will give us a call back."},
            {"name": "Nancy Fitzgerald", "email": "Tajk1987@icloud.com", "phone": "p:+17207741141", "notes": "IJ - Texted and called: no response went on vm."},
            {"name": "Melissa Craig", "email": "mizjune.mm@gmail.com", "phone": "p:+17209845253", "notes": "IJ - Texted and called: no response, went on vm."},
            {"name": "Scott Patrick Selvage", "email": "Scott18selvage@gmail.com", "phone": "p:+17195699190", "notes": "IJ - Texted and called: no response."},
            {"name": "Barbara Romero", "email": "barbara.izabella2012@gmail.com", "phone": "p:+17192928893", "notes": "IJ - Application sent. Available for part-time work any day, including weekends and holidays. She's comfortable with personal care tasks and prefers working in Colorado Springs (COS). Has experience working with seniors, has her own transportation, and holds a valid driver's license. No certification. The application has been sent to her."},
            {"name": "Courtney McGruder", "email": "rainbowbritedecino@gmail.com", "phone": "p:+19703795493", "notes": "IJ - Texted and called: no response, went on vm."},
            {"name": "Jonathan Martinez", "email": "jonathanbmartinezinc@msn.com", "phone": "p:+17202071502", "notes": "IJ - Application sent. available for part-time any day, including weekends and holidays. He's comfortable with personal care tasks, prefers working in Denver, has experience with seniors, and has his own transportation and driver's license. No certificate. "},
            {"name": "Ursula Martinez", "email": "martinezursulat6871@gmail.com", "phone": "p:+17203774935", "notes": "IJ - Texted and called: no response went on vm."},
            {"name": "Chenelle Lenae Sandoval", "email": "herrin-family@msn.com", "phone": "p:+17192914235", "notes": "IJ - Application sent. currently available for weekends and holidays as she's in the process of getting her elderly mother approved for care and adjusting her schedule accordingly. She's comfortable with personal care tasks, prefers working in Colorado Springs (COS), has experience working with seniors, and has her own transportation and a valid driver's license. She has 19 years of caregiving experience in home care and holds CPR and First Aid certifications."},
            {"name": "Veronica Contreras", "email": "luceroveronica126@gmail.com", "phone": "p:+17197171003", "notes": "IJ - Texted and called: no response went on vm."},
            {"name": "Conrad Sims Sims", "email": "crad10102@gmail.com", "phone": "p:+12176194053", "notes": "IJ - Texted and called. no response."},
            {"name": "Ayantu muleta", "email": "kiyyu2278@gmail.com", "phone": "p:+17209539330", "notes": "IJ - Texted and called. no response."},
            {"name": "Zu Hussien", "email": "zumohammed800@gmail.com", "phone": "p:+13035647161", "notes": "IJ - Application sent. available for full-time any day, including weekends and holidays. She's comfortable with personal care tasks, prefers working in Denver, has experience with seniors, and has her own transportation and driver's license. She also has a QMAP."},
            {"name": "Mary Ann Medina", "email": "maryannmedina5@gmail.com", "phone": "p:+17194157215", "notes": "IJ- Texted and called. no response."},
            {"name": "Charlotte Suomie", "email": "charlottesuomie@gmail.com", "phone": "p:+17202297717", "notes": "IJ - Application sent. available for full-time any day, including weekends and holidays. She's comfortable with personal care tasks, prefers working in Denver, has experience with seniors, uses her daughter's transportation, and has a valid driver's license. She has completed CNA training."},
            {"name": "Yah Freeman", "email": "yahfreeman80@yahoo.com", "phone": "p:+12679800420", "notes": "IJ - Texted and called. no response."},
            {"name": "Maucanda rengei", "email": "mattiashetwick@gmail.com", "phone": "p:+17207891522", "notes": "IJ- Texted and called. no response."},
            {"name": "Junie British", "email": "bjune2570@gmail.com", "phone": "p:+17192038371", "notes": "IJ -  Application sent. She has 2 or 3 days of availability. have DL and car, prefer COS, ok with personal care task, CNA trained have 20 years of experience. She asked to send her application. I have sent it. "},
            {"name": "Emma Hodo", "email": "ejh60@netzero.net", "phone": "p:+19412599547", "notes": "IJ - Texted and called: no response. 11/2 no response."},
            {"name": "Chuck Valenzuela Sr.", "email": "chuckvalenzuela88@gmail.com", "phone": "p:+16614839610", "notes": "IJ - Texted and called: no response."},
            {"name": "Georgia Mena", "email": "georgiamena@hotmail.com", "phone": "p:+17208251490", "notes": "IJ - Texted and called: She cannot speak English. She can only speak Spanish. "},
            {"name": "Earlene M. Payne", "email": "early456.ep@gmail.com", "phone": "p:+17192853294", "notes": "IJ - Texted and called she's not interested."},
            {"name": "Lyes ouagued", "email": "lyessou303030@gmail.com", "phone": "p:+17203205803", "notes": "IJ - Texted and called no response yet."},
            {"name": "Sherri A Smith", "email": "bluey4246@yahoo.com", "phone": "p:+17192377113", "notes": "IJ- Application sent. Available for part-time, can work weekends and holidays, available after 2 PM on Saturdays, comfortable with personal care tasks, prefers working in COS, has experience working with seniors, has a valid driver's license and owns a car, no certificates."},
            {"name": "Fredrick Ezeani", "email": "emekaezeani97@gmail.com", "phone": "p:+17206614321", "notes": "IJ - Application sent. Available full-time, including weekends and holidays. Comfortable with personal care tasks.Prefers working in both Denver and Colorado Springs.Has experience working with seniors.Has own transportation and a valid driver's license.Certified in QMAP and CPR, currently pursuing CNA."},
            {"name": "Tseten", "email": "Tsetenzurkhang121@hotmail.com", "phone": "p:5715819587", "notes": "IJ - Texted and called: no response. 11/1 no response"},
            {"name": "Aynlam", "email": "", "phone": "(307) 433-7122", "notes": "IJ - Application sent. Available for full-time and overnight shifts. She's comfortable with personal care tasks and prefers working in Denver. Has 10 years of experience in home care, along with CNA training and QMAP certification. She has a valid driver's license and plans to buy a car in a month but is fine taking shifts even if they're far. The application has been sent to her."},
            {"name": "Donna S Green", "email": "greenintherockies@gmail.com", "phone": "p:+17202167662", "notes": "IJ - Application sent. Available full-time Sunday to Friday, including holidays, comfortable with personal care tasks, prefers working in Denver, has experience working with seniors, has a valid driver's license and owns a car, certified in CPR."},
            {"name": "Christie Cole Phonville", "email": "womackchristie53@gmail.com", "phone": "p:+17194120883", "notes": "IJ - Application sent. She is available full-time, including weekends and holidays. She is comfortable with personal care tasks and prefers working in Colorado Springs. She has extensive experience working with seniors, holds a valid driver's license, owns a car, and is a CNA with 31 years of experience. The"},
            {"name": "Lisa Jo", "email": "happylooker@yahoo.com", "phone": "p:+17194938284", "notes": "IJ - Texted and called no response yet.11/1 no response. 11/02"},
            {"name": "J  Bowers", "email": "Bowersjeannette90@gmail.com", "phone": "p:+17738613475", "notes": "IJ - Texted and called no response yet.11/1 no response. 11/02"},
            {"name": "Leslie Mercado Gomez", "email": "gomezleslie717@gmail.com", "phone": "p:+15628891966", "notes": "IJ - Texted and called no response yet. 11/1 no response. 11/02"},
            {"name": "Kristopher Dee Koetting", "email": "Kristopher Dee Koetting", "phone": "Kristopher Dee Koetting", "notes": "IJ - Texted and called: he lives in Hawaii"},
            {"name": "Kimberly Bashaw", "email": "kimberlybashaw@gmail.com", "phone": "p:+16304083026", "notes": "IJ - Not intrested. she start's with 25$."},
            {"name": "Kelly Trevino", "email": "kellytrevino044@gmail.com", "phone": "p:+19702315168", "notes": "IJ - Not interested. Denver and COS is far for her."},
            {"name": "Tonya Gonzales", "email": "tonyagonzales3131@gmail.com", "phone": "p:+17206765012", "notes": "IJ - Texted and called: She said she's busy today! 11/1 no response yet. 11/02"},
            {"name": "Georgina Garcia", "email": "georgina48g@gmail.com", "phone": "p:+17193078621", "notes": "IJ - Texted and Called: She can't work at denver and COS."},
            {"name": "Les Dorn", "email": "leslie_dorn@comcast.net", "phone": "p:+13039124999", "notes": "IJ - Texted and called: He is not comfortable with personal care task."},
            {"name": "Chris Marez", "email": "czeram83@gmail.com", "phone": "p:+17194044066", "notes": "IJ - Texted and called: call doesn't ring. 11/02"},
            {"name": "Maura Morris", "email": "maurafay1927@gmail.com", "phone": "p:+15122298479", "notes": "IJ - Application sent. She is available for part-time work and can do weekends and holidays. She is comfortable with personal care tasks and prefers working in Colorado Springs. She has experience working with seniors, holds a valid driver's license, and owns a car. She has been a CNA for more than a decade and is currently working at an assisted living facility."},
            {"name": "Daniel Damien Peralta", "email": "peraltadaniel2@gmail.com", "phone": "p:+19705087344", "notes": "IJ - Texted and called no response yet. 11/2 no response."},
            {"name": "Steifi Otup", "email": "Otupsteifi9@gmail.com", "phone": "p:+17122546398", "notes": "IJ- Texted and called. no response. 11/2"},
            {"name": "Katherine Warner", "email": "kathyawarner2@gmail.com", "phone": "p:+17204686761", "notes": "IJ - Application sent.Available for Monday, Tuesday, Thursday, and Saturday, can do weekends and holidays. Comfortable with personal care tasks. Prefers working in Denver. Has experience working with seniors. Has a valid driver's license and owns a car. No certification."},
            {"name": "Eva Vedia", "email": "eva.vedia@icloud.com", "phone": "p:+17199313696", "notes": "IJ - texted and called. no response. 11/2"},
            {"name": "Crystal Gonzales", "email": "crystalpatience24@gmail.com", "phone": "p:+17193556444", "notes": "IJ - Texted and called. She can only lift 20 Ibs"},
            {"name": "Brian Santistevan", "email": "tk741000@gmail.com", "phone": "p:+17194061267", "notes": "IJ - Texted and called. no response. 11/2"},
            {"name": "Deborah Garcia", "email": "loyaloya6879@gmail.com", "phone": "p:+17205523458", "notes": "IJ - Texted an called no response. 11/2"},
            {"name": "Frances Mayfield-Bunch", "email": "flexbunch@gmail.com", "phone": "p:+17202706452", "notes": "FC- no response from my call sent a text instead. IJ - Application sent. Available for part-time, can do weekends and holidays. Comfortable with personal care tasks. Prefers working in Denver. Has experience working with seniors. Has a valid driver's license and owns a car. Has 25 years of caregiving experience, no certification."},
            {"name": "Selamawit Gebre", "email": "gselam2012@gmail.com", "phone": "p:+17203246726", "notes": "FC - Application form sent. Her availability is open, has own vehicle and driver's license, she has 25 years of experience as caregiver - "},
            {"name": "Birdie Inthapatha", "email": "i.birdie@yahoo.com", "phone": "p:+13039197577", "notes": "FC - no response from my call sent a text instead"},
            {"name": "Felicia Carbajal", "email": "feliciacarbajal30@gmail.com", "phone": "p:+17197782975", "notes": "IJ - She can't do Denver, COS, Boulder."},
            {"name": "Tristan Wilson", "email": "brooketalaya2001@gmail.com", "phone": "p:+17204341560", "notes": "IJ - Texted and called no response yet. 11/02 went on vm"},
            {"name": "Pat Shorty-Reyez", "email": "psweety2001@yahoo.com", "phone": "p:+15202708719", "notes": "IJ - Texted and no response yet. 11/02 went on vm"},
            {"name": "katurah kennedy", "email": "katurahkennedy7@gmail.com", "phone": "p:+17195301095", "notes": "IJ - Texted and no response yet. 11/02 went on vm"},
            {"name": "Jill Jantzen", "email": "Jilljantzen@gmail.com", "phone": "+17195940678", "notes": "IJ - She's busy at the moment. 11/02"},
            {"name": "Babyd Marty", "email": "denaya.martinez@gmail.com", "phone": "p:+17208350217", "notes": "IJ - doesn't ring. 11/02"},
            {"name": "Almae Sewell", "email": "chuuk2005@gmail.com", "phone": "", "notes": ""},
            {"name": "Drea Benally", "email": "dbena1228@gmail.com", "phone": "p:+17205741661", "notes": "IJ - Application sent. Available for full-time, can do weekends and holidays. Comfortable with personal care tasks. Prefers working in Denver. Has experience working in healthcare. Has a valid driver's license and owns a car. Has no certification."},
            {"name": "Tammy Spriggs", "email": "spriggstammy04@gmail.com", "phone": "p:+18318016728", "notes": "IJ - Texted and called. went on vm"},
            {"name": "Norma Selifis Manuel", "email": "Normamanuel884@gmail.com", "phone": "p:+17203979860", "notes": "IJ - Texted and called. 11/02"},
            {"name": "Chiffon Neal", "email": "taeneal376@gmail.com", "phone": "17209075400", "notes": "IJ - Application sent. Available for Full time can do weekends and holidays.Comfortable with personal care tasks.Prefers working in Denver.Has experience working with seniors.Owns a car, her driver's license will be done within 3 weeks.. When she get it she'll submit the application she said.Has no certificate."},
            {"name": "Amy Voss Madden", "email": "amynmadden@hotmail.com", "phone": "p:+17193525300", "notes": "IJ - Texted and called . went on vm."},
            {"name": "Watcharline Jules", "email": "charlinelovely@hotmail.com", "phone": "p:+12032435326", "notes": "IJ - Application sent. Available for full-time, can do some weekends and holidays. Comfortable with personal care tasks. Prefers working in Denver. Has experience working with seniors. Has a valid driver's license and owns a car. Has a CNA certificate."},
            {"name": "Estela Brito", "email": "britoestela13@hotmail.com", "phone": "p:+17206290343", "notes": "Ij - Texted and called. went on vm. 11/ 02."},
            {"name": "Antoinette Martinez", "email": "antartist777@gmail.com", "phone": "p:+17194937338", "notes": "IJ - Application sent. Available for full-time, can do weekends and holidays. Comfortable with personal care tasks. Prefers working in Denver and Colorado Springs. Has experience working with seniors. Has a valid driver's license and owns a car. Has no certification."},
            {"name": "Omar Mouhieddine", "email": "Mouhieddineomar6@gmail.com", "phone": "p:+17209800563", "notes": "IJ - Texted and called, no response. went on vm. 11/02"},
            {"name": "Renee Neal", "email": "Raneal1212@gmail.com", "phone": "p:+17203940172", "notes": "Ij - call doesn't ring 11/02"},
            {"name": "Tamie Hiner", "email": "livinglifettf@aol.com", "phone": "p:+17194409566", "notes": "IJ - Texted and called. went on vm. 11/ 02."},
            {"name": "Re Fainaw Kwilliam", "email": "Rufinokamier@yahoo.com", "phone": "p:+17202188397", "notes": "IJ - Texted and called. went on vm. 11/02"},
            {"name": "Victoria Garcia", "email": "toriajade2114@gmail.com", "phone": "p:+17192482826", "notes": "IJ - Application sent. Available for part-time, can do weekends and holidays. Comfortable with personal care tasks. Prefers working in Denver and Colorado Springs. Has many years of experience working with seniors. Has a valid driver's license and owns a car. Has a CPR card."},
            {"name": "Dorette Johnson", "email": "dorettejohnsonsample@gmail.com", "phone": "p:+17196534249", "notes": "IJ - Texted and called, no response yet. 11/02"},
            {"name": "Melissa Romero", "email": "melorissa2015@gmail.com", "phone": "p:+13035642193", "notes": "IJ - Texted"},
            {"name": "Lena Rowen", "email": "Lena.pacheco78@rocketmail.com", "phone": "p:+13035017069", "notes": "IJ - Texted"},
            {"name": "Susan Thorp", "email": "thorpsusan6@gmail.com", "phone": "p:+17193009888", "notes": "IJ - Texted"},
            {"name": "Collette Taylor,pete", "email": "collettetaylor7789@gmail.com", "phone": "p:+17194292297", "notes": "IJ - Texted"},
            {"name": "Josephine Nicole Adams", "email": "adamdfam.0607@gmail.com", "phone": "p:+17197786217", "notes": ""},
            {"name": "Daniel Kale", "email": "danielkale62@gmail.com", "phone": "p:+17202246356", "notes": ""},
            {"name": "Isaiah Jamel Lucas", "email": "Imonster85@icloud.com", "phone": "p:+17209969270", "notes": ""},
            {"name": "Elizabeth Sevidal", "email": "ursulabeth1954@icloud.com", "phone": "p:+17204299720", "notes": ""},
            {"name": "Shelby Fetzer", "email": "sfetzer67@gmail.com", "phone": "p:+19705906105", "notes": ""},
            {"name": "Kuilima Lautaha", "email": "fakatoumaulupe5@gmail.com", "phone": "p:+17208292360", "notes": ""},
            {"name": "Kathy Perry", "email": "katzmeow71@yahoo.com", "phone": "p:+17202151255", "notes": ""},
        ]
        
        updated_count = 0
        not_found_count = 0
        
        for entry in csv_data:
            if not entry.get('notes'):
                continue
            
            name = entry.get('name', '').strip()
            email = entry.get('email', '').strip()
            phone = entry.get('phone', '').strip()
            notes = entry.get('notes', '').strip()
            
            # Clean phone (remove p: prefix)
            if phone.startswith('p:'):
                phone = phone[2:].strip()
            
            # Find matching lead
            lead = None
            if email:
                lead = Lead.query.filter_by(email=email).first()
            if not lead and phone:
                lead = Lead.query.filter_by(phone=phone).first()
            if not lead and name:
                lead = Lead.query.filter(db.func.lower(Lead.name) == name.lower()).first()
            
            if lead:
                lead.notes = notes
                updated_count += 1
            else:
                not_found_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'updated_count': updated_count,
            'not_found_count': not_found_count,
            'cleared_count': len(leads),
            'message': f'Successfully cleared all notes and updated notes for {updated_count} leads from CSV. {not_found_count} leads from CSV not found in database. All other leads now have blank notes.'
        })
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/leads/upload', methods=['POST'])
@require_auth
def upload_leads():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'})
    
    try:
        print(f"Upload received: {file.filename}, content type: {file.content_type}")
        
        results = None
        
        if file.filename.endswith('.zip'):
            with zipfile.ZipFile(file, 'r') as zip_file:
                for filename in zip_file.namelist():
                    if filename.endswith('.csv'):
                        csv_bytes = zip_file.read(filename)
                        csv_content = decode_csv_content(csv_bytes)
                        results = process_csv_content(csv_content)
        else:
            csv_bytes = file.read()
            csv_content = decode_csv_content(csv_bytes)
            results = process_csv_content(csv_content)
        
        # Handle both old format (int) and new format (dict)
        if isinstance(results, dict):
            leads_added = results['leads_added']
            duplicates_skipped = results['duplicates_skipped']
            empty_rows_skipped = results['empty_rows_skipped']
            rows_processed = results['rows_processed']
        else:
            # Legacy format
            leads_added = results if results else 0
            duplicates_skipped = 0
            empty_rows_skipped = 0
            rows_processed = 0
        
        # Build response message
        if leads_added > 0:
            message = f"Successfully added {leads_added} new lead{'s' if leads_added != 1 else ''}!"
            if duplicates_skipped > 0:
                message += f" ({duplicates_skipped} duplicate{'s' if duplicates_skipped != 1 else ''} skipped)"
        elif duplicates_skipped > 0:
            message = f"All leads are duplicates - {duplicates_skipped} lead{'s' if duplicates_skipped != 1 else ''} already exist in the database."
        else:
            message = "No leads were added. The file may be empty or in an unrecognized format."
        
        return jsonify({
            'success': True, 
            'leads_added': leads_added,
            'duplicates_skipped': duplicates_skipped,
            'empty_rows_skipped': empty_rows_skipped,
            'rows_processed': rows_processed,
            'message': message
        })
    
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Error uploading leads: {e}")
        print(error_trace)
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

def decode_csv_content(csv_bytes):
    """Try to decode CSV content with different encodings"""
    encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252', 'iso-8859-1']
    
    for encoding in encodings:
        try:
            # Try to decode with this encoding
            content = csv_bytes.decode(encoding)
            # If successful, return the content
            return content
        except UnicodeDecodeError:
            continue
    
    # If all encodings fail, try with error handling
    try:
        return csv_bytes.decode('utf-8', errors='replace')
    except:
        return csv_bytes.decode('latin-1', errors='replace')

def process_csv_content(csv_content):
    leads_added = 0
    rows_processed = 0
    duplicates_skipped = 0
    empty_rows_skipped = 0
    
    # Try to detect delimiter
    sample = csv_content[:1024]
    delimiter = '\t' if '\t' in sample else ','
    
    print(f"CSV Processing: Using delimiter '{delimiter}'")
    
    reader = csv.DictReader(io.StringIO(csv_content), delimiter=delimiter)
    
    # Debug: Print column names (only once)
    fieldnames_lower = {}
    if reader.fieldnames:
        print(f"CSV Columns found: {list(reader.fieldnames)}")
        # Create lowercase mapping for case-insensitive lookup
        fieldnames_lower = {k.lower().strip('"').strip("'"): k for k in reader.fieldnames}
    
    for row in reader:
        rows_processed += 1
        
        # Handle different CSV formats
        name = None
        email = None
        phone = None
        created_date_str = None
        notes_parts = []
        
        # Format 1: Facebook Lead Ads export (tab-delimited with "full name", "created_time", etc.)
        # Check for the presence of key columns that indicate this format
        has_full_name = 'full name' in fieldnames_lower or any('full name' in k.lower() for k in (reader.fieldnames or []))
        has_created_time = 'created_time' in fieldnames_lower or any('created_time' in k.lower() for k in (reader.fieldnames or []))
        
        if has_full_name or has_created_time:
            # Get the actual column key (handles quoted headers)
            full_name_key = fieldnames_lower.get('full name') or next((k for k in row.keys() if 'full name' in k.lower()), None)
            created_time_key = fieldnames_lower.get('created_time') or next((k for k in row.keys() if 'created_time' in k.lower()), None)
            email_key = fieldnames_lower.get('email') or 'email'
            phone_key = fieldnames_lower.get('phone') or 'phone'
            
            name = row.get(full_name_key, '') if full_name_key else ''
            email = row.get(email_key, '')
            phone = row.get(phone_key, '')
            created_date_str = row.get(created_time_key, '') if created_time_key else ''
            # Strip quotes and whitespace
            if name:
                name = str(name).strip().strip('"').strip("'")
            if email:
                email = str(email).strip().strip('"').strip("'")
            if phone:
                phone = str(phone).strip().strip('"').strip("'")
            if created_date_str:
                created_date_str = str(created_date_str).strip().strip('"').strip("'")
            
            # Don't add campaign info to notes - notes should be blank for new leads
        
        # Format 2: Facebook export format (with Created, Name, Email, etc.)
        elif 'Created' in row and 'Name' in row:
            name = row.get('Name', '').strip()
            email = row.get('Email', '').strip()
            phone = row.get('Phone', '').strip()
            created_date_str = row.get('Created', '').strip()
            # Don't add source/channel/form info to notes - notes should be blank for new leads
        
        # Format 3: Fallback - try generic name/email/phone columns
        else:
            name = row.get('Name', row.get('name', row.get('full name', ''))).strip()
            email = row.get('Email', row.get('email', '')).strip()
            phone = row.get('Phone', row.get('phone', '')).strip()
            created_date_str = row.get('Created', row.get('created_time', row.get('created', ''))).strip()
            # Don't add notes - notes should be blank for new leads
        
        # Skip empty rows
        if not name and not email and not phone:
            empty_rows_skipped += 1
            continue
        
        # Clean phone number (remove p: prefix if present)
        if phone and phone.startswith('p:'):
            phone = phone[2:].strip()
        
        # Parse the date
        date_received = None
        if created_date_str:
            try:
                from datetime import datetime
                # Try ISO format first (2025-10-02T04:26:32-07:00)
                if 'T' in created_date_str:
                    # Remove timezone for parsing
                    date_str_clean = created_date_str.split('T')[0]
                    date_received = datetime.strptime(date_str_clean, '%Y-%m-%d')
                else:
                    # Try Facebook date format: "10/23/2025 10:34pm"
                    date_str_clean = created_date_str.replace('pm', '').replace('am', '').strip()
                    date_received = datetime.strptime(date_str_clean, '%m/%d/%Y %H:%M')
            except Exception as e:
                date_received = None
        
        # Don't add date or any info to notes - notes should be blank for new leads
        notes = ""
        
        # Check if lead already exists (by email, phone, or name)
        existing_lead = None
        
        # First check by email (most reliable)
        if email:
            existing_lead = Lead.query.filter_by(email=email).first()
        
        # If no email match, check by phone
        if not existing_lead and phone:
            existing_lead = Lead.query.filter_by(phone=phone).first()
        
        # If still no match, check by name (case-insensitive)
        if not existing_lead and name:
            existing_lead = Lead.query.filter(
                db.func.lower(Lead.name) == name.lower()
            ).first()
        
        if existing_lead:
            duplicates_skipped += 1
            continue  # Skip duplicate leads
            
        # Create lead (new leads are never contacted and unowned)
        lead = Lead(
            name=name or 'Unknown',
            email=email or '',
            phone=phone or '',
            notes=notes or '',
            status='new',  # Never contacted
            priority='medium',
            # date_received=date_received,  # Will add back after fixing database
            assigned_to=None  # Unowned/unassigned
        )
        
        db.session.add(lead)
        leads_added += 1
    
    db.session.commit()
    print(f"CSV Processing Summary: {rows_processed} rows processed, {leads_added} leads added, {duplicates_skipped} duplicates skipped, {empty_rows_skipped} empty rows skipped")
    
    # Return detailed results for better user feedback
    return {
        'leads_added': leads_added,
        'duplicates_skipped': duplicates_skipped,
        'empty_rows_skipped': empty_rows_skipped,
        'rows_processed': rows_processed
    }

@app.route('/api/users')
@require_auth
def get_users():
    users = User.query.filter_by(is_active=True).all()
    return jsonify([{
        'id': user.id,
        'name': user.name,
        'email': user.email
    } for user in users])

@app.route('/api/users', methods=['POST'])
@require_admin
def create_user():
    data = request.get_json()
    user = User(
        name=data['name'],
        email=data['email']
    )
    db.session.add(user)
    db.session.commit()
    return jsonify({'success': True, 'user_id': user.id})

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@require_admin
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = False
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/users/<int:user_id>', methods=['PUT'])
@require_admin
def update_user(user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    
    if 'name' in data:
        user.name = data['name']
    if 'email' in data:
        user.email = data['email']
    
    db.session.commit()
    return jsonify({'success': True})

def get_beetexting_access_token():
    """Get OAuth 2.0 access token using client credentials flow"""
    client_id = os.getenv('BEETEXTING_CLIENT_ID')
    client_secret = os.getenv('BEETEXTING_CLIENT_SECRET')
    api_key = os.getenv('BEETEXTING_API_KEY')
    
    if not all([client_id, client_secret, api_key]):
        raise ValueError('BeeTexting credentials not fully configured. Need CLIENT_ID, CLIENT_SECRET, and API_KEY')
    
    # OAuth 2.0 token endpoint
    token_url = 'https://auth.beetexting.com/oauth2/token/'
    
    # Try client credentials in form body (most common for client_credentials grant)
    # Try without scope first, as some APIs don't require it for client_credentials
    token_data = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret
    }
    
    headers = {
        'x-api-key': api_key,
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json'
    }
    
    print(f"Requesting OAuth token from BeeTexting...")
    # SECURITY: Don't log sensitive credentials
    print(f"Token URL: {token_url}")

    response = requests.post(token_url, data=token_data, headers=headers, timeout=10)

    print(f"Token response status: {response.status_code}")
    # SECURITY: Don't log full response body as it may contain tokens
    
    if response.status_code == 200:
        token_info = response.json()
        access_token = token_info.get('access_token')
        if not access_token:
            raise Exception(f'No access_token in response: {response.text}')
        print(f"✅ Token obtained successfully")
        return access_token
    else:
        # Parse error response
        error_text = response.text
        try:
            error_json = response.json()
            error_msg = error_json.get('error', error_text)
            error_description = error_json.get('error_description', '')
            if error_description:
                error_msg += f' - {error_description}'
        except:
            error_msg = error_text
        
        raise Exception(f'Failed to get access token: {response.status_code} - {error_msg}')

@app.route('/api/beetexting/test', methods=['GET'])
@require_auth
def test_beetexting_connection():
    """Test BeeTexting API connection and credentials"""
    try:
        # Check environment variables
        client_id = os.getenv('BEETEXTING_CLIENT_ID')
        client_secret = os.getenv('BEETEXTING_CLIENT_SECRET')
        api_key = os.getenv('BEETEXTING_API_KEY')
        from_number = os.getenv('BEETEXTING_FROM_NUMBER')
        
        missing = []
        if not client_id:
            missing.append('BEETEXTING_CLIENT_ID')
        if not client_secret:
            missing.append('BEETEXTING_CLIENT_SECRET')
        if not api_key:
            missing.append('BEETEXTING_API_KEY')
        if not from_number:
            missing.append('BEETEXTING_FROM_NUMBER')
        
        if missing:
            return jsonify({
                'success': False,
                'error': f'Missing environment variables: {", ".join(missing)}'
            }), 400
        
        # Test OAuth token retrieval
        try:
            access_token = get_beetexting_access_token()
            token_preview = access_token[:20] + '...' if len(access_token) > 20 else access_token
            
            return jsonify({
                'success': True,
                'message': 'BeeTexting credentials are valid',
                'config': {
                    'client_id': client_id[:10] + '...',
                    'api_key': api_key[:10] + '...',
                    'from_number': from_number,
                    'token_obtained': True,
                    'token_preview': token_preview
                }
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Failed to obtain access token: {str(e)}',
                'config': {
                    'client_id': client_id[:10] + '...',
                    'api_key': api_key[:10] + '...',
                    'from_number': from_number
                }
            }), 401
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Test failed: {str(e)}'
        }), 500

@app.route('/api/beetexting/send', methods=['POST'])
@require_auth
def send_beetexting_message():
    """Send SMS via BeeTexting API using OAuth 2.0"""
    try:
        data = request.get_json()
        phone = data.get('phone')
        message = data.get('message')
        lead_id = data.get('lead_id')
        
        if not phone or not message:
            return jsonify({'success': False, 'error': 'Phone and message are required'}), 400
        
        # Get OAuth access token
        try:
            access_token = get_beetexting_access_token()
            if not access_token:
                return jsonify({
                    'success': False,
                    'error': 'Failed to obtain access token'
                }), 500
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({
                'success': False,
                'error': f'Authentication failed: {str(e)}'
            }), 500
        
        # Clean phone number (remove non-numeric except +)
        import re
        clean_phone = re.sub(r'[^0-9+]', '', phone)
        if not clean_phone.startswith('+'):
            # Assume US number, add +1
            clean_phone = '+1' + re.sub(r'[^0-9]', '', clean_phone)
        
        # Get API URL and API key
        api_url = os.getenv('BEETEXTING_API_URL', 'https://connect.beetexting.com/prod')
        api_key = os.getenv('BEETEXTING_API_KEY')
        
        # Get sender phone number (from environment - REQUIRED)
        from_number = os.getenv('BEETEXTING_FROM_NUMBER')
        if not from_number:
            return jsonify({
                'success': False,
                'error': 'BEETEXTING_FROM_NUMBER environment variable is not set. Please set your authorized sender phone number.'
            }), 400
        
        # Ensure from number is in E.164 format (+1XXXXXXXXXX)
        if not from_number.startswith('+1') or len(from_number) != 12:
            return jsonify({
                'success': False,
                'error': f'Invalid FROM number format. Must be E.164 format (+1XXXXXXXXXX). Current: {from_number}'
            }), 400
        
        # Prepare request to BeeTexting API
        # Based on BeeTexting API docs: https://beetexting-connect-openapi.apidog.io/send-sms-21020114e0
        # Requires both x-api-key header AND Bearer token
        # Query parameters, not JSON body, so no Content-Type needed
        headers = {
            'Authorization': f'Bearer {access_token}',
            'x-api-key': api_key
        }
        
        # BeeTexting API uses query parameters, not JSON body
        params = {
            'from': from_number,
            'to': clean_phone,
            'text': message
        }
        
        # SECURITY: Don't log tokens or API keys
        print(f"Sending text from {from_number} to {clean_phone}")

        # Send to BeeTexting API
        response = requests.post(
            f'{api_url}/message/sendsms',
            headers=headers,
            params=params,
            timeout=10
        )

        print(f"BeeTexting API response: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            # Update lead notes to track the text message
            if lead_id:
                lead = Lead.query.get(lead_id)
                if lead:
                    timestamp = datetime.utcnow().strftime('%m/%d/%Y %H:%M')
                    text_note = f"\n[{timestamp}] Text sent: {message[:50]}..."
                    lead.notes = (lead.notes or '') + text_note
                    db.session.commit()
            
            return jsonify({
                'success': True,
                'result': result.get('result', 'Message delivered'),
                'message': 'Text message sent successfully'
            })
        else:
            error_msg = response.text
            error_details = {}
            try:
                error_json = response.json()
                error_msg = error_json.get('error', error_json.get('message', error_json.get('error_description', error_msg)))
                error_details = error_json
            except:
                pass
            
            # Provide more detailed error message with troubleshooting tips
            detailed_error = f'BeeTexting API returned status {response.status_code}'
            if error_msg:
                detailed_error += f': {error_msg}'
            
            # Add helpful troubleshooting message for 403 errors
            if response.status_code == 403:
                troubleshooting = (
                    "Common causes: 1) Phone number not verified/authorized for API sending, "
                    "2) Account credits/balance issues, 3) Account not fully activated, "
                    "4) API key missing send permissions. Check your BeeTexting dashboard."
                )
                detailed_error += f' - {troubleshooting}'
            
            return jsonify({
                'success': False,
                'error': f'Failed to send text: {detailed_error}',
                'status_code': response.status_code,
                'response': error_msg
            }), response.status_code
            
    except requests.exceptions.RequestException as e:
        return jsonify({
            'success': False,
            'error': f'Network error: {str(e)}'
        }), 500
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Error sending text: {str(e)}'
        }), 500

# GoFormz Integration
def get_goformz_access_token():
    """Get OAuth 2.0 access token for GoFormz API"""
    client_id = os.getenv('GOFORMZ_CLIENT_ID')
    client_secret = os.getenv('GOFORMZ_CLIENT_SECRET')
    
    if not all([client_id, client_secret]):
        raise ValueError('GoFormz credentials not configured')
    
    token_url = 'https://accounts.goformz.com/connect/token'
    
    data = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret,
        'scope': 'public_api'
    }
    
    response = requests.post(token_url, data=data)
    
    if response.status_code == 200:
        token_data = response.json()
        return token_data.get('access_token')
    else:
        raise Exception(f'Failed to get GoFormz access token: {response.text}')

def get_goformz_templates(access_token):
    """Get list of GoFormz templates to find Employee and Client Packet IDs"""
    api_url = 'https://api.goformz.com/v2/templates'
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    response = requests.get(api_url, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f'Failed to get GoFormz templates: {response.text}')

def get_goformz_users(access_token):
    """Get list of GoFormz users for form assignment"""
    api_url = 'https://api.goformz.com/v2/users'
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    response = requests.get(api_url, headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f'Failed to get GoFormz users: {response.text}')

@app.route('/api/goformz/templates', methods=['GET'])
@require_auth
def goformz_templates():
    """Get GoFormz templates for debugging/setup"""
    try:
        access_token = get_goformz_access_token()
        templates = get_goformz_templates(access_token)
        return jsonify({'success': True, 'templates': templates})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/goformz/template/<template_id>', methods=['GET'])
@require_auth
def goformz_template_detail(template_id):
    """Get detailed info about a specific template including field names"""
    try:
        access_token = get_goformz_access_token()
        
        api_url = f'https://api.goformz.com/v2/templates/{template_id}'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.get(api_url, headers=headers)
        
        if response.status_code == 200:
            template_detail = response.json()
            return jsonify({'success': True, 'template': template_detail})
        else:
            return jsonify({'success': False, 'error': f'Failed to get template: {response.text}'}), response.status_code
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/goformz/send-lead', methods=['POST'])
@require_auth
def send_lead_to_goformz():
    """Send a lead to GoFormz Employee Packet"""
    try:
        data = request.get_json()
        lead_id = data.get('lead_id')
        
        if not lead_id:
            return jsonify({'success': False, 'error': 'Lead ID is required'}), 400
        
        # Get the lead
        lead = Lead.query.get(lead_id)
        if not lead:
            return jsonify({'success': False, 'error': 'Lead not found'}), 404
        
        # Get GoFormz access token
        access_token = get_goformz_access_token()
        
        # Get Employee Packet template ID (you'll need to set this in env vars after checking templates)
        employee_template_id = os.getenv('GOFORMZ_EMPLOYEE_TEMPLATE_ID')
        
        if not employee_template_id:
            # Try to find it automatically
            templates = get_goformz_templates(access_token)
            for template in templates:
                if 'Employee Packet' in template.get('name', ''):
                    employee_template_id = template.get('id')
                    break
            
            if not employee_template_id:
                return jsonify({
                    'success': False,
                    'error': 'Employee Packet template not found. Please set GOFORMZ_EMPLOYEE_TEMPLATE_ID'
                }), 400
        
        # Get assignment user ID (required by GoFormz)
        goformz_user_id = os.getenv('GOFORMZ_USER_ID')
        
        if not goformz_user_id:
            # Auto-detect first user
            try:
                users = get_goformz_users(access_token)
                if users and len(users) > 0:
                    goformz_user_id = users[0].get('id')
                else:
                    return jsonify({
                        'success': False,
                        'error': 'No GoFormz users found. Please set GOFORMZ_USER_ID environment variable.'
                    }), 400
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': f'Failed to get GoFormz users: {str(e)}'
                }), 500
        
        # Prepare form data - create blank form initially
        # Field names must match exactly what's in the GoFormz template
        form_data = {
            'templateId': employee_template_id,
            'name': f'CCA EMPLOYEE PACKET - {lead.name}',
            'assignment': {
                'type': 'User',
                'id': goformz_user_id
            }
        }
        
        # Optional: Try to populate fields if field mapping is provided
        # You can set GOFORMZ_FIELD_MAPPING as JSON in env vars
        field_mapping = os.getenv('GOFORMZ_FIELD_MAPPING')
        if field_mapping:
            try:
                import json
                mapping = json.loads(field_mapping)
                form_data['fields'] = {}
                
                if 'name' in mapping:
                    form_data['fields'][mapping['name']] = lead.name or ''
                if 'email' in mapping:
                    form_data['fields'][mapping['email']] = lead.email or ''
                if 'phone' in mapping:
                    form_data['fields'][mapping['phone']] = lead.phone or ''
                if 'notes' in mapping and lead.notes:
                    form_data['fields'][mapping['notes']] = lead.notes
            except:
                pass  # Skip field mapping if it fails
        
        # Create form in GoFormz
        api_url = 'https://api.goformz.com/v2/formz'
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        response = requests.post(api_url, json=form_data, headers=headers)
        
        if response.status_code == 201:
            result = response.json()
            form_id = result.get('id')
            
            # Update lead notes
            timestamp = datetime.utcnow().strftime('%m/%d/%Y %H:%M')
            goformz_note = f"\n[{timestamp}] Sent to GoFormz Employee Packet (ID: {form_id})"
            lead.notes = (lead.notes or '') + goformz_note
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': 'Lead sent to GoFormz successfully',
                'form_id': form_id
            })
        else:
            return jsonify({
                'success': False,
                'error': f'GoFormz API error: {response.text}',
                'status_code': response.status_code
            }), response.status_code
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Error sending to GoFormz: {str(e)}'
        }), 500

@app.route('/api/alert-rules')
@require_auth
def get_alert_rules():
    rules = AlertRule.query.filter_by(is_active=True).all()
    return jsonify([{
        'id': rule.id,
        'name': rule.name,
        'condition': rule.condition,
        'recipients': rule.recipients
    } for rule in rules])

@app.route('/api/alert-rules', methods=['POST'])
@require_admin
def create_alert_rule():
    data = request.get_json()
    rule = AlertRule(
        name=data['name'],
        condition=data['condition'],
        recipients=data['recipients']
    )
    db.session.add(rule)
    db.session.commit()
    return jsonify({'success': True, 'rule_id': rule.id})

def auto_fetch_leads_scheduler():
    """Background scheduler to automatically fetch Facebook leads every hour"""
    while True:
        try:
            print(f"AUTO-SCHEDULER: Starting automatic lead fetch at {datetime.utcnow()}")
            leads_added = fetch_facebook_leads_enhanced()
            print(f"AUTO-SCHEDULER: Completed - added {leads_added} leads")
        except Exception as e:
            print(f"AUTO-SCHEDULER ERROR: {e}")
        
        # Wait 1 hour (3600 seconds) before next fetch
        time.sleep(3600)

def start_auto_scheduler():
    """Start the automatic lead fetching scheduler in a background thread"""
    scheduler_thread = threading.Thread(target=auto_fetch_leads_scheduler, daemon=True)
    scheduler_thread.start()
    print("AUTO-SCHEDULER: Started automatic Facebook lead fetching (every hour)")

# Ensure schema is up to date (especially for new facebook_lead_id column)
try:
    with app.app_context():
        create_tables()
except Exception as schema_error:
    print(f"Schema init warning: {schema_error}")

# =============================================================================
# WellSky Integration API - Recruiting Dashboard → WellSky Applicants
# =============================================================================

_root_wellsky_cache = {}

def _get_root_wellsky_services():
    """Load WellSky services from root directory (not recruiting local)

    Uses importlib.util to load modules directly by file path,
    avoiding conflicts with recruiting local services modules.
    """
    global _root_wellsky_cache

    if _root_wellsky_cache:
        return _root_wellsky_cache['wellsky'], _root_wellsky_cache['sync'], _root_wellsky_cache['ApplicantStatus']

    import sys as _sys
    import os as _os
    import importlib.util

    root_dir = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))

    # Load wellsky_service module directly by file path
    wellsky_path = _os.path.join(root_dir, 'services', 'wellsky_service.py')
    spec = importlib.util.spec_from_file_location("root_wellsky_service", wellsky_path)
    wellsky_module = importlib.util.module_from_spec(spec)

    # Add root to path temporarily so wellsky_service can find its dependencies
    original_path = _sys.path.copy()
    _sys.path.insert(0, root_dir)

    try:
        # CRITICAL: Add module to sys.modules BEFORE exec_module
        # This is required for @dataclass decorator to work properly
        _sys.modules['root_wellsky_service'] = wellsky_module
        spec.loader.exec_module(wellsky_module)

        # Now load recruiting_wellsky_sync which depends on wellsky_service
        # First make wellsky_service available for import
        _sys.modules['services.wellsky_service'] = wellsky_module

        sync_path = _os.path.join(root_dir, 'services', 'recruiting_wellsky_sync.py')
        sync_spec = importlib.util.spec_from_file_location("root_recruiting_wellsky_sync", sync_path)
        sync_module = importlib.util.module_from_spec(sync_spec)
        # Also add to sys.modules before exec
        _sys.modules['root_recruiting_wellsky_sync'] = sync_module
        sync_spec.loader.exec_module(sync_module)

        _root_wellsky_cache = {
            'wellsky': wellsky_module.wellsky_service,
            'sync': sync_module.recruiting_wellsky_sync,
            'ApplicantStatus': wellsky_module.ApplicantStatus
        }

        return _root_wellsky_cache['wellsky'], _root_wellsky_cache['sync'], _root_wellsky_cache['ApplicantStatus']
    finally:
        # Restore original path
        _sys.path = original_path


@app.route('/api/wellsky/sync/status')
@require_auth
def get_wellsky_sync_status():
    """Get WellSky integration status and sync summary"""
    try:
        wellsky_service, recruiting_wellsky_sync, _ = _get_root_wellsky_services()

        return jsonify({
            'status': 'ok',
            'wellsky_configured': wellsky_service.is_configured,
            'wellsky_mode': 'live' if wellsky_service.is_configured else 'mock',
            'sync_log_entries': len(recruiting_wellsky_sync.get_sync_log()),
            'recent_sync_log': recruiting_wellsky_sync.get_sync_log(limit=10),
        })
    except Exception as e:
        print(f"Error getting WellSky sync status: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


@app.route('/api/wellsky/sync/lead/<int:lead_id>', methods=['POST'])
@require_auth
def sync_lead_to_wellsky(lead_id):
    """Sync a single lead to WellSky as an applicant"""
    try:
        _, recruiting_wellsky_sync, _ = _get_root_wellsky_services()

        # Get lead from database
        lead = Lead.query.get(lead_id)
        if not lead:
            return jsonify({'success': False, 'error': 'Lead not found'}), 404

        lead_dict = {
            'id': lead.id,
            'name': lead.name,
            'email': lead.email,
            'phone': lead.phone,
            'status': lead.status,
            'notes': lead.notes,
            'source': lead.source,
            'assigned_to': lead.assigned_to,
            'created_at': lead.created_at.isoformat() if lead.created_at else None,
        }

        # Sync to WellSky
        success, applicant, message = recruiting_wellsky_sync.sync_lead_to_applicant(lead_dict)

        return jsonify({
            'success': success,
            'message': message,
            'lead_id': lead_id,
            'applicant': applicant.to_dict() if applicant else None,
        })
    except Exception as e:
        print(f"Error syncing lead {lead_id} to WellSky: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/wellsky/sync/all-leads', methods=['POST'])
@require_auth
def sync_all_leads_to_wellsky():
    """Sync all active leads to WellSky as applicants"""
    try:
        _, recruiting_wellsky_sync, _ = _get_root_wellsky_services()

        # Get all leads (excluding terminal statuses)
        leads = Lead.query.filter(
            ~Lead.status.in_(['rejected', 'withdrawn', 'no_show', 'unresponsive'])
        ).all()

        lead_dicts = [{
            'id': lead.id,
            'name': lead.name,
            'email': lead.email,
            'phone': lead.phone,
            'status': lead.status,
            'notes': lead.notes,
            'source': lead.source,
            'assigned_to': lead.assigned_to,
            'created_at': lead.created_at.isoformat() if lead.created_at else None,
        } for lead in leads]

        # Run sync
        results = recruiting_wellsky_sync.sync_all_leads(lead_dicts)

        return jsonify({
            'success': True,
            'results': results,
        })
    except Exception as e:
        print(f"Error syncing all leads to WellSky: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/wellsky/lead/<int:lead_id>/sync-status')
@require_auth
def get_lead_wellsky_sync_status(lead_id):
    """Get WellSky sync status for a specific lead"""
    try:
        _, recruiting_wellsky_sync, _ = _get_root_wellsky_services()

        # Check lead exists
        lead = Lead.query.get(lead_id)
        if not lead:
            return jsonify({'error': 'Lead not found'}), 404

        # Get sync status
        status = recruiting_wellsky_sync.get_sync_status(str(lead_id))

        return jsonify(status)
    except Exception as e:
        print(f"Error getting WellSky sync status for lead {lead_id}: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/wellsky/lead/<int:lead_id>/status-change', methods=['POST'])
@require_auth
def notify_wellsky_lead_status_change(lead_id):
    """Notify WellSky of a lead status change"""
    try:
        _, recruiting_wellsky_sync, _ = _get_root_wellsky_services()

        # Check lead exists
        lead = Lead.query.get(lead_id)
        if not lead:
            return jsonify({'success': False, 'error': 'Lead not found'}), 404

        data = request.get_json() or {}
        new_status = data.get('status', lead.status)
        notes = data.get('notes', '')

        # Sync status change
        success, applicant, message = recruiting_wellsky_sync.sync_lead_status_change(
            str(lead_id), new_status, notes=notes
        )

        return jsonify({
            'success': success,
            'message': message,
            'lead_id': lead_id,
            'new_status': new_status,
            'applicant': applicant.to_dict() if applicant else None,
        })
    except Exception as e:
        print(f"Error syncing lead status change to WellSky: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/wellsky/applicants')
@require_auth
def get_wellsky_applicants():
    """Get applicants from WellSky"""
    try:
        wellsky_service, _, ApplicantStatus = _get_root_wellsky_services()

        status = request.args.get('status')
        limit = int(request.args.get('limit', 100))

        # Parse status if provided
        applicant_status = None
        if status:
            try:
                applicant_status = ApplicantStatus(status.lower())
            except ValueError:
                pass

        applicants = wellsky_service.get_applicants(status=applicant_status, limit=limit)

        return jsonify({
            'applicants': [a.to_dict() for a in applicants],
            'count': len(applicants),
            'wellsky_mode': 'live' if wellsky_service.is_configured else 'mock',
        })
    except Exception as e:
        print(f"Error getting WellSky applicants: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/wellsky/pipeline-summary')
@require_auth
def get_wellsky_pipeline_summary():
    """Get recruiting pipeline summary from WellSky"""
    try:
        _, recruiting_wellsky_sync, _ = _get_root_wellsky_services()

        summary = recruiting_wellsky_sync.get_pipeline_summary()

        return jsonify(summary)
    except Exception as e:
        print(f"Error getting WellSky pipeline summary: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/test')
def test():
    return jsonify({'status': 'OK', 'message': 'Flask app is running!'})

if __name__ == '__main__':
    with app.app_context():
        create_tables()
        # Start automatic lead fetching scheduler
        start_auto_scheduler()
    # SECURITY: Debug mode controlled by environment variable
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
