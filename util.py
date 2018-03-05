import time
from functools import wraps
from bottle import request, redirect, response, HTTPError


def make_login_required_decorator(session_manager):

    def login_required(login_uri='/login/', session_store=session_manager):

        def decorator(fn):

            @wraps(fn)
            def validate_user(*a, **ka):
                if not request.auth or request.auth[0] not in session_store:
                    response.set_cookie(
                        'login_redirect',
                        request.fullpath, path='/',
                        expires=(int(time.time()) + 3600))
                    redirect(login_uri)
                else:
                    fn(*a, **ka)
            return validate_user

        return decorator
    return login_required
"""
            def check_auth(*a, **ka):
                try:
                    data = session_manager.get_session()
                    if not data['valid']:
                        raise KeyError('Invalid login')
                except (KeyError, TypeError):
                    bottle.response.set_cookie(
                        'validuserloginredirect',
                        bottle.request.fullpath, path='/',
                        expires=(int(time.time()) + 3600))
                    bottle.redirect(login_url)
"""

def authenticator(session_manager, validate_user, login_url='/auth/login'):
    '''Create an authenticator decorator.
    :param session_manager: A session manager class to be used for storing
            and retrieving session data.  Probably based on
            :class:`BaseSession`.
    :param login_url: The URL to redirect to if a login is required.
            (default: ``'/auth/login'``).
    '''
    def valid_user(login_url=login_url):
        def decorator(handler, *a, **ka):
            import functools

            @functools.wraps(handler)
            def check_auth(*a, **ka):
                try:
                    if not validate_user():
                        raise KeyError('Invalid login')
                except (KeyError, TypeError):
                    response.set_cookie(
                        'login_redirect',
                        request.fullpath, path='/',
                        expires=(int(time.time()) + 3600))
                    redirect(login_url)
                return handler(*a, **ka)
            return check_auth
        return decorator
    return(valid_user)



def auth_basic(check, realm="private", text="Access denied"):

    def decorator(func):
        @wraps(func)
        def wrapper(*a, **ka):
            user, password = request.auth or (None, None)
            if user is None or not check(user, password):
                err = HTTPError(401, text)
                err.add_header('WWW-Authenticate', 'Basic realm="%s"' % realm)
                return err
            return func(*a, **ka)

        return wrapper
    return decorator
