import hashlib
import logging
import re
from uuid import UUID

import httpx
from bs4 import BeautifulSoup
from fastapi import HTTPException
from lxml import etree
from sqlmodel import desc, select
from sqlmodel.ext.asyncio.session import AsyncSession
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .models.articles import Article, ArticleCreate, WatchLog, WatchLogCreate
from .models.sources import Source, WatchableSelectorType
from .models.urls import AnyUrl


class CheckSourceService:
    """Service to check sources for new content and create articles when content changes.

    This service fetches content from a source URL, extracts content using the specified selector,
    compares it with previous content hash, and creates new articles when changes are detected.

    Parameters
    ----------
    session : AsyncSession
        SQLModel async session for database operations

    Attributes
    ----------
    session : AsyncSession
        SQLModel async session for database operations
    logger : logging.Logger
        Logger for the service
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.logger = logging.getLogger(__name__)

    @retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def _fetch_with_retry(self, client: httpx.AsyncClient, url: str) -> httpx.Response:
        """Execute HTTP GET request with automatic retries.

        Parameters
        ----------
        client : httpx.AsyncClient
            The HTTP client to use for requests
        url : str
            The URL to fetch content from

        Returns
        -------
        httpx.Response
            The HTTP response

        Raises
        ------
        httpx.HTTPError
            If the request fails after all retry attempts
        """
        self.logger.debug(f"Fetching content from {url}")
        response = await client.get(url, timeout=10.0)
        response.raise_for_status()
        self.logger.debug(f"Successfully fetched content from {url} (status code: {response.status_code})")
        return response

    async def fetch_content(self, url: str) -> str:
        """Fetch content from a URL with automatic retries.

        Uses exponential backoff retry strategy for transient errors.

        Parameters
        ----------
        url : str
            The URL to fetch content from

        Returns
        -------
        str
            The raw content retrieved from the URL

        Raises
        ------
        HTTPException
            If there's an error fetching the content after all retries are exhausted
        """
        try:
            self.logger.info(f"Fetching content from URL: {url}")
            async with httpx.AsyncClient() as client:
                response = await self._fetch_with_retry(client, url)
                content = response.text
                self.logger.info(f"Successfully fetched {len(content)} bytes from {url}")
                return content
        except httpx.HTTPError as e:
            self.logger.exception(f"Error fetching content from {url}: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error fetching source content after multiple attempts: {str(e)}"
            ) from e

    def extract_content(self, content: str, selector: str, selector_type: WatchableSelectorType) -> str:
        """Extract content from raw HTML/text using the specified selector.

        Parameters
        ----------
        content : str
            Raw content from the source
        selector : str
            The selector to use for extraction
        selector_type : WatchableSelectorType
            The type of selector (CSS, XPATH, REGEX)

        Returns
        -------
        str
            The extracted content

        Raises
        ------
        HTTPException
            If the selector type is not supported or extraction fails
        """
        if not content:
            self.logger.warning("Empty content provided for extraction")
            return ""

        if not selector:
            self.logger.info("No selector provided, returning full content")
            return content

        try:
            self.logger.debug(f"Extracting content using {selector_type} selector: {selector}")

            if selector_type == WatchableSelectorType.CSS:
                soup = BeautifulSoup(content, "html.parser")
                elements = soup.select(selector)
                extracted = "\n".join([el.get_text().strip() for el in elements])

            elif selector_type == WatchableSelectorType.XPATH:
                tree = etree.HTML(content.encode(), parser=etree.HTMLParser())
                elements = tree.xpath(selector)
                extracted = "\n".join([el.text.strip() if hasattr(el, "text") else str(el) for el in elements])

            elif selector_type == WatchableSelectorType.REGEX:
                matches = re.findall(selector, content)
                extracted = "\n".join(matches)

            else:
                self.logger.error(f"Unsupported selector type: {selector_type}")
                raise HTTPException(status_code=400, detail=f"Unsupported selector type: {selector_type}")

            self.logger.info(f"Successfully extracted {len(extracted)} bytes of content")
            return extracted
        except Exception as e:
            self.logger.exception(f"Error extracting content with {selector_type} selector: {str(e)}")
            raise HTTPException(
                status_code=500, detail=f"Error extracting content with {selector_type} selector: {str(e)}"
            ) from e

    def calculate_hash(self, content: str) -> str:
        """Calculate SHA-256 hash of content.

        Parameters
        ----------
        content : str
            The content to hash

        Returns
        -------
        str
            The hexadecimal digest of the hash
        """
        if not content:
            self.logger.warning("Empty content provided for hashing")
            content = ""

        hash_value = hashlib.sha256(content.encode("utf-8")).hexdigest()
        self.logger.debug(f"Calculated content hash: {hash_value[:8]}...")
        return hash_value

    async def get_latest_watchlog(self, source_uuid: UUID) -> WatchLog | None:
        """Get the most recent watchlog for a source.

        Parameters
        ----------
        source_uuid : UUID
            The UUID of the source

        Returns
        -------
        Optional[WatchLog]
            The most recent watchlog entry, or None if no entries exist
        """
        self.logger.debug(f"Getting latest watchlog for source {source_uuid}")
        stmt = (
            select(WatchLog)
            .where(WatchLog.source_uuid == source_uuid, WatchLog.active)
            .order_by(desc(WatchLog.created_at))
            .limit(1)
        )
        result = await self.session.exec(stmt)
        watchlog = result.first()

        if watchlog:
            await self.session.refresh(watchlog)
            self.logger.debug(f"Found watchlog {watchlog.uuid} from {watchlog.created_at}")
        else:
            self.logger.info(f"No previous watchlog found for source {source_uuid}")

        return watchlog

    async def create_article(self, watchlog_uuid: UUID, source_uri: str, extracted_content: str) -> Article:
        """Create a new article from extracted content.

        Parameters
        ----------
        watchlog_uuid : UUID
            UUID of the associated watchlog
        source_uri : str
            URI of the source
        extracted_content : str
            The extracted content for the article

        Returns
        -------
        Article
            The newly created article
        """
        self.logger.info(f"Creating new article for watchlog {watchlog_uuid}")

        content = extracted_content or ""
        lines = content.split("\n")
        title = lines[0][:100].strip() if lines else ""

        if not title:
            title = "New content from source"
            self.logger.warning(f"No title could be extracted, using default: '{title}'")

        description = content[:200].strip() if len(content) > 30 else None

        article_data = ArticleCreate(
            watchlog_uuid=watchlog_uuid,
            title=title,
            uri=AnyUrl(source_uri),
            description=description,
            is_newsworthy=True,
        )

        article = Article(**article_data.model_dump())
        self.session.add(article)
        await self.session.commit()
        await self.session.refresh(article)
        self.logger.info(f"Created article {article.uuid}: {title}")
        return article

    async def create_watchlog(self, source_uuid: UUID, previous_uuid: UUID | None, content_hash: str) -> WatchLog:
        """Create a new watchlog entry.

        Parameters
        ----------
        source_uuid : UUID
            The UUID of the source
        previous_uuid : Optional[UUID]
            UUID of the previous watchlog entry, if any
        content_hash : str
            Hash of the extracted content

        Returns
        -------
        WatchLog
            The newly created watchlog
        """
        self.logger.info(f"Creating new watchlog for source {source_uuid}")
        watchlog_data = WatchLogCreate(source_uuid=source_uuid, previous_uuid=previous_uuid, content_hash=content_hash)

        watchlog = WatchLog(**watchlog_data.model_dump())
        self.session.add(watchlog)
        await self.session.commit()
        await self.session.refresh(watchlog)
        self.logger.info(f"Created watchlog {watchlog.uuid}")
        return watchlog

    async def check_source(self, source_uuid: UUID) -> Article | None:
        """Check a source for new content and create an article if content has changed.

        Parameters
        ----------
        source_uuid : UUID
            UUID of the source to check

        Returns
        -------
        Optional[Article]
            Newly created article if content changed, None otherwise

        Raises
        ------
        HTTPException
            If source not found or errors occur during processing
        """
        self.logger.info(f"Checking source {source_uuid} for changes")

        stmt = select(Source).where(Source.uuid == source_uuid, Source.active)
        result = await self.session.exec(stmt)
        source = result.one_or_none()

        if source is None:
            self.logger.error(f"Source {source_uuid} not found or not active")
            raise HTTPException(status_code=404, detail="Source not found")

        await self.session.refresh(source)

        source_uri = source.uri
        selector = source.watchable_selector or ""
        selector_type = source.watchable_selector_type or WatchableSelectorType.CSS

        raw_content = await self.fetch_content(source_uri)
        extracted_content = self.extract_content(
            content=raw_content,
            selector=selector,
            selector_type=selector_type,
        )

        content_hash = self.calculate_hash(extracted_content)
        self.logger.debug(f"Content hash: {content_hash}")

        latest_watchlog = await self.get_latest_watchlog(source_uuid)

        previous_hash = None
        if latest_watchlog:
            previous_hash = latest_watchlog.content_hash

        new_watchlog = await self.create_watchlog(
            source_uuid=source_uuid,
            previous_uuid=latest_watchlog.uuid if latest_watchlog else None,
            content_hash=content_hash,
        )

        if previous_hash is None or previous_hash != content_hash:
            self.logger.info(f"Content changed for source {source_uuid}, creating new article")
            article = await self.create_article(
                watchlog_uuid=new_watchlog.uuid,
                source_uri=source_uri,
                extracted_content=extracted_content,
            )
            return article
        else:
            self.logger.info(f"No content changes detected for source {source_uuid}")
            return None
