# 字段定义

| 字段 | 类型 | 说明 |
|---|---|---|
| `row_id` | text | 主键 |
| `work_order` | text | 业务字段 |
| `stage_seq` | int_positive | 业务字段 |
| `stage` | text | 业务字段 |
| `input_qty` | int_positive | 业务字段 |
| `good_qty` | int | 业务字段 |
| `scrap_qty` | int | 业务字段 |
| `rework_qty` | int | 业务字段 |
| `rework_good` | int | 业务字段 |

空字符串、`-`、`NA`、`null` 和 `未提供` 按空值处理。金额字段在整理层转为整数分或整数最小单位；日期按 ISO 日期解析；带时间的字段按本地时间解析。标识字段保持为文本，前导零不会被去除。
