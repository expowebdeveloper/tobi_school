from django.core.management.base import BaseCommand
from django.db import transaction
from schools.models import School, SchoolData


class Command(BaseCommand):
    help = 'Update process status based on whether school has valid calendar data in SchoolData'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without actually updating (default: True)'
        )
        parser.add_argument(
            '--update',
            action='store_true',
            help='Actually update the process status (use with caution!)'
        )
        parser.add_argument(
            '--set-false',
            action='store_true',
            help='Also set process=False for schools without valid calendar data'
        )

    def has_valid_calendar_data(self, school):
        """Check if school has valid calendar data in SchoolData."""
        school_data = SchoolData.objects.filter(school=school).order_by('-created_at').first()
        
        if not school_data or not school_data.data:
            return False
        
        data = school_data.data
        
        # Check if it's in calendar format
        if isinstance(data, dict) and 'school_name' in data and 'terms' in data:
            # Check if terms array is not empty
            terms = data.get('terms', [])
            if isinstance(terms, list) and len(terms) > 0:
                return True
        
        return False

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        update = options['update']
        set_false = options['set_false']

        # Default to dry-run if --update is not specified
        if not update:
            dry_run = True

        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('UPDATING PROCESS STATUS'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(
            f'Mode: {"DRY RUN (preview only)" if dry_run else "UPDATE MODE"}'
        )
        if set_false:
            self.stdout.write(
                self.style.WARNING('Will also set process=False for schools without valid data')
            )
        self.stdout.write('=' * 80)

        # Get all schools
        all_schools = School.objects.all()
        total_schools = all_schools.count()

        schools_to_set_true = []
        schools_to_set_false = []
        schools_already_correct = []

        with transaction.atomic():
            for school in all_schools:
                has_valid_data = self.has_valid_calendar_data(school)
                current_process = school.process

                if has_valid_data:
                    if not current_process:
                        # Has data but process is False - need to set True
                        schools_to_set_true.append(school)
                    else:
                        # Has data and process is already True - correct
                        schools_already_correct.append({
                            'school': school,
                            'status': 'Has data, process=True'
                        })
                else:
                    if current_process and set_false:
                        # No valid data but process is True - set False if flag is set
                        schools_to_set_false.append(school)
                    elif not current_process:
                        # No data and process is False - already correct
                        schools_already_correct.append({
                            'school': school,
                            'status': 'No data, process=False'
                        })

        # Print results
        self.stdout.write('\n' + self.style.SUCCESS('ANALYSIS RESULTS'))
        self.stdout.write('=' * 80)
        self.stdout.write(f'Total schools: {total_schools}')
        self.stdout.write(
            self.style.SUCCESS(
                f'[OK] Schools with valid calendar data: {len(schools_to_set_true) + len([s for s in schools_already_correct if s["status"] == "Has data, process=True"])}'
            )
        )
        self.stdout.write(
            self.style.WARNING(
                f'[UPDATE] Schools to set process=True: {len(schools_to_set_true)}'
            )
        )
        if set_false:
            self.stdout.write(
                self.style.WARNING(
                    f'[UPDATE] Schools to set process=False: {len(schools_to_set_false)}'
                )
            )
        self.stdout.write(
            self.style.SUCCESS(
                f'[OK] Schools already correct: {len(schools_already_correct)}'
            )
        )

        # Show schools to update
        if schools_to_set_true:
            self.stdout.write('\n' + self.style.SUCCESS('SCHOOLS TO SET process=True'))
            self.stdout.write('=' * 80)
            for idx, school in enumerate(schools_to_set_true[:20], 1):
                self.stdout.write(
                    f'[{idx}] URN: {school.urn}, Name: {school.establishment_name}'
                )
            if len(schools_to_set_true) > 20:
                self.stdout.write(
                    f'\n... and {len(schools_to_set_true) - 20} more schools'
                )

        if schools_to_set_false and set_false:
            self.stdout.write('\n' + self.style.WARNING('SCHOOLS TO SET process=False'))
            self.stdout.write('=' * 80)
            for idx, school in enumerate(schools_to_set_false[:20], 1):
                self.stdout.write(
                    f'[{idx}] URN: {school.urn}, Name: {school.establishment_name}'
                )
            if len(schools_to_set_false) > 20:
                self.stdout.write(
                    f'\n... and {len(schools_to_set_false) - 20} more schools'
                )

        # Update if not dry-run
        if not dry_run:
            updated_true_count = 0
            updated_false_count = 0

            self.stdout.write('\n' + self.style.SUCCESS('UPDATING PROCESS STATUS'))
            self.stdout.write('=' * 80)

            # Set process=True for schools with valid data
            for school in schools_to_set_true:
                try:
                    school.process = True
                    school.save()
                    updated_true_count += 1
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'Error updating school {school.urn}: {str(e)}'
                        )
                    )

            # Set process=False for schools without valid data (if flag is set)
            if set_false:
                for school in schools_to_set_false:
                    try:
                        school.process = False
                        school.save()
                        updated_false_count += 1
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(
                                f'Error updating school {school.urn}: {str(e)}'
                            )
                        )

            self.stdout.write(
                self.style.SUCCESS(
                    f'\n[OK] Successfully set process=True for {updated_true_count} schools'
                )
            )
            if set_false:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'[OK] Successfully set process=False for {updated_false_count} schools'
                    )
                )
        else:
            self.stdout.write('\n' + self.style.WARNING('DRY RUN MODE'))
            self.stdout.write('=' * 80)
            self.stdout.write(
                self.style.WARNING(
                    f'[INFO] This is a DRY RUN. No updates were made.\n'
                    f'[INFO] To actually update process status, run:\n'
                    f'[INFO] python manage.py update_process_status --update'
                )
            )

        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('Processing complete!'))
