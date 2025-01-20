from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import mysql.connector
import face_recognition
import cv2
import numpy as np
import base64
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this to a secure key

# Database Configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'fras'
}

# Database Connection Function
def get_db_connection():
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except mysql.connector.Error as e:
        print(f"Error connecting to MySQL Platform: {e}")
        return None

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Validate input
        if not username or not password:
            flash('Username and password are required!', 'danger')
            return redirect(url_for('login'))

        # Check credentials based on ID length
        if len(username) == 6:  # Staff login
            user = authenticate_staff(username, password)
            if user:
                flash('Login successful!', 'success')
                session['staffid'] = user['staffid']
                session['name'] = user['name']
                session['user_type'] = "staff"
                return redirect(url_for('admin_home', name=user['name'], id=user['staffid']))

            else:
                flash('Invalid credentials!', 'danger')
                return redirect(url_for('login'))

        elif len(username) == 10:  # Student login
            user = authenticate_student(username, password)
            if user:
                flash('Login successful!', 'success')
                session['studentid'] = user['studentid']
                session['name'] = user['name']
                session['user_type'] = "student"
                
                return redirect(url_for('student_home', name=user['name'], id=user['studentid']))
            else:
                flash('Invalid credentials!', 'danger')
                return redirect(url_for('login'))

        flash('Invalid username length!', 'danger')
        return redirect(url_for('login'))

    return render_template('login.html')

def authenticate_staff(username, password):
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor(dictionary=True)
        query = "SELECT * FROM staff WHERE staffid = %s AND password = %s"
        cursor.execute(query, (username, password))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        return user
    except mysql.connector.Error as e:
        print(f"Authentication error: {e}")
        return None

def authenticate_student(username, password):
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor(dictionary=True)
        query = "SELECT * FROM student WHERE studentid = %s AND password = %s"
        cursor.execute(query, (username, password))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        return user
    except mysql.connector.Error as e:
        print(f"Authentication error: {e}")
        return None
    
@app.route('/student/homepage')
def student_home():
    if 'studentid' not in session:
        return redirect(url_for('login'))
    
    name = session['name']
    studentid = session['studentid']
    print(studentid)
    return render_template('student/homepage.html', name=name, id=studentid)

@app.route('/admin/homepage')
def admin_home():
    if 'staffid' not in session:
        return redirect(url_for('login'))

    staffid = session['staffid']
    name = session['name']
    user_role = "Staff"

    return render_template('admin/homepage.html', name=name, role=user_role, id=staffid)
    
@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out!', 'info')
    return redirect(url_for('login'))

@app.route("/admin/search_student/<student_id>", methods=["GET"])
def search_student(student_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "message": "Database connection error"})
    
    try:
        cursor = conn.cursor(dictionary=True)
        query = "SELECT name FROM student WHERE studentid = %s"
        cursor.execute(query, (student_id,))
        student = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if student:
            return jsonify({"success": True, "name": student['name']})
        else:
            return jsonify({"success": False, "message": "Student not found."})
    except mysql.connector.Error as e:
        print(f"Error searching student: {e}")
        return jsonify({"success": False, "message": "Database error"})

@app.route('/admin/events')
def admin_event():
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'danger')
        return render_template('admin/event.html', events=[])
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM events")
        events = cursor.fetchall()
        cursor.close()
        conn.close()
        return render_template('admin/event.html', events=events)
    except mysql.connector.Error as e:
        print(f"Error fetching events: {e}")
        flash('Error fetching events', 'danger')
        return render_template('admin/event.html', events=[])
    
@app.route('/admin/get_events', methods=['GET'])
def get_events():
    conn = get_db_connection()
    if not conn:
        return {'events': []}
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM events")
        events = cursor.fetchall()
        cursor.close()
        conn.close()
        return {'events': events}
    except mysql.connector.Error as e:
        print(f"Error fetching events: {e}")
        return {'events': []}

@app.route('/student/attendance', methods=['GET'])
def student_attendance():
    conn = get_db_connection()
    if not conn:
        return jsonify({'events': []}), 500

    try:
        # Get studentid from session
        student_id = session.get('studentid')
        if not student_id:
            return jsonify({'error': 'No studentid in session'}), 400

        # Get query parameters
        session_id = request.args.get('session')
        category = request.args.get('category')

        cursor = conn.cursor(dictionary=True)
        
        # Base query
        query = """
            SELECT 
                a.studentid, 
                a.eventid, 
                e.eventid, 
                e.name, 
                e.date, 
                e.category 
            FROM 
                attendance a
            LEFT JOIN 
                events e ON a.eventid = e.eventid
            WHERE 
                a.studentid = %s
        """
        params = [student_id]

        # Add session filter if provided
        if session_id:
            query += " AND e.session = %s"
            params.append(session_id)

        # Modified category handling
        print(category)
        if category:  # if category parameter exists
            if category == 'all':
                # No additional WHERE clause needed for 'all'
                pass
            else:
                # Add specific category filter
                query += " AND e.category = %s"
                params.append(category)

        # Debug prints
        print("Final query:", query)
        print("Parameters:", params)

        cursor.execute(query, tuple(params))
        events = cursor.fetchall()
        print(query, params)
        cursor.close()
        conn.close()
        return jsonify({'events': events})
        
    except mysql.connector.Error as e:
        print(f"Error fetching events: {e}")
        return jsonify({'error': 'Failed to fetch events', 'details': str(e)}), 500


@app.route('/admin/attendancereport', methods=['GET'])
def admin_attendancereport():
    conn = get_db_connection()
    if not conn:
        return jsonify({'events': []}), 500

    try:
        # Get query parameters
        session = request.args.get('session')
        category = request.args.get('category')
        cursor = conn.cursor(dictionary=True)
        
        # Base query
        query = """
            SELECT 
                e.eventid, 
                e.name, 
                e.date, 
                e.category, 
                COUNT(a.eventid) AS attendance_count
            FROM 
                events e
            LEFT JOIN 
                attendance a 
            ON 
                e.eventid = a.eventid
        """
        params = []

        # Add session filter if provided
        if session:
            query += " WHERE e.session = %s"
            params.append(session)

        # Modified category handling
        print(category)
        if category:  # if category parameter exists
            if category == 'all':
                # No additional WHERE clause needed for 'all'
                pass
            else:
                # Add specific category filter
                query += " AND e.category = %s"
                params.append(category)

        query += """
            GROUP BY 
                e.eventid, e.name, e.date, e.category
        """

        # Debug prints
        print("Final query:", query)
        print("Parameters:", params)

        cursor.execute(query, tuple(params))
        events = cursor.fetchall()
        print(query, params)
        cursor.close()
        conn.close()
        return jsonify({'events': events})
        
    except mysql.connector.Error as e:
        print(f"Error fetching events: {e}")
        return jsonify({'error': 'Failed to fetch events', 'details': str(e)}), 500
    
@app.route('/student/report')
def student_report():
    if 'studentid' not in session:
        return redirect(url_for('login'))
    print('here')
    return render_template('student/report.html')

@app.route('/admin/reports')
def admin_reports():
    if 'staffid' not in session:
        return redirect(url_for('login'))
    print('here')
    return render_template('admin/reports.html')

@app.route('/admin/edit_event/<int:event_id>', methods=['POST'])
def edit_event(event_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        cursor = conn.cursor()
        query = """
        UPDATE events 
        SET name = %s, date = %s, location = %s, details = %s 
        WHERE eventid = %s
        """
        cursor.execute(query, (
            request.json['name'], 
            request.json['date'], 
            request.json['location'], 
            request.json['details'], 
            event_id
        ))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'message': 'Event updated successfully'}), 200
    except mysql.connector.Error as e:
        print(f"Error editing event: {e}")
        return jsonify({'success': False, 'message': 'Database error'}), 500

@app.route('/admin/search_events', methods=['GET'])
def search_events():
    conn = get_db_connection()
    if not conn:
        return jsonify({'events': []}), 500

    try:
        # Get query parameters
        category = request.args.get('category', 'all')
        search_term = request.args.get('searchTerm', '').lower()

        cursor = conn.cursor(dictionary=True)

        # Base query
        query = """
            SELECT 
                e.eventid, 
                e.name, 
                e.date, 
                e.location, 
                e.details
            FROM 
                events e
            WHERE 1=1
        """
        params = []

        # Add category filter
        if category != 'all':
            query += " AND e.category = %s"
            params.append(category)

        # Add search term filter
        if search_term:
            query += " AND (LOWER(e.name) LIKE %s OR LOWER(e.details) LIKE %s)"
            params.extend([f"%{search_term}%", f"%{search_term}%"])

        # Execute query
        cursor.execute(query, tuple(params))
        events = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({"events": events})

    except mysql.connector.Error as e:
        print(f"Error fetching events: {e}")
        return jsonify({'error': 'Failed to fetch events', 'details': str(e)}), 500


@app.route('/admin/delete_event/<int:event_id>', methods=['DELETE'])
def delete_event(event_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM events WHERE eventid = %s", (event_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'message': 'Event deleted successfully'}), 200
    except mysql.connector.Error as e:
        print(f"Error deleting event: {e}")
        return jsonify({'success': False, 'message': 'Database error'}), 500

@app.route('/admin/faceregister')
def admin_faceregister():
    if 'staffid' not in session or session['user_type'] != 'staff':
        return redirect(url_for('login'))
    return render_template('admin/faceregister.html')

@app.route("/admin/register_face", methods=["POST"])
def register_face():
    try:
        # Get data from the request
        data = request.json
        image_base64 = data.get("image")
        student_id = data.get("studentid")

        # Validate input
        if not image_base64 or not student_id:
            return jsonify({"success": False, "message": "Missing image or student ID"})

        # Decode the base64 image
        image_decoded = base64.b64decode(image_base64)
        
        # Convert the image into a NumPy array
        np_image = np.frombuffer(image_decoded, np.uint8)
        frame = cv2.imdecode(np_image, cv2.IMREAD_COLOR)
        
        # Convert the frame to RGB for face_recognition
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Detect faces
        face_locations = face_recognition.face_locations(rgb_frame)
        if not face_locations:
            return jsonify({"success": False, "message": "No face detected"})
        
        # Encode the face
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
        if not face_encodings:
            return jsonify({"success": False, "message": "Failed to encode face"})
        # Store the face encoding with the student ID in the database
        insert_face_encoding(face_encodings[0], student_id)
        
        return jsonify({
            "success": True, 
            "message": f"Face registered successfully for student {student_id}"
        })
    
    except Exception as e:
        print(f"Error in register_face: {str(e)}")
        return jsonify({"success": False, "message": str(e)})
    
def insert_face_encoding(encoding, student_id):
    conn = get_db_connection()
    if not conn:
        raise Exception("Database connection failed")
    
    try:
        # Convert the encoding to JSON (serializable format for insertion)
        encoding_json = json.dumps(encoding.tolist())

        cursor = conn.cursor()
        # SQL query to insert face encoding and student ID into the database
        cursor.execute(
            "INSERT INTO fr (studentid, frdata, timestamp) VALUES (%s, %s, %s)", 
            (student_id, encoding_json, datetime.now())
        )
        conn.commit()
        
        print("Face encoding inserted into database.")
        cursor.close()
        conn.close()
    except mysql.connector.Error as e:
        print(f"Error inserting face encoding into database: {e}")
        raise

@app.route('/admin/attendancesession')
def admin_attendancesession():
    if 'staffid' not in session or session['user_type'] != 'staff':
        return redirect(url_for('login'))
    return render_template('admin/attendancesession.html')

def get_facial_recognition_data():
    # Fetch facial recognition data from the database
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT studentid, frdata FROM fr")
    result = cursor.fetchall()

    recognition_data = []
    for studentid, recognition_data_json in result:
        # Convert the JSON back to a numpy array
        recognition_data_array = np.array(json.loads(recognition_data_json))
        recognition_data.append((studentid, recognition_data_array))
    cursor.close()
    conn.close()
    
    return recognition_data

@app.route('/admin/attendancesession', methods=['POST'])
def attendance_session():
    try:
        # Retrieve the image sent from the frontend
        input_data = request.json
        image_base64 = input_data.get('image')
        if not image_base64:
            return jsonify({'error': 'No image provided'}), 400
        # Decode the image and process it
        image_data = base64.b64decode(image_base64)
        np_image = np.frombuffer(image_data, np.uint8)
        frame = cv2.imdecode(np_image, cv2.IMREAD_COLOR)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        face_locations = face_recognition.face_locations(rgb_frame)
        if not face_locations:
            print("No face detected.")
            return jsonify({"success": False, "message": "No face detected."})

        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

        if len(face_encodings) == 0:
            return jsonify({'recognized': False, 'error': 'No face detected'})

        # Get the encoding of the first detected face
        face_encoding = face_encodings[0]
        # Compare with data from the database
        recognition_data = get_facial_recognition_data()
        for studentid, db_encoding in recognition_data:
            matches = face_recognition.compare_faces([db_encoding], face_encoding, tolerance=0.3)
            if matches[0]:





                #call to insert attendance with verification





                return jsonify({'recognized': True, 'studentid': studentid})

        return jsonify({'recognized': False, 'message': 'No match found'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/attendance/<int:event_id>')
def start_admin_attendancesession(event_id):
    if 'staffid' not in session or session['user_type'] != 'staff':
        return redirect(url_for('login'))
    return render_template('admin/attendance.html', event_id=event_id)

@app.route('/admin/attendance1', methods=['POST'])
def attendance1():
    try:
        # Retrieve the image sent from the frontend
        input_data = request.json
        image_base64 = input_data.get('image')
        event_id = input_data.get('event_id')
        print(event_id)
        print('asdasd')
        if not image_base64:
            return jsonify({'error': 'No image provided'}), 400
        # Decode the image and process it
        image_data = base64.b64decode(image_base64)
        np_image = np.frombuffer(image_data, np.uint8)
        frame = cv2.imdecode(np_image, cv2.IMREAD_COLOR)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        face_locations = face_recognition.face_locations(rgb_frame)
        if not face_locations:
            print("No face detected.")
            return jsonify({"success": False, "message": "No face detected."})

        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

        if len(face_encodings) == 0:
            return jsonify({'recognized': False, 'error': 'No face detected'})

        # Get the encoding of the first detected face
        face_encoding = face_encodings[0]
        # Compare with data from the database
        recognition_data = get_facial_recognition_data()
        for studentid, db_encoding in recognition_data:
            matches = face_recognition.compare_faces([db_encoding], face_encoding, tolerance=0.35)
            if matches[0]:
                if check_and_insert_attendance(event_id, studentid):
                    return jsonify({'recognized': True, 'studentid': studentid})
                else:
                    return jsonify({'recognized': False, 'message': 'Attendance already recorded'})
            else:
                return jsonify({'recognized': False, 'message': 'No match found'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/add_event', methods=['POST'])
def add_event():
    conn = get_db_connection()
    cursor = conn.cursor()

    data = request.json
    print(data)
    name = data.get('name')
    date = data.get('date')
    location = data.get('location')
    details = data.get('details')
    sesi = data.get('sesi')
    category = data.get('category')

    try:
        # Insert the event into the database
        query = """
            INSERT INTO events (name, date, location, details, session, category)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        params = (name, date, location, details, sesi, category)
        cursor.execute(query, params)  # Adjust db.execute to your database library
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        print("Error adding event:", e)
        return jsonify({"success": False, "error": str(e)})



def check_and_insert_attendance(event_id, studentid):
    """
    Checks if the (event_id, studentid) pair already exists in the attendance table.
    If not, inserts the attendance record.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    # Check if attendance already exists for this event_id and studentid
    cursor.execute(
        "SELECT 1 FROM attendance WHERE eventid = %s AND studentid = %s",
        (event_id, studentid)
    )
    result = cursor.fetchone()

    if result is None:
        # No duplicate, insert the attendance
        cursor.execute(
            "INSERT INTO attendance (eventid, studentid) VALUES (%s, %s)",
            (event_id, studentid)
        )
        conn.commit()
        print(f"Attendance recorded for Event ID: {event_id}, Student ID: {studentid}")
        cursor.close()
        conn.close()
        return True
    else:
        print(f"Duplicate attendance for Student ID: {studentid}")
        cursor.close()
        conn.close()
        return False


if __name__ == '__main__':
    app.run(debug=True)
