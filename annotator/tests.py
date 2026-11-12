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
    def test_login_requires_valid_access_code(self):
        """Verify login requires valid access code."""
        response = self.client.post(reverse('login'), {
            'username': 'annotator-1', 'access_code': 'wrong'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='annotator-1').exists())

        response = self.client.post(reverse('login'), {
            'username': 'annotator-1', 'access_code': self.code.code
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
