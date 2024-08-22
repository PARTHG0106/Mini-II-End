from flask import Flask, flash, render_template, redirect, request, url_for, jsonify, session, Response
from forms import LoginForm, SearchForm, RegistrationForm
from flask_migrate import Migrate
from config import Config
from models import User, db, bcrypt, Exercises, UserExercise
from shoulder_press import gen_frames as gen_frames_shoulder_press
from bicep_curls import gen_frames as gen_frames_bicep_curls
from barbell_squats import gen_frames as gen_frames_barbell_squats
from deadlift import gen_frames as gen_frames_deadlift
from lateral_raises import gen_frames as gen_frames_lateral_raises
import pandas as pd
from dash import Dash, html, dcc, Input, Output
import plotly.graph_objects as go
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from datetime import datetime, timedelta
from sqlalchemy import func
from functools import wraps

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
bcrypt.init_app(app)
migrate = Migrate(app, db)
quartz = dbc.themes.SKETCHY

def login_required(f):
    @wraps(f)
    def chck(*args, **kwargs):
        if 'user_id' not in session:
            flash("You need to log in first.", "danger")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return chck


dash_app = Dash(__name__, server=app, external_stylesheets=[quartz], url_base_pathname='/dashboard/')

dash_app.layout = dbc.Container([
    dbc.Row(
        dbc.Col(
            html.A("Go Back", href="/mainboard", className="btn btn-lg text-center text-white", style={
                "background-color": "#98ff98",  # Green mint
                "border-radius": "10px",
                "padding": "10px 20px",
                "display": "block",
                "margin": "0 auto",
                "text-decoration": "none",
                "font-size": "24px",
                "width": "200px",
                "box-shadow": "2px 2px 5px rgba(0, 0, 0, 0.3)"
            }),
            width=12
        )
    ),
    dcc.Tabs(id="tabs-example", value='tab-1', children=[
        dcc.Tab(label='Last Workout', value='tab-1'),
        dcc.Tab(label='Progress', value='tab-2'),
    ]),
    html.Div(id='tabs-content')
])


@dash_app.callback(
    Output('tabs-content', 'children'),
    Input('tabs-example', 'value')
)
def render_content(tab):
    if tab == 'tab-1':
        return dbc.Container([
            dbc.Row([
                dbc.Col(
                    dcc.Dropdown(
                        id='exercise-dropdown',
                        options=[
                            {'label': 'Shoulder Press', 'value': 1},#edit here temporarily for exercise additions
                            {'label': 'Bicep Curl', 'value': 2},
                            {'label': 'Barbell Squats', 'value': 3},
                            {'label': 'Deadlift', 'value': 4},
                            {'label': 'Lateral Raises', 'value': 5}

                        ],
                        value=1,
                        className='mx-auto',
                        style={'width': '50%'}
                    ),
                    width=6
                )
            ], justify="center"),
            html.Div(id='exercise-output', className="mt-4")
        ])
    elif tab == 'tab-2':
        return dbc.Container([
            dbc.Row(
                dbc.Col(html.H3("Overall Progress", className="text-center my-4"), width=12)
            ),
            dbc.Row([
                dbc.Col(
                    dcc.Graph(id='overall-progress-graph'),
                    width=12
                )
            ]),
            dbc.Row([
                dbc.Col(
                    dcc.Dropdown(
                        id='specific-exercise-dropdown',
                        options=[
                            {'label': 'Shoulder Press', 'value': 1},
                            {'label': 'Bicep Curl', 'value': 2},
                            {'label': 'Barbell Squats', 'value': 3},
                            {'label': 'Deadlift', 'value': 4},
                            {'label': 'Lateral Raises', 'value': 5}
                        ],
                        value=1,
                        className='mx-auto',
                        style={'width': '50%'}
                    ),
                    width=6
                )
            ], justify="center", className="mt-4"),
            dbc.Row([
                dbc.Col(
                    dcc.Graph(id='specific-exercise-progress-graph'),
                    width=12
                )
            ]),
            dbc.Row([
                dbc.Col(
                    dcc.Graph(id='muscles-hit-graph'),  # Later
                    width=12
                )
            ])
        ])


# Callback for the Last Workout Tab
@dash_app.callback(
    Output('exercise-output', 'children'),
    Input('exercise-dropdown', 'value')
)
def update_last_workout(exercise_id):
    last_workout = UserExercise.query.filter_by(user_id=session['user_id'], exercise_id=exercise_id).order_by(
        UserExercise.date.desc()).first()

    if last_workout:
        workout_data = {
            'Date': last_workout.date.strftime("%Y-%m-%d %H:%M:%S"),
            'ROM Score': last_workout.rom_score,
            'TUT Score': round(last_workout.tut_score / last_workout.total_reps, 1),
            'Total Reps': last_workout.total_reps,
            'rom_score': last_workout.rom_score,
            'Count': last_workout.count
        }

        pie_chart = go.Figure(data=[go.Pie(labels=['Efficient Reps', 'Missed Reps'],
                                           values=[workout_data['Total Reps'],
                                                   workout_data['Total Reps'] - workout_data['rom_score']])])
        pie_chart.update_layout(
            title={
                'text': 'Efficiency in Last Workout',
                'font': {
                    'color': 'black'
                }
            },
            legend={
                'font': {
                    'color': 'black'
                }
            },
            paper_bgcolor='rgba(0,0,0,0)'
        )

        return html.Div([
            html.H4(f"Last Workout: {workout_data['Date']}"),
            html.P(f"ROM Score: {workout_data['ROM Score']}"),
            html.P(f"TUT: {workout_data['TUT Score']} sec per rep"),
            html.P(f"Total Reps: {workout_data['Total Reps']}"),
            dcc.Graph(figure=pie_chart)
        ])
    else:
        return html.P("No workout data available.")


# Callback to the Progress Tab
@dash_app.callback(
    [Output('overall-progress-graph', 'figure'),
     Output('specific-exercise-progress-graph', 'figure'),
     Output('muscles-hit-graph', 'figure')],
    [Input('tabs-example', 'value'),
     Input('specific-exercise-dropdown', 'value')]
)
def update_progress(tab, exercise_id):
    if tab != 'tab-2':
        raise PreventUpdate

    # Overall Progress DataFrame
    overall_data = UserExercise.query.filter_by(user_id=session['user_id']).all()
    overall_df = pd.DataFrame([{
        'date': record.date,
        'rom_score': record.rom_score,
        'tut_score': record.tut_score,
        'rep_number': record.total_reps,
        'count': record.count,
    } for record in overall_data])

    if overall_df.empty:
        return go.Figure(), go.Figure(), go.Figure()

    overall_df['week'] = overall_df['date'].dt.strftime('%Y-%U')
    overall_df['efficiency'] = (overall_df['count'] / overall_df['rep_number']) * 100
    weekly_efficiency_df = overall_df.groupby('week').agg({'efficiency': 'mean'}).reset_index()
    weekly_efficiency_df['wow_improvement'] = weekly_efficiency_df['efficiency'].pct_change() * 100
    wow = f'{weekly_efficiency_df["wow_improvement"].iloc[-1]:.2f}% better than prev. week ⬆️'

    overall_df = overall_df.groupby('date').agg({
        'rom_score': 'mean',
        'tut_score': 'mean',
        'rep_number': 'sum',
        'count': 'sum'
    }).reset_index()

    overall_line_chart = go.Figure()
    overall_line_chart.add_trace(go.Scatter(x=overall_df['date'], y=overall_df['count'],
                                            mode='lines+markers', name='Efficient Reps'))
    overall_line_chart.add_trace(go.Scatter(x=overall_df['date'], y=overall_df['rep_number'],
                                            mode='lines+markers', name='Total Reps'))
    overall_line_chart.add_annotation(
        text=f"WoW Improvement: {wow}",
        xref="paper", yref="paper",
        x=0.5, y=1.1,
        showarrow=False,
        font=dict(
            size=14,
            color="black"
        ),
        align="center",
        bgcolor="white",
        opacity=0.8
    )
    overall_line_chart.update_layout(title='Overall Week-Over-Week Progress',
                                     xaxis_title='Date', yaxis_title='Efficiency')


    specific_data = UserExercise.query.filter_by(exercise_id=exercise_id, user_id=session['user_id']).all()
    specific_df = pd.DataFrame([{
        'date': record.date,
        'rom_score': record.rom_score,
        'tut_score': record.tut_score,
        'rep_number': record.total_reps,
        'count': record.count,
    } for record in specific_data])

    specific_line_chart = go.Figure()
    if not specific_df.empty:
        specific_df = specific_df.groupby('date').agg({
            'rom_score': 'mean',
            'tut_score': 'mean',
            'rep_number': 'sum',
            'count': 'sum'
        }).reset_index()

        specific_line_chart.add_trace(go.Scatter(x=specific_df['date'], y=specific_df['count'],
                                                 mode='lines+markers', name='Efficient Reps'))
        specific_line_chart.add_trace(go.Scatter(x=specific_df['date'], y=specific_df['rep_number'],
                                                 mode='lines+markers', name='Total Reps'))
        specific_line_chart.update_layout(title='Specific Exercise Progress',
                                          xaxis_title='Date', yaxis_title='Efficiency')


    muscle_data = db.session.query(Exercises.muscles_involved, db.func.sum(UserExercise.total_reps)).join(
        UserExercise, Exercises.id == UserExercise.exercise_id).filter(UserExercise.user_id == session['user_id']).group_by(
        Exercises.muscles_involved).all()

    muscle_df = pd.DataFrame(muscle_data, columns=['Muscles Involved', 'Total Reps'])
    muscle_dict = {}

    for muscles, reps in zip(muscle_df['Muscles Involved'], muscle_df['Total Reps']):

        muscle_list = muscles.split(',')

        for muscle in muscle_list:
            muscle = muscle.strip()
            if muscle in muscle_dict:
                muscle_dict[muscle] += reps
            else:
                muscle_dict[muscle] = reps

    muscle_ind_df = pd.DataFrame(list(muscle_dict.items()), columns=['muscle', 'Total Reps'] )
    muscle_ind_df = muscle_ind_df.sort_values(by='Total Reps', ascending=False)
    muscle_bar_chart = go.Figure(data=[
        go.Bar(x=muscle_ind_df['muscle'], y=muscle_ind_df['Total Reps'])
    ])
    muscle_bar_chart.update_layout(title='Muscles Worked', xaxis_title='Muscle Groups', yaxis_title='Total Reps')

    return overall_line_chart, specific_line_chart, muscle_bar_chart



@app.route("/dash/")
def render_dashboard():
    return dash_app.index()


def gen_frames(exercise, user_id, rep_goal):
    if exercise == 'shoulder_press':
        print('s_press')
        return gen_frames_shoulder_press(user_id, rep_goal)
    elif exercise == 'dumbbell_curls':
        print('b_curls')
        return gen_frames_bicep_curls(user_id, rep_goal)
    elif exercise == 'barbell_squats':
        print('b_squats')
        return gen_frames_barbell_squats(user_id, rep_goal)
    elif exercise == 'deadlift':
        print('dlift')
        return gen_frames_deadlift(user_id, rep_goal)
    elif exercise == 'lateral_raises':
        print('l_raises')
        return gen_frames_lateral_raises(user_id, rep_goal)
    else:
        return None



@app.route('/')
@app.route('/login', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    login_form = LoginForm()
    registration_form = RegistrationForm()

    if request.method == 'POST':
        if 'login_submit' in request.form:
            if login_form.validate_on_submit():
                user = User.query.filter_by(username=login_form.username.data).first()
                if user and user.check_password(login_form.password.data):
                    flash('Login successful!', 'success')
                    session['user_id'] = user.id
                    return redirect(url_for('mainboard'))
                else:
                    flash('Invalid username or password.', 'danger')
            else:
                flash('Login failed. Please check your inputs.', 'danger')


        elif 'register_submit' in request.form:
            if registration_form.validate_on_submit():
                user = User.query.filter_by(username=registration_form.username.data).first()
                if user is None:
                    new_user = User(username=registration_form.username.data, email=registration_form.email.data)
                    new_user.set_password(registration_form.password.data)
                    db.session.add(new_user)
                    db.session.commit()

                    flash('Registration successful! You can now log in.', 'success')
                    session['user_id'] = new_user.id
                    return redirect(url_for('mainboard'))
                else:
                    flash('Username already exists. Please choose a different username.', 'danger')
            else:
                flash('Registration failed. Please choose a different username.', 'danger')

    return render_template('enter.html', login_form=login_form, registration_form=registration_form)


from datetime import datetime, timedelta


@app.route('/mainboard', methods=['GET', 'POST'])
@login_required
def mainboard():
    first_session = session.get('first_session')
    if not first_session:
        print('not first time')
        print(session['user_id'])
    else:
        print(first_session)
        session['first_session'] = False

    search_form = SearchForm()
    user_id = session.get('user_id')
    if not user_id:
        print('error no id')

    all_exercises = UserExercise.query.filter_by(user_id=user_id).all()

    total_rom_score = sum(exercise.rom_score for exercise in all_exercises)
    total_reps = sum(exercise.total_reps for exercise in all_exercises)

    if total_reps > 0:
        efficiency = round(((total_rom_score / total_reps) * 100), 2)
    else:
        efficiency = 0

    total_exercises = UserExercise.query.filter_by(user_id=user_id).count()
    total_reps = db.session.query(db.func.sum(UserExercise.total_reps)).filter_by(user_id=user_id).scalar()

    today = datetime.today()
    start_of_week = today - timedelta(days=today.weekday())

    exercises_this_week = UserExercise.query.filter(
        UserExercise.user_id == user_id,
        UserExercise.date >= start_of_week
    ).count()

    exercise_goal = User.query.filter_by(id=user_id).one()
    print(exercise_goal.ex_goal)
    ex_goal = exercise_goal.ex_goal - exercises_this_week

    thirty_days_ago = today - timedelta(days=30)
    distinct_dates = db.session.query(UserExercise.date).filter(
        UserExercise.user_id == user_id,
        UserExercise.date >= thirty_days_ago
    ).distinct().all()
    workout_days = len(set(date[0].date() for date in distinct_dates))

    exercise_dates = db.session.query(UserExercise.date).filter_by(user_id=user_id).distinct().order_by(
        UserExercise.date).all()

    exercise_dates = [date[0].date() for date in exercise_dates]

    streak = 0
    for i in range(1, len(exercise_dates)):
        if exercise_dates[i] == exercise_dates[i - 1] + timedelta(days=1):
            streak += 1
        else:
            break

    import random


    most_performed_exercise = db.session.query(
        UserExercise.exercise_id, db.func.sum(UserExercise.total_reps).label('total_reps')
    ).filter_by(user_id=user_id).group_by(
        UserExercise.exercise_id
    ).order_by(
        db.func.sum(UserExercise.total_reps).desc()
    ).all()

    if most_performed_exercise:
        top_total_reps = most_performed_exercise[0][1]
        top_exercises = [exercise for exercise in most_performed_exercise if exercise[1] == top_total_reps]
        selected_exercise_id = random.choice(top_exercises)[0]

        selected_exercise = Exercises.query.get(selected_exercise_id)
        selected_exercise_name = selected_exercise.name if selected_exercise else "your most performed exercise"
        alternate_exercise = selected_exercise.alternate if selected_exercise else None

        if alternate_exercise:
            alternate_message = f"{alternate_exercise}"
        else:
            alternate_message = "No alternate exercise available."

    else:
        selected_exercise_name = "your most performed exercise"
        alternate_message = "No exercises found."

    return render_template('mainboard.html', search_form=search_form,
                           first_session=first_session, efficiency=efficiency, total_exercises=total_exercises,
                           total_reps=total_reps, exercises_this_week=exercises_this_week, streak=streak,
                           workout_days=workout_days, selected_exercise_name=selected_exercise_name,
                           alternate_message=alternate_message, ex_goal=ex_goal)


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    search_form = SearchForm()
    user_id = session.get('user_id')

    user_details = User.query.filter_by(id=user_id).first()

    if user_details:
        username = user_details.username
        ex_goal = user_details.ex_goal
        rep_goal = user_details.rep_goal

    if request.method == 'POST':
        if 'change_password' in request.form:
            new_password = request.form['new_password']
            user_details.set_password(new_password)
            db.session.commit()
            flash('Password updated successfully!', 'success')

        elif 'increase_ex_goal' in request.form:
            user_details.ex_goal += 1
            db.session.commit()

        elif 'decrease_ex_goal' in request.form:
            if user_details.ex_goal > 0:
                user_details.ex_goal -= 1
                db.session.commit()

        elif 'increase_rep_goal' in request.form:
            user_details.rep_goal += 1
            db.session.commit()

        elif 'decrease_rep_goal' in request.form:
            if user_details.rep_goal > 0:
                user_details.rep_goal -= 1
                db.session.commit()

        elif 'delete_account' in request.form:
            db.session.delete(user_details)
            db.session.commit()
            flash('Account deleted successfully!', 'success')
            return redirect(url_for('logout'))

    return render_template('profile.html', search_form=search_form,
                           username=username, ex_goal=ex_goal, rep_goal=rep_goal)


@app.route('/search_exercises', methods=['GET'])
@login_required
def search_exercises():
    query = request.args.get('query', '').strip()
    if query:
        exercises = Exercises.query.filter(Exercises.name.ilike(f'%{query}%')).all()
        results = [{'name': exercise.name, 'link': exercise.link} for exercise in exercises]
        return jsonify(results)
    return jsonify([])


@app.route('/exercises', methods=['GET', 'POST'])
@login_required
def exercises():
    exercise = request.args.get('exercise', default=None)

    video_links = {
        'shoulder_press': 'https://www.youtube.com/embed/HzIiNhHhhtA',
        'dumbbell_curls': 'https://www.youtube.com/embed/JnLFSFurrqQ',
        'barbell_squats': 'https://www.youtube.com/embed/i7J5h7BJ07g',
        'deadlift': 'https://www.youtube.com/embed/AweC3UaM14o',
        'lateral_raises': 'https://www.youtube.com/embed/OuG1smZTsQQ'
    }

    video_link = video_links.get(exercise)

    return render_template('exercises.html', video_link=video_link, exercise=exercise)

@app.route('/leaderboard', methods=['GET', 'POST'])
@login_required
def leaderboard():
    search_form = SearchForm()
    view = request.form.get('view', 'total_exercises')


    highest_exercises = db.session.query(
        User.id,
        User.username,
        func.count(UserExercise.id).label('exercise_count')
    ).join(User, User.id == UserExercise.user_id).group_by(User.id).order_by(func.count(UserExercise.id).desc()).all()


    highest_reps = db.session.query(
        User.id,
        User.username,
        func.sum(UserExercise.count).label('total_reps')
    ).join(User, User.id == UserExercise.user_id).group_by(User.id).order_by(func.sum(UserExercise.count).desc()).all()

    return render_template('leaderboard.html', leaderboard_data=highest_exercises if view == 'total_exercises'
    else highest_reps, view=view, search_form=search_form)


@app.route('/workout')
@login_required
def workout():
    search_form = SearchForm()
    return render_template('exercises.html', search_form=search_form)


@app.route('/start/<exercise>')
@login_required
def start(exercise):
    search_form = SearchForm()
    user_id = session.get('user_id')
    rep_goal = db.session.query(User.rep_goal).filter_by(id=user_id).scalar()

    return render_template('instructions.html', search_form=search_form, exercise=exercise, user_id=user_id, rep_goal=rep_goal)

@app.route('/start_page/<exercise>')
@login_required
def start_page(exercise):
    search_form = SearchForm()
    user_id = session.get('user_id')
    rep_goal = db.session.query(User.rep_goal).filter_by(id=user_id).scalar()



    video_feed_url = url_for('video_feed', exercise=exercise, user_id=user_id, rep_goal=rep_goal)

    return render_template('start.html', search_form=search_form, exercise=exercise, user_id=user_id, rep_goal=rep_goal, video_feed_url=video_feed_url)


@app.route('/video_feed/<exercise>/<int:user_id>/<int:rep_goal>')
def video_feed(exercise, user_id, rep_goal):
    return Response(gen_frames(exercise, user_id, rep_goal), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/logout')
@login_required
def logout():
    session.clear()  # Clear all session data
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))


if __name__ == "__main__":
    app.run()
