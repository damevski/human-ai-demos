from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import tools_condition
from langgraph.prebuilt.tool_node import ToolNode

from config import OPENAI_API_KEY
from prompt import REACT_SYSTEM_PROMPT
from tools import query_course_schedule, get_tavily_tool

def _get_llm():
    return ChatOpenAI(model="gpt-4o-mini", temperature=0.7, openai_api_key=OPENAI_API_KEY)

def build_graph():
    llm = _get_llm()

    tools = []
    tavily = get_tavily_tool()
    if tavily:
        tools.append(tavily)
    if query_course_schedule:
        tools.append(query_course_schedule)

    llm_with_tools = llm.bind_tools(tools) if tools else llm

    def chatbot(state: MessagesState):
        result = llm_with_tools.invoke(state["messages"])
        return {"messages": [result]}

    g = StateGraph(MessagesState)
    g.add_node("chatbot", chatbot)
    if tools:
        g.add_node("tools", ToolNode(tools=tools))
        g.add_conditional_edges("chatbot", tools_condition)
        g.add_edge("tools", "chatbot")
    g.add_edge(START, "chatbot")
    g.add_edge("chatbot", END)
    return g.compile()

GRAPH = build_graph()
SYSTEM_MSG = SystemMessage(content=REACT_SYSTEM_PROMPT)