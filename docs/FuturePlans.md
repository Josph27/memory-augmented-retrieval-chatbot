# Possible future directions:

(Where I'd like to take this project if I had free time)

## Containerization:

    - put it in docker. Reliable and easy to operate and start the app.

## Document handling:

    - allow for global document sharing betwee chats
    - allow to turn off document or groups of document for specific chats.
    - allow to specify documents or groups of documents as increased relevance for current chat / group of chats.
    - add response chunk <--> document tracking & extended stats.

## Docs & Memories synergy:

    - make it possible for memories to point to associated documents and chunks, also adding those to context whenever the memory is retrieved.

## Add chat folders / groups / tags.

    - something to oraganize the chats.

## Add workspaces:

    -> scope long term memory not globally, but based
        -> Tags? / Fully disjunct workspace.

## Add workspace oracle:

    -> single turn chat without any short term memory (useful for retrieving specifc information from knowledge bases)
    -> add "verify online" feature that allows agent web-searech.

## Advanced settings features:

    - Build massive settings page system for easy and simple customization:
        -> prompts, models (hugging face links), ... basically everything present in settings.
        -> correct restrictions on settings.
        -> robust error handling,
            -> error origin tracking
            -> reverting to previous / default states in case something breaks.

## Obsidian integration:

    -> obsidian's structure allows it to serve as great knowledge base, optimize system to work with such knowledge bases.
    -> Obsydian graph rag retrieval.
