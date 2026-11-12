# Generated for the data annotation workflow.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('annotator', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CSVDataset',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('file', models.FileField(upload_to='csv_datasets/')),
                ('total_rows', models.PositiveIntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='csv_files', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Annotation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('row_number', models.PositiveIntegerField()),
                ('image', models.TextField(blank=True)),
                ('value', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('annotator', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='annotations', to=settings.AUTH_USER_MODEL)),
                ('dataset', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='annotations', to='annotator.csvdataset')),
            ],
            options={
                'ordering': ['dataset', 'annotator', 'row_number'],
            },
        ),
        migrations.AddConstraint(
            model_name='annotation',
            constraint=models.UniqueConstraint(fields=('dataset', 'annotator', 'row_number'), name='unique_annotation_per_annotator_row'),
        ),
    ]
