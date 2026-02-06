-- Voice Brain Simulation Testing System
-- Stores automated test results with evaluation scores

CREATE TABLE IF NOT EXISTS gigi_simulations (
    id SERIAL PRIMARY KEY,
    scenario_id VARCHAR(100) NOT NULL,
    scenario_name VARCHAR(255) NOT NULL,
    call_id VARCHAR(255) UNIQUE NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',

    -- Execution timing
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds INTEGER,

    -- Conversation data
    transcript TEXT,
    transcript_json JSONB,
    turn_count INTEGER DEFAULT 0,

    -- Tool tracking
    tool_calls_json JSONB,
    expected_tools JSONB,
    tools_used JSONB,

    -- Evaluation scores
    tool_score INTEGER,
    behavior_score INTEGER,
    overall_score INTEGER,
    evaluation_details JSONB,

    -- Metadata
    launched_by VARCHAR(255),
    user_simulator_model VARCHAR(100) DEFAULT 'gemini-2.0-flash-exp',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_simulations_scenario ON gigi_simulations(scenario_id);
CREATE INDEX IF NOT EXISTS idx_simulations_status ON gigi_simulations(status);
CREATE INDEX IF NOT EXISTS idx_simulations_created ON gigi_simulations(created_at);

-- Add comment
COMMENT ON TABLE gigi_simulations IS 'Voice Brain simulation test results with automated evaluation';
