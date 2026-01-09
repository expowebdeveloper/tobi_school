from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
import random
import json
from .models import School, SchoolData


@require_http_methods(["GET"])
def get_school_prompt(request, school_id):
    """
    GET API endpoint that returns school_id and the academic calendar extraction prompt.
    The prompt includes the school's website URL dynamically.

    URL: /api/schools/<school_id>/prompt/
    """
    # Validate that school exists
    try:
        school = School.objects.get(urn=school_id)
    except School.DoesNotExist:
        return JsonResponse(
            {'error': f'School with ID {school_id} not found'},
            status=404
        )
    except ValueError:
        return JsonResponse(
            {'error': 'Invalid school ID format. Must be an integer.'},
            status=400
        )

    # Get website URL from School model
    website_url = school.website
    if website_url:
        website_url = website_url.strip()
    else:
        website_url = 'https://example.com'  # Default fallback

    # Generate prompt with dynamic URL
    prompt = generate_prompt_with_url(website_url)

    # Return the response
    return JsonResponse({
        'school_id': str(school_id),
        'prompt': prompt
    })


def generate_prompt_with_url(school_website_url):
    """
    Generate the academic calendar extraction prompt with dynamic school website URL.
    """
    # Ensure URL has protocol
    if school_website_url and not school_website_url.startswith(('http://', 'https://')):
        school_website_url = 'https://' + school_website_url

    prompt = f"""You are an automated academic calendar and term-date extraction engine.

Input:
- School website URL: {school_website_url}

GOAL:
Extract 100% of ALL academic calendar, term dates, holidays, closures, and staff-only days published anywhere on the website or its linked documents.
ABSOLUTELY NO PARTIAL, GUESSED, OR TRUNCATED DATA IS ALLOWED.

CRITICAL INSTRUCTIONS (MUST FOLLOW):

1. WEBSITE CRAWLING (MANDATORY)
   - Crawl the ENTIRE website recursively.
   - Visit EVERY internal page, including but not limited to:
     - Term Dates
     - School Calendar
     - Academic Calendar
     - Parents Information
     - Key Dates
     - Policies
     - News / Announcements
     - Downloads / Documents
   - Do NOT rely on navigation menus only.
   - Follow ALL internal links until no new date-related pages exist.

2. DOCUMENT HANDLING (MANDATORY)
   - Detect and open ALL downloadable files:
     - PDF, DOC, DOCX, XLS, XLSX
   - Fully read:
     - Tables
     - Headers
     - Footnotes
     - Notes
     - Small print
   - Extract ALL date-related text from documents.
   - If a document is linked from another document, open that too.

3. EVENT EXTRACTION RULES (ZERO TOLERANCE)
   - EVERY event must be extracted as its OWN entry.
   - DO NOT merge events.
   - DO NOT summarise.
   - DO NOT rewrite text.
   - Preserve the FULL original wording EXACTLY as written.

4. DATE RULES (STRICT)
   - Convert ALL dates to ISO format: YYYY-MM-DD
   - If a date range is given:
       - start_date = first date
       - end_date = last date
   - If a single-day event:
       - end_date = null
   - If ANY part of a date is unclear or missing:
       - STOP and SEARCH again until the exact date is found
       - NEVER output placeholders like "?", "…", or incomplete dates
   - Ignore weekday names once the date is identified
   - NEVER infer dates from weekdays alone

5. TIME RULES
   - If a time is written (e.g., "closes at 2pm"):
       - Convert to 24-hour format (HH:MM)
   - If no time is written:
       - time = null

6. COVERAGE REQUIREMENTS (MANDATORY)
 Extract data for:
   - ALL academic years listed (past, current, future)
   - ALL terms:
     - Autumn
     - Spring
     - Summer
   - ALL Half Terms
   - ALL Holidays
   - ALL INSET days
   - ALL Bank Holidays
   - ALL School closures
   - ALL Staff training days
   - ALL early closures

7. VALIDATION BEFORE OUTPUT (REQUIRED)
   - Verify there are NO:
     - Missing end dates
     - Unknown dates
     - Truncated events
     - Partial years
   - If ANY event is incomplete:
     - Re-crawl the site and documents
     - Do NOT output until complete

OUTPUT FORMAT (JSON ONLY — NO EXPLANATION):

{{
  "school_name": "Education My Life Matters (EMLM)",
  "source_url": "{school_website_url}",
  "terms": [
    {{
      "academic_year": "YYYY-YYYY",
      "term_name": "Autumn | Spring | Summer | Holiday | Half Term | INSET | Closure",
      "events": [
        {{
          "start_date": "YYYY-MM-DD",
          "end_date": "YYYY-MM-DD or null",
          "time": "HH:MM or null",
          "event_text": "FULL original event description exactly as written"
        }}
      ]
    }}
  ]
}}

ABSOLUTE RULES:
- JSON ONLY
- NO markdown
- NO explanations
- NO assumptions
- NO placeholders
- NO missing data
- FAIL THE TASK IF DATA IS INCOMPLETE"""

    return prompt


@require_http_methods(["GET"])
def get_random_school_prompt(request):
    """
    GET API endpoint that returns a random school with its prompt.
    The prompt includes the school's website URL dynamically.

    URL: /api/schools/random/prompt/
    """
    # Get all schools (preferably those not yet processed)
    # First try to get schools where process=False, if none available, get any school
    schools_not_processed = School.objects.filter(process=False)

    if schools_not_processed.exists():
        schools_with_data = schools_not_processed
    else:
        # If all schools are processed, get any school
        schools_with_data = School.objects.all()

    if not schools_with_data.exists():
        return JsonResponse(
            {'error': 'No schools found in database'},
            status=404
        )

    # Get a random school
    random_school = random.choice(list(schools_with_data))

    # Update process status to True
    random_school.process = True
    random_school.save()

    # Get website URL from School model
    website_url = random_school.website
    if website_url:
        website_url = website_url.strip()
    else:
        website_url = 'https://example.com'  # Default fallback

    # Generate prompt with dynamic URL
    prompt = generate_prompt_with_url(website_url)

    # Return the response
    return JsonResponse({
        'school_id': str(random_school.urn),
        'prompt': prompt
    })


@csrf_exempt
@require_http_methods(["POST"])
def create_or_update_school_data(request):
    """
    POST API endpoint to create or update SchoolData JSON.
    If data already exists, it will update the existing JSON data.

    URL: /api/schools/data/

    Request Body (JSON):
    {
        "school_id": 100000,
        "data": {
            "key1": "value1",
            "key2": "value2",
            ...
        }
    }
    """
    try:
        # Parse JSON body
        body_data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse(
            {'error': 'Invalid JSON in request body'},
            status=400
        )

    # Validate required fields
    school_id = body_data.get('school_id')
    data = body_data.get('data')

    if school_id is None:
        return JsonResponse(
            {'error': 'school_id is required'},
            status=400
        )

    if data is None:
        return JsonResponse(
            {'error': 'data is required'},
            status=400
        )

    if not isinstance(data, dict):
        return JsonResponse(
            {'error': 'data must be a JSON object'},
            status=400
        )

    # Validate school exists
    try:
        school = School.objects.get(urn=school_id)
    except School.DoesNotExist:
        return JsonResponse(
            {'error': f'School with ID {school_id} not found'},
            status=404
        )
    except ValueError:
        return JsonResponse(
            {'error': 'Invalid school_id format. Must be an integer.'},
            status=400
        )

    # Get the most recent SchoolData for this school
    school_data = SchoolData.objects.filter(
        school=school).order_by('-created_at').first()

    if school_data:
        # Update existing data - merge with existing JSON
        existing_data = school_data.data if school_data.data else {}
        # Merge new data with existing data (new data takes precedence)
        updated_data = {**existing_data, **data}
        school_data.data = updated_data
        school_data.save()

        return JsonResponse({
            'message': 'SchoolData updated successfully',
            'school_id': str(school_id),
            'action': 'updated',
            'data': school_data.data
        }, status=200)
    else:
        # Create new SchoolData entry
        school_data = SchoolData.objects.create(
            school=school,
            data=data
        )

        return JsonResponse({
            'message': 'SchoolData created successfully',
            'school_id': str(school_id),
            'action': 'created',
            'data': school_data.data
        }, status=201)


@require_http_methods(["GET"])
def display_all_schools_data(request):
    """
    Frontend view to display all schools data in formatted JSON.
    URL: /schools/
    """
    # Get all schools with their latest SchoolData
    schools = School.objects.all().prefetch_related('school_data')

    schools_data = []
    for school in schools:
        # Get the most recent SchoolData
        school_data = SchoolData.objects.filter(
            school=school).order_by('-created_at').first()

        school_info = {
            'urn': school.urn,
            'establishment_name': school.establishment_name,
            'local_authority': school.local_authority,
            'establishment_status': school.establishment_status,
            'process': school.process,
            'website': school.website,
            'data': school_data.data if school_data else None,
            'data_created_at': school_data.created_at.isoformat() if school_data else None,
            'data_updated_at': school_data.updated_at.isoformat() if school_data else None,
        }
        schools_data.append(school_info)

    # Convert to JSON string for display
    json_data = json.dumps(schools_data, indent=2, ensure_ascii=False)

    context = {
        'schools_data': schools_data,
        'json_data': json_data,
        'json_data_js': json.dumps(schools_data),  # For JavaScript parsing
        'total_schools': len(schools_data)
    }

    return render(request, 'schools/display_data.html', context)
