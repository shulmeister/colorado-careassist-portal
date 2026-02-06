-- WellSky Cache Tables
-- Stores periodic snapshots of WellSky data for fast local queries
-- Synced every 2 hours via wellsky_sync.py

-- Clients cache
CREATE TABLE IF NOT EXISTS wellsky_clients_cache (
    id SERIAL PRIMARY KEY,
    wellsky_id VARCHAR(255) UNIQUE NOT NULL,

    -- Basic info
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    preferred_name VARCHAR(255),
    email VARCHAR(255),
    phone VARCHAR(50),
    mobile_phone VARCHAR(50),

    -- Address
    address_line1 VARCHAR(255),
    address_line2 VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(50),
    zip_code VARCHAR(20),

    -- Status
    status VARCHAR(50),  -- active, pending, discharged, etc.
    start_date DATE,
    discharge_date DATE,

    -- Additional fields
    birth_date DATE,
    gender VARCHAR(20),
    emergency_contact_name VARCHAR(255),
    emergency_contact_phone VARCHAR(50),

    -- Metadata
    raw_data JSONB,  -- Full WellSky response
    last_synced_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_wellsky_clients_wellsky_id ON wellsky_clients_cache(wellsky_id);
CREATE INDEX idx_wellsky_clients_status ON wellsky_clients_cache(status);
CREATE INDEX idx_wellsky_clients_name ON wellsky_clients_cache(last_name, first_name);
CREATE INDEX idx_wellsky_clients_synced ON wellsky_clients_cache(last_synced_at);

-- Caregivers cache
CREATE TABLE IF NOT EXISTS wellsky_caregivers_cache (
    id SERIAL PRIMARY KEY,
    wellsky_id VARCHAR(255) UNIQUE NOT NULL,

    -- Basic info
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    preferred_name VARCHAR(255),
    email VARCHAR(255),
    phone VARCHAR(50),
    mobile_phone VARCHAR(50),

    -- Address
    address_line1 VARCHAR(255),
    address_line2 VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(50),
    zip_code VARCHAR(20),

    -- Status
    status VARCHAR(50),  -- active, inactive, pending, etc.
    hire_date DATE,
    termination_date DATE,

    -- Additional fields
    birth_date DATE,
    certifications TEXT[],
    languages TEXT[],

    -- Metadata
    raw_data JSONB,  -- Full WellSky response
    last_synced_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_wellsky_caregivers_wellsky_id ON wellsky_caregivers_cache(wellsky_id);
CREATE INDEX idx_wellsky_caregivers_status ON wellsky_caregivers_cache(status);
CREATE INDEX idx_wellsky_caregivers_name ON wellsky_caregivers_cache(last_name, first_name);
CREATE INDEX idx_wellsky_caregivers_synced ON wellsky_caregivers_cache(last_synced_at);

-- Shifts/Appointments cache
CREATE TABLE IF NOT EXISTS wellsky_shifts_cache (
    id SERIAL PRIMARY KEY,
    wellsky_id VARCHAR(255) UNIQUE NOT NULL,

    -- References
    client_wellsky_id VARCHAR(255),
    caregiver_wellsky_id VARCHAR(255),

    -- Schedule
    scheduled_start TIMESTAMP,
    scheduled_end TIMESTAMP,
    actual_start TIMESTAMP,
    actual_end TIMESTAMP,

    -- Status
    status VARCHAR(50),  -- scheduled, confirmed, in_progress, completed, missed, cancelled

    -- Location
    location_address VARCHAR(500),

    -- Additional fields
    service_type VARCHAR(100),
    notes TEXT,

    -- Metadata
    raw_data JSONB,  -- Full WellSky response
    last_synced_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_wellsky_shifts_wellsky_id ON wellsky_shifts_cache(wellsky_id);
CREATE INDEX idx_wellsky_shifts_client ON wellsky_shifts_cache(client_wellsky_id);
CREATE INDEX idx_wellsky_shifts_caregiver ON wellsky_shifts_cache(caregiver_wellsky_id);
CREATE INDEX idx_wellsky_shifts_status ON wellsky_shifts_cache(status);
CREATE INDEX idx_wellsky_shifts_scheduled ON wellsky_shifts_cache(scheduled_start, scheduled_end);
CREATE INDEX idx_wellsky_shifts_synced ON wellsky_shifts_cache(last_synced_at);

-- Sync status tracking
CREATE TABLE IF NOT EXISTS wellsky_sync_status (
    id SERIAL PRIMARY KEY,
    sync_type VARCHAR(50) NOT NULL,  -- 'clients', 'caregivers', 'shifts'
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status VARCHAR(50) NOT NULL,  -- 'running', 'success', 'failed'
    records_processed INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_wellsky_sync_type ON wellsky_sync_status(sync_type);
CREATE INDEX idx_wellsky_sync_started ON wellsky_sync_status(started_at);
