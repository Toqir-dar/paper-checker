import csv
import io

from app.models.batch import BatchDetail


def build_batch_csv(detail: BatchDetail) -> str:
    """One row per student: roll number, score, and every wrong answer with why.

    A submission with no grade result yet (paper uploaded but not graded) still
    gets a row instead of silently vanishing from the export, so a teacher can
    see which papers still need attention.

    Prefixed with a UTF-8 BOM so Excel — which otherwise guesses the system
    codepage — renders non-ASCII roll numbers/names correctly instead of
    mangling them.
    """
    buffer = io.StringIO()
    buffer.write("﻿")
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "roll_number",
            "student_name",
            "points_awarded",
            "points_possible",
            "percentage",
            "wrong_answers",
            "warnings",
        ]
    )

    for row in detail.rows:
        submission = row.submission
        result = row.result

        if result is None:
            writer.writerow([submission.roll_number, submission.student_name, "", "", "", "NOT GRADED YET", ""])
            continue

        percentage = (
            round(result.total_points_awarded / result.total_points_possible * 100, 1)
            if result.total_points_possible
            else 0
        )
        wrong_answers = "; ".join(
            f"{grade.question_id}: {grade.feedback or 'incorrect'}"
            for grade in result.question_grades
            if grade.points_awarded < grade.points_possible
        )

        writer.writerow(
            [
                submission.roll_number,
                submission.student_name,
                result.total_points_awarded,
                result.total_points_possible,
                percentage,
                wrong_answers or "None — full marks",
                " | ".join(result.warnings),
            ]
        )

    return buffer.getvalue()
