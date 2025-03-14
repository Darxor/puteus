import logging
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, ClassVar, Generic, Self, TypedDict, TypeVar

import pydantic
import tenacity
from fake_useragent import UserAgent
from playwright.async_api import Browser, BrowserContext, Locator, Page, async_playwright

logger = logging.getLogger(__name__)


class ScraperConfig(TypedDict):
    """
    Configuration for scraper behavior.

    Parameters
    ----------
    MAX_RETRIES : int
        Maximum number of retry attempts
    SCROLL_TIMEOUT_MS : int
        Timeout between scrolling attempts in milliseconds
    LOAD_TIMEOUT_MS : int
        Timeout for page loading in milliseconds
    DEFAULT_MAX_POSTS : int
        Default maximum number of posts to scrape
    """

    MAX_RETRIES: int
    SCROLL_TIMEOUT_MS: int
    LOAD_TIMEOUT_MS: int
    DEFAULT_MAX_POSTS: int


DEFAULT_SETTINGS: ScraperConfig = {
    "MAX_RETRIES": 3,
    "SCROLL_TIMEOUT_MS": 500,
    "LOAD_TIMEOUT_MS": 500,
    "DEFAULT_MAX_POSTS": 50,
}


# Exception classes
class ScraperError(Exception):
    """Base exception class for all scraper-related errors."""

    pass


class NavigationError(ScraperError):
    """Raised when navigation to a URL fails."""

    pass


class ExtractionError(ScraperError):
    """Raised when content extraction fails."""

    pass


def before_retry_log(retry_state: tenacity.RetryCallState):
    """
    Log before retry with retry number and exception info.

    Parameters
    ----------
    retry_state : tenacity.RetryCallState
        The current state of the retry
    """
    attempt = retry_state.attempt_number
    exc_info = retry_state.outcome.exception() if retry_state.outcome else None
    func_name = retry_state.fn.__name__ if retry_state.fn else "Unknown function"
    wait_time = retry_state.retry_object.wait(retry_state)

    logger.warning(f"{func_name} failed (attempt {attempt}), retrying in {wait_time:.2f}s: {exc_info}")


class BrowserManager:
    """
    Manages browser lifecycle for web scraping.

    Parameters
    ----------
    headless : bool, default=True
        Whether to run browser in headless mode
    user_agent : str, optional
        User agent string to use, if None a random desktop one will be generated
    context_kwargs : dict, optional
        Additional parameters for browser context
    """

    def __init__(
        self, headless: bool = True, user_agent: str | None = None, context_kwargs: dict[str, Any] | None = None
    ) -> None:
        self.headless = headless

        if user_agent is None:
            try:
                user_agent = UserAgent(platforms="desktop").random
                logger.debug(f"Using random user agent: {user_agent}")
            except Exception as e:
                user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36"
                logger.warning(f"Failed to generate random user agent: {e}. Using fallback.")

        self.context_kwargs = {"viewport": {"width": 1280, "height": 720}, "user_agent": user_agent}
        if context_kwargs:
            self.context_kwargs.update(context_kwargs)

        self._context_manager = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None

    async def __aenter__(self) -> Self:
        """Initialize browser for use in async context manager."""
        logger.debug("Launching browser...")
        self._context_manager = async_playwright()
        p = await self._context_manager.__aenter__()
        try:
            self.browser = await p.chromium.launch(headless=self.headless)
            self.context = await self.browser.new_context(**self.context_kwargs)
            logger.debug("Browser initialized successfully")
            return self
        except Exception as e:
            logger.error(f"Error initializing browser: {e}")
            await self._context_manager.__aexit__(None, None, None)
            raise

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up browser resources when exiting context."""
        logger.debug("Cleaning up browser resources")
        if self._context_manager:
            await self._context_manager.__aexit__(exc_type, exc_val, exc_tb)
            self.browser = None
            self.context = None

    async def new_page(self) -> Page:
        """
        Create a new page in the browser context.

        Returns
        -------
        Page
            New playwright page instance
        """
        if not self.context:
            raise RuntimeError("Browser context is not initialized. Use with 'async with' context manager.")
        return await self.context.new_page()


class AttributeType(StrEnum):
    """Enum for attribute types that can be extracted from a locator."""

    INNER_TEXT = "INNER_TEXT"
    INNER_HTML = "INNER_HTML"
    TEXT_CONTENT = "TEXT_CONTENT"


@dataclass
class PostFieldSelector:
    """
    Represents a field in a post model.

    Parameters
    ----------
    selector : str
        CSS selector to extract the field value
    attribute : str or AttributeType
        Attribute name to extract from the field or special extraction type
    """

    selector: str
    attribute: str | AttributeType = AttributeType.INNER_TEXT

    def is_special_attribute(self) -> bool:
        """Check if the attribute is a special extraction type."""
        return self.attribute in {t.value for t in AttributeType}


class PostModel(pydantic.BaseModel):
    """
    Base Pydantic model for all post data.

    This is an abstract model that should be extended by site-specific implementations.
    """

    field_selectors: ClassVar[dict[str, PostFieldSelector]]

    @classmethod
    async def from_locator(cls, locator: Locator) -> Self:
        """
        Creates an instance of the class from a Playwright Locator.

        Parameters
        ----------
        locator : Locator
            A Playwright Locator object pointing to the element containing data.

        Returns
        -------
        Self
            A new instance of the class populated with extracted values.
        """
        values = {}
        for field_name, field in cls.field_selectors.items():
            try:
                field_locator = locator.locator(field.selector) if field.selector else locator

                if field.is_special_attribute():
                    if field.attribute == AttributeType.INNER_TEXT:
                        values[field_name] = await field_locator.inner_text()
                    elif field.attribute == AttributeType.INNER_HTML:
                        values[field_name] = await field_locator.inner_html()
                    elif field.attribute == AttributeType.TEXT_CONTENT:
                        values[field_name] = await field_locator.text_content() or ""
                else:
                    values[field_name] = await field_locator.get_attribute(field.attribute) or ""
            except Exception as e:
                raise ExtractionError(f"Failed to extract field '{field_name}': {e}") from e

        return cls(**values)

    def get_item_id(self) -> str:
        """Generate a unique ID for the item."""
        return self.model_dump_json()


T = TypeVar("T", bound=PostModel)


class ScraperRuleset(pydantic.BaseModel, Generic[T]):
    """
    Base configuration model for scraper rulesets.

    A ruleset defines how to extract data from a specific website.

    Parameters
    ----------
    post_selector : str
        CSS selector to identify individual post elements
    scroll_element_selector : str
        CSS selector for the element to scroll to when loading more content
    post_model : Type[T]
        Pydantic model class for the post data
    """

    DEFAULT_SCROLL: ClassVar[Mapping[str, int | float]] = {"delta_y": 500, "delta_x": 0}

    post_selector: str
    scroll_element_selector: str
    post_model: type[T]

    class Config:
        arbitrary_types_allowed = True

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(DEFAULT_SETTINGS["MAX_RETRIES"]),
        wait=tenacity.wait_exponential(multiplier=0.5, min=0.1, max=10),
        retry=tenacity.retry_if_exception_type((Exception,)),
        before_sleep=before_retry_log,
        reraise=True,
    )
    async def extract_post(self, locator: Locator) -> T:
        """Extract post data from a locator with retry logic."""
        if not self.post_model:
            raise ValueError("post_model must be set before calling extract_post")
        try:
            return await self.post_model.from_locator(locator)
        except Exception as e:
            raise ExtractionError(f"Failed to extract post: {e}") from e

    async def get_scroll_offset(self, page: Page, element: Locator) -> Mapping[str, int | float]:
        """Calculate scroll offset based on element size."""
        try:
            if bounding_box := await element.bounding_box():
                return {"delta_y": bounding_box["height"] + 100, "delta_x": 0}
            return self.DEFAULT_SCROLL
        except Exception as e:
            logger.warning(f"Error getting scroll offset: {e}")
            return self.DEFAULT_SCROLL


class DynamicScraper(Generic[T]):
    """
    Generic scraper for extracting content from dynamically loaded pages.

    Parameters
    ----------
    ruleset : ScraperRuleset
        Ruleset that defines how to extract data
    debug : bool, default=False
        If True, runs browser in visible mode for debugging
    max_retries : int, optional
        Maximum number of retry attempts
    browser_manager : BrowserManager, optional
        Custom browser manager instance
    config : ScraperConfig, optional
        Custom configuration settings
    """

    def __init__(
        self,
        ruleset: ScraperRuleset[T],
        debug: bool = False,
        max_retries: int | None = None,
        browser_manager: BrowserManager | None = None,
        config: ScraperConfig | None = None,
    ):
        self.ruleset = ruleset
        self.config = DEFAULT_SETTINGS.copy()
        if config:
            self.config.update(config)

        self.max_retries = max_retries if max_retries is not None else self.config["MAX_RETRIES"]
        self.browser = browser_manager or BrowserManager(headless=not debug)

    async def __aenter__(self):
        """Set up the browser when entering context."""
        await self.browser.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up resources when exiting context."""
        await self.browser.__aexit__(exc_type, exc_val, exc_tb)

    @tenacity.retry(
        retry=tenacity.retry_if_exception_type(ExtractionError),
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_fixed(0.5),
        before_sleep=before_retry_log,
    )
    async def _extract_items_chunk(self, page: Page) -> list[T]:
        """Extract a batch of items from the current page."""
        logger.debug("Extracting content batch...")
        items = []

        for i, locator in enumerate(await page.locator(self.ruleset.post_selector).all()):
            try:
                if item := await self.ruleset.extract_post(locator):
                    items.append(item)
            except ExtractionError as e:
                logger.warning(f"Failed to extract item {i}: {e}")

        return items

    @tenacity.retry(
        retry=tenacity.retry_if_result(lambda result: result is False),
        stop=tenacity.stop_after_attempt(2),
        wait=tenacity.wait_fixed(1),
        before_sleep=lambda rs: logger.debug(f"Retrying scroll after failed attempt #{rs.attempt_number}"),
    )
    async def _scroll_to_load_more(self, page: Page) -> bool:
        """Scroll to load more content."""
        logger.debug("Scrolling to load more content...")
        try:
            last_element = page.locator(self.ruleset.scroll_element_selector).last
            await last_element.scroll_into_view_if_needed()

            scroll_params = await self.ruleset.get_scroll_offset(page, last_element)
            await page.mouse.wheel(**scroll_params)
            await page.wait_for_timeout(self.config["SCROLL_TIMEOUT_MS"])
            return True
        except Exception as e:
            logger.warning(f"Error during scrolling: {e}")
            return False

    @tenacity.retry(
        stop=tenacity.stop_after_attempt(3),
        wait=tenacity.wait_exponential(multiplier=0.5, min=0.5, max=10),
        retry=tenacity.retry_if_exception_type((NavigationError,)),
        before_sleep=before_retry_log,
    )
    async def _navigate_to_url(self, page: Page, url: str) -> None:
        """Navigate to the specified URL with retry logic."""
        try:
            logger.info(f"Navigating to {url}")
            await page.goto(url)
        except Exception as e:
            raise NavigationError(f"Failed to navigate to {url}: {e}") from e

    async def _collect_items(self, page: Page, max_items: int) -> list[T]:
        """Collect items from the page up to the maximum number."""
        items: list[T] = []
        seen_items = set()

        @tenacity.retry(
            stop=tenacity.stop_after_attempt(self.max_retries),
            wait=tenacity.wait_exponential(multiplier=0.5, min=0.1, max=10),
            retry=tenacity.retry_if_result(lambda result: result is False),
            before_sleep=lambda rs: logger.debug(f"Retrying item collection after attempt #{rs.attempt_number}"),
        )
        async def add_new_items() -> bool:
            prev_item_count = len(items)

            for item in await self._extract_items_chunk(page):
                item_id = item.get_item_id()
                if item_id not in seen_items:
                    seen_items.add(item_id)
                    items.append(item)

            new_items = len(items) - prev_item_count
            logger.info(f"Found {new_items} new items, total {len(items)}/{max_items} items.")

            if new_items == 0:
                return False

            if not await self._scroll_to_load_more(page):
                logger.warning("Failed to scroll, may not find more items.")

            return True

        while len(items) < max_items:
            try:
                await add_new_items()
            except tenacity.RetryError:
                logger.warning("Maximum retries exceeded while collecting items")
                break

        return items[:max_items]

    async def extract_content(self, url: str, max_items: int | None = None) -> list[T]:
        """
        Extract content from the given URL.

        Parameters
        ----------
        url : str
            The URL of the page to scrape
        max_items : int, optional
            Maximum number of items to extract

        Returns
        -------
        list[T]
            List of extracted items
        """
        max_items = max_items if max_items is not None else self.config["DEFAULT_MAX_POSTS"]
        logger.info(f"Extracting up to {max_items} items from {url}")

        if not self.browser.context:
            raise RuntimeError("Browser context is not initialized.")

        page = await self.browser.new_page()
        try:
            await self._navigate_to_url(page, url)
            items = await self._collect_items(page, max_items)
            logger.info(f"Content extraction complete. Extracted {len(items)} items.")
            return items
        finally:
            await page.close()
