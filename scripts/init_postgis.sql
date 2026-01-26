-- PostgreSQL + PostGIS Initialization Script
-- Claude Logistics API

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- For text search optimization

-- Create indexes on commonly queried fields (will be created by Alembic, but included here for reference)
-- These will enhance query performance for geospatial and text searches

-- Optimize PostgreSQL settings for production
ALTER SYSTEM SET max_connections = 100;
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET effective_io_concurrency = 200;
ALTER SYSTEM SET work_mem = '4MB';
ALTER SYSTEM SET min_wal_size = '1GB';
ALTER SYSTEM SET max_wal_size = '4GB';

-- Apply settings
SELECT pg_reload_conf();

-- Create audit logging table (optional)
CREATE TABLE IF NOT EXISTS system_audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    event_type VARCHAR(100) NOT NULL,
    description TEXT,
    metadata JSONB
);

-- Create index on audit log
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON system_audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_event_type ON system_audit_log(event_type);

-- Log initialization
INSERT INTO system_audit_log (event_type, description, metadata)
VALUES ('DATABASE_INIT', 'PostGIS database initialized', jsonb_build_object('version', version()));
