-- Run this script in your Supabase SQL editor to add trace_events and run_id columns
-- This enables persistence of agent reasoning/workflow traces with conversation messages

-- Add trace_events column to conversations table to preserve agent reasoning
ALTER TABLE conversations 
ADD COLUMN IF NOT EXISTS trace_events JSONB DEFAULT NULL;

-- Add index for faster queries on trace events
CREATE INDEX IF NOT EXISTS idx_conversations_trace_events ON conversations USING GIN (trace_events);

-- Add run_id column to associate messages with workflow runs
ALTER TABLE conversations 
ADD COLUMN IF NOT EXISTS run_id TEXT DEFAULT NULL;

-- Add index for run_id lookups
CREATE INDEX IF NOT EXISTS idx_conversations_run_id ON conversations (run_id);

-- Verify the columns were added
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'conversations' 
AND column_name IN ('trace_events', 'run_id');
