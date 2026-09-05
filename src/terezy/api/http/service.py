"""The application: routes built from the category registry, and nothing hand-written per category.

Every endpoint hangs off one prefix (:data:`document.PREFIX`) and every response model is
generated from the same shape its body is encoded from. The interactive documentation is off --
the framework's two default pages fetch from three external hosts across five asset URLs, and
Principle VII forbids a CDN call outright in a repository holding one person's finances.
"""

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Annotated, Final

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.types import ASGIApp

from terezy.api.answer import AnsweredQuestion
from terezy.api.http import (
    answers,
    bind,
    categories,
    document,
    encode,
    envelopes,
    middleware,
    models,
    series,
    shapes,
    summary,
)
from terezy.core.primitives.currency import Currency
from terezy.data.declarations import resolver
from terezy.data.declarations.errors import DeclarationError

DATA_ROOT_VARIABLE: Final[str] = "TEREZY_DATA_ROOT"
CLIENT_VARIABLE: Final[str] = "TEREZY_WEB_DIST"

BASE_CURRENCY: Final[Currency] = Currency.UAH
"""The base role of Principle VI, fixed per process. Not a request parameter: which currency the
tool is denominated in is a property of the owner, not of a question about him."""

AsOf = Annotated[date, Query(description="The date the read is made as of. Required.")]
ScenarioId = Annotated[str | None, Query(description="A declared scenario id, or none.")]


@dataclass(frozen=True, slots=True)
class Read:
    """One request's parameters: what to resolve under, and the date it was asked as of."""

    ask: categories.Ask
    as_of: date


def data_root() -> Path:
    """Where declarations are read from. Fixed per process and never a request parameter: a
    caller choosing a data root is a caller choosing a path into the filesystem."""
    return Path(os.environ.get(DATA_ROOT_VARIABLE, "data"))


def client_root() -> Path:
    """Where a built client would be, if one has been built into this image."""
    return Path(os.environ.get(CLIENT_VARIABLE, "web/dist"))


def create_app(root: Path, *, client: Path | None = None) -> FastAPI:
    """One application over one data root."""
    app = FastAPI(
        title=document.TITLE,
        version=document.VERSION,
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
    )
    router = APIRouter(prefix=document.PREFIX)
    for category in categories.CATEGORIES:
        _register(router, category, root)
    _register_fixed(router, root)
    app.include_router(router)
    app.add_exception_handler(DeclarationError, _declaration_failed)
    _serve_client(app, client)
    return app


def _reader(root: Path, *, scenario: bool) -> Callable[..., Read]:
    """The dependency that reads a request's parameters.

    Two of them, so that a category whose entry point takes no scenario does not advertise a
    parameter that decides nothing -- and so the document says which categories a scenario
    changes the answer for.
    """
    if scenario:

        def with_scenario(as_of: AsOf, scenario_id: ScenarioId = None) -> Read:
            ask = categories.Ask(root, BASE_CURRENCY, _declared_scenario(root, scenario_id))
            return Read(ask, as_of)

        return with_scenario

    def without_scenario(as_of: AsOf) -> Read:
        return Read(categories.Ask(root, BASE_CURRENCY, None), as_of)

    return without_scenario


def _declared_scenario(root: Path, scenario_id: str | None) -> str | None:
    """The scenario the request named, checked against the ones `data/scenarios/` declares.

    Refused as a parameter rather than left to the resolver, which raises the error that means
    *this data root is broken* -- and a caller who named a scenario nobody declares would then be
    sent to `data/` to look for a fault that is not there. It is the same trap FR-008 names for
    an undeclared record id, arriving through a query parameter.
    """
    if scenario_id is None:
        return None
    declared = sorted(resolver.ramp_from_data_root(root, base_currency=BASE_CURRENCY).scenarios)
    if scenario_id not in declared:
        raise HTTPException(
            status_code=422,
            detail=(
                f"no scenario with the id {scenario_id!r} is declared. The declared ids are "
                f"{declared}. A read under a scenario nobody declared would answer under a world "
                "nobody asked for."
            ),
        )
    return scenario_id


def _model(built: type) -> type[BaseModel]:
    return models.model_of(shapes.record_of(built))


def _body(built: type, envelope: object) -> encode.Json:
    return encode.encode(shapes.record_of(built), envelope)


def _register(router: APIRouter, category: categories.Category, root: Path) -> None:
    reader = _reader(root, scenario=category.scenario)
    match category.shape:
        case categories.Keyed():
            _register_keyed(router, category, reader)
        case categories.Document() | categories.Collection():
            _register_singleton(router, category, reader)


def _register_keyed(
    router: APIRouter, category: categories.Category, reader: Callable[..., Read]
) -> None:
    shape = category.shape
    assert isinstance(shape, categories.Keyed)
    is_series = category.id in series.OBSERVATION_TYPES
    listing = envelopes.listing_of(category.id, series=is_series)
    read = envelopes.read_of(category.id, shape.record)

    @router.get(f"/{category.id}", response_model=_model(listing), name=f"{category.id}.list")
    def list_ids(asked: Annotated[Read, Depends(reader)]) -> encode.Json:
        resolved = shape.resolve(asked.ask)
        coverage = {"coverage": _coverage(resolved.records)} if is_series else {}
        return _body(
            listing,
            listing(
                category=category.id,
                as_of=asked.as_of,
                scenario_id=asked.ask.scenario_id,
                ids=tuple(sorted(resolved.records)),
                **coverage,
            ),
        )

    @router.get(
        f"/{category.id}/{{record_id}}", response_model=_model(read), name=f"{category.id}.read"
    )
    def read_one(record_id: str, asked: Annotated[Read, Depends(reader)]) -> encode.Json:
        resolved = shape.resolve(asked.ask)
        held = resolved.records.get(record_id)
        result = held if held is not None else _no_such_id(category.id, record_id, resolved)
        return _body(
            read,
            read(
                category=category.id,
                as_of=asked.as_of,
                scenario_id=asked.ask.scenario_id,
                declared_in=_declared_in(category, resolved.files, record_id, asked.ask.root),
                fields=envelopes.describe(type(result)),
                result=result,
            ),
        )

    if is_series:
        _register_observations(router, category, reader, shape)


def _register_singleton(
    router: APIRouter, category: categories.Category, reader: Callable[..., Read]
) -> None:
    shape = category.shape
    if isinstance(shape, categories.Document):
        envelope = envelopes.document_of(category.id, shape.record)
        held_in = None
    else:
        assert isinstance(shape, categories.Collection)
        held_in, envelope = envelopes.collection_of(category.id, shape.record)

    @router.get(f"/{category.id}", response_model=_model(envelope), name=f"{category.id}.read")
    def read_document(asked: Annotated[Read, Depends(reader)]) -> encode.Json:
        resolved = shape.resolve(asked.ask)
        result = _document(category, resolved, held_in)
        declared_in = None if resolved.file is None else _relative(resolved.file, asked.ask.root)
        return _body(
            envelope,
            envelope(
                category=category.id,
                as_of=asked.as_of,
                scenario_id=asked.ask.scenario_id,
                declared_in=declared_in,
                fields=envelopes.describe(type(result)),
                result=result,
            ),
        )


def _register_observations(
    router: APIRouter,
    category: categories.Category,
    reader: Callable[..., Read],
    shape: categories.Keyed,
) -> None:
    held_in, envelope = envelopes.observations_of(
        category.id, series.OBSERVATION_TYPES[category.id]
    )

    @router.get(
        f"/{category.id}/{{record_id}}/observations",
        response_model=_model(envelope),
        name=f"{category.id}.observations",
    )
    def observations(
        record_id: str,
        asked: Annotated[Read, Depends(reader)],
        window_from: Annotated[str | None, Query(alias="from")] = None,
        window_to: Annotated[str | None, Query(alias="to")] = None,
    ) -> encode.Json:
        resolved = shape.resolve(asked.ask)
        held = resolved.records.get(record_id)
        if held is None:
            result: object = _no_such_id(category.id, record_id, resolved)
        else:
            window = series.window_of(held, window_from, window_to)
            if isinstance(window, series.WindowMalformed):
                raise HTTPException(status_code=422, detail=window.reason)
            read = series.read(held, window)
            result = held_in(
                series_id=record_id,
                window=window,
                covers=series.coverage_of(held),
                observations=read.observations,
                outside=read.outside,
            )
        return _body(
            envelope,
            envelope(category=category.id, as_of=asked.as_of, result=result),
        )


def _register_fixed(router: APIRouter, root: Path) -> None:
    reader = _reader(root, scenario=True)
    answer_envelope = envelopes.answer_of(AnsweredQuestion)

    @router.get("/registry", response_model=_model(summary.RegistrySummary), name="registry")
    def registry(asked: Annotated[Read, Depends(reader)]) -> encode.Json:
        return _body(summary.RegistrySummary, summary.of(asked.ask, as_of=asked.as_of))

    @router.get(
        "/questions/{question_id}/answer",
        response_model=_model(answer_envelope),
        name="questions.answer",
    )
    def answer(question_id: str, asked: Annotated[Read, Depends(reader)]) -> encode.Json:
        return _body(
            answer_envelope,
            answer_envelope(
                question_id=question_id,
                as_of=asked.as_of,
                result=answers.answered(asked.ask, question_id, as_of=asked.as_of),
            ),
        )

    @router.get("/openapi.json", name="openapi")
    def openapi() -> Response:
        return Response(content=document.committed(), media_type="application/json")


def _coverage(records: Mapping[str, object]) -> dict[str, envelopes.SeriesCoverage]:
    """Each declared series' window, by its id.

    Per series rather than one window for the category: a category declaring two series has no
    single coverage, and a field that quietly went empty when a second one was declared would
    leave a client guessing exactly where FR-045a exists to stop it.
    """
    return {
        series_id: window
        for series_id, held in sorted(records.items())
        if (window := series.coverage_of(held)) is not None
    }


def _no_such_id(
    category_id: str, wanted: str, resolved: categories.KeyedRecords
) -> envelopes.CategoryHasNoSuchId:
    return envelopes.CategoryHasNoSuchId(
        category=category_id,
        wanted_id=wanted,
        declared_ids=tuple(sorted(resolved.records)),
        reason=(
            f"the category {category_id!r} declares no {wanted!r}. This is a well-formed "
            "question about an id that does not exist, not a broken data root."
        ),
    )


def _document(
    category: categories.Category,
    resolved: categories.SingleRecord | categories.ManyRecords,
    held_in: type | None,
) -> object:
    match resolved:
        case categories.SingleRecord(record=record) if record is not None:
            return record
        case categories.ManyRecords(records=records, file=file) if file is not None:
            assert held_in is not None
            return held_in(documents=records)
        case _:
            return envelopes.NothingDeclared(
                category=category.id,
                reason=(
                    f"nothing under {categories.directory_of(category)!r} declares a document "
                    "for this owner. An empty document and an absent one are different facts."
                ),
            )


def _declared_in(
    category: categories.Category,
    files: Mapping[str, Path] | categories.NoFileMap,
    record_id: str,
    root: Path,
) -> str | envelopes.FileNotRecorded | None:
    if isinstance(files, categories.NoFileMap):
        return envelopes.FileNotRecorded(category=category.id, reason=files.reason)
    path = files.get(record_id)
    return None if path is None else _relative(path, root)


def _relative(path: Path, root: Path) -> str:
    """The declaring file as a path under the data root, never an absolute one.

    An absolute path is a fact about the machine that served the request, and a reader is shown
    it to go and find the file in the repository.
    """
    return path.relative_to(root).as_posix()


def _serve_client(app: FastAPI, client: Path | None) -> None:
    """Serve a built client from this origin where one exists, and nothing where it does not.

    A 404 under the API prefix stays a JSON refusal even when the fallback is mounted: an SPA
    document served for an unknown API path presents to a generated client as a parse error
    rather than as the missing route it is (021 FR-049).
    """
    index = None if client is None else client / "index.html"

    @app.exception_handler(404)
    async def not_found(request: Request, _: Exception) -> Response:
        if (
            index is not None
            and index.is_file()
            and not request.url.path.startswith(document.PREFIX)
        ):
            return FileResponse(index)
        return JSONResponse(
            status_code=404,
            content={
                "tag": "service.PathNotServed",
                "path": request.url.path,
                "reason": (
                    "this application serves no route at that path. Every endpoint is under "
                    f"{document.PREFIX!r}."
                ),
            },
        )

    if client is not None and client.is_dir():
        app.mount("/", StaticFiles(directory=client, html=True), name="client")


async def _declaration_failed(_: Request, exc: Exception) -> Response:
    """A malformed declaration, carrying the loader's own four fields and nothing added.

    An error status rather than a typed refusal in a 200 body: nothing was answered and no
    partial result exists, which is the distinction the CLI keeps between `LOAD_FAILED` and
    `REFUSED`.
    """
    assert isinstance(exc, DeclarationError)
    failure = envelopes.DeclarationFailed(
        file=str(exc.file),
        field_path=exc.field_path,
        problem=exc.problem,
        remedy=exc.remedy,
    )
    body = _body(envelopes.DeclarationFailed, failure)
    return JSONResponse(status_code=500, content=body)


FILESYSTEM_ROOT: Final[Path] = Path("/")


def bind_context(*, root: Path = FILESYSTEM_ROOT) -> bind.BindContext:
    """The context this process may act under, with the container claim verified.

    Raised rather than defaulted: a value the person who typed it believed in, silently read as
    the default, is the malformed-field default Principle IV forbids in its worst form. The
    marker is checked here as well as in the entry point, because a bare server command reaches
    this module and not that one -- and the per-request guard is the half that has to hold when
    terezy did not start the process.
    """
    resolved = bind.context_in_force(
        os.environ.get(bind.CONTEXT_VARIABLE), marker=bind.container_marker(root)
    )
    match resolved:
        case (
            bind.ContextNotRecognised(reason=reason) | bind.ContainerClaimUnverified(reason=reason)
        ):
            raise ValueError(reason)
        case _:
            return resolved


def guarded(served: FastAPI, *, context: bind.BindContext) -> ASGIApp:
    """The two per-request refusals, wrapped around one application."""
    return middleware.host_allowlist(middleware.loopback_guard(served, context=context))


application: Final[FastAPI] = create_app(data_root(), client=client_root())
"""The routed application. One data root, fixed at import, and the object the document is
generated from."""

app = guarded(application, context=bind_context())
"""What a server command addresses: the application behind both per-request guards."""
