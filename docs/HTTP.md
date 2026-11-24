# 接口

- `GET /`：工作台。
- `GET /api/catalog`：阶段、字段和样例。
- `POST /api/stages/{stage}`：按阶段返回处理结果。
- `POST /api/runs`：执行完整批次并保存草稿。
- `GET /api/runs`：列出本地批次（可加 `?approved=true`）。
- `GET /api/runs/{id}`：读取批次。
- `POST /api/runs/{id}/review`：签发或暂缓，提交 `decision`、`comment`、`expected_revision`。
- `POST /api/comparisons`：选择两批已签发报工生成或幂等重跑对比，支持 `baseline_run_id`/`candidate_run_id`、`before_run_id`/`after_run_id` 或 `run_ids`。
- `GET /api/comparisons/{id}`：读取对比复盘；上游状态或版本变化后响应中 `stale=true`。
- `POST /api/comparisons/{id}/refresh`：按当前上游批次刷新同一条复盘。
- `GET /api/comparisons`：列出对比复盘。
- `GET /api/runs/{id}/evidence`：下载已签发证据。
- `GET /api/examples/{profile}`：下载样例。
- `GET /healthz`：健康检查。
