from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from config.exceptions import NotFoundError, UnavailableError
from config.settings import API_PREFIX
from crocol.app.api.deps import admit_other, container
from crocol.app.deps import AppContainer
from crocol.app.schemas import EntityResponse, ErrorResponse

router = APIRouter(prefix=f"{API_PREFIX}/graph", tags=["graph"])
Kind = Literal["formation", "member", "group", "field", "well",
               "organization", "municipality", "seismic_3d", "fault",
               "contract", "contract_area", "regulation", "document",
               "person", "institution", "topic", "basin"]


@router.get("/entity", response_model=EntityResponse,
            responses={404: {"model": ErrorResponse},
                       503: {"model": ErrorResponse}},
            dependencies=[Depends(admit_other)])
async def entity(name: Annotated[str, Query(min_length=2, max_length=120)],
                 state: Annotated[AppContainer, Depends(container)],
                 kind: Kind | None = None,
                 ) -> dict:
    """Entity card from the knowledge graph: relations and documents."""
    if state.get_entity is None:
        raise UnavailableError()

    card = await state.get_entity.run(name.strip(), kind)
    if card is None:
        raise NotFoundError("entity not found")
    return card
