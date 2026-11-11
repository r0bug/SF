"""Yakima must be sung one way: every spelling becomes Yak-eh-Mah."""

from lyrics_rules import apply_pronunciation


def test_names_and_possessives():
    src = ("Where the Yakima River rolls on by\n"
           "Walking through Yakima Finds' front door\n"
           "Yakima's where my story begins\n"
           "Yak-eh-Mah, you're the heart of me")
    out = apply_pronunciation(src)
    assert "Yakima" not in out
    assert "Yak-eh-Mah River" in out
    assert "Yak-eh-Mah Finds' front door" in out
    assert "Yak-eh-Mah's where" in out
    assert out.endswith("Yak-eh-Mah, you're the heart of me")


def test_case_is_kept():
    assert apply_pronunciation("YAKIMA! yakima") == "YAK-EH-MAH! yak-eh-mah"


def test_empty():
    assert apply_pronunciation("") == ""


def test_generator_output_is_fixed():
    from api_client import SongGenerator
    raw = ('{"title": "T", "genre_label": "G", "prompt": "p", '
           '"lyrics": "Down at Yakima Finds"}')
    assert SongGenerator._parse_response(raw)["lyrics"] == "Down at Yak-eh-Mah Finds"
