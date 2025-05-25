import csv
import os
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from foodgram.models import Ingredient

DATA_ROOT = os.path.join(settings.BASE_DIR, 'data')


class Command(BaseCommand):
    """
    Command which allows you to upload .csv file with ingredients
    For localizations purposes IngredientsEN is hardcoded
    """

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            'filename',
            default='ingredientsRU.csv',
            nargs='?',
            type=str
        )

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            with open(
                os.path.join(DATA_ROOT, options['filename']),
                'r',
                encoding='utf-8'
            ) as f:
                data = csv.reader(f)
                for row in data:
                    if len(row) >= 2:
                        name = row[0].strip()
                        measurement_unit = row[1].strip()
                        if name and measurement_unit:
                            Ingredient.objects.get_or_create(
                                name=name,
                                measurement_unit=measurement_unit
                            )
        except FileNotFoundError:
            raise CommandError(f'Файл {options["filename"]} не найден в директории /data/')
