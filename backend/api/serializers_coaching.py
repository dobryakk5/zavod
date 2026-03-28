from __future__ import annotations

from rest_framework import serializers


class CoachingCompetencySerializer(serializers.Serializer):
    id = serializers.CharField(max_length=128)
    name = serializers.CharField(max_length=255, allow_blank=True)
    score = serializers.IntegerField(min_value=0, max_value=100)
    startScore = serializers.IntegerField(min_value=0, max_value=100)
    color = serializers.CharField(max_length=32, allow_blank=True, required=False, default="")


class CoachingGoalCompetencyLinkSerializer(serializers.Serializer):
    competencyId = serializers.CharField(max_length=128)
    competencyName = serializers.CharField(max_length=255, allow_blank=True, required=False, default="")
    weight = serializers.FloatField(min_value=0, max_value=1)


class CoachingGoalStepSerializer(serializers.Serializer):
    id = serializers.CharField(max_length=128)
    text = serializers.CharField(max_length=500)
    done = serializers.BooleanField(default=False)
    isMilestone = serializers.BooleanField(default=False)
    milestoneNote = serializers.CharField(allow_blank=True, required=False, default="")
    doneAt = serializers.CharField(allow_blank=True, required=False, default="")
    dueDate = serializers.CharField(allow_blank=True, required=False, default="")
    goalId = serializers.CharField(max_length=128, allow_blank=True, required=False, default="")
    goalTitle = serializers.CharField(max_length=255, allow_blank=True, required=False, default="")


class CoachingGoalStepCreateSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=500)
    dueDate = serializers.CharField(allow_blank=True, required=False, default="")


class CoachingGoalStepUpdateSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=500, allow_blank=True, required=False)
    dueDate = serializers.CharField(allow_blank=True, required=False)
    done = serializers.BooleanField(required=False)


class CoachingGoalEditSerializer(serializers.Serializer):
    id = serializers.CharField(max_length=128)
    title = serializers.CharField(max_length=255, allow_blank=True)
    progress = serializers.IntegerField(min_value=0, max_value=100)
    horizon = serializers.ChoiceField(choices=("year", "quarter", "month"))
    status = serializers.ChoiceField(choices=("active", "paused", "achieved", "revised"))
    competencyLinks = CoachingGoalCompetencyLinkSerializer(many=True, required=False, default=list)
    steps = CoachingGoalStepSerializer(many=True, required=False, default=list)
    createdAt = serializers.CharField(allow_blank=True, required=False, default="")


class CoachingMilestoneSerializer(serializers.Serializer):
    id = serializers.CharField(max_length=128)
    clientId = serializers.IntegerField()
    goalId = serializers.CharField(max_length=128, allow_blank=True, required=False, default="")
    text = serializers.CharField(max_length=500)
    note = serializers.CharField(allow_blank=True, required=False, default="")
    createdAt = serializers.CharField()


class CoachingMilestoneCreateSerializer(serializers.Serializer):
    goalId = serializers.CharField(max_length=128, allow_blank=True, required=False, default="")
    text = serializers.CharField(max_length=500)
    note = serializers.CharField(allow_blank=True, required=False, default="")


class CoachingSessionSerializer(serializers.Serializer):
    id = serializers.CharField(max_length=128)
    clientId = serializers.IntegerField()
    number = serializers.IntegerField(min_value=1)
    date = serializers.CharField()
    notes = serializers.CharField(allow_blank=True, required=False, default="")
    coachNotes = serializers.CharField(allow_blank=True, required=False, default="")
    status = serializers.ChoiceField(choices=("draft", "done"), required=False, default="done")


class CoachingSessionCreateSerializer(serializers.Serializer):
    date = serializers.CharField(required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    coachNotes = serializers.CharField(required=False, allow_blank=True, default="")


class CoachingSessionUpdateSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True)
    coachNotes = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=("draft", "done"), required=False)


class CoachingContactUpdateSerializer(serializers.Serializer):
    intention = serializers.CharField(required=True, allow_blank=True)


class CoachingOnboardingSerializer(serializers.Serializer):
    clientId = serializers.CharField(required=False, allow_blank=True, default="")
    intention = serializers.CharField(required=False, allow_blank=True, default="")
    wheel = serializers.ListField(required=False, default=list)
    competencies = serializers.ListField(child=serializers.CharField(), required=False, default=list)
