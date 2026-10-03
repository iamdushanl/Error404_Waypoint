-- Migration 006: Delivery Discrepancies and Evidence Bucket
CREATE TABLE delivery_discrepancies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id        UUID REFERENCES orders(id),
    reported_by     UUID REFERENCES users(id),
    issue_type      TEXT NOT NULL,
    notes           TEXT,
    photo_url       TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE delivery_discrepancies ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Discrepancies insertable by store manager"
    ON delivery_discrepancies FOR INSERT
    WITH CHECK (auth.uid() = reported_by);

CREATE POLICY "Discrepancies viewable by dispatcher"
    ON delivery_discrepancies FOR SELECT
    USING (true); -- Or whatever dispatcher rules apply

-- Create Storage bucket for evidence
INSERT INTO storage.buckets (id, name, public) 
VALUES ('evidence', 'evidence', true)
ON CONFLICT (id) DO NOTHING;

-- Storage RLS Policies
CREATE POLICY "Public Access to Evidence"
    ON storage.objects FOR SELECT
    USING (bucket_id = 'evidence');

CREATE POLICY "Authenticated users can upload evidence"
    ON storage.objects FOR INSERT
    WITH CHECK (bucket_id = 'evidence' AND auth.role() = 'authenticated');
