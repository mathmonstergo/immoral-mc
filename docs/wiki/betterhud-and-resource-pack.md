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

ImmortalMC 插件会安装 HUD 源文件并请求 BetterHud 重新加载，但不会在运行时决定公开
资源包地址。统一的本地启动脚本负责把当前资源包 URL 和 ZIP SHA-1 同步到 Paper 的
`server.properties`；当前本地 BetterHud 配置仍禁用自托管。

日常一键启动会执行以下动作：

1. 验证现有 `build.zip` 非空；
2. 自动计算当前 ZIP 的 SHA-1；
3. 只幂等更新 runtime `server.properties` 中的 `resource-pack` 和
   `resource-pack-sha1`；
4. 在 `immortal-resource-pack` tmux 会话中托管同一个 `build.zip`；
5. Paper 尚未运行时再使用更新后的属性启动 Paper。

在 WSL、局域网或反向代理环境中，建议显式提供 Minecraft 客户端真正可访问的 URL：

```bash
export RESOURCE_PACK_PUBLIC_URL=http://<wsl-ip>:8164/build.zip
./scripts/start-local-server.sh
```

URL 必须使用 `http://` 或 `https://`，并以 `/build.zip` 结尾。未设置时，脚本会从
`hostname -I` 选择第一个非回环 IPv4 地址并生成 URL；存在 Docker、VPN、多网卡或
端口转发时应显式覆盖，不能假定自动选出的地址一定能被 Windows 或远端客户端访问。

本地测试服务固定监听 `0.0.0.0:8164`，并从专用运行目录只公开 `build.zip`。向客户端
广告的 URL 可以指向 HTTPS 反向代理，不要求公开 URL 的端口与本地监听端口一致。

需要单独排查资源包服务时，可从临时目录只托管 ZIP，避免公开 BetterHud 的配置、
数据库或用户目录：

```bash
pack_test_dir="$(mktemp -d)"
ln -s "$PWD/minecraft-nodes/main-server/plugins/BetterHud/build.zip" \
  "$pack_test_dir/build.zip"
python3 -m http.server 8164 --bind 0.0.0.0 --directory "$pack_test_dir"
# 按 Ctrl-C 停止后：rm -r -- "$pack_test_dir"
```

然后核对脚本写入的运行配置：

```properties
resource-pack=http://<wsl-ip>:8164/build.zip
resource-pack-sha1=<current-build.zip-sha1>
require-resource-pack=false
```

正常启动不需要手工计算哈希。诊断时可用下列命令与 `server.properties` 比对：

```bash
sha1sum minecraft-nodes/main-server/plugins/BetterHud/build.zip
```

如果脚本发现 URL 或 SHA-1 已变化，而 `immortal-paper` 会话仍在运行，它会明确提示
重启 Paper。脚本不会自动杀死正在运行的服务器；重启后还需要让客户端重新连接。

## 为什么没有下载请求

请按以下顺序检查：

1. `plugins/BetterHud/build.zip` 存在且大小不为零。
2. 配置的 URL 能从 Windows 打开，而不仅仅是在 WSL 内部可用。
3. 除非已经验证 WSL 转发，否则不要让远程或客户端机器使用 `localhost`；请使用当前
   WSL IP 或实际的 HTTP 主机。
4. `resource-pack` 与脚本输出的客户端 URL 一致，`resource-pack-sha1` 与当前 zip 匹配。
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
