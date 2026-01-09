import json
from django.core.management.base import BaseCommand
from schools.models import School, SchoolData


class Command(BaseCommand):
    help = 'Filter and print SchoolData entries that have invalid or missing JSON data'

    def add_arguments(self, parser):
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
            default='invalid_json_data.txt',
            help='Output file name (only used with --output file)'
        )
        parser.add_argument(
            '--summary-only',
            action='store_true',
            help='Show only summary statistics, not detailed entries'
        )

    def handle(self, *args, **options):
        output_format = options['output']
        output_file = options['file']
        summary_only = options['summary_only']

        self.stdout.write(self.style.SUCCESS(
            'Starting validation of SchoolData JSON...'))
        self.stdout.write('=' * 80)

        # Get all SchoolData entries
        all_school_data = SchoolData.objects.select_related('school').all()
        total_count = all_school_data.count()

        invalid_entries = []
        empty_entries = []
        null_entries = []
        valid_entries = []

        # Check each entry
        for school_data in all_school_data:
            school = school_data.school
            data = school_data.data

            entry_info = {
                'id': school_data.id,
                'school_urn': school.urn,
                'school_name': school.establishment_name,
                'created_at': school_data.created_at,
                'updated_at': school_data.updated_at,
                'data': data
            }

            # Check if data is None
            if data is None:
                null_entries.append(entry_info)
                invalid_entries.append(entry_info)
                continue

            # Check if data is empty dict
            if isinstance(data, dict) and len(data) == 0:
                empty_entries.append(entry_info)
                invalid_entries.append(entry_info)
                continue

            # Try to validate JSON by serializing/deserializing
            try:
                # Try to serialize and deserialize to ensure it's valid JSON
                json_str = json.dumps(data)
                json.loads(json_str)
                valid_entries.append(entry_info)
            except (TypeError, ValueError, json.JSONDecodeError) as e:
                # Invalid JSON
                entry_info['error'] = str(e)
                invalid_entries.append(entry_info)

        # Print summary
        self.stdout.write('\n' + self.style.SUCCESS('VALIDATION SUMMARY'))
        self.stdout.write('=' * 80)
        self.stdout.write(f'Total SchoolData entries: {total_count}')
        self.stdout.write(
            self.style.SUCCESS(
                f'[OK] Valid JSON entries: {len(valid_entries)}')
        )
        self.stdout.write(
            self.style.WARNING(
                f'[WARNING] Invalid/Missing JSON entries: {len(invalid_entries)}')
        )
        self.stdout.write(f'  - NULL entries: {len(null_entries)}')
        self.stdout.write(f'  - Empty entries: {len(empty_entries)}')
        self.stdout.write(
            f'  - Invalid JSON entries: {len(invalid_entries) - len(null_entries) - len(empty_entries)}'
        )

        if summary_only:
            return

        # Print detailed invalid entries
        if invalid_entries:
            self.stdout.write(
                '\n' + self.style.ERROR('INVALID/MISSING JSON ENTRIES'))
            self.stdout.write('=' * 80)

            for entry in invalid_entries:
                self.stdout.write(f"\nEntry ID: {entry['id']}")
                self.stdout.write(f"School URN: {entry['school_urn']}")
                self.stdout.write(f"School Name: {entry['school_name']}")
                self.stdout.write(f"Created At: {entry['created_at']}")
                self.stdout.write(f"Updated At: {entry['updated_at']}")

                if entry['data'] is None:
                    status = 'NULL'
                    self.stdout.write(
                        f"Data Status: {self.style.ERROR(status)}")
                elif isinstance(entry['data'], dict) and len(entry['data']) == 0:
                    status = 'EMPTY DICTIONARY'
                    self.stdout.write(
                        f"Data Status: {self.style.WARNING(status)}")
                else:
                    status = 'INVALID JSON'
                    self.stdout.write(
                        f"Data Status: {self.style.ERROR(status)}")
                    if 'error' in entry:
                        self.stdout.write(f"Error: {entry['error']}")

                data_preview = str(entry['data'])[:200] + "..." if entry['data'] and len(
                    str(entry['data'])) > 200 else (str(entry['data']) if entry['data'] else "None")
                self.stdout.write(f"Data Content: {data_preview}")
                self.stdout.write("-" * 80)

            # Write to file if requested
            if output_format == 'file':
                try:
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write('INVALID/MISSING JSON ENTRIES REPORT\n')
                        f.write('=' * 80 + '\n\n')
                        f.write(
                            f'Total Invalid Entries: {len(invalid_entries)}\n')
                        f.write(f'NULL Entries: {len(null_entries)}\n')
                        f.write(f'Empty Entries: {len(empty_entries)}\n')
                        f.write(
                            f'Invalid JSON Entries: {len(invalid_entries) - len(null_entries) - len(empty_entries)}\n')
                        f.write('\n' + '=' * 80 + '\n\n')

                        for entry in invalid_entries:
                            f.write(f"Entry ID: {entry['id']}\n")
                            f.write(f"School URN: {entry['school_urn']}\n")
                            f.write(f"School Name: {entry['school_name']}\n")
                            f.write(f"Created At: {entry['created_at']}\n")
                            f.write(f"Updated At: {entry['updated_at']}\n")
                            if entry['data'] is None:
                                f.write("Data Status: NULL\n")
                            elif isinstance(entry['data'], dict) and len(entry['data']) == 0:
                                f.write("Data Status: EMPTY DICTIONARY\n")
                            else:
                                f.write("Data Status: INVALID JSON\n")
                                if 'error' in entry:
                                    f.write(f"Error: {entry['error']}\n")
                            data_str = json.dumps(
                                entry['data'], indent=2, ensure_ascii=False) if entry['data'] else "None"
                            f.write(f"Data Content:\n{data_str}\n")
                            f.write("-" * 80 + "\n\n")

                    self.stdout.write(
                        self.style.SUCCESS(f'\nReport saved to: {output_file}')
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Error writing to file: {str(e)}')
                    )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    '\n[OK] All SchoolData entries have valid JSON!')
            )

        # Print schools without any SchoolData
        schools_without_data = School.objects.filter(school_data__isnull=True)
        if schools_without_data.exists():
            self.stdout.write(
                '\n' + self.style.WARNING('SCHOOLS WITHOUT ANY SchoolData'))
            self.stdout.write('=' * 80)
            self.stdout.write(f'Total: {schools_without_data.count()}')
            if not summary_only:
                for school in schools_without_data[:20]:  # Show first 20
                    self.stdout.write(
                        f"  - URN: {school.urn}, Name: {school.establishment_name}")
                if schools_without_data.count() > 20:
                    self.stdout.write(
                        f"  ... and {schools_without_data.count() - 20} more")

        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('Validation complete!'))
