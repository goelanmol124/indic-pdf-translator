import pytest

from indic_pdf_translator.layout import chunk_layout, split_pages, stitch


def test_split_preserves_every_element_once():
    layouts = [list("abcdef"), list("gh"), list("ijklm")]
    splits = split_pages(layouts, overlap=2)
    for layout, s in zip(layouts, splits):
        assert s.head + s.body + s.tail == layout
    assert splits[0].head == [] and splits[-1].tail == []
    # Short middle page: everything goes to the head, nothing reused as tail.
    assert splits[1].head == ["g", "h"] and splits[1].tail == []


def test_stitch_with_identity_merge_is_lossless():
    layouts = [list("abcdef"), list("ghij"), list("klm")]
    splits = split_pages(layouts, overlap=2)
    merged = [splits[i].tail + splits[i + 1].head for i in range(len(splits) - 1)]
    assert stitch(splits, merged) == list("abcdefghijklm")


def test_stitch_single_page():
    splits = split_pages([["x", "y"]], overlap=3)
    assert stitch(splits, []) == ["x", "y"]


def test_stitch_rejects_wrong_boundary_count():
    splits = split_pages([["a"], ["b"]], overlap=1)
    with pytest.raises(ValueError):
        stitch(splits, [])


def test_chunk_layout_groups_by_size():
    layout = ["x" * 400] * 5 + ["short"]
    chunks = chunk_layout(layout, max_tokens=200)
    assert [len(c) for c in chunks] == [2, 2, 2]
    assert sum(chunks, []) == layout
    assert chunk_layout([], 100) == []
