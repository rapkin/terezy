# Running the web client

Two supported ways. Both serve the client and the API from **one origin**, so there is no CORS
allowance in either and no host to configure in the browser.

## Production shape — one container

```bash
docker compose up --build          # from the repository root
```

Open <http://127.0.0.1:8000>. The image builds the client and the API serves it, with `/api`
under the same origin. Stop it with `docker compose down`.

## Development — two processes

```bash
uv run python -m terezy.api.http   # terminal 1, from the repository ROOT
pnpm -C web dev                    # terminal 2
```

Open the URL the dev server prints (<http://127.0.0.1:5173>). Above that banner, as it starts,
it prints the origin it proxies `/api` to; if that is not where the API is listening, set
`TEREZY_API_ORIGIN` and restart it.

Start the API through `python -m terezy.api.http` and never through a bare `uvicorn` command:
the entry point is what applies the bind guard *before* it binds, and what refuses a data root
it cannot read instead of coming up and answering 500 to everything.

## When a screen says the API did not answer

- **"no route of the API produced this"** — either nothing is listening, or a request reached the
  API and failed inside it. Check the `/api →` line the dev server printed against the address
  the API says it is listening on, and then the API's own log.
- **The API refused at startup, naming a path** — it was started somewhere it cannot find
  declarations. It reads `data/` from the checkout it was imported from, so this means either an
  installed copy or a `TEREZY_DATA_ROOT` pointing at the wrong directory. Set that variable to the
  directory holding `venues.toml`.
- **A refusal with a reason, on the screen** — that is the API working. A refusal is a result:
  read what it names.

The API answers on loopback only, and refuses any other address until authentication exists
(constitution Principle VII).
