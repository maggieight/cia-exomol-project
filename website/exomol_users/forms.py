from django.forms import ModelForm
from django.forms.models import model_to_dict, fields_for_model
from django.contrib.auth.models import User
from .models import ExoMolGroupMemberProfile

class ExomolGroupMemberProfileForm(ModelForm):
    def __init__(self, *args, **kwargs):
        instance = kwargs.pop('instance', None)
        _fields = ('first_name', 'last_name', 'email',)
        if instance is None:
            _initial = {}
        else:
            _initial = model_to_dict(instance.user, _fields)
        super().__init__(initial=_initial, instance=instance, *args, **kwargs)
        self.fields.update(fields_for_model(User, _fields))
        self.order_fields(['first_name', 'last_name', 'email', 'www',
                           'twitter_handle', 'affiliation',
                           'subscribed_to_newsletter',
                           'start_date', 'picture', 'biog'])

    class Meta:
        model = ExoMolGroupMemberProfile
        exclude = ['user', 'role', 'current',]

    def save(self, *args, **kwargs):
        user = self.instance.user
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        user.save()
        profile = super().save(*args, **kwargs)
        return profile
