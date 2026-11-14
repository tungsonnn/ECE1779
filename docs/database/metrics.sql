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

-- 2. Error rate per tenant, over finished requests only
CREATE OR REPLACE VIEW metrics_error_rate AS
SELECT t.name AS tenant,
       count(*) FILTER (WHERE a.status = 'error') AS errors,
    count(*)                                   AS finished,
       round(100.0 * count(*) FILTER (WHERE a.status = 'error') / count(*), 1) AS error_pct
FROM audit_log a
         JOIN tenants t ON t.id = a.tenant_id
WHERE a.status IN ('ok', 'error')
GROUP BY t.name;

-- 3. Latency per tenant in milliseconds: avg and 95th
CREATE OR REPLACE VIEW metrics_latency AS
SELECT t.name AS tenant,
       round(avg(a.latency_ms))                                          AS avg_ms,
       round(percentile_cont(0.95) WITHIN GROUP (ORDER BY a.latency_ms)) AS p95_ms
FROM audit_log a
         JOIN tenants t ON t.id = a.tenant_id
WHERE a.latency_ms IS NOT NULL
GROUP BY t.name;

-- 4. PII caught per tenant and entity type, summed from entity_counts JSON
CREATE OR REPLACE VIEW metrics_pii_caught AS
SELECT t.name AS tenant,
       e.key  AS entity,
       sum(e.value::int) AS caught
FROM audit_log a
         JOIN tenants t ON t.id = a.tenant_id
         CROSS JOIN LATERAL jsonb_each_text(a.entity_counts) AS e
GROUP BY t.name, e.key;