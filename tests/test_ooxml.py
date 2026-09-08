from __future__ import annotations

import unittest
from xml.dom import minidom
from xml.etree import ElementTree as ET

from macrofactor_bridge.ooxml import MAIN_NS, XML_NS, XlsxPackage, qn


MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"
DECLARATIONS = (
    f'xmlns:s="{MAIN_NS}" xmlns:mc="{MC_NS}" '
    'xmlns:x="urn:outer" mc:Ignorable="x"'
)
EXTENSIONS = """
    <s:extLst><s:ext uri="example">
        <x:outer/>
        <x:inner xmlns:x="urn:inner" mc:Ignorable="x"/>
        <s:unused xmlns:x="urn:unused" mc:Ignorable="x"/>
    </s:ext></s:extLst>
"""
SHEET = f"""<s:worksheet {DECLARATIONS}>
    <s:sheetData><s:row r="1"><s:c r="A1"/></s:row></s:sheetData>
    {EXTENSIONS}
</s:worksheet>""".encode()
STYLES = f"""<s:styleSheet {DECLARATIONS}>
    <s:fills count="1"><s:fill><s:patternFill patternType="none"/></s:fill></s:fills>
    <s:cellXfs count="1"><s:xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></s:cellXfs>
    {EXTENSIONS}
</s:styleSheet>""".encode()


class NamespacePreservationTests(unittest.TestCase):
    def assert_namespace_scopes_preserved(self, xml: bytes) -> None:
        with minidom.parseString(xml) as document:
            root = document.documentElement
            self.assertEqual(root.getAttribute("xmlns:x"), "urn:outer")
            self.assertEqual(root.getAttributeNS(MC_NS, "Ignorable"), "x")
            self.assertEqual(len(root.getElementsByTagNameNS("urn:outer", "outer")), 1)
            inner = root.getElementsByTagNameNS("urn:inner", "inner")[0]
            self.assertEqual(inner.getAttribute("xmlns:x"), "urn:inner")
            self.assertEqual(inner.getAttributeNS(MC_NS, "Ignorable"), "x")
            unused = root.getElementsByTagNameNS(MAIN_NS, "unused")[0]
            self.assertEqual(unused.getAttribute("xmlns:x"), "urn:unused")
            self.assertEqual(unused.getAttributeNS(MC_NS, "Ignorable"), "x")

    def test_worksheet_keeps_rebound_and_attribute_only_prefixes(self) -> None:
        output = XlsxPackage._updated_sheet_xml(SHEET, {"A1": " 10 & 20 x 8 < 9 "})
        self.assert_namespace_scopes_preserved(output)
        text = ET.fromstring(output).find(f".//{qn(MAIN_NS, 't')}")
        self.assertIsNotNone(text)
        self.assertEqual(text.text, " 10 & 20 x 8 < 9 ")
        self.assertEqual(text.attrib[qn(XML_NS, "space")], "preserve")

    def test_stylesheet_keeps_rebound_and_attribute_only_prefixes(self) -> None:
        output, indexes = XlsxPackage._highlighted_styles_xml(
            STYLES, SHEET, {"A1": "FFFFFF00"}
        )
        self.assert_namespace_scopes_preserved(output)
        root = ET.fromstring(output)
        fills = root.find(qn(MAIN_NS, "fills"))
        xfs = root.find(qn(MAIN_NS, "cellXfs"))
        self.assertEqual(fills.attrib["count"], "2")
        self.assertEqual(xfs.attrib["count"], "2")
        self.assertEqual(indexes, {"A1": 1})
        self.assertEqual(xfs[1].attrib["fillId"], "1")
        self.assertEqual(xfs[1].attrib["applyFill"], "1")
