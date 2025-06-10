from typing import List, Optional

from langchain.tools import Tool
from langchain.tools.tavily_search import TavilySearchResults
from loguru import logger


class WebsiteSearchTool:
    def __init__(self, preferred_websites: Optional[List[str]] = None):
        self.preferred_websites = preferred_websites or [
            "service-public.fr",
            "legifrance.gouv.fr",
            "ants.gouv.fr",
            "info.gouv.fr",
        ]
        self.search = TavilySearchResults(
            max_results=5,
            include_domains=self.preferred_websites,
        )

    def search_web(self, query: str) -> str:
        """Search the web and return the most relevant results from preferred websites."""
        try:
            results = self.search.run(query)

            if not results:
                logger.warning("No results found")
                return "SEARCH_FAILED"

            # Extract URLs from results
            urls = [result.get("url", "") for result in results if result.get("url")]

            if urls:
                logger.info(f"Found {len(urls)} URLs: {urls}")
                return "\n".join(urls)

            return "SEARCH_FAILED"

        except Exception as e:
            logger.error(f"Error during web search: {str(e)}")
            return "SEARCH_FAILED"

    def get_tool(self) -> Tool:
        """Return the search tool for use in the agent."""
        return Tool(
            name="web_search",
            description="""Search the web for information, focusing on French government websites.
            If the search fails (returns 'SEARCH_FAILED'), you should provide an answer based on your knowledge,
            but include a disclaimer that the information should be verified as it comes from your training data
            and not from current official sources. DO NOT include any source URLs when the search fails.""",
            func=self.search_web,
        )
