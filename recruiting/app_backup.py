from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from datetime import datetime, timedelta
import os
import zipfile
import csv
import io
import re
from sqlalchemy import text
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from textblob import TextBlob
import json

app = Flask(__name__)
# Handle PostgreSQL URL format
database_url = os.environ.get('DATABASE_URL', 'sqlite:///caregiver_leads.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

db = SQLAlchemy(app)
CORS(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(200), nullable=False, unique=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    assigned_leads = db.relationship('Lead', backref='assigned_user', lazy=True)

class Lead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200))
    phone = db.Column(db.String(20), nullable=False)
    notes = db.Column(db.Text)
    status = db.Column(db.String(50), default='new')  # new, contacted, interested, not_interested, hired
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    assigned_to = db.Column(db.Integer, db.ForeignKey('user.id'))  # foreign key to user
    last_contact_date = db.Column(db.DateTime)
    sentiment_score = db.Column(db.Float)  # -1 to 1
    priority = db.Column(db.String(20), default='medium')  # low, medium, high
    
    # Relationships
    activities = db.relationship('Activity', backref='lead', lazy=True, cascade='all, delete-orphan')

class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('lead.id'), nullable=False)
    activity_type = db.Column(db.String(50), nullable=False)  # call, email, text, note
    description = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(100), nullable=False)

class AlertRule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    condition = db.Column(db.String(200), nullable=False)  # JSON string with conditions
    email_recipients = db.Column(db.Text, nullable=False)  # comma-separated emails
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Utility Functions
def analyze_sentiment(text):
    """Analyze sentiment of notes text"""
    if not text:
        return 0.0
    blob = TextBlob(text)
    return blob.sentiment.polarity

def extract_phone_from_text(text):
    """Extract phone number from text"""
    phone_pattern = r'[\+]?[1]?[\s\-\.]?[\(]?[0-9]{3}[\)]?[\s\-\.]?[0-9]{3}[\s\-\.]?[0-9]{4}'
    matches = re.findall(phone_pattern, text)
    return matches[0] if matches else None

def send_email_alert(recipients, subject, body):
    """Send email alert to recipients"""
    try:
        smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.environ.get('SMTP_PORT', '587'))
        email_user = os.environ.get('EMAIL_USER')
        email_password = os.environ.get('EMAIL_PASSWORD')
        
        if not email_user or not email_password:
            print("Email credentials not configured")
            return False
            
        msg = MIMEMultipart()
        msg['From'] = email_user
        msg['Subject'] = subject
        
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(email_user, email_password)
        
        for recipient in recipients:
            msg['To'] = recipient
            text = msg.as_string()
            server.sendmail(email_user, recipient, text)
        
        server.quit()
        return True
    except Exception as e:
        print(f"Email sending failed: {e}")
        return False

def check_alert_rules(lead):
    """Check if lead triggers any alert rules"""
    rules = AlertRule.query.filter_by(is_active=True).all()
    
    for rule in rules:
        try:
            conditions = json.loads(rule.condition)
            triggered = True
            
            for condition in conditions:
                field = condition.get('field')
                operator = condition.get('operator')
                value = condition.get('value')
                
                if field == 'status' and operator == 'equals':
                    if lead.status != value:
                        triggered = False
                elif field == 'days_since_contact' and operator == 'greater_than':
                    if lead.last_contact_date:
                        days_diff = (datetime.utcnow() - lead.last_contact_date).days
                        if days_diff <= value:
                            triggered = False
                    else:
                        triggered = False
                elif field == 'priority' and operator == 'equals':
                    if lead.priority != value:
                        triggered = False
            
            if triggered:
                recipients = [email.strip() for email in rule.email_recipients.split(',')]
                subject = f"Alert: {rule.name} - Lead {lead.name}"
                body = f"""
                Alert triggered for lead: {lead.name}
                Phone: {lead.phone}
                Status: {lead.status}
                Priority: {lead.priority}
                Last Contact: {lead.last_contact_date or 'Never'}
                Notes: {lead.notes or 'No notes'}
                
                Please follow up with this lead.
                """
                send_email_alert(recipients, subject, body)
                
        except Exception as e:
            print(f"Error checking alert rule {rule.name}: {e}")

# API Routes
@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Caregiver Recruitment Dashboard</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <style>
            body {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }
            .main-container {
                background: rgba(255, 255, 255, 0.95);
                border-radius: 20px;
                box-shadow: 0 20px 40px rgba(0,0,0,0.1);
                margin: 20px;
                padding: 30px;
            }
            .header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 30px;
                padding-bottom: 20px;
                border-bottom: 2px solid #f8f9fa;
            }
            .header h1 {
                color: #2c3e50;
                font-weight: 700;
                margin: 0;
            }
            .header p {
                color: #7f8c8d;
                margin: 5px 0 0 0;
            }
            .upload-btn {
                background: linear-gradient(45deg, #667eea, #764ba2);
                border: none;
                border-radius: 25px;
                padding: 10px 20px;
                color: white;
                font-weight: 600;
                transition: all 0.3s ease;
            }
            .upload-btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
                color: white;
            }
            .stats-row {
                margin-bottom: 30px;
            }
            .stats-card {
                background: linear-gradient(45deg, #667eea, #764ba2);
                color: white;
                border-radius: 15px;
                padding: 20px;
                text-align: center;
                margin-bottom: 15px;
            }
            .stats-number {
                font-size: 2.5em;
                font-weight: 700;
                margin-bottom: 5px;
            }
            .stats-label {
                font-size: 1.1em;
                opacity: 0.9;
            }
            .leads-section {
                background: white;
                border-radius: 15px;
                padding: 25px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                margin-bottom: 20px;
            }
            .section-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 20px;
                padding-bottom: 15px;
                border-bottom: 2px solid #f8f9fa;
            }
            .section-title {
                color: #2c3e50;
                font-weight: 700;
                font-size: 1.5em;
                margin: 0;
            }
            .btn-primary {
                background: linear-gradient(45deg, #667eea, #764ba2);
                border: none;
                border-radius: 25px;
                padding: 8px 20px;
                font-weight: 600;
                transition: all 0.3s ease;
            }
            .btn-primary:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
            }
            .leads-table {
                background: white;
                border-radius: 10px;
                overflow: hidden;
                box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            }
            .table-header {
                background: #f8f9fa;
                padding: 15px 20px;
                border-bottom: 2px solid #e9ecef;
                font-weight: 600;
                color: #495057;
            }
            .lead-row {
                padding: 12px 20px;
                border-bottom: 1px solid #e9ecef;
                transition: background-color 0.3s ease;
                display: flex;
                align-items: center;
                gap: 15px;
            }
            .lead-row:hover {
                background-color: #f8f9fa;
            }
            .lead-row:last-child {
                border-bottom: none;
            }
            .lead-name {
                font-weight: 700;
                color: #2c3e50;
                min-width: 150px;
                flex-shrink: 0;
            }
            .lead-email {
                color: #6c757d;
                min-width: 200px;
                flex-shrink: 0;
                font-size: 0.9em;
            }
            .lead-phone {
                color: #6c757d;
                min-width: 130px;
                flex-shrink: 0;
                font-size: 0.9em;
            }
            .lead-assignment {
                min-width: 150px;
                flex-shrink: 0;
            }
            .lead-status {
                min-width: 120px;
                flex-shrink: 0;
            }
            .lead-notes {
                color: #495057;
                font-size: 0.85em;
                flex: 1;
                min-width: 200px;
                max-width: 300px;
            }
            .notes-textarea {
                width: 100%;
                min-height: 60px;
                font-size: 0.8em;
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 4px;
                resize: vertical;
            }
            .notes-display {
                cursor: pointer;
                padding: 4px;
                border-radius: 4px;
                transition: background-color 0.2s;
            }
            .notes-display:hover {
                background-color: #f8f9fa;
            }
            .form-select-sm {
                padding: 4px 8px;
                font-size: 0.8em;
                border-radius: 4px;
                border: 1px solid #ced4da;
            }
            .status-badge {
                display: inline-block;
                padding: 2px 6px;
                border-radius: 8px;
                font-size: 0.7em;
                font-weight: 600;
                text-transform: uppercase;
            }
            .status-badge {
                display: inline-block;
                padding: 4px 8px;
                border-radius: 12px;
                font-size: 0.75em;
                font-weight: 600;
                text-transform: uppercase;
            }
            .status-new { background: #e3f2fd; color: #1976d2; }
            .status-contacted { background: #fff3e0; color: #f57c00; }
            .status-interested { background: #e8f5e8; color: #388e3c; }
            .status-hired { background: #e8f5e8; color: #2e7d32; }
            .status-not-interested { background: #ffebee; color: #d32f2f; }
            .pagination {
                justify-content: center;
                margin-top: 20px;
            }
            .page-link {
                color: #667eea;
                border-color: #667eea;
            }
            .page-link:hover {
                background-color: #667eea;
                border-color: #667eea;
                color: white;
            }
            .page-item.active .page-link {
                background-color: #667eea;
                border-color: #667eea;
            }
            .feature-cards {
                display: flex;
                gap: 15px;
                margin-top: 20px;
            }
            .feature-card {
                background: white;
                border-radius: 15px;
                padding: 20px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.1);
                transition: transform 0.3s ease, box-shadow 0.3s ease;
                border: none;
                flex: 1;
            }
            .feature-card:hover {
                transform: translateY(-5px);
                box-shadow: 0 20px 40px rgba(0,0,0,0.15);
            }
            .feature-icon {
                font-size: 2em;
                margin-bottom: 10px;
                background: linear-gradient(45deg, #667eea, #764ba2);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }
            .upload-area {
                border: 2px dashed #667eea;
                border-radius: 10px;
                padding: 20px;
                text-align: center;
                background: rgba(102, 126, 234, 0.05);
                transition: all 0.3s ease;
                margin-top: 15px;
            }
            .upload-area:hover {
                background: rgba(102, 126, 234, 0.1);
                border-color: #764ba2;
            }
            .upload-icon {
                font-size: 1.5em;
                color: #667eea;
                margin-bottom: 10px;
            }
        </style>
    </head>
    <body>
        <div class="main-container">
            <div class="header">
                <div>
                    <h1><i class="fas fa-users"></i> Caregiver Recruitment Dashboard</h1>
                    <p>Manage your lead pipeline and track recruitment success</p>
                </div>
                <div>
                    <button class="btn upload-btn" id="uploadBtn">
                        <i class="fas fa-upload"></i> Upload New Leads
                    </button>
                </div>
            </div>

            <div class="stats-row">
                <div class="row">
                    <div class="col-md-3">
                        <div class="stats-card">
                            <div class="stats-number" id="totalLeads">0</div>
                            <div class="stats-label">Total Leads</div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="stats-card">
                            <div class="stats-number" id="newLeads">0</div>
                            <div class="stats-label">New Leads</div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="stats-card">
                            <div class="stats-number" id="contactedLeads">0</div>
                            <div class="stats-label">Contacted</div>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <div class="stats-card">
                            <div class="stats-number" id="hiredLeads">0</div>
                            <div class="stats-label">Hired</div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="leads-section">
                <div class="section-header">
                    <h2 class="section-title"><i class="fas fa-list"></i> All Leads</h2>
                    <div>
                        <select class="form-select" id="statusFilter" style="width: auto; display: inline-block;">
                            <option value="">All Status</option>
                            <option value="new">New</option>
                            <option value="contacted">Contacted</option>
                            <option value="interested">Interested</option>
                            <option value="hired">Hired</option>
                            <option value="not_interested">Not Interested</option>
                        </select>
                        <button class="btn btn-primary ms-2" id="refreshBtn">
                            <i class="fas fa-sync"></i> Refresh
                        </button>
                    </div>
                </div>
                
                <div class="leads-table">
                    <div class="table-header">
                        <div style="display: flex; align-items: center; gap: 15px;">
                            <div style="min-width: 150px;">Name</div>
                            <div style="min-width: 200px;">Email</div>
                            <div style="min-width: 130px;">Phone</div>
                            <div style="min-width: 150px;">Assigned To</div>
                            <div style="min-width: 120px;">Status</div>
                            <div style="flex: 1; min-width: 200px;">Notes</div>
                        </div>
                    </div>
                    <div id="leadsContainer">
                        <div class="text-center" style="padding: 40px;">
                            <i class="fas fa-spinner fa-spin fa-2x text-muted"></i>
                            <p class="text-muted mt-2">Loading leads...</p>
                        </div>
                    </div>
                </div>
                
                <nav aria-label="Leads pagination" id="paginationContainer" style="display: none;">
                    <ul class="pagination" id="pagination">
                    </ul>
                </nav>
            </div>

            <div class="feature-cards">
                <div class="feature-card">
                    <div class="feature-icon">
                        <i class="fas fa-chart-line"></i>
                    </div>
                    <h5>Analytics Dashboard</h5>
                    <p>Track lead conversion rates, sentiment analysis, and team performance metrics.</p>
                    <button class="btn btn-primary" id="analyticsBtn">
                        <i class="fas fa-chart-bar"></i> View Analytics
                    </button>
                </div>
                <div class="feature-card">
                    <div class="feature-icon">
                        <i class="fas fa-bell"></i>
                    </div>
                    <h5>Alert Management</h5>
                    <p>Set up automated email alerts for high-priority leads and follow-up reminders.</p>
                    <button class="btn btn-primary" id="alertsBtn">
                        <i class="fas fa-cog"></i> Manage Alerts
                    </button>
                </div>
                <div class="feature-card">
                    <div class="feature-icon">
                        <i class="fas fa-users-cog"></i>
                    </div>
                    <h5>Team Management</h5>
                    <p>Manage your recruitment team members and lead assignments.</p>
                    <button class="btn btn-primary" id="usersBtn">
                        <i class="fas fa-user-plus"></i> Manage Team
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
                        <div class="upload-area" id="uploadArea">
                            <div class="upload-icon">
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

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js?v=2"></script>
        <script>
            // Force refresh cache
            console.log('Dashboard loaded at:', new Date().toISOString());
            let currentPage = 1;
            let currentFilter = '';
            
            // Load initial data
            loadStats();
            loadLeads();
            
            // File upload handling
            document.getElementById('fileInput').addEventListener('change', handleFileUpload);
            
            // Button event listeners
            document.getElementById('uploadBtn').addEventListener('click', showUploadModal);
            document.getElementById('statusFilter').addEventListener('change', filterLeads);
            document.getElementById('refreshBtn').addEventListener('click', function() { loadLeads(); });
            document.getElementById('analyticsBtn').addEventListener('click', viewAnalytics);
            document.getElementById('alertsBtn').addEventListener('click', manageAlerts);
            document.getElementById('usersBtn').addEventListener('click', manageUsers);
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
                statusDiv.innerHTML = '<div class="alert alert-info"><i class="fas fa-spinner fa-spin"></i> Uploading...</div>';
                
                fetch('/api/leads/upload', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        statusDiv.innerHTML = '<div class="alert alert-success"><i class="fas fa-check"></i> Successfully uploaded ' + data.leads_added + ' leads!</div>';
                        loadStats();
                        loadLeads();
                        setTimeout(() => {
                            const modal = bootstrap.Modal.getInstance(document.getElementById('uploadModal'));
                            modal.hide();
                        }, 2000);
                    } else {
                        statusDiv.innerHTML = '<div class="alert alert-danger"><i class="fas fa-exclamation-triangle"></i> Error: ' + data.error + '</div>';
                    }
                })
                .catch(error => {
                    statusDiv.innerHTML = '<div class="alert alert-danger"><i class="fas fa-exclamation-triangle"></i> Upload failed: ' + error.message + '</div>';
                });
            }

            function loadStats() {
                fetch('/api/stats')
                    .then(response => response.json())
                    .then(data => {
                        document.getElementById('totalLeads').textContent = data.total_leads;
                        document.getElementById('newLeads').textContent = data.new_leads;
                        document.getElementById('contactedLeads').textContent = data.contacted_leads;
                        document.getElementById('hiredLeads').textContent = data.hired_leads;
                    })
                    .catch(error => console.error('Error loading stats:', error));
            }

            function loadLeads() {
                const url = '/api/leads?page=' + currentPage + '&per_page=50' + (currentFilter ? '&status=' + currentFilter : '');
                
                fetch(url)
                    .then(response => response.json())
                    .then(data => {
                        displayLeads(data.leads);
                        updatePagination(data.pages, data.current_page);
                    })
                    .catch(error => console.error('Error loading leads:', error));
            }

            function displayLeads(leads) {
                const container = document.getElementById('leadsContainer');
                
                if (leads.length === 0) {
                    container.innerHTML = '<div class="text-center py-4 text-muted">No leads found</div>';
                    return;
                }
                
                const leadsHtml = leads.map(lead => {
                    const assignedName = lead.assigned_to || 'Unassigned';
                    const notes = lead.notes || 'Click to add notes';
                    
                    return '<div class="lead-row">' +
                        '<div class="lead-name">' + lead.name + '</div>' +
                        '<div class="lead-email">' + lead.email + '</div>' +
                        '<div class="lead-phone">' + lead.phone + '</div>' +
                        '<div class="lead-assignment">' +
                            '<select class="form-select-sm" data-lead-id="' + lead.id + '" data-type="assignment">' +
                                '<option value="">Unassigned</option>' +
                                '<option value="1"' + (lead.assigned_to_id == 1 ? ' selected' : '') + '>Israt</option>' +
                                '<option value="2"' + (lead.assigned_to_id == 2 ? ' selected' : '') + '>Florisa</option>' +
                                '<option value="3"' + (lead.assigned_to_id == 3 ? ' selected' : '') + '>Cynthia</option>' +
                                '<option value="4"' + (lead.assigned_to_id == 4 ? ' selected' : '') + '>Jason</option>' +
                            '</select>' +
                        '</div>' +
                        '<div class="lead-status">' +
                            '<select class="form-select-sm" data-lead-id="' + lead.id + '" data-type="status">' +
                                '<option value="new"' + (lead.status === 'new' ? ' selected' : '') + '>New</option>' +
                                '<option value="contacted"' + (lead.status === 'contacted' ? ' selected' : '') + '>Contacted</option>' +
                                '<option value="interested"' + (lead.status === 'interested' ? ' selected' : '') + '>Interested</option>' +
                                '<option value="hired"' + (lead.status === 'hired' ? ' selected' : '') + '>Hired</option>' +
                                '<option value="not_interested"' + (lead.status === 'not_interested' ? ' selected' : '') + '>Not Interested</option>' +
                            '</select>' +
                        '</div>' +
                        '<div class="lead-notes">' +
                            '<div class="notes-display" data-lead-id="' + lead.id + '" title="Click to edit notes">' + notes + '</div>' +
                            '<textarea class="notes-textarea" style="display: none;" data-lead-id="' + lead.id + '"></textarea>' +
                        '</div>' +
                    '</div>';
                }).join('');
                
                container.innerHTML = leadsHtml;
                
                // Add event listeners
                addEventListeners(container);
            }

            function addEventListeners(container) {
                // Notes display clicks
                container.querySelectorAll('.notes-display').forEach(display => {
                    display.addEventListener('click', function() {
                        const leadId = this.getAttribute('data-lead-id');
                        editNotes(leadId, this);
                    });
                });
                
                // Textarea keydown
                container.querySelectorAll('.notes-textarea').forEach(textarea => {
                    textarea.addEventListener('keydown', function(event) {
                        if (event.key === 'Enter' && event.ctrlKey) {
                            event.preventDefault();
                            const leadId = this.getAttribute('data-lead-id');
                            saveNotes(leadId, this);
                        }
                    });
                    
                    textarea.addEventListener('blur', function() {
                        const leadId = this.getAttribute('data-lead-id');
                        saveNotes(leadId, this);
                    });
                });
                
                // Select dropdowns
                container.querySelectorAll('select[data-lead-id]').forEach(select => {
                    select.addEventListener('change', function() {
                        const leadId = this.getAttribute('data-lead-id');
                        const type = this.getAttribute('data-type');
                        const value = this.value;
                        
                        if (type === 'assignment') {
                            updateAssignment(leadId, value);
                        } else if (type === 'status') {
                            updateStatus(leadId, value);
                        }
                    });
                });
            }

            function updatePagination(totalPages, currentPage) {
                const container = document.getElementById('paginationContainer');
                const pagination = document.getElementById('pagination');
                
                if (totalPages <= 1) {
                    container.style.display = 'none';
                    return;
                }
                
                container.style.display = 'block';
                
                let paginationHtml = '';
                
                if (currentPage > 1) {
                    paginationHtml += '<li class="page-item"><a class="page-link" href="#" data-page="' + (currentPage - 1) + '">Previous</a></li>';
                }
                
                for (let i = 1; i <= totalPages; i++) {
                    const activeClass = i === currentPage ? 'active' : '';
                    paginationHtml += '<li class="page-item ' + activeClass + '"><a class="page-link" href="#" data-page="' + i + '">' + i + '</a></li>';
                }
                
                if (currentPage < totalPages) {
                    paginationHtml += '<li class="page-item"><a class="page-link" href="#" data-page="' + (currentPage + 1) + '">Next</a></li>';
                }
                
                pagination.innerHTML = paginationHtml;
                
                // Add event listeners for pagination
                pagination.querySelectorAll('a[data-page]').forEach(link => {
                    link.addEventListener('click', function(e) {
                        e.preventDefault();
                        const page = parseInt(this.getAttribute('data-page'));
                        loadLeads(page);
                    });
                });
            }

            function filterLeads() {
                currentFilter = document.getElementById('statusFilter').value;
                loadLeads(1);
            }

            function editNotes(leadId, displayElement) {
                const textarea = displayElement.nextElementSibling;
                textarea.value = displayElement.textContent === 'Click to add notes' ? '' : displayElement.textContent;
                displayElement.style.display = 'none';
                textarea.style.display = 'block';
                textarea.focus();
            }

            function saveNotes(leadId, textarea) {
                const notes = textarea.value;
                const displayElement = textarea.previousElementSibling;
                
                fetch('/api/leads/' + leadId, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ notes: notes })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        displayElement.textContent = notes || 'Click to add notes';
                        displayElement.style.display = 'block';
                        textarea.style.display = 'none';
                        loadStats();
                    } else {
                        alert('Error updating notes: ' + data.error);
                    }
                })
                .catch(error => {
                    console.error('Error updating notes:', error);
                    alert('Error updating notes: ' + error.message);
                });
            }

            function updateAssignment(leadId, userId) {
                fetch('/api/leads/' + leadId, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ assigned_to: userId || null })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        loadStats();
                    } else {
                        alert('Error updating assignment: ' + data.error);
                    }
                })
                .catch(error => {
                    console.error('Error updating assignment:', error);
                    alert('Error updating assignment: ' + error.message);
                });
            }

            function updateStatus(leadId, status) {
                fetch('/api/leads/' + leadId, {
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

            function viewAnalytics() {
                alert('Analytics Dashboard - Coming Soon!\n\nThis feature will show:\n• Lead conversion rates\n• Sentiment analysis\n• Team performance metrics\n• Contact success rates');
            }

            function manageAlerts() {
                alert('Alert Management - Coming Soon!\n\nThis feature will allow you to:\n• Set up automated email alerts\n• Create follow-up reminders\n• Configure high-priority notifications\n• Manage alert rules');
            }

            function manageUsers() {
                alert('Team Management - Coming Soon!\n\nThis feature will allow you to:\n• Add/remove team members\n• Manage user permissions\n• View team performance\n• Assign lead ownership');
            }
        </script>
    </body>
    </html>
    '''

@app.route('/test')
def test():
    return jsonify({'status': 'working', 'message': 'App is running successfully!'})

@app.route('/api/leads', methods=['GET'])
def get_leads():
    """Get all leads with optional filtering"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    status_filter = request.args.get('status')
    assigned_filter = request.args.get('assigned_to')
    
    query = Lead.query
    
    if status_filter:
        query = query.filter(Lead.status == status_filter)
    if assigned_filter:
        query = query.filter(Lead.assigned_to == assigned_filter)
    
    # Order by original CSV order (newest first by ID)
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
            'updated_at': lead.updated_at.isoformat(),
            'last_contact_date': lead.last_contact_date.isoformat() if lead.last_contact_date else None,
            'sentiment_score': lead.sentiment_score,
            'activity_count': len(lead.activities)
        } for lead in leads.items],
        'total': leads.total,
        'pages': leads.pages,
        'current_page': page
    })

@app.route('/api/leads/<int:lead_id>', methods=['GET'])
def get_lead(lead_id):
    """Get specific lead with activities"""
    lead = Lead.query.get_or_404(lead_id)
    activities = Activity.query.filter_by(lead_id=lead_id).order_by(Activity.created_at.desc()).all()
    
    return jsonify({
        'lead': {
            'id': lead.id,
            'name': lead.name,
            'email': lead.email,
            'phone': lead.phone,
            'notes': lead.notes,
            'status': lead.status,
            'priority': lead.priority,
            'assigned_to': lead.assigned_to,
            'created_at': lead.created_at.isoformat(),
            'updated_at': lead.updated_at.isoformat(),
            'last_contact_date': lead.last_contact_date.isoformat() if lead.last_contact_date else None,
            'sentiment_score': lead.sentiment_score
        },
        'activities': [{
            'id': activity.id,
            'type': activity.activity_type,
            'description': activity.description,
            'created_at': activity.created_at.isoformat(),
            'created_by': activity.created_by
        } for activity in activities]
    })

@app.route('/api/leads/<int:lead_id>', methods=['PUT'])
def update_lead(lead_id):
    """Update lead information"""
    lead = Lead.query.get_or_404(lead_id)
    data = request.get_json()
    
    # Update fields
    if 'name' in data:
        lead.name = data['name']
    if 'email' in data:
        lead.email = data['email']
    if 'phone' in data:
        lead.phone = data['phone']
    if 'notes' in data:
        lead.notes = data['notes']
        lead.sentiment_score = analyze_sentiment(data['notes'])
    if 'status' in data:
        lead.status = data['status']
    if 'priority' in data:
        lead.priority = data['priority']
    if 'assigned_to' in data:
        lead.assigned_to = data['assigned_to'] if data['assigned_to'] else None
    
    lead.updated_at = datetime.utcnow()
    
    # Add activity if notes were updated
    if 'notes' in data and data['notes']:
        activity = Activity(
            lead_id=lead_id,
            activity_type='note',
            description=f"Updated notes: {data['notes']}",
            created_by=data.get('updated_by', 'system')
        )
        db.session.add(activity)
    
    db.session.commit()
    
    # Check for alert triggers
    check_alert_rules(lead)
    
    return jsonify({'message': 'Lead updated successfully'})

@app.route('/api/leads/<int:lead_id>/activities', methods=['POST'])
def add_activity(lead_id):
    """Add activity to a lead"""
    lead = Lead.query.get_or_404(lead_id)
    data = request.get_json()
    
    activity = Activity(
        lead_id=lead_id,
        activity_type=data['type'],
        description=data['description'],
        created_by=data['created_by']
    )
    
    db.session.add(activity)
    
    # Update last contact date if it's a contact activity
    if data['type'] in ['call', 'email', 'text']:
        lead.last_contact_date = datetime.utcnow()
    
    db.session.commit()
    
    # Check for alert triggers
    check_alert_rules(lead)
    
    return jsonify({'message': 'Activity added successfully'})

@app.route('/api/upload', methods=['POST'])
def upload_leads():
    """Upload and process zip file with leads"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not file.filename.endswith('.zip'):
        return jsonify({'error': 'File must be a zip file'}), 400
    
    try:
        # Read zip file
        zip_data = file.read()
        zip_file = zipfile.ZipFile(io.BytesIO(zip_data))
        
        leads_added = 0
        leads_updated = 0
        
        # Process each file in the zip
        for file_info in zip_file.filelist:
            if file_info.filename.endswith('.csv'):
                csv_data = zip_file.read(file_info.filename).decode('utf-8')
                # Try to detect delimiter (tab or comma)
                delimiter = '\t' if '\t' in csv_data.split('\n')[0] else ','
                csv_reader = csv.DictReader(io.StringIO(csv_data), delimiter=delimiter)
                
                for row in csv_reader:
                    # Extract data from CSV row - handle Facebook ads format
                    name = row.get('"full name"', row.get('full name', row.get('name', ''))).strip()
                    email = row.get('email', '').strip()
                    phone = row.get('phone', '').strip()
                    notes = row.get('notes', '').strip()
                    
                    # Clean phone number (remove p: prefix if present)
                    if phone.startswith('p:'):
                        phone = phone[2:].strip()
                    
                    # Try to extract phone from name field if not in phone column
                    if not phone and name:
                        phone = extract_phone_from_text(name)
                    
                    if name and phone:
                        # Check if lead already exists
                        existing_lead = Lead.query.filter_by(phone=phone).first()
                        
                        if existing_lead:
                            # Update existing lead
                            if notes and notes != existing_lead.notes:
                                existing_lead.notes = notes
                                existing_lead.sentiment_score = analyze_sentiment(notes)
                                existing_lead.updated_at = datetime.utcnow()
                                leads_updated += 1
                        else:
                            # Create new lead
                            new_lead = Lead(
                                name=name,
                                email=email,
                                phone=phone,
                                notes=notes,
                                sentiment_score=analyze_sentiment(notes)
                            )
                            db.session.add(new_lead)
                            leads_added += 1
        
        db.session.commit()
        
        return jsonify({
            'message': 'Leads processed successfully',
            'leads_added': leads_added,
            'leads_updated': leads_updated
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error processing file: {str(e)}'}), 500

@app.route('/api/analytics', methods=['GET'])
def get_analytics():
    """Get analytics data"""
    total_leads = Lead.query.count()
    
    # Status breakdown
    status_counts = db.session.query(Lead.status, db.func.count(Lead.id)).group_by(Lead.status).all()
    status_breakdown = {status: count for status, count in status_counts}
    
    # Priority breakdown
    priority_counts = db.session.query(Lead.priority, db.func.count(Lead.id)).group_by(Lead.priority).all()
    priority_breakdown = {priority: count for priority, count in priority_counts}
    
    # Recruiter performance
    recruiter_counts = db.session.query(Lead.assigned_to, db.func.count(Lead.id)).filter(Lead.assigned_to.isnot(None)).group_by(Lead.assigned_to).all()
    recruiter_performance = {recruiter: count for recruiter, count in recruiter_counts}
    
    # Sentiment analysis
    avg_sentiment = db.session.query(db.func.avg(Lead.sentiment_score)).scalar() or 0
    
    # Recent activity
    recent_activities = Activity.query.order_by(Activity.created_at.desc()).limit(10).all()
    recent_activity_data = [{
        'lead_name': activity.lead.name,
        'type': activity.activity_type,
        'description': activity.description,
        'created_at': activity.created_at.isoformat(),
        'created_by': activity.created_by
    } for activity in recent_activities]
    
    return jsonify({
        'total_leads': total_leads,
        'status_breakdown': status_breakdown,
        'priority_breakdown': priority_breakdown,
        'recruiter_performance': recruiter_performance,
        'average_sentiment': avg_sentiment,
        'recent_activities': recent_activity_data
    })

@app.route('/api/alert-rules', methods=['GET'])
def get_alert_rules():
    """Get all alert rules"""
    rules = AlertRule.query.all()
    return jsonify([{
        'id': rule.id,
        'name': rule.name,
        'condition': rule.condition,
        'email_recipients': rule.email_recipients,
        'is_active': rule.is_active,
        'created_at': rule.created_at.isoformat()
    } for rule in rules])

@app.route('/api/alert-rules', methods=['POST'])
def create_alert_rule():
    """Create new alert rule"""
    data = request.get_json()
    
    rule = AlertRule(
        name=data['name'],
        condition=data['condition'],
        email_recipients=data['email_recipients'],
        is_active=data.get('is_active', True)
    )
    
    db.session.add(rule)
    db.session.commit()
    
    return jsonify({'message': 'Alert rule created successfully'})

@app.route('/api/users', methods=['GET'])
def get_users():
    """Get all active users"""
    users = User.query.filter_by(is_active=True).all()
    return jsonify([{
        'id': user.id,
        'name': user.name,
        'email': user.email,
        'created_at': user.created_at.isoformat(),
        'lead_count': len(user.assigned_leads)
    } for user in users])

@app.route('/api/users', methods=['POST'])
def create_user():
    """Create new user"""
    data = request.get_json()
    
    # Check if email already exists
    existing_user = User.query.filter_by(email=data['email']).first()
    if existing_user:
        return jsonify({'error': 'User with this email already exists'}), 400
    
    user = User(
        name=data['name'],
        email=data['email'],
        is_active=True
    )
    
    db.session.add(user)
    db.session.commit()
    
    return jsonify({
        'message': 'User created successfully',
        'user': {
            'id': user.id,
            'name': user.name,
            'email': user.email
        }
    })

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    """Delete user (soft delete)"""
    user = User.query.get_or_404(user_id)
    
    # Check if user has assigned leads
    if user.assigned_leads:
        return jsonify({'error': 'Cannot delete user with assigned leads. Please reassign leads first.'}), 400
    
    user.is_active = False
    db.session.commit()
    
    return jsonify({'message': 'User deleted successfully'})

@app.route('/api/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    """Update user information"""
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    
    # Check if email already exists (excluding current user)
    if 'email' in data:
        existing_user = User.query.filter(User.email == data['email'], User.id != user_id).first()
        if existing_user:
            return jsonify({'error': 'User with this email already exists'}), 400
        user.email = data['email']
    
    if 'name' in data:
        user.name = data['name']
    
    db.session.commit()
    
    return jsonify({'message': 'User updated successfully'})

# Initialize database
def create_tables():
    with app.app_context():
        db.create_all()
        
        # Create default users
        if User.query.count() == 0:
            default_users = [
                User(name="Israt", email="israt@colorcareassist.com"),
                User(name="Florisa", email="florisa@coloradocareassist.com"),
                User(name="Cynthia", email="cynthia@coloradocareassist.com"),
                User(name="Jason", email="jason@coloradocareassist.com")
            ]
            
            for user in default_users:
                db.session.add(user)
        
        # Create default alert rules
        if AlertRule.query.count() == 0:
            default_rules = [
                AlertRule(
                    name="High Priority Leads",
                    condition='[{"field": "priority", "operator": "equals", "value": "high"}]',
                    email_recipients="israt@colorcareassist.com,florisa@coloradocareassist.com,cynthia@coloradocareassist.com,jason@coloradocareassist.com"
                ),
                AlertRule(
                    name="No Contact in 3 Days",
                    condition='[{"field": "days_since_contact", "operator": "greater_than", "value": 3}]',
                    email_recipients="jason@coloradocareassist.com"
                )
            ]
            
            for rule in default_rules:
                db.session.add(rule)
            
            db.session.commit()

# Initialize tables when app starts (only if needed)
# create_tables()

if __name__ == '__main__':
    # SECURITY: Debug mode controlled by environment variable
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
