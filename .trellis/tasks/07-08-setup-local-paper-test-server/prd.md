# Setup Local Paper Test Server

## Goal

Prepare a local Paper `1.21.11` test server under `minecraft-nodes/main-server/`
with the current ImmortalMC adapter plugin installed, so the user can launch a
Windows Minecraft client and test `/immortal health` plus `/immortal spirit-root`.

## What I already know

* The plugin target is Paper `1.21.11`.
* The current adapter plugin jar is built from `minecraft-nodes/main-plugin/`.
* The plugin expects Game Service at `http://127.0.0.1:8000` by default.
* The user wants Windows Minecraft client testing while the server can run from
  WSL.
* WSL memory should be watched, but earlier Gradle work stayed around 10 GiB
  available with no swap usage.
* Windows `localhost:25549` does not forward to this WSL Paper port on this
  machine; Windows client testing should use the WSL IP and port `25549`.
* Java 21 `HttpClient` can attempt h2c upgrade for plain HTTP; Game Service
  requests from the Adapter must force HTTP/1.1 so FastAPI receives the body.
* Adapter debug/status events should be visible in Paper logs rather than
  player chat.

## Requirements

* Create `minecraft-nodes/main-server/` as local Paper server runtime.
* Download the stable Paper `1.21.11` server jar.
* Add `eula.txt` with `eula=true` for local testing.
* Add basic `server.properties` suitable for local Windows client testing.
* Build or reuse the current adapter plugin jar.
* Copy the plugin jar into `minecraft-nodes/main-server/plugins/`.
* Provide exact commands to start Game Service and Paper server.
* Do not start a long-running Paper server unless explicitly useful for a quick
  smoke test.
* Keep local Paper runtime artifacts ignored; track only lightweight docs and
  reusable config templates.
* Use server-side logs for plugin testability:
  * player login sync success/failure
  * diagnostic health checks
  * temporary spirit-root test command outcomes

## Acceptance Criteria

* [x] Paper server jar exists under `minecraft-nodes/main-server/`.
* [x] `eula.txt` and `server.properties` exist.
* [x] Adapter plugin jar exists under `minecraft-nodes/main-server/plugins/`.
* [x] Local build command for the plugin passes or existing jar is verified.
* [x] Final instructions explain Windows client connection address and test
      commands.
* [x] Paper listens on `25549` and Windows client can connect through WSL IP.
* [x] Adapter login calls force HTTP/1.1 and no longer fail with HTTP 422.
* [x] Plugin emits server-side logs for debug/test events instead of join
      lifecycle chat spam.

## Definition of Done

* Files created for the test server.
* Plugin jar placed in `plugins/`.
* Build/check commands run where appropriate.
* Memory/process status checked after setup.
* Work committed or clearly reported if runtime files are intentionally ignored.

## Technical Approach

Use the official Paper downloads API to fetch latest stable `1.21.11` build if
not already available. Keep runtime artifacts under ignored server paths, while
tracking only intentional lightweight config/docs if needed.

## Out of Scope

* Production deployment.
* MCDR automation.
* PostgreSQL/Redis persistence.
* Public network port forwarding.
* Installing mature plugins like WorldEdit/MythicMobs.

## Technical Notes

* Paper API/build metadata: `https://fill.papermc.io/v3/projects/paper/versions/1.21.11/builds`
* Plugin build output:
  `minecraft-nodes/main-plugin/build/libs/immortal-main-plugin-0.1.0-SNAPSHOT.jar`
* Paper is currently run in tmux session `immortal-paper` for local testing.
