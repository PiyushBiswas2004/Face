import cv2
import os
import sqlite3
from flask import Flask, request, render_template, redirect, url_for, flash, session
from datetime import date, datetime
import numpy as np
from sklearn.neighbors import KNeighborsClassifier
import joblib
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

nimgs = 10
imgBackground = cv2.imread("background.png")
datetoday2 = date.today().strftime("%d-%B-%Y")
face_detector = cv2.CascadeClassifier('haarcascade_frontalface_default.xml')
#login setup
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function
# Database setup functions
def init_db():
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    
    # Create users table (existing)
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            roll_number TEXT UNIQUE NOT NULL
        )
    ''')
    
    # Create auth table (new)
    c.execute('''
        CREATE TABLE IF NOT EXISTS auth_users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            role TEXT NOT NULL DEFAULT 'user'
        )
    ''')
    
    # Create attendance table (existing)
    c.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id, date)
        )
    ''')
    
    conn.commit()
    conn.close()
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = sqlite3.connect('attendance.db')
        c = conn.cursor()
        
        c.execute('SELECT * FROM auth_users WHERE username = ?', (username,))
        user = c.fetchone()
        conn.close()
        
        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['role'] = user[4]
            flash('Logged in successfully!')
            return redirect(url_for('home'))
        
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        role = 'admin' if request.form.get('is_admin') else 'user'
        
        conn = sqlite3.connect('attendance.db')
        c = conn.cursor()
        
        try:
            hashed_password = generate_password_hash(password)
            c.execute('INSERT INTO auth_users (username, password, email, role) VALUES (?, ?, ?, ?)',
                     (username, hashed_password, email, role))
            conn.commit()
            flash('Account created successfully! Please login.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or email already exists!')
        finally:
            conn.close()
            
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully!')
    return redirect(url_for('login'))

def add_user_to_db(username, userid):
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users (name, roll_number) VALUES (?, ?)', (username, userid))
        conn.commit()
    except sqlite3.IntegrityError:
        print(f"User with roll number {userid} already exists")
    finally:
        conn.close()

def add_attendance_to_db(name, userid):
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    current_date = date.today().strftime("%Y-%m-%d")
    current_time = datetime.now().strftime("%H:%M:%S")
    
    try:
        # Check if attendance already exists for today
        c.execute('''
            SELECT a.id FROM attendance a 
            JOIN users u ON a.user_id = u.id 
            WHERE u.roll_number = ? AND a.date = ?
        ''', (userid, current_date))
        
        if not c.fetchone():
            # Get user_id
            c.execute('SELECT id FROM users WHERE roll_number = ?', (userid,))
            user_id = c.fetchone()[0]
            
            # Add attendance
            c.execute('''
                INSERT INTO attendance (user_id, date, time) 
                VALUES (?, ?, ?)
            ''', (user_id, current_date, current_time))
            conn.commit()
    finally:
        conn.close()

def get_attendance_data():
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    current_date = date.today().strftime("%Y-%m-%d")
    
    c.execute('''
        SELECT u.name, u.roll_number, a.time 
        FROM attendance a 
        JOIN users u ON a.user_id = u.id 
        WHERE a.date = ?
    ''', (current_date,))
    
    attendance_data = c.fetchall()
    conn.close()
    
    names = [row[0] for row in attendance_data]
    rolls = [row[1] for row in attendance_data]
    times = [row[2] for row in attendance_data]
    return names, rolls, times, len(attendance_data)

def totalreg():
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM users')
    count = c.fetchone()[0]
    conn.close()
    return count

# Rest of the face recognition functions remain the same
def extract_faces(img):
    try:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        face_points = face_detector.detectMultiScale(gray, 1.2, 5, minSize=(20, 20))
        return face_points
    except:
        return []

def identify_face(facearray):
    model = joblib.load('static/face_recognition_model.pkl')
    return model.predict(facearray)

def train_model():
    faces = []
    labels = []
    userlist = os.listdir('static/faces')
    for user in userlist:
        for imgname in os.listdir(f'static/faces/{user}'):
            img = cv2.imread(f'static/faces/{user}/{imgname}')
            resized_face = cv2.resize(img, (50, 50))
            faces.append(resized_face.ravel())
            labels.append(user)
    faces = np.array(faces)
    knn = KNeighborsClassifier(n_neighbors=5)
    knn.fit(faces, labels)
    joblib.dump(knn, 'static/face_recognition_model.pkl')

# Modified routes
@app.route('/')
@login_required
def home():
    names, rolls, times, l = get_attendance_data()
    return render_template('home.html', 
                         names=names, 
                         rolls=rolls, 
                         times=times, 
                         l=l, 
                         totalreg=totalreg(), 
                         datetoday2=datetoday2,
                         username=session.get('username'))

@app.route('/start', methods=['GET'])
@login_required
def start():
    names, rolls, times, l = get_attendance_data()

    if 'face_recognition_model.pkl' not in os.listdir('static'):
        return render_template('home.html', names=names, rolls=rolls, times=times, l=l, totalreg=totalreg(), datetoday2=datetoday2, mess='There is no trained model in the static folder. Please add a new face to continue.')

    ret = True
    cap = cv2.VideoCapture(0)
    while ret:
        ret, frame = cap.read()
        if len(extract_faces(frame)) > 0:
            (x, y, w, h) = extract_faces(frame)[0]
            cv2.rectangle(frame, (x, y), (x+w, y+h), (86, 32, 251), 1)
            face = cv2.resize(frame[y:y+h, x:x+w], (50, 50))
            identified_person = identify_face(face.reshape(1, -1))[0]
            username, userid = identified_person.split('_')
            add_attendance_to_db(username, userid)
            cv2.putText(frame, f'{identified_person}', (x,y-15), cv2.FONT_HERSHEY_COMPLEX, 1, (255,255,255), 1)
            cv2.rectangle(frame, (x,y), (x+w, y+h), (50,50,255), 1)
        imgBackground[162:162 + 480, 55:55 + 640] = frame
        cv2.imshow('Attendance', imgBackground)
        if cv2.waitKey(1) == 27:
            break
    cap.release()
    cv2.destroyAllWindows()
    names, rolls, times, l = get_attendance_data()
    return render_template('home.html', names=names, rolls=rolls, times=times, l=l, totalreg=totalreg(), datetoday2=datetoday2)
pass

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    # Check if user has admin role
    if session.get('role') != 'admin':
        flash('Only administrators can add new users!')
        return redirect(url_for('home'))
    newusername = request.form['newusername']
    newuserid = request.form['newuserid']
    
    # Add user to database
    add_user_to_db(newusername, newuserid)
    
    userimagefolder = 'static/faces/'+newusername+'_'+str(newuserid)
    if not os.path.isdir(userimagefolder):
        os.makedirs(userimagefolder)
    
    i, j = 0, 0
    cap = cv2.VideoCapture(0)
    while 1:
        _, frame = cap.read()
        faces = extract_faces(frame)
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 20), 2)
            cv2.putText(frame, f'Images Captured: {i}/{nimgs}', (30, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 20), 2, cv2.LINE_AA)
            if j % 5 == 0:
                name = newusername+'_'+str(i)+'.jpg'
                cv2.imwrite(userimagefolder+'/'+name, frame[y:y+h, x:x+w])
                i += 1
            j += 1
        if j == nimgs*5:
            break
        cv2.imshow('Adding new User', frame)
        if cv2.waitKey(1) == 27:
            break
    cap.release()
    cv2.destroyAllWindows()
    print('Training Model')
    train_model()
    names, rolls, times, l = get_attendance_data()
    return render_template('home.html', names=names, rolls=rolls, times=times, l=l, totalreg=totalreg(), datetoday2=datetoday2)
    pass