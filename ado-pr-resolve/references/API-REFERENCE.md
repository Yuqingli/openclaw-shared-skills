# Azure DevOps API Reference — PR Comment Resolution

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
| Reply to thread | POST | `/_apis/git/repositories/{repo}/pullrequests/{prId}/threads/{threadId}/comments` | 7.0 |

---

## Get PR Details

```bash
curl -s "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}/pullrequests/{prId}?api-version=7.1" \
  -H "Authorization: Bearer $TOKEN"
```

**Response fields of interest:**
- `sourceRefName` — source branch (e.g., `refs/heads/feature/xyz`)
- `targetRefName` — target branch (e.g., `refs/heads/main`)
- `title`, `description` — PR metadata
- `status` — PR status (active, completed, abandoned)

---

## Get Threads

```bash
curl -s "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}/pullRequests/{prId}/threads?api-version=7.0" \
  -H "Authorization: Bearer $TOKEN"
```

**Response structure:**
```json
{
  "value": [
    {
      "id": 123,
      "status": "active",
      "threadContext": {
        "filePath": "/src/file.cpp",
        "rightFileStart": { "line": 42, "offset": 1 },
        "rightFileEnd": { "line": 45, "offset": 1 }
      },
      "comments": [
        {
          "id": 1,
          "parentCommentId": 0,
          "content": "Comment text here",
          "author": { "displayName": "Reviewer Name" },
          "commentType": "text"
        }
      ]
    }
  ]
}
```

**Thread status values:** `active`, `fixed`, `wontFix`, `closed`, `byDesign`, `pending`

**Filtering for active threads:**
- Check `status === "active"`
- Skip threads without `threadContext` (these are PR-level / system threads)
- Skip threads where `comments[0].commentType === "system"` (auto-generated)

---

## Post New Thread (Create Inline Comment)

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

### With Special Characters (File-Based)

Write JSON to file first to avoid bash escaping issues:

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

---

## Reply to Thread

Post a reply to an existing thread. Used after applying a fix to explain what was changed.

```bash
curl -s -X POST \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}/pullRequests/{prId}/threads/{threadId}/comments?api-version=7.0" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Fixed: brief explanation of what was changed",
    "parentCommentId": 1,
    "commentType": 1
  }'
```

**Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `content` | string | Markdown-formatted reply text |
| `parentCommentId` | int | ID of the comment being replied to (usually `1` for the first comment in the thread) |
| `commentType` | int | `1` = text comment |

**Response:** Returns the created comment object with `id`, `content`, `author`, etc.

### Reply with Code Example (File-Based)

```bash
cat > /tmp/reply.json << 'EOF'
{
  "content": "Fixed: Changed `oldMethod()` to `newMethod()` to address the thread safety concern.\n\n```cpp\n// Before\noldMethod();\n\n// After\nnewMethod();\n```",
  "parentCommentId": 1,
  "commentType": 1
}
EOF

curl -s -X POST \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}/pullRequests/{prId}/threads/{threadId}/comments?api-version=7.0" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @/tmp/reply.json
```

---

## Update Thread Status (Resolve)

Mark a thread as resolved/fixed after applying changes.

```bash
curl -s -X PATCH \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}/pullRequests/{prId}/threads/{threadId}?api-version=7.0" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"status": "fixed"}'
```

**Status values for resolution:**
| Status | When to Use |
|--------|-------------|
| `fixed` | Code change was made to address the comment |
| `wontFix` | Acknowledged but intentionally not changing |
| `closed` | Comment no longer relevant |
| `byDesign` | Current behavior is intentional |

**Response:** Returns the updated thread object.

**Note:** Only change status after user explicitly approves. Never auto-resolve.

---

## Thread Context Fields

| Field | Description |
|-------|-------------|
| `filePath` | Path relative to repo root, starting with `/` |
| `rightFileStart.line` | Start line (1-indexed) in the NEW file version |
| `rightFileEnd.line` | End line (for multi-line comments) |
| `offset` | Character offset within the line (usually `1`) |

---

## Comment Markdown Format

ADO threads support a subset of Markdown:

```markdown
**Bold title**

Description with context.

```cpp
// Code block
int x = 42;
```

- Bullet lists
- [Links](https://example.com)
```

---

## Common Issues

- File paths **must** start with `/` (e.g., `/src/file.cpp`)
- Use API version **7.0** for all thread operations
- For special characters in JSON, use file-based approach (`-d @/tmp/file.json`)
- `az repos pr` CLI does **not** have thread/comment commands — always use REST API with curl
- `parentCommentId: 1` refers to the first comment in the thread (root comment)
- Token expires after ~1 hour; re-fetch if you get 401 errors
- Rate limiting: ADO API has generous limits but add small delays between batch operations

---

## Error Handling

| HTTP Status | Meaning | Action |
|-------------|---------|--------|
| 200/201 | Success | Continue |
| 401 | Token expired / unauthorized | Re-fetch token with `az account get-access-token` |
| 403 | Insufficient permissions | User needs Contribute to PR permission |
| 404 | PR/thread/repo not found | Verify URL components |
| 409 | Conflict (thread already resolved) | Skip — someone resolved it already |
| 429 | Rate limited | Wait and retry |
