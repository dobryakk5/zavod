-- Fix sequence for map.crm_event_types.id after manual inserts
SELECT setval(
    pg_get_serial_sequence('map.crm_event_types', 'id'),
    COALESCE((SELECT MAX(id) FROM map.crm_event_types), 0),
    true
);
