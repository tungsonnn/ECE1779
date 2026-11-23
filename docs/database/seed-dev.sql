-- Dev-only seed, loaded by Docker Compose after schema.sql.
-- Matches the demo tenants in app/services/auth.py (ids 1 and 2), so the
-- audit_log foreign key holds while auth is still a stub.
INSERT INTO tenants (id, name) VALUES
  (1, 'Demo Team A'),
  (2, 'Demo Team B')
ON CONFLICT (id) DO NOTHING;

-- Keep SERIAL in sync after inserting explicit ids.
SELECT setval('tenants_id_seq', (SELECT max(id) FROM tenants));
