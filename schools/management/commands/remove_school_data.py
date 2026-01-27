import json
from django.core.management.base import BaseCommand
from schools.models import SchoolData


class Command(BaseCommand):
    help = 'Remove SchoolData entries from the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Delete all SchoolData entries'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting (default: True)'
        )
        parser.add_argument(
            '--delete',
            action='store_true',
            help='Actually delete the entries (use with caution!)'
        )
        parser.add_argument(
            '--school-id',
            type=int,
            help='Delete SchoolData entries for a specific school URN'
        )
        parser.add_argument(
            '--filter-unwanted-text',
            action='store_true',
            help='Delete SchoolData entries containing unwanted event description text'
        )

    def search_in_data(self, data, search_strings):
        """
        Recursively search for strings in JSON data structure.
        Returns True if any of the search strings is found.
        """
        if data is None:
            return False

        # Convert data to string for searching
        try:
            data_str = json.dumps(data, ensure_ascii=False).lower()
            search_strings_lower = [s.lower() for s in search_strings]

            # Check if any search string is in the data
            for search_str in search_strings_lower:
                if search_str in data_str:
                    return True
            return False
        except (TypeError, ValueError, json.JSONDecodeError):
            return False

    def handle(self, *args, **options):
        delete_all = options['all']
        dry_run = options['dry_run']
        delete = options['delete']
        school_id = options['school_id']
        filter_unwanted_text = options['filter_unwanted_text']

        # Default to dry-run if --delete is not specified
        if not delete:
            dry_run = True

        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('REMOVE SchoolData ENTRIES'))
        self.stdout.write(self.style.SUCCESS('=' * 80))

        # Unwanted text patterns to search for
        unwanted_texts = [
            "FULL original event description exactly as written",
            "Original official event description"
        ]

        # Determine what to delete
        if filter_unwanted_text:
            # Filter entries containing unwanted text
            self.stdout.write(
                'Target: SchoolData entries containing unwanted event description text')
            self.stdout.write('Searching for:')
            for text in unwanted_texts:
                self.stdout.write(f'  - "{text}"')

            # Get all SchoolData entries and filter by text
            all_entries = SchoolData.objects.select_related('school').all()
            matching_ids = []

            self.stdout.write('\nScanning SchoolData entries...')
            for entry in all_entries:
                if self.search_in_data(entry.data, unwanted_texts):
                    matching_ids.append(entry.id)

            queryset = SchoolData.objects.filter(id__in=matching_ids)
            self.stdout.write(
                f'Found {len(matching_ids)} entries with unwanted text')

        elif school_id:
            queryset = SchoolData.objects.filter(school__urn=school_id)
            self.stdout.write(
                f'Target: SchoolData entries for school URN: {school_id}')
        elif delete_all:
            queryset = SchoolData.objects.all()
            self.stdout.write('Target: ALL SchoolData entries')
        else:
            self.stdout.write(self.style.ERROR(
                'Error: You must specify --all, --school-id <urn>, or --filter-unwanted-text'
            ))
            self.stdout.write('\nUsage examples:')
            self.stdout.write(
                '  python manage.py remove_school_data --all --delete')
            self.stdout.write(
                '  python manage.py remove_school_data --school-id 100000 --delete')
            self.stdout.write(
                '  python manage.py remove_school_data --filter-unwanted-text --delete')
            return

        count = queryset.count()
        self.stdout.write(f'Total entries to delete: {count}')
        self.stdout.write(
            f'Mode: {"DRY RUN (preview only)" if dry_run else "DELETE MODE"}')
        self.stdout.write('=' * 80)

        if count == 0:
            self.stdout.write(
                self.style.WARNING(
                    '\n[INFO] No SchoolData entries found to delete.')
            )
            return

        # Show some examples
        if count > 0 and count <= 10:
            self.stdout.write('\nEntries to be deleted:')
            for entry in queryset[:10]:
                self.stdout.write(
                    f'  - ID: {entry.id}, School: {entry.school.establishment_name} '
                    f'(URN: {entry.school.urn}), Created: {entry.created_at}'
                )
        elif count > 10:
            self.stdout.write('\nFirst 10 entries to be deleted:')
            for entry in queryset[:10]:
                self.stdout.write(
                    f'  - ID: {entry.id}, School: {entry.school.establishment_name} '
                    f'(URN: {entry.school.urn}), Created: {entry.created_at}'
                )
            self.stdout.write(f'  ... and {count - 10} more entries')

        # Delete if requested
        if delete and not dry_run:
            self.stdout.write(
                '\n' + self.style.ERROR('DELETING SchoolData ENTRIES'))
            self.stdout.write('=' * 80)

            confirm = input(
                f'\nAre you sure you want to delete {count} SchoolData entries? (yes/no): ')

            if confirm.lower() == 'yes':
                deleted_count, _ = queryset.delete()
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\n[OK] Successfully deleted {deleted_count} SchoolData entries')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        '\n[CANCELLED] Deletion cancelled by user')
                )
        elif dry_run:
            self.stdout.write('\n' + self.style.WARNING('DRY RUN MODE'))
            self.stdout.write('=' * 80)
            self.stdout.write(
                self.style.WARNING(
                    f'[INFO] This is a DRY RUN. No entries were deleted.\n'
                    f'[INFO] To actually delete these {count} entries, add --delete flag:\n'
                )
            )
            if filter_unwanted_text:
                self.stdout.write(
                    f'[INFO] python manage.py remove_school_data --filter-unwanted-text --delete'
                )
            elif school_id:
                self.stdout.write(
                    f'[INFO] python manage.py remove_school_data --school-id {school_id} --delete'
                )
            else:
                self.stdout.write(
                    f'[INFO] python manage.py remove_school_data --all --delete'
                )

        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('Operation complete!'))
