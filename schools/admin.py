import csv
from django.contrib import admin
from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils.html import format_html
from .models import School, SchoolData


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ('urn', 'establishment_name', 'local_authority',
                    'establishment_status', 'process', 'second_scraper', 'third_scraper')
    list_filter = ('local_authority', 'establishment_status',
                   'process', 'second_scraper', 'third_scraper')
    search_fields = ('urn', 'establishment_name', 'local_authority')
    ordering = ('establishment_name',)
    readonly_fields = ('urn',)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}

        # Get total counts
        total_schools = School.objects.count()
        processed_count = School.objects.filter(process=True).count()
        not_processed_count = School.objects.filter(process=False).count()

        # Calculate percentage
        processed_percentage = (
            processed_count / total_schools * 100) if total_schools > 0 else 0
        not_processed_percentage = (
            not_processed_count / total_schools * 100) if total_schools > 0 else 0

        # Get second_scraper counts
        second_scraper_true = School.objects.filter(
            second_scraper=True).count()
        second_scraper_false = School.objects.filter(
            second_scraper=False).count()
        second_scraper_true_percentage = (
            second_scraper_true / total_schools * 100) if total_schools > 0 else 0
        second_scraper_false_percentage = (
            second_scraper_false / total_schools * 100) if total_schools > 0 else 0

        # Get third_scraper counts
        third_scraper_true = School.objects.filter(third_scraper=True).count()
        third_scraper_false = School.objects.filter(
            third_scraper=False).count()
        third_scraper_true_percentage = (
            third_scraper_true / total_schools * 100) if total_schools > 0 else 0
        third_scraper_false_percentage = (
            third_scraper_false / total_schools * 100) if total_schools > 0 else 0

        extra_context['process_stats'] = {
            'total': total_schools,
            'processed': processed_count,
            'not_processed': not_processed_count,
            'processed_percentage': round(processed_percentage, 1),
            'not_processed_percentage': round(not_processed_percentage, 1),
        }

        extra_context['second_scraper_stats'] = {
            'true': second_scraper_true,
            'false': second_scraper_false,
            'true_percentage': round(second_scraper_true_percentage, 1),
            'false_percentage': round(second_scraper_false_percentage, 1),
        }

        extra_context['third_scraper_stats'] = {
            'true': third_scraper_true,
            'false': third_scraper_false,
            'true_percentage': round(third_scraper_true_percentage, 1),
            'false_percentage': round(third_scraper_false_percentage, 1),
        }

        return super().changelist_view(request, extra_context=extra_context)


@admin.register(SchoolData)
class SchoolDataAdmin(admin.ModelAdmin):
    list_display = ('school', 'data_status', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('school__urn', 'school__establishment_name')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    actions = ['export_to_csv']

    fieldsets = (
        ('School Information', {
            'fields': ('school',)
        }),
        ('JSON Data', {
            'fields': ('data',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def data_status(self, obj):
        """Display status of the data (Refined/Invalid)."""
        if not obj.data:
            return format_html('<span style="color: red;">❌ NULL</span>')

        data = obj.data
        if isinstance(data, dict) and 'school_name' in data and 'terms' in data:
            terms = data.get('terms', [])
            if isinstance(terms, list) and len(terms) > 0:
                return format_html('<span style="color: green;">✓ Refined</span>')
            else:
                return format_html('<span style="color: orange;">⚠ Empty Terms</span>')
        else:
            return format_html('<span style="color: red;">❌ Invalid</span>')

    data_status.short_description = 'Data Status'

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}

        # Get all SchoolData entries
        all_data = SchoolData.objects.all()
        total_count = all_data.count()

        # Count refined data (valid calendar format with terms)
        refined_count = 0
        invalid_count = 0
        empty_terms_count = 0
        null_count = 0

        for sd in all_data:
            if not sd.data:
                null_count += 1
                invalid_count += 1
            elif isinstance(sd.data, dict) and 'school_name' in sd.data and 'terms' in sd.data:
                terms = sd.data.get('terms', [])
                if isinstance(terms, list) and len(terms) > 0:
                    refined_count += 1
                else:
                    empty_terms_count += 1
                    invalid_count += 1
            else:
                invalid_count += 1

        # Calculate percentages
        refined_percentage = (refined_count / total_count *
                              100) if total_count > 0 else 0
        invalid_percentage = (invalid_count / total_count *
                              100) if total_count > 0 else 0

        extra_context['data_stats'] = {
            'total': total_count,
            'refined': refined_count,
            'invalid': invalid_count,
            'empty_terms': empty_terms_count,
            'null': null_count,
            'refined_percentage': round(refined_percentage, 1),
            'invalid_percentage': round(invalid_percentage, 1),
        }

        return super().changelist_view(request, extra_context=extra_context)

    def export_to_csv(self, request, queryset):
        """Export selected SchoolData entries to CSV."""
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="school_data_export.csv"'

        writer = csv.writer(response)

        # Write headers
        writer.writerow([
            'ID', 'School URN', 'School Name', 'Local Authority',
            'Data Status', 'Has Terms', 'Terms Count', 'Created At', 'Updated At'
        ])

        # Write data rows
        for school_data in queryset:
            school = school_data.school
            data = school_data.data

            # Determine status
            status = 'Invalid'
            has_terms = False
            terms_count = 0

            if not data:
                status = 'NULL'
            elif isinstance(data, dict) and 'school_name' in data and 'terms' in data:
                terms = data.get('terms', [])
                if isinstance(terms, list):
                    terms_count = len(terms)
                    if terms_count > 0:
                        status = 'Refined'
                        has_terms = True
                    else:
                        status = 'Empty Terms'

            writer.writerow([
                school_data.id,
                school.urn,
                school.establishment_name,
                school.local_authority,
                status,
                'Yes' if has_terms else 'No',
                terms_count,
                school_data.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                school_data.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
            ])

        self.message_user(
            request, f'Successfully exported {queryset.count()} entries to CSV.')
        return response

    export_to_csv.short_description = 'Export selected entries to CSV'
