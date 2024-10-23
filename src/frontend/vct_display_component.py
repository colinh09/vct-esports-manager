import streamlit as st
import json
from typing import Dict, Any
import pandas as pd

def parse_agent_response(content: str) -> Dict[Any, Any]:
    """Parse the agent's JSON response string into a dictionary."""
    try:
        # Find the JSON content within the string (in case there's other text)
        start_idx = content.find('{')
        end_idx = content.rfind('}') + 1
        if start_idx == -1 or end_idx == 0:
            raise ValueError("No JSON content found")
        
        json_content = content[start_idx:end_idx]
        return json.loads(json_content)
    except Exception as e:
        st.error(f"Error parsing response: {str(e)}")
        return None

def display_team_composition(team_data: Dict[str, Any]):
    """Display the team composition section."""
    st.header("Team Composition")
    
    # Create a DataFrame for better display
    players = pd.DataFrame(team_data["team_composition"]["players"])
    st.dataframe(
        players,
        column_config={
            col: st.column_config.TextColumn(col.replace("_", " ").title())
            for col in players.columns
        },
        hide_index=True
    )
    
    st.info(team_data["team_composition"]["constraint_satisfaction"])

def display_player_analysis(player: Dict[str, Any]):
    """Display analysis for a single player."""
    with st.expander(f"{player['player_info']['full_name']} ({player['player_info']['handle']})"):
        col1, col2 = st.columns([3, 2])
        
        with col1:
            st.subheader("Player Statistics")
            st.write(f"Total Games: {player['player_info']['total_games']}")
            
            # Preferred Agents
            st.write("**Preferred Agents:**")
            agents_df = pd.DataFrame(player["preferred_agents"])
            st.dataframe(agents_df, hide_index=True)
            
            # Selection Reasoning
            st.write("**Selection Reasoning:**")
            for reason in player["selection_reasoning"]:
                st.write(f"• {reason}")
        
        with col2:
            # Top Maps with Visualizations
            st.write("**Top Maps:**")
            for map_data in player["top_maps"]:
                with st.container():
                    st.write(f"**{map_data['map_name']}**")
                    st.write(f"Games: {map_data['games_played']} | KDA: {map_data['kda']}")
                    st.write(f"Preferred Site: {map_data['preferred_site']} ({map_data['site_percentage']}%)")
                    if map_data.get('visualization_url'):
                        st.image(map_data['visualization_url'], caption=f"{map_data['map_name']} Analysis")

def display_team_synopsis(synopsis: Dict[str, Any]):
    """Display the team synopsis section."""
    st.header("Team Synopsis")
    
    cols = st.columns(2)
    with cols[0]:
        st.subheader("Playstyle")
        st.write(synopsis["playstyle"])
        st.subheader("Map Coverage")
        st.write(synopsis["map_coverage"])
    
    with cols[1]:
        st.subheader("Team Synergies")
        st.write(synopsis["synergies"])
        st.subheader("Strategic Advantages")
        st.write(synopsis["strategic_advantages"])

def display_honorable_mentions(mentions: list):
    """Display the honorable mentions section."""
    st.header("Honorable Mentions")
    mentions_df = pd.DataFrame(mentions)
    st.dataframe(
        mentions_df,
        column_config={
            col: st.column_config.TextColumn(col.replace("_", " ").title())
            for col in mentions_df.columns
        },
        hide_index=True
    )

def display_vct_response(content: str):
    """Main function to display the VCT agent response."""
    parsed_data = parse_agent_response(content)
    if not parsed_data:
        st.markdown(content)  # Fallback to raw markdown if parsing fails
        return
    
    # Display each section
    display_team_composition(parsed_data)
    
    st.header("Player Analysis")
    for player in parsed_data["player_analysis"]:
        display_player_analysis(player)
    
    display_team_synopsis(parsed_data["team_synopsis"])
    display_honorable_mentions(parsed_data["honorable_mentions"])