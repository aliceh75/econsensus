#pylint: disable=E1102
#config import is unused but required here for livesettings
import config  # pylint: disable=W0611
import re

from notification import models as notification

from django.db import models
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.translation import ugettext_lazy as _
from django.utils.translation import ugettext_noop
from django.contrib.auth.models import User
from django.contrib.comments.models import Comment
from django.contrib.contenttypes import generic
from django.contrib.contenttypes.models import ContentType
from django.dispatch import receiver
from django.conf import settings
from django.contrib.sites.models import Site
from django.db.models import Count

from tagging.fields import TagField
from organizations.models import Organization
from managers import DecisionManager

from custom_notification.utils import send_observation_notices_for

# Ideally django-tinymce should be patched
# http://south.aeracode.org/wiki/MyFieldsDontWork
# http://code.google.com/p/django-tinymce/issues/detail?id=80
# TODO: Status codes could possibly be harvested off into its
# own class with accessor methods to return values.

from south.modelsinspector import add_introspection_rules
from signals.management import FEEDBACK_NEW, FEEDBACK_CHANGE, COMMENT_CHANGE,\
    COMMENT_NEW, DECISION_CHANGE, DECISION_NEW

add_introspection_rules([], ["^tagging\.fields\.TagField"])

STANDARD_SENDING_HEADERS = {'Precedence': 'bulk', 'Auto-Submitted': 'auto-generated'}


class Decision(models.Model):

    TAGS_HELP_FIELD_TEXT = "Enter a list of tags separated by spaces."
    DISCUSSION_STATUS = 'discussion'
    PROPOSAL_STATUS = 'proposal'
    DECISION_STATUS = 'decision'
    ARCHIVED_STATUS = 'archived'

    STATUS_CHOICES = (
                  (DISCUSSION_STATUS, _('discussion')),
                  (PROPOSAL_STATUS, _('proposal')),
                  (DECISION_STATUS, _('decision')),
                  (ARCHIVED_STATUS, _('archived')),
                  )

    DEFAULT_SIZE = 140

    #User entered fields
    description = models.TextField(verbose_name=_('Description'))
    decided_date = models.DateField(null=True, blank=True,
        verbose_name=_('Decided Date'))
    effective_date = models.DateField(null=True, blank=True,
        verbose_name=_('Effective Date'))
    review_date = models.DateField(null=True, blank=True,
        verbose_name=_('Review Date'))
    expiry_date = models.DateField(null=True, blank=True,
        verbose_name=_('Expiry Date'))
    deadline = models.DateField(null=True, blank=True,
        verbose_name=_('Deadline'))
    archived_date = models.DateField(null=True, blank=True,
        verbose_name=_('Archived Date'))
    budget = models.CharField(blank=True, max_length=255,
        verbose_name=_('Budget/Resources'))
    people = models.CharField(max_length=255, null=True, blank=True)
    meeting_people = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(choices=STATUS_CHOICES,
                                 default=PROPOSAL_STATUS,
                                 max_length=10)
    tags = TagField(null=True, blank=True, editable=True,
                    help_text=TAGS_HELP_FIELD_TEXT)
    organization = models.ForeignKey(Organization)
    #admin stuff
    author = models.ForeignKey(User, blank=True, null=True, editable=False, related_name="%(app_label)s_%(class)s_authored")
    editor = models.ForeignKey(User, blank=True, null=True, editable=False, related_name="%(app_label)s_%(class)s_edited")
    last_modified = models.DateTimeField(null=True, auto_now_add=True, verbose_name=_('Last Modified'))
    last_status = models.CharField(choices=STATUS_CHOICES,
                                 default="new",
                                 max_length=10, editable=False)

    watchers = generic.GenericRelation(notification.ObservedItem)

    #Autocompleted fields
    #should use editable=False?
    excerpt = models.CharField(verbose_name=_('Excerpt'), max_length=255, blank=True)
    creation = models.DateField(null=True, auto_now_add=True,
        verbose_name=_('Creation'))

    objects = DecisionManager()

    # Fields that'll trigger last_modified update upon change
    TRIGGER_FIELDS = ('description', 'decided_date', 'effective_date', 'review_date',
              'expiry_date', 'deadline', 'archived_date', 'budget', 'people',
              'meeting_people', 'status', 'excerpt', 'creation')

    def __init__(self, *args, **kwargs):
        # Unpersisted flag for suppressing notifications at save time
        self.minor_edit = False

        super(Decision, self).__init__(*args, **kwargs)

    #methods
    def unresolvedfeedback(self):
        answer = _("No")
        linked_feedback = self.feedback_set.all()
        for thisfeedback in linked_feedback:
            if (not thisfeedback.resolved):

                answer = _("Yes")
                break

        return answer

    unresolvedfeedback.short_description = _("Unresolved Feedback")

    def feedbackcount(self):
        return self.feedback_set.all().count()

    feedbackcount.short_description = _("Feedback")

    def _get_excerpt(self):
        description = strip_tags(self.description)
        match = re.search("\.|\\r|\\n", description)
        position = self.DEFAULT_SIZE
        if match:
            start = match.start()
            if start < position:
                position = start
        return description[:position]

    def __unicode__(self):
        return self.excerpt

    @classmethod
    def get_fields(cls):
        return cls._meta.fields

    @models.permalink
    def get_absolute_url(self):
        return ('publicweb_item_detail', [self.id])

    def get_email(self):
        """
        Generates an email address based on the Decision's organization
        and settings.DEFAULT_FROM_EMAIL
        """
        default_from_email = settings.DEFAULT_FROM_EMAIL
        return re.sub('\w+@', "%s@" % self.organization.slug, default_from_email)

    def get_feedback_statistics(self):
        statistics = dict([(unicode(x),0) for x in Feedback.rating_names])
        raw_data = self.feedback_set.values('rating').annotate(Count('rating'))
        for x in raw_data:
            key = unicode(Feedback.rating_names[x['rating']])
            statistics[key] = x['rating__count']
        return statistics

    def get_message_id(self):
        """
        Generates a message id that can be used in email headers
        """
        return "<decision-%s@%s>" % (self.id, Site.objects.get_current().domain)

    def _update_notification_for_org_change(self):
        self.watchers.all().delete()
        org_users = self.organization.users.all()
        for user in org_users:
            notification.observe(self, user, 'decision_change')
        for feedback in self.feedback_set.all():
            feedback.watchers.all().delete()
            for user in org_users:
                notification.observe(feedback, user, 'feedback_change')
            for comment in feedback.comments.all():
                comment_watchers = notification.ObservedItem.objects.filter(
                    content_type = ContentType.objects.get(name='comment'),
                    object_id = comment.id)
                comment_watchers.delete()
                for user in org_users:
                    notification.observe(comment, user, 'comment_change')

    def _send_change_notifications(self):
        headers = {'Message-ID' : self.get_message_id()}
        headers.update(STANDARD_SENDING_HEADERS)
        send_observation_notices_for(self, headers=headers, from_email=self.get_email())

    def _is_same(self, other):
        for field in self.TRIGGER_FIELDS:
            if getattr(self, field) != getattr(other, field):
                return False
        return True

    def _update_last_modified(self):
        self.last_modified = timezone.now()

    def save(self, *args, **kwargs):
        self.excerpt = self._get_excerpt()
        if self.id:
            prev = self.__class__.objects.get(id=self.id)
            if prev.organization.id != self.organization.id:
                self._update_notification_for_org_change()
            if not self.minor_edit:
                self._send_change_notifications()
            if not self._is_same(prev):
                self._update_last_modified()
        super(Decision, self).save(*args, **kwargs)

    def note_external_modification(self):
        """
        Called when some other object is saved (e.g. a comment
        and we want this to be reflected in this decision's
        "last modified" date.
        """
        self._update_last_modified()
        # Go to superclass to avoid sending email notifications
        super(Decision, self).save()

class Feedback(models.Model):

    rating_names = (ugettext_noop('question'),
                    ugettext_noop('danger'),
                    ugettext_noop('concerns'),
                    ugettext_noop('consent'),
                    ugettext_noop('comment'))

    RATING_CHOICES = [(rating_names.index(x), x) for x in rating_names]

    QUESTION_STATUS = rating_names.index('question')
    DANGER_STATUS = rating_names.index('danger')
    CONCERNS_STATUS = rating_names.index('concerns')
    CONSENT_STATUS = rating_names.index('consent')
    COMMENT_STATUS = rating_names.index('comment')

    description = models.TextField(verbose_name=_('Description'), null=True, blank=True)
    author = models.ForeignKey(User, blank=True, null=True, editable=False, related_name="%(app_label)s_%(class)s_related")
    editor = models.ForeignKey(User, blank=True, null=True, editable=False, related_name="%(app_label)s_%(class)s_edited")
    decision = models.ForeignKey('Decision', verbose_name=_('Decision'))
    resolved = models.BooleanField(verbose_name=_('Resolved'))
    rating = models.IntegerField(choices=RATING_CHOICES, default=COMMENT_STATUS)

    watchers = generic.GenericRelation(notification.ObservedItem)
    comments = generic.GenericRelation(Comment, object_id_field='object_pk')

    def __init__(self, *args, **kwargs):
        # Unpersisted flag for suppressing notifications at save time
        self.minor_edit = False

        super(Feedback, self).__init__(*args, **kwargs)

    @models.permalink
    def get_absolute_url(self):
        return ('publicweb_feedback_detail', [self.id])

    @models.permalink
    def get_parent_url(self):
        return ('publicweb_item_detail', [self.decision.id])

    def get_author_name(self):
        if hasattr(self.author, 'username') and self.author.username:
            return self.author.username
        else:
            return "An Anonymous Contributor"

    def get_message_id(self):
        """
        Generates a message id that can be used in email headers
        """
        return "<feedback-%s@%s>" % (self.id, Site.objects.get_current().domain)

# The indexes are numeric because the notification levels are cumulative
# This enables us to do if notification_level >= number
NO_NOTIFICATIONS = 0
NO_NOTIFICATIONS_TEXT = _("1. Silent")
MAIN_ITEMS_NOTIFICATIONS_ONLY = 1
MAIN_ITEMS_NOTIFICATIONS_ONLY_TEXT = _("2. Major events")
FEEDBACK_ADDED_NOTIFICATIONS = 2
FEEDBACK_ADDED_NOTIFICATIONS_TEXT = _("3. Feedback and changes")
FEEDBACK_MAJOR_CHANGES = 3
FEEDBACK_MAJOR_CHANGES_TEXT = _("4. Full discussion")
MINOR_CHANGES_NOTIFICATIONS = 4
MINOR_CHANGES_NOTIFICATIONS_TEXT = _("5. Everything, even minor changes")
NOTIFICATION_LEVELS = (
          (NO_NOTIFICATIONS, NO_NOTIFICATIONS_TEXT),
          (MAIN_ITEMS_NOTIFICATIONS_ONLY, MAIN_ITEMS_NOTIFICATIONS_ONLY_TEXT),
          (FEEDBACK_ADDED_NOTIFICATIONS, FEEDBACK_ADDED_NOTIFICATIONS_TEXT),
          (FEEDBACK_MAJOR_CHANGES, FEEDBACK_MAJOR_CHANGES_TEXT),
          (MINOR_CHANGES_NOTIFICATIONS, MINOR_CHANGES_NOTIFICATIONS_TEXT)        
                      )

class NotificationSettings(models.Model):
    user = models.ForeignKey(User)
    organization = models.ForeignKey(Organization)
    notification_level = models.IntegerField(choices=NOTIFICATION_LEVELS,
        default=MAIN_ITEMS_NOTIFICATIONS_ONLY,
        help_text=_("Levels are cumulative, so if, for example, you choose to "
            "get notifications of replies to feedback, you will get "
            "notifications of all changes to main items as well."))
    
    class Meta:
        unique_together = ('user', 'organization')

class OrganizationSettings(models.Model):
    organization = models.OneToOneField(Organization)
    default_notification_level = models.IntegerField(choices=NOTIFICATION_LEVELS,
        help_text=_("Levels are cumulative, so if, for example, you choose to "
            "get notifications of replies to feedback, you will get "
            "notifications of all changes to main items as well."))

@receiver(models.signals.post_save, sender=Decision, dispatch_uid="publicweb.models.decision_signal_handler")
def decision_signal_handler(sender, **kwargs):
    """
    All users except the author will get a notification informing them of
    new content.
    All users are made observers of the decision.
    """
    instance = kwargs.get('instance')
    headers = {'Message-ID' : instance.get_message_id()}
    headers.update(STANDARD_SENDING_HEADERS)
    if kwargs.get('created', True):
        active_users = instance.organization.users.filter(is_active=True)
        all_but_author = active_users.exclude(username=instance.author)
        for user in active_users:
            notification.observe(instance, user, DECISION_CHANGE)
        extra_context = {}
        extra_context.update({"observed": instance})
        notification.send(all_but_author, DECISION_NEW, extra_context, headers, from_email=instance.get_email())

@receiver(models.signals.post_save, sender=Feedback, dispatch_uid="publicweb.models.feedback_signal_handler")
def feedback_signal_handler(sender, **kwargs):
    """
    All watchers of a decision will get a notification informing them of
    new feedback.
    All watchers become observers of the feedback.
    """
    instance = kwargs.get('instance')
    headers = {'Message-ID' : instance.get_message_id()}
    headers.update(STANDARD_SENDING_HEADERS)
    headers.update({'In-Reply-To' : instance.decision.get_message_id()})

    instance.decision.note_external_modification()

    if kwargs.get('created', True):
        #author gets notified if the feedback is edited.
        notification.observe(instance, instance.author, FEEDBACK_CHANGE)

        #All watchers of parent get notified of new feedback.
        all_observed_items_but_authors = list(instance.decision.watchers.exclude(user=instance.author))
        observer_list = [x.user for x in all_observed_items_but_authors]
        extra_context = dict({"observed": instance})
        notification.send(observer_list, FEEDBACK_NEW, extra_context, headers, from_email=instance.decision.get_email())
    else:
        # An edit by someone other than the author never counts as minor
        if instance.author != instance.editor or not instance.minor_edit:
            send_observation_notices_for(instance, headers=headers, from_email=instance.decision.get_email())

@receiver(models.signals.post_save, sender=Comment, dispatch_uid="publicweb.models.comment_signal_handler")
def comment_signal_handler(sender, **kwargs):
    """
    All watchers of a decision will get a notification informing them of
    new comment.
    All watchers become observers of the comment.
    """
    instance = kwargs.get('instance')
    headers = {'Message-ID' : "comment-%s@%s" % (instance.id, Site.objects.get_current().domain)}
    headers.update(STANDARD_SENDING_HEADERS)
    headers.update({'In-Reply-To' : instance.content_object.get_message_id()})

    instance.content_object.decision.note_external_modification()

    if kwargs.get('created', True):
        # Creator gets notified if the comment is edited.
        notification.observe(instance, instance.user, COMMENT_CHANGE)

        #All watchers of parent get notified of new comment.
        all_observed_items_but_author = list(instance.content_object.decision.watchers.exclude(user=instance.user))
        observer_list = [x.user for x in all_observed_items_but_author]
        extra_context = dict({"observed": instance})
        notification.send(observer_list, COMMENT_NEW, extra_context, headers, from_email=instance.content_object.decision.get_email())
    else:
        send_observation_notices_for(instance, headers=headers, from_email=instance.content_object.decision.get_email())

