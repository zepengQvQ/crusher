# contracts/

接口说明书的快照（机器导出，方便前后端对齐）。

- `openapi.json`：跑 `make export-openapi` 从后端生成
- 前端 `frontend-h5/src/api/generated-types.js` 会跟着一起更新

你改了接口字段后，记得跑一次导出，避免网页和后端对不上。
