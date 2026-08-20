"""Dash application review guidance tool."""

from ai_reviewer.tools._tool_template import make_review_tool

toolset = make_review_tool(
    name="dash_app_review_guidance",
    prompt_file="dash_app_review.md",
    description=(
        "Get instructions for reviewing Plotly Dash applications. "
        "Call this tool when the PR touches files importing `dash`, "
        "`dash_bootstrap_components`, or `plotly.graph_objects`/`plotly.express` "
        "for an app layout, OR contains `@app.callback`/`@callback` decorators, "
        "OR modifies files under an `app_src/`-style Dash app directory "
        "(dashboards/, callbacks/, charts/, assets/*.js clientside callbacks)."
    ),
)
