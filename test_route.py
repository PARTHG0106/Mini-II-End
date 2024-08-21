import pytest
from flask import session as flask_session
from app import app as flask_app, db
from models import User


@pytest.fixture(scope='module')
def app():
    flask_app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
    })

    yield flask_app


@pytest.fixture(scope='function')
def init_database():
    with flask_app.app_context():
        if not User.query.filter_by(username="newuser").first():
            user = User(username="newuser", email="newuser@example.com")
            user.set_password("newpassword")
            db.session.add(user)
            db.session.commit()

        yield db


def test_successful_login(client, init_database):
    #with correct data.
    response = client.post('/login', data={
        'username': 'newuser',
        'password': 'newpassword',
        'login_submit': '1'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'Workouts Completed' in response.data
    assert flask_session['user_id'] == User.query.filter_by(username='newuser').first().id


def test_failed_login(client, init_database):
    #with incorrect data.
    response = client.post('/login', data={
        'username': 'newuser',
        'password': 'wrongpassword',
        'login_submit': '1'
    }, follow_redirects=True)

    print(response.data)
    assert response.status_code == 200
    assert b'Invalid username or password' in response.data
    assert 'user_id' not in flask_session


def test_successful_registration(client, init_database):
    #registration of a new user.
    response = client.post('/login', data={
        'username': 'anotheruser',
        'email': 'anotheruser@example.com',
        'password': 'anotherpassword',
        'password2': 'anotherpassword',
        'register_submit': '1'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'Workouts Completed' in response.data
    new_user = User.query.filter_by(username='anotheruser').first()
    assert new_user is not None
    assert flask_session['user_id'] == new_user.id


def test_registration_with_existing_username_or_email(client, init_database):
   #registration with existing data.
    if not User.query.filter_by(username="uniqueuser").first():
        client.post('/login', data={
            'username': 'uniqueuser',
            'email': 'uniqueuser@example.com',
            'password': 'uniquepassword',
            'password2': 'uniquepassword',
            'register_submit': '1'
        }, follow_redirects=True)


    response = client.post('/login', data={
        'username': 'uniqueuser',
        'email': 'anotheremail@example.com',
        'password': 'anotherpassword',
        'password2': 'anotherpassword',
        'register_submit': '1'
    }, follow_redirects=True)

    print(response.data)
    assert response.status_code == 200
    assert b'Registration failed. Please choose a different username.' in response.data

    # Registering with the same email
    response = client.post('/login', data={
        'username': 'differentuser',
        'email': 'uniqueuser@example.com',
        'password': 'anotherpassword',
        'password2': 'anotherpassword',
        'register_submit': '1'
    }, follow_redirects=True)

    print(response.data)
    assert response.status_code == 200
    assert b'Please use a different email address.' in response.data
