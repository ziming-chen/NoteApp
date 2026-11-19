# 第十课学习说明 — 存储型 XSS（你的文字在别人浏览器里运行）

> 这份是给子明看的学习版。英文正式报告见 [README.md](README.md)，交给老师的四行结论见 [audit.txt](audit.txt)，机器可读的核验记录见 [verification.json](verification.json)。
> 本次一个人做，修复 commit 为 `845e4be`，实验日期 2026-11-18。

## 一句话抓住本质

上一课（第九课）是**进来的方向**注入：你输入的文字被拼进命令，服务器照做。
这一课是**出去的方向**注入：服务器把存着的文字**当成代码**交给别人的浏览器，浏览器照做。

一个老师写一次评语，所有打开那一页的学生都会中招，**攻击者根本不需要在场**。这就是“存储型”（stored）的含义。

## 这一课在整门课里的位置

| 课 | 被攻击的东西 | 一句话 |
|---|---|---|
| 第五课 | 传输中的保密 | 路上别被看、被改（HTTPS） |
| 第五课 | 静态存储 | 库里别被还原（Argon2、MD5 对比） |
| 第六、七课 | 认证（who） | 令牌能伪造、密钥能猜出来 |
| 第八课 | 授权（which object） | 有权限 ≠ 有这条记录的权限 |
| 第九课 | 数据 → 命令（**in**） | 拼接让数据变成命令 |
| **第十课** | 数据 → 代码（**out**） | 关掉转义让数据变成代码 |
| 第十一课（预告） | 意图（**intent**） | cookie 证明“你是谁”，不证明“你想发这条请求” |

一条主线：**数据必须一直是数据。** 第九课是“别把数据当命令”，第十课是“别把数据当标记”。

## 英文术语

| 术语 | 意思 |
|---|---|
| XSS（cross-site scripting） | 跨站脚本：让攻击者的脚本在别人的页面里执行 |
| stored XSS | 存储型：脚本先存进数据库，之后每个读者都被打到 |
| reflected XSS | 反射型：脚本从 URL 参数原样反射回来，只打中点击链接的人 |
| DOM XSS | 客户端自己把不可信数据写进 `innerHTML` 之类的入口 |
| autoescape | 模板的“默认转义”开关；Jinja2 默认开启 |
| HTML escaping / entity | 把 `<` 变成 `&lt;`，让解析器只当字符看 |
| MarkupSafe | Jinja2 背后做转义的库；`'` → `&#39;`、`"` → `&#34;` |
| sanitise（allow-list） | 用白名单净化，只保留安全标签（如 `bleach`），而不是关掉转义 |
| CSP（Content-Security-Policy） | 浏览器端的内容策略，可限制内联脚本；本应用**没有**设置 |
| `HttpOnly` | 让 JS 读不到 cookie；Flask 会话 cookie 默认开启 |

## Part 1：种进去，看它在 alice 的浏览器里跑

哪条数据成了攻击面？**成绩评语（`notes.comment`）**。note 1 属于 alice（user id 6，Mathematics，16.2）。老师 `prof.turing` 通过正常的 `/grades` 表单把评语写成：

```
<script>alert('XSS by Eve')</script>
```

### 页面现在长什么样

修复前，`web/templates/dashboard.html` 第 15 行是：

```jinja
<td>{% autoescape false %}{{ n.comment }}{% endautoescape %}</td>
```

于是 alice 收到的 HTML 里，那个单元格**就是**一段脚本：

```html
<td><script>alert('XSS by Eve')</script></td>
```

### 两个证据的分工

| 手段 | 能看到什么 | 不能看到什么 |
|---|---|---|
| `curl` + grep | 服务器**发出去**的字节：1 处原始 `<script>`、0 处 `&lt;script&gt;` | 浏览器有没有真的执行 |
| 真浏览器（Playwright + Chrome） | 弹窗事件 `alert / "XSS by Eve"`、单元格里有没有 `<script>` 元素 | —— |

课件专门提醒过：**`curl` 不会运行 JavaScript**。所以命令行证据的可靠形式是“页面里存在未转义的 `<script>`”，而“它真的跑了”要用真浏览器证明。我们两个都做了。

### 浏览器里到底发生了什么

HTML 解析器读到 `<script>` 就切换进“脚本模式”，把后面的内容交给 JavaScript 引擎。所以那个单元格里：

- `innerHTML` = `<script>alert('XSS by Eve')</script>`（是标签）
- `textContent` = `"alert('XSS by Eve')"`（只剩脚本文本，**没有任何可见文字**）
- 页面上多出一个 `<script>` 元素

这解释了一张容易被误读的截图：修复前 `dashboard-before.png` 里 note 1 的 COMMENT 列是**空白**的。不是评语丢了，而是它**变成了代码被执行掉了**，所以没有文字显示。

### 为什么截图里看不到弹窗

`alert` 是**浏览器的原生对话框**，不属于网页内容（不在页面像素里），所以对页面截图拍不到它。证据是浏览器记录的对话框事件，保存在 `evidence/before/browser-before.json`：

```json
"dialogs": [{ "type": "alert", "message": "XSS by Eve" }]
```

这一点在报告里写清楚了，没有拿截图冒充。

## Part 2：把玻璃装回去

修复只有一行，两个模板各一处：

```jinja
<td>{{ n.comment }}</td>
```

为什么这样就够了？因为 **Jinja2 默认就是转义的**，是那句 `{% autoescape false %}` 手动把安全关掉了。恢复默认后：

| 字符 | 转义成 | 浏览器显示 |
|---|---|---|
| `<` | `&lt;` | `<` |
| `>` | `&gt;` | `>` |
| `&` | `&amp;` | `&` |
| `'` | `&#39;` | `'` |

页面对 alice 变成：

```html
<td>&lt;script&gt;alert(&#39;XSS by Eve&#39;)&lt;/script&gt;</td>
```

浏览器显示这串字符，不再生成元素，自然也不会执行。

**为什么必须重建镜像？** 模板是在 `docker build` 时 `COPY . /app` 进镜像的，改主机上的文件不会自动进容器，所以 `docker compose ... up -d --build`。验证方法是直接进容器 grep：

```
docker exec noteapp-web-1 grep -rn 'autoescape false' /app/templates/   # 无匹配，退出码 1
```

## 为什么是“转义”，不是“过滤黑名单”

如果采用“把 `<script>` 删掉”的思路，你需要穷举所有写法，而它们永远比你的列表多：

```html
<img src=x onerror=alert(1)>
<svg onload=alert(1)>
<iframe srcdoc="<script>alert(1)</script>">
<a href="javascript:alert(1)">x</a>
<body onpageshow=alert(1)>
```

转义不需要猜：它让**所有**字符都变回字符，解析器永远离不开“文本模式”。这就是为什么课件说“修复不是 ban 掉 script 这个词”。

如果将来真的要支持富文本（加粗、链接），正确做法是**服务端白名单净化**（例如 `bleach`，只保留允许的标签），而不是打开 `autoescape false`。

## Part 3 和 Part 4：证明关掉了，也证明没改坏

- **Part 3**：修好之后，用老师身份把**同一个 payload 再提交一次**。页面里 `grep "<script>alert"` 找不到，`&lt;script&gt;` 找到——同一个输入、同一个数据库值，输出变安全了。
- 关键理解：**转义发生在“输出的那一刻”**，所以旧数据不用重新录入就自动安全了。老师不需要把历史评语重发一遍。
- **Part 4**：换一条正常评语 `score < 10 on part 1 & 2, see me`。页面里存的是 `score &lt; 10 on part 1 &amp; 2, see me`，浏览器显示回原样。修复不是“把评语搞坏”。

## 代码入口

| 文件 | 位置 | 作用 |
|---|---|---|
| `web/templates/dashboard.html` | 第 14–16 行 | 学生成绩表；修复点（flaw #10） |
| `web/templates/teacher.html` | 第 49–50 行 | 教师总表；同一个缺陷 |
| `web/app.py` | `grades()`（约 304 行起） | 老师写评语；评语用 AES-GCM 加密后入库 |
| `web/app.py` | `decrypt_notes()`（约 91 行） | 读出时解密，然后原样交给模板 |
| `tests/test_stored_xss.py` | 全文件（新增 4 项） | 回归测试：含“任何模板出现 autoescape false 就失败”的守卫 |

## 运行方法

```bash
# 启动（Windows 本机端口映射 + 普通 HTTP）
docker compose -f docker-compose.yml -f compose.windows.yml up -d --build
# 浏览器打开 http://127.0.0.1:8080 ，alice/alicepw、prof.turing/teach123

# 真实浏览器验证（三种模式：before / after / normal）
node verify_browser.js before ./evidence/before
node verify_browser.js after  ./evidence/after
node verify_browser.js normal ./evidence/after

# 回归测试
python -m pytest -q --cov=web --cov-report=term-missing
```

`verify_browser.js` 用系统自带的 Chrome/Edge（`executablePath`），不需要另外下载 Playwright 的浏览器。

## 证据清单

```
evidence/before/  part1_curl_transcript.txt        修复前的 curl 结果与状态码
                  part1_alice_dashboard_raw.html   alice 收到的原始页面（含活 <script>）
                  part1_teacher_dashboard_raw.html 教师页同样中招
                  browser-before.json              弹窗事件记录
                  dashboard-before.png             截图：CELL 空白（已被执行）
evidence/after/   part2_escaped_transcript.txt     同一行数据，转义后的输出
                  part3_resaved_transcript.txt     重发同一 payload 的结果
                  part4_normal_comment_transcript.txt  正常评语的显示
                  browser-after.json / browser-normal.json
                  dashboard-after.png              截图：显示 <script>…</script> 文本
                  dashboard-normal.png             截图：score < 10 … & …
                  pytest.txt                       106 项通过
                  data_integrity.txt               行数与密文核对
```

看证据的推荐顺序：先看两张截图对比（空白 vs 显示文字），再看 `browser-before.json` 的弹窗，最后看 raw HTML 里的 `<td>` 一行。

## 容易踩的坑

1. **只改 `dashboard.html`，忘了 `teacher.html`**：教师的表同样会执行，问题没修完。
2. **改完不重建镜像**：容器里还是旧模板。
3. **把 `{{ n.comment }}` 也删了**：单元格直接空白，属于“修过头”。
4. **以为 `curl` 看到 200 就证明执行了**：`curl` 不跑 JS，只能证明“页面里有没有活代码”。
5. **以为加密评语就能防 XSS**：AES-GCM 保护的是**数据库里**的数据，应用读取后仍要原样放进页面；加密和转义解决的是两个不同层面。

## 自测题

1. 为什么这一课叫“存储型”？和反射型的区别是什么？
2. 修复前 alice 页面里那一段是“字符串”还是“元素”？从 `textContent` 为空能看出什么？
3. 为什么说 `curl` 的 grep 是可靠命令行证据，但它不能证明“弹窗弹出来了”？
4. 修复为什么是删掉 `autoescape false`，而不是过滤 `<script>`？举一个能绕过黑名单的写法。
5. 为什么转义能自动保护**历史**上已经存进数据库的旧评语？
6. 如果这个站点同时还有第十课的 XSS，那么第十一课要加的 CSRF token 还挡得住吗？为什么？

> 提示：第 6 题是下一课的引子——XSS 让攻击者脚本运行在**同源**里，可以直接读取页面里的 token。

## 一句话带走

服务器把用户文字写进 HTML 时，要么**转义**（默认，首选），要么用**白名单净化**；永远不要为了“显示富文本”而关掉转义。玻璃可以擦，但不能拆。
