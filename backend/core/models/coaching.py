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


class CoachGroup(models.Model):
    tenant = models.ForeignKey(
        "core.Client",
        on_delete=models.CASCADE,
        related_name="coach_groups",
    )
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=("tenant", "created_at"), name="idx_coach_group_tenant_created"),
        ]
        ordering = ("created_at", "id")

    def __str__(self) -> str:
        return f"tenant={self.tenant_id} group={self.name}"


class CoachGroupMember(models.Model):
    group = models.ForeignKey(
        "core.CoachGroup",
        on_delete=models.CASCADE,
        related_name="members",
    )
    contact_id = models.IntegerField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("group", "contact_id"),
                name="uniq_coach_group_member",
            ),
        ]
        indexes = [
            models.Index(fields=("group", "contact_id"), name="idx_coach_group_member"),
        ]
        ordering = ("created_at", "id")

    def __str__(self) -> str:
        return f"group={self.group_id} contact={self.contact_id}"


class CoachGroupTask(models.Model):
    group = models.ForeignKey(
        "core.CoachGroup",
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    text = models.CharField(max_length=500)
    due_date = models.DateField(null=True, blank=True)
    step_refs = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=("group", "created_at"), name="idx_coach_group_task"),
        ]
        ordering = ("created_at", "id")

    def __str__(self) -> str:
        return f"group={self.group_id} task={self.id}"
