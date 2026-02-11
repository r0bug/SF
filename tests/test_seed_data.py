"""Tests for seed data integrity."""


def test_all_seed_songs_have_matching_genre():
    """S-005: Every song in SEED_SONGS must map to a genre in SEED_GENRES."""
    from seed_data import SEED_GENRES, SEED_SONGS

    genre_names_upper = {g["name"].upper() for g in SEED_GENRES}

    unmatched = []
    for song in SEED_SONGS:
        label = song.get("genre_label", "").upper()
        found = any(gname in label for gname in genre_names_upper)
        if not found:
            unmatched.append((song["title"], song["genre_label"]))

    assert unmatched == [], f"Songs with no matching genre: {unmatched}"


def test_seed_genres_count():
    from seed_data import SEED_GENRES
    assert len(SEED_GENRES) == 25


def test_seed_songs_count():
    from seed_data import SEED_SONGS
    assert len(SEED_SONGS) == 29


def test_seed_lore_count():
    from seed_data import SEED_LORE
    assert len(SEED_LORE) >= 16


def test_seed_genres_have_required_fields():
    from seed_data import SEED_GENRES
    for genre in SEED_GENRES:
        assert "name" in genre, f"Genre missing name: {genre}"
        assert "prompt_template" in genre, f"Genre missing prompt_template: {genre}"
        assert len(genre["name"]) > 0
        assert len(genre["prompt_template"]) > 0


def test_seed_songs_have_required_fields():
    from seed_data import SEED_SONGS
    for song in SEED_SONGS:
        assert "title" in song, f"Song missing title"
        assert "genre_label" in song, f"Song missing genre_label: {song.get('title')}"
        assert "prompt" in song, f"Song missing prompt: {song.get('title')}"
        assert "lyrics" in song, f"Song missing lyrics: {song.get('title')}"
        assert len(song["title"]) > 0
        assert len(song["prompt"]) > 0
        assert len(song["lyrics"]) > 0


def test_seed_prompt_length():
    """Prompts should be <= 300 chars per Yakima Finds rules."""
    from seed_data import SEED_SONGS
    over_limit = [
        (s["title"], len(s["prompt"]))
        for s in SEED_SONGS
        if len(s["prompt"]) > 300
    ]
    assert over_limit == [], f"Songs with prompt > 300 chars: {over_limit}"


def test_all_seed_songs_resolve_to_genre_id(seeded_db):
    """In a seeded database, every song should have a non-NULL genre_id."""
    songs = seeded_db.get_all_songs()
    null_genre = [(s["title"], s["genre_label"]) for s in songs if s["genre_id"] is None]
    assert null_genre == [], f"Songs with NULL genre_id: {null_genre}"
