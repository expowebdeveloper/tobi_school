import json
import re
from django.core.management.base import BaseCommand
from django.db import transaction
from schools.models import School, SchoolData


class Command(BaseCommand):
    help = 'Refine and format SchoolData to extract academic calendar JSON, save in proper format, and optionally delete invalid entries'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be processed without actually saving (default: True)'
        )
        parser.add_argument(
            '--save',
            action='store_true',
            help='Actually save the refined data (use with caution!)'
        )
        parser.add_argument(
            '--delete-invalid',
            action='store_true',
            help='Delete entries that cannot be refined to the calendar format'
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
            default='refined_calendar_data.json',
            help='Output file name (only used with --output file)'
        )

    def extract_json_from_text(self, text):
        """Extract JSON from text that might contain markdown code blocks or other text."""
        if not text:
            return None

        # Try to parse as direct JSON first
        try:
            data = json.loads(text)
            return data
        except:
            pass

        # Try to extract JSON from markdown code blocks
        # Pattern: ```json ... ``` or ``` ... ```
        json_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        matches = re.findall(json_pattern, text, re.DOTALL)
        if matches:
            try:
                return json.loads(matches[0])
            except:
                pass

        # Try to find JSON object in text
        # Look for { ... } pattern
        brace_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(brace_pattern, text, re.DOTALL)
        for match in matches:
            try:
                data = json.loads(match)
                # Check if it has the expected structure
                if isinstance(data, dict) and 'school_name' in data and 'terms' in data:
                    return data
            except:
                continue

        return None

    def validate_calendar_format(self, data):
        """Validate that data matches the expected calendar format."""
        if not isinstance(data, dict):
            return False, "Not a dictionary"

        required_fields = ['school_name', 'source_url', 'terms']
        for field in required_fields:
            if field not in data:
                return False, f"Missing required field: {field}"

        if not isinstance(data['terms'], list):
            return False, "terms must be a list"

        # Check if terms array is empty
        if len(data['terms']) == 0:
            return False, "terms array is empty (no terms data)"

        # Validate each term
        for term in data['terms']:
            if not isinstance(term, dict):
                return False, "Term must be a dictionary"
            if 'academic_year' not in term or 'term_name' not in term or 'events' not in term:
                return False, "Term missing required fields"
            if not isinstance(term['events'], list):
                return False, "Events must be a list"

            # Validate each event
            for event in term['events']:
                if not isinstance(event, dict):
                    return False, "Event must be a dictionary"
                required_event_fields = ['start_date', 'event_text']
                for field in required_event_fields:
                    if field not in event:
                        return False, f"Event missing required field: {field}"

        return True, "Valid"

    def refine_data(self, data):
        """Refine data to match the exact format."""
        if not data:
            return None

        refined = {
            'school_name': data.get('school_name', ''),
            'source_url': data.get('source_url', ''),
            'terms': []
        }

        # Process terms
        for term in data.get('terms', []):
            refined_term = {
                'academic_year': term.get('academic_year', ''),
                'term_name': term.get('term_name', ''),
                'events': []
            }

            # Process events
            for event in term.get('events', []):
                refined_event = {
                    'start_date': event.get('start_date', ''),
                    'end_date': event.get('end_date'),
                    'time': event.get('time'),
                    'event_text': event.get('event_text', '')
                }
                refined_term['events'].append(refined_event)

            refined['terms'].append(refined_term)

        return refined

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        save = options['save']
        delete_invalid = options['delete_invalid']
        output_format = options['output']
        output_file = options['file']

        # Default to dry-run if --save is not specified
        if not save:
            dry_run = True

        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS(
            'REFINING ACADEMIC CALENDAR DATA'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(
            f'Mode: {"DRY RUN (preview only)" if dry_run else "SAVE MODE"}')
        if delete_invalid:
            self.stdout.write(self.style.WARNING(
                'Will delete invalid entries after processing'))
        self.stdout.write('=' * 80)

        # Get all SchoolData entries
        all_school_data = SchoolData.objects.select_related('school').all()
        total_count = all_school_data.count()

        refined_entries = []
        invalid_entries = []
        processed_count = 0

        with transaction.atomic():
            for school_data in all_school_data:
                school = school_data.school
                data = school_data.data

                if data is None:
                    invalid_entries.append({
                        'id': school_data.id,
                        'school_urn': school.urn,
                        'school_name': school.establishment_name,
                        'reason': 'Data is NULL'
                    })
                    continue

                # Try to extract JSON from various formats
                extracted_json = None

                # Check if data is already in the correct format
                if isinstance(data, dict) and 'school_name' in data and 'terms' in data:
                    extracted_json = data
                # Check if data has 'text' or 'raw' field with JSON
                elif isinstance(data, dict):
                    if 'text' in data:
                        extracted_json = self.extract_json_from_text(
                            data['text'])
                    elif 'raw' in data:
                        extracted_json = self.extract_json_from_text(
                            data['raw'])
                    # Try the whole data as JSON string
                    elif len(data) == 1 and isinstance(list(data.values())[0], str):
                        extracted_json = self.extract_json_from_text(
                            list(data.values())[0])

                if not extracted_json:
                    invalid_entries.append({
                        'id': school_data.id,
                        'school_urn': school.urn,
                        'school_name': school.establishment_name,
                        'reason': 'Could not extract JSON'
                    })
                    continue

                # Validate format
                is_valid, error_msg = self.validate_calendar_format(
                    extracted_json)
                if not is_valid:
                    invalid_entries.append({
                        'id': school_data.id,
                        'school_urn': school.urn,
                        'school_name': school.establishment_name,
                        'reason': f'Invalid format: {error_msg}'
                    })
                    continue

                # Refine data
                refined_data = self.refine_data(extracted_json)

                if refined_data:
                    entry_info = {
                        'id': school_data.id,
                        'school_urn': school.urn,
                        'school_name': school.establishment_name,
                        'original_data': data,
                        'refined_data': refined_data
                    }
                    refined_entries.append(entry_info)

                    # Save if not dry-run
                    if not dry_run:
                        school_data.data = refined_data
                        school_data.save()
                        processed_count += 1

        # Print results
        self.stdout.write('\n' + self.style.SUCCESS('PROCESSING RESULTS'))
        self.stdout.write('=' * 80)
        self.stdout.write(f'Total SchoolData entries: {total_count}')
        self.stdout.write(
            self.style.SUCCESS(
                f'[OK] Entries with valid calendar data: {len(refined_entries)}')
        )
        self.stdout.write(
            self.style.WARNING(
                f'[WARNING] Invalid entries: {len(invalid_entries)}')
        )

        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'[OK] Successfully saved: {processed_count} entries')
            )

        # Show refined entries
        if refined_entries:
            self.stdout.write('\n' + self.style.SUCCESS('REFINED ENTRIES'))
            self.stdout.write('=' * 80)

            all_refined_data = []
            # Show first 10
            for idx, entry in enumerate(refined_entries[:10], 1):
                self.stdout.write(f'\n[{idx}] Entry ID: {entry["id"]}')
                self.stdout.write(f'    School URN: {entry["school_urn"]}')
                self.stdout.write(f'    School Name: {entry["school_name"]}')
                self.stdout.write(
                    f'    Calendar: {entry["refined_data"]["school_name"]}')
                self.stdout.write(
                    f'    Terms: {len(entry["refined_data"]["terms"])} terms')
                all_refined_data.append(entry["refined_data"])

            if len(refined_entries) > 10:
                self.stdout.write(
                    f'\n... and {len(refined_entries) - 10} more entries')

            # Save to file if requested
            if output_format == 'file':
                try:
                    # Collect all refined data
                    all_data = [e["refined_data"] for e in refined_entries]
                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(all_data, f, indent=2, ensure_ascii=False)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'\nRefined data saved to: {output_file}')
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Error writing to file: {str(e)}')
                    )

        # Show invalid entries
        if invalid_entries:
            self.stdout.write('\n' + self.style.WARNING('INVALID ENTRIES'))
            self.stdout.write('=' * 80)
            # Show first 20
            for idx, entry in enumerate(invalid_entries[:20], 1):
                self.stdout.write(
                    f'[{idx}] Entry ID: {entry["id"]}, '
                    f'URN: {entry["school_urn"]}, '
                    f'Name: {entry["school_name"]}, '
                    f'Reason: {entry["reason"]}'
                )
            if len(invalid_entries) > 20:
                self.stdout.write(
                    f'\n... and {len(invalid_entries) - 20} more invalid entries')

            # Delete invalid entries if requested
            if delete_invalid and not dry_run:
                self.stdout.write(
                    '\n' + self.style.ERROR('DELETING INVALID ENTRIES'))
                self.stdout.write('=' * 80)

                confirm = input(
                    f'\nAre you sure you want to delete {len(invalid_entries)} invalid entries? (yes/no): '
                )

                if confirm.lower() == 'yes':
                    deleted_count = 0
                    for entry in invalid_entries:
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
            elif delete_invalid and dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        f'\n[DRY RUN] Would delete {len(invalid_entries)} invalid entries'
                    )
                )

        if dry_run:
            self.stdout.write('\n' + self.style.WARNING('DRY RUN MODE'))
            self.stdout.write('=' * 80)
            self.stdout.write(
                self.style.WARNING(
                    f'[INFO] This is a DRY RUN. No data was saved.\n'
                    f'[INFO] To actually save refined data, run:\n'
                    f'[INFO] python manage.py refine_calendar_data --save'
                )
            )

        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('Processing complete!'))
