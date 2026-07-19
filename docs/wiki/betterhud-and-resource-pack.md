# BetterHud 与资源包

BetterHud 是可选的展示集成。HUD 缺失或加载失败绝不会改变 Game Service 的权威状态。

## 运行要求

- BetterHud `2.0.0`
- ImmortalMC 构建和本地 Paper 运行均只支持 Java `25`
- 客户端接受并下载生成的资源包

ImmortalMC 和 BetterHud `2.0.0` 都以 Java 25 为本地基线。Paper 启动器会校验真实
Java 主版本必须为 25，不提供 Java 21 回退。

## 托管的 HUD 资源

每次启用 ImmortalMC 时，适配器都会使用自身 jar 中的文件覆盖以下由 BetterHud 管理的
资源，并触发 BetterHud 重新加载：

```text
plugins/BetterHud/images/immortal-cultivation.yml
plugins/BetterHud/layouts/immortal-cultivation.yml
plugins/BetterHud/huds/immortal-cultivation.yml
plugins/BetterHud/texts/immortal-cultivation.yml
plugins/BetterHud/assets/immortal/*.png
```

不要通过编辑这些生成副本来进行永久修改。应编辑以下目录中的打包文件：

```text
minecraft-nodes/main-plugin/src/main/resources/betterhud/
```

然后重新构建并复制 ImmortalMC jar，再重启 Paper。

## HUD 内容

`immortal_cultivation` HUD 会显示：

- 彩色主进度条：当前境界内的已炼化修为进度；
- 中文境界名称；
- 灰色细进度条：未炼化修为储备相对于储备上限的进度。

ImmortalMC 注册的原生 BetterHud 占位符：

```text
immortal_realm_name
immortal_current
immortal_max
immortal_current_ratio
immortal_reserve
immortal_reserve_cap
immortal_reserve_ratio
```

不需要 PlaceholderAPI。

## 资源包生成与下发

这是两个相互独立的步骤：

1. BetterHud 构建 `plugins/BetterHud/build.zip`。
2. Minecraft 的 `server.properties` 或其他资源包分发器告知客户端下载地址。

ImmortalMC 会安装 HUD 源文件并请求 BetterHud 重新加载。它不会配置公开资源包 URL，
也不会强制客户端下载。当前本地 BetterHud 配置已禁用自托管。

日常一键启动会在 `immortal-resource-pack` tmux 会话中托管现有 `build.zip`：

```bash
./scripts/start-local-server.sh
```

需要单独排查资源包服务时，也可手动建立简单的 WSL 测试主机：

```bash
cd minecraft-nodes/main-server/plugins/BetterHud
python3 -m http.server 8164
```

然后配置 Windows Minecraft 客户端可访问的 URL：

```properties
resource-pack=http://<wsl-ip>:8164/build.zip
resource-pack-sha1=<sha1-of-build.zip>
require-resource-pack=false
```

每次重新构建资源包后都要计算哈希：

```bash
sha1sum minecraft-nodes/main-server/plugins/BetterHud/build.zip
```

修改 `server.properties` 后，重启 Paper 并让客户端重新连接。

## 为什么没有下载请求

请按以下顺序检查：

1. `plugins/BetterHud/build.zip` 存在且大小不为零。
2. 配置的 URL 能从 Windows 打开，而不仅仅是在 WSL 内部可用。
3. 除非已经验证 WSL 转发，否则不要让远程或客户端机器使用 `localhost`；请使用当前
   WSL IP 或实际的 HTTP 主机。
4. `resource-pack-sha1` 与当前 zip 匹配。
5. 玩家没有在服务器列表条目中永久拒绝服务器资源包。
6. 修改 URL/哈希后，Paper 已重启且玩家已重新连接。

当 `enable-self-host: false` 时，BetterHud 不会替代上面的独立 HTTP 主机。即使资源包
有效且已生成，如果 Paper 没有可访问的下发 URL，客户端仍然不会发出请求。

## 日志

成功启动时会出现：

```text
[BetterHud] Plugin enabled.
[ImmortalMC] betterhud_cultivation_enabled hud=immortal_cultivation
```

如果 BetterHud 缺失，或者其 API/重新加载失败，ImmortalMC 会记录清晰可见的警告，
并且只禁用 HUD 展示。
