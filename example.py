"""
This example is based on the code example from bottle-session by
Christopher De Vries (https://github.com/devries/bottle-session).
"""

import bottle
import random
import string

from peewee_session import PeeweeSessionPlugin

from peewee import SqliteDatabase

db = SqliteDatabase('test.db')

CONFIG = {'db': db}


app = bottle.app()
app.config.update(CONFIG)

session_plugin = PeeweeSessionPlugin(
    cookie_lifetime='10 seconds',
    db_conn=db, cookie_secret='very-s3kr3t-s4lt')

app.install(session_plugin)

csrf = ''.join(random.choice(
            string.ascii_uppercase+string.ascii_lowercase+string.digits)
            for x in range(32))


@app.route('/')
def get_main_page(session):

    if session.load('name') is None:
        context = {'csrf_token': csrf}

        return bottle.template('set_name', **context)

    else:
        context = {'csrf_token': csrf,
                   'name': session.load('name'),
                   'trigger': session.load('trigger')
                   }

        return bottle.template('has_name', **context)


@app.route('/trigger')
def get_trigger_page(session):

    session['csrf'] = csrf

    if session.load('trigger') is None:
        context = {'csrf_token': csrf}

        return bottle.template('set_trigger', **context)

    else:
        context = {'csrf_token': csrf,
                   'name': session.load('name'),
                   'trigger': session.load('trigger')
                   }

        return bottle.template('has_name', **context)


@app.route('/submit-trigger', method='POST')
def set_trigger(session):
    session['trigger'] = bottle.request.forms.trigger.strip()
    csrf_submitted = bottle.request.forms.get('csrf_token')

    if csrf_submitted != csrf:
        return bottle.template('error',
                               warning_message='Cross-site scripting error.')

    bottle.redirect('/trigger')


@app.route('/submit', method='POST')
def set_name(session):
    session['name'] = bottle.request.forms.name.strip()
    csrf_submitted = bottle.request.forms.get('csrf_token')

    if csrf_submitted != csrf:
        return bottle.template('error',
                               warning_message='Cross-site scripting error.')

    bottle.redirect('/')


@app.route('/logout')
def logout(session):
    del session['name']
    bottle.redirect('/')


if __name__ == '__main__':
    bottle.debug(True)
    bottle.run(app=app, host='127.0.0.1', port=8080)
