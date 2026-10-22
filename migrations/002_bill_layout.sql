ALTER TABLE products ADD COLUMN brand text NOT NULL DEFAULT '';
ALTER TABLE products ADD COLUMN pack text NOT NULL DEFAULT '';
ALTER TABLE products ADD COLUMN grade text NOT NULL DEFAULT '';
ALTER TABLE batches ADD COLUMN colour text NOT NULL DEFAULT '';
ALTER TABLE documents ADD COLUMN vehicle_no text NOT NULL DEFAULT '';
ALTER TABLE document_lines ADD COLUMN product_name text NOT NULL DEFAULT '';
ALTER TABLE document_lines ADD COLUMN brand text NOT NULL DEFAULT '';
ALTER TABLE document_lines ADD COLUMN pack text NOT NULL DEFAULT '';
ALTER TABLE document_lines ADD COLUMN grade text NOT NULL DEFAULT '';
ALTER TABLE document_lines ADD COLUMN colour text NOT NULL DEFAULT '';
UPDATE document_lines l SET product_name=p.name
FROM batches b JOIN products p ON p.id=b.product_id WHERE b.id=l.batch_id;
