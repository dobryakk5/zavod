from django.db import models


class EmailAuthToken(models.Model):
    email = models.EmailField(db_index=True)
    token = models.CharField(max_length=100, unique=True, db_index=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Email auth token"
        verbose_name_plural = "Email auth tokens"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.email} ({self.expires_at.isoformat()})"
