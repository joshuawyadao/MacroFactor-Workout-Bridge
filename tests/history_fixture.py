"""Small synthetic irregular sheet shared by history and desktop regressions."""

from pathlib import Path
from xml.etree import ElementTree as ET
import zipfile

from macrofactor_bridge.history_layout import HistoryWeek
from macrofactor_bridge.ooxml import MAIN_NS, XlsxPackage, qn, split_cell_reference


LAYOUT = (
    HistoryWeek('Week 10', 'I3', 'Week 10'),
    HistoryWeek('Week 11', 'K3', 'Week 11'),
    HistoryWeek('Week 12', 'M3', 'Train on 8/18'),
)


def irregular_workbook(
    destination: Path, *, extra_cells: dict[str, str] | None = None,
    header_merges: tuple[str, ...] = ('I3:J4', 'K3:L4', 'M3:N4', 'Q3:R4', 'S3:T4'),
    formulas: dict[str, str | None] | None = None,
) -> None:
    source = Path(__file__).parent / 'fixtures/coach-template.xlsx'
    part = XlsxPackage(source).sheet_by_name('Training Block').path
    sheet = ET.Element(qn(MAIN_NS, 'worksheet'))
    data = ET.SubElement(sheet, qn(MAIN_NS, 'sheetData'))
    values = {
        'D3': 'Variation', 'I3': 'Week 10', 'K3': 'Week 11',
        'M3': 'Train on 8/18', 'Q3': 'Week 8', 'S3': 'Week 9',
        'D5': 'Tempo Squat', 'D6': 'Chest Press', 'D7': 'Cable Curl',
        'J5': '200 x 5', 'L6': '100 x 8', 'N7': '30 x 10',
        'R5': 'historical result', 'T5': 'historical result',
    }
    values.update(extra_cells or {})
    rows = {}
    for reference, value in sorted(values.items(), key=lambda item: split_cell_reference(item[0])):
        row_number, _ = split_cell_reference(reference)
        if row_number not in rows:
            rows[row_number] = ET.SubElement(data, qn(MAIN_NS, 'row'), {'r': str(row_number)})
        if formulas is not None and reference in formulas:
            cell = ET.SubElement(rows[row_number], qn(MAIN_NS, 'c'), {'r': reference, 't': 'str'})
            ET.SubElement(cell, qn(MAIN_NS, 'f'), {'t': 'shared', 'si': '0'}).text = formulas[reference]
            ET.SubElement(cell, qn(MAIN_NS, 'v')).text = value
        else:
            cell = ET.SubElement(rows[row_number], qn(MAIN_NS, 'c'), {'r': reference, 't': 'inlineStr'})
            inline = ET.SubElement(cell, qn(MAIN_NS, 'is'))
            ET.SubElement(inline, qn(MAIN_NS, 't')).text = value
    merges = ET.SubElement(sheet, qn(MAIN_NS, 'mergeCells'), {'count': str(len(header_merges))})
    for reference in header_merges:
        ET.SubElement(merges, qn(MAIN_NS, 'mergeCell'), {'ref': reference})
    with zipfile.ZipFile(source) as reader, zipfile.ZipFile(destination, 'w') as writer:
        for item in reader.infolist():
            writer.writestr(item, ET.tostring(sheet) if item.filename == part else reader.read(item.filename))
