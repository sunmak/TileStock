CREATE TABLE customer_returns (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 document_id bigint NOT NULL REFERENCES documents(id),
 reason text NOT NULL, total numeric(14,2) NOT NULL CHECK(total>=0),
 request_key uuid NOT NULL UNIQUE, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON customer_returns(document_id);
CREATE TABLE customer_return_lines (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 return_id bigint NOT NULL REFERENCES customer_returns(id),
 document_line_id bigint NOT NULL REFERENCES document_lines(id),
 quantity numeric(14,3) NOT NULL CHECK(quantity>0),
 restock boolean NOT NULL, amount numeric(14,2) NOT NULL CHECK(amount>=0),
 UNIQUE(return_id,document_line_id)
);
CREATE INDEX ON customer_return_lines(document_line_id);
CREATE TABLE refunds (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 document_id bigint NOT NULL REFERENCES documents(id),
 amount numeric(14,2) NOT NULL CHECK(amount>0),
 method text NOT NULL CHECK(method IN ('cash','bank','card','upi','other')),
 reference text NOT NULL DEFAULT '', request_key uuid NOT NULL UNIQUE,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON refunds(document_id);
ALTER TABLE stock_movements ADD COLUMN return_id bigint REFERENCES customer_returns(id);
CREATE VIEW document_balances AS
SELECT document_id,paid,returned,refunded,net_total,balance,
 greatest(balance,0) AS due, greatest(-balance,0) AS refund_due
FROM (
 SELECT d.id AS document_id,coalesce(p.amount,0) AS paid,
 coalesce(r.amount,0) AS returned,coalesce(f.amount,0) AS refunded,
 d.total-coalesce(r.amount,0) AS net_total,
 d.total-coalesce(r.amount,0)-coalesce(p.amount,0)+coalesce(f.amount,0) AS balance
 FROM documents d
 LEFT JOIN (SELECT document_id,sum(amount) amount FROM payments GROUP BY document_id) p ON p.document_id=d.id
 LEFT JOIN (SELECT document_id,sum(total) amount FROM customer_returns GROUP BY document_id) r ON r.document_id=d.id
 LEFT JOIN (SELECT document_id,sum(amount) amount FROM refunds GROUP BY document_id) f ON f.document_id=d.id
) b;
