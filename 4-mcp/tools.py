from typing import Any, Dict, List, Optional, TypedDict
from pydantic import BaseModel, Field
import os
import pandas as pd
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain.schema.messages import ToolMessage  
from langchain.tools import tool
from langgraph.prebuilt.tool_node import ToolNode
from langchain_community.tools.tavily_search import TavilySearchResults


XLSX_PATH = "VCU-CMSC-202610-FA2025.xlsx"


def get_tavily_tool():
    tavily_key = os.getenv("TAVILY_API_KEY", "")
    tool = TavilySearchResults(max_results=2) if tavily_key else None
    return tool

class CourseScheduleArgs(BaseModel):
    course: Optional[str] = Field(None, description="Course code prefix or full code, e.g., 'CMSC691'")
    instructor: Optional[str] = Field(None, description="Instructor last name, e.g., 'Damevski'")
    max_rows: Optional[int] = Field(None, description="If set, cap the number of returned rows.")

@tool(args_schema=CourseScheduleArgs)
def query_course_schedule(course: Optional[str] = None,
                          instructor: Optional[str] = None,
                          max_rows: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Query VCU course schedule by course code or instructor last name.
    """
    df = pd.read_excel(XLSX_PATH)

    # Keep columns that are useful to the model and user
    keep_cols = [
        'COURSE',
        'TITLE',
        'CRN',
        'SECT',
        'PRIMARY\nINSTRUCTOR\nLAST NAME',
        'SCHEDULE',
        'BUILDING',
        'ROOM',
        'BEGIN\nTIME',
        'END\nTIME',
        'MODALITY\nTEXT',
        'MAX\nCREDITS',
        'ACTUAL\nENROLLMENT',
        'MAX\nSIZE',
        'MON-IND',
        'TUE-IND',
        'WED-IND',
        'THU-IND',
        'FRI-IND',
    ]
    
    existing_cols = [c for c in keep_cols if c in df.columns]
    if existing_cols:
        df = df[existing_cols]

    # Apply filters if given
    filtered = df
    applied_filter = False
    if course:
        filtered = filtered[filtered["COURSE"].str.contains(course, case=False, na=False)]
        applied_filter = True
    if instructor:
        filtered = filtered[filtered["PRIMARY\nINSTRUCTOR\nLAST NAME"].str.contains(instructor, case=False, na=False)]
        applied_filter = True

    # Decide what to return
    if applied_filter and not filtered.empty:
        out = filtered
    else:
        # Either no filters or no matches, return full schedule
        out = df

    if max_rows is not None:
        out = out.head(max_rows)

    return out.to_dict(orient="records")

