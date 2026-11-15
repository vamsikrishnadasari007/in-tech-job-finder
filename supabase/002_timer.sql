-- Migration 002: the 30-minute timer. Supabase's pg_cron calls the website's /api/tick, which
-- starts the GitHub scrape workflow (GitHub's own cron skips runs on new repos).
-- Replace __CRON_SECRET__ with the CRON_SECRET value (the filled-in copy is 002_timer.local.sql,
-- which is gitignored) and __SITE__ with the Vercel address. Safe to re-run.
-- Undo:  select cron.unschedule('jobfinder-in-quick'); select cron.unschedule('jobfinder-in-full');

create extension if not exists pg_cron;
create extension if not exists pg_net;

delete from vault.secrets where name = 'jobfinder_in_cron_secret';
select vault.create_secret('__CRON_SECRET__', 'jobfinder_in_cron_secret');

create or replace function jobfinder_in.tick(mode text default 'quick') returns bigint
language sql security definer set search_path = '' as $$
  select net.http_post(
    url     := 'https://__SITE__/api/tick?mode=' || mode,
    headers := jsonb_build_object(
                 'Content-Type', 'application/json',
                 'Authorization', 'Bearer ' || (select decrypted_secret from vault.decrypted_secrets
                                                where name = 'jobfinder_in_cron_secret')),
    body    := '{}'::jsonb
  );
$$;
revoke all on function jobfinder_in.tick(text) from public, anon, authenticated;

-- Every 30 minutes at :22 and :52 (the Philippines finder uses :07 / :37, so they never overlap),
-- and the nightly full sweep at 2:17 AM India time (20:47 UTC).
select cron.unschedule(jobid) from cron.job where jobname in ('jobfinder-in-quick', 'jobfinder-in-full');
select cron.schedule('jobfinder-in-quick', '22,52 * * * *', $$select jobfinder_in.tick('quick')$$);
select cron.schedule('jobfinder-in-full',  '47 20 * * *',   $$select jobfinder_in.tick('full')$$);

-- Check it:  select jobname, schedule, active from cron.job where jobname like 'jobfinder-in%';
