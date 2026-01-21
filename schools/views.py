from django.db.models import Prefetch
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

    prompt = f"""

You are an automated academic calendar and term-date extraction engine.

INPUT - School website URL: {school_website_url}

GOAL
Extract academic calendar data from the school website.
If the school does NOT publish term dates, fall back to the official local authority
school holiday calendar for the school’s location (England).

IMPORTANT BEHAVIOUR CHANGE (DO NOT FAIL)
- If school-specific term dates are NOT found, DO NOT fail.
- Instead, identify the school’s local authority and use its official
  school term and holiday dates.
- Always return JSON output.

WEBSITE CHECK (FIRST PRIORITY)
- Check the entire school website for:
  Term Dates
  Calendar
  Parents Information
  Downloads
  Prospectus
  Newsletters
- Extract any dates found.

FALLBACK RULE (MANDATORY)
- If no term dates are published by the school:
  - Detect the school’s local authority
  - Use the official local authority term & holiday dates
  - Clearly reflect them as holidays/terms in the output

EVENT RULES
- Each event must be its own entry
- Do NOT merge events
- Do NOT guess individual school INSET days
- Use only official published dates

DATE RULES
- Convert all dates to ISO format: YYYY-MM-DD
- Date range → start_date & end_date
- Single day → end_date = null
- No weekday inference

TIME RULES
- If no time is written → time = null

OUTPUT RULES
- JSON ONLY
- NO explanations
- NO markdown
- NO comments
- NO failure responses

OUTPUT FORMAT

{{
  "school_name": "",
  "source_url": "",
  "terms": [
    {{
      "academic_year": "YYYY-YYYY",
      "term_name": "Autumn | Spring | Summer | Holiday",
      "events": [
        {{
          "start_date": "YYYY-MM-DD",
          "end_date": "YYYY-MM-DD or null",
          "time": null,
          "event_text": "Original official event description"
        }}
      ]
    }}
  ]
}}

FINAL INSTRUCTION
- ALWAYS return valid JSON
- NEVER stop execution
- NEVER say data is missing



"""

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
    schools_not_processed = School.objects.filter(
        process=True, second_scraper=False)

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
    random_school.third_scraper = True
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
def get_schools_with_invalid_data(request):
    """
    GET API endpoint that returns a random school link for a school that has process=True,
    second_scraper=False, and either no data in SchoolData or invalid calendar data.

    When a school is selected, its second_scraper status is automatically set to True.

    Invalid data means:
    - No SchoolData entries exist, OR
    - SchoolData exists but doesn't have valid calendar format (missing 'school_name' or 'terms' keys)

    URL: /api/schools/invalid-data/

    Returns:
    {
        "school_id": 100000,
        "school_name": "Example School",
        "website": "https://example.com",
        "reason": "no_data" or "invalid_data"
    }

    Or if no school found:
    {
        "error": "No school found with invalid data"
    }
    """

    # Optimize: Get all schools with process=True, second_scraper=False, and website exists
    # Filter at database level to reduce data transfer and use prefetch for related data
    schools = School.objects.filter(
        process=True,
        second_scraper=False,
        website__isnull=False
    ).exclude(website='').prefetch_related(
        Prefetch(
            'school_data',
            queryset=SchoolData.objects.order_by('-created_at'),
            to_attr='all_school_data'
        )
    )

    # Collect all schools with invalid or missing data
    valid_schools = []

    # Evaluate queryset once - this is the only database hit for schools
    schools_list = list(schools)

    for school in schools_list:
        # Use prefetched data - get the first (latest) one
        school_data_list = getattr(school, 'all_school_data', [])
        school_data = school_data_list[0] if school_data_list else None

        # Check if school has no data or invalid data
        has_invalid_data = False
        reason = None

        if not school_data:
            # No SchoolData exists
            has_invalid_data = True
            reason = "no_data"
        else:
            # Check if data is valid calendar format
            data = school_data.data
            if not isinstance(data, dict):
                # Data is not a dictionary
                has_invalid_data = True
                reason = "invalid_data"
            elif 'school_name' not in data or 'terms' not in data:
                # Data doesn't have required calendar format keys
                has_invalid_data = True
                reason = "invalid_data"

        # Collect schools with invalid or missing data
        if has_invalid_data:
            valid_schools.append({
                'school': school,
                'reason': reason
            })

    # Return random school if available
    if valid_schools:
        selected = random.choice(valid_schools)
        school = selected['school']

        # Update second_scraper status to True when school is selected
        school.second_scraper = True
        school.save(update_fields=['second_scraper'])

        return JsonResponse({
            'school_id': school.urn,
            'school_name': school.establishment_name,
            'website': school.website.strip(),
            'reason': selected['reason']
        })

    # No school found
    return JsonResponse({
        'error': 'No school found with invalid data'
    }, status=404)


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
