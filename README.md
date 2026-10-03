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

1. 在「点位」「货道」查看售货机布局与库存；货道页可直接修改库存/在途并保存，货道现态、最新补货单对应行、满仓名单与汇总计数在同一次保存内一起跳变。
2. 在「销量」了解近期出货。
3. 打开「补货单」按缺口生成建议补货量（库存加在途大于容量即为超占，补量强制为 0）。
4. 在「满仓」「汇总」查看已满货道与补货合计；满仓页只列恰好等于容量的货道，不含超占。

## 开发与测试

```bash
docker compose exec api pytest -q
```
