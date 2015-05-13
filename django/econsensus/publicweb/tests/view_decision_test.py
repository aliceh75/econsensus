import lxml.html
from django.core.urlresolvers import reverse
from notification import models as notification
from publicweb.tests.decision_test_case import DecisionTestCase
from publicweb.models import Feedback, Decision
from signals.management import DECISION_CHANGE


# TODO: Check that POSTs save correct data and redirects work
class ViewDecisionTest(DecisionTestCase):
    def test_view_decision(self):
        decision = self.create_and_return_decision()
        response = self.client.get(reverse('publicweb_decision_detail', args=[decision.id]))
        self.assertContains(response, u"Proposal")
        self.assertContains(response, decision.description)

    def test_view_feedback(self):
        decision = self.create_and_return_decision()
        feedback = Feedback(description='test feedback',
                          decision=decision,
                          author=self.user)
        feedback.save()
        response = self.client.get(reverse('publicweb_feedback_detail', args=[feedback.id]))
        self.assertContains(response, u"Feedback")
        self.assertContains(response, feedback.description)

    def test_load_decision_snippet(self):
        decision = self.create_and_return_decision(status=Decision.DECISION_STATUS)
        response = self.client.get(reverse('publicweb_decision_snippet_detail', args=[decision.id]))       
        self.assertTrue(response.content.strip().startswith('<div id="decision_snippet_envelope">'))
        self.assertContains(response, u'<div id="decision_detail" class="decision">')

    def test_load_form_snippet(self):
        form_fields = set(['status', 'review_date', 'description', 'tags', 'people', 'effective_date', 'csrfmiddlewaretoken', 'decided_date'])
        decision = self.create_and_return_decision(status=Decision.DECISION_STATUS)
        response = self.client.get(reverse('publicweb_decision_snippet_update', args=[decision.id]))
        self.assertTrue(response.content.strip().startswith('<form action="#" method="post" id="decision_update_form" class="decision">'))
        form_data = self.get_form_values_from_response(response, 1)
         
        self.assertTrue(form_fields.issubset(set(form_data.keys())))

    def test_load_decision_form(self):
        form_fields = set(['status', 'review_date', 'description', 'tags', 'people', 'effective_date', 'csrfmiddlewaretoken', 'decided_date'])
        decision = self.create_and_return_decision(status=Decision.DECISION_STATUS)
        response = self.client.get(reverse('publicweb_decision_update', args=[decision.id]))
        response_content = response.content.strip()
        self.assertFalse(response_content.startswith('<form action="#" method="post" class="edit_decision_form">'))
        self.assertTrue(response_content.startswith('<!DOCTYPE html'))
        self.assertContains(response, u"Update Decision #%s" % decision.id)

        form_data = self.get_form_values_from_response(response, 1)
        self.assertTrue(form_fields.issubset(set(form_data.keys())))

    def test_decision_detail_contains_watch_toggle_link(self):
        decision = self.create_and_return_decision()
        doc = self._get_document('publicweb_decision_detail', decision.id)
        elements = doc.cssselect('div#decision_detail a.watch.toggle')
        self.assertEquals(len(elements), 1)

    def test_view_page_watch_toggle_is_unwatched_when_no_user_is_watching(self):
        decision = self.create_and_return_decision()
        doc = self._get_document('publicweb_decision_detail', decision.id)
        elements = doc.cssselect('div#decision_detail a.watch.toggle.unwatched')
        self.assertEquals(len(elements), 1)

    def test_view_page_watch_toggle_is_watched_when_the_current_user_is_watching(self):
        decision = self.create_and_return_decision()
        notification.observe(decision, self.user, DECISION_CHANGE)
        doc = self._get_document('publicweb_decision_detail', decision.id)
        elements = doc.cssselect('div#decision_detail a.watch.toggle.watched')
        self.assertEquals(len(elements), 1)

    def test_view_page_watch_toggle_is_unwatched_when_users_other_than_current_are_watching(self):
        decision = self.create_and_return_decision()
        notification.observe(decision, self.charlie, DECISION_CHANGE)
        doc = self._get_document('publicweb_decision_detail', decision.id)
        elements = doc.cssselect('div#decision_detail a.watch.toggle.unwatched')
        self.assertEquals(len(elements), 1)

    def test_following_unwatched_watch_toggle_adds_watcher(self):
        decision = self.create_and_return_decision()
        doc = self._get_document('publicweb_decision_detail', decision.id)
        elements = doc.cssselect('div#decision_detail a.watch.toggle')
        url = elements[0].get('href')
        self.assertEquals(len(decision.watchers.all()), 0)
        self.client.get(url)
        self.assertEquals(len(decision.watchers.all()), 1)

    def test_following_watched_watch_toggle_removes_watcher(self):
        decision = self.create_and_return_decision()
        notification.observe(decision, self.user, DECISION_CHANGE)
        doc = self._get_document('publicweb_decision_detail', decision.id)
        elements = doc.cssselect('div#decision_detail a.watch.toggle')
        url = elements[0].get('href')
        self.assertEquals(len(decision.watchers.all()), 1)
        self.client.get(url)
        self.assertEquals(len(decision.watchers.all()), 0)

    def _get_document(self, view, *args):
        """Fetch the given view, and return the result parsed with lxml"""
        response = self.client.get(reverse(view, args=args))
        return lxml.html.fromstring(str(response))
