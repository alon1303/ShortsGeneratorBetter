"""
Reddit client for fetching trending stories from subreddits.
Uses HTTP requests to Reddit's public JSON endpoints (no API keys required).
"""

import asyncio
import re
import logging
import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import os
import time

import httpx
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class RedditStory:
    """Represents a cleaned Reddit story with metadata."""
    id: str
    title: str
    text: str
    subreddit: str
    url: str
    score: int
    upvote_ratio: float
    created_utc: float
    author: Optional[str]
    is_nsfw: bool
    word_count: int
    estimated_duration: float  # in seconds (150 words/minute)
    
    def __str__(self) -> str:
        return f"{self.title}\n\n{self.text}"

class RedditClient:
    """Async Reddit client for fetching and processing stories using HTTP requests."""
    
    def __init__(
        self,
        user_agent: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
    ):
        """
        Initialize Reddit client with HTTP configuration.
        
        Args:
            user_agent: User agent string for HTTP requests
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.user_agent = user_agent or os.getenv(
            "REDDIT_USER_AGENT", 
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self.timeout = timeout
        self.max_retries = max_retries
        self.client = None
        
        # Base URLs for Reddit JSON endpoints
        self.base_url = "https://www.reddit.com"
        self.oauth_url = "https://oauth.reddit.com"
        
        logger.info(f"Reddit HTTP client initialized (user_agent: {self.user_agent[:50]}...)")
    
    async def initialize(self):
        """Initialize the HTTP client."""
        if self.client is None:
            self.client = httpx.AsyncClient(
                headers={
                    "User-Agent": self.user_agent,
                    "Accept": "application/json",
                },
                timeout=self.timeout,
                follow_redirects=True,
            )
            logger.debug("HTTP client initialized")
    
    async def close(self):
        """Close the HTTP client connection."""
        if self.client:
            await self.client.aclose()
            self.client = None
            logger.debug("HTTP client closed")
    
    async def __aenter__(self):
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def _make_request(self, url: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make HTTP request to Reddit with retry logic.
        
        Args:
            url: URL to request
            params: Query parameters
            
        Returns:
            JSON response as dict or None if failed
        """
        if self.client is None:
            await self.initialize()
        
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Requesting {url} (attempt {attempt + 1}/{self.max_retries})")
                response = await self.client.get(url, params=params)
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:  # Rate limited
                    wait_time = (attempt + 1) * 2  # Exponential backoff
                    logger.warning(f"Rate limited, waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                elif response.status_code == 404:
                    logger.error(f"Resource not found: {url}")
                    return None
                else:
                    logger.error(f"HTTP {response.status_code}: {response.text[:200]}")
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(1)
                        
            except httpx.TimeoutException:
                logger.warning(f"Timeout on attempt {attempt + 1}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Request error on attempt {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1)
        
        logger.error(f"Failed to fetch {url} after {self.max_retries} attempts")
        return None
    
    @staticmethod
    def clean_story_text(text: str) -> str:
        """
        Clean Reddit story text by removing unwanted elements.
        
        Args:
            text: Raw Reddit post text
            
        Returns:
            Cleaned text with URLs, edits, and markdown removed
        """
        if not text:
            return ""
        
        # Remove URLs (but keep the text)
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)  # Markdown links
        text = re.sub(r'https?://\S+', '', text)  # Raw URLs
        
        # Remove common Reddit formatting
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Bold
        text = re.sub(r'\*(.*?)\*', r'\1', text)  # Italics
        text = re.sub(r'~~(.*?)~~', r'\1', text)  # Strikethrough
        text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)  # Headers
        text = re.sub(r'`{1,3}(.*?)`{1,3}', r'\1', text)  # Code blocks
        
        # Remove edit notes and common phrases
        edit_patterns = [
            r'EDIT\s*[:\.].*',
            r'Update\s*[:\.].*',
            r'\(edit:.*?\)',
            r'\[edit:.*?\]',
            r'Thanks for the gold.*',
            r'Thanks for the awards.*',
            r'Wow this blew up.*',
            r'RIP my inbox.*',
        ]
        
        for pattern in edit_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        # Remove excessive whitespace
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        
        # Remove quote blocks (lines starting with >)
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            if not line.strip().startswith('>'):
                cleaned_lines.append(line.strip())
        
        text = '\n'.join(cleaned_lines)
        
        # Final cleanup
        text = text.strip()
        
        return text
    
    @staticmethod
    def calculate_duration(word_count: int, words_per_minute: int = 150) -> float:
        """
        Calculate estimated narration duration.
        
        Args:
            word_count: Number of words in text
            words_per_minute: Narration speed (default 150 wpm)
            
        Returns:
            Duration in seconds
        """
        minutes = word_count / words_per_minute
        return minutes * 60
    
    def _parse_post_data(self, post_data: Dict, subreddit: str) -> Optional[RedditStory]:
        """
        Parse Reddit post data into RedditStory object.
        
        Args:
            post_data: Post data from Reddit API
            subreddit: Subreddit name
            
        Returns:
            RedditStory object or None if invalid
        """
        try:
            # Skip if not a text post
            if post_data.get("is_self", False) is False:
                return None
            
            # Get text content
            text = post_data.get("selftext", "")
            if not text or text in ["[deleted]", "[removed]"]:
                return None
            
            # Clean the text
            cleaned_text = self.clean_story_text(text)
            
            # Skip if text is too short after cleaning
            if len(cleaned_text) < 100:
                return None
            
            # Calculate word count and duration
            word_count = len(cleaned_text.split())
            estimated_duration = self.calculate_duration(word_count)
            
            # Create story object
            story = RedditStory(
                id=post_data.get("id", ""),
                title=post_data.get("title", ""),
                text=cleaned_text,
                subreddit=subreddit,
                url=f"https://reddit.com{post_data.get('permalink', '')}",
                score=post_data.get("score", 0),
                upvote_ratio=post_data.get("upvote_ratio", 0.0),
                created_utc=post_data.get("created_utc", 0),
                author=post_data.get("author"),
                is_nsfw=post_data.get("over_18", False),
                word_count=word_count,
                estimated_duration=estimated_duration,
            )
            
            return story
            
        except Exception as e:
            logger.error(f"Error parsing post data: {e}")
            return None
    
    async def fetch_trending_stories(
        self,
        subreddit: str = "AskReddit",
        time_filter: str = "day",
        limit: int = 10,
        min_score: int = 100,
        min_text_length: int = 200,
        max_text_length: int = 5000,
        exclude_nsfw: bool = True,
    ) -> List[RedditStory]:
        """
        Fetch trending stories from a subreddit using Reddit's JSON endpoint.
        
        Args:
            subreddit: Subreddit name to fetch from
            time_filter: Time filter (hour, day, week, month, year, all)
            limit: Maximum number of posts to fetch
            min_score: Minimum score (upvotes) threshold
            min_text_length: Minimum text length in characters
            max_text_length: Maximum text length in characters
            exclude_nsfw: Whether to exclude NSFW posts
            
        Returns:
            List of cleaned RedditStory objects
        """
        logger.info(f"Fetching trending stories from r/{subreddit} (time_filter={time_filter})")
        
        # Map time_filter to Reddit's t parameter
        time_map = {
            "hour": "hour",
            "day": "day",
            "week": "week",
            "month": "month",
            "year": "year",
            "all": "all",
            "hot": "hot"  # Special case for hot posts
        }
        
        t_param = time_map.get(time_filter, "day")
        
        stories = []
        try:
            # Construct URL for subreddit's top posts
            if time_filter == "hot":
                url = f"{self.base_url}/r/{subreddit}/hot.json"
                params = {"limit": limit * 2}  # Fetch extra to filter
            else:
                url = f"{self.base_url}/r/{subreddit}/top.json"
                params = {"t": t_param, "limit": limit * 2}
            
            # Make request
            data = await self._make_request(url, params)
            if not data or "data" not in data:
                logger.error(f"No data returned from r/{subreddit}")
                return stories
            
            # Process posts
            posts = data["data"].get("children", [])
            logger.debug(f"Received {len(posts)} posts from r/{subreddit}")
            
            for post in posts:
                try:
                    post_data = post.get("data", {})
                    
                    # Apply filters
                    if exclude_nsfw and post_data.get("over_18", False):
                        logger.debug(f"Skipping NSFW post: {post_data.get('id')}")
                        continue
                        
                    if post_data.get("score", 0) < min_score:
                        logger.debug(f"Skipping low-score post ({post_data.get('score')}): {post_data.get('id')}")
                        continue
                    
                    # Parse post data
                    story = self._parse_post_data(post_data, subreddit)
                    if not story:
                        continue
                    
                    # Check text length
                    if len(story.text) < min_text_length:
                        logger.debug(f"Skipping short post ({len(story.text)} chars): {story.id}")
                        continue
                        
                    if len(story.text) > max_text_length:
                        logger.debug(f"Skipping long post ({len(story.text)} chars): {story.id}")
                        continue
                    
                    stories.append(story)
                    logger.info(f"Added story: {story.title[:50]}... ({story.word_count} words, {story.estimated_duration:.1f}s)")
                    
                    # Stop if we have enough stories
                    if len(stories) >= limit:
                        break
                        
                except Exception as e:
                    logger.error(f"Error processing post {post_data.get('id', 'unknown')}: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error fetching stories from r/{subreddit}: {e}")
        
        logger.info(f"Fetched {len(stories)} stories from r/{subreddit}")
        return stories
    
    async def fetch_story_by_id(self, story_id: str) -> Optional[RedditStory]:
        """
        Fetch a specific story by its Reddit ID using JSON endpoint.
        
        Args:
            story_id: Reddit submission ID
            
        Returns:
            RedditStory object or None if not found
        """
        logger.info(f"Fetching story by ID: {story_id}")
        
        try:
            # Construct URL for specific post
            url = f"{self.base_url}/by_id/t3_{story_id}.json"
            
            # Make request
            data = await self._make_request(url)
            if not data or "data" not in data:
                logger.error(f"No data returned for story {story_id}")
                return None
            
            # Extract post data
            posts = data["data"].get("children", [])
            if not posts:
                logger.error(f"No post found with ID {story_id}")
                return None
            
            post_data = posts[0].get("data", {})
            
            # Parse post data
            subreddit = post_data.get("subreddit", "unknown")
            story = self._parse_post_data(post_data, subreddit)
            
            if story:
                logger.info(f"Fetched story by ID: {story.title[:50]}...")
            else:
                logger.warning(f"Story {story_id} is not a valid text post")
            
            return story
            
        except Exception as e:
            logger.error(f"Error fetching story {story_id}: {e}")
            return None
    
    async def search_stories(
        self,
        query: str,
        subreddit: Optional[str] = None,
        limit: int = 10,
        sort: str = "relevance",
        time_filter: str = "all",
    ) -> List[RedditStory]:
        """
        Search for stories matching a query using Reddit's search JSON endpoint.
        
        Args:
            query: Search query
            subreddit: Optional subreddit to search within
            limit: Maximum number of results
            sort: Sort method (relevance, hot, top, new, comments)
            time_filter: Time filter (all, day, week, month, year)
            
        Returns:
            List of RedditStory objects
        """
        logger.info(f"Searching for stories with query: '{query}'")
        
        # Map sort parameter
        sort_map = {
            "relevance": "relevance",
            "hot": "hot",
            "top": "top",
            "new": "new",
            "comments": "comments"
        }
        
        sort_param = sort_map.get(sort, "relevance")
        
        stories = []
        try:
            # Construct search URL
            if subreddit:
                url = f"{self.base_url}/r/{subreddit}/search.json"
            else:
                url = f"{self.base_url}/search.json"
            
            params = {
                "q": query,
                "sort": sort_param,
                "t": time_filter,
                "limit": limit * 2,  # Fetch extra to filter
                "restrict_sr": "on" if subreddit else "off",
                "type": "link",
            }
            
            # Make request
            data = await self._make_request(url, params)
            if not data or "data" not in data:
                logger.error(f"No search results for query: '{query}'")
                return stories
            
            # Process search results
            posts = data["data"].get("children", [])
            logger.debug(f"Received {len(posts)} search results")
            
            for post in posts:
                try:
                    post_data = post.get("data", {})
                    
                    # Parse post data
                    story_subreddit = post_data.get("subreddit", "unknown")
                    story = self._parse_post_data(post_data, story_subreddit)
                    if not story:
                        continue
                    
                    stories.append(story)
                    
                    # Stop if we have enough stories
                    if len(stories) >= limit:
                        break
                        
                except Exception as e:
                    logger.error(f"Error processing search result {post_data.get('id', 'unknown')}: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error searching stories: {e}")
        
        logger.info(f"Found {len(stories)} stories matching query: '{query}'")
        return stories

    @staticmethod
    def extract_story_id_from_url(url: str) -> Optional[str]:
        """
        Extract Reddit story ID from a URL.
        
        Args:
            url: Reddit URL (e.g., https://www.reddit.com/r/AskReddit/comments/abc123/...)
            
        Returns:
            Story ID or None if not found
        """
        import re
        
        # Common Reddit URL patterns
        patterns = [
            r'reddit\.com/r/\w+/comments/([a-z0-9]+)/',  # Standard URL
            r'redd\.it/([a-z0-9]+)',  # Short URL
            r'/comments/([a-z0-9]+)/',  # Path only
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None

    async def fetch_story_from_url(self, url: str) -> Optional[RedditStory]:
        """
        Fetch a Reddit story from a URL.
        
        Args:
            url: Reddit story URL
            
        Returns:
            RedditStory object or None if not found
        """
        # Extract story ID from URL
        story_id = self.extract_story_id_from_url(url)
        
        if not story_id:
            logger.error(f"Could not extract story ID from URL: {url}")
            return None
        
        # Fetch story by ID
        story = await self.fetch_story_by_id(story_id)
        
        if not story:
            logger.error(f"Failed to fetch story from URL: {url}")
            logger.error(f"Possible reasons: Post deleted/removed, not a text post, or Reddit rate limiting")
        
        return story


# Example usage and testing
async def example_usage():
    """Example usage of the RedditClient."""
    import os
    from dotenv import load_dotenv
    
    # Load environment variables
    load_dotenv()
    
    # Create client
    async with RedditClient() as client:
        # Fetch trending stories from AskReddit
        print("Fetching trending stories from r/AskReddit...")
        stories = await client.fetch_trending_stories(
            subreddit="AskReddit",
            time_filter="day",
            limit=3,
            min_score=100,
        )
        
        for i, story in enumerate(stories, 1):
            print(f"\n{'='*60}")
            print(f"Story {i}: {story.title}")
            print(f"Score: {story.score}, Words: {story.word_count}, Duration: {story.estimated_duration:.1f}s")
            print(f"Text preview: {story.text[:200]}...")
            print(f"URL: {story.url}")
        
        if stories:
            # Fetch a specific story by ID
            print(f"\n{'='*60}")
            print(f"Fetching specific story by ID: {stories[0].id}")
            specific_story = await client.fetch_story_by_id(stories[0].id)
            if specific_story:
                print(f"Found: {specific_story.title}")

if __name__ == "__main__":
    # Run example if executed directly
    asyncio.run(example_usage())
