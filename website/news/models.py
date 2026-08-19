from django.db import models
from mezzanine.core.models import RichText
from data.models import DataSet

class News(RichText):
    headline = models.TextField()
    date = models.DateField()
    important = models.BooleanField(default=False)

    class Meta:
        ordering = ['-date']
        verbose_name_plural = 'news items'

    def __str__(self):
        return '{}: {}'.format(self.date.strftime('%d %b %Y'), self.headline)


class UpdateAnnouncement(RichText):
    headline = models.TextField()
    date = models.DateField()
    dataset = models.ForeignKey(DataSet, on_delete=models.CASCADE)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return '{}: {}'.format(self.date.strftime('%d %b %Y'), self.headline)
