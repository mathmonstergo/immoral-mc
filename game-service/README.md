# Immortal MMO Game Service

FastAPI backend service for the Immortal Minecraft MMORPG. PostgreSQL is the
authoritative store; the local Compose service is disposable development
infrastructure only.

面向服主、内容作者和接入方的中文说明统一维护在
[ImmortalMC Wiki](../docs/wiki/index.md)。常用入口：
[API 参考](../docs/wiki/api-reference.md)、
[运维与故障排查](../docs/wiki/operations-and-troubleshooting.md)、
[任务系统](../docs/wiki/quests.md)和[修炼系统](../docs/wiki/cultivation.md)。
本 README 仅保留 Game Service 开发细节。

## Local setup

From the repository root:

```bash
cp game-service/.env.example game-service/.env
set -a
source game-service/.env
set +a
docker compose up -d --wait postgres
```

The Compose healthcheck waits for PostgreSQL on `127.0.0.1:5432`. The service
uses the strict `postgresql+asyncpg://` URL from `DATABASE_URL`.

## Install, migrate, and start

```bash
cd game-service
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/alembic upgrade head
.venv/bin/alembic current
cd ..
./scripts/start-game-service.sh
```

`start-game-service.sh` requires the prepared `.venv` and `DATABASE_URL`, then
starts `immortal_mmo.entrypoint:app`. It does not install dependencies or run
migrations. Run the setup and migration commands explicitly after creating a
new database or applying a migration.

Open the API documentation at <http://127.0.0.1:8000/docs>.

## MythicMobs reward catalog

Combat rewards are authoritative in Game Service. Paper submits amount-free
kill facts to:

```http
POST /api/v1/combat/mythicmob-kills/batch
```

The exact MythicMobs top-level/internal name is resolved through
`src/immortal_mmo/combat/mythicmob_rewards.json`. Unknown IDs return the stable
`not_rewardable` result; they never receive a fallback amount. Catalog changes
are startup content changes, so restart Game Service after editing and keep the
Mythic YAML key and catalog `internal_name` identical.

## Cultivation progression

Game Service owns the 22-level realm catalog, common technique definitions,
unrefined reserve, technique-backed realized cultivation, seclusion sessions,
realm-entry history, regression, and the initial 练气 -> 筑基 breakthrough.

Key endpoints:

```http
GET  /api/v1/players/{account_id}/current-life/cultivation
GET  /api/v1/players/{account_id}/current-life/cultivation/techniques
POST /api/v1/players/{account_id}/current-life/cultivation/seclusions
GET  /api/v1/players/{account_id}/current-life/cultivation/seclusions/{session_id}
POST /api/v1/players/{account_id}/current-life/cultivation/seclusions/{session_id}/settle
POST /api/v1/players/{account_id}/current-life/cultivation/breakthroughs
GET  /api/v1/players/{account_id}/current-life/cultivation/breakthroughs/{session_id}
POST /api/v1/players/{account_id}/current-life/cultivation/breakthroughs/{session_id}/settle
```

Mutation starts require `Idempotency-Key: <UUID>`. Monster rewards add only
unrefined reserve. Ordinary seclusion consumes reserve and retains cultivation
only where selected techniques have capacity. Abandoning a technique removes
the same realized cultivation and may invalidate realm entries across major
realms; it never changes the unrefined reserve.

The current common-technique model supports nine retained `qi` techniques and
five per later exact-level group. Authored cross-realm techniques such as the
future 青元剑诀 progression model and live combat effects are intentionally not
implemented here. Learned-technique snapshots include catalog-derived display
names, attribute codes, and the layer projected from retained investment for
Paper's seclusion GUI.

Invalid seclusion selections, conflicting active sessions/idempotency keys,
unknown or wrong-kind session IDs, too-early settlements, and insufficient
breakthrough items return stable structured 4xx domain errors. They never leak
raw repository or Python exceptions as HTTP 500 responses.

The initial breakthrough catalog is
`src/immortal_mmo/cultivation/breakthrough_rules.json`. One-to-three roots use
the guaranteed one-pill profile; four- and five-root curves are independent
explicit basis-point tables. Failed loss outcomes use a frozen HMAC-SHA256
partition of `floor(source max_exp / 3)` and persist every per-technique debit.

## Disposable development reset

This permanently deletes the local PostgreSQL volume and all development data:

```bash
docker compose down -v
docker compose up -d --wait postgres
cd game-service
.venv/bin/alembic upgrade head
.venv/bin/alembic current
cd ..
```

## Backup and isolated restore

Create a custom-format dump from the running local database:

```bash
docker compose exec -T postgres pg_dump -U immortal -d immortal -Fc > /tmp/immortal-dev.dump
```

Restore it into a separate database in the same local PostgreSQL container:

```bash
docker compose exec -T postgres dropdb --if-exists -U immortal immortal_restore
docker compose exec -T postgres createdb -U immortal -O immortal immortal_restore
docker compose exec -T postgres pg_restore --exit-on-error -U immortal -d immortal_restore < /tmp/immortal-dev.dump
```

Verify the restored database revision before starting a service against it:

```bash
export DATABASE_URL=postgresql+asyncpg://immortal:immortal_dev_only@127.0.0.1:5432/immortal_restore
cd game-service
.venv/bin/alembic current
cd ..
```

Start the service with that restored URL in a separate terminal:

```bash
DATABASE_URL=postgresql+asyncpg://immortal:immortal_dev_only@127.0.0.1:5432/immortal_restore ./scripts/start-game-service.sh
```

## Restart and restore smoke

Run the service in Terminal A, and run the following from Terminal B. Keep the
same UUIDs and idempotency keys across every restart; the response body files
are the byte-level replay checks.

```bash
MINECRAFT_UUID=00000000-0000-0000-0000-000000000077
LOGIN_BODY=$(curl -fsS -X POST http://127.0.0.1:8000/api/v1/players/login \
  -H 'content-type: application/json' \
  -d "{\"minecraft_uuid\":\"$MINECRAFT_UUID\",\"player_name\":\"SmokePlayer\"}")
ACCOUNT_ID=$(printf '%s' "$LOGIN_BODY" | python3 -c 'import json,sys; print(json.load(sys.stdin)["account"]["account_id"])')

printf '%s' "$LOGIN_BODY" > /tmp/login-before.json
curl -fsS -X POST "http://127.0.0.1:8000/api/v1/players/$ACCOUNT_ID/current-life/spirit-root" > /tmp/root-before.json
curl -fsS -X PUT "http://127.0.0.1:8000/api/v1/players/$ACCOUNT_ID/current-life/quests/first-steps/accept" \
  -H 'content-type: application/json' -H 'Idempotency-Key: 00000000-0000-0000-0000-000000000078' \
  -d '{"provider_id":"old-man"}' > /tmp/accept-before.json
```

Stop Terminal A with `Ctrl-C`, start it again with the same `DATABASE_URL`,
then run this from Terminal B to save the second responses:

```bash
LOGIN_AFTER=$(curl -fsS -X POST http://127.0.0.1:8000/api/v1/players/login \
  -H 'content-type: application/json' \
  -d "{\"minecraft_uuid\":\"$MINECRAFT_UUID\",\"player_name\":\"SmokePlayer\"}")
printf '%s' "$LOGIN_AFTER" > /tmp/login-after.json
curl -fsS -X POST "http://127.0.0.1:8000/api/v1/players/$ACCOUNT_ID/current-life/spirit-root" > /tmp/root-after.json
curl -fsS -X PUT "http://127.0.0.1:8000/api/v1/players/$ACCOUNT_ID/current-life/quests/first-steps/accept" \
  -H 'content-type: application/json' -H 'Idempotency-Key: 00000000-0000-0000-0000-000000000078' \
  -d '{"provider_id":"old-man"}' > /tmp/accept-after.json
```

Assert the account/life identity and frozen accept response are unchanged. The
first login happened before root detection, so its initial `spirit_root: null`
must not be compared with the post-restart login snapshot:

```bash
cmp /tmp/accept-before.json /tmp/accept-after.json
python3 -c 'import json; before=json.load(open("/tmp/login-before.json")); after=json.load(open("/tmp/login-after.json")); root_before=json.load(open("/tmp/root-before.json")); root_after=json.load(open("/tmp/root-after.json")); assert before["account"]["account_id"] == after["account"]["account_id"]; assert before["current_life"]["life_id"] == after["current_life"]["life_id"]; assert root_after["already_detected"] is True; assert root_before["spirit_root"] == root_after["spirit_root"]'
```

Turn in, restart once more, and replay the same turn-in operation:

```bash
curl -fsS -X PUT "http://127.0.0.1:8000/api/v1/players/$ACCOUNT_ID/current-life/quests/first-steps/turn-in" \
  -H 'content-type: application/json' -H 'Idempotency-Key: 00000000-0000-0000-0000-000000000079' \
  -d '{"provider_id":"old-man"}' > /tmp/turn-in-before.json
# Restart Terminal A with the same DATABASE_URL, then run the identical command again:
curl -fsS -X PUT "http://127.0.0.1:8000/api/v1/players/$ACCOUNT_ID/current-life/quests/first-steps/turn-in" \
  -H 'content-type: application/json' -H 'Idempotency-Key: 00000000-0000-0000-0000-000000000079' \
  -d '{"provider_id":"old-man"}' > /tmp/turn-in-after.json
cmp /tmp/turn-in-before.json /tmp/turn-in-after.json
```

After the source-database smoke succeeds, create the dump and isolated restore
using the commands above. With `DATABASE_URL` pointing to `immortal_restore`,
stop the source-database service in Terminal A with `Ctrl-C`, then verify the
revision and start a fresh service process in Terminal A:

```bash
cd game-service
.venv/bin/alembic current
cd ..
DATABASE_URL=postgresql+asyncpg://immortal:immortal_dev_only@127.0.0.1:5432/immortal_restore ./scripts/start-game-service.sh
```

In Terminal B, replay the same durable reads and operation IDs against the
restored database:

```bash
MINECRAFT_UUID=00000000-0000-0000-0000-000000000077
LOGIN_RESTORED=$(curl -fsS -X POST http://127.0.0.1:8000/api/v1/players/login \
  -H 'content-type: application/json' \
  -d "{\"minecraft_uuid\":\"$MINECRAFT_UUID\",\"player_name\":\"SmokePlayer\"}")
printf '%s' "$LOGIN_RESTORED" > /tmp/login-restored.json
RESTORED_ACCOUNT_ID=$(printf '%s' "$LOGIN_RESTORED" | python3 -c 'import json,sys; print(json.load(sys.stdin)["account"]["account_id"])')

curl -fsS -X POST "http://127.0.0.1:8000/api/v1/players/$RESTORED_ACCOUNT_ID/current-life/spirit-root" > /tmp/root-restored.json
curl -fsS -X PUT "http://127.0.0.1:8000/api/v1/players/$RESTORED_ACCOUNT_ID/current-life/quests/first-steps/accept" \
  -H 'content-type: application/json' -H 'Idempotency-Key: 00000000-0000-0000-0000-000000000078' \
  -d '{"provider_id":"old-man"}' > /tmp/accept-restored.json
curl -fsS -X PUT "http://127.0.0.1:8000/api/v1/players/$RESTORED_ACCOUNT_ID/current-life/quests/first-steps/turn-in" \
  -H 'content-type: application/json' -H 'Idempotency-Key: 00000000-0000-0000-0000-000000000079' \
  -d '{"provider_id":"old-man"}' > /tmp/turn-in-restored.json

cmp /tmp/login-after.json /tmp/login-restored.json
cmp /tmp/accept-before.json /tmp/accept-restored.json
cmp /tmp/turn-in-before.json /tmp/turn-in-restored.json
python3 -c 'import json; before=json.load(open("/tmp/root-after.json")); restored=json.load(open("/tmp/root-restored.json")); assert restored["already_detected"] is True; assert restored["spirit_root"] == before["spirit_root"]'
```

All comparisons must succeed; otherwise the restore drill is incomplete.
