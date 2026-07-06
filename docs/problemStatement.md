# AI-Powered Review Discovery Engine for Spotify

## Objective

Build an AI-powered review discovery engine for Spotify that analyzes large-scale user feedback to understand why users struggle with music discovery and recommendation quality. The system should identify recurring frustrations, repeated listening patterns, unmet needs, and user-segment-specific discovery challenges by combining structured reviews and social feedback with a Large Language Model (LLM) utilizing Gemini as the primary engine and Groq as the backup/support engine.

## Data Sources

The system uses three structured and unstructured data sources, split into primary and secondary priority levels:

### Primary Source (High Priority)
1. **Merged CSV File**: App Store and Google Play Store reviews for the Spotify app. This represents the primary, direct feedback channel.

### Secondary Sources (Medium Priority)
2. **Product Hunt API**: Reviews, posts, and comments for the Spotify product on Product Hunt (using the product slug **`spotify`** for identification and retrieval).
3. **YouTube Data API**: Video metadata and comments retrieved via keyword-based search queries related to Spotify's discovery, recommendations, and listening experience.

## Core Questions

The system helps answer the following questions:

- Why do users struggle to discover new music on Spotify?
- What are the most common frustrations with recommendations?
- What listening behaviors are users trying to achieve?
- What causes users to repeatedly listen to the same content?
- Which user segments experience different discovery challenges?
- What unmet needs emerge consistently across user feedback?

## System Workflow

### 1. Data Ingestion

Load and preprocess data from:
- Merged Spotify App Store and Play Store reviews CSV.
- Product Hunt API (using slug-based lookup).
- YouTube Data API (using keyword search).

Extract or preserve fields such as:
- review, post, or comment text
- rating or score (e.g., star rating, Product Hunt votes, YouTube comment likes)
- title
- author or username
- source platform (app_store, play_store, product_hunt, youtube)
- review, post, or comment date
- app version (app reviews only)
- product slug (Product Hunt only)
- video ID and search query (YouTube only)
- URL or external link

### 2. User Input / Exploration

Allow the user to explore the feedback intelligence system using filters:
- source type
- platform
- sentiment
- issue category
- topic/theme
- date range
- user segment

### 3. Integration Layer

Normalize the primary CSV reviews and secondary Product Hunt & YouTube data into a common schema so they can be analyzed together. The system supports source-specific filtering while enabling cross-source comparison (comparing App reviews vs. Product Hunt vs. YouTube).

### 4. AI-Powered Analysis

Use AI/LLM-based analysis (Gemini as primary, Groq as fallback/support) to:
- detect recurring themes
- classify complaints
- infer user goals and listening intent
- identify repeated listening loop causes
- detect unmet needs
- summarize evidence from feedback sources
- compare app store reviews vs. Product Hunt posts vs. YouTube comment narratives

### 5. Output Display

Present results in a dashboard format:
- top issue categories
- recurring discovery pain points
- recommendation frustrations
- listening behavior insights
- user segments and their challenges
- unmet needs
- AI-generated explanations
- supporting review, post, or comment snippets

## Expected Deliverable

Build a working prototype including:
- a CSV ingestion pipeline
- Product Hunt API and YouTube Data API connectors
- a preprocessing and normalization layer
- an AI/LLM-based analysis engine (Gemini primary, Groq fallback)
- a dashboard/UI for exploring insights
- structured outputs useful for product management decision-making

## Scope Constraint

The broader review discovery problem may include additional public feedback sources such as community forums and general social media conversations. However, for this implementation, the project uses the three sources currently defined:

- merged Spotify review CSV (Primary)
- Product Hunt API (Secondary, slug-based)
- YouTube Data API (Secondary, keyword-based)

These sources are analyzed and compared to surface a comprehensive view of the Spotify user experience, prioritizing the direct feedback from the App Store and Google Play Store CSV data.