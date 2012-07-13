#Configuration for django-livesettings.
#http://django-livesettings.readthedocs.org

from livesettings import config_register, ConfigurationGroup, StringValue, \
    BooleanValue, PasswordValue, IntegerValue
from django.utils.translation import ugettext_lazy as _

# First, setup a grup to hold all our possible configs
POSTBYMAIL_GROUP = ConfigurationGroup(
    'PostByEmail',               # key: internal name of the group to be created
    _('Post By Email Settings'),  # name: verbose name which can be automatically translated
    ordering=0             # ordering: order of group in the list (default is 1)
    )

# Now, add our number of images to display value
# If a user doesn't enter a value, default to 5
config_register(StringValue(
    POSTBYMAIL_GROUP,           # group: object of ConfigurationGroup created above
        'USERNAME',      # key:   internal name of the configuration value to be created
        description = _('Username'),              # label for the value
        help_text = _("Enter the Username used to access the email account."),  # help text
        ordering = 0
    ))

config_register(PasswordValue(
    POSTBYMAIL_GROUP,
        'PASSWORD',
        description='Password',
        help_text='Enter the password to access this mail account.',
        render_value=True,
        ordering = 1
    ))

config_register(StringValue(
    POSTBYMAIL_GROUP,
        'SERVER',
        description=_("Server"),
        help_text=_("Enter the url of the mail server."),
        ordering = 2

    ))

config_register(IntegerValue(
    POSTBYMAIL_GROUP,
        'PORT',
        description=_("Port"),
        help_text=_("Enter the port number of the mail server."),
        ordering = 3
    ))

config_register(BooleanValue(
    POSTBYMAIL_GROUP,
        'SSL_ENABLED',
        description=_("SSL Enabled"),
        help_text=_("Check to enable SSL transfer"),
        default=False,
        ordering = 4
    ))
