-- ============================================================
-- BEACON Supabase Schema v3.2.2 — Production Final
-- Includes Migration Guards, RLS, Real-time, and Performance Tiers
-- ============================================================

-- STEP 1: MIGRATION SAFEGUARDS (Update existing tables)
ALTER TABLE audits   ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE;
ALTER TABLE scans    ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE pages    ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE;
ALTER TABLE issues   ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE;

-- STEP 2: CREATE TABLES (Safe idempotent creation)

-- 1. Audits Table
CREATE TABLE IF NOT EXISTS audits (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    scan_mode TEXT NOT NULL,
    site_score FLOAT DEFAULT 0.0,
    status TEXT DEFAULT 'completed',
    pages_audited INTEGER DEFAULT 1,
    pages_discovered INTEGER DEFAULT 1,
    total_duration_ms INTEGER DEFAULT 0,
    degraded_mode BOOLEAN DEFAULT FALSE,
    enrichment_status TEXT DEFAULT 'pending',
    schema_version TEXT DEFAULT '3.1',
    summary TEXT DEFAULT '',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE
);

-- 2. Pages Table
CREATE TABLE IF NOT EXISTS pages (
    id BIGSERIAL PRIMARY KEY,
    audit_id TEXT REFERENCES audits(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    score FLOAT DEFAULT 0.0,
    degraded_mode BOOLEAN DEFAULT FALSE,
    engine_timings JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE
);

-- 3. Issues Table
CREATE TABLE IF NOT EXISTS issues (
    id BIGSERIAL PRIMARY KEY,
    page_id BIGINT REFERENCES pages(id) ON DELETE CASCADE,
    audit_id TEXT REFERENCES audits(id) ON DELETE CASCADE,
    rule_id TEXT DEFAULT '',
    wcag_criterion TEXT DEFAULT '',
    severity TEXT DEFAULT 'moderate',
    confidence FLOAT DEFAULT 0.0,
    affected_pages INTEGER DEFAULT 1,
    enrichment_source TEXT DEFAULT 'pending',
    fix JSONB DEFAULT '{"proposed": null, "validated": false, "sandbox_result": "pending", "introduced_issues": []}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE
);

-- 4. Projects Table
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    description TEXT DEFAULT '',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_scan_at TIMESTAMP WITH TIME ZONE,
    latest_score FLOAT,
    total_issues INTEGER DEFAULT 0,
    deleted_at TIMESTAMP WITH TIME ZONE,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE
);

-- 5. Scans Table (Consolidated for Dashboard)
CREATE TABLE IF NOT EXISTS scans (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'scanning',
    url TEXT NOT NULL,
    scan_mode TEXT DEFAULT 'fast',
    score FLOAT,
    total_issues INTEGER DEFAULT 0,
    critical_issues INTEGER DEFAULT 0,
    serious_issues INTEGER DEFAULT 0,
    moderate_issues INTEGER DEFAULT 0,
    minor_issues INTEGER DEFAULT 0,
    summary TEXT DEFAULT '',
    ai_analysis TEXT DEFAULT '',
    issues JSONB DEFAULT '[]',
    groups JSONB DEFAULT '[]',
    priority_ranking JSONB DEFAULT '[]',
    trust JSONB DEFAULT '{}',
    engines_used JSONB DEFAULT '[]',
    scan_time_seconds FLOAT DEFAULT 0.0,
    pages_scanned INTEGER DEFAULT 1,
    pages_discovered INTEGER DEFAULT 1,
    scraped_pages JSONB DEFAULT '[]',
    degraded_mode BOOLEAN DEFAULT FALSE,
    degraded_reason TEXT,
    skipped_components JSONB DEFAULT '[]',
    enrichment_status TEXT DEFAULT 'pending',
    cognitive_scores JSONB,
    markdown_report TEXT DEFAULT '',
    site_topology TEXT,
    templates_found INTEGER,
    urls_discovered INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    lighthouse_enrichment JSONB,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE
);

-- 6. Usage Limits Table
CREATE TABLE IF NOT EXISTS usage_limits (
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE PRIMARY KEY,
    plan TEXT DEFAULT 'free',
    audits_this_month INTEGER DEFAULT 0,
    pages_per_audit INTEGER DEFAULT 10,
    last_reset_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- STEP 3: INDEXES (Performance Optimization)
CREATE INDEX IF NOT EXISTS idx_pages_audit_id       ON pages(audit_id);
CREATE INDEX IF NOT EXISTS idx_pages_user_id        ON pages(user_id);
CREATE INDEX IF NOT EXISTS idx_issues_audit_id      ON issues(audit_id);
CREATE INDEX IF NOT EXISTS idx_issues_user_id       ON issues(user_id);
CREATE INDEX IF NOT EXISTS idx_issues_severity      ON issues(severity);
CREATE INDEX IF NOT EXISTS idx_scans_project_id     ON scans(project_id);
CREATE INDEX IF NOT EXISTS idx_scans_user_id        ON scans(user_id);
CREATE INDEX IF NOT EXISTS idx_scans_status         ON scans(status);
CREATE INDEX IF NOT EXISTS idx_scans_created_at     ON scans(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_projects_user_id     ON projects(user_id);
CREATE INDEX IF NOT EXISTS idx_audits_user_id       ON audits(user_id);
CREATE INDEX IF NOT EXISTS idx_audits_created_at    ON audits(created_at DESC);

-- STEP 4: SECURITY & PERMISSIONS
REVOKE ALL ON projects     FROM anon;
REVOKE ALL ON scans        FROM anon;
REVOKE ALL ON audits       FROM anon;
REVOKE ALL ON pages        FROM anon;
REVOKE ALL ON issues       FROM anon;
REVOKE ALL ON usage_limits FROM anon;

GRANT SELECT, INSERT, UPDATE, DELETE ON projects     TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON scans        TO authenticated;
GRANT SELECT                         ON audits       TO authenticated;
GRANT SELECT                         ON pages        TO authenticated;
GRANT SELECT                         ON issues       TO authenticated;
GRANT SELECT                         ON usage_limits TO authenticated;

-- Backend (Python) full access
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;

-- Required for BIGSERIAL auto-increment on pages and issues
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO authenticated;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role;

-- STEP 5: ROW LEVEL SECURITY (RLS) policies
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Users see own projects" ON projects;
CREATE POLICY "Users see own projects" ON projects 
    FOR ALL USING (auth.uid() = user_id AND deleted_at IS NULL)
    WITH CHECK (auth.uid() = user_id);

ALTER TABLE scans ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Users see own scans" ON scans;
CREATE POLICY "Users see own scans" ON scans 
    FOR ALL USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

ALTER TABLE audits ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Users see own audits" ON audits;
CREATE POLICY "Users see own audits" ON audits 
    FOR SELECT USING (auth.uid() = user_id);

ALTER TABLE pages ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Users see own pages" ON pages;
CREATE POLICY "Users see own pages" ON pages 
    FOR SELECT USING (auth.uid() = user_id);

ALTER TABLE issues ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Users see own issues" ON issues;
CREATE POLICY "Users see own issues" ON issues 
    FOR SELECT USING (auth.uid() = user_id);

ALTER TABLE usage_limits ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Users see own limits" ON usage_limits;
CREATE POLICY "Users see own limits" ON usage_limits 
    FOR SELECT USING (auth.uid() = user_id);

-- STEP 6: REALTIME ENABLEMENT
-- Ensure realtime is active for status updates on the dashboard
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
        CREATE PUBLICATION supabase_realtime;
    END IF;
END $$;

ALTER PUBLICATION supabase_realtime ADD TABLE scans;
ALTER PUBLICATION supabase_realtime ADD TABLE audits;
