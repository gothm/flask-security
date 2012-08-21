# -*- coding: utf-8 -*-
"""
    flask.ext.security.datastore
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    This module contains an user datastore classes.

    :copyright: (c) 2012 by Matt Wright.
    :license: MIT, see LICENSE for more details.
"""

from . import exceptions


class UserDatastore(object):
    """Abstracted user datastore. Always extend this class and implement the
    :attr:`_save_model`, :attr:`_delete_model`, :attr:`_do_find_user`,  and
    :attr:`_do_find_role` methods.

    :param db: An instance of a configured databse manager from a Flask
               extension such as Flask-SQLAlchemy or Flask-MongoEngine
    :param user_model: A user model class definition
    :param role_model: A role model class definition
    """
    pwd_context = None
    default_roles = []

    def __init__(self, db, user_model, role_model):
        self.db = db
        self.user_model = user_model
        self.role_model = role_model

    def _commit(self, *args, **kwargs):
        pass

    def _save_model(self, model, **kwargs):
        raise NotImplementedError(
            "User datastore does not implement _save_model method")

    def _delete_model(self, model):
        raise NotImplementedError(
            "User datastore does not implement _delete_model method")

    def _do_find_user(self, **kwargs):
        raise NotImplementedError(
            "User datastore does not implement _do_find_user method")

    def _do_find_role(self, **kwargs):
        raise NotImplementedError(
            "User datastore does not implement _do_find_role method")

    def _do_add_role(self, user, role):
        user, role = self._prepare_role_modify_args(user, role)
        if role not in user.roles:
            user.roles.append(role)
        return user

    def _do_remove_role(self, user, role):
        user, role = self._prepare_role_modify_args(user, role)
        if role in user.roles:
            user.roles.remove(role)
        return user

    def _do_toggle_active(self, user, active):
        user = self.find_user(email=user.email)
        if active != user.active:
            user.active = active
        return user

    def _do_deactive_user(self, user):
        return self._do_toggle_active(user, False)

    def _do_active_user(self, user):
        return self._do_toggle_active(user, True)

    def _prepare_role_modify_args(self, user, role):
        role = role.name if isinstance(role, self.role_model) else role
        return self.find_user(email=user.email), self.find_role(role)

    def _prepare_create_user_args(self, **kwargs):
        kwargs.setdefault('active', True)
        roles = kwargs.get('roles', [])

        for i, role in enumerate(roles):
            rn = role.name if isinstance(role, self.role_model) else role
            # see if the role exists
            roles[i] = self.find_role(rn)

        kwargs['roles'] = roles

        return kwargs

    def find_user(self, **kwargs):
        """Returns a user based on the specified identifier.

        :param user: User identifier, usually email address
        """
        user = self._do_find_user(**kwargs)
        if user:
            return user
        raise exceptions.UserNotFoundError('Parameters=%s' % kwargs)

    def find_role(self, role):
        """Returns a role based on its name.

        :param role: Role name
        """
        role = self._do_find_role(role)
        if role:
            return role
        raise exceptions.RoleNotFoundError()

    def create_role(self, **kwargs):
        """Creates and returns a new role.

        :param name: Role name
        """
        role = self.role_model(**kwargs)
        return self._save_model(role)

    def create_user(self, **kwargs):
        """Creates and returns a new user.

        :param email: Email address
        :param password: Unencrypted password
        :param active: The optional active state
        """
        user = self.user_model(**self._prepare_create_user_args(**kwargs))
        return self._save_model(user)

    def delete_user(self, user):
        """Delete the specified user

        :param user: The user to delete_user
        """
        self._delete_model(user)

    def add_role_to_user(self, user, role):
        """Adds a role to a user if the user does not have it already. Returns
        the modified user.

        :param user: A User instance or a user identifier
        :param role: A Role instance or a role name
        """
        return self._save_model(self._do_add_role(user, role))

    def remove_role_from_user(self, user, role):
        """Removes a role from a user if the user has the role. Returns the
        modified user.

        :param user: A User instance or a user identifier
        :param role: A Role instance or a role name
        """
        return self._save_model(self._do_remove_role(user, role))

    def deactivate_user(self, user):
        """Deactivates a user and returns the modified user.

        :param user: A User instance or a user identifier
        """
        return self._save_model(self._do_deactive_user(user))

    def activate_user(self, user):
        """Activates a user and returns the modified user.

        :param user: A User instance or a user identifier
        """
        return self._save_model(self._do_active_user(user))


class SQLAlchemyUserDatastore(UserDatastore):
    """A SQLAlchemy datastore implementation for Flask-Security that assumes the
    use of the Flask-SQLAlchemy extension.
    """

    def _commit(self, *args, **kwargs):
        self.db.session.commit()

    def _save_model(self, model):
        self.db.session.add(model)
        return model

    def _delete_model(self, model):
        self.db.session.delete(model)

    def _do_find_user(self, **kwargs):
        return self.user_model.query.filter_by(**kwargs).first()

    def _do_find_role(self, role):
        return self.role_model.query.filter_by(name=role).first()


class MongoEngineUserDatastore(UserDatastore):
    """A MongoEngine datastore implementation for Flask-Security that assumes
    the use of the Flask-MongoEngine extension.
    """

    def _save_model(self, model):
        model.save()
        return model

    def _delete_model(self, model):
        model.delete()

    def _do_find_user(self, **kwargs):
        return self.user_model.objects(**kwargs).first()

    def _do_find_role(self, role):
        return self.role_model.objects(name=role).first()
