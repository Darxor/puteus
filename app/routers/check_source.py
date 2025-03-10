import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from ..check_source import CheckSourceService
from ..db import get_async_session
from ..models.articles import Article

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/check-source", tags=["check-source"])


class ArticleOrError(BaseModel):
    """Response model for check source endpoint."""

    source_uuid: UUID
    article: Article | None = None
    error: str | None = None
    message: str | None = None


async def get_check_source_service(session: AsyncSession = Depends(get_async_session)) -> CheckSourceService:
    """Get an instance of the CheckSourceService.

    Parameters
    ----------
    session : AsyncSession
        The database session from dependency

    Returns
    -------
    CheckSourceService
        An instance of CheckSourceService
    """
    return CheckSourceService(session=session)


@router.post(
    "/batch",
    response_model=list[ArticleOrError],
    status_code=status.HTTP_200_OK,
)
async def check_multiple_sources(
    source_uuids: list[UUID] = Query(..., description="List of source UUIDs to check"),
    service: CheckSourceService = Depends(get_check_source_service),
) -> list[ArticleOrError]:
    """
    Check multiple sources for new content and create articles for changed content.

    Empty article indicates no content changes detected.
    """
    logger.info(f"API request to check {len(source_uuids)} sources")

    response: list[ArticleOrError] = []

    for source_uuid in source_uuids:
        try:
            article = await service.check_source(source_uuid=source_uuid)
            if article:
                response.append(ArticleOrError(source_uuid=source_uuid, article=article, error=None))
            else:
                response.append(
                    ArticleOrError(source_uuid=source_uuid, article=None, message="No content changes detected")
                )
        except Exception as e:
            logger.exception(f"Error checking source {source_uuid}: {str(e)}")
            response.append(ArticleOrError(source_uuid=source_uuid, article=None, error=str(e)))

    articles = [item.article for item in response if item.article]
    errors = [item.error for item in response if item.error]

    if len(errors) == len(source_uuids):
        logger.error("All source checks failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "All source checks failed", "errors": [r.model_dump(mode="json") for r in response]},
        )

    logger.info(f"Batch check completed. Created {len(articles)} articles, encountered {len(errors)} errors")
    return response


@router.post(
    "/batch/all",
    response_model=list[ArticleOrError],
    status_code=status.HTTP_200_OK,
)
async def check_all_sources(
    service: CheckSourceService = Depends(get_check_source_service),
) -> list[ArticleOrError]:
    """
    Check all sources for new content and create articles for changed content.
    """
    logger.info("API request to check all sources")
    source_uuids = [source.uuid for source in await service.get_all_sources()]

    return await check_multiple_sources(source_uuids=source_uuids, service=service)


@router.post(
    "/{source_uuid}",
    response_model=Article,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Source checked and article created if content changed"},
        204: {"description": "Source checked but no content changes detected"},
        404: {"description": "Source not found"},
        500: {"description": "Error checking source"},
    },
)
async def check_source_endpoint(
    source_uuid: UUID = Path(..., description="UUID of the source to check"),
    service: CheckSourceService = Depends(get_check_source_service),
) -> Article:
    """Check a source for new content and create an article if content has changed."""
    logger.info(f"API request to check source {source_uuid}")

    try:
        article = await service.check_source(source_uuid=source_uuid)
        if article:
            return article
        else:
            raise HTTPException(
                status_code=status.HTTP_204_NO_CONTENT, detail="Source checked but no content changes detected"
            )
    except HTTPException:
        raise

    except Exception as e:
        logger.exception(f"Unexpected error checking source {source_uuid}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error checking source: {str(e)}"
        ) from e
