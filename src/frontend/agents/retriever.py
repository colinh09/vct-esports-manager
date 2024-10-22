import os
from typing import Any, Dict, List
from multi_agent_orchestrator.retrievers import Retriever
import psycopg2
from dotenv import load_dotenv

class RDSRetrieverOptions:
    def __init__(self, database_url: str):
        self.database_url = database_url

class RDSRetriever(Retriever):
    def __init__(self, options: RDSRetrieverOptions):
        super().__init__(options)
        self.options = options
        
        # Load environment variables
        load_dotenv()
        
        # Get the database URL from environment variable
        self.database_url = os.getenv('RDS_DATABASE_URL', options.database_url)

        if not self.database_url:
            raise ValueError("RDS_DATABASE_URL is not set in the environment variables or options")

    async def retrieve(self, handle: str) -> List[Dict[str, Any]]:
        try:
            with psycopg2.connect(self.database_url) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT player_id FROM players WHERE handle = %s", (handle,))
                    result = cur.fetchone()
                    if result:
                        return [{"player_id": result[0]}]
                    else:
                        return []
        except Exception as e:
            raise Exception(f"Failed to retrieve: {str(e)}")

    async def retrieve_and_combine_results(self, handle: str) -> str:
        results = await self.retrieve(handle)
        if results:
            return f"Player ID: {results[0]['player_id']}"
        else:
            return "No player found with the given handle."

    async def retrieve_and_generate(self, handle: str) -> str:
        return await self.retrieve_and_combine_results(handle)

# Example usage:
# retriever = RDSRetriever(RDSRetrieverOptions(database_url="your_database_url_here"))
# result = await retriever.retrieve_and_combine_results("player_handle")
# print(result)