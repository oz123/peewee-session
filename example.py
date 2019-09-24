"""
This example is based on the code example from bottle-session by
Christopher De Vries (https://github.com/devries/bottle-session).
"""

import bottle
import random
import string
import time

from bottle import request, response, HTTPResponse, template
from peewee_session import PeeweeSessionPlugin
from util import authenticator, generate_token

from peewee import SqliteDatabase

db = SqliteDatabase('test.db')

CONFIG = {'db': db}


app = bottle.app()
app.config.update(CONFIG)

session_plugin = PeeweeSessionPlugin(
    cookie_lifetime='10 seconds',
    db_conn=db, cookie_secret='very-s3kr3t-s4lt')

app.install(session_plugin)

csrf_token = generate_token(20)

username = "Mellanie"
PASSWORD = "StickyNotesOnTheBackofYourScreenAren'tSafe"


class User:
    @staticmethod
    def verify_password(user, password):
        if user == username and password == PASSWORD:
            return True
        else:
            return False


login_required = authenticator(session_plugin.session_manager,
                               csrf_token,
                               User.verify_password, app,
                               '/login',
                               redirect_success="/",
                               session_cookie='coldswaet-cookie'
                               )


@app.route('/')
@login_required()
def get_main_page(session):

    if session.load('name') is None:
        context = {'csrf_token': csrf_token}

        return bottle.template('set_name', **context)

    else:
        context = {'csrf_token': csrf_token,
                   'name': session.load('name'),
                   'trigger': session.load('trigger')
                   }

        return bottle.template('has_name', **context)


@app.route('/submit', method='POST')
def set_name(session):
    session['name'] = request.forms.name.strip()
    csrf_submitted = request.forms.get('csrf_token')

    if csrf_submitted != csrf_token:
        return template('error',
                        warning_message='Cross-site scripting error.')

    bottle.redirect('/')


@app.route('/logout')
def logout(session):
    del session['name']
    response = HTTPResponse(
                body="Bye!",
                status=200,
                )
    response.delete_cookie('login_redirect',
                        path='/',)
    return response


if __name__ == '__main__':
    bottle.debug(True)
    bottle.run(app=app, host='127.0.0.1', port=8080)
