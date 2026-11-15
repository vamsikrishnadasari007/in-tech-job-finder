-- India tech job finder: database objects, all inside their own schema `jobfinder_in`.
-- Nothing here touches the public / JARVIS tables or the Philippines `jobfinder` schema.
-- Safe to re-run (idempotent).  Undo everything with:  drop schema jobfinder_in cascade;

create schema if not exists jobfinder_in;

-- ------------------------------------------------------------------------------------
-- One row per job per platform.
-- ------------------------------------------------------------------------------------
create table if not exists jobfinder_in.postings (
  id               text primary key,                 -- 'naukri:141025025347'
  platform         text not null,
  platform_id      text not null,
  title            text not null,
  company          text not null default '',
  url              text not null,
  location         text not null default '',
  areas            text[] not null default '{}',     -- Bengaluru / Hyderabad / Remote / ...
  address          text not null default '',
  salary           text not null default '',
  work_type        text not null default '',
  work_mode        text not null default '',         -- Office / Hybrid / Remote
  company_url      text not null default '',
  description      text not null default '',
  has_description  boolean generated always as (length(description) > 200) stored,
  posted_at        timestamptz,
  posted_precision text not null default 'exact' check (posted_precision in ('exact', 'hour', 'date', 'seen')),
  roles            text[] not null default '{}',
  skills           text[] not null default '{}',
  flags            text[] not null default '{}',     -- 'Bond: 2 years', 'Via consultancy'
  is_internship    boolean not null default false,
  exp_min          real,
  exp_max          real,
  experience       text not null default '',         -- 'Freshers welcome' / '1 year asked' / 'Internship' / ...
  exp_range        text not null default '',         -- '0–2 yrs'
  emails           text[] not null default '{}',
  phones           text[] not null default '{}',
  hidden_reason    text,                             -- null = shown
  dedupe_key       text not null,
  first_seen       timestamptz not null default now(),
  last_seen        timestamptz not null default now(),
  is_active        boolean not null default true,
  updated_at       timestamptz not null default now()
);
create index if not exists postings_feed_idx     on jobfinder_in.postings (is_active, posted_at desc) where hidden_reason is null;
create index if not exists postings_dedupe_idx   on jobfinder_in.postings (dedupe_key);
create index if not exists postings_platform_idx on jobfinder_in.postings (platform, last_seen);

-- Saved / Applied marks, keyed by dedupe_key so a mark survives across platforms.
create table if not exists jobfinder_in.job_status (
  dedupe_key  text primary key,
  saved       boolean not null default false,
  applied     boolean not null default false,
  applied_at  timestamptz,
  note        text not null default '',
  updated_at  timestamptz not null default now()
);

-- One row per source per scraper run (freshness + health on the website).
create table if not exists jobfinder_in.scrape_runs (
  id          bigint generated always as identity primary key,
  source      text not null,
  mode        text not null check (mode in ('quick', 'full')),
  started_at  timestamptz not null default now(),
  finished_at timestamptz,
  fetched     int not null default 0,
  new_count   int not null default 0,
  ok          boolean,
  error       text not null default ''
);
create index if not exists scrape_runs_source_idx on jobfinder_in.scrape_runs (source, started_at desc);

-- Small key/value store: role groups, cities, extra links (written by the scraper).
create table if not exists jobfinder_in.meta (
  key        text primary key,
  value      jsonb not null,
  updated_at timestamptz not null default now()
);

-- ------------------------------------------------------------------------------------
-- What the website shows: visible, active jobs from the last 15 days, one row per dedupe_key
-- (main copy: company site > Naukri > foundit > ... > LinkedIn), the other copies as also_on.
-- ------------------------------------------------------------------------------------
create or replace view jobfinder_in.feed with (security_invoker = true) as
with vis as (
  select p.*,
         row_number() over (
           partition by p.dedupe_key
           order by case p.platform when 'Company site' then 0 when 'Naukri' then 1 when 'foundit' then 2
                                     when 'Instahyre' then 3 when 'Internshala' then 4 when 'Indeed' then 5
                                     when 'Glassdoor' then 6 when 'LinkedIn' then 7 else 9 end,
                    p.posted_at desc nulls last
         ) as rn
  from jobfinder_in.postings p
  where p.is_active and p.hidden_reason is null
    and p.posted_at > now() - interval '15 days'
)
select m.id, m.platform, m.platform_id, m.title, m.company, m.url, m.location, m.areas, m.address,
       m.salary, m.work_type, m.work_mode, m.company_url, left(m.description, 6000) as description,
       m.posted_at, m.posted_precision, m.roles, m.skills, m.flags, m.is_internship, m.experience, m.exp_range,
       m.emails, m.phones, m.dedupe_key, m.first_seen,
       coalesce((select jsonb_agg(jsonb_build_object('platform', o.platform, 'url', o.url))
                 from vis o where o.dedupe_key = m.dedupe_key and o.rn > 1), '[]'::jsonb) as also_on
from vis m
where m.rn = 1;

-- Jobs removed (senior, outside India, asks for money): shown in the "Hidden" tab.
-- "not a developer role" is only counted, not listed (there are far too many).
create or replace view jobfinder_in.hidden with (security_invoker = true) as
select id, platform, platform_id, title, company, url, location, areas, address, salary, work_type, work_mode,
       left(description, 3000) as description, posted_at, posted_precision, roles, skills, flags, is_internship,
       experience, exp_range, emails, phones, dedupe_key, first_seen, hidden_reason, '[]'::jsonb as also_on
from jobfinder_in.postings
where is_active and hidden_reason is not null
  and hidden_reason in ('senior / too much experience required', 'outside India', 'asks for money / paid training')
  and posted_at > now() - interval '15 days';

create or replace view jobfinder_in.hidden_counts with (security_invoker = true) as
select hidden_reason, count(*)::int as n
from jobfinder_in.postings
where is_active and hidden_reason is not null and posted_at > now() - interval '15 days'
group by hidden_reason;

-- Latest run per source (for "Updated 12 min ago · Naukri ✓").
create or replace view jobfinder_in.source_status with (security_invoker = true) as
select distinct on (source) source, mode, started_at, finished_at, fetched, new_count, ok, error,
       (select max(r2.finished_at) from jobfinder_in.scrape_runs r2
         where r2.source = r.source and r2.ok) as last_ok_at
from jobfinder_in.scrape_runs r
order by source, started_at desc;

-- ------------------------------------------------------------------------------------
-- Security: RLS on, no policies. Only the service-role key (scraper + website API, both
-- server side) can read or write.
-- ------------------------------------------------------------------------------------
alter table jobfinder_in.postings    enable row level security;
alter table jobfinder_in.job_status  enable row level security;
alter table jobfinder_in.scrape_runs enable row level security;
alter table jobfinder_in.meta        enable row level security;

revoke all on schema jobfinder_in from anon, authenticated;
grant usage on schema jobfinder_in to service_role;
grant all on all tables in schema jobfinder_in to service_role;
grant all on all sequences in schema jobfinder_in to service_role;
alter default privileges in schema jobfinder_in grant all on tables to service_role;
alter default privileges in schema jobfinder_in grant all on sequences to service_role;

notify pgrst, 'reload schema';
-- After running this: Project Settings → API → "Exposed schemas" → add jobfinder_in.
