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
                session['user_id'] = user['staffid']
                session['user_name'] = user['name']
                session['user_type'] = "staff"
                print(f"User ID: {user['staffid']}, Role: staff")
                return redirect(url_for('admin_home', name=user['name'], id=user['staffid']))

            else:
                flash('Invalid credentials!', 'danger')
                return redirect(url_for('login'))

        elif len(username) == 10:  # Student login
            user = authenticate_student(username, password)
            if user:
                flash('Login successful!', 'success')
                session['user_id'] = user['studentid']
                session['user_name'] = user['name']
                session['user_type'] = "student"
                print(f"User ID: {user['id']}, Role: student")
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
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    name = session['user_name']
    id = session['user_id']
    return render_template('student/homepage.html', name=name, id=id)

@app.route('/admin/homepage')
def admin_home():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    user_name = session['user_name']
    user_role = "Staff"

    return render_template('admin/homepage.html', name=user_name, role=user_role)

    
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
    if 'user_id' not in session or session['user_type'] != 'staff':
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
    if 'user_id' not in session or session['user_type'] != 'staff':
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
        print('point 3')

        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

        if len(face_encodings) == 0:
            return jsonify({'recognized': False, 'error': 'No face detected'})

        # Get the encoding of the first detected face
        face_encoding = face_encodings[0]
        # Compare with data from the database
        recognition_data = get_facial_recognition_data()
        for studentid, db_encoding in recognition_data:
            print(f"Student ID: {studentid}, DB Encoding: {db_encoding}")

        for studentid, db_encoding in recognition_data:
            matches = face_recognition.compare_faces([db_encoding], face_encoding, tolerance=0.3)
            if matches[0]:
                return jsonify({'recognized': True, 'studentid': studentid})

        return jsonify({'recognized': False, 'message': 'No match found'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
