import logging

from .check_source import CheckSourceService

logger = logging.getLogger(__name__)


async def check_all_sources(
    check_source_service: CheckSourceService,
) -> None:
    """
    Check all sources for new content and create articles for changed content.
    """
    logger.info("Checking all sources")
    sources = await check_source_service.get_all_sources()

    articles = []
    errors = []

    for source in sources:
        try:
            article = await check_source_service.check_source(source_uuid=source.uuid)
            if article:
                articles.append(article)
        except Exception as e:
            logger.error(f"Error checking source {source.uuid}: {e}")
            errors.append((source.uuid, str(e)))

    logger.info(f"Checked {len(sources)} sources, {len(articles)} articles created, {len(errors)} errors")
