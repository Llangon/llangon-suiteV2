"""Privacy-oriented metadata cleanup for generated Office documents."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
CP_NS = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
DC_NS = "http://purl.org/dc/elements/1.1/"
EP_NS = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"

_REMOVED_PART_PATTERNS = (
    re.compile(r"^customXml/", re.IGNORECASE),
    re.compile(r"^docProps/custom\.xml$", re.IGNORECASE),
    re.compile(r"^word/comments", re.IGNORECASE),
    re.compile(r"^word/printerSettings/", re.IGNORECASE),
)


def clear_word_core_properties(document: object) -> None:
    properties = document.core_properties
    properties.author = ""
    properties.last_modified_by = ""
    properties.comments = ""
    properties.category = ""
    properties.keywords = ""


def clear_workbook_metadata(workbook: object) -> None:
    properties = workbook.properties
    properties.creator = ""
    properties.lastModifiedBy = ""
    properties.description = ""
    properties.keywords = ""
    properties.subject = ""
    properties.title = ""
    for attribute in ("company", "manager"):
        if hasattr(properties, attribute):
            setattr(properties, attribute, "")


def scrub_docx_package(source: Path, destination: Path) -> None:
    """Remove personal/package residue without touching semantic content."""

    with zipfile.ZipFile(source, "r") as input_zip, zipfile.ZipFile(
        destination,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as output_zip:
        for item in input_zip.infolist():
            name = item.filename
            if _should_remove_part(name):
                continue
            data = input_zip.read(name)
            if name.endswith(".rels"):
                data = _scrub_relationships(data)
            elif name == "[Content_Types].xml":
                data = _scrub_content_types(data)
            elif name == "docProps/core.xml":
                data = _scrub_core_properties(data)
            elif name == "docProps/app.xml":
                data = _scrub_app_properties(data)
            elif name.startswith("word/") and name.endswith(".xml"):
                data = _scrub_word_xml(data)
            output_zip.writestr(item, data)


def _should_remove_part(name: str) -> bool:
    return any(pattern.search(name) for pattern in _REMOVED_PART_PATTERNS)


def _scrub_relationships(data: bytes) -> bytes:
    root = ET.fromstring(data)
    for relationship in list(root):
        target = relationship.attrib.get("Target", "")
        rel_type = relationship.attrib.get("Type", "")
        external = relationship.attrib.get("TargetMode") == "External"
        lowered = f"{target} {rel_type}".lower()
        local_external = external and not target.lower().startswith(
            ("http://", "https://", "mailto:")
        )
        if (
            local_external
            or "custom-properties" in lowered
            or "comments" in lowered
            or "printersettings" in lowered
            or "customxml" in lowered
            or "attachedtemplate" in lowered
        ):
            root.remove(relationship)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _scrub_content_types(data: bytes) -> bytes:
    root = ET.fromstring(data)
    for child in list(root):
        part_name = child.attrib.get("PartName", "").lstrip("/")
        content_type = child.attrib.get("ContentType", "").lower()
        if _should_remove_part(part_name) or any(
            token in content_type
            for token in ("comments", "custom-properties", "printersettings")
        ):
            root.remove(child)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _scrub_core_properties(data: bytes) -> bytes:
    root = ET.fromstring(data)
    for tag in (
        f"{{{DC_NS}}}creator",
        f"{{{CP_NS}}}lastModifiedBy",
        f"{{{CP_NS}}}lastPrinted",
        f"{{{CP_NS}}}keywords",
        f"{{{DC_NS}}}subject",
    ):
        element = root.find(tag)
        if element is not None:
            element.text = ""
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _scrub_app_properties(data: bytes) -> bytes:
    root = ET.fromstring(data)
    for local_name in ("Company", "Manager", "HyperlinkBase"):
        element = root.find(f"{{{EP_NS}}}{local_name}")
        if element is not None:
            element.text = ""
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _scrub_word_xml(data: bytes) -> bytes:
    root = ET.fromstring(data)
    for element in root.iter():
        for attribute in tuple(element.attrib):
            local_name = attribute.rsplit("}", 1)[-1]
            if local_name.lower().startswith("rsid"):
                del element.attrib[attribute]
    _remove_comment_anchors(root)
    _unwrap_content_controls(root)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _remove_comment_anchors(root: ET.Element) -> None:
    comment_tags = {
        f"{{{W_NS}}}commentRangeStart",
        f"{{{W_NS}}}commentRangeEnd",
        f"{{{W_NS}}}commentReference",
    }
    for parent in root.iter():
        for child in list(parent):
            if child.tag in comment_tags:
                parent.remove(child)


def _unwrap_content_controls(root: ET.Element) -> None:
    sdt_tag = f"{{{W_NS}}}sdt"
    content_tag = f"{{{W_NS}}}sdtContent"
    changed = True
    while changed:
        changed = False
        for parent in root.iter():
            children = list(parent)
            for index, child in enumerate(children):
                if child.tag != sdt_tag:
                    continue
                content = child.find(content_tag)
                replacement = list(content) if content is not None else []
                parent.remove(child)
                for offset, replacement_child in enumerate(replacement):
                    parent.insert(index + offset, replacement_child)
                changed = True
                break
            if changed:
                break


__all__ = (
    "clear_word_core_properties",
    "clear_workbook_metadata",
    "scrub_docx_package",
)
