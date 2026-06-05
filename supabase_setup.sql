-- CIMSummarizer — Supabase setup
-- Run this SQL in your Supabase project's SQL Editor (Dashboard → SQL Editor → New query)

CREATE TABLE IF NOT EXISTS saved_summaries (
  id          uuid          DEFAULT gen_random_uuid() PRIMARY KEY,
  job_id      text          NOT NULL,
  deal_name   text          NOT NULL,
  sponsor_name text          DEFAULT '',
  saved_at    timestamptz   DEFAULT now() NOT NULL,
  summary     jsonb         NOT NULL
);

-- Index for fast list queries sorted by date
CREATE INDEX IF NOT EXISTS idx_saved_summaries_saved_at ON saved_summaries (saved_at DESC);

-- Optional: Row Level Security (disable for service-role key usage, enable if using anon key)
-- ALTER TABLE saved_summaries ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "service role full access" ON saved_summaries USING (true);
