# -*- coding: utf-8 -*-
"""
    flask.ext.security.script
    ~~~~~~~~~~~~~~~~~~~~~~~~~

    Flask-Security script module

    :copyright: (c) 2012 by Matt Wright.
    :license: MIT, see LICENSE for more details.
"""
try:
    import simplejson as json
except ImportError:
    import json

import re

from flask.ext.script import Command, Option
from flask.ext.security import user_datastore


def pprint(obj):
    print json.dumps(obj, sort_keys=True, indent=4)


def commit(fn):
    def wrapper(*args, **kwargs):
        fn(*args, **kwargs)
        _datastore._commit()
    return wrapper


class CreateUserCommand(Command):
    """Create a user"""

    option_list = (
        Option('-e', '--email',    dest='email',    default=None),
        Option('-p', '--password', dest='password', default=None),
        Option('-a', '--active',   dest='active',   default=''),
        Option('-r', '--roles',    dest='roles',    default=''),
    )

    @commit
    def run(self, **kwargs):
        # sanitize active input
        ai = re.sub(r'\s', '', str(kwargs['active']))
        kwargs['active'] = ai.lower() in ['', 'y', 'yes', '1', 'active']

        # sanitize role input a bit
        ri = re.sub(r'\s', '', kwargs['roles'])
        kwargs['roles'] = [] if ri == '' else ri.split(',')
        kwargs['password'] = encrypt_password(kwargs['password'])

        user_datastore.create_user(**kwargs)

        print 'User created successfully.'
        kwargs['password'] = '****'
        pprint(kwargs)


class CreateRoleCommand(Command):
    """Create a role"""

    option_list = (
        Option('-n', '--name', dest='name', default=None),
        Option('-d', '--desc', dest='description', default=None),
    )

    @commit
    def run(self, **kwargs):
        user_datastore.create_role(**kwargs)
        print 'Role "%(name)s" created successfully.' % kwargs


class _RoleCommand(Command):
    option_list = (
        Option('-u', '--user', dest='user_identifier'),
        Option('-r', '--role', dest='role_name'),
    )


class AddRoleCommand(_RoleCommand):
    """Add a role to a user"""

    @commit
    def run(self, user_identifier, role_name):
        _datastore.add_role_to_user(user_identifier, role_name)
        print "Role '%s' added to user '%s' successfully" % (role_name, user_identifier)


class RemoveRoleCommand(_RoleCommand):
    """Add a role to a user"""

    @commit
    def run(self, user_identifier, role_name):
        _datastore.remove_role_from_user(user_identifier, role_name)
        print "Role '%s' removed from user '%s' successfully" % (role_name, user_identifier)


class _ToggleActiveCommand(Command):
    option_list = (
        Option('-u', '--user', dest='user_identifier'),
    )


class DeactivateUserCommand(_ToggleActiveCommand):
    """Deactive a user"""

    @commit
    def run(self, user_identifier):
        _datastore.deactivate_user(user_identifier)
        print "User '%s' has been deactivated" % user_identifier


class ActivateUserCommand(_ToggleActiveCommand):
    """Deactive a user"""

    @commit
    def run(self, user_identifier):
        pass

class GenerateBlueprintCommand(Command):
    """Generate a Flask-Security blueprint object"""

    option_list = (
        Option('--output', '-o', dest='output', default=None),
    )

    def run(self, output):
        output = os.path.join(os.getcwd(), output) if output else 'security.py'

        if os.path.exists(output):
            msg = 'File %s exists. Do you want to overwrite it?' % output
            if not prompt_bool(msg):
                return

        with open(output, 'w') as o:
            source = inspect.getfile(views).replace('.pyc', '.py')

            with open(source, 'r') as s:
                to_remove = '"""' + views.__doc__ + '"""'
                to_replace = """
\"""
    Flask-Security
    ~~~~~~~~~~~~~~

    This module was generated by Flask-Security to give developers greater
    control over the various security mechanisms. For more information about
    using this feature see:

    TODO: Documentation URL
\"""
"""
                contents = s.read().replace(to_remove, to_replace)
                o.write(contents)

        print 'File generated successfully.'
        print output
=======
        user_datastore.activate_user(user_identifier)
        print "User '%s' has been activated" % user_identifier
>>>>>>> 0ddbcdca06435d83188c5f8ba16c0c6f72940671
=======
>>>>>>> da9f683c2231b79f8becf0bf18b9a32e5c3c005b
