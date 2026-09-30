-- =====================================================================================
-- TENANT REGISTRY — Cloud SQL for PostgreSQL (private IP)   database: tenancy
-- Owner: partner-data-api team · Written only by onboarding · Read by the Looker API services
--
-- Pattern: standard multi-tenant RBAC  (tenants · users · memberships · roles → resources · audit)
--   tenants            = tenants / organizations
--   partner_users      = users (external partners and machine clients)
--   tenant_groups      = tenant-scoped roles  (one row = one Looker group)
--   group_folders      = role → resource grants (Looker group → Looker folder)
--   partner_groups     = user ↔ role memberships (user_roles)
--   role_capabilities  = role → permission set (what a user may DO in Looker)
--   registry_audit     = append-only change history ("who could access X on date T?")
--
-- Conventions: snake_case · TEXT ids for external systems (Looker ids are strings)
-- · status columns instead of hard deletes · created_at / updated_at / updated_by on every table
-- · tenant_id on every access boundary · composite FKs so a partner can never be mapped to
--   another tenant's group.
-- =====================================================================================

-- ---------------------------------------------------------------- 1. tenants
CREATE TABLE tenants (
  tenant_id          TEXT        PRIMARY KEY,                 -- our identifier, e.g. 'acme'
  display_name       TEXT        NOT NULL,                    -- 'Acme Ltd'
  status             TEXT        NOT NULL DEFAULT 'active'
                     CHECK (status IN ('active','suspended','offboarded')),
  home_dashboard_id  TEXT,                                    -- optional landing dashboard (Looker id)
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_by         TEXT        NOT NULL                     -- onboarding job / admin id
);

-- ---------------------------------------------------------------- 2. tenant_groups  (tenant-scoped roles)
CREATE TABLE tenant_groups (
  tenant_id          TEXT        NOT NULL REFERENCES tenants(tenant_id),
  looker_group_id    TEXT        NOT NULL,                    -- id Looker assigned, e.g. '17'
  group_name         TEXT        NOT NULL,                    -- 'Partner acme', 'Partner acme – Retail'
  group_type         TEXT        NOT NULL DEFAULT 'tenant'
                     CHECK (group_type IN ('tenant','business_group','shared')),
  business_group     TEXT,                                    -- 'retail' when group_type = business_group
  status             TEXT        NOT NULL DEFAULT 'active' CHECK (status IN ('active','retired')),
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_by         TEXT        NOT NULL,
  PRIMARY KEY (tenant_id, looker_group_id),
  UNIQUE (looker_group_id)                                    -- a Looker group belongs to ONE tenant
);

-- ---------------------------------------------------------------- 3. group_folders  (role → resource)
-- Copy of the Looker folder permission (group has View on folder). Source of truth is Looker;
-- a nightly job compares the two.
CREATE TABLE group_folders (
  tenant_id          TEXT        NOT NULL,
  looker_group_id    TEXT        NOT NULL,
  looker_folder_id   TEXT        NOT NULL,                    -- e.g. '512' = Shared/Partners/acme
  folder_path        TEXT        NOT NULL,                    -- human readable, 'Partners/acme/Retail'
  permission         TEXT        NOT NULL DEFAULT 'view' CHECK (permission IN ('view')),
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_by         TEXT        NOT NULL,
  PRIMARY KEY (looker_group_id, looker_folder_id),
  FOREIGN KEY (tenant_id, looker_group_id) REFERENCES tenant_groups (tenant_id, looker_group_id)
);

-- ---------------------------------------------------------------- 4. role_capabilities  (role → permission set)
-- Replaces the hard-coded ROLE_MAP; changed only through a reviewed change.
CREATE TABLE role_capabilities (
  role_name          TEXT        PRIMARY KEY,                 -- 'viewer', 'analyst'
  role_rank          INT         NOT NULL UNIQUE,             -- 1 = lowest; used for the ceiling rule
  looker_permissions TEXT[]      NOT NULL,                    -- {access_data,see_user_dashboards,...}
  looker_models      TEXT[]      NOT NULL,                    -- {partner_analytics}
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_by         TEXT        NOT NULL
);

-- ---------------------------------------------------------------- 5. partner_users  (users)
CREATE TABLE partner_users (
  partner_id         TEXT        PRIMARY KEY,                 -- = JWT sub, e.g. 'PRT-ACME-0071'
  tenant_id          TEXT        NOT NULL REFERENCES tenants(tenant_id),
  kind               TEXT        NOT NULL CHECK (kind IN ('human','machine')),
  status             TEXT        NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled')),
  max_role           TEXT        NOT NULL REFERENCES role_capabilities(role_name),  -- ceiling
  business_groups    TEXT        NOT NULL DEFAULT '',         -- row filter value, e.g. 'retail' or 'wealth,corporate'
  display_name       TEXT,                                    -- optional, for support screens only
  looker_user_id     TEXT,                                    -- filled after first login (Looker's own id)
  looker_external_user_id TEXT GENERATED ALWAYS AS (partner_id || '::' || tenant_id) STORED,
                                                              -- = Looker external_user_id, e.g. 'PRT-ACME-0071::acme'
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_by         TEXT        NOT NULL
);
CREATE INDEX partner_users_tenant_idx ON partner_users (tenant_id);
CREATE UNIQUE INDEX ux_partner_users_ext_id ON partner_users (looker_external_user_id);
-- Already created the table without the column? Add it instead with:
--   ALTER TABLE partner_users
--     ADD COLUMN looker_external_user_id TEXT
--     GENERATED ALWAYS AS (partner_id || '::' || tenant_id) STORED;
--   CREATE UNIQUE INDEX ux_partner_users_ext_id ON partner_users (looker_external_user_id);

-- ---------------------------------------------------------------- 6. partner_groups  (memberships)
CREATE TABLE partner_groups (
  partner_id         TEXT        NOT NULL REFERENCES partner_users(partner_id),
  tenant_id          TEXT        NOT NULL,
  looker_group_id    TEXT        NOT NULL,
  valid_from         TIMESTAMPTZ NOT NULL DEFAULT now(),
  valid_to           TIMESTAMPTZ,                             -- NULL = open-ended
  granted_reason     TEXT,                                    -- ticket / approval reference
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_by         TEXT        NOT NULL,
  PRIMARY KEY (partner_id, looker_group_id),
  -- composite FK: the group must belong to the SAME tenant as the partner
  FOREIGN KEY (tenant_id, looker_group_id) REFERENCES tenant_groups (tenant_id, looker_group_id)
);
CREATE INDEX partner_groups_partner_tenant_idx ON partner_groups (partner_id, tenant_id);

-- guard: partner_groups.tenant_id must equal the partner's own tenant
CREATE FUNCTION check_partner_tenant() RETURNS trigger AS $$
BEGIN
  IF NEW.tenant_id <> (SELECT tenant_id FROM partner_users WHERE partner_id = NEW.partner_id) THEN
    RAISE EXCEPTION 'partner % does not belong to tenant %', NEW.partner_id, NEW.tenant_id;
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER partner_groups_tenant_guard BEFORE INSERT OR UPDATE ON partner_groups
  FOR EACH ROW EXECUTE FUNCTION check_partner_tenant();

-- ---------------------------------------------------------------- 7. registry_audit  (append-only history)
CREATE TABLE registry_audit (
  audit_id           BIGSERIAL   PRIMARY KEY,
  table_name         TEXT        NOT NULL,
  operation          TEXT        NOT NULL,                    -- INSERT | UPDATE | DELETE
  row_key            JSONB       NOT NULL,
  old_row            JSONB,
  new_row            JSONB,
  changed_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  changed_by         TEXT        NOT NULL DEFAULT current_user
);

CREATE FUNCTION audit_row() RETURNS trigger AS $$
BEGIN
  INSERT INTO registry_audit (table_name, operation, row_key, old_row, new_row)
  VALUES (TG_TABLE_NAME, TG_OP,
          to_jsonb(COALESCE(NEW, OLD)) - 'created_at' - 'updated_at',
          CASE WHEN TG_OP <> 'INSERT' THEN to_jsonb(OLD) END,
          CASE WHEN TG_OP <> 'DELETE' THEN to_jsonb(NEW) END);
  RETURN COALESCE(NEW, OLD);
END $$ LANGUAGE plpgsql;

CREATE TRIGGER tenants_audit        AFTER INSERT OR UPDATE OR DELETE ON tenants        FOR EACH ROW EXECUTE FUNCTION audit_row();
CREATE TRIGGER tenant_groups_audit  AFTER INSERT OR UPDATE OR DELETE ON tenant_groups  FOR EACH ROW EXECUTE FUNCTION audit_row();
CREATE TRIGGER group_folders_audit  AFTER INSERT OR UPDATE OR DELETE ON group_folders  FOR EACH ROW EXECUTE FUNCTION audit_row();
CREATE TRIGGER partner_users_audit  AFTER INSERT OR UPDATE OR DELETE ON partner_users  FOR EACH ROW EXECUTE FUNCTION audit_row();
CREATE TRIGGER partner_groups_audit AFTER INSERT OR UPDATE OR DELETE ON partner_groups FOR EACH ROW EXECUTE FUNCTION audit_row();

-- ---------------------------------------------------------------- access control on the database
-- API services only READ; onboarding writes; nobody can edit the audit trail.
CREATE ROLE data_api   LOGIN;
CREATE ROLE onboarding LOGIN;
GRANT SELECT ON tenants, tenant_groups, group_folders, role_capabilities, partner_users, partner_groups TO data_api;
GRANT SELECT, INSERT, UPDATE ON tenants, tenant_groups, group_folders, role_capabilities, partner_users, partner_groups TO onboarding;
GRANT INSERT ON registry_audit TO onboarding;
GRANT USAGE ON SEQUENCE registry_audit_audit_id_seq TO onboarding;
REVOKE UPDATE, DELETE ON registry_audit FROM PUBLIC;

-- =====================================================================================
-- SAMPLE DATA
-- =====================================================================================
INSERT INTO role_capabilities VALUES
 ('viewer',  1, '{access_data,see_user_dashboards,see_looks}',                                 '{partner_analytics}', now(), 'seed'),
 ('analyst', 2, '{access_data,see_user_dashboards,see_looks,explore,download_without_limit}', '{partner_analytics}', now(), 'seed');

INSERT INTO tenants (tenant_id, display_name, status, home_dashboard_id, updated_by)
VALUES ('acme', 'Acme Ltd', 'active', '42', 'onboarding');

INSERT INTO tenant_groups (tenant_id, looker_group_id, group_name, group_type, business_group, updated_by) VALUES
 ('acme', '17', 'Partner acme',          'tenant',         NULL,     'onboarding'),
 ('acme', '31', 'Partner acme – Retail', 'business_group', 'retail', 'onboarding');

INSERT INTO group_folders (tenant_id, looker_group_id, looker_folder_id, folder_path, updated_by) VALUES
 ('acme', '17', '512', 'Partners/acme',        'onboarding'),
 ('acme', '31', '530', 'Partners/acme/Retail', 'onboarding');

INSERT INTO partner_users (partner_id, tenant_id, kind, status, max_role, business_groups, updated_by) VALUES
 ('PRT-ACME-0071', 'acme', 'human', 'active', 'analyst', 'retail', 'onboarding'),
 ('PRT-ACME-0099', 'acme', 'human', 'active', 'viewer',  '',       'onboarding');

INSERT INTO partner_groups (partner_id, tenant_id, looker_group_id, granted_reason, updated_by) VALUES
 ('PRT-ACME-0071', 'acme', '17', 'CHG-1001', 'onboarding'),
 ('PRT-ACME-0071', 'acme', '31', 'CHG-1001', 'onboarding'),
 ('PRT-ACME-0099', 'acme', '17', 'CHG-1002', 'onboarding');

-- =====================================================================================
-- QUERIES THE APIs RUN
-- =====================================================================================

-- Q1 (5.3) everything needed for one login, in one round trip
SELECT pu.partner_id, pu.tenant_id, pu.looker_external_user_id, pu.status AS partner_status, t.status AS tenant_status,
       pu.max_role, pu.business_groups, t.home_dashboard_id,
       array_agg(DISTINCT pg.looker_group_id)  AS looker_group_ids,
       array_agg(DISTINCT gf.looker_folder_id) AS looker_folder_ids
FROM   partner_users  pu
JOIN   tenants        t  ON t.tenant_id = pu.tenant_id
JOIN   partner_groups pg ON pg.partner_id = pu.partner_id AND pg.tenant_id = pu.tenant_id
                        AND pg.valid_from <= now() AND (pg.valid_to IS NULL OR pg.valid_to > now())
JOIN   tenant_groups  tg ON tg.tenant_id = pg.tenant_id AND tg.looker_group_id = pg.looker_group_id
                        AND tg.status = 'active'
JOIN   group_folders  gf ON gf.looker_group_id = tg.looker_group_id
WHERE  pu.partner_id = 'PRT-ACME-0071'
GROUP  BY pu.partner_id, pu.tenant_id, pu.looker_external_user_id, pu.status, t.status, pu.max_role, pu.business_groups, t.home_dashboard_id;
-- → PRT-ACME-0071 | acme | PRT-ACME-0071::acme | active | active | analyst | retail | 42 | {17,31} | {512,530}

-- Q2 which folders can a partner open (support / audit)
SELECT pg.partner_id, tg.group_name, gf.folder_path, gf.looker_folder_id
FROM   partner_groups pg
JOIN   tenant_groups  tg USING (tenant_id, looker_group_id)
JOIN   group_folders  gf USING (tenant_id, looker_group_id)
WHERE  pg.partner_id = 'PRT-ACME-0071';

-- Q3 who could open folder 530 on a given date (compliance)
SELECT DISTINCT pg.partner_id
FROM   partner_groups pg
JOIN   group_folders  gf USING (tenant_id, looker_group_id)
WHERE  gf.looker_folder_id = '530'
  AND  pg.valid_from <= TIMESTAMPTZ '2026-09-01' AND (pg.valid_to IS NULL OR pg.valid_to > TIMESTAMPTZ '2026-09-01');
-- (for exact history use registry_audit, since rows can change after that date)
