from indic_pdf_translator.htmltext import map_text, strip_tags
from indic_pdf_translator.languages import detect_script, language_name
from indic_pdf_translator.render import build_html


def test_map_text_keeps_tags_and_attributes():
    src = '<div style="text-align:center"><b>Hello</b> world <span class="doubtful">x</span></div>'
    out = map_text(src, str.upper)
    assert out == '<div style="text-align:center"><b>HELLO</b> WORLD <span class="doubtful">X</span></div>'


def test_map_text_escapes_output():
    assert map_text("<p>a</p>", lambda t: "<b>") == "<p>&lt;b&gt;</p>"


def test_strip_tags():
    assert strip_tags("<div>Page <b>2</b></div>") == "Page 2"


def test_detect_script():
    assert detect_script("न्यायालय") == "devanagari"
    assert detect_script("நீதிமன்றம்") == "tamil"
    assert detect_script("plain English") is None
    assert language_name("hi") == "Hindi"
    assert language_name("xx") == "xx"


def test_build_html_decorates_elements():
    doc = build_html(["<div>IN THE HIGH COURT</div>", "<table><tr><td>1</td></tr></table>", "<div>आदेश</div>"],
                     lang="hi")
    assert doc.startswith("<!DOCTYPE html>")
    assert '<html lang="hi">' in doc
    assert '<div class="heading"><div>IN THE HIGH COURT</div></div>' in doc
    assert '<div class="table-container"><table>' in doc
    assert '<div class="devanagari"><div>आदेश</div></div>' in doc
    assert "Noto+Sans+Devanagari" in doc
