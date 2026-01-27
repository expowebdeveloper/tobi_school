from django.core.management.base import BaseCommand
from django.db.models import Count, Q

from schools.models import School


class Command(BaseCommand):
    help = (
        'Set second_scraper=False and third_scraper=False for schools '
        'that have no entries in the SchoolData model.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show which schools would be updated without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # Schools with no SchoolData entries
        schools_no_data = School.objects.annotate(
            num_data=Count('school_data')
        ).filter(num_data=0)

        # Only schools that currently have at least one flag True
        to_update = schools_no_data.filter(
            Q(second_scraper=True) | Q(third_scraper=True)
        )

        count = to_update.count()

        if count == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    'No schools need updating (all schools with no SchoolData '
                    'already have second_scraper=False and third_scraper=False).'
                )
            )
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'[DRY RUN] Would update {count} school(s) to '
                    'second_scraper=False, third_scraper=False:'
                )
            )
            for s in to_update.values_list('urn', 'establishment_name')[:20]:
                self.stdout.write(f'  URN {s[0]}: {s[1]}')
            if count > 20:
                self.stdout.write(f'  ... and {count - 20} more.')
            return

        updated = to_update.update(second_scraper=False, third_scraper=False)
        self.stdout.write(
            self.style.SUCCESS(
                f'Updated {updated} school(s): set second_scraper=False and '
                'third_scraper=False (schools with no SchoolData).'
            )
        )
