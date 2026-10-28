"""Packaging, licence, and attribution. A release must not miss these."""

import json
import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
LINKEDIN = "https://www.linkedin.com/in/raphaelmansuy/"


def _project() -> dict:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)["project"]


def test_licence_files_exist():
    licence = ROOT / "LICENSE"
    assert licence.exists()
    text = licence.read_text()
    assert "Apache License" in text
    assert "Version 2.0" in text
    assert "Copyright [yyyy] [name of copyright owner]" in text


def test_notice_names_author_and_sqlglot():
    notice = (ROOT / "NOTICE").read_text()
    assert "Raphael Mansuy" in notice
    assert "Apache License, Version 2.0" in notice
    assert LINKEDIN in notice
    assert "SQLGlot" in notice
    assert "MIT" in notice


def test_metadata_is_publishable():
    project = _project()
    assert project["name"] == "edgesql"
    assert project["license"] == "Apache-2.0"
    assert project["license-files"] == ["LICENSE", "NOTICE"]
    assert project["readme"] == "README.md"
    assert project["dependencies"] == ["sqlglot==30.25.0"]
    assert project["authors"][0]["name"] == "Raphael Mansuy"
    assert project["urls"]["Author"] == LINKEDIN
    assert project["urls"]["Documentation"].startswith("https://")
    assert "py.typed" not in project.get("classifiers", [])
    assert re.fullmatch(r"\d+\.\d+\.\d+", project["version"])


def test_no_licence_classifier_when_using_an_expression():
    # setuptools refuses both a licence expression and a licence classifier.
    classifiers = _project()["classifiers"]
    assert not [item for item in classifiers if item.startswith("License ::")]


def test_typed_package_marker_exists():
    assert (ROOT / "edgesql" / "py.typed").exists()


def test_changelog_has_the_current_version():
    version = _project()["version"]
    changelog = (ROOT / "CHANGELOG.md").read_text()
    assert f"## [{version}]" in changelog
    assert "Keep a Changelog" in changelog


def test_readme_has_install_and_author():
    readme = (ROOT / "README.md").read_text()
    assert "pip install edgesql" in readme
    assert LINKEDIN in readme
    assert "Apache License" in readme
    assert "docs/assets/raphael-mansuy.jpg" in readme


def test_workflows_exist():
    publish = (ROOT / ".github" / "workflows" / "publish.yml").read_text()
    pages = (ROOT / ".github" / "workflows" / "pages.yml").read_text()
    assert "pypa/gh-action-pypi-publish" in publish
    assert "id-token: write" in publish
    assert "twine check" in publish
    # The upload job stays off until a trusted publisher and a new version exist.
    assert "vars.PUBLISH_ENABLED == 'true'" in publish
    assert "upload-pages-artifact" in pages
    assert "path: docs" in pages


def test_publishing_guide_exists():
    guide = ROOT / "docs" / "PUBLISHING.md"
    assert guide.exists()
    text = guide.read_text()
    for step in ("trusted publisher", "make release-check", "make publish"):
        assert step in text


def test_readme_documents_pypi_and_uv():
    readme = (ROOT / "README.md").read_text()
    assert "pip install edgesql" in readme
    assert "uv add edgesql" in readme
    assert "uv pip install edgesql" in readme
    assert "https://pypi.org/project/edgesql/" in readme


def test_readme_links_the_other_projects():
    readme = (ROOT / "README.md").read_text()
    for url in (
        "https://edgequake.com/",
        "https://www.edgecrab.com/",
        "https://edgewhisper.com/",
        "https://www.oreilly.com/library/view/the-definitive-guide/9781837631919/",
        "https://www.favikon.com/blog/top-ai-experts-france",
    ):
        assert url in readme, url
    for image in (
        "docs/assets/projects/edgequake.jpg",
        "docs/assets/projects/edgecrab.jpg",
        "docs/assets/projects/edgewhisper.jpg",
        "docs/assets/book/definitive-guide-data-integration.jpg",
    ):
        assert image in readme, image
        assert (ROOT / image).exists(), image
    assert "12" in readme
    assert "7,012" in readme


@pytest.mark.parametrize("page", ["index.html", "tutorial.html", "examples.html", "reference.html"])
def test_site_links_the_other_projects(page):
    text = (ROOT / "docs" / page).read_text()
    for url in (
        "https://edgequake.com/",
        "https://www.edgecrab.com/",
        "https://edgewhisper.com/",
        "https://www.oreilly.com/library/view/the-definitive-guide/9781837631919/",
        "https://www.favikon.com/blog/top-ai-experts-france",
        "https://pypi.org/project/edgesql/",
    ):
        assert url in text, (page, url)
    for image in (
        "assets/projects/edgequake.jpg",
        "assets/projects/edgecrab.jpg",
        "assets/projects/edgewhisper.jpg",
        "assets/book/definitive-guide-data-integration.jpg",
    ):
        assert image in text, (page, image)


def test_project_and_book_images_are_real():
    for name in (
        "docs/assets/projects/edgequake.jpg",
        "docs/assets/projects/edgecrab.jpg",
        "docs/assets/projects/edgewhisper.jpg",
        "docs/assets/book/definitive-guide-data-integration.jpg",
    ):
        path = ROOT / name
        assert path.stat().st_size > 20_000, name
        assert path.read_bytes()[:3] == b"\xff\xd8\xff", name


@pytest.mark.parametrize("page", ["index.html", "tutorial.html", "examples.html", "reference.html"])
def test_site_has_author_and_licence(page):
    text = (ROOT / "docs" / page).read_text()
    assert "raphael-mansuy.jpg" in text
    assert LINKEDIN in text
    assert "Apache License, Version 2.0" in text
    assert 'class="cta-band"' in text


@pytest.mark.parametrize("page", ["index.html", "tutorial.html", "examples.html", "reference.html"])
def test_page_has_search_metadata(page):
    text = (ROOT / "docs" / page).read_text()
    assert 'name="description"' in text
    assert 'name="author" content="Raphael Mansuy"' in text
    assert 'name="keywords"' in text
    assert 'rel="canonical" href="https://raphaelmansuy.github.io/EdgeSQL/' in text
    assert 'property="og:title"' in text
    assert 'property="og:image"' in text
    assert 'name="twitter:card"' in text
    assert "application/ld+json" in text
    # One canonical and one description per page.
    assert text.count('rel="canonical"') == 1
    assert text.count('name="description"') == 1


def test_structured_data_is_valid_json():
    text = (ROOT / "docs" / "index.html").read_text()
    match = re.search(r'<script type="application/ld\+json">(.*?)</script>', text, re.DOTALL)
    assert match
    data = json.loads(match.group(1))
    kinds = {node["@type"] for node in data["@graph"]}
    assert {"SoftwareSourceCode", "Person"} <= kinds
    software = next(node for node in data["@graph"] if node["@type"] == "SoftwareSourceCode")
    assert software["license"] == "https://www.apache.org/licenses/LICENSE-2.0"
    assert software["author"]["url"] == LINKEDIN


def test_sitemap_and_robots():
    sitemap = (ROOT / "docs" / "sitemap.xml").read_text()
    robots = (ROOT / "docs" / "robots.txt").read_text()
    for path in ("", "tutorial.html", "examples.html", "reference.html"):
        assert f"https://raphaelmansuy.github.io/EdgeSQL/{path}" in sitemap
    assert "Sitemap: https://raphaelmansuy.github.io/EdgeSQL/sitemap.xml" in robots


def test_author_photo_is_published():
    photo = ROOT / "docs" / "assets" / "raphael-mansuy.jpg"
    assert photo.exists()
    assert photo.stat().st_size > 2000
