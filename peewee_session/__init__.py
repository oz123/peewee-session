"""
This file is distributed under the terms of the LGPL v3.
Copyright Oz N Tiram <oz.tiram@gmail.com> 2018
"""

import base64
import datetime
import hashlib
import hmac
import inspect
import json
import re
import time
import uuid

import peewee

from bottle import PluginError
from passlib.utils import rng, getrandbytes

__version__ = '0.1'

UNITS = ('days', 'hours', 'minutes', 'seconds')

TRIGGER_SQL = """
CREATE TRIGGER IF NOT EXISTS clean_old_sessions
AFTER INSERT ON {}
BEGIN
DELETE FROM {} WHERE DATETIME(timestamp) <= DATETIME('now', '-{} {}');
END;
"""


class SessionError(Exception):
    pass


def getUuid():
    return uuid.UUID(bytes=getrandbytes(rng, 16))


class PeeweeSessionPlugin:
    """Bottle sessions using peewee.

    This class creates a plugin for the bottle framework which uses cookies
    to handle sessions and stores session information in a peewee supported
    database.
    """

    name = 'peewee-session'
    api = 2

    def __init__(self, db_conn=None, cookie_secret=None,
                 cookie_name='peewee.session',
                 cookie_lifetime='7 days', keyword='session'):
        """Session plugin for the bottle framework.

        Args:
            cookie_name (str): The name of the browser cookie in which to
            store the session id. Defaults to 'bottle.session'.
            cookie_lifetime (int): The lifetime of the cookie in seconds.
            When the cookie's lifetime expires it will be deleted from
            the redis  database. The browser should also cause it to expire.
            If the value is 'None' then the cookie will expire from the redis
            database in 7 days and will be a session cookie on the
            browser. The default value is 300 seconds.
            keyword (str): The bottle plugin keyword. By default this is
            'session'.

        Returns:
            A bottle plugin object.
        """

        self.cookie_name = cookie_name
        self.cookie_secret = cookie_secret
        self.cookie_lifetime = cookie_lifetime
        self.keyword = keyword
        self.db_conn = db_conn
        self.session_manager = None

    def setup(self, app):
        for other in app.plugins:
            if not isinstance(other, PeeweeSessionPlugin):
                continue
            if other.keyword == self.keyword:
                raise PluginError(
                    "Found another session plugin with "
                    "conflicting settings (non-unique keyword).")
        # app config should contain a handle to peewee db instance
        # creation of tables should be done here!
        # we should default to using the same db of the app, but we can use
        # another

        if not self.db_conn:
            self.db_conn = app.config.get('db')

        if not self.cookie_secret:
            self.cookie_secret = app.config.get('cookie-secret')

        if not re.match('\d+ (%s)' % "|".join(UNITS), self.cookie_lifetime):
            raise PluginError('cookie_lifetime misconfigured')
        ttl, ttl_unit = self.cookie_lifetime.split(' ')

        session_model = model_factory(self.db_conn,
                                      app.config.get('session-table',
                                                     'sessions'))
        self.session_manager = SessionManager(self.db_conn,
                                              session_model,
                                              self.cookie_secret,
                                              ttl=int(ttl), ttl_unit=ttl_unit
                                              )

    def apply(self, callback, context):
        args = inspect.getfullargspec(callback)[0]

        if self.keyword not in args:
            return callback

        def wrapper(*args, **kwargs):
            kwargs[self.keyword] = self.session_manager
            rv = callback(*args, **kwargs)
            return rv
        return wrapper


def for_all_methods(decorator):
    """
    Decorate all class methods with a function
    """
    def decorate(cls):
        methods = inspect.getmembers(cls, predicate=inspect.ismethod)
        for name, method in methods:
            if name == '__init__':
                continue
            setattr(cls, name, decorator(method))

        return cls
    return decorate


def open_close_db(fn):
    """
    A helper to patch a method with action before and after
    """
    from functools import wraps

    @wraps(fn)
    def wrapper(self, *args, **kwargs):
        self.db.connect()
        rv = fn(self, *args, **kwargs)
        self.db.close()
        return rv

    return wrapper


def model_factory(db_conn, table='sessions'):

    class SessionStore(peewee.Model):

        class Meta:
            database = db_conn
            table_name = table

        id = peewee.CharField(unique=True)
        timestamp = peewee.DateTimeField(default=datetime.datetime.utcnow)
        data = peewee.TextField()

    return SessionStore


@for_all_methods(open_close_db)
class BaseSessionManager:

    """
    BaseSessionManager - a session manager that uses peewee.

    This session manager class is dumb and saves the information
    in the database and the cookie in clear text.

    Do not use it in real production. Instead you should use
    SessionManager
    """

    def __init__(self, db_conn, model, ttl=None, ttl_unit='minutes'):
        """
        param str: database file path
        param model: a Model instance

        Both model and db are currently using Peewee ORM, but it's easy to
        change this to another ORM.
        """
        self.db_conn = db_conn
        self.model = model
        self.db_conn.create_tables([model])
        if ttl and not isinstance(ttl, int):
            raise ValueError("ttl must be an integer.")
        if ttl_unit not in UNITS:
            raise ValueError("Illegal ttl_unit.")
        if ttl:
            sessions_table = model._meta.table_name
            self.model.raw(
                TRIGGER_SQL.format(
                    sessions_table, sessions_table, ttl, ttl_unit)).execute()

        self.db_conn.close()

    def __setitem__(self, id, data):
        fields = {"id": id}
        fields.update({"data": json.dumps(data)})
        query = self.model.insert(**fields).on_conflict_replace()
        query.execute()

    def __getitem__(self, id):
        try:
            data = self.model.select().where(self.model.id == id).get().data
        except self.model.DoesNotExist:
            raise SessionError("Item not found %s" % id)
        data = json.loads(data)
        return data

    def __delitem__(self, key):
        self.model.delete().where(self.model.id == key).execute()

    def __contains__(self, id):
        rv = self.model.select().where(self.model.id == id).exists()
        return rv

    def pop(self, key):
        val = self.__getitem__(key)
        self.__delitem__(key)
        return val


@for_all_methods(open_close_db)
class SessionManager(BaseSessionManager):

    """
    A Session manager that helps you save data in SQLite in a safe manner.

    It adds `load` and `save` methods that wrap your values properly.
    """
    encoding = 'utf-8'

    def __init__(self, db_conn, model, secret, hash=hashlib.sha256,
                 ttl=None, ttl_unit='minutes'):
        super().__init__(db_conn, model, ttl, ttl_unit)
        self.secret = secret

    def create_signature(self, value, timestamp):
        h = hmac.new(self.secret.encode(), digestmod=hashlib.sha1)
        h.update(timestamp)
        h.update(value)
        return h.hexdigest()

    def __setitem__(self, id, data):
        data = json.dumps(data, indent=None, separators=(',', ':'))
        data = self.encrypt(data)
        super().__setitem__(id, data)

    def __getitem__(self, id):
        data = super().__getitem__(id)
        data = self.decrypt(data)
        data = json.loads(data)
        return data

    def load(self, id):
        try:
            return self.__getitem__(id)
        except SessionError:
            pass

    def get(self, key, default=None):
        return self.load(key) or default

    def save(self, id, data):
        self.__setitem__(id, data)

    def encrypt(self, value):
        timestamp = str(int(time.time())).encode()
        value = base64.b64encode(value.encode(self.encoding))
        signature = self.create_signature(value, timestamp)
        return "|".join([value.decode(self.encoding),
                         timestamp.decode(self.encoding), signature])

    def decrypt(self, value):
        value, timestamp, signature = value.split("|")
        check = self.create_signature(value.encode(self.encoding),
                                      timestamp.encode())
        if check != signature:
            return None

        return base64.b64decode(value).decode(self.encoding)

    def _create_signature(self, value, timestamp):
        h = hmac.new(self.secret.encode(), digestmod=self.hash)
        h.update(timestamp)
        h.update(value)
        return h.hexdigest()
