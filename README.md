# VendFill 售货机补货

按货道容量、库存与在途量计算缺口，生成不超缺口、非负的补货单。

技术栈：Python 3.12 / FastAPI / SQLAlchemy / PostgreSQL / Vue 3 / TypeScript / Vite

## 启动

```bash
docker compose up --build
```

| 服务 | 地址 |
| --- | --- |
| 前端 | http://localhost:4800 |
| API | http://localhost:9800 |
| API 文档 | http://localhost:9800/docs |
| Postgres | localhost:5449 |

健康检查：`GET http://localhost:9800/api/health`

## 使用说明

1. 在「点位」「货道」查看售货机布局与库存，并可直接修改库存/在途后保存。
2. 在「销量」了解近期出货。
3. 打开「补货单」按缺口生成建议补货量。
4. 在「满仓」「汇总」查看已满货道与补货合计。

## 口径：超占 / 满仓 / 待补

- `库存 + 在途 > 容量` → **超占**（overbooked），补量恒为 0；
- `库存 + 在途 = 容量` → **满仓**（full），补量为 0；
- `库存 + 在途 < 容量` → **待补**（need_fill），补量在 `[0, 缺口]` 内。

超占与满仓互斥，满仓页只列满仓、不含超占。在货道页保存库存/在途时，
货道现态、最新补货单对应行状态、满仓名单、汇总超占/满仓计数在同一事务内
一起跳变；更早的历史补货单保留生成当时的内容，不会被回刷。

## 开发与测试

```bash
docker compose exec api pytest -q
```
