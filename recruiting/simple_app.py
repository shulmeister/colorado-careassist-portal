from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import os
import zipfile
import csv
import io
from datetime import datetime
from textblob import TextBlob
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# Database configuration
if os.getenv('DATABASE_URL'):
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL').replace('postgres://', 'postgresql://')
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///leads.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    assigned_leads = db.relationship('Lead', backref='assigned_user', lazy=True)

class Lead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default='new')
    priority = db.Column(db.String(20), default='medium')
    assigned_to = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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

def create_tables():
    """Create database tables and add default users"""
    db.create_all()
    
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
                min-height: calc(100vh - 40px);
            }
            .header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 30px;
                padding-bottom: 20px;
                border-bottom: 2px solid #f0f0f0;
            }
            .header h1 {
                color: #333;
                font-weight: 700;
                margin: 0;
            }
            .header p {
                color: #666;
                margin: 5px 0 0 0;
            }
            .stats-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            .stat-card {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 25px;
                border-radius: 15px;
                text-align: center;
                box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
                transition: transform 0.3s ease;
            }
            .stat-card:hover {
                transform: translateY(-5px);
            }
            .stat-number {
                font-size: 2.5rem;
                font-weight: bold;
                margin-bottom: 10px;
            }
            .stat-label {
                font-size: 1rem;
                opacity: 0.9;
            }
            .leads-section {
                background: white;
                border-radius: 15px;
                padding: 25px;
                box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            }
            .section-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 20px;
            }
            .section-title {
                color: #333;
                font-weight: 600;
                margin: 0;
            }
            .upload-btn {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border: none;
                color: white;
                padding: 12px 25px;
                border-radius: 25px;
                font-weight: 600;
                transition: all 0.3s ease;
            }
            .upload-btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
                color: white;
            }
            .leads-table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
            }
            .leads-table th {
                background: #f8f9fa;
                padding: 15px 10px;
                text-align: left;
                font-weight: 600;
                color: #333;
                border-bottom: 2px solid #dee2e6;
            }
            .leads-table td {
                padding: 12px 10px;
                border-bottom: 1px solid #dee2e6;
                vertical-align: middle;
            }
            .leads-table tr:hover {
                background: #f8f9fa;
            }
            .form-select-sm {
                padding: 5px 10px;
                font-size: 0.9rem;
                border-radius: 5px;
                border: 1px solid #ced4da;
            }
            .notes-display {
                cursor: pointer;
                padding: 5px;
                border-radius: 3px;
                transition: background 0.2s;
            }
            .notes-display:hover {
                background: #f0f0f0;
            }
            .notes-textarea {
                width: 100%;
                min-height: 60px;
                padding: 8px;
                border: 1px solid #ced4da;
                border-radius: 5px;
                font-size: 0.9rem;
            }
            .btn-primary {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: 500;
            }
            .btn-primary:hover {
                background: linear-gradient(135deg, #5a6fd8 0%, #6a4190 100%);
                transform: translateY(-1px);
            }
            .loading {
                text-align: center;
                padding: 40px;
                color: #666;
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
                    <button class="btn upload-btn" onclick="showUploadModal()">
                        <i class="fas fa-upload"></i> Upload New Leads
                    </button>
                </div>
            </div>

            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number" id="totalLeads">0</div>
                    <div class="stat-label">Total Leads</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="newLeads">0</div>
                    <div class="stat-label">New Leads</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="contactedLeads">0</div>
                    <div class="stat-label">Contacted</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="hiredLeads">0</div>
                    <div class="stat-label">Hired</div>
                </div>
            </div>

            <div class="leads-section">
                <div class="section-header">
                    <h2 class="section-title"><i class="fas fa-list"></i> All Leads</h2>
                    <div>
                        <select class="form-select" id="statusFilter" onchange="filterLeads()" style="width: auto; display: inline-block;">
                            <option value="">All Status</option>
                            <option value="new">New</option>
                            <option value="contacted">Contacted</option>
                            <option value="interested">Interested</option>
                            <option value="hired">Hired</option>
                            <option value="not_interested">Not Interested</option>
                        </select>
                        <button class="btn btn-primary ms-2" onclick="loadLeads()">
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
                            <button class="btn btn-primary" onclick="document.getElementById('fileInput').click()">
                                <i class="fas fa-upload"></i> Choose File
                            </button>
                        </div>
                        <div id="uploadStatus" class="mt-3" style="display: none;"></div>
                    </div>
                </div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            let currentPage = 1;
            let currentFilter = '';
            
            // Load initial data
            loadStats();
            loadLeads();
            
            // File upload handling
            document.getElementById('fileInput').addEventListener('change', handleFileUpload);
            
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
                
                let leadsHtml = '<table class="leads-table"><thead><tr><th>Name</th><th>Email</th><th>Phone</th><th>Assigned To</th><th>Status</th><th>Notes</th></tr></thead><tbody>';
                
                leads.forEach(lead => {
                    const assignedName = lead.assigned_to || 'Unassigned';
                    const notes = lead.notes || 'Click to add notes';
                    
                    leadsHtml += '<tr>';
                    leadsHtml += '<td>' + lead.name + '</td>';
                    leadsHtml += '<td>' + lead.email + '</td>';
                    leadsHtml += '<td>' + lead.phone + '</td>';
                    leadsHtml += '<td>';
                    leadsHtml += '<select class="form-select-sm" onchange="updateAssignment(' + lead.id + ', this.value)">';
                    leadsHtml += '<option value="">Unassigned</option>';
                    leadsHtml += '<option value="1"' + (lead.assigned_to_id == 1 ? ' selected' : '') + '>Israt</option>';
                    leadsHtml += '<option value="2"' + (lead.assigned_to_id == 2 ? ' selected' : '') + '>Florisa</option>';
                    leadsHtml += '<option value="3"' + (lead.assigned_to_id == 3 ? ' selected' : '') + '>Cynthia</option>';
                    leadsHtml += '<option value="4"' + (lead.assigned_to_id == 4 ? ' selected' : '') + '>Jason</option>';
                    leadsHtml += '</select>';
                    leadsHtml += '</td>';
                    leadsHtml += '<td>';
                    leadsHtml += '<select class="form-select-sm" onchange="updateStatus(' + lead.id + ', this.value)">';
                    leadsHtml += '<option value="new"' + (lead.status === 'new' ? ' selected' : '') + '>New</option>';
                    leadsHtml += '<option value="contacted"' + (lead.status === 'contacted' ? ' selected' : '') + '>Contacted</option>';
                    leadsHtml += '<option value="interested"' + (lead.status === 'interested' ? ' selected' : '') + '>Interested</option>';
                    leadsHtml += '<option value="hired"' + (lead.status === 'hired' ? ' selected' : '') + '>Hired</option>';
                    leadsHtml += '<option value="not_interested"' + (lead.status === 'not_interested' ? ' selected' : '') + '>Not Interested</option>';
                    leadsHtml += '</select>';
                    leadsHtml += '</td>';
                    leadsHtml += '<td>';
                    leadsHtml += '<div class="notes-display" onclick="editNotes(' + lead.id + ', this)" title="Click to edit notes">' + notes + '</div>';
                    leadsHtml += '<textarea class="notes-textarea" style="display: none;" onblur="saveNotes(' + lead.id + ', this)"></textarea>';
                    leadsHtml += '</td>';
                    leadsHtml += '</tr>';
                });
                
                leadsHtml += '</tbody></table>';
                container.innerHTML = leadsHtml;
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
                    paginationHtml += '<li class="page-item"><a class="page-link" href="#" onclick="loadLeads(' + (currentPage - 1) + ')">Previous</a></li>';
                }
                
                for (let i = 1; i <= totalPages; i++) {
                    const activeClass = i === currentPage ? 'active' : '';
                    paginationHtml += '<li class="page-item ' + activeClass + '"><a class="page-link" href="#" onclick="loadLeads(' + i + ')">' + i + '</a></li>';
                }
                
                if (currentPage < totalPages) {
                    paginationHtml += '<li class="page-item"><a class="page-link" href="#" onclick="loadLeads(' + (currentPage + 1) + ')">Next</a></li>';
                }
                
                pagination.innerHTML = paginationHtml;
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
        </script>
    </body>
    </html>
    '''

@app.route('/api/stats')
def get_stats():
    total_leads = Lead.query.count()
    new_leads = Lead.query.filter_by(status='new').count()
    contacted_leads = Lead.query.filter_by(status='contacted').count()
    hired_leads = Lead.query.filter_by(status='hired').count()
    
    return jsonify({
        'total_leads': total_leads,
        'new_leads': new_leads,
        'contacted_leads': contacted_leads,
        'hired_leads': hired_leads
    })

@app.route('/api/leads')
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

@app.route('/api/leads/upload', methods=['POST'])
def upload_leads():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'})
    
    try:
        leads_added = 0
        
        if file.filename.endswith('.zip'):
            with zipfile.ZipFile(file, 'r') as zip_file:
                for filename in zip_file.namelist():
                    if filename.endswith('.csv'):
                        csv_content = zip_file.read(filename).decode('utf-8')
                        leads_added += process_csv_content(csv_content)
        else:
            csv_content = file.read().decode('utf-8')
            leads_added = process_csv_content(csv_content)
        
        return jsonify({'success': True, 'leads_added': leads_added})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def process_csv_content(csv_content):
    leads_added = 0
    
    # Try to detect delimiter
    sample = csv_content[:1024]
    delimiter = '\t' if '\t' in sample else ','
    
    reader = csv.DictReader(io.StringIO(csv_content), delimiter=delimiter)
    
    for row in reader:
        # Extract data from Facebook Ads format
        name = row.get('"full name"', '').strip('"')
        email = row.get('email', '').strip('"')
        phone = row.get('phone', '').strip('"')
        
        # Clean phone number (remove p: prefix)
        if phone.startswith('p:'):
            phone = phone[2:]
        
        if name and email and phone:
            # Check if lead already exists
            existing_lead = Lead.query.filter_by(phone=phone).first()
            if not existing_lead:
                lead = Lead(
                    name=name,
                    email=email,
                    phone=phone,
                    status='new',
                    priority='medium'
                )
                db.session.add(lead)
                leads_added += 1
    
    db.session.commit()
    return leads_added

@app.route('/api/users')
def get_users():
    users = User.query.filter_by(is_active=True).all()
    return jsonify([{
        'id': user.id,
        'name': user.name,
        'email': user.email
    } for user in users])

@app.route('/api/users', methods=['POST'])
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
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = False
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    
    if 'name' in data:
        user.name = data['name']
    if 'email' in data:
        user.email = data['email']
    
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/alert-rules')
def get_alert_rules():
    rules = AlertRule.query.filter_by(is_active=True).all()
    return jsonify([{
        'id': rule.id,
        'name': rule.name,
        'condition': rule.condition,
        'recipients': rule.recipients
    } for rule in rules])

@app.route('/api/alert-rules', methods=['POST'])
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

@app.route('/test')
def test():
    return jsonify({'status': 'OK', 'message': 'Flask app is running!'})

if __name__ == '__main__':
    with app.app_context():
        create_tables()
    # SECURITY: Debug mode controlled by environment variable
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")



