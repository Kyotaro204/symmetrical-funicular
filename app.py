import sqlite3
import json
from flask import Flask, render_template, request, redirect, url_for, session
from collections import defaultdict

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this to a secure random string in production

# Database setup
def get_db():
    conn = sqlite3.connect('evaluations.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                section TEXT NOT NULL,
                teacher TEXT NOT NULL,
                scores TEXT NOT NULL,  -- JSON string of list
                comments TEXT,
                overall_average_rating REAL NOT NULL,
                overall_interpretation TEXT NOT NULL
            )
        ''')

# Initialize database on startup
init_db()

# START PAGE 
@app.route('/')
def index():
    return render_template('index.html')

# EVALUATION FORM
@app.route('/evaluation', methods=['POST'])
def evaluation():
    name = request.form.get('name')
    section = request.form.get('section')  # Now represents "Year and Section"
    return render_template('evaluation.html', name=name, section=section)

# SUBMIT AND SUMMARY 
@app.route('/submit', methods=['POST'])
def submit():
    name = request.form.get('name', '')
    section = request.form.get('section', '')  # Now represents "Year and Section"
    teacher = request.form.get('teacher', 'Not specified')
    comments = request.form.get('comments', '')

    # Scale & Interpretation function (unchanged)
    def get_rating_and_interpretation(q_score):
        scale_score = 20 + ((float(q_score) - 1) * 20)
        if 91 <= scale_score <= 100:
            interp = "Outstanding"
        elif 71 <= scale_score <= 90.9999:
            interp = "Very Satisfactory"
        elif 51 <= scale_score <= 70.9999:
            interp = "Satisfactory"
        elif 31 <= scale_score <= 50.9999:
            interp = "Fair"
        else:
            interp = "Poor"
        return round(scale_score, 4), interp

    # Collect raw scores (1-5) and compute individual ratings/interpretations
    scores = []
    question_results = []
    for i in range(1, 21):
        val = request.form.get(f'q{i}', 1)
        score_val = float(val) 
        scores.append(score_val)
        
        rating, interp = get_rating_and_interpretation(score_val)
        question_results.append({
            'qnum': i,
            'rating': rating,
            'interpretation': interp
        })

    # Compute overall average rating (raw 1-5 average)
    overall_average_rating = sum(scores) / len(scores) if scores else 0

    # Compute overall scaled score and interpretation
    individual_scaled_scores = [get_rating_and_interpretation(s)[0] for s in scores]
    overall_scaled_score = sum(individual_scaled_scores) / len(individual_scaled_scores) if individual_scaled_scores else 0
    _, overall_interpretation = get_rating_and_interpretation(overall_average_rating)  # Use average rating to get interpretation

    # Save the evaluation to the database
    with get_db() as conn:
        conn.execute('''
            INSERT INTO evaluations (name, section, teacher, scores, comments, overall_average_rating, overall_interpretation)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (name, section, teacher, json.dumps(scores), comments, round(overall_average_rating, 2), overall_interpretation))

    return render_template(
        'summary.html',
        name=name,
        section=section,
        teacher=teacher,
        comments=comments,
        question_results=question_results,
        overall_average_rating=round(overall_average_rating, 2),
        overall_interpretation=overall_interpretation
    )

# Admin Login Route
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        # Simple hardcoded check (replace with secure storage in production)
        if username == 'admin' and password == 'password':
            session['admin_logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            return render_template('admin_login.html', error='Invalid credentials')
    return render_template('admin_login.html')

# Logout Route
@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('index'))

# DASHBOARD (now protected)
@app.route('/dashboard')
def dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))  # Redirect to login if not authenticated
    
    # Load evaluations from the database
    with get_db() as conn:
        rows = conn.execute('SELECT * FROM evaluations').fetchall()
    
    # Aggregate data per teacher
    teacher_data = defaultdict(lambda: {'students': [], 'sections': set(), 'ratings': []})
    for row in rows:
        teacher = row['teacher']
        teacher_data[teacher]['students'].append(row['name'])
        teacher_data[teacher]['sections'].add(row['section'])
        teacher_data[teacher]['ratings'].append(row['overall_average_rating'])
    
    # Compute aggregated stats
    dashboard_data = []
    for teacher, data in teacher_data.items():
        num_students = len(data['students'])
        final_average_rating = sum(data['ratings']) / len(data['ratings']) if data['ratings'] else 0
        sections = ', '.join(sorted(data['sections']))
        # Compute interpretation based on final average rating
        def get_rating_and_interpretation(q_score):
            scale_score = 20 + ((float(q_score) - 1) * 20)
            if 91 <= scale_score <= 100:
                interp = "Outstanding"
            elif 71 <= scale_score <= 90.9999:
                interp = "Very Satisfactory"
            elif 51 <= scale_score <= 70.9999:
                interp = "Satisfactory"
            elif 31 <= scale_score <= 50.9999:
                interp = "Fair"
            else:
                interp = "Poor"
            return round(scale_score, 4), interp
        _, interpretation = get_rating_and_interpretation(final_average_rating)
        
        dashboard_data.append({
            'teacher': teacher,
            'num_students': num_students,
            'final_average_rating': round(final_average_rating, 2),
            'sections': sections,
            'interpretation': interpretation
        })
    
    return render_template('dashboard.html', dashboard_data=dashboard_data)

# RUN SERVER
if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)  # Allows access from other devices on the same network