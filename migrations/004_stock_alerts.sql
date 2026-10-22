ALTER TABLE products ADD COLUMN criticality text NOT NULL DEFAULT 'medium'
 CHECK(criticality IN ('high','medium','low'));
ALTER TABLE products ADD COLUMN minimum_stock numeric(14,3) NOT NULL DEFAULT 0 CHECK(minimum_stock>=0);
ALTER TABLE products ADD COLUMN critical_stock numeric(14,3) NOT NULL DEFAULT 0 CHECK(critical_stock>=0 AND critical_stock<=minimum_stock);
ALTER TABLE products ADD COLUMN stock_alerts_enabled boolean NOT NULL DEFAULT true;
