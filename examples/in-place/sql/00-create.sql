-- marketing_consent is declared without a type, so SQLite stores each value
-- exactly as written: text when loaded, integers after normalization.
CREATE TABLE customers (
  customer_id TEXT PRIMARY KEY,
  email TEXT,
  marketing_consent,
  region TEXT,
  age INTEGER
);
