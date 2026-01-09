import csv
import json
import os
from django.core.management.base import BaseCommand
from django.db import transaction
from schools.models import School, SchoolData


class Command(BaseCommand):
    help = 'Import schools data from CSV file. Skips records that already exist.'

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_file',
            type=str,
            help='Path to the CSV file to import'
        )
        parser.add_argument(
            '--process',
            action='store_true',
            help='Set process to True for all imported schools (default: False)'
        )

    def handle(self, *args, **options):
        csv_file_path = options['csv_file']
        process_value = options.get('process', False)

        # Check if file exists
        if not os.path.exists(csv_file_path):
            self.stdout.write(
                self.style.ERROR(f'File not found: {csv_file_path}')
            )
            return

        self.stdout.write(f'Starting import from {csv_file_path}...')

        created_count = 0
        skipped_count = 0
        error_count = 0

        # Try different encodings to handle various CSV file formats
        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
        file = None
        encoding_used = None

        for encoding in encodings:
            try:
                file = open(csv_file_path, 'r', encoding=encoding)
                # Test read first line to verify encoding works
                file.readline()
                file.seek(0)  # Reset to beginning
                encoding_used = encoding
                self.stdout.write(f'Using encoding: {encoding}')
                break
            except (UnicodeDecodeError, UnicodeError):
                if file:
                    file.close()
                continue
            except Exception:
                if file:
                    file.close()
                continue

        if not file or not encoding_used:
            self.stdout.write(
                self.style.ERROR(
                    'Could not determine file encoding. Tried: utf-8, latin-1, cp1252, iso-8859-1')
            )
            return

        try:
            reader = csv.DictReader(file)

            with transaction.atomic():
                # Start at 2 (row 1 is header)
                for row_num, row in enumerate(reader, start=2):
                    try:
                        # Extract required fields
                        urn_str = row.get('URN', '').strip()

                        # Skip empty rows
                        if not urn_str:
                            continue

                        try:
                            urn = int(urn_str)
                        except ValueError:
                            self.stdout.write(
                                self.style.WARNING(
                                    f'Row {row_num}: Invalid URN "{urn_str}", skipping...'
                                )
                            )
                            error_count += 1
                            continue

                        # Check if school already exists
                        if School.objects.filter(urn=urn).exists():
                            skipped_count += 1
                            continue

                        # Extract other required fields
                        establishment_name = row.get(
                            'EstablishmentName', '').strip()
                        local_authority = row.get('LA (name)', '').strip()
                        establishment_status = row.get(
                            'EstablishmentStatus (name)', '').strip()
                        website = row.get('SchoolWebsite', '').strip()

                        # Validate required fields
                        if not establishment_name:
                            self.stdout.write(
                                self.style.WARNING(
                                    f'Row {row_num}: Missing EstablishmentName for URN {urn}, skipping...'
                                )
                            )
                            error_count += 1
                            continue

                        # Create School object
                        school = School.objects.create(
                            urn=urn,
                            establishment_name=establishment_name,
                            local_authority=local_authority or 'Unknown',
                            establishment_status=establishment_status or 'Unknown',
                            process=process_value,
                            website=website or None
                        )

                        # Store full row data as JSON in SchoolData
                        # Convert all values to strings and clean up
                        json_data = {}
                        for key, value in row.items():
                            if value and value.strip():
                                json_data[key] = value.strip()
                            else:
                                json_data[key] = None

                        created_count += 1

                        if created_count % 100 == 0:
                            self.stdout.write(
                                f'Processed {created_count} schools...'
                            )

                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(
                                f'Row {row_num}: Error - {str(e)}'
                            )
                        )
                        error_count += 1
                        continue

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error reading CSV file: {str(e)}')
            )
            return
        finally:
            if file:
                file.close()

        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f'\nImport completed!\n'
                f'Created: {created_count} schools\n'
                f'Skipped (already exist): {skipped_count} schools\n'
                f'Errors: {error_count} rows'
            )
        )
