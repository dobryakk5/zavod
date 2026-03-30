import uuid

from django.db import models
from django.utils import timezone


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


class CoachingGoal(models.Model):
    TYPE_PERSONAL = "personal"
    TYPE_GROUP = "group"
    TYPE_CHOICES = (
        (TYPE_PERSONAL, "Personal"),
        (TYPE_GROUP, "Group"),
    )

    HORIZON_YEAR = "year"
    HORIZON_QUARTER = "quarter"
    HORIZON_MONTH = "month"
    HORIZON_CHOICES = (
        (HORIZON_YEAR, "Year"),
        (HORIZON_QUARTER, "Quarter"),
        (HORIZON_MONTH, "Month"),
    )

    STATUS_ACTIVE = "active"
    STATUS_PAUSED = "paused"
    STATUS_ACHIEVED = "achieved"
    STATUS_REVISED = "revised"
    STATUS_CHOICES = (
        (STATUS_ACTIVE, "Active"),
        (STATUS_PAUSED, "Paused"),
        (STATUS_ACHIEVED, "Achieved"),
        (STATUS_REVISED, "Revised"),
    )

    profile = models.ForeignKey(
        "core.ContactCoachingProfile",
        on_delete=models.CASCADE,
        related_name="goal_rows",
    )
    public_id = models.CharField(max_length=128)
    goal_type = models.CharField(max_length=16, choices=TYPE_CHOICES, default=TYPE_PERSONAL)
    title = models.CharField(max_length=255, blank=True, default="")
    progress = models.PositiveSmallIntegerField(default=0)
    horizon = models.CharField(max_length=16, choices=HORIZON_CHOICES, default=HORIZON_QUARTER)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    sort_order = models.IntegerField(default=0)
    group = models.ForeignKey(
        "core.CoachGroup",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="coaching_goals",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("profile", "public_id"),
                name="uniq_coaching_goal_profile_public_id",
            ),
        ]
        indexes = [
            models.Index(fields=("profile", "sort_order", "id"), name="idx_coach_goal_profile_sort"),
            models.Index(fields=("profile", "goal_type"), name="idx_coach_goal_profile_type"),
            models.Index(fields=("group",), name="idx_coach_goal_group"),
        ]
        ordering = ("sort_order", "created_at", "id")

    def __str__(self) -> str:
        return f"profile={self.profile_id} goal={self.public_id}"


class CoachingGoalCompetency(models.Model):
    goal = models.ForeignKey(
        "core.CoachingGoal",
        on_delete=models.CASCADE,
        related_name="competency_links",
    )
    competency_id = models.CharField(max_length=128)
    competency_name = models.CharField(max_length=255, blank=True, default="")
    weight = models.FloatField(default=0)
    sort_order = models.IntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=("goal", "sort_order", "id"), name="idx_coach_goal_comp_goal_sort"),
        ]
        ordering = ("sort_order", "id")

    def __str__(self) -> str:
        return f"goal={self.goal_id} competency={self.competency_id}"


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


class InviteLink(models.Model):
    tenant = models.ForeignKey(
        "core.Client",
        on_delete=models.CASCADE,
        related_name="coach_invite_links",
    )
    contact_id = models.IntegerField(db_index=True)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=("tenant", "contact_id"), name="idx_coach_inv_tenant_contact"),
            models.Index(fields=("used_at",), name="idx_coach_invite_used_at"),
        ]
        ordering = ("-created_at", "-id")

    def __str__(self) -> str:
        return f"tenant={self.tenant_id} contact={self.contact_id} token={self.token}"
