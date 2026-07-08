# ImmortalMC Local Paper Server

Local Paper `1.21.11` test server for Windows Minecraft client testing.

## Start Order

1. Start Game Service:

   ```bash
   cd /home/adam/projects/immortal_mc
   ./scripts/start-game-service.sh
   ```

2. Start Paper:

   ```bash
   cd /home/adam/projects/immortal_mc
   tmux new-session -s immortal-paper './scripts/start-paper-server.sh'
   ```

   To attach later:

   ```bash
   tmux attach -t immortal-paper
   ```

   To stop Paper cleanly from outside tmux:

   ```bash
   tmux send-keys -t immortal-paper 'stop' Enter
   ```

3. In Windows Minecraft Java Edition `1.21.11`, connect to the WSL IP and
   local Paper port:

   ```text
   172.25.217.166:25549
   ```

   The WSL IP can change after restarting WSL. Run `hostname -I` in WSL and use
   the first IP address with port `25549`. `localhost:25549` can work on some
   WSL setups, but this machine currently needs the WSL IP.

## Test Commands

```text
/immortal health
/immortal spirit-root
```

`/immortal health` is an operator diagnostics command. `/immortal spirit-root`
is a temporary development test entrypoint; the planned gameplay flow should use
NPC, block, region, or item interactions instead of player-entered commands.

## Collaborative Testing

When testing from Windows, run the action in game and then inspect the Paper log:

```bash
tail -n 80 /home/adam/projects/immortal_mc/minecraft-nodes/main-server/logs/latest.log
```

Plugin debug/status details belong in Paper logs, not player chat. Player chat
should only show intentional gameplay feedback.

`online-mode=false`, `enforce-secure-profile=false`, and
`prevent-proxy-connections=false` are set for local-only testing. Do not use
this config for a public server.
