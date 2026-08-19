from mezzanine.conf import register_setting

register_setting(
    name="RICHTEXT_ALLOWED_TAGS",
    append=True,
    default=('iframe',),
)

register_setting(
    name="RICHTEXT_ALLOWED_STYLES",
    append=True,
    default=('width',),
)
