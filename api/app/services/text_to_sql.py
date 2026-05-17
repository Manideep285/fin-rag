"""Text-to-SQL — Natural language to SQL query generation and execution.

Pipeline:
1. Get schema description for the project's structured data
2. Generate SQL via LLM using the schema context
3. Validate SQL for safety (read-only, no injection)
4. Execute against DuckDB
5. Return structured results

Supports financial query patterns: aggregations, temporal comparisons,
rankings, percentage calculations, and multi-table joins.
"""
from __future__ import annotations
import re
from typing import Optional
from uuid import UUID

from ..config import settings
from ..guardrails import is_safe_sql
from ..logging_setup import log
from ..services.answer_synthesizer import StructuredResult
from ..services.llm import chat_completion
from ..services.prompts import build_sql_generation_messages
from ..services.schema_manager import execute_sql, get_project_schema_description


async def text_to_sql_query(
    project_id: UUID,
    question: str,
) -> StructuredResult:
    """Generate and execute a SQL query from a natural language question.

    Args:
        project_id: The project whose structured data to query.
        question: The user's natural language question.

    Returns:
        StructuredResult with query results or error.
    """
    # 1. Get schema description
    schema_desc = get_project_schema_description(project_id)
    if not schema_desc:
        return StructuredResult(
            sql_query="",
            data_source="none",
            rows=[],
            columns=[],
            row_count=0,
            error="No structured data sources found for this project.",
        )

    # 2. Generate SQL via LLM
    try:
        sql_query = await _generate_sql(schema_desc, question)
    except Exception as e:
        log.error("text_to_sql.generation_failed", error=str(e))
        return StructuredResult(
            sql_query="",
            data_source=schema_desc.split("\n")[0] if schema_desc else "unknown",
            rows=[],
            columns=[],
            row_count=0,
            error=f"Failed to generate SQL query: {str(e)}",
        )

    if sql_query.startswith("CANNOT_ANSWER:"):
        reason = sql_query.replace("CANNOT_ANSWER:", "").strip()
        return StructuredResult(
            sql_query="",
            data_source=schema_desc.split("\n")[0] if schema_desc else "unknown",
            rows=[],
            columns=[],
            row_count=0,
            error=f"Cannot answer with available data: {reason}",
        )

    # 3. Validate SQL safety
    is_safe, reason = is_safe_sql(sql_query)
    if not is_safe:
        log.warning("text_to_sql.unsafe_sql", sql=sql_query[:200], reason=reason)
        return StructuredResult(
            sql_query=sql_query,
            data_source="rejected",
            rows=[],
            columns=[],
            row_count=0,
            error=f"Generated SQL failed safety check: {reason}",
        )

    # 4. Execute SQL
    log.info("text_to_sql.executing", sql=sql_query[:200])
    result = execute_sql(project_id, sql_query)

    if "error" in result and result["error"]:
        # Try to self-correct once
        log.info("text_to_sql.self_correcting", error=result["error"][:200])
        corrected = await _self_correct_sql(
            schema_desc, question, sql_query, result["error"]
        )
        if corrected and corrected != sql_query:
            is_safe2, reason2 = is_safe_sql(corrected)
            if is_safe2:
                result = execute_sql(project_id, corrected)
                sql_query = corrected

    # 5. Return result
    return StructuredResult(
        sql_query=sql_query,
        data_source=schema_desc.split("\n")[0] if schema_desc else "DuckDB",
        rows=result.get("rows", []),
        columns=result.get("columns", []),
        row_count=result.get("row_count", 0),
        truncated=result.get("truncated", False),
        error=result.get("error"),
    )


async def _generate_sql(schema: str, question: str) -> str:
    """Use LLM to generate a SQL query from natural language."""
    messages = build_sql_generation_messages(
        schema=schema,
        question=question,
        dialect="DuckDB (PostgreSQL-compatible)",
    )

    resp = await chat_completion(messages, max_tokens=500, temperature=0.0)
    content = resp["choices"][0]["message"]["content"].strip()

    # Extract SQL from markdown code block if present
    sql = _extract_sql(content)

    log.info("text_to_sql.generated", sql=sql[:200])
    return sql


async def _self_correct_sql(
    schema: str, question: str, failed_sql: str, error: str
) -> Optional[str]:
    """Attempt to fix a failed SQL query using the error message."""
    correction_prompt = f"""The following SQL query failed with an error.
Fix the query to work correctly.

SCHEMA:
{schema}

ORIGINAL QUESTION: {question}

FAILED SQL:
```sql
{failed_sql}
```

ERROR:
{error}

Generate ONLY the corrected SQL query in ```sql ... ``` markers.
Do NOT explain — just provide the fixed query.
"""
    try:
        messages = [
            {"role": "system", "content": "You are a SQL expert. Fix the broken query."},
            {"role": "user", "content": correction_prompt},
        ]
        resp = await chat_completion(messages, max_tokens=500, temperature=0.0)
        content = resp["choices"][0]["message"]["content"].strip()
        return _extract_sql(content)
    except Exception as e:
        log.warning("text_to_sql.self_correct_failed", error=str(e))
        return None


def _extract_sql(content: str) -> str:
    """Extract SQL from LLM response, handling various formats."""
    # Check for CANNOT_ANSWER
    if "CANNOT_ANSWER" in content:
        # Find the CANNOT_ANSWER line
        for line in content.split("\n"):
            if "CANNOT_ANSWER" in line:
                return line.strip()

    # Try to extract from ```sql ... ``` block
    sql_match = re.search(r"```sql\s*\n?(.*?)```", content, re.DOTALL | re.IGNORECASE)
    if sql_match:
        return sql_match.group(1).strip()

    # Try generic code block
    code_match = re.search(r"```\s*\n?(.*?)```", content, re.DOTALL)
    if code_match:
        return code_match.group(1).strip()

    # If the content looks like SQL (starts with SELECT/WITH), use it directly
    stripped = content.strip()
    upper = stripped.upper()
    if upper.startswith("SELECT") or upper.startswith("WITH"):
        return stripped

    # Last resort: find any SELECT statement in the text
    select_match = re.search(r"(SELECT\b.*?)(?:;|\Z)", content, re.DOTALL | re.IGNORECASE)
    if select_match:
        return select_match.group(1).strip()

    return content.strip()
