# Albums and photos resources (/albums, /photos)

## Albums

`GET /albums` returns 100 albums, 10 per user. Fields: `id`, `userId`, `title`.
`GET /users/{id}/albums` lists one user's albums.

## Photos

`GET /photos` returns 5000 photos, 50 per album. Fields: `id`, `albumId`, `title`, `url`,
`thumbnailUrl`. `GET /albums/{id}/photos` lists one album's photos.

Fetching all photos returns a large response (5000 items). Always filter, for example
`GET /photos?albumId=1`, or paginate (see the pagination page).

## MCP tools

None. They are left out on purpose: expose few tools, each answering real questions. Add one only
when users actually ask about albums or photos.
