from flask import Flask, flash, render_template, redirect, request, url_for, jsonify, session, Response
from forms import LoginForm, SearchForm, RegistrationForm
from flask_migrate import Migrate
from config import Config
from models import User, db, bcrypt, Exercises, UserExercise
from shoulder_press import gen_frames as gen_frames_shoulder_press
from bicep_curls import gen_frames as gen_frames_bicep_curls
import pandas as pd
from dash import Dash, html, dcc, Input, Output
import plotly.graph_objects as go
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from datetime import datetime, timedelta
from sqlalchemy import func

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
bcrypt.init_app(app)
migrate = Migrate(app, db)
quartz = dbc.themes.SKETCHY

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
                            {'label': 'Shoulder Press', 'value': 1},
                            {'label': 'Bicep Curl', 'value': 2}
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
                            {'label': 'Bicep Curl', 'value': 2}
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
            ])
        ])


# Callback for the Last Workout Tab with Pie Chart
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
        pie_chart.update_layout(title='Efficiency in Last Workout')

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
     Output('specific-exercise-progress-graph', 'figure')],
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
        text=f"WoW Improvement: {wow}",  # The wow text
        xref="paper", yref="paper",
        x=0.5, y=1.1,  # relative position
        showarrow=False,  # No arrow
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

    # Specific Exercise Progress DataFrame
    specific_data = UserExercise.query.filter_by(exercise_id=exercise_id, user_id=session['user_id']).all()
    specific_df = pd.DataFrame([{
        'date': record.date,
        'rom_score': record.rom_score,
        'tut_score': record.tut_score,
        'rep_number': record.total_reps,
        'count': record.count,
    } for record in specific_data])

    specific_df = specific_df.groupby('date').agg({
        'rom_score': 'mean',
        'tut_score': 'mean',
        'rep_number': 'sum',
        'count': 'sum'
    }).reset_index()

    specific_line_chart = go.Figure()
    specific_line_chart.add_trace(go.Scatter(x=specific_df['date'], y=specific_df['count'],
                                             mode='lines+markers', name='Efficient Reps'))
    specific_line_chart.add_trace(go.Scatter(x=specific_df['date'], y=specific_df['rep_number'],
                                             mode='lines+markers', name='Total Reps'))
    specific_line_chart.update_layout(title='Specific Exercise Progress',
                                      xaxis_title='Date', yaxis_title='Efficiency')

    return overall_line_chart, specific_line_chart


@app.route("/dash/")
def render_dashboard():
    return dash_app.index()


def gen_frames(exercise, user_id, rep_goal):
    if exercise == 'shoulder_press':
        print('spress')
        return gen_frames_shoulder_press(user_id, rep_goal)
    elif exercise == 'dumbbell_curls':
        print('bcurls')
        return gen_frames_bicep_curls(user_id, rep_goal)
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

    exercise_dates = db.session.query(UserExercise.date).filter_by(user_id=user_id).distinct().order_by(
        UserExercise.date).all()

    exercise_dates = [date[0].date() for date in exercise_dates]

    streak = 0
    for i in range(1, len(exercise_dates)):
        if exercise_dates[i] == exercise_dates[i - 1] + timedelta(days=1):
            streak += 1
        else:
            break

    return render_template('mainboard.html', search_form=search_form,
                           first_session=first_session, efficiency=efficiency, total_exercises= total_exercises,
                           total_reps = total_reps, exercises_this_week=exercises_this_week, streak=streak)


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    search_form = SearchForm()
    user_id = session.get('user_id')

    user_details = User.query.filter_by(id=user_id).first()

    if user_details:
        print('success fetching user details')
        username = user_details.username

    return render_template('profile.html', search_form=search_form,
                           username=username)


@app.route('/search_exercises', methods=['GET'])
def search_exercises():
    query = request.args.get('query', '').strip()
    if query:
        exercises = Exercises.query.filter(Exercises.name.ilike(f'%{query}%')).all()
        results = [{'name': exercise.name, 'link': exercise.link} for exercise in exercises]
        return jsonify(results)
    return jsonify([])


@app.route('/exercises', methods=['GET', 'POST'])
def exercises():
    print(session['user_id'])
    search_form = SearchForm()
    return render_template('exercises.html', search_form=search_form)


@app.route('/leaderboard', methods=['GET', 'POST'])
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
    user_id = session.get('user_id')
    rep_goal = db.session.query(User.rep_goal).filter_by(id=user_id).scalar()
    return render_template('start.html', search_form=search_form, exercise=exercise, user_id=user_id, rep_goal=rep_goal)


@app.route('/video_feed/<exercise>/<int:user_id>/<int:rep_goal>')
def video_feed(exercise, user_id, rep_goal):
    return Response(gen_frames(exercise, user_id, rep_goal), mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__ == "__main__":
    app.run()
