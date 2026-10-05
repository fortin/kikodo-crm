import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from crm.models import (
    Company,
    NewsletterEdition,
    NewsletterPlan,
    NewsletterTemplate,
    NewsletterTemplateSection,
    Signal,
)


class NewsletterTemplateDefaultTests(TestCase):
    def test_saving_default_unsets_previous_default(self):
        first = NewsletterTemplate.objects.create(name="Weekly", is_default=True)
        second = NewsletterTemplate.objects.create(name="Digest", is_default=True)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.is_default)
        self.assertTrue(second.is_default)
        self.assertEqual(NewsletterTemplate.get_default(), second)


class NewsletterIssueCreateTemplateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("editor", password="pass")
        self.client.login(username="editor", password="pass")
        self.create_url = reverse("crm:newsletter_issue_create")

    def _template_with_section(self, name, heading, is_default=False):
        template = NewsletterTemplate.objects.create(name=name, is_default=is_default)
        NewsletterTemplateSection.objects.create(
            template=template,
            order=1,
            heading=heading,
            body_markdown="Hello",
        )
        return template

    def test_create_without_templates_shows_blank_form(self):
        response = self.client.get(self.create_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "crm/newsletter_issue_form.html")
        self.assertNotContains(response, "Choose a template")

    def test_create_with_templates_and_no_default_shows_picker(self):
        self._template_with_section("Weekly", "Intro")
        response = self.client.get(self.create_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "crm/newsletter_issue_choose_template.html")
        self.assertContains(response, "Choose a template")
        self.assertContains(response, "Weekly")

    def test_create_with_default_template_skips_picker_and_copies_sections(self):
        template = self._template_with_section("Weekly", "Intro", is_default=True)
        response = self.client.get(self.create_url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "crm/newsletter_issue_form.html")
        self.assertContains(response, "Creating from template")
        self.assertContains(response, "Intro")
        self.assertEqual(response.context["from_template"], template)

    def test_explicit_from_template_overrides_default(self):
        self._template_with_section("Weekly", "Intro", is_default=True)
        other = self._template_with_section("Digest", "Roundup")
        response = self.client.get(self.create_url, {"from_template": other.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Roundup")
        self.assertNotContains(response, "Intro")

    def test_blank_skips_default_template(self):
        self._template_with_section("Weekly", "Intro", is_default=True)
        response = self.client.get(self.create_url, {"blank": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "crm/newsletter_issue_form.html")
        self.assertNotContains(response, "Creating from template")
        self.assertNotContains(response, "Intro")

    def test_select_template_redirects_to_create_form(self):
        template = self._template_with_section("Weekly", "Intro")
        response = self.client.post(
            self.create_url,
            {"action": "select_template", "template_id": str(template.pk)},
        )
        self.assertRedirects(
            response,
            f"{self.create_url}?from_template={template.pk}",
        )

    def test_select_template_can_set_default(self):
        template = self._template_with_section("Weekly", "Intro")
        response = self.client.post(
            self.create_url,
            {
                "action": "select_template",
                "template_id": str(template.pk),
                "make_default": "1",
            },
        )
        self.assertRedirects(
            response,
            f"{self.create_url}?from_template={template.pk}",
        )
        template.refresh_from_db()
        self.assertTrue(template.is_default)

    def test_skip_template_opens_blank_form(self):
        self._template_with_section("Weekly", "Intro")
        response = self.client.post(
            self.create_url,
            {
                "action": "select_template",
                "template_id": "1",
                "skip_template": "1",
            },
        )
        self.assertRedirects(response, f"{self.create_url}?blank=1")

    def test_from_edition_with_default_uses_edition_title_and_template_sections(self):
        template = self._template_with_section("Weekly", "Intro", is_default=True)
        plan = NewsletterPlan.objects.create(year=2026, name="2026")
        edition = NewsletterEdition.objects.create(
            plan=plan,
            quarter="Q1",
            week_number=1,
            weekly_theme="Launch week",
            notes="Plan notes",
        )
        response = self.client.get(
            self.create_url,
            {"from_edition": edition.pk},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Launch week")
        self.assertContains(response, "Intro")
        self.assertEqual(response.context["from_template"], template)
        self.assertNotContains(response, "Plan notes")

    def test_set_default_from_template_list(self):
        template = self._template_with_section("Weekly", "Intro")
        url = reverse("crm:newsletter_template_set_default", args=[template.pk])
        response = self.client.post(url)
        self.assertRedirects(response, reverse("crm:newsletter_template_list"))
        template.refresh_from_db()
        self.assertTrue(template.is_default)

    def test_choose_query_shows_picker_even_with_default(self):
        self._template_with_section("Weekly", "Intro", is_default=True)
        response = self.client.get(self.create_url, {"choose": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "crm/newsletter_issue_choose_template.html")
        self.assertContains(response, "Weekly")


class CreateSignalToolTests(TestCase):
    def _dispatch(self, name, arguments):
        from crm.mcp_app import _dispatch

        result = _dispatch(name, arguments)
        return json.loads(result[0].text)

    def test_create_signal_links_mentioned_companies(self):
        existing = Company.objects.create(name="Acme")
        payload = self._dispatch(
            "create_signal",
            {
                "source_url": "https://example.com/news",
                "headline": "Acme and Globex expand",
                "summary": "Partnership announced.",
                "mentioned_company_names": ["Acme", "Globex", ""],
            },
        )
        self.assertTrue(payload["created"])
        signal = Signal.objects.get(pk=payload["signal_id"])
        self.assertEqual(signal.linked_company_id, existing.pk)
        self.assertEqual(payload["linked_company_id"], existing.pk)
        globex = Company.objects.get(name="Globex")
        self.assertEqual(payload["mentioned_company_ids"], [existing.pk, globex.pk])
