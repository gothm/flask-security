# -*- coding: utf-8 -*-
"""
    flask.ext.security.utils
    ~~~~~~~~~~~~~~~~~~~~~~~~

    Flask-Security utils module

    :copyright: (c) 2012 by Matt Wright.
    :license: MIT, see LICENSE for more details.
"""

import base64
import hashlib
import hmac
import os
from contextlib import contextmanager
from datetime import datetime, timedelta

from flask import url_for, flash, current_app, request, session, render_template
from flask.ext.login import make_secure_token, login_user as _login_user, \
     logout_user as _logout_user
from flask.ext.principal import Identity, AnonymousIdentity, identity_changed
from werkzeug.local import LocalProxy

from .signals import user_registered, password_reset_requested


# Convenient references
_security = LocalProxy(lambda: current_app.extensions['security'])

_datastore = LocalProxy(lambda: _security.datastore)

_pwd_context = LocalProxy(lambda: _security.pwd_context)

_logger = LocalProxy(lambda: current_app.logger)


def login_user(user, remember=True):
    """Performs the login and sends the appropriate signal."""

    if not _login_user(user, remember):
        return False

    if user.authentication_token is None:
        user.authentication_token = generate_authentication_token(user)

    if remember:
        user.remember_token = get_remember_token(user.email, user.password)

    if _security.trackable:
        old_current, new_current = user.current_login_at, datetime.utcnow()
        user.last_login_at = old_current or new_current
        user.current_login_at = new_current

        old_current, new_current = user.current_login_ip, request.remote_addr
        user.last_login_ip = old_current or new_current
        user.current_login_ip = new_current

        user.login_count = user.login_count + 1 if user.login_count else 0

    _datastore._save_model(user)

    identity_changed.send(current_app._get_current_object(),
                          identity=Identity(user.id))

    _logger.debug('User %s logged in' % user)
    return True


def logout_user():
    for key in ('identity.name', 'identity.auth_type'):
        session.pop(key, None)

    identity_changed.send(current_app._get_current_object(),
                          identity=AnonymousIdentity())

    _logout_user()


def get_hmac(msg, salt=None, digestmod=None):
    digestmod = digestmod or hashlib.sha512
    return base64.b64encode(hmac.new(salt, msg, digestmod).digest())


def verify_password(password, password_hash, salt=None, use_hmac=False):
    hmac_value = get_hmac(password, salt) if use_hmac else password
    return _pwd_context.verify(hmac_value, password_hash)


def encrypt_password(password, salt=None, use_hmac=False):
    hmac_value = get_hmac(password, salt) if use_hmac else password
    return _pwd_context.encrypt(hmac_value)


def generate_authentication_token(user):
    """Generates a unique authentication token for the specified user.

    :param user: The user to work with
    """
    data = [str(user.id), md5(user.email)]
    return _security.token_auth_serializer.dumps(data)


def md5(data):
    return hashlib.md5(data).hexdigest()


def generate_token():
    """Generate an arbitrary URL safe token."""
    return base64.urlsafe_b64encode(os.urandom(30))


def get_remember_token(email, password):
    assert email is not None
    assert password is not None
    return make_secure_token(email, password)


def do_flash(message, category=None):
    """Flash a message depending on if the `FLASH_MESSAGES` configuration
    value is set.

    :param message: The flash message
    :param category: The flash message category
    """
    if config_value('FLASH_MESSAGES'):
        flash(message, category)


def get_url(endpoint_or_url):
    """Returns a URL if a valid endpoint is found. Otherwise, returns the
    provided value.

    :param endpoint_or_url: The endpoint name or URL to default to
    """
    try:
        return url_for(endpoint_or_url)
    except:
        return endpoint_or_url


def get_post_login_redirect():
    """Returns the URL to redirect to after a user logs in successfully."""
    return (get_url(request.args.get('next')) or
            get_url(request.form.get('next')) or
            find_redirect('SECURITY_POST_LOGIN_VIEW'))


def find_redirect(key):
    """Returns the URL to redirect to after a user logs in successfully.

    :param key: The session or application configuration key to search for
    """
    result = (get_url(session.pop(key.lower(), None)) or
              get_url(current_app.config[key.upper()] or None) or '/')

    session.pop(key.lower(), None)

    return result


def get_config(app):
    """Conveniently get the security configuration for the specified
    application without the annoying 'SECURITY_' prefix.

    :param app: The application to inspect
    """
    items = app.config.items()
    prefix = 'SECURITY_'

    def strip_prefix(tup):
        return (tup[0].replace('SECURITY_', ''), tup[1])

    return dict([strip_prefix(i) for i in items if i[0].startswith(prefix)])


def get_message(key, **kwargs):
    rv = config_value('MSG_' + key)
    return rv[0] % kwargs, rv[1]


def config_value(key, app=None, default=None):
    """Get a Flask-Security configuration value.

    :param key: The configuration key without the prefix `SECURITY_`
    :param app: An optional specific application to inspect. Defaults to Flask's
                `current_app`
    :param default: An optional default value if the value is not set
    """
    app = app or current_app
    return get_config(app).get(key.upper(), default)


def get_max_age(key, app=None):
    now = datetime.utcnow()
    expires = now + get_within_delta(key + '_WITHIN', app)
    return int(expires.strftime('%s')) - int(now.strftime('%s'))


def get_within_delta(key, app=None):
    """Get a timedelta object from the application configuration following
    the internal convention of::

        <Amount of Units> <Type of Units>

    Examples of valid config values::

        5 days
        10 minutes

    :param key: The config value key without the 'SECURITY_' prefix
    :param app: Optional application to inspect. Defaults to Flask's
                `current_app`
    """
    txt = config_value(key, app=app)
    values = txt.split()
    return timedelta(**{values[1]: int(values[0])})


def send_mail(subject, recipient, template, context=None):
    """Send an email via the Flask-Mail extension.

    :param subject: Email subject
    :param recipient: Email recipient
    :param template: The name of the email template
    :param context: The context to render the template with
    """
    mail = current_app.extensions.get('mail', None)
    current_app.logger.debug('%s' % current_app.extensions)

    if mail is None:
        raise RuntimeError('You need to install and configure the '
                           'Flask-Mail extension in order to send '
                           'emails with Flask-Security')

    from flask.ext.mail import Message

    context = context or {}

    msg = Message(subject,
                  sender=_security.email_sender,
                  recipients=[recipient])

    base = 'security/email'
    msg.body = render_template('%s/%s.txt' % (base, template), **context)
    msg.html = render_template('%s/%s.html' % (base, template), **context)

    mail.send(msg)


@contextmanager
def capture_registrations():
    """Testing utility for capturing registrations.

    :param confirmation_sent_at: An optional datetime object to set the
                                 user's `confirmation_sent_at` to
    """
    registrations = []

    def _on(data, app):
        registrations.append(data)

    user_registered.connect(_on)

    try:
        yield registrations
    finally:
        user_registered.disconnect(_on)


@contextmanager
def capture_reset_password_requests(reset_password_sent_at=None):
    """Testing utility for capturing password reset requests.

    :param reset_password_sent_at: An optional datetime object to set the
                                   user's `reset_password_sent_at` to
    """
    reset_requests = []

    def _on(request, app):
        reset_requests.append(request)

    password_reset_requested.connect(_on)

    try:
        yield reset_requests
    finally:
        password_reset_requested.disconnect(_on)
