-- CareBank initial schema for persistence + audit governance
create extension if not exists "pgcrypto";

create table if not exists profiles (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null unique,
    email text,
    created_at timestamptz not null default now()
);

create table if not exists transactions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null,
    amount numeric not null,
    transaction_type text not null default 'debit',
    category text not null default 'Uncategorized',
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists behavior_snapshots (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null,
    correlation_id text,
    idempotency_key text unique,
    snapshot jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists risk_snapshots (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null,
    correlation_id text,
    idempotency_key text unique,
    snapshot jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists guidance_snapshots (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null,
    correlation_id text,
    idempotency_key text unique,
    snapshot jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists financial_score_snapshots (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null,
    correlation_id text,
    idempotency_key text unique,
    snapshot jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists guidance_items (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null,
    correlation_id text,
    idempotency_key text unique,
    payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists risk_events (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null,
    correlation_id text,
    event_id text unique,
    payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists system_events (
    id uuid primary key default gen_random_uuid(),
    user_id uuid,
    event_id text not null unique,
    event_type text not null,
    correlation_id text,
    idempotency_key text unique,
    payload jsonb not null default '{}'::jsonb,
    status text not null default 'pending',
    created_at timestamptz not null default now()
);

create table if not exists processing_events (
    id uuid primary key default gen_random_uuid(),
    user_id uuid,
    event_id text not null,
    correlation_id text,
    idempotency_key text,
    payload jsonb not null default '{}'::jsonb,
    status text not null default 'processing',
    created_at timestamptz not null default now()
);

create table if not exists live_alert_events (
    id uuid primary key default gen_random_uuid(),
    user_id uuid,
    event_id text unique,
    correlation_id text,
    payload jsonb not null default '{}'::jsonb,
    status text not null default 'pending',
    expires_at timestamptz,
    archived_at timestamptz,
    created_at timestamptz not null default now()
);

create table if not exists dead_letter_events (
    id uuid primary key default gen_random_uuid(),
    user_id uuid,
    event_id text unique,
    correlation_id text,
    idempotency_key text,
    payload jsonb not null default '{}'::jsonb,
    status text not null default 'dlq',
    expires_at timestamptz,
    replayed_at timestamptz,
    created_at timestamptz not null default now()
);

create table if not exists event_replay_history (
    id uuid primary key default gen_random_uuid(),
    user_id uuid,
    original_event_id text not null,
    replayed_event_id text not null unique,
    correlation_id text,
    payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create table if not exists audit_logs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid null,
    audit_type text not null,
    severity text not null default 'info',
    metadata jsonb not null default '{}'::jsonb,
    expires_at timestamptz,
    archived_at timestamptz,
    created_at timestamptz not null default now()
);

create index if not exists idx_transactions_user_created on transactions(user_id, created_at desc);
create index if not exists idx_behavior_snapshots_user_created on behavior_snapshots(user_id, created_at desc);
create index if not exists idx_risk_snapshots_user_created on risk_snapshots(user_id, created_at desc);
create index if not exists idx_guidance_snapshots_user_created on guidance_snapshots(user_id, created_at desc);
create index if not exists idx_financial_score_snapshots_user_created on financial_score_snapshots(user_id, created_at desc);
create index if not exists idx_guidance_items_user_created on guidance_items(user_id, created_at desc);
create index if not exists idx_risk_events_user_created on risk_events(user_id, created_at desc);
create index if not exists idx_system_events_created on system_events(created_at desc);
create index if not exists idx_system_events_correlation on system_events(correlation_id);
create index if not exists idx_processing_events_created on processing_events(created_at desc);
create index if not exists idx_processing_events_correlation on processing_events(correlation_id);
create index if not exists idx_live_alert_events_created on live_alert_events(created_at desc);
create index if not exists idx_dead_letter_events_created on dead_letter_events(created_at desc);
create index if not exists idx_event_replay_history_created on event_replay_history(created_at desc);
create index if not exists idx_event_replay_history_correlation on event_replay_history(correlation_id);
create index if not exists idx_audit_logs_created on audit_logs(created_at desc);

alter table transactions enable row level security;
alter table behavior_snapshots enable row level security;
alter table risk_snapshots enable row level security;
alter table guidance_snapshots enable row level security;
alter table financial_score_snapshots enable row level security;
alter table guidance_items enable row level security;
alter table risk_events enable row level security;

create policy if not exists transactions_user_isolation_select on transactions for select using (user_id = auth.uid());
create policy if not exists transactions_user_isolation_insert on transactions for insert with check (user_id = auth.uid());
create policy if not exists transactions_user_isolation_update on transactions for update using (user_id = auth.uid()) with check (user_id = auth.uid());

create policy if not exists behavior_snapshots_user_isolation_select on behavior_snapshots for select using (user_id = auth.uid());
create policy if not exists behavior_snapshots_user_isolation_insert on behavior_snapshots for insert with check (user_id = auth.uid());
create policy if not exists behavior_snapshots_user_isolation_update on behavior_snapshots for update using (user_id = auth.uid()) with check (user_id = auth.uid());

create policy if not exists risk_snapshots_user_isolation_select on risk_snapshots for select using (user_id = auth.uid());
create policy if not exists risk_snapshots_user_isolation_insert on risk_snapshots for insert with check (user_id = auth.uid());
create policy if not exists risk_snapshots_user_isolation_update on risk_snapshots for update using (user_id = auth.uid()) with check (user_id = auth.uid());

create policy if not exists guidance_snapshots_user_isolation_select on guidance_snapshots for select using (user_id = auth.uid());
create policy if not exists guidance_snapshots_user_isolation_insert on guidance_snapshots for insert with check (user_id = auth.uid());
create policy if not exists guidance_snapshots_user_isolation_update on guidance_snapshots for update using (user_id = auth.uid()) with check (user_id = auth.uid());

create policy if not exists financial_score_snapshots_user_isolation_select on financial_score_snapshots for select using (user_id = auth.uid());
create policy if not exists financial_score_snapshots_user_isolation_insert on financial_score_snapshots for insert with check (user_id = auth.uid());
create policy if not exists financial_score_snapshots_user_isolation_update on financial_score_snapshots for update using (user_id = auth.uid()) with check (user_id = auth.uid());

create policy if not exists guidance_items_user_isolation_select on guidance_items for select using (user_id = auth.uid());
create policy if not exists guidance_items_user_isolation_insert on guidance_items for insert with check (user_id = auth.uid());
create policy if not exists guidance_items_user_isolation_update on guidance_items for update using (user_id = auth.uid()) with check (user_id = auth.uid());

create policy if not exists risk_events_user_isolation_select on risk_events for select using (user_id = auth.uid());
create policy if not exists risk_events_user_isolation_insert on risk_events for insert with check (user_id = auth.uid());
create policy if not exists risk_events_user_isolation_update on risk_events for update using (user_id = auth.uid()) with check (user_id = auth.uid());

-- System/audit tables remain service-role only by default (no broad authenticated policies).
