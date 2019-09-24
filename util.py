import base64
import hashlib
import hmac
import json
import pickle
import string
import time

from functools import wraps
from random import choice

from bottle import (request, abort, HTTPError, tob, _lscmp,
                     redirect, response, template)


def generate_token(length):
    '''Generate a random string using range [a-zA-Z0-9].'''
    chars = string.ascii_letters + string.digits
    return ''.join([choice(chars) for i in range(length)])


def authenticator(session_manager, csrf_token, check, app,
                  login_url='/auth/login/', redirect_success="/admin/",
                  message="Permission denied",
                  session_cookie='session-cookie',
                  login_template='login.tpl'
                  ):
    '''Create an authenticator decorator.
    :param session_manager: A session manager class to be used for storing
            and retrieving session data.  Probably based on
            :class:`BaseSession`.
    :param login_url: The URL to redirect to if a login is required.
            (default: ``'/auth/login'``).

    This authenticator needs a form based login.

    Your login form should include at least:

        <form action="/login" method="post">
            username: <input name="username" type="text" />
            password: <input name="password" type="password" />
            <input value="Login" type="submit" />
        </form>
    If you want to customize the templated with extra variables, you can a
    context to the login template via ``app.config``. It should have a key
    called ``authcontext``, and it's value can be a dictionary containing the
    variables you want to pass.
    '''

    context = app.config.get("authcontext", {})

    def l_form_p():
        username = request.forms.get('username')
        password = request.forms.get('password')
        if check(username, password):
            token = generate_token(64)
            session_manager[username] = {'token': token}
            response.set_cookie(session_cookie,
                                json.dumps({"username": username,
                                            "token": token}),
                                secret=session_manager.secret,
                                path='/',
                                expires=(int(time.time()) + 3600))
            return redirect(redirect_success)
        else:
            return template(login_template,
                            csrf_token=csrf_token,
                            url=login_url,
                            **context)
    def l_form_g():
        return template(login_template,
                        csrf_token=csrf_token,
                        url=login_url,
                        **context)

    app.route(path=login_url, callback=l_form_g, method=["GET"])
    app.route(path=login_url, callback=l_form_p, method=["POST"])

    def valid_user(login_url=login_url):
        def decorator(handler, *a, **ka):
            import functools
            @functools.wraps(handler)
            def check_auth(*a, **ka):

                try:
                    cookie = json.loads(
                        request.get_cookie(
                            session_cookie, secret=session_manager.secret))
                except Exception:
                    cookie = {}

                if not cookie:
                    redirect(login_url)

                if 'token' and 'username' in cookie:
                    cookie_token = cookie['token']
                    s_token = session_manager.get(
                        cookie['username'], {}).get('token')

                    if not s_token == cookie_token:
                        redirect(login_url)

                ka['session'] = session_manager

                return handler(*a, **ka)
            return check_auth
        return decorator
    return valid_user
