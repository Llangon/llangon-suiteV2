import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
import unicodedata
from html import unescape
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlparse
from urllib.request import Request, urlopen

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover
    BeautifulSoup = None


USER_AGENT = "Mozilla/5.0 LlangonWebApp/Monitor"
TIMEOUT = 35

DOCUMENT_EXTENSIONS = {
    ".pdf", ".xml", ".html", ".htm", ".txt",
    ".doc", ".docx", ".xls", ".xlsx", ".xlsm",
    ".ppt", ".pptx", ".zip", ".rtf", ".csv", ".ods", ".odt",
}

DOCUMENT_HINTS = (
    "download",
    "descarga",
    "documento",
    "adjunto",
    "medias",
    "getdocument",
    "documentidparam",
    "print/pdf",
    "descarrega-document",
    "anuncio",
    "pliego",
    "pcap",
    "ppt",
    "deuc",
    "xml",
)

GENERIC_LINK_TEXT = {
    "",
    "descargar",
    "descarga",
    "pdf",
    "xml",
    "html",
    "ver",
    "abrir",
    "enlace",
    "documento",
    "descarga documento anuncio pdf",
    "este se abrira en una nueva ventana",
    "se abrira en una nueva ventana",
    "este enlace se abrira en una nueva ventana",
    "abre en nueva ventana",
    "opens in a new window",
    "deferred modules",
    "getdocumentbyidservlet",
    "getdocumentbyidservlet getdocumentbyidservlet",
}

DOCUMENT_DATE_RE = re.compile(
    r"(\d{1,2})/(\d{1,2})/(\d{2,4})(?:\s+(\d{1,2}):(\d{2}))?",
    re.IGNORECASE,
)


def clean_text(value):
    text = unescape(str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_text(value):
    text = unicodedata.normalize("NFD", clean_text(value))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", text).strip().lower()


def extension_from_url(url):
    path = unquote(urlparse(url).path).lower()
    match = re.search(r"(\.[a-z0-9]{2,5})$", path)
    if match and match.group(1) in DOCUMENT_EXTENSIONS:
        return match.group(1)
    return ""


def extension_from_text(text):
    normalized = normalize_text(text)
    for ext in DOCUMENT_EXTENSIONS:
        if ext.strip(".") in normalized.split():
            return ext
    if "pdf" in normalized:
        return ".pdf"
    if "xml" in normalized:
        return ".xml"
    return ""


def title_from_url(url):
    path = unquote(urlparse(url).path).strip("/")
    if not path:
        return "Documento"
    raw = path.rsplit("/", 1)[-1]
    if normalize_text(raw) in {"getdocumentbyidservlet", "servlet"}:
        return "Documento"
    raw = re.sub(r"\.[a-zA-Z0-9]{2,5}$", "", raw)
    raw = raw.replace("_", " ").replace("-", " ")
    return clean_text(raw).title() or "Documento"


def is_bad_document_title(text):
    normalized = normalize_text(text)
    if normalized in GENERIC_LINK_TEXT:
        return True
    if "getdocumentbyidservlet" in normalized:
        return True
    if "deferred modules" in normalized:
        return True
    if "se abrira en una nueva ventana" in normalized:
        return True
    if "abre en nueva ventana" in normalized:
        return True
    if "opens in a new window" in normalized:
        return True
    if normalized.startswith(("http ", "https ", "www ")):
        return True
    return False


def clean_context_title(text):
    title = clean_text(text)
    title = re.sub(r"\bAdvertisements and documents\b", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"\bPost on platform\b", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"\bVeure documents\b", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"\bEste\s+(?:enlace\s+)?se\s+abrir[aá]\s+en\s+una\s+nueva\s+ventana\b", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"\bSe\s+abrir[aá]\s+en\s+una\s+nueva\s+ventana\b", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"\bOpens\s+in\s+a\s+new\s+window\b", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"\b(Fecha|Importe|Descarga|Descargar|Documento)\b\s*:?", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"\b\d{1,2}/\d{1,2}/\d{2,4}(?:\s+\d{1,2}:\d{2})?\b", " ", title)
    title = re.sub(r"\b20\d{2}-\d+\b", " ", title)
    title = re.sub(r"\b(PDF|XML|HTML?)\b", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+", " ", title).strip(" .:-")
    if len(title) > 180:
        title = title[-180:].strip(" .:-")
    return title


def extract_document_date(text):
    match = DOCUMENT_DATE_RE.search(clean_text(text))
    if not match:
        return ""

    day = int(match.group(1))
    month = int(match.group(2))
    year = int(match.group(3))
    if year < 100:
        year += 2000

    if not (1 <= day <= 31 and 1 <= month <= 12):
        return ""

    hour = match.group(4)
    minute = match.group(5)
    if hour is not None and minute is not None:
        hour_i = int(hour)
        minute_i = int(minute)
        if 0 <= hour_i <= 23 and 0 <= minute_i <= 59:
            return f"{year:04d}-{month:02d}-{day:02d}T{hour_i:02d}:{minute_i:02d}:00"

    return f"{year:04d}-{month:02d}-{day:02d}"


def clean_junta_document_title(text, url=""):
    title = clean_text(text)
    title = re.sub(r"^\s*descarg(?:a|ue)\s+(?:el\s+)?", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"^\s*documento\s+anuncio\s+pdf\s*", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"^\s*\([^)]+\)\s*", " ", title)
    title = re.sub(r"\s*descarga\s+sello\s+de\s+tiempo.*$", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"\s*\(\s*activo\s*\)\s*\.?\s*$", " ", title, flags=re.IGNORECASE)
    title = DOCUMENT_DATE_RE.sub(" ", title)
    title = re.sub(r"\b20\d{2}-\d+\b", " ", title)
    title = re.sub(r"\(\s*\.?\s*(PDF|XML|HTML?)\s*\)", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"\.(PDF|XML|HTML?)\b", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"\b(PDF|XML|HTML?)\b", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+", " ", title).strip(" .:-,")

    if " - " in title:
        parts = [part.strip(" .:-,") for part in title.split(" - ") if part.strip(" .:-,")]
        if parts:
            title = max(parts, key=score_title)

    if not title or is_bad_document_title(title):
        title = title_from_url(url)
    return title


def score_title(title):
    normalized = normalize_text(title)
    if not normalized or is_bad_document_title(title):
        return -100
    score = min(len(normalized), 80)
    good_words = (
        "pliego", "pcap", "ppt", "memoria", "deuc", "anexo", "resolucion",
        "informe", "aprobacion", "licitacion", "adjudicacion", "formalizacion",
        "prescripciones", "administrativas", "tecnicas", "contrato", "csv",
    )
    bad_words = (
        "advertisements", "post on platform", "veure documents", "end date",
        "breadcrumb", "contact", "deferred", "modules", "menu", "skip",
    )
    score += sum(25 for word in good_words if word in normalized)
    score -= sum(45 for word in bad_words if word in normalized)
    if len(normalized) > 140:
        score -= 40
    return score


def best_title(candidates, url):
    cleaned = []
    for candidate in candidates:
        title = clean_context_title(candidate)
        if title:
            cleaned.append(title)
    cleaned.append(title_from_url(url))
    return max(cleaned, key=score_title)


def context_candidate(parts):
    ignored = {
        "documentos",
        "documentacion",
        "documentacion complementaria",
        "anuncios publicados",
        "place detail",
    }
    for part in reversed(parts):
        normalized = normalize_text(part)
        if not normalized or normalized in ignored:
            continue
        if is_bad_document_title(part):
            continue
        return clean_text(part)
    return ""


def clean_document_title(text, url, context=""):
    original = clean_text(text)
    normalized = normalize_text(original)
    title = original

    if is_bad_document_title(title) or len(normalized) <= 2:
        context_title = clean_context_title(context)
        title = context_title if context_title and not is_bad_document_title(context_title) else title_from_url(url)

    title = re.sub(r"\bDescargar\b", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"\bDescarga\b", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"\bEste\s+(?:enlace\s+)?se\s+abrir[aá]\s+en\s+una\s+nueva\s+ventana\b", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"\bSe\s+abrir[aá]\s+en\s+una\s+nueva\s+ventana\b", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"\bOpens\s+in\s+a\s+new\s+window\b", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"\bdocumento\s+anuncio\s+PDF\b", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"\bPDF\b|\bXML\b", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"\b\d{1,2}/\d{1,2}/\d{2,4}\s+\d{1,2}:\d{2}\b", " ", title)
    title = re.sub(r"\b20\d{2}-\d+\b", " ", title)
    title = re.sub(r"\s+", " ", title).strip(" .:-")
    return title or title_from_url(url)


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.title = ""
        self.text_parts = []
        self.current_heading = ""
        self._anchor = None
        self._title_active = False
        self._heading_tag = None
        self._heading_text = []
        self._recent_text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        tag = tag.lower()
        if tag == "a":
            self._anchor = {
                "href": attrs.get("href", ""),
                "text": [],
                "section": self.current_heading,
                "context": context_candidate(self._recent_text),
            }
        elif tag == "title":
            self._title_active = True
        elif tag in {"h1", "h2", "h3", "h4"}:
            self._heading_tag = tag
            self._heading_text = []

    def handle_data(self, data):
        text = clean_text(data)
        if not text:
            return
        self.text_parts.append(text)
        if self._anchor is not None:
            self._anchor["text"].append(text)
        if self._title_active:
            self.title = clean_text(f"{self.title} {text}")
        if self._heading_tag:
            self._heading_text.append(text)
        self._recent_text.append(text)
        self._recent_text = self._recent_text[-16:]

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "a" and self._anchor is not None:
            self._anchor["text"] = clean_text(" ".join(self._anchor["text"]))
            self.links.append(self._anchor)
            self._anchor = None
        elif tag == "title":
            self._title_active = False
        elif tag == self._heading_tag:
            heading = clean_text(" ".join(self._heading_text))
            if heading:
                self.current_heading = heading
            self._heading_tag = None
            self._heading_text = []


def fetch_html(url):
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=TIMEOUT) as response:
        content_type = response.headers.get("content-type", "")
        raw = response.read()
    encoding = "utf-8"
    match = re.search(r"charset=([^;]+)", content_type, re.IGNORECASE)
    if match:
        encoding = match.group(1).strip()
    return raw.decode(encoding, errors="replace"), content_type


def is_document_link(url, text):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False

    combined = normalize_text(f"{url} {text}")
    if extension_from_url(url) or extension_from_text(text):
        return True
    return any(hint in combined for hint in DOCUMENT_HINTS)


def infer_section(section):
    return clean_text(section) or "Documentación"


def extract_documents(url, links):
    documents = []
    seen = set()

    for link in links:
        href = clean_text(link.get("href"))
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        absolute = urljoin(url, href)
        text = clean_text(link.get("text"))
        if not is_document_link(absolute, text):
            continue

        title = clean_document_title(text, absolute, link.get("context"))
        ext = extension_from_url(absolute) or extension_from_text(text)
        fingerprint_source = f"{absolute}|{normalize_text(title)}"
        fingerprint = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()
        if fingerprint in seen:
            continue
        seen.add(fingerprint)

        documents.append(
            {
                "titulo": title,
                "url": absolute,
                "extension": ext,
                "seccion": infer_section(link.get("section")),
                "fecha": extract_document_date(f"{text} {link.get('context', '')}"),
                "fingerprint": fingerprint,
            }
        )

    documents.sort(key=lambda item: (normalize_text(item["seccion"]), normalize_text(item["titulo"]), item["url"]))
    return documents


def soup_text(node):
    if not node:
        return ""
    return clean_text(node.get_text(" ", strip=True))


def candidate_titles_from_soup_link(link):
    candidates = [
        link.get("title"),
        link.get("aria-label"),
        soup_text(link),
    ]

    td = link.find_parent("td")
    if td:
        previous = td.find_previous_sibling("td")
        if previous:
            candidates.append(soup_text(previous))
            div = previous.find("div")
            if div:
                candidates.append(soup_text(div))

    li = link.find_parent("li")
    if li:
        li_text = soup_text(li)
        anchor_text = soup_text(link)
        if anchor_text:
            li_text = li_text.replace(anchor_text, " ")
        candidates.append(li_text)

    for parent_name in ("tr", "article", "section", "div"):
        parent = link.find_parent(parent_name)
        if parent:
            text = soup_text(parent)
            if len(text) <= 260:
                candidates.append(text)

    previous_span = link.find_previous("span", class_=re.compile("outputText", re.IGNORECASE))
    if previous_span:
        candidates.append(soup_text(previous_span))

    return [candidate for candidate in candidates if clean_text(candidate)]


def is_junta_url(url):
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    return (
        "juntadeandalucia.es" in host
        or "junta-andalucia.es" in host
        or "pdc-front-publico" in path
        or "pdc_sirec" in path
    )


def is_place_url(url):
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    return "contrataciondelestado.es" in host


def is_place_document_href(href):
    return "GetDocumentByIdServlet" in str(href or "") or "DocumentIdParam=" in str(href or "")


def is_catalunya_url(url):
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    return host == "contractaciopublica.cat" or host.endswith(".contractaciopublica.cat")


def is_catalunya_document_url(url):
    parsed = urlparse(url)
    path = parsed.path.lower()
    return is_catalunya_url(url) and (
        "/portal-api/descarrega-document/" in path
        or "/portal-api/descarrega-document-antic/" in path
    )


def heading_level(tag):
    name = getattr(tag, "name", "") or ""
    if re.fullmatch(r"h[1-6]", name, re.IGNORECASE):
        return int(name[1])
    return 3


def links_in_named_section(soup, wanted_title):
    wanted = normalize_text(wanted_title)
    candidates = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "legend", "strong", "b", "span", "div", "p"])
    heading = next((tag for tag in candidates if normalize_text(soup_text(tag)) == wanted), None)
    if not heading:
        return []

    tags = list(soup.find_all(True))
    try:
        start = tags.index(heading)
    except ValueError:
        return []

    level = heading_level(heading)
    end = len(tags)
    for index in range(start + 1, len(tags)):
        tag = tags[index]
        name = getattr(tag, "name", "") or ""
        if re.fullmatch(r"h[1-6]", name, re.IGNORECASE) and heading_level(tag) <= level:
            text = normalize_text(soup_text(tag))
            if text and text != wanted:
                end = index
                break

    links = [tag for tag in tags[start + 1:end] if getattr(tag, "name", "") == "a" and tag.get("href")]
    if links:
        return links

    sibling = heading.next_sibling
    attempts = 0
    while sibling is not None and attempts < 12:
        attempts += 1
        if hasattr(sibling, "find_all"):
            links.extend(sibling.find_all("a", href=True))
        sibling = sibling.next_sibling
    return links


def document_from_junta_link(base_url, link, section_key, seen):
    href = clean_text(link.get("href"))
    if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
        return None

    absolute = urljoin(base_url, href)
    link_text = soup_text(link) or clean_text(link.get("title")) or clean_text(link.get("download"))
    li = link.find_parent("li")
    tr = link.find_parent("tr")
    parent_text = soup_text(li) or soup_text(tr) or soup_text(link.parent) or link_text
    normalized_link = normalize_text(f"{link_text} {link.get('title') or ''}")
    normalized_item = normalize_text(f"{parent_text} {link_text} {href}")

    if "sello de tiempo" in normalized_link:
        return None
    if section_key == "anuncios":
        if "documento anuncio pdf" not in normalized_item:
            return None
        if "documento descriptivo" in normalized_item or "xml" in normalized_item:
            return None

    if not is_document_link(absolute, f"{link_text} {parent_text}"):
        return None

    title_source = parent_text if section_key == "anuncios" else (link_text or parent_text)
    title = clean_junta_document_title(title_source, absolute)
    ext = extension_from_url(absolute) or extension_from_text(f"{link_text} {parent_text}") or (".pdf" if section_key == "anuncios" else "")
    section = "Anuncios publicados" if section_key == "anuncios" else "Documentación complementaria"
    fecha = extract_document_date(parent_text)
    fingerprint_source = f"{absolute}|{normalize_text(title)}"
    fingerprint = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()
    if fingerprint in seen:
        return None
    seen.add(fingerprint)

    return {
        "titulo": title,
        "url": absolute,
        "extension": ext,
        "seccion": section,
        "fecha": fecha,
        "fingerprint": fingerprint,
    }


def extract_junta_documents_bs4(url, soup):
    documents = []
    seen = set()
    sections = [
        ("documentacion", "Documentación complementaria"),
        ("anuncios", "Anuncios publicados"),
    ]
    for section_key, heading in sections:
        for link in links_in_named_section(soup, heading):
            document = document_from_junta_link(url, link, section_key, seen)
            if document:
                documents.append(document)
    documents.sort(key=lambda item: (normalize_text(item["seccion"]), item.get("fecha") or "", normalize_text(item["titulo"])))
    return documents


def document_from_junta_browser_link(base_url, enlace, seen):
    href = clean_text(enlace.get("href"))
    if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
        return None
    absolute = urljoin(base_url, href)
    section_key = clean_text(enlace.get("section")) or "documentacion"
    item_text = clean_text(enlace.get("itemText"))
    link_text = clean_text(enlace.get("text") or enlace.get("title") or enlace.get("download"))
    source = item_text or link_text
    title = clean_junta_document_title(source, absolute)
    ext = extension_from_url(absolute) or extension_from_text(source) or (".pdf" if section_key == "anuncios" else "")
    section = "Anuncios publicados" if section_key == "anuncios" else "Documentación complementaria"
    fecha = extract_document_date(source)
    fingerprint_source = f"{absolute}|{normalize_text(title)}"
    fingerprint = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()
    if fingerprint in seen:
        return None
    seen.add(fingerprint)
    return {
        "titulo": title,
        "url": absolute,
        "extension": ext,
        "seccion": section,
        "fecha": fecha,
        "fingerprint": fingerprint,
    }


def extract_junta_documents_browser(url):
    try:
        import Descargar_JuntaAndalucia as junta
    except Exception:
        return []

    proceso = None
    perfil_temporal = None
    browser = None
    page = None
    carpeta_temporal = tempfile.mkdtemp(prefix="llangon_monitor_junta_")
    documents = []
    seen = set()

    try:
        junta.log = lambda *args, **kwargs: None
        proceso, perfil_temporal, browser, port = junta.abrir_chrome()
        page = junta.crear_pagina(browser, port, carpeta_temporal)
        page.call("Page.navigate", {"url": url}, timeout=10)
        junta.esperar_documentacion_complementaria(page)
        enlaces = junta.extraer_enlaces(page, False)
        for enlace in enlaces:
            document = document_from_junta_browser_link(url, enlace, seen)
            if document:
                documents.append(document)
    except Exception:
        documents = []
    finally:
        try:
            if proceso and perfil_temporal:
                junta.cerrar_chrome(proceso, perfil_temporal, browser, page)
        finally:
            shutil.rmtree(carpeta_temporal, ignore_errors=True)

    documents.sort(key=lambda item: (normalize_text(item["seccion"]), item.get("fecha") or "", normalize_text(item["titulo"])))
    return documents


def clean_catalunya_document_title(text, url=""):
    title = clean_text(text)
    title = re.sub(r"\b(Descarregar|Descargar|Download)\b", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"\b(PDF|XML|HTML?|DOCX?|XLSX?|ZIP|RTF|CSV|ODS|ODT)\b", " ", title, flags=re.IGNORECASE)
    title = re.sub(r"\b\d+(?:[.,]\d+)?\s*(?:KB|MB|GB|bytes?)\b", " ", title, flags=re.IGNORECASE)
    title = DOCUMENT_DATE_RE.sub(" ", title)
    title = re.sub(r"\s+", " ", title).strip(" .:-")
    if not title or is_bad_document_title(title):
        title = title_from_url(url)
    return title


def document_from_catalunya_link(base_url, link, seen):
    href = clean_text(link.get("href"))
    if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
        return None
    absolute = urljoin(base_url, href)
    if not is_catalunya_document_url(absolute):
        return None

    link_text = soup_text(link) or clean_text(link.get("title")) or clean_text(link.get("download"))
    parent = link.find_parent(["li", "tr", "div", "section", "article"])
    parent_text = soup_text(parent) if parent else link_text
    source = link_text or parent_text
    title = clean_catalunya_document_title(source, absolute)
    ext = extension_from_url(absolute) or extension_from_text(f"{link_text} {parent_text}")
    heading = link.find_previous(["h1", "h2", "h3", "h4"])
    section = soup_text(heading) if heading else "Documentación"
    fecha = extract_document_date(parent_text)
    fingerprint_source = f"{absolute}|{normalize_text(title)}"
    fingerprint = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()
    if fingerprint in seen:
        return None
    seen.add(fingerprint)
    return {
        "titulo": title,
        "url": absolute,
        "extension": ext,
        "seccion": section or "Documentación",
        "fecha": fecha,
        "fingerprint": fingerprint,
    }


def extract_catalunya_documents_bs4(url, soup):
    documents = []
    seen = set()
    seen_urls = set()
    for link in soup.find_all("a", href=True):
        document = document_from_catalunya_link(url, link, seen)
        if document and document["url"].lower() not in seen_urls:
            seen_urls.add(document["url"].lower())
            documents.append(document)

    pattern = re.compile(r'(?:https?://[^"\'\s<>]+)?/portal-api/descarrega-document(?:-antic)?/[^"\'\s<>]+', re.IGNORECASE)
    for tag in soup.find_all(True):
        attr_text = " ".join(
            " ".join(map(str, value)) if isinstance(value, list) else str(value)
            for value in tag.attrs.values()
        )
        if "descarrega-document" not in attr_text:
            continue
        for href in pattern.findall(attr_text):
            absolute = urljoin(url, href)
            if not is_catalunya_document_url(absolute):
                continue
            link_text = soup_text(tag) or clean_text(tag.get("title")) or clean_text(tag.get("aria-label"))
            parent = tag.find_parent(["li", "tr", "div", "section", "article"])
            parent_text = soup_text(parent) if parent else link_text
            if len(parent_text) > 350:
                parent_text = link_text
            title = clean_catalunya_document_title(link_text or parent_text, absolute)
            ext = extension_from_url(absolute) or extension_from_text(f"{link_text} {parent_text}")
            fecha = extract_document_date(parent_text)
            if absolute.lower() in seen_urls:
                continue
            fingerprint_source = f"{absolute}|{normalize_text(title)}"
            fingerprint = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            seen_urls.add(absolute.lower())
            documents.append(
                {
                    "titulo": title,
                    "url": absolute,
                    "extension": ext,
                    "seccion": "Documentación",
                    "fecha": fecha,
                    "fingerprint": fingerprint,
                }
            )
    documents.sort(key=lambda item: (item.get("fecha") or "", normalize_text(item["titulo"]), item["url"]))
    return documents


def document_from_catalunya_browser_link(base_url, enlace, seen):
    href = clean_text(enlace.get("href"))
    if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
        return None
    absolute = urljoin(base_url, href)
    if not is_catalunya_document_url(absolute):
        return None

    item_text = clean_text(enlace.get("itemText"))
    link_text = clean_text(enlace.get("text") or enlace.get("title") or enlace.get("download"))
    source = link_text or item_text
    title = clean_catalunya_document_title(source, absolute)
    ext = extension_from_url(absolute) or extension_from_text(f"{source} {item_text}")
    section = clean_text(enlace.get("section")) or "Documentación"
    fecha = clean_text(enlace.get("fecha")) or extract_document_date(item_text)
    fingerprint_source = f"{absolute}|{normalize_text(title)}"
    fingerprint = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()
    if fingerprint in seen:
        return None
    seen.add(fingerprint)
    return {
        "titulo": title,
        "url": absolute,
        "extension": ext,
        "seccion": section,
        "fecha": fecha,
        "fingerprint": fingerprint,
    }


def extract_catalunya_documents_browser(url):
    try:
        import Descargar_Catalunya as catalunya
    except Exception:
        return []

    documents = []
    seen = set()
    try:
        catalunya.log = lambda *args, **kwargs: None
        enlaces = catalunya.extraer_documentos_renderizados(url)
        for enlace in enlaces:
            document = document_from_catalunya_browser_link(url, enlace, seen)
            if document:
                documents.append(document)
    except Exception:
        documents = []
    documents.sort(key=lambda item: (item.get("fecha") or "", normalize_text(item["titulo"]), item["url"]))
    return documents


def clean_place_document_title(text, url=""):
    title = clean_document_title(text, url)
    if is_bad_document_title(title):
        title = ""
    return title or title_from_url(url)


def place_title_from_table(link, estamos_en_otros_documentos=False):
    if estamos_en_otros_documentos:
        span = link.find_previous("span", class_=re.compile("outputText", re.IGNORECASE))
        if span:
            text = soup_text(span)
            if text and not is_bad_document_title(text):
                return text

    td_actual = link.find_parent("td")
    if td_actual:
        td_anterior = td_actual.find_previous_sibling("td")
        if td_anterior:
            div = td_anterior.find("div")
            if div:
                text = soup_text(div)
                if text and not is_bad_document_title(text):
                    return text

            text = soup_text(td_anterior)
            if text and not is_bad_document_title(text):
                return text

    for selector in [
        ("span", re.compile("outputText", re.IGNORECASE)),
        ("label", None),
        ("div", None),
    ]:
        name, pattern = selector
        previous = link.find_previous(name, class_=pattern) if pattern else link.find_previous(name)
        if previous:
            text = soup_text(previous)
            if text and len(text) <= 180 and not is_bad_document_title(text):
                return text

    return ""


def document_from_place_link(base_url, link, seen, estamos_en_otros_documentos=False):
    href = clean_text(link.get("href"))
    if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
        return None
    if not is_place_document_href(href):
        return None

    absolute = urljoin(base_url, href)
    table_title = place_title_from_table(link, estamos_en_otros_documentos)
    visible_text = soup_text(link)
    candidates = []
    if table_title:
        candidates.append(table_title)
    candidates.extend(candidate_titles_from_soup_link(link))
    title = best_title(candidates, absolute)
    if score_title(title) < 0:
        title = clean_place_document_title(table_title or visible_text, absolute)
    ext = extension_from_url(absolute) or extension_from_text(" ".join(candidates + [visible_text]))
    parent = link.find_parent(["tr", "li", "div", "section", "article"])
    parent_text = soup_text(parent) if parent else visible_text
    heading = link.find_previous(["h1", "h2", "h3", "h4"])
    section = soup_text(heading) if heading else "Documentación"
    fecha = extract_document_date(parent_text)
    fingerprint_source = f"{absolute}|{normalize_text(title)}"
    fingerprint = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()
    if fingerprint in seen:
        return None
    seen.add(fingerprint)
    return {
        "titulo": title,
        "url": absolute,
        "extension": ext,
        "seccion": section or "Documentación",
        "fecha": fecha,
        "fingerprint": fingerprint,
    }


def extract_place_documents_bs4(url, soup):
    documents = []
    seen = set()
    estamos_en_otros_documentos = False
    base_tag = soup.find("base", href=True)
    base_url = urljoin(url, base_tag["href"]) if base_tag else url

    for tag in soup.find_all(True):
        if tag.has_attr("title") and "otros documentos" in normalize_text(tag.get("title")):
            estamos_en_otros_documentos = True

        if tag.name != "a" or not tag.has_attr("href"):
            continue

        document = document_from_place_link(base_url, tag, seen, estamos_en_otros_documentos)
        if document:
            documents.append(document)

    documents.sort(key=lambda item: (item.get("fecha") or "", normalize_text(item["seccion"]), normalize_text(item["titulo"]), item["url"]))
    return documents


def extract_documents_bs4(url, html):
    if BeautifulSoup is None:
        return []
    soup = BeautifulSoup(html, "html.parser")
    if is_place_url(url):
        place_documents = extract_place_documents_bs4(url, soup)
        if place_documents:
            return place_documents
    if is_junta_url(url):
        junta_documents = extract_junta_documents_bs4(url, soup)
        if junta_documents:
            return junta_documents
    if is_catalunya_url(url):
        catalunya_documents = extract_catalunya_documents_bs4(url, soup)
        if catalunya_documents:
            return catalunya_documents

    documents = []
    seen = set()

    for link in soup.find_all("a", href=True):
        href = clean_text(link.get("href"))
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        absolute = urljoin(url, href)
        visible_text = soup_text(link)
        if not is_document_link(absolute, visible_text):
            continue

        candidates = candidate_titles_from_soup_link(link)
        title = best_title(candidates, absolute)
        if score_title(title) < 0:
            continue
        ext = extension_from_url(absolute) or extension_from_text(" ".join(candidates))
        section = ""
        heading = link.find_previous(["h1", "h2", "h3", "h4"])
        if heading:
            section = soup_text(heading)
        section = section or "Documentación"
        fingerprint_source = f"{absolute}|{normalize_text(title)}"
        fingerprint = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        documents.append(
            {
                "titulo": title,
                "url": absolute,
                "extension": ext,
                "seccion": section,
                "fecha": extract_document_date(" ".join(candidates)),
                "fingerprint": fingerprint,
            }
        )

    documents.sort(key=lambda item: (normalize_text(item["seccion"]), normalize_text(item["titulo"]), item["url"]))
    return documents


def extract_relevant_data(text):
    data = {}
    patterns = {
        "expediente": r"(?:expediente|n[uú]mero\s+de\s+expediente|referencia)\s*:?\s*([A-Z0-9][A-Z0-9/_. -]{3,60})",
        "presupuesto": r"(?:presupuesto|valor\s+estimado|importe)\s*:?\s*([0-9][0-9., ]+\s*(?:€|eur)?)",
        "fecha_limite": r"(?:fecha\s+l[ií]mite|fin\s+de\s+plazo|presentaci[oó]n\s+de\s+ofertas)\s*:?\s*(\d{1,2}/\d{1,2}/\d{2,4}(?:\s+\d{1,2}:\d{2})?)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            data[key] = clean_text(match.group(1))[:160]
    return data


def monitor_url(url):
    html, content_type = fetch_html(url)
    parser = LinkParser()
    parser.feed(html)
    full_text = clean_text(" ".join(parser.text_parts))
    documents = extract_documents_bs4(url, html) or extract_documents(url, parser.links)
    if is_junta_url(url) and not documents:
        documents = extract_junta_documents_browser(url)
    if is_catalunya_url(url) and not documents:
        documents = extract_catalunya_documents_browser(url)
    content_hash = hashlib.sha256(
        json.dumps(
            {
                "title": parser.title,
                "text": full_text[:20000],
                "documents": documents,
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()

    return {
        "url": url,
        "page_title": parser.title or title_from_url(url),
        "content_type": content_type,
        "content_hash": content_hash,
        "text_excerpt": full_text[:12000],
        "datos": extract_relevant_data(full_text),
        "documentos": documents,
    }


def main():
    parser = argparse.ArgumentParser(description="Monitoriza una URL de licitación y devuelve una foto JSON.")
    parser.add_argument("url")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    try:
        result = monitor_url(args.url)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1

    result["ok"] = True
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
