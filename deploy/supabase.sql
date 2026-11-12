-- Run once in Supabase SQL Editor before Django migrations.
-- Keep this schema OUT of the Supabase Data API exposed schemas list.
CREATE SCHEMA IF NOT EXISTS django;
REVOKE ALL ON SCHEMA django FROM PUBLIC;
REVOKE ALL ON SCHEMA django FROM anon, authenticated;
