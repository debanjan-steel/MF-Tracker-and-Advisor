-- Supabase PostgreSQL Schema for Mutual Fund Tracker & Advisor
-- Run this in your Supabase Dashboard SQL Editor (https://app.supabase.com/project/_/sql)
-- Note: Even without running this SQL, the app automatically persists all holdings,
-- alert settings, and preferences into Supabase GoTrue user_metadata.

CREATE TABLE IF NOT EXISTS public.user_holdings (
    id                  TEXT PRIMARY KEY,
    user_id             UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    scheme_code         INTEGER NOT NULL,
    scheme_name         TEXT NOT NULL,
    units               NUMERIC NOT NULL,
    avg_nav             NUMERIC NOT NULL,
    invested_amount     NUMERIC NOT NULL,
    category            TEXT DEFAULT 'Equity',
    folio_number        TEXT,
    investment_type     TEXT DEFAULT 'LUMPSUM',
    investment_date     TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, scheme_code)
);

-- Enable Row Level Security (RLS)
ALTER TABLE public.user_holdings ENABLE ROW LEVEL SECURITY;

-- Allow users to manage only their own portfolio holdings
CREATE POLICY "Users can manage their own holdings"
    ON public.user_holdings
    FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- Index for high-speed queries
CREATE INDEX IF NOT EXISTS idx_user_holdings_user ON public.user_holdings(user_id);

