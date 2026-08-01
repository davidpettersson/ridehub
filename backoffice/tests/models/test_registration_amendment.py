from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from backoffice.models import Event, Program, Registration, RegistrationAmendment


class RegistrationAmendmentTests(TestCase):
    def setUp(self):
        # Arrange
        self.program = Program.objects.create(name="Test Program")
        self.event = Event.objects.create(
            name="Test Event",
            program=self.program,
            starts_at=timezone.now() + timezone.timedelta(days=7),
        )
        self.user = User.objects.create_user(
            username='rider@example.com',
            email='rider@example.com',
            password='password123',
        )
        self.registration = Registration.objects.create(
            event=self.event,
            user=self.user,
            name='Rider Person',
            first_name='Rider',
            last_name='Person',
            email=self.user.email,
            phone='+16135550100',
        )

    def _create_amendment(self, **overrides) -> RegistrationAmendment:
        values = {
            'registration': self.registration,
            'actor': self.user,
            'changed_fields': ['ride'],
            'first_name': 'Rider',
            'last_name': 'Person',
            'email': self.user.email,
            'phone': '+16135550100',
        }
        values.update(overrides)
        return RegistrationAmendment(**values)

    def test_valid_amendment_passes_validation(self):
        # Arrange
        amendment = self._create_amendment()

        # Act
        amendment.full_clean()

        # Assert
        self.assertEqual(['ride'], amendment.changed_fields)

    def test_empty_changed_fields_is_rejected(self):
        # Arrange
        amendment = self._create_amendment(changed_fields=[])

        # Act & Assert
        with self.assertRaises(ValidationError) as context:
            amendment.full_clean()
        self.assertIn('changed_fields', context.exception.message_dict)

    def test_unknown_changed_field_is_rejected(self):
        # Arrange
        amendment = self._create_amendment(changed_fields=['state'])

        # Act & Assert
        with self.assertRaises(ValidationError) as context:
            amendment.full_clean()
        self.assertIn('changed_fields', context.exception.message_dict)

    def test_non_list_changed_fields_is_rejected(self):
        # Arrange
        amendment = self._create_amendment(changed_fields={'ride': 'x'})

        # Act & Assert
        with self.assertRaises(ValidationError) as context:
            amendment.full_clean()
        self.assertIn('changed_fields', context.exception.message_dict)

    def test_amendments_are_deleted_with_the_registration(self):
        # Arrange
        self._create_amendment().save()

        # Act
        self.registration.delete()

        # Assert
        self.assertEqual(0, RegistrationAmendment.objects.count())

    def test_amendments_are_ordered_most_recent_first(self):
        # Arrange
        older = self._create_amendment(changed_fields=['ride'])
        older.save()
        newer = self._create_amendment(changed_fields=['emergency_contact_name'])
        newer.save()

        # Act
        amendments = list(RegistrationAmendment.objects.all())

        # Assert
        self.assertEqual([newer.id, older.id], [amendment.id for amendment in amendments])
