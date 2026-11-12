import csv
import io
import zipfile

from django.contrib import admin
from django.contrib.auth.models import User
from django.db import transaction
from django.http import HttpResponse, FileResponse
from django.core.exceptions import PermissionDenied
from django.utils.text import slugify
from annotator.csv_results import refresh_annotator_csv, safe_csv_cell
from django.urls import path, reverse
from django.utils.html import format_html

from annotator.models import (
    AccessCode, AnnotatorResultCSV, EvaluationRating,
)


@admin.register(AccessCode)
class AccessCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'is_active', 'created_at')
    list_editable = ('is_active',)
    search_fields = ('code',)


@admin.action(description='Download selected ratings as CSV')
def download_evaluation_ratings(modeladmin, request, queryset):
    """Export the selected rating records in the study CSV format."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="evaluation_ratings.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'annotator_id', 'category', 'step', 'example_id',
        'eval_type', 'eval_target', 'dimension', 'score',
    ])
    for rating in queryset.select_related('annotator'):
        writer.writerow([
            safe_csv_cell(rating.annotator.username), rating.category, rating.step,
            rating.example_id, rating.eval_type, rating.eval_target,
            rating.dimension, safe_csv_cell(rating.score),
        ])
    return response


@admin.register(EvaluationRating)
class EvaluationRatingAdmin(admin.ModelAdmin):
    list_display = (
        'annotator', 'category', 'step', 'example_id', 'eval_type',
        'eval_target', 'dimension', 'score', 'updated_at',
    )
    list_filter = ('annotator', 'category', 'step', 'eval_type', 'dimension')
    search_fields = ('annotator__username', 'dimension', 'score')
    actions = (download_evaluation_ratings,)
    readonly_fields = ('annotator', 'category', 'step', 'example_id', 'eval_type', 'eval_target', 'dimension')

    def has_add_permission(self, request):
        """Require ratings to originate from the validated evaluation workflow."""
        return False

    def save_model(self, request, obj, form, change):
        """Keep the saved CSV synchronized after a researcher edits a score."""
        User.objects.select_for_update().get(pk=obj.annotator_id)
        super().save_model(request, obj, form, change)
        refresh_annotator_csv(obj.annotator)

    def delete_model(self, request, obj):
        """Refresh the owner's CSV after deleting an individual rating."""
        owner = User.objects.select_for_update().get(pk=obj.annotator_id)
        super().delete_model(request, obj)
        refresh_annotator_csv(owner)

    @transaction.atomic
    def delete_queryset(self, request, queryset):
        """Refresh all affected CSVs after a bulk rating deletion."""
        owner_ids = list(queryset.values_list('annotator_id', flat=True).distinct())
        owners = list(User.objects.select_for_update().filter(pk__in=owner_ids).order_by('pk'))
        super().delete_queryset(request, queryset)
        for owner in owners:
            refresh_annotator_csv(owner)


@admin.register(AnnotatorResultCSV)
class AnnotatorResultCSVAdmin(admin.ModelAdmin):
    change_list_template = 'admin/annotator_results.html'
    list_display = ('annotator', 'row_count', 'updated_at', 'download_link')
    readonly_fields = ('annotator', 'row_count', 'updated_at', 'download_link')
    fields = ('annotator', 'row_count', 'updated_at', 'download_link')
    search_fields = ('annotator__username',)

    def has_delete_permission(self, request, obj=None):
        """Keep generated exports available; manage source ratings instead."""
        return False

    def has_add_permission(self, request):
        """Disallow manual creation of generated CSV snapshots."""
        return False

    def get_urls(self):
        """Register permission-protected individual and bulk download endpoints."""
        return [
            path('download-all/', self.admin_site.admin_view(self.download_all),
                 name='annotator_annotatorresultcsv_download_all'),
            path(
                '<int:object_id>/download/',
                self.admin_site.admin_view(self.download_csv),
                name='annotator_annotatorresultcsv_download',
            ),
        ] + super().get_urls()

    @admin.display(description='CSV file')
    def download_link(self, obj):
        """Render the admin download link with escaped username text."""
        if not obj or not obj.pk:
            return 'Not generated yet'
        url = reverse('admin:annotator_annotatorresultcsv_download', args=[obj.pk])
        return format_html('<a href="{}">Download {}_ratings.csv</a>', url, obj.annotator.username)

    def download_csv(self, request, object_id):
        """Return a stored CSV only to staff with the required model permission."""
        result = self.get_object(request, object_id)
        if result is None:
            from django.http import Http404
            raise Http404
        if not self.has_view_permission(request, result):
            raise PermissionDenied
        response = HttpResponse(result.content, content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = (
            f'attachment; filename="{slugify(result.annotator.username) or "annotator"}_ratings.csv"'
        )
        return response

    def download_all(self, request):
        """Download all saved CSV snapshots in one permission-protected ZIP."""
        if not self.has_view_permission(request):
            raise PermissionDenied
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
            for result in self.get_queryset(request).select_related('annotator'):
                name = slugify(result.annotator.username) or 'annotator'
                archive.writestr(
                    f'{result.annotator_id}_{name}_ratings.csv', result.content
                )
        output.seek(0)
        return FileResponse(output, as_attachment=True, filename='all_annotator_results.zip')
