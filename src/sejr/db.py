from pathlib import Path

import duckdb

from sejr.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS threads (
  thread_id   BIGINT PRIMARY KEY,
  kind        VARCHAR NOT NULL,
  month       DATE NOT NULL,
  title       VARCHAR NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL,
  snapshot_at TIMESTAMPTZ NOT NULL,
  fetched_at  TIMESTAMPTZ NOT NULL,
  removed_in_snapshot INTEGER,
  UNIQUE (kind, month)
);
CREATE TABLE IF NOT EXISTS posts (
  post_id     BIGINT PRIMARY KEY,
  thread_id   BIGINT NOT NULL,
  author      VARCHAR,
  created_at  TIMESTAMPTZ NOT NULL,
  text_html   VARCHAR NOT NULL,
  text        VARCHAR NOT NULL,
  in_snapshot BOOLEAN NOT NULL
);
CREATE TABLE IF NOT EXISTS replies (
  reply_id    BIGINT PRIMARY KEY,
  post_id     BIGINT NOT NULL,
  parent_id   BIGINT NOT NULL,
  thread_id   BIGINT NOT NULL,
  author      VARCHAR,
  created_at  TIMESTAMPTZ NOT NULL,
  text        VARCHAR NOT NULL,
  depth       INTEGER NOT NULL,
  in_snapshot BOOLEAN NOT NULL
);
CREATE TABLE IF NOT EXISTS answers (
  post_id       BIGINT NOT NULL,
  question      VARCHAR NOT NULL,
  method        VARCHAR NOT NULL,
  version       VARCHAR NOT NULL,
  value         DOUBLE,
  label         VARCHAR,
  probabilities JSON,
  confidence    DOUBLE,
  PRIMARY KEY (post_id, question, method, version)
);
CREATE TABLE IF NOT EXISTS monthly_metrics (
  month    DATE NOT NULL,
  kind     VARCHAR NOT NULL,
  metric   VARCHAR NOT NULL,
  category VARCHAR NOT NULL DEFAULT '',
  value    DOUBLE,
  n        INTEGER,
  PRIMARY KEY (month, kind, metric, category)
);
"""


def connect(path: Path | str = DB_PATH) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(path))
    con.execute("SET TimeZone = 'UTC'")
    con.execute(SCHEMA)
    return con
