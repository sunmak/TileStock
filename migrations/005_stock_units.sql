CREATE TABLE product_units (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 product_id bigint NOT NULL REFERENCES products(id),
 name text NOT NULL CHECK(length(trim(name))>0),
 factor numeric(16,6) NOT NULL CHECK(factor>0),
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ON product_units(product_id,lower(trim(name)));
ALTER TABLE stock_movements ADD COLUMN entered_quantity numeric(14,3);
ALTER TABLE stock_movements ADD COLUMN entered_unit text;
ALTER TABLE stock_movements ADD COLUMN conversion_factor numeric(16,6);
ALTER TABLE stock_movements ADD COLUMN stock_unit text;
