CREATE TABLE tenants (
                         id          SERIAL PRIMARY KEY,
                         name        TEXT NOT NULL UNIQUE,
                         created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE api_keys (
                          id          SERIAL PRIMARY KEY,
                          tenant_id   INT NOT NULL REFERENCES tenants(id),
                          key_hash    TEXT NOT NULL UNIQUE,      -- never the raw key
                          created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE audit_log (
                           id            BIGSERIAL PRIMARY KEY,
                           tenant_id     INT NOT NULL REFERENCES tenants(id),
                           created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
                           status        TEXT NOT NULL DEFAULT 'pending', CHECK(status IN ('pending', 'ok', 'error')), -- pending | ok | error
                           entity_counts JSONB NOT NULL DEFAULT '{}',      -- e.g. {"PERSON": 2, "EMAIL_ADDRESS": 1}
                           latency_ms    INT,                              -- filled in after the LLM call
                           error_code    TEXT                              -- filled in only on error
);