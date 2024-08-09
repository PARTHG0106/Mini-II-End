from flask import Flask, flash, render_template, redirect, request, url_for, jsonify, session, Response
from forms import LoginForm, SearchForm, RegistrationForm
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import Config
from models import User, db, bcrypt, Exercises, UserExercise, WeeklyWorkout
import cv2
import numpy as np
import mediapipe as mp
from shoulder_press import gen_frames as gen_frames_shoulder_press
from bicep_curls import gen_frames as gen_frames_bicep_curls

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
bcrypt.init_app(app)
migrate = Migrate(app, db)



def gen_frames(exercise):
    if exercise == 'shoulder_press':
        print('spress')
        return gen_frames_shoulder_press()
    elif exercise == 'dumbbell_curls':
        print('bcurls')
        return gen_frames_bicep_curls()
    else:
        return None


@app.route('/')
@app.route('/login', methods=['GET', 'POST'])
def login():
    login_form = LoginForm()
    registration_form = RegistrationForm()
    if request.method == 'POST':
        if 'login_submit' in request.form and login_form.validate_on_submit():
            user = User.query.filter_by(username=login_form.username.data).first()
            if user and user.check_password(login_form.password.data):
                flash('Login successful!', 'success')
                session['user_id'] = user.id
                return redirect(url_for('mainboard'))
            else:
                flash('Invalid username or password.', 'danger')
        elif 'register_submit' in request.form and registration_form.validate_on_submit():
            user = User.query.filter_by(username=registration_form.username.data).first()
            if user is None:
                new_user = User(username=registration_form.username.data, email=registration_form.email.data)
                new_user.set_password(registration_form.password.data)
                db.session.add(new_user)
                db.session.commit()

                flash('Registration successful! You can now log in.', 'success')
                session['user_id'] = new_user.id
                session['first_session'] = True
                return redirect(url_for('mainboard'))
            else:
                flash('Username already exists. Please choose a different username.', 'danger')
    return render_template('enter.html', login_form=login_form, registration_form=registration_form)




@app.route('/mainboard', methods=['GET', 'POST'])
def mainboard():
    first_session = session.get('first_session')
    if not first_session:
        print('not first time')
    else:
        print(first_session)
        session['first_session'] = False
    search_form = SearchForm()
    user_id = session.get('user_id')
    if not user_id:
        print('error no id')
    weekly_workout = WeeklyWorkout.query.filter_by(user_id=user_id).first()

    if weekly_workout:
        print('success fetching id')
        workouts_completed = weekly_workout.completed
        weekly_goal = weekly_workout.goal
        workouts_remaining = max(weekly_goal - workouts_completed, 0)
        efficiency = (workouts_completed / weekly_goal) * 100 if weekly_goal > 0 else 0
        progress = (workouts_completed / weekly_goal) * 100 if weekly_goal > 0 else 0
    else:

        workouts_completed = 0
        weekly_goal = 3
        workouts_remaining = 3
        efficiency = 0
        progress = 0

    return render_template('mainboard.html', search_form=search_form,workouts_completed=workouts_completed,
                           weekly_goal=weekly_goal, workouts_remaining=workouts_remaining, efficiency=efficiency,progress=progress,
                           first_session=first_session)


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    search_form = SearchForm()
    user_id = session.get('user_id')
    weekly_workout = WeeklyWorkout.query.filter_by(user_id=user_id).first()
    user_details = User.query.filter_by(id=user_id).first()
    if weekly_workout:
        print('success fetching id')
        weekly_goal = weekly_workout.goal

    if user_details:
        print('success fetching user details')
        username = user_details.username

    return render_template('profile.html', search_form=search_form, weekly_goal=weekly_goal,
                           username = username)


@app.route('/search_exercises', methods=['GET'])
def search_exercises():
    query = request.args.get('query', '').strip()
    if query:
        exercises = Exercises.query.filter(Exercises.name.ilike(f'%{query}%')).all()
        results = [{'name': exercise.name, 'link': exercise.link} for exercise in exercises]
        return jsonify(results)
    return jsonify([])

@app.route('/exercises', methods=['GET','POST'])
def exercises():
    search_form = SearchForm()
    return render_template('exercises.html', search_form=search_form)


@app.route('/leaderboard', methods=['GET','POST'])
def leaderboard():
    search_form = SearchForm()
    return render_template('leaderboard.html', search_form=search_form)

@app.route('/workout')
def workout():
    search_form = SearchForm()
    return render_template('exercises.html', search_form=search_form)


@app.route('/start/<exercise>')
def start(exercise):
    search_form = SearchForm()
    return render_template('start.html', search_form=search_form, exercise=exercise)


@app.route('/video_feed')
def video_feed():
    exercise = request.args.get('exercise', 'shoulder_press')  # Default to 'shoulder_press'
    frame_generator = gen_frames(exercise)
    if frame_generator:
        return Response(frame_generator, mimetype='multipart/x-mixed-replace; boundary=frame')
    else:
        return "Invalid exercise type", 400



if __name__ == '__main__':
    app.run(debug=True)
