# BRAIN 3.0 — First Deploy Checklist

One-time checklist for the initial production deployment. See `deployment.md` for detailed instructions.

## Environment Setup

- [ ] TrueNAS Docker environment is running (`docker --version`)
- [ ] Repository cloned and on `develop` branch
- [ ] `.env` created from `.env.production.example`
- [ ] `POSTGRES_PASSWORD` set to a strong, unique value
- [ ] `BACKUP_PATH` configured to a TrueNAS dataset
- [ ] Backup directory created (`mkdir -p $BACKUP_PATH`)

## Start the Stack

- [ ] `docker compose -f docker-compose.prod.yml up -d --build` completes without errors
- [ ] `docker compose -f docker-compose.prod.yml ps` shows both `brain3-db` and `brain3-api` healthy
- [ ] API logs show successful migration and startup: `docker compose -f docker-compose.prod.yml logs api`

## Verify API

- [ ] Health endpoint responds: `curl http://localhost:8000/health` returns `{"status":"healthy","database":"connected"}`
- [ ] API docs accessible at `http://TRUENAS_IP:8000/docs`

## Smoke Test

- [ ] `./scripts/smoke-test.sh http://localhost:8000` passes all steps (exit code 0)

## Backup

- [ ] Manual backup succeeds: `./scripts/backup.sh`
- [ ] Backup file exists in `BACKUP_PATH`: `ls -la $BACKUP_PATH/brain3_*.sql.gz`
- [ ] Cron job configured in TrueNAS UI (daily at 2:00 AM)
- [ ] Verify cron ran successfully the following day (check `backup.log`)

## MCP Connectivity

- [ ] `BRAIN3_API_URL` set to `http://TRUENAS_IP:8000` in MCP config on client machine
- [ ] MCP `health_check` tool returns healthy through Claude
- [ ] End-to-end test: create a domain through Claude MCP conversation

## Resilience

- [ ] Restart API container: `docker restart brain3-api` — API recovers and serves requests
- [ ] Restart DB container: `docker restart brain3-db` — API reconnects after DB is healthy
- [ ] Full stack restart: `docker compose -f docker-compose.prod.yml restart` — both services recover
