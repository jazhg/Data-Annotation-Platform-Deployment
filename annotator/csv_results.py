import csv
import io

from annotator.models import AnnotatorResultCSV, EvaluationRating


CSV_FIELDS = (
    'annotator_id', 'category', 'step', 'example_id',
    'eval_type', 'eval_target', 'dimension', 'score',
)


def safe_csv_cell(value):
    """Escape formula-leading text so spreadsheet applications cannot execute it."""
    text = str(value)
    return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) else text


def refresh_annotator_csv(annotator):
    """Rebuild and store one annotator's CSV inside the configured database."""
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDS)
    writer.writeheader()
    ratings = EvaluationRating.objects.filter(annotator=annotator).order_by(
        'example_id', 'eval_type', 'eval_target', 'dimension'
    )
    row_count = 0
    for rating in ratings:
        writer.writerow({
            'annotator_id': safe_csv_cell(annotator.username),
            'category': rating.category,
            'step': rating.step,
            'example_id': rating.example_id,
            'eval_type': rating.eval_type,
            'eval_target': rating.eval_target,
            'dimension': rating.dimension,
            'score': safe_csv_cell(rating.score),
        })
        row_count += 1
    result, _ = AnnotatorResultCSV.objects.update_or_create(
        annotator=annotator,
        defaults={'content': output.getvalue(), 'row_count': row_count},
    )
    return result
