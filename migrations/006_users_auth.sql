CREATE TABLE app_users (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 email text NOT NULL UNIQUE CHECK(email=lower(trim(email))),
 name text NOT NULL, role text NOT NULL CHECK(role IN ('owner','sales','stock','viewer')),
 active boolean NOT NULL DEFAULT true, password_hash text NOT NULL,
 totp_secret text, mfa_enabled boolean NOT NULL DEFAULT false,
 last_totp_step bigint NOT NULL DEFAULT -1,
 force_password_change boolean NOT NULL DEFAULT false,
 session_version integer NOT NULL DEFAULT 1,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE auth_challenges (
 token_hash text PRIMARY KEY, user_id bigint NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
 version integer NOT NULL, mode text NOT NULL CHECK(mode IN ('enroll','verify')),
 pending_secret text, expires_at timestamptz NOT NULL,
 attempts integer NOT NULL DEFAULT 0, consumed boolean NOT NULL DEFAULT false
);
CREATE INDEX ON auth_challenges(user_id);
CREATE TABLE auth_sessions (
 token_hash text PRIMARY KEY, user_id bigint NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
 version integer NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 last_seen timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL
);
CREATE INDEX ON auth_sessions(user_id);
CREATE TABLE recovery_codes (
 user_id bigint NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
 code_hash text NOT NULL, used_at timestamptz, PRIMARY KEY(user_id,code_hash)
);
CREATE TABLE auth_limits (
 key text PRIMARY KEY, started_at timestamptz NOT NULL DEFAULT now(), count integer NOT NULL DEFAULT 0
);
CREATE TABLE audit_log (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 actor_id bigint REFERENCES app_users(id) ON DELETE SET NULL, actor_email text NOT NULL DEFAULT '',
 action text NOT NULL, entity text NOT NULL DEFAULT '', entity_id text NOT NULL DEFAULT '',
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON audit_log(created_at);
CREATE FUNCTION audit_business_change() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE actor bigint; actor_mail text;
BEGIN
 actor := nullif(current_setting('app.actor_id',true),'')::bigint;
 SELECT email INTO actor_mail FROM app_users WHERE id=actor;
 INSERT INTO audit_log(actor_id,actor_email,action,entity,entity_id)
 VALUES(actor,coalesce(actor_mail,'local/database'),TG_OP,TG_TABLE_NAME,
 CASE WHEN TG_OP='DELETE' THEN OLD.id::text ELSE NEW.id::text END);
 RETURN NULL;
END $$;
CREATE TRIGGER product_audit AFTER INSERT OR UPDATE OR DELETE ON products FOR EACH ROW EXECUTE FUNCTION audit_business_change();
CREATE TRIGGER batch_audit AFTER INSERT OR UPDATE OR DELETE ON batches FOR EACH ROW EXECUTE FUNCTION audit_business_change();
CREATE TRIGGER customer_audit AFTER INSERT OR UPDATE OR DELETE ON customers FOR EACH ROW EXECUTE FUNCTION audit_business_change();
CREATE TRIGGER document_audit AFTER INSERT OR UPDATE OR DELETE ON documents FOR EACH ROW EXECUTE FUNCTION audit_business_change();
CREATE TRIGGER movement_audit AFTER INSERT OR UPDATE OR DELETE ON stock_movements FOR EACH ROW EXECUTE FUNCTION audit_business_change();
CREATE TRIGGER payment_audit AFTER INSERT OR UPDATE OR DELETE ON payments FOR EACH ROW EXECUTE FUNCTION audit_business_change();
CREATE TRIGGER return_audit AFTER INSERT OR UPDATE OR DELETE ON customer_returns FOR EACH ROW EXECUTE FUNCTION audit_business_change();
CREATE TRIGGER refund_audit AFTER INSERT OR UPDATE OR DELETE ON refunds FOR EACH ROW EXECUTE FUNCTION audit_business_change();
