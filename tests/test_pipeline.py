import json

from indic_pdf_translator import Options, translate_pdf
from indic_pdf_translator.cli import main
from indic_pdf_translator.pdf import load_pages
from indic_pdf_translator.providers import MockProvider


def test_load_pages_reads_text_layer_and_tables(sample_pdf):
    pages = load_pages(str(sample_pdf), dpi=72)
    assert len(pages) == 2
    assert pages[0].image.size[0] > 0
    assert "DISTRICT COURT" in pages[0].text
    tables = [b for b in pages[1].blocks if b.rows]
    assert tables and tables[0].rows[0] == ["Item", "Description", "Amount"]
    assert tables[0].rows[1][1] == "Application fee"


def test_end_to_end_mock_hindi(sample_pdf):
    result = translate_pdf(sample_pdf, "mock", Options(target="hi", dpi=72))
    assert result.page_count == 2
    assert not result.warnings
    src = result.source_layout
    # The paragraph split across the page break is merged into one element.
    joined = [e for e in src if "merge step of the translation pipeline" in e]
    assert len(joined) == 1
    # Page numbers are dropped; nothing is duplicated.
    assert not any(e.strip() in ("<div>Page 1</div>", "<div>Page 2</div>") for e in src)
    assert len(src) == len(set(src))
    # Structure is preserved through translation.
    assert len(result.translated_layout) == len(src)
    assert any("<table>" in e for e in result.translated_layout)
    assert "न्यायालय" in result.html and "रुपये" in result.html
    assert '<html lang="hi">' in result.html


def test_end_to_end_mock_other_target(sample_pdf):
    result = translate_pdf(str(sample_pdf), MockProvider(), Options(target="ta", dpi=72))
    assert "[ta] ORDER" in result.html


def test_cli_writes_outputs(sample_pdf, tmp_path, capsys):
    out = tmp_path / "out.html"
    inter = tmp_path / "debug"
    rc = main([str(sample_pdf), "-o", str(out), "-t", "hi", "--dpi", "72", "-p", "mock",
               "--save-intermediate", str(inter)])
    assert rc == 0
    assert "न्यायालय" in out.read_text(encoding="utf-8")
    data = json.loads((inter / "intermediate.json").read_text(encoding="utf-8"))
    assert data["page_count"] == 2
    assert "HTML written" in capsys.readouterr().out


def test_cli_missing_file(tmp_path):
    assert main([str(tmp_path / "nope.pdf")]) == 2
