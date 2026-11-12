# 第七课学习说明｜修复登录

第六课保存的两枚伪造令牌，修复前都能请求 Bob 的成绩。修复后，用完全相同的两枚令牌访问 `/api/notes/3`，服务器都返回 `401 Unauthorized`。Alice 正常登录后拿到新令牌，只带这枚令牌请求自己的成绩，返回 `200 OK`。详见 [Audit](audit.txt) 和 [本机复测记录](evidence/final.json)。

## 先理解三个词

- **JWT（JSON Web Token，令牌）** 由 `header.payload.signature` 三段组成。头部声明算法，载荷描述身份，最后一段用于检查前两段是否由持有密钥的一方签发。Base64url 只是编码，拿到令牌的人可以读出前两段。
- **HS256（HMAC-SHA-256）** 用同一把密钥签发和验证。把载荷里的 `"role":"student"` 改为 `"role":"teacher"` 后，原签名就对不上。服务端重新算一遍，再用 `hmac.compare_digest` 比较。
- **密钥轮换（key rotation）** 是把服务端使用的旧密钥换成新值。以前用旧密钥签发的令牌会失效，正常用户重新登录就能拿到新令牌。课堂用 `secrets.token_urlsafe(32)` 从 32 个随机字节生成密钥，由 Docker Compose 从本机环境注入。

## 为什么要做两步

| 版本 | 无签名 teacher 令牌 | 旧密钥签名的 teacher 令牌 |
| --- | --- | --- |
| 修复前 | 200 | 200 |
| 固定算法为 HS256 | 401 | 200 |
| 再轮换为长随机密钥 | 401 | 401 |

第二行说明，只拒绝 `alg:none` 时，攻击者如果已经知道旧密钥，仍能为伪造身份算出符合 HS256 的签名。第三行说明，更换密钥后，旧签名就无法通过。三行都来自本机 Docker 的真实 HTTP 请求。课前预测见 [predictions.md](predictions.md)。

## 对着代码看

1. 在 `web/app.py` 找 `login()`。Alice 的账号密码验证通过后，`make_jwt()` 签发令牌，网页会把它用于请求成绩详情。
2. 找 `current_identity()`。浏览器发来 `Authorization: Bearer <token>` 时会调用 `verify_jwt()`，验证失败返回 401。
3. 找 `verify_jwt()`。函数检查头部的算法是否精确为 `HS256`，再用配置中的密钥对 `header.payload` 验签，成功后才返回身份。
4. 打开 `docker-compose.yml` 查看 `web.environment.JWT_SECRET`。本机 `.env` 已配置并由 Git 忽略。换电脑时用自己的随机值重新配置。

## 在本机重跑

在 NotesApp 根目录启动 Docker Desktop，按 [英文 README 的复测步骤](README.md#reproduce)启动已有的 HTTPS 配置。浏览器打开 `https://localhost`，用课程测试账户 `alice / alicepw` 登录，进入 **My grades**，在 **Grade detail (API)** 中点击 **Load**。若浏览器还持有旧令牌，先退出再登录。脚本会额外用无 Cookie 的客户端验证 Alice 的新 Bearer 令牌。

复测结束后可关闭应用，保留 PostgreSQL 数据卷。

```powershell
docker compose -p noteapp -f docker-compose.yml -f compose.windows.yml -f docker-compose.https.yml down
```

## 自测

1. 把 JWT 头部的算法改成 `none`，函数会在哪一步拒绝？
2. 为什么只固定算法之后，旧密钥签过的假令牌仍返回 200？
3. Alice 登录后看到了成绩页，为什么实验还要用一个无 Cookie 的客户端请求成绩 API？
4. 确认来人是 Alice 属于身份认证（authentication）。确认 Alice 有权读取某条成绩属于什么检查？

参考答案依次为算法检查、旧签名和旧密钥仍匹配、单独验证新 JWT 确实有效、授权（authorization）。本课测试的是 JWT 认证，成绩归属检查对应后续访问控制实验。 [课程要求](https://kristenpire.github.io/epita-security-labs/class7/fix-the-login/)
