import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import FileResponse, Http404, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.db import transaction
from annotator.forms import AnnotatorEntryForm
from annotator.models import EvaluationRating
from annotator.csv_results import refresh_annotator_csv
from annotator.rubrics import expected_rating_keys, rubric_sections


EVALUATION_DATA_PATH = settings.BASE_DIR / 'annotator' / 'data' / 'evaluation_results.json'
EVALUATION_IMAGES_PATH = settings.BASE_DIR / 'Images'


def load_evaluation_data():
    """Load the bundled study metadata without importing historical human ratings."""
    with EVALUATION_DATA_PATH.open(encoding='utf-8') as data_file:
        return json.load(data_file)


def image_relative_path(raw_path):
    """Translate legacy absolute image paths into study-relative asset paths."""
    normalized = raw_path.replace('\\', '/')
    marker = 'Images_pilot/'
    return normalized.split(marker, 1)[1] if marker in normalized else Path(normalized).name


def entry_view(request):
    """Authenticate annotators using a username and active shared access code."""
    if request.user.is_authenticated:
        return redirect('/admin/' if request.user.is_staff else 'dashboard')

    if request.method == 'POST':
        form = AnnotatorEntryForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            user, created = User.objects.get_or_create(username=username)

            if created:
                user.set_unusable_password()
                user.save()
            elif user.has_usable_password() or user.is_staff or user.is_superuser or not user.is_active:
                form.add_error('username', "This username belongs to an admin account. Use Admin Login.")
                return render(request, 'login.html', {'form': form})

            login(request, user)
            return redirect('dashboard')
    else:
        form = AnnotatorEntryForm()

    return render(request, 'login.html', {'form': form})


@login_required
def dashboard_view(request):
    """Show completion counts and resume at the first unfinished example."""
    if request.user.is_staff:
        return redirect('/admin/')

    data = load_evaluation_data()
    ratings = EvaluationRating.objects.filter(annotator=request.user)
    completed = 0
    first_incomplete = 0
    for index, example in enumerate(data):
        saved = set(ratings.filter(example_id=example['example_id']).values_list(
            'eval_type', 'eval_target', 'dimension'
        ))
        if set(expected_rating_keys(example)).issubset(saved):
            completed += 1
        elif completed == index:
            first_incomplete = index
    return render(request, 'dashboard.html', {
        'completed': completed,
        'total': len(data),
        'start_index': first_incomplete,
    })


@login_required
def evaluation_view(request, index):
    """Display an example and atomically save its ratings and CSV snapshot."""
    if request.user.is_staff:
        return redirect('/admin/')
    data = load_evaluation_data()
    if index < 0 or index >= len(data):
        raise Http404('Evaluation example not found.')
    example = data[index]

    existing = {
        (rating.eval_type, rating.eval_target, rating.dimension): rating.score
        for rating in EvaluationRating.objects.filter(
            annotator=request.user, example_id=example['example_id']
        )
    }
    sections = rubric_sections(example)
    if request.method == 'POST':
        # Reject malformed scores rather than silently reporting a successful save.
        for section in sections:
            for dimension, rubric in section['rubrics'].items():
                field = f"rating__{section['eval_type']}__{section['eval_target']}__{dimension}"
                score = request.POST.get(field)
                allowed = {str(v) for v in rubric.get('scale', rubric.get('choices', ()))}
                if score is not None and score not in allowed:
                    return HttpResponseBadRequest('Invalid rating. No changes were saved.')
        # Serialize saves for each annotator and commit the CSV with its ratings.
        with transaction.atomic():
            User.objects.select_for_update().get(pk=request.user.pk)
            for section in sections:
                for dimension, rubric in section['rubrics'].items():
                    field_name = f"rating__{section['eval_type']}__{section['eval_target']}__{dimension}"
                    score = request.POST.get(field_name)
                    valid_scores = {str(value) for value in rubric.get('scale', rubric.get('choices', ())) }
                    if score in valid_scores:
                        EvaluationRating.objects.update_or_create(
                            annotator=request.user,
                            example_id=example['example_id'],
                            eval_type=section['eval_type'],
                            eval_target=section['eval_target'],
                            dimension=dimension,
                            defaults={
                                'category': example['category'], 'step': example['step'], 'score': score,
                            },
                        )
            refresh_annotator_csv(request.user)
        destination = request.POST.get('navigate', 'stay')
        if destination == 'next' and index + 1 < len(data):
            return redirect('evaluation', index=index + 1)
        if destination == 'previous' and index > 0:
            return redirect('evaluation', index=index - 1)
        return redirect('evaluation', index=index)

    completed_examples = 0
    all_ratings = EvaluationRating.objects.filter(annotator=request.user)
    for candidate in data:
        saved = set(all_ratings.filter(example_id=candidate['example_id']).values_list(
            'eval_type', 'eval_target', 'dimension'
        ))
        if set(expected_rating_keys(candidate)).issubset(saved):
            completed_examples += 1

    for section in sections:
        for image in section['images']:
            image['web_path'] = image_relative_path(image['path'])
        section['rating_rows'] = []
        for dimension, rubric in section.pop('rubrics').items():
            choices = rubric.get('scale') or {choice: choice.title() for choice in rubric['choices']}
            section['rating_rows'].append({
                'dimension': dimension,
                'name': rubric['name'],
                'description': rubric['description'],
                'choices': choices.items(),
                'current': existing.get((section['eval_type'], section['eval_target'], dimension), ''),
                'field_name': f"rating__{section['eval_type']}__{section['eval_target']}__{dimension}",
            })
    return render(request, 'evaluation.html', {
        'example': example, 'sections': sections, 'index': index,
        'position': index + 1, 'total': len(data), 'completed': completed_examples,
        'has_previous': index > 0, 'has_next': index + 1 < len(data),
    })


@login_required
def study_image_view(request, image_path):
    """Serve authenticated study images while rejecting paths outside the image root."""
    candidate = (EVALUATION_IMAGES_PATH / image_path).resolve()
    image_root = EVALUATION_IMAGES_PATH.resolve()
    if image_root not in candidate.parents or not candidate.is_file():
        raise Http404('Study image is not available.')
    return FileResponse(candidate.open('rb'))
