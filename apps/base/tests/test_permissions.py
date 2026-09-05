from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from apps.base.api.user.viewsPermissions import (
    IsAdminOrCreator, IsWorkerOrCreator, isCreator, isWorker,
)
from apps.base.models import TipoUsuario
from apps.base.tests.factories import make_company, make_user


def _check(perm_cls, user):
    req = APIRequestFactory().get("/")
    req.user = user
    return perm_cls().has_permission(req, view=None)


class RolePermissionTest(TestCase):
    def setUp(self):
        self.company, self.creador = make_company()
        self.worker = make_user("wrk", tipo=TipoUsuario.WORKER, company=self.company)
        self.cliente = make_user("cli", tipo=TipoUsuario.CLIENTE)

    def test_is_creator(self):
        self.assertTrue(_check(isCreator, self.creador))
        self.assertFalse(_check(isCreator, self.worker))
        self.assertFalse(_check(isCreator, self.cliente))

    def test_is_worker(self):
        self.assertTrue(_check(isWorker, self.worker))
        self.assertFalse(_check(isWorker, self.creador))

    def test_worker_or_creator_incluye_admin(self):
        admin = make_user("adm", tipo="admin", company=self.company)
        self.assertTrue(_check(IsWorkerOrCreator, self.worker))
        self.assertTrue(_check(IsWorkerOrCreator, self.creador))
        self.assertTrue(_check(IsWorkerOrCreator, admin))
        self.assertFalse(_check(IsWorkerOrCreator, self.cliente))

    def test_admin_or_creator(self):
        self.assertTrue(_check(IsAdminOrCreator, self.creador))
        self.assertFalse(_check(IsAdminOrCreator, self.worker))

    def test_anonimo_siempre_false(self):
        self.assertFalse(_check(isCreator, AnonymousUser()))
        self.assertFalse(_check(IsWorkerOrCreator, AnonymousUser()))

    def test_usuario_inactivo_false(self):
        self.creador.is_active = False
        self.creador.save()
        self.assertFalse(_check(isCreator, self.creador))
