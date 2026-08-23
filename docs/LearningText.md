# AI Agent 与大模型应用开发学习文档

> 本文档面向面试准备与技能提升，覆盖 LangChain、LangGraph、React、多 Agent 系统、Skill 开发与国内 Agent 生态六大主题。每节标注 🎯 面试高频考点。

---

## 目录

1. [LangChain 底层原理与源码解读](#1-langchain-底层原理与源码解读)
2. [LangGraph 状态图编排](#2-langgraph-状态图编排)
3. [React 前端框架原理](#3-react-前端框架原理)
4. [多 Agent 系统设计](#4-多-agent-系统设计)
5. [Skill 搭建与脚本开发](#5-skill-搭建与脚本开发)
6. [国内 Agent 开发生态分析](#6-国内-agent-开发生态分析)

---

## 1. LangChain 底层原理与源码解读

### 1.1 LCEL 表达式语言原理（Runnable 管道）

#### 1.1.1 核心概念

- **LCEL（LangChain Expression Language）**：LangChain v0.1+ 推出的声明式组合语法，通过管道符 `|` 将 Runnable 组件串联成链。
- **Runnable 协议**：所有 LCEL 组件都实现 `Runnable` 接口，统一提供 `invoke`/`batch`/`stream`/`ainvoke` 等方法，实现"可组合、可流式、可异步、可批处理"。
- **管道语义**：`A | B` 等价于 `B(A.invoke(x))`，但带有：
  - 自动异步支持
  - 流式 token 传输（token-by-token）
  - 内置重试、超时、并行
  - Callback/Tracing 自动注入

#### 1.1.2 基础示例

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

# LCEL 管道：prompt -> model -> parser
prompt = ChatPromptTemplate.from_template("用一句话解释 {topic}")
model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
parser = StrOutputParser()

chain = prompt | model | parser

# 同步调用
result = chain.invoke({"topic": "量子计算"})
# 流式调用
for chunk in chain.stream({"topic": "量子计算"}):
    print(chunk, end="", flush=True)
# 异步批处理
results = await chain.abatch([{"topic": "AI"}, {"topic": "区块链"}])
```

#### 1.1.3 Runnable 接口核心方法

| 方法 | 说明 |
|------|------|
| `invoke(input)` | 单次同步调用 |
| `ainvoke(input)` | 单次异步调用 |
| `batch(inputs)` | 批量同步调用（自动并行） |
| `abatch(inputs)` | 批量异步调用 |
| `stream(input)` | 同步流式输出 |
| `astream(input)` | 异步流式输出 |
| `with_config(config)` | 注入运行时配置（tags/metadata/callbacks） |
| `with_retry()` | 自动重试包装 |
| `with_types()` | 类型注解强化 |

#### 1.1.4 管道实现原理

🎯 **面试高频考点**：LCEL 管道本质是 `RunnableSequence`，它在调用时按顺序执行各 Runnable，并把上一步输出作为下一步输入。关键点：

- **输入输出协议对齐**：每个 Runnable 都有 `input_type` 与 `output_type`，管道在运行时通过 Pydantic 做类型校验。
- **流式透传**：`RunnableSequence.stream` 会用 `transform` 方法逐 chunk 传递，而不是等整段生成完再传给下一步。
- **callback 继承**：父 Runnable 的 callbacks 会被自动透传给子 Runnable，实现全链路追踪。

```python
# 简化版 RunnableSequence 伪代码
class RunnableSequence(Runnable):
    def __init__(self, first, last):
        self.first = first
        self.last = last

    def invoke(self, input, config=None):
        # 1. 把 callbacks 透传给每一步
        # 2. 顺序执行：first.invoke -> ... -> last.invoke
        result = self.first.invoke(input, config)
        return self.last.invoke(result, config)

    def stream(self, input, config=None):
        # 1. 用 transform 逐 chunk 处理
        # 2. 上一步产出 chunk 就立即喂给下一步
        for chunk in self.first.stream(input, config):
            yield from self.last.transform(iter([chunk]), config)
```

### 1.2 Chain / Memory / Retriever / Tool 核心抽象

#### 1.2.1 Chain（旧版链 vs LCEL）

- **旧版 `Chain` 类**：基于 `BaseChain`，通过 `_call` 实现逻辑，已被官方标记为 legacy。
- **LCEL 推荐**：用 `prompt | model | parser` 替代 `LLMChain`，更灵活、更易调试。
- **迁移建议**：新项目直接用 LCEL；老项目可逐步迁移。

```python
# 旧版（不推荐）
from langchain.chains import LLMChain
chain = LLMChain(llm=model, prompt=prompt)

# LCEL 版（推荐）
chain = prompt | model | parser
```

#### 1.2.2 Memory（记忆机制）

🎯 **面试高频考点**：Memory 的本质是"上下文窗口管理"，常见四种策略：

| 类型 | 代表类 | 适用场景 |
|------|--------|----------|
| 简单缓冲 | `ConversationBufferMemory` | 短对话，token 充足 |
| 窗口缓冲 | `ConversationBufferWindowMemory` | 只保留最近 K 轮 |
| 摘要记忆 | `ConversationSummaryMemory` | 长对话，用 LLM 滚动摘要 |
| 向量记忆 | `VectorStoreRetrieverMemory` | 超长对话，按相关性检索 |

```python
from langchain.memory import ConversationBufferWindowMemory

memory = ConversationBufferWindowMemory(k=5, return_messages=True)
memory.save_context({"input": "你好"}, {"output": "你好，我是助手"})
# 取最近 5 轮作为上下文
history = memory.load_memory_variables({})
```

> ⚠️ LangChain v0.3 起，Memory 推荐迁移到 `RunnableWithMessageHistory` 或 LangGraph 的 State 持久化方案。

#### 1.2.3 Retriever（检索器）

🎯 **面试高频考点**：Retriever 是 RAG 的核心抽象，统一接口 `get_relevant_documents(query)`。

- **向量检索**：`VectorStoreRetriever`，基于 embedding 相似度
- **关键词检索**：`BM25Retriever`，基于词频
- **混合检索**：`EnsembleRetriever`，向量 + 关键词加权
- **多查询检索**：`MultiQueryRetriever`，用 LLM 改写多个 query 提召回
- **压缩检索**：`ContextualCompressionRetriever`，先召回再用 LLM 压缩

```python
from langchain_community.retrievers import BM25Retriever
from langchain.retrievers import EnsembleRetriever

vector_retriever = vectorstore.as_retriever(search_kwargs={"k": 5})
bm25_retriever = BM25Retriever.from_documents(docs)
ensemble = EnsembleRetriever(
    retrievers=[vector_retriever, bm25_retriever],
    weights=[0.6, 0.4]
)
```

#### 1.2.4 Tool（工具调用）

- **Tool 抽象**：`BaseTool`，包含 `name`、`description`、`args_schema`、`_run`/`_arun`。
- **工具绑定**：`model.bind_tools([tool1, tool2])`，把工具 schema 注入模型。
- **工具调用循环**：Agent 调用工具后，需要把结果回填给模型再决策（见 LangGraph 部分）。

```python
from langchain_core.tools import tool

@tool
def search_weather(city: str) -> str:
    """查询指定城市的天气"""
    return f"{city} 今天晴，25℃"

model_with_tools = model.bind_tools([search_weather])
```

### 1.3 Callback / Tracing 机制

#### 1.3.1 Callback 架构

🎯 **面试高频考点**：Callback 是 LangChain 的可观测性基石，事件流贯穿整个 Runnable 链。

- **核心抽象**：`BaseCallbackHandler`，定义 `on_llm_start`、`on_llm_new_token`、`on_chain_start`、`on_tool_start` 等钩子。
- **触发时机**：每个 Runnable 在关键节点会调用 `callback_manager.on_xxx`。
- **多 handler 支持**：一次调用可挂载多个 handler（日志、监控、Tracing 同时进行）。

```python
from langchain_core.callbacks import BaseCallbackHandler

class MyHandler(BaseCallbackHandler):
    def on_llm_start(self, serialized, prompts, **kwargs):
        print(f"LLM 开始: {prompts[0][:30]}...")

    def on_llm_new_token(self, token, **kwargs):
        print(f"新 token: {token}", end="")

    def on_tool_end(self, output, **kwargs):
        print(f"工具结束: {output}")

chain.invoke({"topic": "AI"}, config={"callbacks": [MyHandler()]})
```

#### 1.3.2 LangSmith Tracing

- LangSmith 是官方的可观测平台，通过环境变量自动接入：

```bash
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=ls_xxx
export LANGCHAIN_PROJECT=my-project
```

- 接入后每次 `invoke` 都会在 LangSmith 看到完整调用树：prompt → model → tool → parser，含 token、延迟、cost。

### 1.4 核心源码文件解读

#### 1.4.1 `runnable.py`（核心：Runnable 协议）

🎯 **面试高频考点**：`Runnable` 是 LangChain 的"灵魂抽象"，所有可执行组件都继承它。

关键源码位置：`libs/core/langchain_core/runnables/base.py`

```python
class Runnable(RunnableSerializable):
    # 1. 核心执行入口
    def invoke(self, input, config=None, **kwargs):
        # 默认实现：用 transform 把同步转流式
        config = ensure_config(config)
        return self._call_with_config(self._invoke, input, config)

    # 2. 流式入口
    def stream(self, input, config=None, **kwargs):
        # 默认实现：invoke 后 yield 整个结果
        yield self.invoke(input, config)

    # 3. 配置注入
    def with_config(self, config):
        return RunnableBinding(self, config=config)

    # 4. 重试包装
    def with_retry(self, **kwargs):
        return RunnableWithRetry(self, **kwargs)

    # 5. 类型协议（子类可覆盖）
    @property
    def InputType(self): ...
    @property
    def OutputType(self): ...
```

**设计精髓**：
- 所有组件实现同一接口 → 可任意组合
- `invoke`/`stream`/`batch` 都有默认实现 → 子类只需覆盖关键的
- `config` 贯穿全链路 → callbacks/metadata/tags 自动透传

#### 1.4.2 `chain.py`（Chain 抽象）

关键源码：`libs/langchain/langchain/chains/base.py`

```python
class BaseChain(ABC, RunnableSerializable):
    memory: BaseMemory
    callbacks: Callbacks
    verbose: bool

    @abstractmethod
    def _call(self, inputs: dict) -> dict:
        """子类实现具体逻辑"""

    def invoke(self, input, config=None):
        # 1. 从 memory 加载上下文
        # 2. 调用 _call
        # 3. 保存到 memory
        # 4. 触发 callbacks
```

> ⚠️ Chain 类已标记 legacy，新代码建议用 LCEL。但理解它的设计有助于读懂老项目。

#### 1.4.3 `memory.py`（记忆抽象）

关键源码：`libs/langchain/langchain/memory/chat_memory.py`

```python
class BaseChatMemory(BaseMemory):
    chat_memory: BaseChatMessageHistory  # 历史存储后端
    return_messages: bool = False
    input_key: str = "input"
    output_key: str = "output"

    def save_context(self, inputs, outputs):
        # 1. 把 input/output 转成 HumanMessage/AIMessage
        # 2. 写入 chat_memory
        self.chat_memory.add_user_message(inputs[self.input_key])
        self.chat_memory.add_ai_message(outputs[self.output_key])

    def load_memory_variables(self, inputs):
        # 子类覆盖：决定如何裁剪/摘要
        return {"history": self.buffer_as_messages}
```

**记忆设计关键**：
- 存储与裁剪解耦：`chat_memory` 负责"存"，`BaseChatMemory` 子类负责"取"
- 可换后端：`ChatMessageHistory` 支持 Redis/Postgres/文件/SQL 多种后端

---

## 2. LangGraph 状态图编排

### 2.1 StateGraph / Node / Edge 核心概念

#### 2.1.1 为什么需要 LangGraph

🎯 **面试高频考点**：LangChain 的 AgentExecutor 是"循环 + 工具调用"，但难以表达复杂流程（条件分支、人在回路、并行、持久化）。LangGraph 把 Agent 抽象为**状态机**，更通用、更可控。

#### 2.1.2 三大核心抽象

| 概念 | 说明 |
|------|------|
| **State** | 共享数据结构（TypedDict/Pydantic），节点读写它 |
| **Node** | 接收 state、返回 state 更新的函数 |
| **Edge** | 节点间的连接，可为普通或条件边 |

```python
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from operator import add

class State(TypedDict):
    messages: Annotated[list, add]  # 用 reducer 累加而非覆盖

def chatbot(state: State):
    response = model.invoke(state["messages"])
    return {"messages": [response]}

graph_builder = StateGraph(State)
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_edge(START, "chatbot")
graph_builder.add_edge("chatbot", END)
graph = graph_builder.compile()
```

**Annotated + reducer 是关键**：默认 state 字段会被新值覆盖；用 `Annotated[list, add]` 可以让节点返回的 list 被 append 累加，这是消息历史能持续累积的原理。

### 2.2 Conditional Branch（条件分支）

🎯 **面试高频考点**：条件边是 LangGraph 表达复杂流程的核心。

```python
def route_after_tool(state: State) -> str:
    last_msg = state["messages"][-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "tools"
    return END

graph_builder.add_conditional_edges(
    "agent",            # 起点
    route_after_tool,   # 路由函数（返回字符串或字典）
    {
        "tools": "tools",   # 返回值 -> 目标节点
        END: END
    }
)
graph_builder.add_edge("tools", "agent")  # 工具执行完回到 agent
```

**路由函数约定**：
- 接收 state，返回字符串或 list（多目标，实现 fan-out 并行）
- 返回值需在 `path_map` 字典的 keys 中

### 2.3 Checkpointing 持久化

🎯 **面试高频考点**：Checkpoint 是 LangGraph 实现"断点续跑""记忆持久化""人机回路"的基础。

```python
from langgraph.checkpoint.memory import MemorySaver
# 生产用：
# from langgraph_checkpoint_sqlite import SqliteSaver
# from langgraph_checkpoint_postgres import PostgresSaver

checkpointer = MemorySaver()
graph = graph_builder.compile(checkpointer=checkpointer)

# 用 thread_id 关联会话
config = {"configurable": {"thread_id": "user-123"}}
graph.invoke({"messages": [{"role": "user", "content": "我叫张三"}]}, config)
# 下次调用自动恢复上下文
graph.invoke({"messages": [{"role": "user", "content": "我叫什么"}]}, config)
# → "你叫张三"
```

**原理**：每个 super-step 结束后，LangGraph 把当前 state 序列化写入 checkpointer。下次同一 `thread_id` 调用时先从 checkpointer 反序列化 state，再继续执行。

### 2.4 Human-in-the-loop 机制

🎯 **面试高频考点**：让"人"在 Agent 执行过程中介入，常用于工具审核、危险操作确认、信息补充。

#### 2.4.1 interrupt_before（执行前暂停）

```python
graph = graph_builder.compile(
    checkpointer=checkpointer,
    interrupt_before=["sensitive_tool"]  # 进入该节点前暂停
)
# 第一次调用会暂停在 sensitive_tool 前
graph.invoke(input, config)
# 审核后继续
graph.invoke(None, config)  # 传 None 表示继续上次
```

#### 2.4.2 interrupt_after + 动态更新 state

```python
# 暂停后人工修改 state
state = graph.get_state(config)
state.values["messages"][-1] = human_approved_msg
graph.update_state(config, {"messages": [human_approved_msg]})
graph.invoke(None, config)
```

### 2.5 与 LangChain AgentExecutor 的区别

| 维度 | AgentExecutor | LangGraph |
|------|---------------|-----------|
| 抽象 | 循环 + 工具调用 | 状态机 + 图 |
| 流程表达 | 单一 Agent 循环 | 条件分支、并行、子图 |
| 持久化 | 需自己实现 Memory | 内置 Checkpoint |
| 人机回路 | 难 | 原生支持 interrupt |
| 多 Agent | 难组织 | 用图天然支持 |
| 流式中间态 | 弱 | 每个 node 都可流式 |
| 调试 | 黑盒 | 可视化图 + state 快照 |

🎯 **面试结论**：新项目优先选 LangGraph，AgentExecutor 已逐步被官方边缘化。

---

## 3. React 前端框架原理

### 3.1 Virtual DOM diff 算法

#### 3.1.1 为什么需要 Virtual DOM

- 直接操作真实 DOM 成本高（重排/重绘），框架用 JS 对象描述 UI（vnode），diff 后只更新差异部分。
- 跨平台：同一 vnode 树可渲染到 DOM、Native、SSR、Canvas。

#### 3.1.2 Diff 三层假设

🎯 **面试高频考点**：React diff 复杂度从 O(n³) 降到 O(n²)→O(n)，靠三个假设：

1. **同层比较**：只比较同层级节点，不跨层。
2. **类型不同直接替换**：`<div>` 变 `<span>` 直接销毁重建。
3. **key 标识列表项**：通过 key 复用同类型节点，避免重渲染整个列表。

#### 3.1.3 简化 diff 伪代码

```javascript
function diff(oldVNode, newVNode) {
  // 1. 新节点不存在 -> 删除旧
  if (!newVNode) return { type: 'REMOVE', node: oldVNode };
  // 2. 类型不同 -> 替换
  if (oldVNode.type !== newVNode.type) {
    return { type: 'REPLACE', newNode: newVNode };
  }
  // 3. 文本节点 -> 比较内容
  if (typeof oldVNode === 'string') {
    if (oldVNode !== newVNode) return { type: 'TEXT', text: newVNode };
    return null;
  }
  // 4. 同类型元素 -> diff props + diff children（带 key）
  const propPatches = diffProps(oldVNode.props, newVNode.props);
  const childPatches = diffChildren(oldVNode.children, newVNode.children);
  return { type: 'UPDATE', propPatches, childPatches };
}
```

### 3.2 Fiber 架构

#### 3.2.1 为什么需要 Fiber

🎯 **面试高频考点**：React 15 的 reconciler 是同步递归的，一旦开始 diff 就停不下来，大组件树会卡 UI 线程。Fiber 架构（React 16+）把渲染工作拆成可中断、可恢复的小单元。

#### 3.2.2 Fiber 数据结构

每个组件对应一个 Fiber 节点，构成链表树：

```typescript
type Fiber = {
  type: 'div' | Function | Class,  // 组件类型
  key: string | null,
  stateNode: Element | Instance,   // 真实 DOM 或类实例
  child: Fiber | null,             // 第一个子节点
  sibling: Fiber | null,           // 下一个兄弟
  return: Fiber | null,            // 父节点
  pendingProps: any,                // 新 props
  memoizedProps: any,              // 旧 props
  memoizedState: any,              // 旧 state（hooks 链表头）
  updateQueue: UpdateQueue,        // 更新队列
  flags: Flags,                    // 副作用标记（插入/更新/删除）
  lanes: Lanes,                    // 优先级
  alternate: Fiber | null,        // 双缓冲对应节点
};
```

#### 3.2.3 双阶段调度

🎯 **面试高频考点**：Fiber 工作分两阶段。

| 阶段 | 名称 | 工作内容 | 可中断 |
|------|------|----------|--------|
| 1 | Render（render phase） | 构建 workInProgress 树、计算 flags | ✅ 可被高优任务打断 |
| 2 | Commit（commit phase） | 把 flags 应用到真实 DOM、跑生命周期/useEffect | ❌ 同步不可中断 |

**时间切片**：Render 阶段用 `MessageChannel` 调度，每帧给 5ms，到点就让出主线程。

### 3.3 Hooks 原理（useState / useEffect 闭包）

#### 3.3.1 Hooks 链表

🎯 **面试高频考点**：Hooks 数据存在 Fiber 的 `memoizedState` 上，是一条**单向链表**。每次函数组件渲染，按调用顺序从链表取对应 hook。

```javascript
// useState 简化实现
function useState(initialValue) {
  const hook = currentHookNode;  // 当前 fiber 的 hook 节点
  if (hook === null) {
    // 首次：初始化
    currentHookNode = {
      state: typeof initialValue === 'function' ? initialValue() : initialValue,
      next: null,
      queue: [],  // 待处理的 update
    };
  }
  // 处理 queue 累积的更新
  hook.queue.forEach(update => hook.state = update(hook.state));
  const setState = (action) => {
    hook.queue.push(action);
    scheduleUpdate();  // 触发重新渲染
  };
  currentHookNode = hook.next;  // 移到下一个 hook
  return [hook.state, setState];
}
```

**为什么不能在条件分支里调用 Hook**：因为靠调用顺序匹配链表位置，顺序变化会导致 state 错位。

#### 3.3.2 useState 闭包陷阱

🎯 **面试高频考点**：经典面试题。

```javascript
function Counter() {
  const [count, setCount] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => {
      setCount(count + 1);  // ❌ 永远是 1，count 被闭包锁死
    }, 1000);
    return () => clearInterval(timer);
  }, []);  // 空依赖，effect 只跑一次
}
```

**原因**：effect 在首次渲染时注册，闭包捕获的 `count` 是 0，永远不变。

**解法**：
1. 函数式更新：`setCount(c => c + 1)`
2. 把 `count` 加进依赖数组（但会反复重建 timer）
3. 用 `useRef` 存最新值

```javascript
const countRef = useRef(count);
countRef.current = count;  // 每次渲染同步
setInterval(() => setCount(countRef.current + 1), 1000);
```

#### 3.3.3 useEffect vs useLayoutEffect

| 维度 | useEffect | useLayoutEffect |
|------|-----------|-----------------|
| 执行时机 | Commit 后异步 | DOM 变更后同步，paint 前 |
| 阻塞渲染 | 否 | 是 |
| 适用 | 数据请求、订阅 | 测量 DOM、防闪烁 |

### 3.4 Reconciliation 调和过程

🎯 **面试高频考点**：Reconciliation = 把 React 元素树与上次 Fiber 树对比，生成新 workInProgress 树的过程。

#### 流程

1. **触发更新**：`setState`/`useState` 触发，标记当前 fiber 的 lanes。
2. **调度**：Scheduler 根据优先级决定何时开始 work。
3. **Begin Work**：自顶向下遍历，为每个组件创建/复用子 fiber，处理 props。
4. **Complete Work**：自底向上，收集 flags（Placement/Update/Deletion）。
5. **Commit**：遍历带 flags 的 fiber，操作 DOM，执行 `useLayoutEffect` → paint → `useEffect`。

#### 优先级模型（Lanes）

```typescript
// React 18 的 lanes（位运算）
const SyncLane = 0b0001;          // 同步，最高
const InputContinuousLane = 0b0010; // 输入连续
const DefaultLane = 0b0100;        // 默认
const TransitionLane = 0b1000;     // transition（startTransition）
```

### 3.5 React 19 新特性

#### 3.5.1 主要新特性

🎯 **面试高频考点**：

1. **Actions（原 useFormStatus/useFormState）**：简化异步表单提交。
2. **`use` API**：在渲染中读 Promise/Context，可与条件分支共存。
3. **Server Components 稳定**：RSC 可直接访问后端、零客户端 JS。
4. **Document Metadata**：组件内写 `<title>`/`<meta>`，自动 hoist。
5. **Asset Loading APIs**：`preload`/`preinit` 显式控制资源加载。
6. **ref as prop**：函数组件不再需要 `forwardRef`。
7. **Context as Provider**：`<Context>` 可直接当 Provider，不用 `.Provider`。

#### 3.5.2 use() 示例

```jsx
import { use } from 'react';

function Note({ promise }) {
  // 在渲染中"等待" Promise，自动 Suspense
  const note = use(promise);
  return <p>{note.body}</p>;
}

// 可在条件分支里用，hook 不行
function Conditional({ cond, promise }) {
  if (cond) {
    const data = use(promise);  // ✅ 合法
    return <div>{data}</div>;
  }
  return null;
}
```

#### 3.5.3 Actions 示例

```jsx
import { useActionState } from 'react';

function Form() {
  const [state, formAction, isPending] = useActionState(
    async (prev, formData) => {
      const name = formData.get('name');
      await submitToServer(name);
      return { ok: true };
    },
    null
  );
  return (
    <form action={formAction}>
      <input name="name" />
      <button disabled={isPending}>提交</button>
    </form>
  );
}
```

---

## 4. 多 Agent 系统设计

### 4.1 Multi-Agent 协作模式

#### 4.1.1 三大协作模式

🎯 **面试高频考点**：

| 模式 | 结构 | 优势 | 劣势 | 适用 |
|------|------|------|------|------|
| **中心化（Hub-spoke）** | 一个 orchestrator 调度多个 worker | 控制清晰、易调试 | 中心节点成瓶颈 | 工具型任务分发 |
| **去中心化（P2P）** | Agent 间直接通信 | 涌现性强、抗单点 | 难预测、易跑偏 | 探索式、辩论 |
| **层级（hierarchical）** | 主管 Agent 拆解任务给子 Agent，结果逐层汇总 | 复杂任务分解清晰 | 上下文丢失风险 | 项目管理、复杂推理 |

#### 4.1.2 中心化示例（Supervisor 模式）

LangGraph 中的 supervisor 模式：

```python
from langgraph.graph import StateGraph, START, END

class TeamState(TypedDict):
    messages: Annotated[list, add]
    next: str

def supervisor(state):
    # LLM 决策下一步交给谁
    decision = supervisor_llm.invoke(state["messages"])
    return {"next": decision.agent}  # "researcher" | "writer" | "FINISH"

def researcher(state):
    result = research_agent.invoke(state["messages"])
    return {"messages": [result]}

builder = StateGraph(TeamState)
builder.add_node("supervisor", supervisor)
builder.add_node("researcher", researcher)
builder.add_node("writer", writer)
builder.add_conditional_edges("supervisor", lambda s: s["next"], {
    "researcher": "researcher",
    "writer": "writer",
    "FINISH": END
})
# 每个工具 Agent 执行完回到 supervisor
builder.add_edge("researcher", "supervisor")
builder.add_edge("writer", "supervisor")
builder.add_edge(START, "supervisor")
```

#### 4.1.3 去中心化示例（Swarm）

OpenAI Swarm 的核心思路是 `handoff`：Agent A 处理完后把任务"递"给 Agent B。

```python
def handoff_to_billing(context):
    return billing_agent.invoke(context)

triage_agent = Agent(
    name="Triage",
    instructions="负责分流，必要时交接给 billing",
    functions=[handoff_to_billing],
)
```

### 4.2 AutoGen / CrewAI / MetaGPT 框架对比

🎯 **面试高频考点**：理解三个主流多 Agent 框架的设计哲学差异。

| 维度 | AutoGen | CrewAI | MetaGPT |
|------|---------|--------|---------|
| 出身 | 微软 | Crew Inc. | 国内开源 |
| 核心抽象 | ConversableAgent + GroupChat | Crew + Agent + Task + Role | Role + SOP 流程 |
| 通信方式 | 对话式（Agent 间互发消息） | 任务委派 | 标准操作流程（SOP）编码 |
| 强项 | 对话式协作、代码生成 | 角色定义清晰、上手快 | 模拟软件公司 SOP |
| 弱项 | 流程控制松散 | 调试困难 | 通用性弱、定制难 |
| 典型场景 | 多 Agent 辩论、研发 | 营销/研究 Crew | 模拟软件研发流程 |

#### AutoGen 示例

```python
from autogen import AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager

coder = AssistantAgent("coder", system_prompt="你是 Python 工程师")
reviewer = AssistantAgent("reviewer", system_prompt="你是代码审查员")
user = UserProxyAgent("user", human_input_mode="NEVER")

gc = GroupChat(agents=[coder, reviewer, user], messages=[], max_round=10)
manager = GroupChatManager(groupchat=gc)
user.initiate_chat(manager, message="写一个并查集")
```

#### CrewAI 示例

```python
from crewai import Agent, Task, Crew

researcher = Agent(
    role="Researcher",
    goal="搜集 LLM 资料",
    backstory="资深研究员",
    tools=[search_tool],
)
writer = Agent(
    role="Writer",
    goal="写成报告",
    backstory="资深技术写作",
)
crew = Crew(
    agents=[researcher, writer],
    tasks=[
        Task(description="搜集资料", agent=researcher),
        Task(description="写报告", agent=writer),
    ],
)
result = crew.kickoff()
```

### 4.3 Agent 通信协议（A2A）

🎯 **面试高频考点**：A2A（Agent2Agent）协议由 Google 牵头，解决不同厂商 Agent 互通问题。

#### 核心概念

- **Agent Card**：JSON-LD 文档，描述 Agent 能力、端点、认证、技能。
- **Task**：A2A 的核心工作单元，有生命周期（submitted → working → done）。
- **Message**：任务中 Agent 与 Agent 的消息，含多个 Part。
- **Artifact**：任务产出的最终结果。
- **Transport**：默认 JSON-RPC 2.0 over HTTPS，支持 SSE 流式。

#### Agent Card 示例

```json
{
  "name": "TravelPlanner",
  "description": "规划旅行行程",
  "url": "https://agent.example.com/a2a",
  "version": "1.0",
  "capabilities": {
    "streaming": true,
    "pushNotifications": true
  },
  "skills": [
    {
      "id": "plan_trip",
      "name": "规划行程",
      "description": "根据目的地和预算生成行程"
    }
  ],
  "authentication": { "schemes": ["bearer"] }
}
```

#### A2A 调用流程

1. 客户端发现 Agent（拉取 Agent Card）
2. `tasks/send` 提交任务
3. 服务端 `working` 状态，可选 `tasks/sendSubscribe` SSE 流式
4. 客户端可发 `tasks/cancel` 取消
5. 完成后返回 `Artifact`

### 4.4 任务分配与冲突解决

#### 4.4.1 任务分配策略

🎯 **面试高频考点**：

- **能力匹配（capability matching）**：按 Agent 的 skills 字段做匹配。
- **负载均衡（load balancing）**：维护每个 Agent 当前任务数，挑最闲的。
- **优先级队列**：高优任务插队，低优排队。
- **拍卖式（contract net）**：广播任务 → Agent 投标 → 中标者执行。

#### 4.4.2 冲突类型与解决

| 冲突类型 | 表现 | 解决方法 |
|----------|------|----------|
| 资源冲突 | 多 Agent 同时写同一文件 | 加锁、Actor 模型单写 |
| 观点冲突 | 两 Agent 给出矛盾结论 | 引入"裁判 Agent"投票/辩论 |
| 死锁 | A 等 B，B 等 A | 超时回退 + 检测环 |
| 目标冲突 | Agent 目标互相抵消 | 顶层目标对齐 + 优先级 |

#### 4.4.3 共享状态设计要点

- 优先用**消息传递**而非共享内存（更好并行、更易扩缩容）
- 共享状态用 `reducer` 累加而非覆盖（避免互相覆盖）
- 关键状态加版本号（乐观锁）

---

## 5. Skill 搭建与脚本开发

### 5.1 MCP（Model Context Protocol）协议详解

#### 5.1.1 MCP 是什么

🎯 **面试高频考点**：MCP 是 Anthropic 在 2024 年开源的协议，目标是**让 LLM 与外部工具/数据源标准化对接**，被比喻为"AI 的 USB-C"。

- 协议层：基于 JSON-RPC 2.0，传输支持 stdio 和 HTTP+SSE。
- 三类能力：**Tools**（可调用函数）、**Resources**（可读数据）、**Prompts**（可复用提示模板）。
- 生态：官方 SDK 支持 Python/TypeScript/Java 等，社区已有大量 MCP server。

#### 5.1.2 MCP 架构

```
┌─────────────┐  JSON-RPC   ┌──────────────┐
|  MCP Client | <─────────> |  MCP Server  |
|  (Claude等) |  stdio/SSE  | (filesystem) |
└─────────────┘             └──────────────┘
       │
       ▼
   LLM 决策调用
```

#### 5.1.3 用 Python 写一个 MCP Server

```python
from mcp.server import Server
from mcp.types import Tool

app = Server("weather-server")

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_weather",
            description="查询城市天气",
            inputSchema={
                "type": "object",
                "properties": {
                    "city": {"type": "string"}
                },
                "required": ["city"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name, arguments):
    if name == "get_weather":
        city = arguments["city"]
        return [{"type": "text", "text": f"{city} 晴 25℃"}]

if __name__ == "__main__":
    import mcp.server.stdio as stdio
    app.run(stdio)
```

#### 5.1.4 TRAE 中接入 MCP

TRAE 通过 `mcp` 字段在 plugin 中声明 MCP server 配置，AI agent 会自动发现并按需调用其 tools。

### 5.2 Skill 设计模式

🎯 **面试高频考点**：Skill = 可复用的"任务能力包"，由 skill 文件（YAML/MD）+ 资源组成，AI 通过读取 skill 描述决定何时调用。

#### 5.2.1 好的 Skill 设计原则

- **单一职责**：一个 skill 解决一类问题，避免"万能 skill"。
- **自描述**：description 写清"何时该用、何时不该用"。
- **可组合**：skill 之间能协作（一个 skill 调另一个 skill）。
- **幂等**：重复调用同样输入结果一致。
- **可观测**：关键步骤打 log，便于调试。

#### 5.2.2 Skill 生命周期

```
触发判断（description + 用户意图）
  → 加载 skill prompt
  → 执行 skill 内的步骤（可能调用 tools/MCP）
  → 返回结果
```

#### 5.2.3 Skill 骨架示例

```yaml
name: pdf-to-markdown
description: |
  当用户需要把 PDF 转成 Markdown 时使用。
  不适用于扫描版无文字层的 PDF。
inputs:
  - name: file_path
    type: string
    description: PDF 文件绝对路径
steps:
  - tool: pdf.parse
    args: { file_path: "{{file_path}}" }
  - tool: markdown.normalize
    args: { content: "{{steps[0].output}}" }
outputs:
  - name: markdown
    type: string
```

### 5.3 脚本化工作流编排

#### 5.3.1 何时脚本化

- 任务步骤固定、频繁复现 → 写成脚本（Python/Node）而非每次让 LLM 临时决策。
- 可重复、可版本控制、可单测。

#### 5.3.2 LangGraph 作为编排引擎

LangGraph 天然适合做"脚本化"工作流：节点是确定性函数，边是条件，整体可断点续跑。

```python
import subprocess
from langgraph.graph import StateGraph, START, END

class FlowState(TypedDict):
    code: str
    test_result: str
    lint_passed: bool

def write_code(state):
    code = llm.invoke("写代码")
    return {"code": code}

def lint(state):
    r = subprocess.run(["ruff", "check", "-"], input=state["code"], capture_output=True, text=True)
    return {"lint_passed": r.returncode == 0}

def test(state):
    r = subprocess.run(["pytest"], capture_output=True, text=True)
    return {"test_result": r.stdout}

def route(state):
    return "test" if state["lint_passed"] else "rewrite"

g = StateGraph(FlowState)
g.add_node("write", write_code)
g.add_node("lint", lint)
g.add_node("test", test)
g.add_node("rewrite", write_code)
g.add_edge(START, "write")
g.add_edge("write", "lint")
g.add_conditional_edges("lint", route, {"test": "test", "rewrite": "rewrite"})
g.add_edge("test", END)
```

### 5.4 工具调用（Function Calling）最佳实践

#### 5.4.1 Schema 设计要点

🎯 **面试高频考点**：

- **description 要写给模型看**：像写"机器可读的注释"，明确输入格式、取值范围、副作用。
- **参数最少**：能默认值的不让模型填，减少出错。
- **用 enum 约束**：限定取值集合，避免幻觉。
- **必填字段标注 required**。
- **错误返回结构化**：`{"error": "...", "code": 123}`，让模型能理解并自纠错。

#### 5.4.2 反模式

- ❌ 一个工具参数超 10 个 → 拆成多个工具
- ❌ 工具名模糊（`do_action`）→ 起具体名（`create_issue`）
- ❌ description 留空或写"做点什么"
- ❌ 让模型输出大段自由文本作为参数 → 用结构化 schema

#### 5.4.3 工具调用循环（含错误处理）

```python
async def agent_loop(query, tools, max_iter=10):
    messages = [{"role": "user", "content": query}]
    for _ in range(max_iter):
        resp = await model.bind_tools(tools).ainvoke(messages)
        messages.append(resp)
        if not resp.tool_calls:
            return resp.content
        for call in resp.tool_calls:
            try:
                result = await dispatch_tool(call)
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})
            except Exception as e:
                # 把错误信息回填给模型，让它自己纠错
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": f"ERROR: {e}"})
    return "达到最大迭代数"
```

---

## 6. 国内 Agent 开发生态分析

### 6.1 主流框架对比（LangChain vs Dify vs Coze vs 百度千帆）

🎯 **面试高频考点**：

| 平台 | 类型 | 定位 | 优势 | 劣势 |
|------|------|------|------|------|
| **LangChain/LangGraph** | 代码框架 | 开发者 SDK | 灵活、可控、生态广 | 学习曲线陡、运维自负责 |
| **Dify** | 开源自托管 | LLMOps 平台 | 可视化 + 代码双模式、私有部署 | 复杂 Agent 编排弱 |
| **Coze（扣子）** | 字节 SaaS | Agent 搭建平台 | 上手快、生态完善、渠道分发强 | 数据不出云、定制有限 |
| **百度千帆 AppBuilder** | 商业云 | 企业 Agent 平台 | 国内合规、百度生态 | 闭源、迁移成本高 |

#### 选型建议

- **研究/原型**：LangChain + LangGraph
- **企业内网应用、私有部署**：Dify
- **快速上线 C 端 Agent（飞书/微信）**：Coze
- **央国企、强合规要求**：千帆 AppBuilder

### 6.2 国内大模型 API 对比

🎯 **面试高频考点**：

| 厂商 | 主力模型 | 强项 | 接入方式 | 价格档（输入/百万 token） |
|------|----------|------|----------|--------------------------|
| **DeepSeek** | deepseek-v3 / R1 | 推理强、性价比极高 | OpenAI 兼容 | 1~2 元（V3）/2~8 元（R1） |
| **智谱 AI** | GLM-4.5 / GLM-4-Plus | 多模态、Agent 能力全 | 自有 SDK + OpenAI 兼容 | 5~50 元 |
| **通义千问** | Qwen3-Max / Plus | 开源生态强、多模态 | DashScope | 2~20 元 |
| **百度文心** | ERNIE 4.5 / X1 | 中文理解、合规 | 千帆 SDK | 4~40 元 |
| **月之暗面** | Kimi K2 | 长上下文、Agent | 自有 SDK | 4~28 元 |
| **MiniMax** | abab / M1 | 语音、角色扮演 | 自有 SDK | 1~10 元 |

#### 接入示例（DeepSeek，OpenAI 兼容）

```python
from openai import OpenAI

client = OpenAI(
    api_key="sk-xxx",
    base_url="https://api.deepseek.com"  # 直接替换
)
resp = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "你好"}]
)
```

#### 选型建议

- **代码 + 推理**：DeepSeek V3/R1（性价比之王）
- **中文通用对话**：GLM-4.5 / Qwen3-Max
- **多模态 + Agent**：GLM-4.5 / 通义
- **长文档总结**：Kimi
- **央国企客户**：文心

### 6.3 企业级 Agent 落地场景分析

🎯 **面试高频考点**：用 STAR 模式描述场景，强调"降本 + 增效"。

#### 6.3.1 典型落地场景

| 场景 | 价值 | 关键技术 | 难点 |
|------|------|----------|------|
| **智能客服** | 7x24 响应、降人力成本 | RAG + 多轮 + 工单转人工 | 知识更新、幻觉控制 |
| **IT 运维助手** | 故障定位、自动修复 | RAG + 工具调用（API/SQL/脚本） | 权限、操作可逆 |
| **金融研究助理** | 自动研报、数据汇总 | 多 Agent + 长上下文 | 数据准确性、可溯源 |
| **法务合规审查** | 合同条款比对 | RAG + Prompt 模板 | 准确率要求极高 |
| **销售助理** | 客户画像、话术生成 | CRM 集成 + 个性化 | 实时性、CRM 数据 |
| **代码助手** | 代码生成、Code Review | 代码 RAG + Agent | 私有代码安全 |
| **HR 招聘** | 简历筛选、初筛面试 | 多 Agent + 评估 | 公平性、合规 |

#### 6.3.2 落地架构（通用三层）

```
┌─────────────────────────────────┐
|  接入层：飞书/钉钉/Web/小程序    |
├─────────────────────────────────┤
|  Agent 编排层：LangGraph/Coze  |
|   - 任务规划 + 工具调用 + 记忆  |
├─────────────────────────────────┤
|  数据与模型层：                  |
|   - LLM API（DeepSeek/GLM）    |
|   - RAG（向量库 + 知识库）      |
|   - 工具/业务系统 API          |
└─────────────────────────────────┘
```

#### 6.3.3 落地关键挑战

🎯 **面试高频考点**：

1. **幻觉控制**：用 RAG 锚定事实、关键事实"引用原文"、低温度。
2. **延迟与成本**：长链路 Agent 延迟高 → 用小模型路由 + 大模型兜底、缓存热点结果。
3. **可观测性**：全链路 Trace（LangSmith/Prometheus）+ 人工抽检。
4. **安全与权限**：工具调用做 RBAC、敏感操作 HITL 审批。
5. **评测体系**：建测试集，跑准确率/召回率/成本/延迟，回归测试。
6. **数据治理**：知识库版本化、增量更新、定期清洗。
7. **合规**：内容审核（敏感词/政治）、数据脱敏、日志留存。

#### 6.3.4 ROI 评估

- **降本**：人力替代率 × 单次成本 × 调用量
- **增效**：响应时长缩短、吞吐量提升
- **新增量**：原来做不了的事现在能做（如全量 Code Review）
- **隐性成本**：维护、Prompt 迭代、模型切换成本

---

## 附录：面试高频考点速查表

| 主题 | 高频考点 |
|------|----------|
| LangChain | LCEL 管道本质、Runnable 协议、Memory 四种策略、Retriever 类型、Callback 透传机制 |
| LangGraph | State + reducer、条件边、Checkpoint、Human-in-the-loop、与 AgentExecutor 区别 |
| React | diff 三假设、Fiber 双阶段、Hooks 链表、闭包陷阱、Reconciliation 流程、React 19 use()/Actions |
| 多 Agent | 三大协作模式、AutoGen vs CrewAI vs MetaGPT、A2A 协议、任务分配与冲突解决 |
| Skill/MCP | MCP 三类能力、Skill 设计原则、Function Calling schema 最佳实践、工具调用循环 |
| 国内生态 | 四大平台选型、六大模型对比、企业落地场景、幻觉/延迟/安全挑战 |

---

## 附录：学习路径建议

1. **入门（1-2 周）**：跑通 LangChain 官方 quickstart，理解 LCEL。
2. **进阶（2-3 周）**：读 `runnable.py` 源码，用 LangGraph 实现一个 ReAct Agent。
3. **深入（3-4 周）**：搭一个多 Agent 系统（如研究 + 写作 Crew），接入 MCP 工具。
4. **落地（持续）**：选一个真实业务场景（如客服/Code Review），端到端做出来，建评测集。

---

> 文档持续更新，建议结合官方文档与源码同步学习：
> - LangChain：https://python.langchain.com
> - LangGraph：https://langchain-ai.github.io/langgraph
> - React：https://react.dev
> - MCP：https://modelcontextprotocol.io
> - LangSmith：https://smith.langchain.com
