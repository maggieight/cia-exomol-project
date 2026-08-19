from mezzanine.pages.page_processors import processor_for
from exomol_users.models import ExoMolGroupMemberProfile

NEWS_ITEMS_SHOWN = 5

@processor_for('about/group')
def group_member_profiles(request, page):
    current_group_member_profiles = ExoMolGroupMemberProfile.objects\
                .filter(current=True).order_by('role')
    former_group_member_profiles = ExoMolGroupMemberProfile.objects\
                .filter(current=False).order_by('role')
    return {'current_group_member_profiles': current_group_member_profiles,
            'former_group_member_profiles': former_group_member_profiles}
