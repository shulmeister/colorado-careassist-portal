-- WellSky API Cache Tables
-- Optimized for fast caller ID lookup during Gigi calls
-- Sync frequency: Every 24 hours (3am cron job)

-- =============================================================================
-- Cached Practitioners (Caregivers)
-- =============================================================================

CREATE TABLE IF NOT EXISTS cached_practitioners (
    id VARCHAR(50) PRIMARY KEY,                    -- WellSky practitioner ID
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    full_name VARCHAR(200),
    phone VARCHAR(20),                             -- Mobile phone (primary)
    home_phone VARCHAR(20),
    work_phone VARCHAR(20),
    email VARCHAR(200),
    address VARCHAR(500),
    city VARCHAR(100),
    state VARCHAR(10),
    zip_code VARCHAR(20),
    status VARCHAR(50),                            -- HIRED, ACTIVE, INACTIVE, etc.
    is_hired BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT false,
    hire_date DATE,
    skills TEXT,                                   -- JSON array of skill IDs
    certifications TEXT,                           -- JSON array of certification IDs
    notes TEXT,
    external_id VARCHAR(100),                      -- Payroll/external system ID
    wellsky_data JSONB,                            -- Full WellSky response (for reference)
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Last sync time
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for FAST caller ID lookup (critical path)
CREATE INDEX IF NOT EXISTS idx_practitioners_phone ON cached_practitioners(phone);
CREATE INDEX IF NOT EXISTS idx_practitioners_home_phone ON cached_practitioners(home_phone);
CREATE INDEX IF NOT EXISTS idx_practitioners_work_phone ON cached_practitioners(work_phone);
CREATE INDEX IF NOT EXISTS idx_practitioners_status ON cached_practitioners(status);
CREATE INDEX IF NOT EXISTS idx_practitioners_is_hired ON cached_practitioners(is_hired);
CREATE INDEX IF NOT EXISTS idx_practitioners_is_active ON cached_practitioners(is_active);
CREATE INDEX IF NOT EXISTS idx_practitioners_synced_at ON cached_practitioners(synced_at);

-- Full-text search for name lookup
CREATE INDEX IF NOT EXISTS idx_practitioners_full_name ON cached_practitioners USING gin(to_tsvector('english', full_name));


-- =============================================================================
-- Cached Patients (Clients)
-- =============================================================================

CREATE TABLE IF NOT EXISTS cached_patients (
    id VARCHAR(50) PRIMARY KEY,                    -- WellSky patient ID
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    full_name VARCHAR(200),
    phone VARCHAR(20),                             -- Mobile phone (primary)
    home_phone VARCHAR(20),
    work_phone VARCHAR(20),
    email VARCHAR(200),
    address VARCHAR(500),
    city VARCHAR(100),
    state VARCHAR(10),
    zip_code VARCHAR(20),
    status VARCHAR(50),                            -- PROSPECT, ACTIVE, ON_HOLD, etc.
    is_active BOOLEAN DEFAULT false,
    start_date DATE,                               -- Care start date
    emergency_contact_name VARCHAR(200),
    emergency_contact_phone VARCHAR(20),
    referral_source VARCHAR(200),
    notes TEXT,
    wellsky_data JSONB,                            -- Full WellSky response (for reference)
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Last sync time
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for FAST caller ID lookup (critical path)
CREATE INDEX IF NOT EXISTS idx_patients_phone ON cached_patients(phone);
CREATE INDEX IF NOT EXISTS idx_patients_home_phone ON cached_patients(home_phone);
CREATE INDEX IF NOT EXISTS idx_patients_work_phone ON cached_patients(work_phone);
CREATE INDEX IF NOT EXISTS idx_patients_status ON cached_patients(status);
CREATE INDEX IF NOT EXISTS idx_patients_is_active ON cached_patients(is_active);
CREATE INDEX IF NOT EXISTS idx_patients_synced_at ON cached_patients(synced_at);

-- Full-text search for name lookup
CREATE INDEX IF NOT EXISTS idx_patients_full_name ON cached_patients USING gin(to_tsvector('english', full_name));


-- =============================================================================
-- Sync Metadata (track sync jobs)
-- =============================================================================

CREATE TABLE IF NOT EXISTS wellsky_sync_log (
    id SERIAL PRIMARY KEY,
    sync_type VARCHAR(50),                         -- 'practitioners', 'patients', 'full'
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    records_synced INTEGER,
    records_added INTEGER,
    records_updated INTEGER,
    errors TEXT,
    status VARCHAR(20)                             -- 'running', 'completed', 'failed'
);

CREATE INDEX IF NOT EXISTS idx_sync_log_started_at ON wellsky_sync_log(started_at DESC);


-- =============================================================================
-- Helper Functions
-- =============================================================================

-- Function to find caller by any phone number (caregiver or client)
-- Returns: type ('practitioner' or 'patient'), id, name, status
CREATE OR REPLACE FUNCTION identify_caller(phone_number VARCHAR)
RETURNS TABLE (
    caller_type VARCHAR,
    caller_id VARCHAR,
    caller_name VARCHAR,
    caller_status VARCHAR,
    caller_city VARCHAR
) AS $$
BEGIN
    -- Clean phone number (remove formatting)
    phone_number := regexp_replace(phone_number, '[^0-9]', '', 'g');

    -- Take last 10 digits (remove country code if present)
    IF length(phone_number) > 10 THEN
        phone_number := right(phone_number, 10);
    END IF;

    -- Check practitioners first (caregivers more likely to call)
    RETURN QUERY
    SELECT
        'practitioner'::VARCHAR,
        p.id,
        p.full_name,
        p.status,
        p.city
    FROM cached_practitioners p
    WHERE
        regexp_replace(p.phone, '[^0-9]', '', 'g') LIKE '%' || phone_number
        OR regexp_replace(p.home_phone, '[^0-9]', '', 'g') LIKE '%' || phone_number
        OR regexp_replace(p.work_phone, '[^0-9]', '', 'g') LIKE '%' || phone_number
    LIMIT 1;

    -- If not found, check patients
    IF NOT FOUND THEN
        RETURN QUERY
        SELECT
            'patient'::VARCHAR,
            pt.id,
            pt.full_name,
            pt.status,
            pt.city
        FROM cached_patients pt
        WHERE
            regexp_replace(pt.phone, '[^0-9]', '', 'g') LIKE '%' || phone_number
            OR regexp_replace(pt.home_phone, '[^0-9]', '', 'g') LIKE '%' || phone_number
            OR regexp_replace(pt.work_phone, '[^0-9]', '', 'g') LIKE '%' || phone_number
        LIMIT 1;
    END IF;

    RETURN;
END;
$$ LANGUAGE plpgsql;


-- =============================================================================
-- Usage Examples
-- =============================================================================

-- Fast caller ID lookup (< 5ms)
-- SELECT * FROM identify_caller('7195551234');

-- Find all active hired caregivers in Denver
-- SELECT * FROM cached_practitioners
-- WHERE is_hired = true AND is_active = true AND city = 'Denver';

-- Find stale data (needs re-sync)
-- SELECT COUNT(*) FROM cached_practitioners WHERE synced_at < NOW() - INTERVAL '25 hours';

-- Check last sync status
-- SELECT * FROM wellsky_sync_log ORDER BY started_at DESC LIMIT 5;
