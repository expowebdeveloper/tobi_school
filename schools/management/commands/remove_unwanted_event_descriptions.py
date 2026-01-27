import json
from django.core.management.base import BaseCommand
from schools.models import School, SchoolData


class Command(BaseCommand):
    help = 'Remove SchoolData entries that contain unwanted event description text patterns'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting (default: True)'
        )
        parser.add_argument(
            '--delete',
            action='store_true',
            help='Actually delete the matching entries (use with caution!)'
        )
        parser.add_argument(
            '--case-sensitive',
            action='store_true',
            help='Make search case-sensitive (default: case-insensitive)'
        )

    def search_in_data(self, data, search_strings, case_sensitive=False):
        """
        Recursively search for strings in JSON data structure.
        Returns True if any of the search strings is found.
        """
        if data is None:
            return False

        # Convert data to string for searching
        try:
            data_str = json.dumps(data, ensure_ascii=False)
            if not case_sensitive:
                data_str = data_str.lower()
                search_strings = [s.lower() for s in search_strings]
            
            # Check if any search string is in the data
            for search_str in search_strings:
                if search_str in data_str:
                    return True
            return False
        except (TypeError, ValueError, json.JSONDecodeError):
            return False

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        delete = options['delete']
        case_sensitive = options['case_sensitive']

        # Default to dry-run if --delete is not specified
        if not delete:
            dry_run = True

        # Strings to search for
        search_strings = [
            "FULL original event description exactly as written",
            "Original official event description"
        ]

        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS(
            'REMOVING SchoolData WITH UNWANTED EVENT DESCRIPTIONS'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write('Search Strings:')
        for search_str in search_strings:
            self.stdout.write(f'  - "{search_str}"')
        self.stdout.write(f'Case Sensitive: {case_sensitive}')
        self.stdout.write(
            f'Mode: {"DRY RUN (preview only)" if dry_run else "DELETE MODE"}')
        self.stdout.write('=' * 80)

        # Get all SchoolData entries
        all_school_data = SchoolData.objects.select_related('school').all()
        total_count = all_school_data.count()

        matching_entries = []

        # Search through each entry
        self.stdout.write('\nSearching through SchoolData entries...')
        for school_data in all_school_data:
            school = school_data.school
            data = school_data.data

            # Skip if data is None
            if data is None:
                continue

            # Check if any of the search strings are in the data
            if self.search_in_data(data, search_strings, case_sensitive):
                entry_info = {
                    'id': school_data.id,
                    'school_urn': school.urn,
                    'school_name': school.establishment_name,
                    'local_authority': school.local_authority,
                    'created_at': school_data.created_at,
                    'updated_at': school_data.updated_at,
                    'data': data
                }
                matching_entries.append(entry_info)

        # Print results
        self.stdout.write('\n' + self.style.SUCCESS('SEARCH RESULTS'))
        self.stdout.write('=' * 80)
        self.stdout.write(f'Total SchoolData entries checked: {total_count}')
        self.stdout.write(
            self.style.WARNING(
                f'Entries containing unwanted text: {len(matching_entries)}')
        )

        if matching_entries:
            self.stdout.write('\n' + self.style.ERROR('MATCHING ENTRIES'))
            self.stdout.write('=' * 80)

            for idx, entry in enumerate(matching_entries, 1):
                self.stdout.write(f'\n[{idx}] Entry ID: {entry["id"]}')
                self.stdout.write(f'    School URN: {entry["school_urn"]}')
                self.stdout.write(f'    School Name: {entry["school_name"]}')
                self.stdout.write(
                    f'    Local Authority: {entry["local_authority"]}')
                self.stdout.write(f'    Created At: {entry["created_at"]}')
                self.stdout.write(f'    Updated At: {entry["updated_at"]}')
                
                # Show a preview of the data
                try:
                    data_preview = json.dumps(
                        entry["data"], indent=2, ensure_ascii=False)[:500]
                    self.stdout.write(f'    Data Preview: {data_preview}...')
                except:
                    self.stdout.write(f'    Data Preview: [Unable to display]')
                
                self.stdout.write('-' * 80)

            # Delete entries if requested
            if delete and not dry_run:
                self.stdout.write(
                    '\n' + self.style.ERROR('DELETING MATCHING ENTRIES'))
                self.stdout.write('=' * 80)

                confirm = input(
                    f'\nAre you sure you want to delete {len(matching_entries)} entries? (yes/no): ')

                if confirm.lower() == 'yes':
                    deleted_count = 0
                    for entry in matching_entries:
                        try:
                            SchoolData.objects.filter(id=entry['id']).delete()
                            deleted_count += 1
                        except Exception as e:
                            self.stdout.write(
                                self.style.ERROR(
                                    f'Error deleting entry {entry["id"]}: {str(e)}')
                            )

                    self.stdout.write(
                        self.style.SUCCESS(
                            f'\n[OK] Successfully deleted {deleted_count} entries')
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
                        f'[INFO] To actually delete these {len(matching_entries)} entries, run:\n'
                        f'[INFO] python manage.py remove_unwanted_event_descriptions --delete'
                    )
                )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n[OK] No entries found containing the unwanted text patterns')
            )

        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('Search complete!'))
