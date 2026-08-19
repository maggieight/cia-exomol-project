from django.http import Http404
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.template import RequestContext
from django.contrib.auth.decorators import login_required
from exomol_users.models import ExoMolUserProfile, ExoMolGroupMemberProfile
from exomol_users.forms import ExomolGroupMemberProfileForm

@login_required
def update_profile(request):
    user = request.user
    try:
        profile = user.userprofile.exomolgroupmemberprofile
    except (ExoMolUserProfile.DoesNotExist,
            ExoMolGroupMemberProfile.DoesNotExist):
        raise Http404

    form = ExomolGroupMemberProfileForm(request.POST or None,
                    request.FILES or None, instance=profile)
    if request.method == 'POST':
        if form.is_valid():
            profile = form.save(commit=False)
            profile.user = request.user
            profile.save()
            return HttpResponseRedirect('/about/group#user{:d}'
                                            .format(request.user.id))
    c = {'form': form}
    return render(request, 'pages/profile/update.html', c)
