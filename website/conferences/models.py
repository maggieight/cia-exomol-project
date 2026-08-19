from django.db import models

class Conference(models.Model):

    title = models.CharField(max_length=200)
    short_title = models.CharField(max_length=20)
    start_date = models.DateField()
    end_date = models.DateField()

    def __str__(self):
        return '{} ({})'.format(self.title, self.short_title)

class Presentation(models.Model):

    conference = models.ForeignKey(Conference, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    first_names = models.CharField(max_length=200)
    surname = models.CharField(max_length=100)
    email = models.EmailField()
    organisation = models.CharField(max_length=200)
    abstract_title = models.CharField(max_length=1000)
    abstract_html = models.TextField()
    presentation_filename = models.CharField(max_length=200, blank=True,
                                             null=True)

    def __str__(self):
        return self.title
