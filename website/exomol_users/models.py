from django.db import models
from mezzanine.core.fields import RichTextField

class ExoMolUserProfile(models.Model):
    user = models.OneToOneField('auth.user', related_name='userprofile',
                                on_delete=models.CASCADE)
    www = models.URLField(null=True, blank=True, verbose_name='website')
    affiliation = models.CharField(max_length=200,null=True,blank=True)
    subscribed_to_newsletter = models.BooleanField(default=True)

    def __str__(self):
        return '{:s} {:s}'.format(self.user.first_name, self.user.last_name)

    class Meta:
        verbose_name = 'ExoMol user profile'


class ExoMolGroupMemberProfile(ExoMolUserProfile):

    EXOMOL_GROUP_MEMBER_ROLES = [
        (0, 'Principal Investigator'),
        (1, 'Project Manager'),
        (2, ''),
        (3, 'PhD student'),
        (4, 'MSc student'),
    ]

    twitter_handle = models.CharField(max_length=15, null=True, blank=True,
            help_text='Maximum of 15 characters, omit the leading @')

    start_date = models.DateField()
    role = models.IntegerField(choices=EXOMOL_GROUP_MEMBER_ROLES, default=2,
                               null=True, blank=True)
    picture = models.ImageField(upload_to='uploads/profile-pics',
                                null=True, blank=True)
    current = models.BooleanField(default=True)
    biog = RichTextField(null=True, blank=True)

    class Meta:
        verbose_name = 'ExoMol group member profile'
    
