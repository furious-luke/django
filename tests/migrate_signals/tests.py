from django.apps import apps
from django.core import management
from django.db.models import signals
from django.test import TestCase, override_settings
from django.utils import six

APP_CONFIG = apps.get_app_config('migrate_signals')
SIGNAL_ARGS = ['app_config', 'verbosity', 'interactive', 'using']
MIGRATE_DATABASE = 'default'
MIGRATE_VERBOSITY = 1
MIGRATE_INTERACTIVE = False


class Receiver(object):
    def __init__(self, signal):
        self.call_counter = 0
        self.call_args = None
        signal.connect(self, sender=APP_CONFIG)

    def __call__(self, signal, sender, **kwargs):
        self.call_counter = self.call_counter + 1
        self.call_args = kwargs


class OneTimeReceiver(object):
    """
    Special receiver for handle the fact that test runner calls migrate for
    several databases and several times for some of them.
    """

    def __init__(self, signal):
        self.signal = signal
        self.call_counter = 0
        self.call_args = None
        self.signal.connect(self, sender=APP_CONFIG)

    def __call__(self, signal, sender, **kwargs):
        # Although test runner calls migrate for several databases,
        # testing for only one of them is quite sufficient.
        if kwargs['using'] == MIGRATE_DATABASE:
            self.call_counter = self.call_counter + 1
            self.call_args = kwargs
            # we need to test only one call of migrate
            self.signal.disconnect(self, sender=APP_CONFIG)


# We connect receiver here and not in unit test code because we need to
# connect receiver before test runner creates database.  That is, sequence of
# actions would be:
#
#   1. Test runner imports this module.
#   2. We connect receiver.
#   3. Test runner calls migrate for create default database.
#   4. Test runner execute our unit test code.
pre_migrate_receiver = OneTimeReceiver(signals.pre_migrate)
post_migrate_receiver = OneTimeReceiver(signals.post_migrate)


class MigrateSignalTests(TestCase):

    available_apps = ['migrate_signals']

    def test_call_time(self):
        self.assertEqual(pre_migrate_receiver.call_counter, 1)
        self.assertEqual(post_migrate_receiver.call_counter, 1)

    def test_args(self):
        pre_migrate_receiver = Receiver(signals.pre_migrate)
        post_migrate_receiver = Receiver(signals.post_migrate)
        management.call_command(
            'migrate', database=MIGRATE_DATABASE, verbosity=MIGRATE_VERBOSITY,
            interactive=MIGRATE_INTERACTIVE, stdout=six.StringIO(),
        )

        for receiver in [pre_migrate_receiver, post_migrate_receiver]:
            args = receiver.call_args
            self.assertEqual(receiver.call_counter, 1)
            self.assertEqual(set(args), set(SIGNAL_ARGS))
            self.assertEqual(args['app_config'], APP_CONFIG)
            self.assertEqual(args['verbosity'], MIGRATE_VERBOSITY)
            self.assertEqual(args['interactive'], MIGRATE_INTERACTIVE)
            self.assertEqual(args['using'], 'default')

    @override_settings(MIGRATION_MODULES={'migrate_signals': 'migrate_signals.custom_migrations'})
    def test_migrations_only(self):
        """
        If all apps have migrations, migration signals should be sent.
        """
        pre_migrate_receiver = Receiver(signals.pre_migrate)
        post_migrate_receiver = Receiver(signals.post_migrate)
        stdout = six.StringIO()
        management.call_command(
            'migrate', database=MIGRATE_DATABASE, verbosity=MIGRATE_VERBOSITY,
            interactive=MIGRATE_INTERACTIVE, stdout=stdout,
        )
        for receiver in [pre_migrate_receiver, post_migrate_receiver]:
            args = receiver.call_args
            self.assertEqual(receiver.call_counter, 1)
            self.assertEqual(set(args), set(SIGNAL_ARGS))
            self.assertEqual(args['app_config'], APP_CONFIG)
            self.assertEqual(args['verbosity'], MIGRATE_VERBOSITY)
            self.assertEqual(args['interactive'], MIGRATE_INTERACTIVE)
            self.assertEqual(args['using'], 'default')
