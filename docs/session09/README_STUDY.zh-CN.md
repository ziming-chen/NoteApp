# 第九课学习说明 — 注入(SQL 注入与命令注入)

> 这份是给子明看的学习版。英文正式报告见 [README.md](README.md),交给老师的 finding 见 [audit.txt](audit.txt)。
> 本次一个人做。修复 commit 为 `420132e`。

## 一句话抓住本质

服务器干活时,会**拼一句话**交给一个“听话的东西”去执行:
- 交给**数据库**,它说的语言是 **SQL**;
- 交给**操作系统外壳(shell)**,它说的语言是**系统命令**。

出 bug 的根源:它把你输入的文字**直接粘进这句话里**。你的文字本该是“答案/数据”,可一旦被粘进去,只要里面带了这句话自己的标点(`'`、`--`、`;`),它就从“数据”变成了“命令的一部分”。这就是**注入**。两处漏洞是同一个错,只是一个在 SQL 里、一个在 shell 里。

修复也是同一个形状:**把数据当数据传,别拼进命令里。**

## 先看这里:和课件的差异

课件 Part 1 假设登录 SQL 是:

```sql
... WHERE username = '你输入的' AND password = '你输入的'
```

但我们这版在第五课已经改过:SQL 只按用户名查一行,密码用 Python 的 `check_password`(Argon2,兼容旧明文)单独校验。**我没有把第五课的加固改回去**,所以课件里的 `admin' --` 在我们这版挡得住——SQL 里根本没有 `AND password = ...` 这一段可供注释。

注入点仍然真实存在。真正完成“无密码登录 admin”的是下面的 **UNION**;这不是照抄课件,是实测结论。

## 英文术语

| 术语 | 意思 |
|---|---|
| SQL injection | SQL 注入:把 SQL 标点注入查询,改变查询结构 |
| command injection | 命令注入:把 shell 标点注入命令,运行额外命令 |
| parameterised query | 参数化查询:用占位符 `%s`,输入作为“数据信封”单独传给数据库驱动 |
| UNION | SQL 关键字,把两个查询结果拼接;攻击里用来“伪造”一行 |
| `shell=True` | Python 里让命令经过 shell 解释(于是 `;` 等有特殊含义);去掉它+用参数列表就安全 |
| payload | 攻击载荷,也就是你故意构造的输入 |

## Part 1:登录处的 SQL 注入

修复前,登录拼的是:

```sql
SELECT id, username, role, password FROM users WHERE username = '你输入的'
```

### 真正的突破:用 UNION 伪造 admin 行

```
用户名: zzz' UNION SELECT 1,'admin','admin','pwned' --
密码:   pwned
```

`UNION` 把“我自己造的一行”接到查询结果后面:这一行的 `id=1`、用户名 `admin`、角色 `admin`、密码 `pwned`。因为这一行的密码是明文 `pwned`,而登录逻辑支持旧明文密码,所以 `check_password('pwned','pwned')` 通过,直接拿到管理员权限。

修复前实测:登录 POST **302**、admin 页 **200** = 拿到管理员权限。证据在 [before/part1b_union_admin_login.txt](evidence/before/part1b_union_admin_login.txt)。

### 课件经典招为什么登不进去

课件教的 `admin' -- `(把密码判断注释掉)在我们这版失败:

```
用户名: admin' --
密码:   anything(错误的密码)
```

结果:登录 POST 200、admin 页 302 = 没进去。原因是 SQL 只按用户名查出这一行,密码是 Python 里另外用 `check_password` 校验的——SQL 里没有“AND 密码”这段可供注释掉。修复后同样还是 200/302,原因不变。

**这是实测结果,不是照抄课件。** 要诚实区分:“课件经典招失败”和“注入点不存在”是两件事;注入点仍然存在,只是换成了 UNION。

## Part 2:把查询拆开——修复

代码入口 `web/app.py` 的 `login()`:

```python
query = "SELECT id, username, role, password FROM users WHERE username = %s"
cur.execute(query, (username,))
```

`%s` 不是字符串格式化,是数据库驱动的**占位符**。输入装进单独的“数据信封”送过去,于是 `'`、`--`、`UNION` 全都只是用户名里的普通字符。

修复后同样的 UNION 用户名 → 登录 POST 200、admin 页 302 = 失败。证据在 [after/part1b_union_blocked.txt](evidence/after/part1b_union_blocked.txt)。

测试里把旧的那条“断言旧漏洞会报 `Query error`”的测试换掉了:留着它等于要求保留漏洞。新测试断言:单独的引号只是普通字符、该输入不再泄露原始 SQL 错误、UNION 不能伪造 admin。

## Part 3:ping 框的命令注入

`admin_ping()` 原来是 `"ping -c 1 " + host` 再 `shell=True` 执行,`;` 就能接着跑第二条命令。

载荷 `host = 127.0.0.1; id; head -2 /etc/passwd`,修复前返回了 `uid=0(root)...` 和 `/etc/passwd` 前两行——我在自己的容器里以 root 跑了自己的命令。证据在 [before/part3_cmdinjection_output.txt](evidence/before/part3_cmdinjection_output.txt)。

**修复**:

```python
result = subprocess.run(
    ["ping", "-c", "1", host],
    capture_output=True, text=True, timeout=10,
)
```

用**参数列表**、不走 shell。整个 `host` 从头到尾是**一个参数**,`;` `|` `&` `$()` 反引号都失效。修复后同样的载荷 → `Name or service not known`(整串被当成一个解析不了的主机名),没有 `id`、没有 `/etc/passwd`。证据在 [after/part3_cmdinjection_blocked.txt](evidence/after/part3_cmdinjection_blocked.txt)。

## 为什么两处是同一个道理

SQL 和 shell 是两种语言,但错误一样:**你的文字被粘进了命令字符串**。凡是“文字遇到解释器”的地方都可能中招——数据库、shell、网页(那是下一课的 XSS)、文件路径。规矩永远一样:**数据走数据的信封,别当命令传。**

## 数据完整性:我踩的坑

演示 UNION 时用了 `id=1`。因为“遗留明文密码登录成功会自动升级”,这一下把**真实 admin 行**的密码覆盖成了我编的 `pwned`。

我已经把密码重置为 `admin123`,并用一次新的 admin 登录验证通过;现在存的是 Argon2id 哈希,不是原始 seed 明文。其他表没有改动。**正确做法是用一个不存在的 id(比如 999)**,就不会误伤真实数据。这个坑值得记下来:攻击演示也会改数据,做之前先想好副作用。

## 怎么运行 / 自测

```bash
docker compose -f docker-compose.yml -f compose.windows.yml up -d --build
# 应用在 http://localhost:8080;admin/admin123,alice/alicepw
python -m pip install -r requirements-dev.txt
pytest -q   # 102 项全过
```

测试里新增了 `tests/test_command_injection.py`(`;`/`$()`/反引号都不会执行第二条命令),并把一个旧测试(断言旧漏洞会报 "Query error")改成了修复后的正确断言。命令注入测试是“负向控制”(确认没有 `uid=`、没有 `/etc/passwd`);普通 ping 的正向控制看 Part 4 证据。

## 自测问题(练完可以自己回答)

1. 为什么 `admin' --` 在我们这版登不进去,但在课件标准版能进?差别在哪一行代码?
2. UNION 注入为什么用 `id=999` 比 `id=1` 安全?
3. 参数化查询和“过滤掉引号”相比,为什么前者才是正解?
4. 命令注入的修复里,去掉 `shell=True` 和改用参数列表,哪一个才是真正堵住洞的?
5. 为什么参数化查询之后,`UNION` 这个“SQL 关键字”就失效了?它变成了什么?
