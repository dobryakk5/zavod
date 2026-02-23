from pathlib import Path

from django.test import SimpleTestCase


BACKEND_ROOT = Path(__file__).resolve().parents[2]
CRM_ORM_VIEWS_FILE = BACKEND_ROOT / "api" / "views_crm_orm.py"
API_URLS_FILE = BACKEND_ROOT / "api" / "urls.py"
PROJECT_URLS_FILE = BACKEND_ROOT / "config" / "urls.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestCRMArchitectureGuardrails(SimpleTestCase):
    def test_crm_orm_views_do_not_use_raw_sql_cursor_calls(self):
        source = _read(CRM_ORM_VIEWS_FILE)
        self.assertNotIn("connection.cursor(", source)
        self.assertNotIn("cursor.execute(", source)

    def test_crm_orm_views_do_not_access_models_directly(self):
        source = _read(CRM_ORM_VIEWS_FILE)
        self.assertNotIn(".objects.", source)

    def test_active_api_urls_do_not_reference_legacy_raw_crm_module(self):
        api_urls_source = _read(API_URLS_FILE)
        project_urls_source = _read(PROJECT_URLS_FILE)

        self.assertNotIn(".views_map_crm", api_urls_source)
        self.assertNotIn("urls_map_crm", api_urls_source)
        self.assertNotIn("urls_map_crm", project_urls_source)

    def test_active_crm_router_contains_expected_orm_resources(self):
        source = _read(API_URLS_FILE)
        expected_fragments = [
            "crm_router.register(r'contacts', MapContactViewSet",
            "crm_router.register(r'payments', MapCRMPaymentViewSet",
            "crm_router.register(r'tags', MapCRMTagViewSet",
            "crm_router.register(r'categories', MapCRMCategoryViewSet",
            "crm_router.register(r'contact-tags', MapContactTagsViewSet",
            "crm_router.register(r'event-types', MapCRMEventTypeViewSet",
            "crm_router.register(r'events', MapCRMEventViewSet",
            "crm_router.register(r'availability-events', MapAvailabilityEventViewSet",
            "crm_router.register(r'notes', MapCRMNoteViewSet",
        ]
        for fragment in expected_fragments:
            self.assertIn(fragment, source)
