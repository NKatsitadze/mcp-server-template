from mcp.types import ToolAnnotations

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True)
# Clients such as Claude Code ask the user before every call to a destructive tool.
IDEMPOTENT_WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True)
NOT_IDEMPOTENT_WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False)
