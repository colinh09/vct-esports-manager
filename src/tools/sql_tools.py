from langchain.tools import StructuredTool
from backend.queries.player_info import PlayerInfoQueries

player_info_instance = PlayerInfoQueries()

fetch_player_info_by_handle_tool = StructuredTool.from_function(
    func=player_info_instance.get_player_info_by_handle,
    name="FetchPlayerInfoByHandle",
    description="Fetches player information based on the player's handle. A handle is a nickname players used within a game.",
)

fetch_player_info_by_name_tool = StructuredTool.from_function(
    func=player_info_instance.get_player_info_by_name,
    name="FetchPlayerInfoByName",
    description="Fetches player information based on the player's first and last name. Call this when prompted about a player and their first name and last name is used.",
)

tools = [fetch_player_info_by_handle_tool, fetch_player_info_by_name_tool]