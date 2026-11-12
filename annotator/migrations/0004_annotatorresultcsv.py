import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('annotator', '0003_evaluationrating'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AnnotatorResultCSV',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField(blank=True)),
                ('row_count', models.PositiveIntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('annotator', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='result_csv', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'annotator result CSV',
                'verbose_name_plural': 'annotator result CSVs',
            },
        ),
    ]
