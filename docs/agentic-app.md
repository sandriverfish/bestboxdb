# BestBox Agentic Application — How-To Guide

Build a LangGraph agent that queries your SmartTrade ERP data in natural language using a local LLM (Qwen3) and the BestBox REST API.

---

## Overview

```
User prompt
    └── LangGraph ReAct agent (Qwen3 via Ollama)
            └── @tool functions
                    └── BestBox REST API  (http://localhost:8000/api/v1)
                                └── SmartTrade SQL Server
```

The agent receives a natural-language question, decides which BestBox tools to call (and in what order), executes them against the live REST API, and synthesises the results into a plain-language answer.

**Why REST and not MCP?**
MCP requires a native MCP client runtime. LangGraph uses standard Python function-calling tools. The BestBox REST API maps directly to `@tool` definitions with no additional infrastructure.

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | |
| BestBox REST API | running at `http://localhost:8000` | See [README](README.md) |
| [Ollama](https://ollama.com) | latest | Hosts the local LLM |
| Qwen3 model | `qwen3:30b-a3b` (Q4_K_M recommended) | See model note below |

**Model note:** The MoE (Mixture-of-Experts) Qwen3 variant — 30B total parameters, ~3B active per token — runs comfortably on a single 16 GB GPU at Q4_K_M quantisation. It reliably produces valid tool-call JSON, which is the critical capability for a ReAct agent.

Pull the model before starting:

```bash
ollama pull qwen3:30b-a3b
```

---

## 1. Start the BestBox REST API

```bash
cd E:\MyCode\bestboxdb
uvicorn bestbox.rest.main:app --host 0.0.0.0 --port 8000
```

Verify it's up:

```bash
curl http://localhost:8000/api/v1/orders/sales?limit=1
```

---

## 2. Install Dependencies

Create a separate project directory for the agentic application and install:

```bash
pip install langgraph langchain-ollama langchain-core httpx
```

| Package | Purpose |
|---|---|
| `langgraph` | Agent loop and graph orchestration |
| `langchain-ollama` | `ChatOllama` — wraps local Ollama models as LangChain chat models |
| `langchain-core` | `@tool` decorator and message types |
| `httpx` | HTTP client for REST API calls |

---

## 3. Define the ERP Tools

Each BestBox REST endpoint becomes one `@tool` function. The docstring is what the LLM reads to decide when to call it — write it in business terms, not technical ones.

```python
# tools.py
import httpx
from langchain_core.tools import tool

BASE_URL = "http://localhost:8000/api/v1"

def _get(path: str, params: dict = None) -> dict | list:
    """Shared HTTP GET helper. Raises on non-2xx responses."""
    params = {k: v for k, v in (params or {}).items() if v is not None}
    response = httpx.get(f"{BASE_URL}{path}", params=params, timeout=30)
    response.raise_for_status()
    return response.json()


@tool
def get_sales_order(order_id: int) -> dict:
    """
    Get the full detail of a sales order including all line items, quantities
    ordered, quantities shipped, and current fulfilment status.
    Use this when you need item-level detail or an accurate order status.
    """
    return _get(f"/orders/sales/{order_id}")


@tool
def list_sales_orders(
    customer_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    status: int | None = None,
    limit: int = 20,
) -> list:
    """
    List sales orders. Supports filtering by customer ID, date range (ISO format:
    YYYY-MM-DD), and status (0=Pending, 1=Approved). Returns order headers only —
    call get_sales_order for line item detail. Maximum 200 results per call.
    Note: status filter only works reliably for 0 (Pending) and 1 (Approved).
    """
    return _get("/orders/sales", {
        "customer_id": customer_id,
        "date_from": date_from,
        "date_to": date_to,
        "status": status,
        "limit": min(limit, 200),
    })


@tool
def get_purchase_order(order_id: int) -> dict:
    """
    Get the full detail of a purchase order including all line items.
    On purchase orders, qty_shipped means quantity received from the supplier,
    not dispatched. Use this to check incoming stock status.
    """
    return _get(f"/orders/purchases/{order_id}")


@tool
def list_purchase_orders(
    supplier_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 20,
) -> list:
    """
    List purchase orders with optional filtering by supplier ID and date range.
    Returns order headers only — call get_purchase_order for line item detail.
    """
    return _get("/orders/purchases", {
        "supplier_id": supplier_id,
        "date_from": date_from,
        "date_to": date_to,
        "limit": min(limit, 200),
    })


@tool
def check_stock(part_number: str) -> dict:
    """
    Check available inventory for a part number. Returns total_qty (all lots),
    available_qty (ready to ship — excludes held, quarantine, locked stock),
    on_order_qty (incoming from open purchase orders), and individual lots.
    Part number must be exact and case-sensitive.
    Returns zeros if the part number is not found in the product master —
    in that case, use get_inventory_lots with the product_id from the order line.
    """
    try:
        return _get(f"/inventory/stock/by-part/{part_number}")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return {"available_qty": 0, "total_qty": 0, "on_order_qty": 0, "lots": []}
        raise


@tool
def list_low_stock(threshold: float = 10.0) -> list:
    """
    List all products whose available quantity is below the threshold.
    Keep threshold at 100 or below when using this tool — higher values
    return very large result sets. For a broad scan, start at 10 and increase.
    """
    return _get("/inventory/low-stock", {"threshold": threshold})


@tool
def get_inventory_lots(product_id: int) -> list:
    """
    Get individual lot-level inventory detail for a product: lot ID, quantity,
    stockroom, date code, and lot status (1=Available, 2=Held, 3=Quarantine, 4=Locked).
    Use this when check_stock returns zero but you know the product_id, or when
    you need stockroom location or date code information.
    """
    return _get(f"/inventory/lots/{product_id}")


ERP_TOOLS = [
    get_sales_order,
    list_sales_orders,
    get_purchase_order,
    list_purchase_orders,
    check_stock,
    list_low_stock,
    get_inventory_lots,
]
```

---

## 4. Build the Agent

```python
# agent.py
from langchain_ollama import ChatOllama
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage
from tools import ERP_TOOLS

SYSTEM_PROMPT = """You are an ERP assistant for a electronics components distributor
using SmartTrade ERP. You help staff — from General Manager to warehouse operators —
query live orders and inventory data.

Guidelines:
- Always use get_sales_order (not list_sales_orders) when you need accurate order
  status or line item quantities. The list endpoint shows a simplified status.
- For stock checks: use check_stock first. If it returns zero and you have a
  product_id from an order line, follow up with get_inventory_lots(product_id).
- available_qty is the only quantity you can commit to a customer.
  Do not promise on_order_qty — it has not arrived yet.
- Currency code 3 = CNY, code 2 = USD.
- Order dates are in China Standard Time (UTC+8).
- When listing orders, status filter only works for Pending (0) and Approved (1).
  To find partial or fulfilled orders, fetch them individually.
- Be concise. Managers want a one-line answer; staff want the numbers.
"""

llm = ChatOllama(
    model="qwen3:30b-a3b",
    temperature=0,        # deterministic tool calls
    num_ctx=8192,         # enough for multi-tool conversations
)

agent = create_react_agent(
    model=llm,
    tools=ERP_TOOLS,
    prompt=SystemMessage(content=SYSTEM_PROMPT),
)
```

---

## 5. Run the Agent

### Interactive REPL

```python
# main.py
from agent import agent
from langchain_core.messages import HumanMessage

def chat(question: str) -> str:
    result = agent.invoke({"messages": [HumanMessage(content=question)]})
    return result["messages"][-1].content

if __name__ == "__main__":
    print("BestBox ERP Assistant — type 'quit' to exit\n")
    while True:
        question = input("You: ").strip()
        if question.lower() in ("quit", "exit"):
            break
        if question:
            print(f"Agent: {chat(question)}\n")
```

```bash
python main.py
```

### Single query

```python
from agent import agent
from langchain_core.messages import HumanMessage

result = agent.invoke({
    "messages": [HumanMessage(content="Do we have any approved orders that haven't shipped yet?")]
})
print(result["messages"][-1].content)
```

---

## 6. Example Queries

These examples show the kind of questions the agent handles and which tools it calls behind the scenes.

### General Manager queries

```
"How many sales orders were placed this month?"
→ list_sales_orders(date_from="2026-03-01", date_to="2026-03-31", limit=200)

"What's the total value of pending orders?"
→ list_sales_orders(status=0, limit=200)  # agent sums total_amount

"Are we running low on any stock?"
→ list_low_stock(threshold=100)
```

### Sales / operations queries

```
"What parts are on order YSTX-SO26030405?"
→ list_sales_orders(date_from="2026-03-01", date_to="2026-03-31", limit=100)
   get_sales_order(order_id=35171)

"Can we ship order 35171 today?"
→ get_sales_order(order_id=35171)
   check_stock(part_number="V104K0201X5R6R3NAT")

"Show all pending orders for customer 838"
→ list_sales_orders(customer_id=838, status=0)
```

### Warehouse queries

```
"Where is product 18349 stored and how much is available?"
→ get_inventory_lots(product_id=18349)

"What's the date code on the MURATA GRM188R60J475KE19D lots?"
→ check_stock(part_number="GRM188R60J475KE19D")
   get_inventory_lots(product_id=7555)  # if lots show in check_stock response

"What purchase orders are arriving this week?"
→ list_purchase_orders(date_from="2026-03-25", date_to="2026-03-31")
```

---

## 7. Multi-step Workflow Example

For complex questions the agent chains multiple tool calls automatically:

**Prompt:** *"Can we fulfil order 31716? If not, when can we expect the stock?"*

Agent reasoning:
1. `get_sales_order(31716)` → finds 2 line items, both status=2, qty_shipped=0
2. `check_stock("RSFM1801A")` → checks available stock for line 1
3. `check_stock("RSFD1954C")` → checks available stock for line 2
4. If either is short: `list_purchase_orders(date_from="...", date_to="...")` → finds open POs
5. Synthesises: *"Order 31716 cannot ship today — RSFM1801A shows 0 available. There is a purchase order due 2026-04-05 that should cover the shortfall."*

No code change is needed for this — the ReAct loop handles it.

---

## 8. Known Quirks and Workarounds

These are verified against the live database and documented here so you can handle them in prompts or pre/post-processing.

### `check_stock` returns zero despite real stock

The part number in the inventory product master may not match exactly. If the order line item has a `product_id`, fall back to lot-level data:

```python
# In your application logic or as an agent instruction
stock = check_stock("PART-XYZ")
if stock["available_qty"] == 0 and product_id:
    lots = get_inventory_lots(product_id)
    available = sum(float(l["quantity"]) for l in lots if l["status"] == 1)
```

### `list_sales_orders` status filter

`status=0` and `status=1` work. Passing `status=2`, `3`, or `4` returns all orders unfiltered. The system prompt already informs the agent of this — it will use `get_sales_order` to confirm status on individual orders when needed.

### Status divergence between list and detail

An order may appear as `status=0` in a list but `status=2` when fetched with `get_sales_order`. This is because the list uses the header approval flag only; the detail aggregates item-level shipment state. Always use `get_sales_order` for accurate status.

### `qty_shipped` on purchase orders

On purchase orders, `qty_shipped` means **received**, not dispatched. An agent should interpret "how much has arrived from the supplier" — not "how much we sent out."

---

## 9. Production Tips

### Stream responses for long queries

```python
for chunk in agent.stream(
    {"messages": [HumanMessage(content=question)]},
    stream_mode="values",
):
    last = chunk["messages"][-1]
    if hasattr(last, "content") and last.content:
        print(last.content, end="", flush=True)
```

### Add conversation memory

```python
from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()
agent = create_react_agent(
    model=llm,
    tools=ERP_TOOLS,
    prompt=SystemMessage(content=SYSTEM_PROMPT),
    checkpointer=memory,
)

# Pass thread_id to maintain conversation context per user session
config = {"configurable": {"thread_id": "user-session-42"}}
result = agent.invoke({"messages": [HumanMessage(content=question)]}, config=config)
```

### Limit tool call depth

Prevent runaway chains on ambiguous questions:

```python
agent = create_react_agent(
    model=llm,
    tools=ERP_TOOLS,
    prompt=SystemMessage(content=SYSTEM_PROMPT),
    max_iterations=10,   # stop after 10 tool calls
)
```

### Parallel tool calls

Qwen3 supports parallel tool calls. When the agent needs stock for multiple parts simultaneously (e.g. checking all items on an order), it can emit multiple `check_stock` calls in a single LLM response. LangGraph executes them in parallel automatically — no extra code required.

### Validate model tool-call quality

Before deploying, run this sanity check to confirm the quantised model reliably produces valid tool calls:

```python
from agent import agent
from langchain_core.messages import HumanMessage

test_cases = [
    "Check stock for part GRM188R60J475KE19D",
    "List pending orders for customer 838",
    "Get details of sales order 35171",
]

for q in test_cases:
    result = agent.invoke({"messages": [HumanMessage(content=q)]})
    msgs = result["messages"]
    tool_calls = [m for m in msgs if hasattr(m, "tool_calls") and m.tool_calls]
    print(f"Q: {q}")
    print(f"  Tools called: {[tc['name'] for m in tool_calls for tc in m.tool_calls]}")
    print(f"  Answer: {msgs[-1].content[:120]}\n")
```

---

## 10. Full Stack Startup Checklist

```
1. Start SmartTrade SQL Server         # 192.168.1.147:20241
2. Start BestBox REST API              # uvicorn bestbox.rest.main:app --port 8000
3. Start Ollama                        # ollama serve
4. Confirm model is loaded             # ollama list → qwen3:30b-a3b
5. Run the agent                       # python main.py
```

All five must be running simultaneously. The agent will fail loudly if either the REST API or Ollama is unreachable.

---

## Related Documentation

- [REST API Reference](api-reference.md) — full endpoint and parameter reference
- [User Guide](user-guide.md) — BestBox tool usage with example queries
- [FAQ](faq.md) — common operational questions, known quirks, and workarounds
