import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium


# --------------------------------------------------------------------------------------
# Basic settings
# --------------------------------------------------------------------------------------
st.set_page_config(
    page_title="Movies Success Dashboard",
    page_icon="🎬",
    layout="wide",
)

st.title("🎬 What Makes Movies Successful?")
st.write(
    """
This dashboard explores how **location, genre, year, and budget** relate to **movie success**,  
where *success* is defined as the **IMDB average rating**.
Use the filters on the left to interactively explore the data.
"""
)


# --------------------------------------------------------------------------------------
# Load & preprocess data (movies_with_coords.csv)
# --------------------------------------------------------------------------------------
@st.cache_data
def load_data():
    df = pd.read_csv("movies_with_coords.csv")

    # startYear, averageRating, budget, numVotes, lat, lon, genres, title
    df["startYear"] = pd.to_numeric(df["startYear"], errors="coerce")
    df["averageRating"] = pd.to_numeric(df["averageRating"], errors="coerce")
    df["budget"] = pd.to_numeric(df["budget"], errors="coerce")
    df["numVotes"] = pd.to_numeric(df["numVotes"], errors="coerce")
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")

    df["genres"] = df["genres"].fillna("\\N")
    df["genres"] = df["genres"].replace("\\N", np.nan)

    return df


df = load_data()

# --------------------------------------------------------------------------------------
# Sidebar Filters
# --------------------------------------------------------------------------------------
st.sidebar.header("Filters")

# 1) Year range slider
valid_years = df["startYear"].dropna()
if not valid_years.empty:
    min_year = int(valid_years.min())
    max_year = int(valid_years.max())
else:
    min_year, max_year = 1900, 2025

years = st.sidebar.slider(
    "Release Year",
    min_value=min_year,
    max_value=max_year,
    value=(max(min_year, 2000), max_year),
)

# 2) Genre multiselect
genres_list = (
    df["genres"]
    .dropna()
    .unique()
    .tolist()
)
genres_list = sorted(genres_list)

if genres_list:
    default_genres = [x for x in genres_list if x in ['Action', 'Comedy', 'Drama']]
    selected_genres = st.sidebar.multiselect(
        "Genres",
        options=genres_list,
        default=default_genres,
    )
else:
    selected_genres = []

# 3) Budget slider
budget_valid = df["budget"].dropna() 
if not budget_valid.empty: 
    b_min, b_max = budget_valid.quantile([0.05, 0.95]) 
    b_min = float(b_min) 
    b_max = float(b_max) 
else: 
    b_min, b_max = 0.0, float(budget_valid.max()) if not budget_valid.empty else 1.0

budget_range = st.sidebar.slider("Budget (USD approx. 5% ~ 95% range)",
                                 min_value=float(b_min), max_value=float(b_max),
                                 value=(float(b_min), float(b_max)),
                                )

# 4) Rating slider (success metric)
ratings_valid = df["averageRating"].dropna()
if not ratings_valid.empty:
    min_rating = float(ratings_valid.min())
    max_rating = float(ratings_valid.max())
else:
    min_rating, max_rating = 0.0, 10.0

rating_range = st.sidebar.slider(
    "Average Rating (Success Metric)",
    min_value=float(np.floor(min_rating)),
    max_value=float(np.ceil(max_rating)),
    value=(max(0.0, float(np.floor(min_rating))), float(np.ceil(max_rating))),
    step=0.1,
)

st.sidebar.caption("Success is defined as the **IMDB average rating**.")

# --------------------------------------------------------------------------------------
# Apply filters
# --------------------------------------------------------------------------------------
df_filtered = df.copy()

# Year filter
df_filtered = df_filtered[df_filtered["startYear"].between(years[0], years[1])]

# Genre filter
if selected_genres:
    df_filtered = df_filtered[df_filtered["genres"].isin(selected_genres)]

# Rating filter
df_filtered = df_filtered[
    df_filtered["averageRating"].between(rating_range[0], rating_range[1])
]

# Budget filter
df_filtered = df_filtered[
    df_filtered["budget"].between(budget_range[0], budget_range[1])
]

# --------------------------------------------------------------------------------------
# Tabs: Map / Trends / Data
# --------------------------------------------------------------------------------------
tab_map, tab_trends, tab_table = st.tabs(["🌍 Map", "📈 Trends", "📋 Data"])

# --------------------------------------------------------------------------------------
# 🌍 Tab 1: Folium Map
# --------------------------------------------------------------------------------------
with tab_map:
    st.subheader("Filming Locations and Movie Success (Average Rating)")

    df_map = df_filtered.dropna(subset=["lat", "lon"]).copy()

    if df_filtered.empty:
        st.info("No data for the selected filters.")
    elif df_map.empty:
        st.info("No movies with valid latitude/longitude after filtering.")
    else:
        center_lat = df_map["lat"].mean()
        center_lon = df_map["lon"].mean()

        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=2,
            tiles=None,
            prefer_canvas=True,
            no_wrap=True,
        )
        folium.TileLayer(
            "cartodbpositron",
            name="BaseMap",
            control=False,
            no_wrap=True,
        ).add_to(m)

        cluster = MarkerCluster(
            name="Filming Locations",
            disableClusteringAtZoom=5,
        ).add_to(m)

        for _, row in df_map.iterrows():
            title = row["title"]
            year = int(row["startYear"]) if not pd.isna(row["startYear"]) else "N/A"
            genre = row["genres"] if not pd.isna(row["genres"]) else "N/A"
            rating = round(row["averageRating"], 2) if not pd.isna(row["averageRating"]) else "N/A"
            budget = int(row["budget"]) if not pd.isna(row["budget"]) else "N/A"

            popup_lines = [
                f"<b>{title}</b>",
                f"Year: {year}",
                f"Genre: {genre}",
                f"Rating: {rating}",
                f"Budget: {budget:,}" if budget != "N/A" else "Budget: N/A",
            ]
            popup_html = "<br>".join(popup_lines)

            folium.Marker(
                location=[row["lat"], row["lon"]],
                popup=popup_html,
                tooltip=title,
            ).add_to(cluster)

        folium.LayerControl(collapsed=False).add_to(m)

        st_folium(m, width=1100, height=600)

# --------------------------------------------------------------------------------------
# 📈 Tab 2: Trends (Rating by Year/Genre + Budget vs Rating)
# --------------------------------------------------------------------------------------
with tab_trends:
    st.subheader("Trends of Average Rating and Budget Relationship")

    if df_filtered.empty:
        st.info("No data for the selected filters.")
    else:
        col1, col2 = st.columns(2)

        # (1) Year–Genre Rating Trend
        with col1:
            st.markdown("**Average Rating by Year and Genre**")

            df_group = (
                df_filtered
                .dropna(subset=["startYear", "genres", "averageRating"])
                .groupby(["startYear", "genres"], as_index=False)["averageRating"]
                .mean()
                .rename(columns={"startYear": "year", "averageRating": "avg_rating"})
            )

            if df_group.empty:
                st.info("No grouped data to display trends.")
            else:
                chart = (
                    alt.Chart(df_group)
                    .mark_line()
                    .encode(
                        x=alt.X("year:O", title="Year"),
                        y=alt.Y("avg_rating:Q", title="Average Rating"),
                        color=alt.Color("genres:N", title="Genre"),
                        tooltip=["year", "genres", "avg_rating"],
                    )
                    .properties(height=350)
                )
                st.altair_chart(chart, use_container_width=True)

        # (2) Budget vs Rating Scatter
        with col2:
            st.markdown("**Budget(USD) vs Average Rating**")

            df_scatter = df_filtered.dropna(subset=["budget", "averageRating"]).copy()

            if df_scatter.empty:
                st.info("No data with both budget and rating.")
            else:
                chart2 = (
                    alt.Chart(df_scatter)
                    .mark_circle(size=60, opacity=0.65)
                    .encode(
                        x=alt.X(
                            "budget:Q",
                            title="Budget(USD)",
                            scale=alt.Scale(type="log", nice=True),
                        ),
                        y=alt.Y("averageRating:Q", title="Average Rating"),
                        color=alt.Color("genres:N", title="Genre", legend=None),
                        tooltip=["title", "startYear", "genres", "budget", "averageRating"],
                    )
                    .properties(height=350)
                )
                st.altair_chart(chart2, use_container_width=True)

# --------------------------------------------------------------------------------------
# 📋 Tab 3: Filtered Data Table
# --------------------------------------------------------------------------------------
with tab_table:
    st.subheader("Filtered Movies Data")

    if df_filtered.empty:
        st.info("No data for the selected filters.")
    else:
        columns_to_show = [
            "title",
            "startYear",
            "genres",
            "averageRating",
            "budget",
            "numVotes",
            "lat",
            "lon",
        ]

        df_display = df_filtered[columns_to_show].sort_values(
            by=["startYear","averageRating","budget","numVotes"], ascending=False, na_position="last"
        )

        st.dataframe(df_display, use_container_width=True)