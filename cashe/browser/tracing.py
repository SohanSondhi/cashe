"""Browser workflow, decision, and action callbacks share the investigation ID."""

from langchain_core.runnables import RunnableLambda

from cashe.config import settings


def create_handler(session_id: str):
    if not settings.prismtrace_enabled:
        return None
    if settings.app_env != "staging":
        raise ValueError("Browser tracing currently requires APP_ENV=staging")
    if not all((settings.prismtrace_api_key, settings.prismtrace_project_id, settings.prismtrace_host)):
        raise ValueError("PRISMTRACE_API_KEY, PRISMTRACE_PROJECT_ID and PRISMTRACE_HOST are required")
    from prismtrace import PRISMtraceCallbackHandler

    return PRISMtraceCallbackHandler(
        api_key=settings.prismtrace_api_key, project_id=settings.prismtrace_project_id,
        host=settings.prismtrace_host, session_id=session_id, agent_name="Cashe browser acquisition",
    )


def traced_call(name, function, payload, config):
    return RunnableLambda(function).with_config(run_name=name).invoke(payload, config=config)
