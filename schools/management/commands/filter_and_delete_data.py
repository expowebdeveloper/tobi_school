import json
from django.core.management.base import BaseCommand
from schools.models import School, SchoolData


class Command(BaseCommand):
    help = 'Filter SchoolData entries by text pattern and optionally delete them (with dry-run option)'

    def add_arguments(self, parser):
        parser.add_argument(
            'search_text',
            type=str,
            help='Text to search for in SchoolData JSON'
        )
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
        parser.add_argument(
            '--output',
            type=str,
            choices=['console', 'file'],
            default='console',
            help='Output format: console (default) or file'
        )
        parser.add_argument(
            '--file',
            type=str,
            default='filtered_data_report.txt',
            help='Output file name (only used with --output file)'
        )

    def handle(self, *args, **options):
        search_text = options['search_text']
        dry_run = options['dry_run']
        delete = options['delete']
        case_sensitive = options['case_sensitive']
        output_format = options['output']
        output_file = options['file']

        # Default to dry-run if --delete is not specified
        if not delete:
            dry_run = True

        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS(
            'SEARCHING SchoolData FOR TEXT PATTERN'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(f'Search Text: "{search_text}"')
        self.stdout.write(f'Case Sensitive: {case_sensitive}')
        self.stdout.write(
            f'Mode: {"DRY RUN (preview only)" if dry_run else "DELETE MODE"}')
        self.stdout.write('=' * 80)

        # Get all SchoolData entries
        all_school_data = SchoolData.objects.select_related('school').all()
        total_count = all_school_data.count()

        matching_entries = []
        search_lower = search_text.lower() if not case_sensitive else search_text

        # Search through each entry
        for school_data in all_school_data:
            school = school_data.school
            data = school_data.data

            # Skip if data is None or empty
            if data is None:
                continue

            # Convert data to string for searching
            try:
                data_str = json.dumps(data, ensure_ascii=False)
                if not case_sensitive:
                    data_str = data_str.lower()

                # Check if search text is in the data
                if search_text in data_str if case_sensitive else search_lower in data_str:
                    entry_info = {
                        'id': school_data.id,
                        'school_urn': school.urn,
                        'school_name': school.establishment_name,
                        'local_authority': school.local_authority,
                        'created_at': school_data.created_at,
                        'updated_at': school_data.updated_at,
                        'data': data,
                        'data_preview': json.dumps(data, indent=2, ensure_ascii=False)[:500]
                    }
                    matching_entries.append(entry_info)
            except (TypeError, ValueError, json.JSONDecodeError):
                # Skip invalid JSON
                continue

        # Print results
        self.stdout.write('\n' + self.style.SUCCESS('SEARCH RESULTS'))
        self.stdout.write('=' * 80)
        self.stdout.write(f'Total SchoolData entries checked: {total_count}')
        self.stdout.write(
            self.style.WARNING(
                f'Entries containing "{search_text}": {len(matching_entries)}')
        )

        if matching_entries:
            self.stdout.write('\n' + self.style.ERROR('MATCHING ENTRIES'))
            self.stdout.write('=' * 80)

            output_lines = []

            for idx, entry in enumerate(matching_entries, 1):
                self.stdout.write(f'\n[{idx}] Entry ID: {entry["id"]}')
                self.stdout.write(f'    School URN: {entry["school_urn"]}')
                self.stdout.write(f'    School Name: {entry["school_name"]}')
                self.stdout.write(
                    f'    Local Authority: {entry["local_authority"]}')
                self.stdout.write(f'    Created At: {entry["created_at"]}')
                self.stdout.write(f'    Updated At: {entry["updated_at"]}')
                self.stdout.write(f'    Data Preview:')

                # Show data preview with context around search text
                try:
                    data_str = json.dumps(
                        entry["data"], indent=2, ensure_ascii=False)
                    # Replace problematic Unicode characters
                    data_str = data_str.encode(
                        'ascii', 'replace').decode('ascii')
                except:
                    data_str = str(entry["data"])[:500]

                if len(data_str) > 1000:
                    preview = data_str[:1000] + "\n... (truncated)"
                else:
                    preview = data_str

                for line in preview.split('\n')[:20]:  # Show first 20 lines
                    try:
                        self.stdout.write(f'      {line}')
                    except UnicodeEncodeError:
                        # Skip lines with problematic characters
                        self.stdout.write(
                            f'      [Line contains non-printable characters]')

                if len(preview.split('\n')) > 20:
                    self.stdout.write(
                        f'      ... ({len(preview.split(chr(10))) - 20} more lines)')

                self.stdout.write('-' * 80)

                # Store for file output
                output_lines.append({
                    'entry': entry,
                    'preview': preview
                })

            # Write to file if requested
            if output_format == 'file':
                try:
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write('SCHOOLDATA SEARCH RESULTS\n')
                        f.write('=' * 80 + '\n\n')
                        f.write(f'Search Text: "{search_text}"\n')
                        f.write(f'Case Sensitive: {case_sensitive}\n')
                        f.write(f'Total Entries Checked: {total_count}\n')
                        f.write(f'Matching Entries: {len(matching_entries)}\n')
                        f.write('\n' + '=' * 80 + '\n\n')

                        for idx, item in enumerate(output_lines, 1):
                            entry = item['entry']
                            f.write(f"[{idx}] Entry ID: {entry['id']}\n")
                            f.write(f"School URN: {entry['school_urn']}\n")
                            f.write(f"School Name: {entry['school_name']}\n")
                            f.write(
                                f"Local Authority: {entry['local_authority']}\n")
                            f.write(f"Created At: {entry['created_at']}\n")
                            f.write(f"Updated At: {entry['updated_at']}\n")
                            f.write(f"Full Data:\n{item['preview']}\n")
                            f.write("-" * 80 + "\n\n")

                    self.stdout.write(
                        self.style.SUCCESS(f'\nReport saved to: {output_file}')
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Error writing to file: {str(e)}')
                    )

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
                        f'[INFO] python manage.py filter_and_delete_data "{search_text}" --delete'
                    )
                )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n[OK] No entries found containing "{search_text}"')
            )

        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('Search complete!'))
