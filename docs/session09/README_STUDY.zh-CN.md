# 第九课学习说明 — 注入(SQL 注入与命令注入)

> 这份是给子明看的学习版。英文正式报告见 [README.md](README.md),交给老师的 finding 见 [audit.txt](audit.txt)。
> 本次一个人做。

## 一句话抓住本质

服务器干活时,会**拼一句话**交给一个"听话的东西"去执行:
- 交给**数据库**,它说的语言是 **SQL**;
- 交给**操作系统外壳(shell)**,它说的语言是**系统命令**。

出 bug 的根源:它把你输入的文字**直接粘进这句话里**。你的文字本该是"答案/数据",可一旦被粘进去,只要里面带了这句话自己的标点(`'`、`--`、`;`),它就从"数据"变成了"命令的一部分"。这就是**注入**。两处漏洞是同一个错,只是一个在 SQL 里、一个在 shell 里。

修复也是同一个形状:**把数据当数据传,别拼进命令里。**

## 英文术语

| 术语 | 意思 |
|---|---|
| SQL injection | SQL 注入:把 SQL 标点注入查询,改变查询结构 |
| command injection | 命令注入:把 shell 标点注入命令,运行额外命令 |
| parameterised query | 参数化查询:用占位符 `%s`,输入作为"数据信封"单独传给数据库驱动 |
| UNION | SQL 关键字,把两个查询结果拼接;攻击里用来"伪造"一行 |
| `shell=True` | Python 里让命令经过 shell 解释(于是 `;` 等有特殊含义);去掉它+用参数列表就安全 |
| payload | 攻击载荷,也就是你故意构造的输入 |

## Part 1:登录处的 SQL 注入

登录拼的是:`SELECT id, username, role, password FROM users WHERE username = '你输入的'`。

**实测重点(要诚实区分)**:课件教的经典招 `admin' --`(把密码判断注释掉)**在我们这版登不进去**。因为第五课加了 Argon2,这版 SQL 只按用户名查出这一行,密码是 Python 里另外用 `check_password` 校验的——SQL 里根本没有"AND 密码"这段可供注释掉。所以这招失败是**实测结果**,不是照抄课件。

但**注入点真实存在**。改用 `UNION` 伪造一行 admin,密码我自己定,就能进:

```
用户名: zzz' UNION SELECT 1,'admin','admin','pwned' --
密码:   pwned
```

修复前:登录返回 302、admin 页 200 = 拿到管理员权限。

> 我踩的一个坑(记下来):演示时 `UNION SELECT 1,...` 用了 `id=1`。因为"遗留密码登录成功会自动升级",这一下把**真实 admin 行**的密码覆盖成了我编的 `pwned`。我已经还原成 `admin123`。**正确做法用一个不存在的 id(比如 999)**,就不会误伤真实数据。

**修复**(代码入口 `web/app.py` 的 `login()`):

```python
query = "SELECT id, username, role, password FROM users WHERE username = %s"
cur.execute(query, (username,))
```

`%s` 不是字符串格式化,是数据库驱动的**占位符**。输入装进单独的"数据信封"送过去,于是 `'`、`--`、`UNION` 全都只是用户名里的普通字符。修复后同样的 UNION 用户名 → 登录失败、admin 页 302。

## Part 3:ping 框的命令注入

`admin_ping()` 原来是 `"ping -c 1 " + host` 再 `shell=True` 执行,`;` 就能接着跑第二条命令。

载荷 `host = 127.0.0.1; id; head -2 /etc/passwd`,修复前返回了 `uid=0(root)...` 和 `/etc/passwd` 前两行——我在服务器上以 root 跑了自己的命令。

**修复**:

```python
result = subprocess.run(
    ["ping", "-c", "1", host],
    capture_output=True, text=True, timeout=10,
)
```

用**参数列表**、不走 shell。整个 `host` 从头到尾是**一个参数**,`;` `|` `&` `$()` 反引号都失效。修复后同样的载荷 → `Name or service not known`(整串被当成一个解析不了的主机名),没有 `id`、没有 `/etc/passwd`。

## 为什么两处是同一个道理

SQL 和 shell 是两种语言,但错误一样:**你的文字被粘进了命令字符串**。凡是"文字遇到解释器"的地方都可能中招——数据库、shell、网页(那是下一课的 XSS)、文件路径。规矩永远一样:**数据走数据的信封,别当命令传。**

## 怎么运行 / 自测

```bash
docker compose -f docker-compose.yml -f compose.windows.yml up -d --build
# 应用在 http://localhost:8080;admin/admin123,alice/alicepw
pytest -q   # 102 项全过
```

测试里新增了 `tests/test_command_injection.py`(`;`/`$()`/反引号都不会执行第二条命令),并把一个旧测试(断言旧漏洞会报 "Query error")改成了修复后的正确断言。

## 自测问题(练完可以自己回答)

1. 为什么 `admin' --` 在我们这版登不进去,但在课件标准版能进?差别在哪一行代码?
2. UNION 注入为什么用 `id=999` 比 `id=1` 安全?
3. 参数化查询和"过滤掉引号"相比,为什么前者才是正解?
4. 命令注入的修复里,去掉 `shell=True` 和改用列表,哪一个才是真正堵住洞的?
