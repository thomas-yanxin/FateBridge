# FateBridge 快速入门

这份指南会带你先把 FateBridge 跑起来，再发出第一条请求。如果你刚接触这个项目，从这里开始最合适。

## 环境准备

你需要先装好：

- Python 3.10+
- Git

如果打算使用西占推运能力，建议确认本地有对应的运行时可用；不然核心 chart 家族仍然可以跑，但西占推运类接口会直接提示依赖缺失。详见 [algorithm-coverage.md](algorithm-coverage.md)。

## 克隆仓库并安装

```bash
git clone https://github.com/Yonder-Lab/FateBridge.git
cd FateBridge
```

推荐用 [uv](https://docs.astral.sh/uv/) 安装：

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
```

当然也可以用 pip：

```bash
python -m venv venv
source venv/bin/activate
pip install -e .
```

## 配置环境变量

从模板复制一份 `.env`：

```bash
cp .env.example .env
```

默认内容如下：

```bash
API_HOST=0.0.0.0
API_PORT=8010
ALLOWED_ORIGINS=http://localhost:3000
LOG_LEVEL=INFO
FATEBRIDGE_API_KEYS=
API_KEY_HEADER_NAME=X-API-Key
```

本地调试时通常不用改。几点说明：

- `FATEBRIDGE_API_KEYS` 为空时，REST API 默认不启用鉴权。
- 如果设成 `FATEBRIDGE_API_KEYS=agent:replace-me`，请求业务端点时要带上 `X-API-Key: replace-me`。
- `8010` 是内部访问端口，不要直接暴露到公网作为业务入口。

## 启动服务

```bash
python -m fatebridge.api
# 或
fatebridge-api
```

看到类似下面的输出就说明启动成功了：

```text
INFO:     Uvicorn running on http://0.0.0.0:8010
```

## 验证接口

健康检查：

```bash
curl http://localhost:8010/health
```

应返回：

```json
{"status":"healthy"}
```

再看一下就绪状态和指标：

```bash
curl http://localhost:8010/ready
curl http://localhost:8010/metrics
```

浏览器打开 `http://localhost:8010/docs` 或 `http://localhost:8010/redoc`，可以直接在线调试接口。

## 试一下命理接口

```bash
curl -X POST http://localhost:8010/api/calculate \
  -H "Content-Type: application/json" \
  -H "X-API-Key: replace-me" \
  -d '{
    "name": "张三",
    "gender": "男",
    "birth_year": 1990,
    "birth_month": 5,
    "birth_day": 15,
    "birth_hour": 10,
    "birth_minute": 30,
    "birth_timezone": "Asia/Shanghai",
    "birth_place": "北京",
    "use_true_solar_time": true
  }'
```

如果你没有配置 `FATEBRIDGE_API_KEYS`，把 `X-API-Key` 这一行去掉即可。

正常返回里会看到 `person_info`、`four_pillars`、`day_master`、`element_distribution`、`patterns`、`calendar_context` 这些字段。

## 试一下占星接口

```bash
curl -X POST http://localhost:8010/api/astro/chart \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Chart Demo",
    "birth_year": 1990,
    "birth_month": 4,
    "birth_day": 6,
    "birth_hour": 9,
    "birth_minute": 33,
    "birth_timezone": "Asia/Shanghai",
    "birth_longitude": 121.4667,
    "birth_latitude": 31.2167,
    "birth_place": "上海"
  }'
```

如果本地 `swisseph` 可用，返回结果里的 `chart_profile.engine_precision` 一般会显示高精度运行时；否则会回退到 FateBridge 的离线近似模型。

## 通过 MCP 接入

如果你不想走 HTTP，而是让 Agent 直接把 FateBridge 当作工具箱使用，可以启动 FastMCP：

```bash
fatebridge-mcp
# 或等价写法（未安装时）
python -m fatebridge.mcp_server
```

启动后把它注册到你的 MCP host 里即可。具体工具清单参考 [api-reference.md](api-reference.md)。

## 接下来看什么

- 想浏览全部接口：参考 [api-reference.md](api-reference.md)。
- 想了解代码结构：参考 [architecture.md](architecture.md)。
- 想知道哪些能力是近似实现：参考 [algorithm-coverage.md](algorithm-coverage.md)。
- 已经遇到错误：参考 [troubleshooting.md](troubleshooting.md)。
