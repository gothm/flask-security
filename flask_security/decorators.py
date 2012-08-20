# -*- coding: utf-8 -*-
"""
    flask.ext.security.decorators
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Flask-Security decorators module

    :copyright: (c) 2012 by Matt Wright.
    :license: MIT, see LICENSE for more details.
"""

from functools import wraps

from flask import current_app, Response, request, redirect
from flask.ext.login import current_user, login_required
from flask.ext.principal import RoleNeed, Permission, Identity, identity_changed
from werkzeug.local import LocalProxy

from . import utils
from .exceptions import UserNotFoundError


# Convenient references
_security = LocalProxy(lambda: current_app.extensions['security'])

_logger = LocalProxy(lambda: current_app.logger)


_default_unauthorized_html = """
    <h1>Unauthorized</h1>
    <p>The server could not verify that you are authorized to access the URL
    requested. You either supplied the wrong credentials (e.g. a bad password),
    or your browser doesn't understand how to supply the credentials required.</p>
    """


def _get_unauthorized_response(text=None, headers=None):
    text = text or _default_unauthorized_html
    headers = headers or {}
    return Response(text, 401, headers)


def _get_unauthorized_view():
    cv = utils.get_url(utils.config_value('UNAUTHORIZED_VIEW'))
    utils.do_flash(*utils.get_message('UNAUTHORIZED'))
    return redirect(cv or request.referrer or '/')


def _check_token():
    header_key = _security.token_authentication_header
    args_key = _security.token_authentication_key
    header_token = request.headers.get(header_key, None)
    token = request.args.get(args_key, header_token)
    serializer = _security.remember_token_serializer
    rv = False

    try:
        data = serializer.loads(token)
        user = _security.datastore.find_user(id=data[0])
        rv = utils.md5(user.password) == data[1]
    except:
        pass

    return rv


def _check_http_auth():
    auth = request.authorization or dict(username=None, password=None)

    try:
        user = _security.datastore.find_user(email=auth.username)
        if utils.verify_password(auth.password, user.password,
                                 salt=_security.password_salt,
                                 use_hmac=_security.password_hmac):
            identity_changed.send(current_app._get_current_object(),
                                  identity=Identity(user.id))
            return True
    except UserNotFoundError:
        return False


def http_auth_required(realm):
    """Decorator that protects endpoints using Basic HTTP authentication.
    The username should be set to the user's email address.

    :param realm: optional realm name"""

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if _check_http_auth():
                return fn(*args, **kwargs)
            r = _security.default_http_auth_realm if callable(realm) else realm
            h = {'WWW-Authenticate': 'Basic realm="%s"' % r}
            return _get_unauthorized_response(headers=h)
        return wrapper

    if callable(realm):
        return decorator(realm)
    return decorator


def auth_token_required(fn):
    """Decorator that protects endpoints using token authentication. The token
    should be added to the request by the client by using a query string
    variable with a name equal to the configuration value of
    `SECURITY_TOKEN_AUTHENTICATION_KEY` or in a request header named that of
    the configuration value of `SECURITY_TOKEN_AUTHENTICATION_HEADER`
    """

    @wraps(fn)
    def decorated(*args, **kwargs):
        if _check_token():
            return fn(*args, **kwargs)
        return _get_unauthorized_response()
    return decorated


def roles_required(*roles):
    """Decorator which specifies that a user must have all the specified roles.
    Example::

        @app.route('/dashboard')
        @roles_required('admin', 'editor')
        def dashboard():
            return 'Dashboard'

    The current user must have both the `admin` role and `editor` role in order
    to view the page.

    :param args: The required roles.
    """
    def wrapper(fn):
        @wraps(fn)
        def decorated_view(*args, **kwargs):
            perms = [Permission(RoleNeed(role)) for role in roles]
            for perm in perms:
                if not perm.can():
                    _logger.debug('Identity does not provide the '
                                  'roles: %s' % [r for r in roles])
                    return _get_unauthorized_view()
            return fn(*args, **kwargs)
        return decorated_view
    return wrapper


def roles_accepted(*roles):
    """Decorator which specifies that a user must have at least one of the
    specified roles. Example::

        @app.route('/create_post')
        @roles_accepted('editor', 'author')
        def create_post():
            return 'Create Post'

    The current user must have either the `editor` role or `author` role in
    order to view the page.

    :param args: The possible roles.
    """
    def wrapper(fn):
        @wraps(fn)
        def decorated_view(*args, **kwargs):
            perm = Permission(*[RoleNeed(role) for role in roles])
            if perm.can():
                return fn(*args, **kwargs)
            r1 = [r for r in roles]
            r2 = [r.name for r in current_user.roles]
            _logger.debug('Current user does not provide a required role. '
                          'Accepted: %s Provided: %s' % (r1, r2))
            return _get_unauthorized_view()
        return decorated_view
    return wrapper
