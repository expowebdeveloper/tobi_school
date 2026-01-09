import csv
import json
from django.core.management.base import BaseCommand
from schools.models import School, SchoolData


class Command(BaseCommand):
    help = 'Export refined academic calendar data to CSV format with school information and term/date details'

    def add_arguments(self, parser):
        parser.add_argument(
            'output_file',
            type=str,
            help='Output CSV file path'
        )
        parser.add_argument(
            '--include-invalid',
            action='store_true',
            help='Include schools without valid calendar data'
        )

    def extract_school_info(self, school):
        """Extract school information for CSV."""
        # Try to get address from SchoolData if available
        address = ''
        latitude = ''
        longitude = ''
        contact_detail = '{}'

        # Get all SchoolData entries to find original CSV data
        all_school_data = SchoolData.objects.filter(
            school=school).order_by('-created_at')

        # First, try to find original CSV data (not refined calendar format)
        original_data = None
        for sd in all_school_data:
            if sd.data and isinstance(sd.data, dict):
                # Check if it's original CSV data (has URN, EstablishmentName, etc.)
                if 'URN' in sd.data or 'EstablishmentName' in sd.data:
                    original_data = sd.data
                    break

        # Extract address and location from original data
        if original_data:
            # Build address from Street, Locality, Town, Postcode
            address_parts = []
            if original_data.get('Street'):
                address_parts.append(str(original_data['Street']))
            if original_data.get('Locality'):
                address_parts.append(str(original_data['Locality']))
            if original_data.get('Town'):
                address_parts.append(str(original_data['Town']))
            if original_data.get('Postcode'):
                address_parts.append(str(original_data['Postcode']))
            address = ', '.join(address_parts) if address_parts else ''

            # Check for direct lat/lon if available (some datasets have these)
            if 'Latitude' in original_data:
                latitude = str(original_data['Latitude'])
            if 'Longitude' in original_data:
                longitude = str(original_data['Longitude'])
            # Note: Easting/Northing would need conversion to lat/lon

        # Build contact detail JSON
        contact_info = {}
        if school.website:
            contact_info['website'] = school.website
        elif original_data and original_data.get('SchoolWebsite'):
            contact_info['website'] = original_data['SchoolWebsite']

        if original_data:
            if original_data.get('TelephoneNum'):
                contact_info['telephone'] = original_data['TelephoneNum']

        if contact_info:
            contact_detail = json.dumps(contact_info)

        return {
            'address': address,
            'latitude': latitude,
            'longitude': longitude,
            'contact_detail': contact_detail
        }

    def extract_term_events(self, calendar_data):
        """Extract term/date/event information from calendar data."""
        terms_data = []

        if not calendar_data or 'terms' not in calendar_data:
            return terms_data

        # Process all terms (no limit)
        for term in calendar_data['terms']:
            term_name = term.get('term_name', '')
            events = term.get('events', [])

            # Get the first event's date (or combine if multiple)
            if events:
                first_event = events[0]
                start_date = first_event.get('start_date', '')
                end_date = first_event.get('end_date', '')

                # Format date
                if end_date:
                    date_str = f"{start_date} to {end_date}" if start_date != end_date else start_date
                else:
                    date_str = start_date

                # Get event text (combine all events in the term)
                event_texts = [e.get('event_text', '')
                               for e in events if e.get('event_text')]
                event_detail = ' | '.join(event_texts) if event_texts else ''
            else:
                date_str = ''
                event_detail = ''

            terms_data.append({
                'term': term_name,
                'date': date_str,
                'detail': event_detail
            })

        return terms_data

    def find_max_terms(self, schools, include_invalid=False):
        """Scan all schools to find the maximum number of terms."""
        max_terms = 0

        self.stdout.write('Scanning schools to determine maximum terms...')

        for school in schools:
            school_data = SchoolData.objects.filter(
                school=school).order_by('-created_at').first()

            calendar_data = None
            if school_data and school_data.data:
                data = school_data.data
                if isinstance(data, dict) and 'school_name' in data and 'terms' in data:
                    calendar_data = data

            if calendar_data:
                terms_count = len(calendar_data.get('terms', []))
                if terms_count > max_terms:
                    max_terms = terms_count
            elif include_invalid:
                # Count as 0 terms
                pass

        return max_terms

    def handle(self, *args, **options):
        output_file = options['output_file']
        include_invalid = options['include_invalid']

        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('EXPORTING CALENDAR DATA TO CSV'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(f'Output file: {output_file}')
        self.stdout.write('=' * 80)

        # Get all schools
        schools = School.objects.all().prefetch_related('school_data')
        total_schools = schools.count()

        # First pass: Find maximum number of terms across all schools
        max_terms = self.find_max_terms(schools, include_invalid)

        self.stdout.write(
            self.style.SUCCESS(f'Maximum terms found: {max_terms}')
        )
        self.stdout.write('=' * 80)

        # Prepare CSV headers
        headers = [
            'school_id',
            'school_name',
            'address',
            'latitude',
            'longitude',
            'contact_detail'
        ]

        # Dynamically add term/date/detail columns based on max_terms
        for i in range(1, max_terms + 1):
            headers.extend([f'term_{i}', f'date_{i}', f'nt_detail'])

        rows = []
        valid_count = 0
        invalid_count = 0

        self.stdout.write('Processing schools and extracting data...')

        for school in schools:
            # Get the most recent SchoolData with calendar format
            school_data = SchoolData.objects.filter(
                school=school).order_by('-created_at').first()

            calendar_data = None
            if school_data and school_data.data:
                data = school_data.data
                # Check if it's in calendar format
                if isinstance(data, dict) and 'school_name' in data and 'terms' in data:
                    calendar_data = data

            # Skip if no valid calendar data and not including invalid
            if not calendar_data and not include_invalid:
                invalid_count += 1
                continue

            # Extract school info
            school_info = self.extract_school_info(school)

            # Start building row
            row = [
                school.urn,  # school_id
                school.establishment_name,  # school_name
                school_info['address'],
                school_info['latitude'],
                school_info['longitude'],
                school_info['contact_detail']
            ]

            # Extract term/date/event data (no limit - extract all)
            if calendar_data:
                terms_data = self.extract_term_events(calendar_data)
                valid_count += 1
            else:
                terms_data = []

            # Add term columns (fill up to max_terms)
            for i in range(max_terms):
                if i < len(terms_data):
                    row.append(terms_data[i]['term'])
                    row.append(terms_data[i]['date'])
                    row.append(terms_data[i]['detail'])
                else:
                    row.extend(['', '', ''])  # Empty term, date, detail

            rows.append(row)

        # Write to CSV
        try:
            with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(headers)
                writer.writerows(rows)

            self.stdout.write('\n' + self.style.SUCCESS('EXPORT RESULTS'))
            self.stdout.write('=' * 80)
            self.stdout.write(f'Total schools processed: {total_schools}')
            self.stdout.write(
                self.style.SUCCESS(
                    f'[OK] Schools with calendar data: {valid_count}')
            )
            if include_invalid:
                self.stdout.write(
                    self.style.WARNING(
                        f'[INFO] Schools without calendar data: {invalid_count}')
                )
            self.stdout.write(f'Total rows exported: {len(rows)}')
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n[OK] CSV file created successfully: {output_file}')
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error writing CSV file: {str(e)}')
            )
            return

        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('Export complete!'))
