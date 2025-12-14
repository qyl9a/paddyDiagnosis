import json
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = 'secret_key_for_session'  # Required for login security (Change this in production)

DATA_FILE = 'data.json'

# --- HELPER FUNCTIONS ---
def load_data():
    """Reads the JSON file and returns data."""
    if not os.path.exists(DATA_FILE):
        # Fallback if file is missing
        return {"diseases": [], "symptoms": []}
    with open(DATA_FILE, 'r') as f:
        return json.load(f)

def save_data(data):
    """Writes data back to the JSON file."""
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# --- PUBLIC ROUTES ---

@app.route('/')
def homepage():
    return render_template('home.html')


@app.route('/diagnose', methods=['GET', 'POST'])
def diagnose():
@app.route('/', methods=['GET', 'POST'])
def home():
    """
    The main diagnosis page. 
    Handles both showing the form (GET) and processing results (POST).
    """
    data = load_data()
    diagnosis = None
    selected_symptoms = []
    
    if request.method == 'POST':
        # 1. Get user input (list of selected symptom IDs)
        selected_symptoms = request.form.getlist('symptoms')
        scores = []
        
        # 2. Inference Engine: Loop through all diseases in the Knowledge Base
        for disease in data['diseases']:
            # Find matching symptoms (Intersection of User Selection & Disease Rules)
            matches = [s for s in disease['symptoms'] if s in selected_symptoms]
            
            # Calculate Confidence Score %
            total_rules = len(disease['symptoms'])
            confidence = (len(matches) / total_rules) * 100 if total_rules > 0 else 0
            
            # If there is any match at all, add to results
            if confidence > 0:
                disease_copy = disease.copy()
                disease_copy['confidence'] = round(confidence, 1)
                disease_copy['match_count'] = len(matches)
                scores.append(disease_copy)
        
        # 3. Sort results: Highest confidence first
        scores.sort(key=lambda x: x['confidence'], reverse=True)
        diagnosis = scores

    return render_template('index.html', symptoms_list=data['symptoms'], diagnosis=diagnosis, selected_symptoms=selected_symptoms)

# --- ADMIN ROUTES ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Simple Admin Login Page."""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Hardcoded credentials for demonstration.
        # In a real app, use a database and hash the passwords!
        if username == 'admin' and password == 'paddy123':
            session['logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid Credentials. Please try again.')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('home'))

@app.route('/admin')
def admin_dashboard():
    """The Dashboard to view and delete rules."""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    data = load_data()
    return render_template('admin.html', data=data)

@app.route('/admin/add', methods=['POST'])
def add_disease():
    """Handles adding a new disease rule to the JSON file."""
    if not session.get('logged_in'): 
        return redirect(url_for('login'))
    
    data = load_data()
    
    # Create a unique ID based on the name (e.g., "Brown Spot" -> "brown_spot")
    new_id = request.form['name'].strip().lower().replace(' ', '_')
    
    # Construct the new rule object
    new_disease = {
        "id": new_id,
        "name": request.form['name'],
        "type": request.form['type'],
        "severity": request.form['severity'],
        "management": request.form['management'],
        # request.form.getlist gets ALL selected options from the multi-select box
        "symptoms": request.form.getlist('symptoms') 
    }
    
    data['diseases'].append(new_disease)
    save_data(data)
    
    flash(f"Rule for '{request.form['name']}' added successfully!")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete/<disease_id>')
def delete_disease(disease_id):
    """Handles deleting a rule by ID."""
    if not session.get('logged_in'): 
        return redirect(url_for('login'))
    
    data = load_data()
    
    # Filter: Keep all diseases EXCEPT the one matching disease_id
    original_count = len(data['diseases'])
    data['diseases'] = [d for d in data['diseases'] if d['id'] != disease_id]
    
    if len(data['diseases']) < original_count:
        save_data(data)
        flash('Rule deleted successfully.')
    else:
        flash('Error: Rule not found.')
    
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    # Run the app in debug mode (auto-reloads when you change code)
    app.run(debug=True)