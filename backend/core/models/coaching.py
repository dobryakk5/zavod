from django.db import models


class ContactCoachingProfile(models.Model):
    tenant = models.ForeignKey(
        "core.Client",
        on_delete=models.CASCADE,
        related_name="contact_coaching_profiles",
    )
    contact_id = models.IntegerField(db_index=True)
    intention = models.TextField(blank=True, default="")
    wheel = models.JSONField(default=list, blank=True)
    competencies = models.JSONField(default=list, blank=True)
    goals = models.JSONField(default=list, blank=True)
    tasks = models.JSONField(default=list, blank=True)
    milestones = models.JSONField(default=list, blank=True)
    sessions = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("tenant", "contact_id"),
                name="uniq_contact_coaching_profile",
            ),
        ]
        indexes = [
            models.Index(fields=("tenant", "contact_id"), name="idx_contact_coaching_profile"),
        ]
        ordering = ("tenant_id", "contact_id", "id")

    def __str__(self) -> str:
        return f"tenant={self.tenant_id} contact={self.contact_id}"
