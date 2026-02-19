"""
DEPRECATED.

Legacy raw-SQL CRM routes from `views_map_crm.py`.
This module is intentionally kept only for transition and must not be wired into runtime URLs.
Active CRM surface is `backend/api/urls.py` + `backend/api/views_crm_orm.py`.
"""

from django.urls import path
from .views_map_crm import (
    ContactsListView,
    ContactDetailView,
    ContactTelegramLinkView,
    TagsListView,
    TagDetailView,
    ContactTagsView,
    CategoriesListView,
    CategoryDetailView,
    EventTypesListView,
    EventTypeDetailView,
    EventsListView,
    EventDetailView,
    AvailabilityEventsListView,
    AvailabilityEventDetailView,
    PaymentsListView,
    PaymentDetailView,
    NotesListView,
    NoteDetailView,
)

urlpatterns = [
    # Contacts endpoints
    path('contacts/', ContactsListView.as_view(), name='map-contacts-list'),
    path('contacts/<int:contact_id>/', ContactDetailView.as_view(), name='map-contact-detail'),
    path('contacts/<int:contact_id>/telegram-link/', ContactTelegramLinkView.as_view(), name='map-contact-telegram-link'),
    
    # Tags endpoints
    path('tags/', TagsListView.as_view(), name='map-tags-list'),
    path('tags/<int:tag_id>/', TagDetailView.as_view(), name='map-tag-detail'),
    
    # Contact-Tag relationships
    path('contact-tags/', ContactTagsView.as_view(), name='map-contact-tags'),

    # Categories endpoints
    path('categories/', CategoriesListView.as_view(), name='map-categories-list'),
    path('categories/<int:category_id>/', CategoryDetailView.as_view(), name='map-category-detail'),
    
    # Event types endpoints
    path('event-types/', EventTypesListView.as_view(), name='map-event-types-list'),
    path('event-types/<int:event_type_id>/', EventTypeDetailView.as_view(), name='map-event-type-detail'),
    
    # Events endpoints
    path('events/', EventsListView.as_view(), name='map-events-list'),
    path('events/<int:event_id>/', EventDetailView.as_view(), name='map-event-detail'),

    # Availability events endpoints
    path('availability-events/', AvailabilityEventsListView.as_view(), name='map-availability-events-list'),
    path('availability-events/<int:event_id>/', AvailabilityEventDetailView.as_view(), name='map-availability-event-detail'),
    
    # Payments endpoints
    path('payments/', PaymentsListView.as_view(), name='map-payments-list'),
    path('payments/<int:payment_id>/', PaymentDetailView.as_view(), name='map-payment-detail'),
    
    # Notes endpoints
    path('notes/', NotesListView.as_view(), name='map-notes-list'),
    path('notes/<int:note_id>/', NoteDetailView.as_view(), name='map-note-detail'),
]
