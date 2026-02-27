-- Gigi Evaluation Pipeline — stores LLM-judged quality scores for Gigi responses
CREATE TABLE IF NOT EXISTS gigi_evaluations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id INTEGER,
    channel TEXT NOT NULL,
    user_message TEXT NOT NULL,
    gigi_response TEXT NOT NULL,
    accuracy_score SMALLINT,
    helpfulness_score SMALLINT,
    tone_score SMALLINT,
    tool_selection_score SMALLINT,
    safety_score SMALLINT,
    overall_score DECIMAL(3,2),
    response_latency_ms INTEGER,
    justification JSONB,
    tools_used TEXT[],
    mode_at_time TEXT,
    judge_model TEXT,
    evaluated_at TIMESTAMP DEFAULT NOW(),
    sms_draft_id INTEGER,
    wellsky_accuracy DECIMAL(3,2),
    wellsky_refs_checked INTEGER DEFAULT 0,
    wellsky_refs_correct INTEGER DEFAULT 0,
    flagged BOOLEAN DEFAULT false,
    flag_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_eval_channel ON gigi_evaluations(channel, evaluated_at DESC);
CREATE INDEX IF NOT EXISTS idx_eval_flagged ON gigi_evaluations(flagged) WHERE flagged = true;
CREATE INDEX IF NOT EXISTS idx_eval_overall ON gigi_evaluations(overall_score);
CREATE INDEX IF NOT EXISTS idx_eval_conv_id ON gigi_evaluations(conversation_id);
