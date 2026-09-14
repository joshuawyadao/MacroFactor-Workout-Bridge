from __future__ import annotations

import unittest
from xml.dom import minidom
from xml.etree import ElementTree as ET

from macrofactor_bridge.ooxml import MAIN_NS, XML_NS, WorkbookError, XlsxPackage, qn


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


class InheritedHighlightStyleTests(unittest.TestCase):
    def setUp(self) -> None:
        formats = "".join(
            f'<xf numFmtId="{164 + index}" fontId="{index}" fillId="0" '
            f'borderId="{index}" xfId="0" applyAlignment="1" applyNumberFormat="1">'
            f'<alignment horizontal="center" indent="{index}" wrapText="1"/>'
            '<protection locked="0"/></xf>'
            for index in range(4)
        )
        self.styles = (
            f'<styleSheet xmlns="{MAIN_NS}"><fills count="1">'
            '<fill><patternFill patternType="none"/></fill></fills>'
            f'<cellXfs count="4">{formats}</cellXfs></styleSheet>'
        ).encode()

    def assert_highlight_uses_style(
        self, row_attributes: str, cell_attributes: str, columns: str, expected: int
    ) -> None:
        sheet = (
            f'<worksheet xmlns="{MAIN_NS}"><cols>{columns}</cols>'
            f'<sheetData><row r="1" {row_attributes}><c r="B1" {cell_attributes}/>'
            '</row></sheetData></worksheet>'
        ).encode()
        output, indexes = XlsxPackage._highlighted_styles_xml(
            self.styles, sheet, {"B1": "FFFFFF00"}
        )
        original_xfs = ET.fromstring(self.styles).find(qn(MAIN_NS, "cellXfs"))
        root = ET.fromstring(output)
        xfs = root.find(qn(MAIN_NS, "cellXfs"))
        for index in range(4):
            self.assertEqual(ET.tostring(original_xfs[index]), ET.tostring(xfs[index]))
        highlighted = xfs[indexes["B1"]]
        expected_attributes = dict(original_xfs[expected].attrib, fillId="1", applyFill="1")
        self.assertEqual(highlighted.attrib, expected_attributes)
        self.assertEqual(
            [ET.tostring(child) for child in highlighted],
            [ET.tostring(child) for child in original_xfs[expected]],
        )
        self.assertEqual(
            root.find(f".//{qn(MAIN_NS, 'fgColor')}").attrib["rgb"], "FFFFFF00"
        )
        written = XlsxPackage._updated_sheet_xml(sheet, {"B1": "Skip"}, indexes)
        cell = ET.fromstring(written).find(f".//{qn(MAIN_NS, 'c')}")
        self.assertEqual(cell.attrib["s"], str(indexes["B1"]))

    def test_explicit_cell_style_wins_even_when_zero(self) -> None:
        for style in (0, 3):
            with self.subTest(style=style):
                self.assert_highlight_uses_style(
                    's="1" customFormat="1"', f's="{style}"',
                    '<col min="1" max="3" style="2"/>', style,
                )

    def test_custom_row_style_wins_over_column(self) -> None:
        for flag in ("1", "true"):
            with self.subTest(flag=flag):
                self.assert_highlight_uses_style(
                    f's="1" customFormat="{flag}"', "",
                    '<col min="1" max="3" style="2"/>', 1,
                )

    def test_column_style_applies_without_custom_row_format(self) -> None:
        for attributes in ('', 's="1"', 's="1" customFormat="0"', 's="1" customFormat="false"'):
            with self.subTest(attributes=attributes):
                self.assert_highlight_uses_style(
                    attributes, "", '<col min="1" max="3" style="2"/>', 2
                )

    def test_default_style_applies_outside_formatted_column_range(self) -> None:
        self.assert_highlight_uses_style("", "", '<col min="3" max="4" style="2"/>', 0)
        self.assert_highlight_uses_style("", "", "", 0)

    def test_invalid_or_ambiguous_inherited_style_is_rejected(self) -> None:
        for row, cell, columns in (
            ('s="-1" customFormat="1"', "", ""),
            ('s="4" customFormat="1"', "", ""),
            ('s="invalid" customFormat="1"', "", ""),
            ("", 's="-1"', ""),
            ("", "", '<col min="1" max="3" style="4"/>'),
            ("", "", '<col min="1" max="3" style="1"/><col min="2" max="2" style="2"/>'),
        ):
            with self.subTest(row=row, cell=cell, columns=columns):
                with self.assertRaisesRegex(WorkbookError, "Target cell B1 has an invalid style"):
                    self.assert_highlight_uses_style(row, cell, columns, 0)
