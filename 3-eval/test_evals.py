from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from run import get_graph
from dotenv import load_dotenv
from prompt import REACT_SYSTEM_PROMPT, RESPONSE_CRITERIA_SYSTEM_PROMPT
import os
import pytest
import pandas as pd
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

XLSX_PATH = "GPD_chatbot_eval.xlsx"
MAX_ROWS_TO_TEST = 50

# Load environment variables
load_dotenv()

class CriteriaGrade(BaseModel):
    """Score the response against specific criteria."""
    justification: str = Field(description="The justification for the grade and score, including specific examples from the response.")
    grade: bool = Field(description="Does the response meet the provided criteria?")


# create evaluation LLM once
api_key = os.getenv("OPENAI_API_KEY")
criteria_eval_llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.0,
        openai_api_key=api_key
    )
criteria_eval_structured_llm = criteria_eval_llm.with_structured_output(CriteriaGrade)


def _load_row_indices():
    if not os.path.exists(XLSX_PATH):
        return []
    df = pd.read_excel(XLSX_PATH)
    if "user_question" not in df.columns or "gpd_answer" not in df.columns:
        return []
    return list(range(min(MAX_ROWS_TO_TEST, len(df))))


@pytest.fixture(scope="module")
def gpd_graph():
    return get_graph()


@pytest.mark.parametrize("row_index", _load_row_indices())
def test_graph_returns_ai_response_and_meets_criteria(gpd_graph, row_index):
    # load the row data
    df = pd.read_excel(XLSX_PATH)
    if "user_question" not in df.columns or "gpd_answer" not in df.columns:
        pytest.skip("Required columns 'user_question' or 'gpd_answer' missing")

    user_question = str(df.iloc[row_index]["user_question"])
    gpd_answer = str(df.iloc[row_index]["gpd_answer"])

    # prepare messages for the graph
    system_msg = SystemMessage(content=REACT_SYSTEM_PROMPT)
    human_msg = HumanMessage(content=user_question)
    initial_messages = [system_msg, human_msg]

    # invoke the graph
    state = gpd_graph.invoke({"messages": initial_messages})

    assert isinstance(state, dict), "Graph.invoke should return a dict-like state"
    assert "messages" in state, "Returned state missing 'messages'"

    # find last AI message produced by the graph
    last_ai = None
    for m in reversed(state["messages"]):
        if isinstance(m, AIMessage):
            last_ai = m
            break

    assert last_ai is not None, "No AIMessage found in returned state messages"
    assistant_response = last_ai.content
    assert isinstance(assistant_response, str) and assistant_response.strip(), "AIMessage content is empty"

    # Evaluate assistant response against ground truth using structured LLM
    eval_prompt_user = (
        f"\n\n Ground truth response: {gpd_answer} \n\n"
        f"Assistant's response: \n\n {assistant_response} \n\n"
        "Evaluate whether the assistant's response has the similar key points as the ground truth response and justify your answer."
    )

    eval_result = criteria_eval_structured_llm.invoke([
        {"role": "system", "content": RESPONSE_CRITERIA_SYSTEM_PROMPT},
        {"role": "user", "content": eval_prompt_user},
    ])

    assert hasattr(eval_result, "grade"), "Evaluator returned no 'grade' field"
    assert eval_result.grade is True, f"Response did not meet criteria: {eval_result.justification}"
