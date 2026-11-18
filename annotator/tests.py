import io
import zipfile

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from annotator.models import (
    AccessCode, AnnotatorResultCSV, EvaluationRating,
)
from annotator.views import load_evaluation_data


class AnnotationWorkflowTests(TestCase):
    def test_admin_rejects_out_of_rubric_scores(self):
        """Reject invalid admin edits for both ordinal and binary dimensions."""
        from django.contrib import admin
        from django.test import RequestFactory
        request = RequestFactory().get('/admin/')
        request.user = self.owner
        for dimension, kind, invalid, valid in [
            ('object_entity', 't2i', '999', '6'),
            ('sequencing', 'sequence', '6', 'yes'),
        ]:
            rating = EvaluationRating(
                annotator=self.owner, category='C1', step='2step', example_id=0,
                eval_type=kind, eval_target='0', dimension=dimension,
            )
            form_class = admin.site._registry[EvaluationRating].get_form(request, rating)
            self.assertFalse(form_class(data={'score': invalid}, instance=rating).is_valid())
            self.assertTrue(form_class(data={'score': valid}, instance=rating).is_valid())

    def test_export_escapes_spreadsheet_formulas(self):
        """Ensure user-controlled names cannot become executable spreadsheet cells."""
        from annotator.csv_results import safe_csv_cell
        self.assertEqual(safe_csv_cell('@SUM(1)'), "'@SUM(1)")
        self.assertEqual(safe_csv_cell('6'), '6')

    def test_admin_bulk_delete_refreshes_csv(self):
        """Exercise PostgreSQL locking and CSV synchronization on bulk deletion."""
        from django.contrib import admin
        from annotator.csv_results import refresh_annotator_csv
        user = User.objects.create_user('delete-rater')
        rating = EvaluationRating.objects.create(
            annotator=user, category='C1', step='2step', example_id=0,
            eval_type='t2i', eval_target='0', dimension='object_entity', score='6',
        )
        refresh_annotator_csv(user)
        admin.site._registry[EvaluationRating].delete_queryset(
            None, EvaluationRating.objects.filter(pk=rating.pk)
        )
        self.assertEqual(AnnotatorResultCSV.objects.get(annotator=user).row_count, 0)

    def test_invalid_score_rejected_without_partial_save(self):
        """Reject an invalid score before persisting any part of the submission."""
        user = User.objects.create_user('invalid-rater')
        self.client.force_login(user)
        response = self.client.post(reverse('evaluation', args=[0]), {
            'rating__t2i__0__object_entity': '6',
            'rating__sequence__sequence__sequencing': 'invalid',
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(EvaluationRating.objects.exists())

    def test_study_structure_and_assets(self):
        """Verify all examples, required ratings, and image assets are intact."""
        from annotator.rubrics import expected_rating_keys
        from annotator.views import EVALUATION_IMAGES_PATH, image_relative_path
        data = load_evaluation_data()
        self.assertEqual(sum(len(expected_rating_keys(e)) for e in data), 1260)
        for example in data:
            for image in example['images']:
                self.assertTrue((EVALUATION_IMAGES_PATH / image_relative_path(image['path'])).is_file())

    def test_zip_contains_every_csv_and_requires_permission(self):
        """Check ZIP contents, unique safe filenames, and staff authorization."""
        for name in ('alice', 'bob'):
            user = User.objects.create_user(name)
            AnnotatorResultCSV.objects.create(annotator=user, content=f'{name},6\r\n')
        url = reverse('admin:annotator_annotatorresultcsv_download_all')
        self.assertEqual(self.client.get(url).status_code, 302)
        staff = User.objects.create_user('limited', is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.owner)
        response = self.client.get(url)
        with zipfile.ZipFile(io.BytesIO(b''.join(response.streaming_content))) as archive:
            self.assertEqual(len(archive.namelist()), 2)
            self.assertEqual({archive.read(n) for n in archive.namelist()},
                             {b'alice,6\r\n', b'bob,6\r\n'})

    def test_shared_code_cannot_log_in_inactive_or_staff_users(self):
        """Ensure the shared access code cannot bypass privileged account controls."""
        for name, flags in [('inactive', {'is_active': False}), ('staff', {'is_staff': True})]:
            user = User.objects.create_user(name, **flags)
            user.set_unusable_password()
            user.save()
            response = self.client.post(reverse('login'), {
                'username': name, 'access_code': self.code.code,
            })
            self.assertEqual(response.status_code, 200)
            self.assertNotIn('_auth_user_id', self.client.session)

    def test_csv_failure_rolls_back_ratings(self):
        """Fail a CSV update and confirm PostgreSQL rolls back the entire submission."""
        from unittest.mock import patch
        user = User.objects.create_user('rollback')
        self.client.force_login(user)
        with patch('annotator.views.refresh_annotator_csv', side_effect=RuntimeError('failed')):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse('evaluation', args=[0]), {
                    'rating__t2i__0__object_entity': '6',
                })
        self.assertFalse(EvaluationRating.objects.filter(annotator=user).exists())

    def setUp(self):
        """Create isolated researcher and access-code fixtures for workflow tests."""
        self.code = AccessCode.objects.create(code='study-code')
        self.owner = User.objects.create_superuser('researcher', password='secret')
    def test_registration_requires_valid_access_code(self):
        """Verify only registration uses the shared code."""
        response = self.client.post(reverse('register'), {
            'email': 'participant@example.com', 'password': 'Study-Strong-Password-719!',
            'password_confirm': 'Study-Strong-Password-719!', 'access_code': 'wrong'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='annotator-1').exists())

        response = self.client.post(reverse('register'), {
            'email': 'participant@example.com', 'password': 'Study-Strong-Password-719!',
            'password_confirm': 'Study-Strong-Password-719!', 'access_code': self.code.code
        })
        self.assertRedirects(response, reverse('dashboard'))

    def test_staff_users_go_to_django_admin(self):
        """Verify staff users go to django admin."""
        self.client.force_login(self.owner)
        response = self.client.get(reverse('dashboard'))
        self.assertRedirects(response, '/admin/', fetch_redirect_response=False)

    def test_legacy_dataset_and_rating_structure(self):
        """Verify legacy dataset and rating structure."""
        data = load_evaluation_data()
        self.assertEqual(len(data), 60)
        self.assertEqual({item['category'] for item in data}, {'C1', 'C2', 'C3', 'C4'})

        annotator = User.objects.create_user('legacy-rater')
        self.client.force_login(annotator)
        response = self.client.get(reverse('evaluation', args=[0]))
        self.assertContains(response, 'Text-to-Image')
        self.assertContains(response, 'Image-to-Image')
        self.assertContains(response, 'Sequence Evaluation')

        response = self.client.post(reverse('evaluation', args=[0]), {
            'rating__t2i__0__object_entity': '6',
            'rating__sequence__sequence__sequencing': 'yes',
            'navigate': 'stay',
        })
        self.assertRedirects(response, reverse('evaluation', args=[0]))
        self.assertEqual(EvaluationRating.objects.count(), 2)
        self.assertTrue(EvaluationRating.objects.filter(
            eval_type='sequence', dimension='sequencing', score='yes'
        ).exists())
        stored_csv = AnnotatorResultCSV.objects.get(annotator=annotator)
        self.assertEqual(stored_csv.row_count, 2)
        self.assertIn('annotator_id,category,step,example_id', stored_csv.content)
        self.assertIn('legacy-rater,C1,2step,0,sequence,sequence,sequencing,yes', stored_csv.content)

    def test_admin_can_download_postgresql_backed_user_csv(self):
        """Verify admin can download postgresql backed user csv."""
        annotator = User.objects.create_user('csv-rater')
        result = AnnotatorResultCSV.objects.create(
            annotator=annotator,
            content='annotator_id,score\r\ncsv-rater,6\r\n',
            row_count=1,
        )
        self.client.force_login(self.owner)
        response = self.client.get(reverse(
            'admin:annotator_annotatorresultcsv_download', args=[result.pk]
        ))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn('csv-rater_ratings.csv', response['Content-Disposition'])


class EmailAuthenticationTests(TestCase):
    password = 'Study-Strong-Password-719!'

    def setUp(self):
        self.code = AccessCode.objects.create(code='invite')
        self.payload = {'email': 'Rater@Example.com', 'password': self.password,
                        'password_confirm': self.password, 'access_code': 'invite'}

    def register(self):
        response = self.client.post(reverse('register'), self.payload)
        self.assertRedirects(response, reverse('dashboard'))
        return User.objects.get(email='rater@example.com')

    def test_password_required_and_case_insensitive_email(self):
        user = self.register()
        self.assertTrue(user.check_password(self.password))
        self.assertNotEqual(user.password, self.password)
        self.client.logout()
        self.code.is_active = False
        self.code.save()
        for data in ({'email': user.email, 'password': 'wrong'},
                     {'username': user.username, 'access_code': 'invite'},
                     {'email': 'unknown@example.com', 'password': self.password}):
            self.assertEqual(self.client.post(reverse('login'), data).status_code, 200)
            self.assertNotIn('_auth_user_id', self.client.session)
        response = self.client.post(reverse('login'), {'email': 'RATER@EXAMPLE.COM', 'password': self.password})
        self.assertRedirects(response, reverse('dashboard'))
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

    def test_duplicate_email_cannot_claim_or_replace_account(self):
        user = self.register()
        self.client.logout()
        self.payload['email'] = 'RATER@example.com'
        response = self.client.post(reverse('register'), self.payload)
        self.assertContains(response, 'An account with this email already exists.')
        self.assertEqual(User.objects.count(), 1)
        self.assertNotIn('_auth_user_id', self.client.session)
        user.refresh_from_db()
        self.assertTrue(user.check_password(self.password))

    def test_reject_invalid_registration(self):
        for field, value in [('access_code', ''), ('access_code', 'wrong'),
                             ('email', 'invalid'), ('password_confirm', 'different'),
                             ('password', '123')]:
            with self.subTest(field=field, value=value):
                response = self.client.post(reverse('register'), {**self.payload, field: value})
                self.assertEqual(response.status_code, 200)
                self.assertFalse(User.objects.exists())
        self.code.is_active = False
        self.code.save()
        self.client.post(reverse('register'), self.payload)
        self.assertFalse(User.objects.exists())

    def test_inactive_account_cannot_login(self):
        user = self.register()
        self.client.logout()
        user.is_active = False
        user.save()
        self.client.post(reverse('login'), {'email': user.email, 'password': self.password})
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_legacy_username_cannot_be_claimed(self):
        old = User.objects.create_user('rater@example.com')
        new = self.register()
        self.assertNotEqual(old.pk, new.pk)
        old.refresh_from_db()
        self.assertFalse(old.has_usable_password())

    def test_registration_and_login_links(self):
        self.assertContains(self.client.get(reverse('login')), reverse('register'))
        self.assertContains(self.client.get(reverse('register')), 'Confirm password')


class PasswordRecoveryTests(TestCase):
    def setUp(self):
        from annotator.models import EmailAccount
        self.user = User.objects.create_user('recovery-user', email='recovery@example.com', password='Old-Password-719!')
        EmailAccount.objects.create(user=self.user, email=self.user.email)

    def test_reset_link_changes_password_and_cannot_be_reused(self):
        import re
        from django.core import mail
        from django.test import override_settings
        with override_settings(MAILERS={'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'}}):
            response = self.client.post(reverse('password_reset'), {'email': 'RECOVERY@example.com'})
            self.assertRedirects(response, reverse('password_reset_done'))
            self.assertEqual(len(mail.outbox), 1)
            self.assertEqual(mail.outbox[0].to, [self.user.email])
            link = re.search(r'http://testserver(/reset/\S+)', mail.outbox[0].body).group(1)
            response = self.client.get(link)
            confirm_url = response.url
            self.assertContains(self.client.get(confirm_url), 'Choose a new password')
            response = self.client.post(confirm_url, {'new_password1': 'New-Password-829!', 'new_password2': 'New-Password-829!'})
            self.assertRedirects(response, reverse('password_reset_complete'))
            self.user.refresh_from_db()
            self.assertTrue(self.user.check_password('New-Password-829!'))
            self.assertFalse(self.user.check_password('Old-Password-719!'))
            self.assertContains(self.client.get(link), 'Invalid or expired link')
            self.assertRedirects(self.client.post(reverse('login'), {'email': self.user.email, 'password': 'New-Password-829!'}), reverse('dashboard'))

    def test_unknown_inactive_and_legacy_accounts_do_not_receive_email(self):
        from django.core import mail
        from django.test import override_settings
        User.objects.create_user('legacy-recovery', email='legacy@example.com', password='Old-Password-719!')
        self.user.is_active = False
        self.user.save()
        with override_settings(MAILERS={'default': {'BACKEND': 'django.core.mail.backends.locmem.EmailBackend'}}):
            for email in ['missing@example.com', 'legacy@example.com', self.user.email]:
                response = self.client.post(reverse('password_reset'), {'email': email})
                self.assertRedirects(response, reverse('password_reset_done'))
            self.assertEqual(len(mail.outbox), 0)

    def test_expired_link_is_rejected(self):
        from datetime import datetime, timedelta
        from unittest.mock import patch
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode
        with patch.object(default_token_generator, '_now', return_value=datetime.now() - timedelta(hours=2)):
            token = default_token_generator.make_token(self.user)
        url = reverse('password_reset_confirm', args=[urlsafe_base64_encode(force_bytes(self.user.pk)), token])
        self.assertContains(self.client.get(url), 'Invalid or expired link')


class CSVDeletionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_superuser('csv-admin', password='Admin-Password-719!')
        self.annotator = User.objects.create_user('csv-delete')
        self.rating = EvaluationRating.objects.create(
            annotator=self.annotator, category='C1', step='2step', example_id=0,
            eval_type='t2i', eval_target='0', dimension='object_entity', score='6')
        self.csv = AnnotatorResultCSV.objects.create(annotator=self.annotator, content='example,6', row_count=1)

    def test_admin_can_delete_csv_without_deleting_ratings(self):
        self.client.force_login(self.owner)
        url = reverse('admin:annotator_annotatorresultcsv_delete', args=[self.csv.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(url, {'post': 'yes'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(AnnotatorResultCSV.objects.exists())
        self.assertTrue(EvaluationRating.objects.filter(pk=self.rating.pk).exists())

    def test_bulk_delete_and_permissions(self):
        from django.contrib.auth.models import Permission
        limited = User.objects.create_user('csv-viewer', is_staff=True)
        limited.user_permissions.add(Permission.objects.get(codename='view_annotatorresultcsv'))
        self.client.force_login(limited)
        delete_url = reverse('admin:annotator_annotatorresultcsv_delete', args=[self.csv.pk])
        self.assertEqual(self.client.post(delete_url, {'post': 'yes'}).status_code, 403)
        self.assertTrue(AnnotatorResultCSV.objects.exists())
        self.client.force_login(self.owner)
        response = self.client.post(reverse('admin:annotator_annotatorresultcsv_changelist'), {
            'action': 'delete_selected', '_selected_action': [str(self.csv.pk)], 'post': 'yes'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(AnnotatorResultCSV.objects.exists())


class RegistrationRaceTests(TestCase):
    def test_database_rejects_duplicate_even_after_both_forms_validate(self):
        from django.db import IntegrityError
        from annotator.forms import RegistrationForm
        from annotator.models import EmailAccount
        AccessCode.objects.create(code='race-code')
        payload = {'email': 'race@example.com', 'password': 'Strong-Race-Password-719!',
                   'password_confirm': 'Strong-Race-Password-719!', 'access_code': 'race-code'}
        first, second = RegistrationForm(payload), RegistrationForm(payload)
        self.assertTrue(first.is_valid())
        self.assertTrue(second.is_valid())
        first.save()
        with self.assertRaises(IntegrityError):
            second.save()
        self.assertEqual(EmailAccount.objects.count(), 1)
        self.assertEqual(User.objects.count(), 1)
