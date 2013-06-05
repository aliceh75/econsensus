# coding: utf-8

from django.core.urlresolvers import reverse
from django.utils import translation

from lxml.html.soupparser import fromstring
from lxml.cssselect import CSSSelector

from publicweb.models import Decision
from publicweb.tests.open_consent_test_case import EconsensusFixtureTestCase

class InternationalisationTest(EconsensusFixtureTestCase):
    
    def test_all_text_translated_when_viewing_decision_list(self):
        Decision.objects.all().delete()
        self.check_all_text_translated('publicweb_item_list', args=[self.bettysorg.slug, 'decision'])

    def test_all_text_translated_when_adding_decision(self):
        self.check_all_text_translated('publicweb_decision_create', args=[self.bettysorg.slug, Decision.PROPOSAL_STATUS])

    def check_all_text_translated(self, view, args):
        old_lang = translation.get_language()
        
        self.mock_get_text_functions_for_french()
        
        translation.activate("fr")

        response = self.client.get(reverse(view, args=args), follow=True)
        html = response.content # pylint: disable=E1103
        root = fromstring(html)        
        sel = CSSSelector('*')

        for element in sel(root):
            if self.has_translatable_text(element):
                try:
                    self.assertTrue(self.contains(element.text, "XXX "), "No translation for element " + element.tag
                                    + " with text '" + element.text + "' from view '" + view + "'")
                finally:
                    translation.activate(old_lang)

    def has_translatable_text(self, element):
        if element.text is None \
            or element.text.strip() == "" \
            or element.text.strip('-') == "" \
            or "not_translated" in element.attrib.get('class', '').split(" ") \
            or element.tag == 'script' \
            or element.text.isdigit():
            return False
        else:
            return True
        
    def contains(self, string_to_search, sub_string):
        return string_to_search.find(sub_string) > -1
        
    # adapted from
    # http://www.technomancy.org/python/django-i18n-test-translation-by-manually-setting-translations/
    def mock_get_text_functions_for_french(self):
        # A decorator function that just adds 'XXX ' to the front of all strings
        def wrap_with_xxx(func):
            def new_func(*args, **kwargs):
                output = func(*args, **kwargs)
                return "XXX "+output
            return new_func

        old_lang = translation.get_language()
        # Activate french, so that if the fr files haven't been loaded, they will be loaded now.
        translation.activate("fr")
         
        french_translation = translation.trans_real._active.value
         
        # wrap the ugettext and ungettext functions so that 'XXX ' will prefix each translation
        french_translation.ugettext = wrap_with_xxx(french_translation.ugettext)
        french_translation.ungettext = wrap_with_xxx(french_translation.ungettext)
         
        # Turn back on our old translations
        translation.activate(old_lang)
        del old_lang
