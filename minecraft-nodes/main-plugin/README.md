# ImmortalMC Main Plugin

Thin Paper adapter plugin for the ImmortalMC Game Service.

## Target

- Minecraft / Paper: `1.21.11`
- Java: `21`
- Build tool: Gradle Kotlin DSL, wrapper pinned to `9.6.1`
- Plugin descriptor: `src/main/resources/plugin.yml`

The plugin is an adapter only. It reports Minecraft-side facts to the FastAPI
Game Service and displays the response in Minecraft. Cultivation, combat,
loot, economy, player progression, and persistence rules belong in
`game-service/`.

## Current Slices

Connectivity command:

```bash
/immortal health
```

It reads `game-service.base-url` from `config.yml`, calls `GET /health`
asynchronously, and sends the result back to the command sender on the Paper
main thread.

Default config:

```yaml
game-service:
  base-url: "http://127.0.0.1:8000"
```

Player login sync:

- listens for Paper `PlayerJoinEvent`
- calls `POST /api/v1/players/login` asynchronously
- caches the returned account/current-life snapshot in memory
- sends player-facing success/failure feedback on the Paper main thread

## Development Flow

1. Write or update automated tests for the adapter behavior.
2. Implement the Java adapter code.
3. Run checks:

   ```bash
   ./gradlew --no-daemon --max-workers=1 test
   ./gradlew --no-daemon --max-workers=1 build
   ```

   The first `./gradlew` run downloads Gradle. If WSL networking times out
   while downloading, install/use a local Gradle `9.6.1` and run the same
   tasks with `gradle --no-daemon --max-workers=1 test build`.

4. Start the FastAPI Game Service.
5. Put `build/libs/immortal-main-plugin-0.1.0-SNAPSHOT.jar` in a Paper
   `1.21.11` server's `plugins/` directory.
6. Start the Paper server and run `/immortal health` as an operator.

Server verification comes after automated checks. For most feature slices,
the expected loop is: implement a small task, run tests/build, then verify the
visible Minecraft behavior in the server.

## Low-Memory Notes

Gradle is configured in `gradle.properties` with `org.gradle.daemon=false`,
`org.gradle.workers.max=1`, and a small JVM heap. Avoid starting a full Paper
server during routine unit-test work; run the server only when verifying a
Minecraft-facing behavior.
