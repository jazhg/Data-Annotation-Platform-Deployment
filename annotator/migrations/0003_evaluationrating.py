import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('annotator', '0002_csvdataset_annotation'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='EvaluationRating',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('category', models.CharField(max_length=20)),
                ('step', models.CharField(max_length=20)),
                ('example_id', models.PositiveIntegerField()),
                ('eval_type', models.CharField(max_length=20)),
                ('eval_target', models.CharField(max_length=30)),
                ('dimension', models.CharField(max_length=60)),
                ('score', models.CharField(max_length=10)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('annotator', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='evaluation_ratings', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['annotator', 'example_id', 'eval_type', 'eval_target', 'dimension'],
            },
        ),
        migrations.AddConstraint(
            model_name='evaluationrating',
            constraint=models.UniqueConstraint(fields=('annotator', 'example_id', 'eval_type', 'eval_target', 'dimension'), name='unique_legacy_evaluation_rating'),
        ),
    ]
