from django.db import models
from django.utils import timezone


class OAuthToken(models.Model):
    session_id    = models.CharField(max_length=64, unique=True, db_index=True)
    access_token  = models.TextField()
    refresh_token = models.TextField(default='')
    created_at    = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'oauth_token'
