from django.db import models


class School(models.Model):
    """
    Model to store UK schools data with core key fields.
    """
    urn = models.IntegerField(
        primary_key=True,
        unique=True,
        help_text="Unique identifier for each school"
    )
    establishment_name = models.CharField(
        max_length=255,
        help_text="Name of the school establishment"
    )
    local_authority = models.CharField(
        max_length=255,
        help_text="Local authority name (e.g., Camden, City of London)"
    )
    establishment_status = models.CharField(
        max_length=255,
        help_text="Status of the establishment"
    )
    process = models.BooleanField(
        default=False,
        help_text="Process status for the school"
    )
    website = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="School website URL"
    )
    second_scraper = models.BooleanField(
        default=False,
        help_text="Second scraper status for the school"
    )

    class Meta:
        ordering = ['establishment_name']
        indexes = [
            models.Index(fields=['urn']),
            models.Index(fields=['local_authority']),
            models.Index(fields=['establishment_status']),
        ]

    def __str__(self):
        return f"{self.establishment_name} ({self.urn})"


class SchoolData(models.Model):
    """
    Model to store school data in JSON format, related to School.
    """
    school = models.ForeignKey(
        School,
        on_delete=models.CASCADE,
        related_name='school_data',
        help_text="Related school"
    )
    data = models.JSONField(
        help_text="JSON data related to the school"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when this data was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when this data was last updated"
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['school', '-created_at']),
        ]

    def __str__(self):
        return f"Data for {self.school.establishment_name} ({self.school.urn})"
