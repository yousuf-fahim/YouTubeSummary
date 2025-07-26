-- Create the schema for YouTube summaries application

-- Table for storing transcripts
CREATE TABLE public.transcripts (
  id SERIAL PRIMARY KEY,
  video_id VARCHAR(20) NOT NULL UNIQUE,
  title VARCHAR(255) NOT NULL,
  channel VARCHAR(255) NOT NULL,
  transcript_text TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for faster lookup by video_id
CREATE INDEX idx_transcripts_video_id ON public.transcripts(video_id);

-- Table for storing summaries
CREATE TABLE public.summaries (
  id SERIAL PRIMARY KEY,
  video_id VARCHAR(20) NOT NULL UNIQUE,
  summary_text TEXT NOT NULL,
  title VARCHAR(255),
  points JSONB,
  noteworthy_mentions JSONB,
  verdict VARCHAR(512),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for faster lookup by video_id
CREATE INDEX idx_summaries_video_id ON public.summaries(video_id);

-- Table for storing configuration
CREATE TABLE public.config (
  id SERIAL PRIMARY KEY,
  openai_api_key VARCHAR(255),
  webhooks JSONB,
  prompts JSONB,
  webhook_auth_token VARCHAR(255),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Limit to one config row using a trigger
CREATE OR REPLACE FUNCTION prevent_multiple_configs()
RETURNS TRIGGER AS $$
BEGIN
  IF (SELECT COUNT(*) FROM public.config) > 0 AND NEW.id IS NULL THEN
    RAISE EXCEPTION 'Only one configuration row is allowed';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER enforce_single_config
BEFORE INSERT ON public.config
FOR EACH ROW EXECUTE PROCEDURE prevent_multiple_configs();

-- Table for storing tracked YouTube channels
CREATE TABLE public.tracked_channels (
  id SERIAL PRIMARY KEY,
  channel VARCHAR(255) NOT NULL UNIQUE,
  last_video_id VARCHAR(20),
  last_video_title VARCHAR(255),
  last_video_published VARCHAR(255),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for faster lookup by channel
CREATE INDEX idx_tracked_channels_channel ON public.tracked_channels(channel); 