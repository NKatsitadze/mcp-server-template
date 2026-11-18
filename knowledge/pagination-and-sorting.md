# Pagination and sorting

Collections accept these query parameters:

| Parameter | Effect | Example |
|---|---|---|
| `_page`, `_limit` | page number (from 1) and page size | `/posts?_page=2&_limit=3` returns posts 4, 5, 6 |
| `_start`, `_end` | slice by position, end exclusive | `/todos?_start=5&_end=8` returns todos 6, 7, 8 |
| `_sort`, `_order` | sort by a field, `asc` or `desc` | `/users?_sort=name&_order=desc` |

With `_page`, the response headers include `X-Total-Count` (the total number of items, e.g. 100 for
posts) and a `Link` header with `first`, `next` and `last` page URLs.

## How the MCP tools handle long lists

The tools do not page through the API. They fetch the filtered collection once and show at most 50
rows, always with the full count ("12 of 100 post(s)", "…and 70 more"). The model is told to narrow
the filter instead of asking for more rows.
