-- Metrics for the admin page, stored as views on audit_log. Apply after schema.sql. Read with: SELECT * FROM <view name>;
-- Idempotent-safe(CREATE OR REPLACE)

-- 1. Requests per tenant. "pending" = started but never finished (e.g. a crash).
CREATE OR REPLACE VIEW metrics_requests AS
SELECT t.name AS tenant,
       count(*)                                     AS requests,
       count(*) FILTER (WHERE a.status = 'pending') AS pending
FROM audit_log a
JOIN tenants t ON t.id = a.tenant_id
GROUP BY t.name;
