import csv
import os
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from foodgram.models import Tag

DATA_ROOT = os.path.join(settings.BASE_DIR, 'data')


class Command(BaseCommand):
    """
    Command which allows you to upload .csv file with tags
    For localizations purposes TagsEN is hardcoded
    """
    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            'filename',
            default='tagsRU.csv',
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
                    Tag.objects.get_or_create(
                        name=row[0],
                        color=row[1],
                        slug=row[2]
                    )
        except FileNotFoundError:
            raise CommandError(f'Файл {options["filename"]} не найден в директории /data/')
