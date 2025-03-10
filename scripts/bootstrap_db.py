#!/usr/bin/env python
"""
Bootstrap script for initializing the database with sample Sites and Sources.

This script creates sample Sites and their respective Sources in the database
to help with development and testing.

Usage:
    uv run python -m scripts.bootstrap_db
"""

import asyncio
import logging
import sys
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

sys.path.append(".")  # Add the current directory to path for imports

from app.db import async_sessionmaker, init_db
from app.models.sources import Site, Source, SourceType, WatchableSelectorType
from app.models.urls import AnyUrl

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

SAMPLE_SITES: list[dict[str, Any]] = [
    {
        "name": "The New York Times",
        "url": "https://www.nytimes.com",
        "description": "The New York Times is an American daily newspaper based in New York City.",
        "country": "USA",
    },
    {
        "name": "BBC News",
        "url": "https://www.bbc.com/news",
        "description": "BBC News is an operational division of the British Broadcasting Corporation.",
        "country": "GBR",
    },
    {
        "name": "The Guardian",
        "url": "https://www.theguardian.com",
        "description": "The Guardian is a British daily newspaper.",
        "country": "GBR",
    },
    {
        "name": "Reuters",
        "url": "https://www.reuters.com",
        "description": "Reuters is an international news organization.",
        "country": "GBR",
    },
    {
        "name": "Al Jazeera",
        "url": "https://www.aljazeera.com",
        "description": "Al Jazeera is a Qatari international news channel.",
        "country": "QAT",
    },
    {
        "name": "RIA Novosti",
        "url": "https://ria.ru",
        "description": "RIA Novosti is a Russian state-owned news agency.",
        "country": "RUS",
    },
    {
        "name": "TASS",
        "url": "https://tass.ru",
        "description": "TASS is a major Russian news agency founded in 1904.",
        "country": "RUS",
    },
    {
        "name": "Kommersant",
        "url": "https://www.kommersant.ru",
        "description": "Kommersant is a nationally distributed daily newspaper published in Russia.",
        "country": "RUS",
    },
    {
        "name": "RT",
        "url": "https://russian.rt.com",
        "description": "RT is a Russian international television network.",
        "country": "RUS",
    },
    {
        "name": "Interfax",
        "url": "https://www.interfax.ru",
        "description": "Interfax is a major Russian news agency.",
        "country": "RUS",
    },
]

SAMPLE_SOURCE_TEMPLATES: list[dict[str, Any]] = [
    # RSS feeds
    {
        "site_name": "The New York Times",
        "type": SourceType.RSS,
        "uri": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
        "locale": "en",
        "watchable_selector": "//item",
        "watchable_selector_type": WatchableSelectorType.XPATH,
    },
    {
        "site_name": "BBC News",
        "type": SourceType.RSS,
        "uri": "http://feeds.bbci.co.uk/news/world/rss.xml",
        "locale": "en",
        "watchable_selector": "//item",
        "watchable_selector_type": WatchableSelectorType.XPATH,
    },
    {
        "site_name": "The Guardian",
        "type": SourceType.RSS,
        "uri": "https://www.theguardian.com/world/rss",
        "locale": "en",
        "watchable_selector": "//item",
        "watchable_selector_type": WatchableSelectorType.XPATH,
    },
    # Web pages
    {
        "site_name": "Reuters",
        "type": SourceType.WEBPAGE,
        "uri": "https://www.reuters.com/world/",
        "locale": "en",
        "watchable_selector": "article.story",
        "watchable_selector_type": WatchableSelectorType.CSS,
    },
    {
        "site_name": "Al Jazeera",
        "type": SourceType.WEBPAGE,
        "uri": "https://www.aljazeera.com/news/",
        "locale": "en",
        "watchable_selector": "#featured-news-container",
        "watchable_selector_type": WatchableSelectorType.CSS,
    },
    {
        "site_name": "RIA Novosti",
        "type": SourceType.WEBPAGE,
        "uri": "https://ria.ru/world/",
        "locale": "ru",
        "watchable_selector": ".rubric-list .list-item",
        "watchable_selector_type": WatchableSelectorType.CSS,
    },
    {
        "site_name": "TASS",
        "type": SourceType.WEBPAGE,
        "uri": "https://tass.ru/mezhdunarodnaya-panorama",
        "locale": "ru",
        "watchable_selector": "#infinite_listing a",
        "watchable_selector_type": WatchableSelectorType.CSS,
    },
    {
        "site_name": "Kommersant",
        "type": SourceType.WEBPAGE,
        "uri": "https://www.kommersant.ru/rubric/5",
        "locale": "ru",
        "watchable_selector": ".rubric_lenta > article",
        "watchable_selector_type": WatchableSelectorType.CSS,
    },
    {
        "site_name": "RT",
        "type": SourceType.WEBPAGE,
        "uri": "https://russian.rt.com/world",
        "locale": "ru",
        "watchable_selector": ".listing__column_sections",
        "watchable_selector_type": WatchableSelectorType.CSS,
    },
    {
        "site_name": "Interfax",
        "type": SourceType.WEBPAGE,
        "uri": "https://www.interfax.ru/world/",
        "locale": "ru",
        "watchable_selector": ".timeline",
        "watchable_selector_type": WatchableSelectorType.CSS,
    },
]


async def create_site(session: AsyncSession, site_data: dict[str, Any]) -> Site:
    """
    Create a Site in the database.

    Parameters
    ----------
    session : AsyncSession
        The database session
    site_data : dict[str, Any]
        The site data to create

    Returns
    -------
    Site
        The created site instance
    """
    # Check if site already exists
    stmt = select(Site).where(Site.url == site_data["url"], Site.active)
    result = await session.exec(stmt)
    existing_site = result.first()

    if existing_site:
        logger.info(f"Site {site_data['name']} already exists, skipping creation")
        return existing_site

    # Create new site
    site = Site(
        url=AnyUrl(site_data["url"]),
        name=site_data["name"],
        description=site_data["description"],
        country=site_data["country"],
    )

    session.add(site)
    await session.commit()
    await session.refresh(site)
    logger.info(f"Created site: {site.name} ({site.uuid})")
    return site


async def create_source(session: AsyncSession, source_data: dict[str, Any], site_map: dict[str, Site]) -> Source | None:
    """
    Create a Source in the database.

    Parameters
    ----------
    session : AsyncSession
        The database session
    source_data : dict[str, Any]
        The source data to create
    site_map : dict[str, Site]
        A mapping of site names to Site objects

    Returns
    -------
    Source
        The created source instance or None if the site is not found
    """
    site = site_map.get(source_data["site_name"])
    if not site:
        logger.error(f"Site {source_data['site_name']} not found, cannot create source")
        return None

    # Check if source already exists
    stmt = select(Source).where(Source.uri == source_data["uri"], Source.active)
    result = await session.exec(stmt)

    if existing_source := result.first():
        logger.info(f"Source {source_data['uri']} already exists, skipping creation")
        return existing_source

    # Create new source
    source = Source(
        site_uuid=site.uuid,
        type=source_data["type"],
        locale=source_data["locale"],
        uri=AnyUrl(source_data["uri"]),
        watchable_selector=source_data["watchable_selector"],
        watchable_selector_type=source_data["watchable_selector_type"],
    )

    session.add(source)
    await session.commit()
    await session.refresh(source)
    logger.info(f"Created source: {source.type.name} for site {site.name} ({source.uuid})")
    return source


async def bootstrap_database() -> None:
    """Bootstrap the database with initial data."""
    logger.info("Initializing database...")
    await init_db()

    async with async_sessionmaker() as session:
        # Create sites
        site_map = {}
        logger.info("Creating sites...")
        for site_data in SAMPLE_SITES:
            site = await create_site(session, site_data)
            site_map[site.name] = site

        # Create sources for each site
        logger.info("Creating sources...")
        for source_data in SAMPLE_SOURCE_TEMPLATES:
            await create_source(session, source_data, site_map)

        logger.info("Database bootstrapping completed successfully!")


async def main() -> None:
    """Main entry point for the bootstrap script."""
    try:
        logger.info("Starting database bootstrap process")
        await bootstrap_database()
    except Exception as e:
        logger.exception(f"Error bootstrapping database: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
