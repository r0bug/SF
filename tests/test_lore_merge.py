"""Merging several Lore Discovery summaries into one lore entry."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from web_search import SearchResult


def _summary(n):
    return {
        "title": f"Article {n}",
        "content": f"Fact {n} about Yak-eh-Mah.\n\nSource: https://ex.com/{n}",
        "category": "places",
        "source_url": f"https://ex.com/{n}",
    }


def _summarizer(reply):
    from lore_summarizer import LoreSummarizer
    with patch("lore_summarizer.Anthropic"):
        s = LoreSummarizer(api_key="k", model="m")
    s.client = MagicMock()
    s.client.messages.create.return_value = SimpleNamespace(
        content=[SimpleNamespace(type="text", text=reply)])
    return s


# ---------------------------------------------------------------------------
# LoreSummarizer.merge
# ---------------------------------------------------------------------------

def test_merge_parses_title_and_lists_sources():
    s = _summarizer("TITLE: Second Street History\n\nCombined facts.")
    merged = s.merge([_summary(1), _summary(2), _summary(1)],
                     category="places", title_hint="second street")

    assert merged["title"] == "Second Street History"
    assert merged["content"].startswith("Combined facts.")
    assert merged["source_urls"] == ["https://ex.com/1", "https://ex.com/2"]
    assert merged["content"].endswith("- https://ex.com/1\n- https://ex.com/2")
    assert merged["merged_count"] == 3
    assert merged["category"] == "places"

    prompt = s.client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "Research topic: second street" in prompt
    assert "Fact 2 about Yak-eh-Mah." in prompt
    assert "Source: https://ex.com/2" not in prompt  # per-summary footer stripped


def test_merge_without_title_line_uses_hint():
    s = _summarizer("Just the merged text.")
    merged = s.merge([_summary(1), _summary(2)], title_hint="Lotus Room")
    assert merged["title"] == "Lotus Room"
    assert merged["content"].startswith("Just the merged text.")


def test_merge_needs_two():
    s = _summarizer("x")
    with pytest.raises(ValueError):
        s.merge([_summary(1)])


# ---------------------------------------------------------------------------
# LoreDiscoveryTab merge UI
# ---------------------------------------------------------------------------

@pytest.fixture
def tab(qt_app, temp_db):
    from tabs.lore_discovery import LoreDiscoveryTab
    t = LoreDiscoveryTab(temp_db)
    t._on_search_results([SearchResult(title=f"R{i}", url=f"https://ex.com/{i}",
                                       snippet="s") for i in range(3)])
    return t


def test_merge_mode_shows_only_merged_card(tab):
    tab._merge_mode = True
    tab._on_item_complete(0, _summary(1))
    tab._on_item_complete(1, _summary(2))
    assert tab._summary_cards == []

    tab._on_merged({**_summary(9), "title": "Merged", "merged_count": 2,
                    "source_urls": ["https://ex.com/1", "https://ex.com/2"]})
    tab._on_all_complete()

    assert [c.get_data()["title"] for c in tab._summary_cards] == ["Merged"]
    assert "Merged from 2 sources" in tab._summary_cards[0].merge_checkbox.text()


@patch("tabs.lore_discovery.QMessageBox")
def test_merge_failure_falls_back_to_individual_cards(_mb, tab):
    tab._merge_mode = True
    tab._on_item_complete(0, _summary(1))
    tab._on_item_complete(1, _summary(2))
    tab._on_merge_error("boom")
    assert len(tab._summary_cards) == 2


def test_merge_selected_button_needs_two_checked(tab):
    for n in (1, 2, 3):
        tab._add_summary_card(_summary(n))
    assert not tab.merge_selected_btn.isEnabled()

    tab._summary_cards[0].merge_checkbox.setChecked(True)
    assert not tab.merge_selected_btn.isEnabled()
    tab._summary_cards[2].merge_checkbox.setChecked(True)
    assert tab.merge_selected_btn.isEnabled()
    assert tab.merge_selected_btn.text() == "Merge 2 Summaries"


def test_merge_selected_sends_edited_summaries(tab, temp_db):
    temp_db.set_config("api_key", "k")
    for n in (1, 2, 3):
        tab._add_summary_card(_summary(n))
    tab._summary_cards[0].content_edit.setPlainText("Edited fact 1")
    tab._summary_cards[0].merge_checkbox.setChecked(True)
    tab._summary_cards[1].merge_checkbox.setChecked(True)

    with patch("tabs.lore_discovery.MergeWorker") as mw:
        tab._on_merge_selected()
    sent = mw.call_args.kwargs["summaries"]
    assert [s["content"] for s in sent][0] == "Edited fact 1"
    assert len(sent) == 2

    tab._on_merge_selected_done({**_summary(9), "title": "Merged", "merged_count": 2})
    assert tab._summary_cards[0].get_data()["title"] == "Merged"
    assert not any(c.merge_checkbox.isChecked() for c in tab._summary_cards)


@patch("tabs.lore_discovery.QMessageBox")
def test_summarize_and_merge_needs_two_results(_mb, tab):
    tab._result_rows[0].checkbox.setChecked(True)
    with patch("tabs.lore_discovery.SummarizeWorker") as sw:
        tab._on_summarize(merge=True)
    sw.assert_not_called()
