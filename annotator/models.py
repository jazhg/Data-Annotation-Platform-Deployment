from django.contrib.auth.models import User
from django.db import models
from django.core.exceptions import ValidationError


class EmailAccount(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='email_account')
    email = models.EmailField(unique=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(email=models.functions.Lower('email')), name='email_account_lowercase')]


class AccessCode(models.Model):
    code = models.CharField(max_length=50, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        """Return a readable label for this record in researcher-facing administration."""
        return self.code


class CSVDataset(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='csv_files')
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='csv_datasets/')
    total_rows = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        """Return a readable label for this record in researcher-facing administration."""
        return f"{self.title} ({self.owner.username})"


class Annotation(models.Model):
    dataset = models.ForeignKey(
        CSVDataset, on_delete=models.CASCADE, related_name='annotations'
    )
    annotator = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='annotations'
    )
    row_number = models.PositiveIntegerField()
    image = models.TextField(blank=True)
    value = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['dataset', 'annotator', 'row_number'],
                name='unique_annotation_per_annotator_row',
            )
        ]
        ordering = ['dataset', 'annotator', 'row_number']

    def __str__(self):
        """Return a readable label for this record in researcher-facing administration."""
        return f"{self.annotator.username}: {self.dataset.title} row {self.row_number}"


class EvaluationRating(models.Model):
    annotator = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='evaluation_ratings'
    )
    category = models.CharField(max_length=20)
    step = models.CharField(max_length=20)
    example_id = models.PositiveIntegerField()
    eval_type = models.CharField(max_length=20)
    eval_target = models.CharField(max_length=30)
    dimension = models.CharField(max_length=60)
    score = models.CharField(max_length=10)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        """Validate score values against the dimension's original study rubric."""
        from annotator.rubrics import T2I_RUBRICS, I2I_RUBRICS, SEQUENCE_RUBRICS
        super().clean()
        rubric = {
            't2i': T2I_RUBRICS, 'i2i': I2I_RUBRICS, 'sequence': SEQUENCE_RUBRICS,
        }.get(self.eval_type, {}).get(self.dimension)
        if rubric is None:
            raise ValidationError('Unknown evaluation type or dimension.')
        choices = rubric.get('scale', rubric.get('choices', ()))
        if str(self.score) not in {str(value) for value in choices}:
            raise ValidationError({'score': 'Select a valid score for this dimension.'})

    class Meta:
        ordering = ['annotator', 'example_id', 'eval_type', 'eval_target', 'dimension']
        constraints = [
            models.UniqueConstraint(
                fields=['annotator', 'example_id', 'eval_type', 'eval_target', 'dimension'],
                name='unique_legacy_evaluation_rating',
            )
        ]

    def __str__(self):
        """Return a readable label for this record in researcher-facing administration."""
        return f"{self.annotator.username}: example {self.example_id} {self.dimension}"


class AnnotatorResultCSV(models.Model):
    annotator = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='result_csv'
    )
    content = models.TextField(blank=True)
    row_count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'annotator result CSV'
        verbose_name_plural = 'annotator result CSVs'

    def __str__(self):
        """Return a readable label for this record in researcher-facing administration."""
        return f"{self.annotator.username}_ratings.csv"
