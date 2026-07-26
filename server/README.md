# Space Kill Game Server (太空杀游戏后端服务器)

基于逆向分析实现的太空杀游戏完整后端服务器，支持 HTTP 登录、Gate/RPC 通信和 Scene 场景同步。

## 架构

```
┌─────────────────────────────────────────────────┐
│                  Game Server                     │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ HTTP(8080)│  │Gate(8100)│  │ Scene(8200)  │  │
│  │  登录服务  │  │ RPC通信  │  │  场景同步    │  │
│  └─────┬─────┘  └─────┬────┘  └──────┬───────┘  │
│        │              │              │           │
│        └──────────────┴──────────────┘           │
│                       │                          │
│              ┌────────┴────────┐                 │
│              │  Player Manager │                 │
│              │  Room Manager   │                 │
│              └─────────────────┘                 │
└──────────────────────────────────────────────────┘
```

## 功能模块

### HTTP 服务器 (端口 8080)
- 用户登录认证 (Login)
- 开始游戏分配房间 (StartGame)
- 第三方绑定 (Bind)
- 验证码服务 (VerificationCode)

### Gate/RPC 服务器 (端口 8100)
- Gate 登录认证 (GateLogin)
- 心跳保活 (HeartBeat)
- 服务器时间同步 (Betick)
- 用户模块 (User) - 角色详情、背包、装扮等
- 关系模块 (Relation) - 关注、粉丝、好友
- 房间模块 (Room) - 房间列表、操作
- 商店模块 (Shop) - 服装购买
- 排位模块 (Qualifying) - 排位信息
- BBS模块 - 留言板
- 邮件模块 (Mail)

### Scene 服务器 (端口 8200)
- 场景登录 (SceneLogin)
- 心跳保活 (HeartBeat)
- 玩家移动同步 (Move/BatchMove)
- 玩家状态变更 (ChangeState)
- 聊天系统 (RoomChat)
- 表情系统 (SendEmoji)
- 玩家进出通知 (AddDelPlayer)
- 游戏进度通知 (GameProgressNotice)
- 颜色切换 (ChangeColor)

## 文件结构

```
server/
├── server.py       # 主服务器实现 (HTTP + Gate + Scene)
├── config.py       # 配置文件 (IP/端口/模块/命令枚举)
├── messages.py     # Protobuf 消息编解码
├── pb.py           # Protobuf 读写工具
├── start.sh        # 启动脚本
└── README.md       # 本文件
```

## 快速开始

### 环境要求
- Python 3.8+
- 无需额外依赖（仅使用标准库）

### 启动服务器

```bash
# 测试模式 (本地 127.0.0.1)
cd server
./start.sh

# 生产模式 (IP 172.21.26.128，匹配已配置的APK)
./start.sh prod
```

### 服务器端口

| 服务 | 端口 | 协议 | 说明 |
|------|------|------|------|
| HTTP | 8080 | TCP/HTTP | 登录、开始游戏 |
| Gate | 8100 | TCP | RPC 通信 |
| Scene | 8200 | TCP | 场景同步 |

## 通信协议

### HTTP 协议
```
请求: POST /login
Body: module(2B LE) + cmd(2B LE) + uid(8B LE) + PbObj data
响应: flag(1B) + PbObj data  (flag=0成功, flag=1失败)
```

### Gate/RPC TCP 协议
```
请求:  total_size(3B BE) + flag(1B) + module(2B BE) + cmd(2B BE) + sid(4B BE) + PbObj
响应:  total_size(3B BE) + flag(1B) + sid(4B BE) + PbObj
```

### Scene TCP 协议
```
请求:  body_size(3B LE) + flag(1B) + cmd(4B BE, module<<16|cmd) + PbObj
响应:  body_size(3B LE) + flag(1B) + cmd(4B BE) + PbObj
```

## 配置说明

修改 `config.py` 中的 `SERVER_IP`：

```python
# 测试模式
SERVER_IP = "127.0.0.1"

# 生产模式 (匹配APK中配置的IP)
SERVER_IP = "172.21.26.128"
```

## APK 配置

APK 中的 `Assembly-CSharp.dll` 已修补，将以下服务器地址替换为 `172.21.26.128`：

| 原始地址 | 替换地址 |
|---------|---------|
| `http://78.helpyun.top/login` | `http://172.21.26.128:8080/l` |
| `https://game.90992.cn/login` | `http://172.21.26.128:8080/l` |
| `http://upload.90992.cn` | `http://172.21.26.128:8080` |
| `http://image.90992.cn` | `http://172.21.26.128:8080` |
| `http://report.90992.cn` | `http://172.21.26.128:8080` |

## 测试

```bash
# 启动服务器
./start.sh

# 运行测试客户端 (需安装 requests)
python3 test_client.py
```

测试流程：
1. HTTP 登录 → 获取 Player ID 和 Gate Key
2. Gate TCP 登录 → 认证成功
3. 心跳测试 → 正常响应
4. GetSvrTime → 返回服务器时间
5. GetRoleDetail → 返回角色详情
6. HTTP StartGame → 获取 Scene 地址
7. Scene TCP 登录 → 进入场景
8. Scene 心跳 → 正常响应

## 技术细节

### Protobuf 实现
使用纯 Python 实现的 Protobuf 编解码器，无需 protoc 编译：
- `PBWriter` - 编写 varint、string、bytes、message 字段
- `PBReader` - 读取和跳过字段

### 多线程架构
- HTTP 服务器运行在独立线程
- Gate 服务器为每个客户端创建独立线程
- Scene 服务器为每个客户端创建独立线程
- 心跳线程定期清理过期会话

## License

MIT
