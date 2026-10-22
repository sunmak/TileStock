CREATE TABLE products (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 sku text NOT NULL UNIQUE, name text NOT NULL,
 unit text NOT NULL DEFAULT 'box', area_per_unit numeric(12,4) NOT NULL DEFAULT 0 CHECK(area_per_unit>=0),
 sale_price numeric(14,2) NOT NULL CHECK(sale_price>=0),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE batches (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 product_id bigint NOT NULL REFERENCES products(id), code text NOT NULL,
 shade text NOT NULL DEFAULT '', size text NOT NULL DEFAULT '',
 quantity numeric(14,3) NOT NULL DEFAULT 0 CHECK(quantity>=0),
 UNIQUE(product_id,code)
);
CREATE TABLE customers (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 name text NOT NULL, phone text NOT NULL DEFAULT '', address text NOT NULL DEFAULT ''
);
CREATE TABLE documents (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 kind text NOT NULL CHECK(kind IN ('estimate','invoice')),
 status text NOT NULL CHECK(status IN ('draft','posted','void')),
 customer_id bigint NOT NULL REFERENCES customers(id),
 customer_name text NOT NULL, customer_address text NOT NULL,
 source_estimate_id bigint UNIQUE REFERENCES documents(id),
 request_key uuid NOT NULL UNIQUE,
 notes text NOT NULL DEFAULT '', total numeric(14,2) NOT NULL DEFAULT 0 CHECK(total>=0),
 created_at timestamptz NOT NULL DEFAULT now(), posted_at timestamptz
);
CREATE TABLE document_lines (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 document_id bigint NOT NULL REFERENCES documents(id),
 batch_id bigint NOT NULL REFERENCES batches(id), description text NOT NULL,
 unit text NOT NULL, quantity numeric(14,3) NOT NULL CHECK(quantity>0),
 unit_price numeric(14,2) NOT NULL CHECK(unit_price>=0),
 amount numeric(14,2) NOT NULL CHECK(amount>=0), UNIQUE(document_id,batch_id)
);
CREATE TABLE stock_movements (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 batch_id bigint NOT NULL REFERENCES batches(id),
 delta numeric(14,3) NOT NULL CHECK(delta<>0), reason text NOT NULL,
 document_id bigint REFERENCES documents(id), request_key uuid UNIQUE,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE payments (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 document_id bigint NOT NULL REFERENCES documents(id),
 amount numeric(14,2) NOT NULL CHECK(amount>0),
 method text NOT NULL CHECK(method IN ('cash','bank','card','upi','other')),
 reference text NOT NULL DEFAULT '', request_key uuid NOT NULL UNIQUE,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON batches(product_id);
CREATE INDEX ON documents(customer_id);
CREATE INDEX ON document_lines(document_id);
CREATE INDEX ON payments(document_id);
CREATE INDEX ON stock_movements(batch_id,id);
CREATE TABLE api_requests (
 request_key uuid PRIMARY KEY, fingerprint text NOT NULL, result jsonb NOT NULL
);
