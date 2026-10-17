import json
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from config.exceptions import NotFoundError, UnavailableError
from config.settings import API_PREFIX
from crocol.app.api.deps import admit_other, container
from crocol.app.deps import AppContainer
from crocol.app.schemas import ErrorResponse, LocateResponse

router = APIRouter(prefix=f"{API_PREFIX}/map", tags=["map"])


@router.get("/locate", response_model=LocateResponse,
            responses={404: {"model": ErrorResponse},
                       503: {"model": ErrorResponse}},
            dependencies=[Depends(admit_other)])
async def locate(name: Annotated[str, Query(min_length=2, max_length=120)],
                 state: Annotated[AppContainer, Depends(container)]
                 ) -> dict:
    """GeoJSON (WGS84) of a well, field or municipality in the VMM."""
    if state.spatial is None:
        raise UnavailableError()

    result = await state.spatial.run("locate", {"name": name})
    if not result.rows:
        raise NotFoundError("place not found")

    row = result.rows[0]
    geojson = json.loads(row["geojson"]) if row.get("geojson") else None
    return {"kind": row["kind"], "name": row["name"], "geojson": geojson,
            "source": row.get("source") or result.source}
