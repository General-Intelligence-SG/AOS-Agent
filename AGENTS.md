# AOS Agent 协调规范

> 核心原则：AOS 现在以 `objects` 为统一事实源。联系人、项目、会议、任务、文档、记忆，以及它们之间的关系和证据，都应优先按对象模型读写；`tasks`、`knowledge`、`memory` 只是兼容视图，不再是主存储入口。

---

## 1. 总体规则

1. 对结构化信息，优先调用对象化 MCP 工具：
   - 写入优先：`aos_create_object`、`aos_update_object`
   - 关系优先：`aos_link_objects`
   - 证据优先：`aos_add_object_evidence`
   - 查询优先：`aos_list_objects`、`aos_get_object`、`aos_list_object_links`、`aos_list_object_evidences`
2. 旧工具继续可用，但只作为兼容入口：
   - `aos_create_task` / `aos_list_tasks` / `aos_update_task`
   - `aos_create_knowledge` / `aos_search_knowledge` / `aos_get_knowledge`
   - `aos_store_memory` / `aos_recall_memory`
3. 当信息天然包含关联时，不只存单条记录，还要补关系和证据：
   - 例：会议关联项目、会议关联联系人、任务来源于会议纪要
4. 删除、导出、外发、权限变更仍属于高风险动作，必须先确认。

---

## 2. 对象优先映射

| 场景 | 首选对象类型 | 必要动作 |
|---|---|---|
| 联系人 / 客户 / 合作方 | `contact` | `aos_create_object`，必要时关联项目或会议 |
| 项目 / 计划 / 课题 | `project` | `aos_create_object`，阶段变化用 `aos_update_object` |
| 会议 / 访谈 / 沟通纪要 | `meeting` | 建对象，补参与方关系，补纪要证据 |
| 任务 / 待办 / 缺陷 / 评审项 | `work_item` | 建对象，和项目/会议/文档建立关系 |
| 文档 / 知识 / 方案 / 笔记 | `document` | 建对象，必要时补来源证据 |
| 记忆 / 规则 / 偏好 | `memory` | 建对象，按层级写入 detail |

说明：
- `task`、`knowledge`、`doc` 会被规范化到对象类型别名中。
- 专门类型必须带对应 detail 载荷，不能只创建基础 object。

---

## 3. 工具选择顺序

### 3.1 写入

1. 如果要表达“一个实体”或“一个事件”，优先 `aos_create_object`
2. 如果对象之间有上下游、归属、来源、参与、引用关系，补 `aos_link_objects`
3. 如果内容来自会话、消息、文件、外部系统，补 `aos_add_object_evidence`
4. 只有在需要兼容旧流程时，才额外调用旧视图工具

### 3.2 查询

1. 先查对象：
   - `aos_list_objects`
   - `aos_get_object`
   - `aos_list_object_links`
   - `aos_list_object_evidences`
2. 再查旧视图：
   - `aos_list_tasks`
   - `aos_search_knowledge`
   - `aos_recall_memory`
3. 对“这个任务属于哪个项目”“这条结论从哪来”“谁参与了这次会议”这类问题，优先依赖关系和证据，不要只靠文本摘要回答。

---

## 4. 兼容视图约定

1. `work_item` 是任务兼容视图的主对象类型
2. `document` 是知识库兼容视图的主对象类型
3. `memory` 是记忆兼容视图的主对象类型
4. 如果通过对象工具创建了上述类型，必须保证 detail 完整，否则旧接口可能无法检索到它
5. 迁移期内：
   - 新增数据尽量走对象工具
   - 旧工具写入的数据可以继续被对象查询看到
   - 回答时优先用对象视角组织信息

---

## 5. 推荐关系类型

常用 `link_type` 可优先采用以下约定：

- `belongs_to`：任务属于项目，文档属于项目
- `related_to`：普通相关关系
- `depends_on`：任务依赖任务
- `generated_from`：任务由会议或文档提取而来
- `mentions`：会议或文档提到某联系人
- `owner_of`：联系人或 Agent 负责项目 / 任务
- `evidence_for`：通过证据表表达时的语义补充

如果现有类型不够，再扩展，但要保持名称稳定、语义清晰。

---

## 6. 推荐证据策略

出现以下来源时，应优先补证据：

- 对话中提炼出的行动项：记录 `conversation_id` / `message_id`
- 上传文件中抽出的知识：记录 `file_id`
- 外部系统同步来的实体：记录 `source_system_id`
- 文本结论需要可追溯：记录 `snippet_text` 和 `locator`

原则：
- 能追溯来源的对象，不要只留摘要
- 证据不足时，应在回答中说明“这是归纳，不是已验证事实”

---

## 7. 典型操作范式

### 7.1 用户说“帮我记一个项目”

1. `aos_create_object(object_type="project", ...)`
2. 如果同时提到负责人、阶段、进度，写入 `project` detail
3. 如果有负责人联系人，再补联系人对象和关系

### 7.2 用户说“把会议纪要整理成任务”

1. 先创建 `meeting`
2. 给会议补 `document` 或 `file` 相关证据
3. 为每个行动项创建 `work_item`
4. 用 `generated_from` 把任务连回会议

### 7.3 用户问“这个结论从哪来的”

1. `aos_get_object`
2. `aos_list_object_evidences`
3. `aos_list_object_links`
4. 先回答来源链路，再回答内容

---

## 8. 安全红线

以下动作必须确认：

- 删除对象或兼容视图数据
- 导出数据
- 发送外部消息、邮件或通知
- 涉及资金、合同、权限的操作
- 覆盖已有结论且没有保留证据链的更新

---

## 9. 一句话执行标准

能抽象成对象，就不要只记成文本；能建立关系，就不要只存孤岛记录；能补证据，就不要只给结论。
