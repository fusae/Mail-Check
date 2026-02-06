# SQLite -> MySQL (Navicat) 迁移说明

适用场景：本项目已切换为 **MySQL-only**，你希望把原先 `processed_emails.db` 的数据迁移到 MySQL。

## 1. 先在 MySQL 侧建表（推荐）

不要让 Navicat 自动建表（它经常把 `AUTO_INCREMENT` 主键建成 `NULL`，导致 1171 报错）。

在项目根目录执行一次（会创建数据库与表/索引）：

```bash
python3 -c "import os; import src.db as db; db.ensure_schema(os.getcwd())"
```

如果你是通过 API 服务启动的，也会自动执行建表逻辑。

## 2. Navicat Data Transfer 正确姿势

1. Source 选择 SQLite：指向 `data/processed_emails.db`
2. Target 选择 MySQL：连接到你的 MySQL，选择目标库（如 `mail_check` / `mail-check`）
3. 选择要迁移的表：
   - `processed_emails`
   - `negative_sentiments`
   - `sentiment_feedback`
   - `feedback_rules`
   - `feedback_queue`
   - `event_groups`（如果你启用了“事件归并/重复舆情”功能）
   - **不要选** `sqlite_sequence`
4. Options（关键）：
   - 取消勾选 `Create tables`
   - 取消勾选 `Drop target objects before create`
   - 勾选 `Create records`
   - 勾选 `Use transaction`

这样 Navicat 只会“导入数据”，不会改你的表结构。

## 3. 常见报错与原因

### 1171 - All parts of a PRIMARY KEY must be NOT NULL

原因：Navicat 自动建表时把主键建成了 `id int NULL AUTO_INCREMENT`。

解决：按本文的“先建表，再迁移记录”的方式，或手工把主键改为 `NOT NULL`（例如 `BIGINT NOT NULL AUTO_INCREMENT`）。

### 1071 - Specified key was too long; max key length is 3072 bytes

原因：`utf8mb4` 下对长文本/长 URL 建“全字段索引”可能超出 InnoDB 索引长度上限。

解决：使用**前缀索引**（例如 `event_url(191)`）。这不会影响 URL 的存储，只影响索引使用方式。

