# frontend-h5/

手机网页（正式 Demo 前端）。用 Vue 写页面，用 Vant 做组件样式。

| 内容 | 白话 |
|------|------|
| `src/` | 页面、跳转、调接口、示例文案 |
| `src/__tests__/` | Vitest 真实组件流程（`npm test`） |
| `package.json` / `package-lock.json` | Node 依赖及锁定版本 |
| `vite.config.js` | 开发转发 `/api`；Vitest 配置 |

```bash
npm install && npm run dev
npm test                 # 组件流程测试
```

默认打开 http://localhost:5173。双终端完整启动见根目录 `README.md`。
