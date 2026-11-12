# Session 8 实验学习版：成绩接口的访问控制

## Alice 已登录，为什么还会越权？

**身份认证（authentication）**确认请求来自 Alice。**授权（authorization）**判断 Alice 是否有权读这条成绩。
URL 中的 `3` 只是成绩记录编号（note ID）。老师预置的数据中，记录 3 的所有者编号（`student_id`）是 7，对应 Bob。Alice 的用户编号（`user_id`）是 6。

```text
GET /api/notes/3 + Alice 的登录凭据
        ↓
认证 → user_id = 6，role = student
        ↓
数据库按 note ID 3 找到记录 → student_id = 7
        ↓
授权检查 → 6 与 7 不同，学生角色无跨账户权限 → 404
```

修复前，最后一步缺失。只改 URL 中的数字，就能让服务器返回 Bob 的 12.6 分和 “Solid work, keep it up.”。这类漏洞叫 **IDOR**（Insecure Direct Object Reference，不安全的直接对象引用）。
即使编号换成难猜的随机字符串，一旦有人拿到它，服务端仍需判断访问权限。

## 实测结果怎么读

| 场景 | 修复前 | 修复后 |
| --- | --- | --- |
| Alice 看自己的第 1 条记录 | 200，16.2 分 | 200，16.2 分 |
| Alice 看 Bob 的第 3 条记录 | 200，12.6 分和评语 | 404 |
| Alice 查不存在的第 99999 条记录 | 404 | 404 |
| 教师或管理员读 Bob 的记录 | 本轮基线未测 | 200，12.6 分 |
| 未登录用户请求第 3 条记录 | 401 | 401 |

`401` 表示缺少有效认证。访问别人的记录与访问不存在的记录都返回 `404` 和同一条 JSON 错误，响应不会直接提示哪个编号对应真实记录。教师和管理员是课件明确允许跨账户读取的角色。

## 代码和复现

- 打开 NotesApp 的 `web/app.py`，搜索 `def api_notes`。先看 `current_identity()` 如何取得登录身份，再看查询后的归属判断。拒绝请求会在解密评语前结束。
- 用课程种子账户 Alice 登录本机页面 `http://127.0.0.1:8080`，在 **Grade detail (API)** 输入 1，再输入 3。该按钮走 Bearer JWT。脚本也验证了仅凭 session cookie 的同一条路由。
- 按英文说明启动独立 Docker Compose 项目，执行 `python "$lab/verify_live.py" after after-recheck.json`。在 NotesApp 根目录用 `docs/session08` 替换 `$lab`。两份实测 JSON 只记录种子数据的响应。
[英文复现步骤](README.md#reproduce-on-windows) · [修复前](evidence/before.json) · [修复后](evidence/after.json)

## 自测

1. URL 中的 `note_id=3`、Alice 的 `user_id=6` 和 Bob 的 `student_id=7` 分别表示什么？
2. 第七课已经修好 JWT 验签，为什么 Alice 仍然能在第八课复现 IDOR？
3. Alice 请求 3 返回 404 后，还应验证哪几个用户的正常读取？为什么选择用同一个响应表示无权访问和记录缺失？
