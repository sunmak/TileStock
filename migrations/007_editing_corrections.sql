ALTER TABLE products ADD COLUMN version integer NOT NULL DEFAULT 1;
ALTER TABLE customers ADD COLUMN version integer NOT NULL DEFAULT 1;
ALTER TABLE documents ADD COLUMN version integer NOT NULL DEFAULT 1;
CREATE FUNCTION advance_record_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN NEW.version := OLD.version+1; RETURN NEW; END $$;
CREATE TRIGGER product_version BEFORE UPDATE ON products FOR EACH ROW EXECUTE FUNCTION advance_record_version();
CREATE TRIGGER customer_version BEFORE UPDATE ON customers FOR EACH ROW EXECUTE FUNCTION advance_record_version();
CREATE TRIGGER document_version BEFORE UPDATE ON documents FOR EACH ROW EXECUTE FUNCTION advance_record_version();
ALTER TABLE customer_returns ADD COLUMN reversed_at timestamptz;
ALTER TABLE customer_returns ADD COLUMN reversed_by bigint REFERENCES app_users(id);
ALTER TABLE customer_returns ADD COLUMN reversal_reason text;
ALTER TABLE refunds ADD COLUMN reversed_at timestamptz;
ALTER TABLE refunds ADD COLUMN reversed_by bigint REFERENCES app_users(id);
ALTER TABLE refunds ADD COLUMN reversal_reason text;
CREATE TABLE correction_log (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 actor_id bigint REFERENCES app_users(id), actor_email text NOT NULL,
 action text NOT NULL, entity text NOT NULL, entity_id bigint NOT NULL,
 reason text NOT NULL CHECK(length(trim(reason))>0),
 before_data jsonb NOT NULL, after_data jsonb NOT NULL,
 request_key uuid NOT NULL UNIQUE, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON correction_log(entity,entity_id);
CREATE OR REPLACE VIEW document_balances AS
SELECT document_id,paid,returned,refunded,net_total,balance,
 greatest(balance,0) AS due, greatest(-balance,0) AS refund_due
FROM (
 SELECT d.id AS document_id,coalesce(p.amount,0) AS paid,
 coalesce(r.amount,0) AS returned,coalesce(f.amount,0) AS refunded,
 d.total-coalesce(r.amount,0) AS net_total,
 d.total-coalesce(r.amount,0)-coalesce(p.amount,0)+coalesce(f.amount,0) AS balance
 FROM documents d
 LEFT JOIN (SELECT document_id,sum(amount) amount FROM payments GROUP BY document_id) p ON p.document_id=d.id
 LEFT JOIN (SELECT document_id,sum(total) amount FROM customer_returns WHERE reversed_at IS NULL GROUP BY document_id) r ON r.document_id=d.id
 LEFT JOIN (SELECT document_id,sum(amount) amount FROM refunds WHERE reversed_at IS NULL GROUP BY document_id) f ON f.document_id=d.id
) b;
