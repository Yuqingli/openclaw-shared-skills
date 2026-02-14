# Azure DevOps API Reference

## Authentication

```bash
# Azure DevOps resource ID
AZURE_DEVOPS_RESOURCE="499b84ac-1321-427f-aa17-267ca6975798"

# Get access token
TOKEN=$(az account get-access-token --resource "$AZURE_DEVOPS_RESOURCE" --query accessToken -o tsv)
```

## Base URL

```
https://dev.azure.com/{organization}/{project}
```

## API Endpoints

| Operation | Method | Endpoint | API Version |
|-----------|--------|----------|-------------|
| Get PR | GET | `/_apis/git/repositories/{repo}/pullrequests/{prId}` | 7.1 |
| Get iterations | GET | `/_apis/git/repositories/{repo}/pullrequests/{prId}/iterations` | 7.1 |
| Get changes | GET | `/_apis/git/repositories/{repo}/pullrequests/{prId}/iterations/{id}/changes` | 7.1 |
| Get threads | GET | `/_apis/git/repositories/{repo}/pullrequests/{prId}/threads` | 7.0 |
| Post thread | POST | `/_apis/git/repositories/{repo}/pullrequests/{prId}/threads` | 7.0 |
| Update thread | PATCH | `/_apis/git/repositories/{repo}/pullrequests/{prId}/threads/{threadId}` | 7.0 |

## Posting Inline Comments

**Important:** `az repos pr thread` does NOT exist. Use REST API with curl.

### Simple Comment
```bash
curl -s -X POST \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}/pullRequests/{prId}/threads?api-version=7.0" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "comments": [{"parentCommentId": 0, "content": "Comment text", "commentType": "text"}],
    "status": "active",
    "threadContext": {
      "filePath": "/path/to/file.cpp",
      "rightFileStart": {"line": 42, "offset": 1},
      "rightFileEnd": {"line": 42, "offset": 1}
    }
  }'
```

### Comment with Special Characters

Write JSON to file first (avoids bash escaping issues):

```bash
cat > /tmp/comment.json << 'EOF'
{
  "comments": [
    {
      "parentCommentId": 0,
      "content": "**Bug:** Description\n\n```cpp\n// Code example\nfoo();\n```",
      "commentType": "text"
    }
  ],
  "status": "active",
  "threadContext": {
    "filePath": "/path/to/file.cpp",
    "rightFileStart": {"line": 42, "offset": 1},
    "rightFileEnd": {"line": 45, "offset": 1}
  }
}
EOF

curl -s -X POST \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}/pullRequests/{prId}/threads?api-version=7.0" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @/tmp/comment.json
```

## Thread Context Fields

| Field | Description |
|-------|-------------|
| `filePath` | Path relative to repo root, starting with `/` |
| `rightFileStart.line` | Start line (1-indexed) in NEW file |
| `rightFileEnd.line` | End line (for multi-line comments) |
| `offset` | Character offset in line (usually `1`) |

## Comment Markdown Format

```markdown
**Bug: Brief title**

Description with context.

**Fix:**
```cpp
// Suggested code
```
```

## Common Issues

- File paths must start with `/` (e.g., `/src/file.cpp`)
- Use API version 7.0 for thread operations
- For special characters in JSON, use file-based approach
- `az repos pr` CLI doesn't have thread commands - use curl
