s = open("build_srs.js", encoding="utf-8").read()
BS = chr(92)
TAB_HOD = 'run("' + BS + 't[Head of Department]")'
TAB_PLACE_OLD = 'run("' + BS + 'tPlace: [City]")'
TAB_PLACE_NEW = 'run("' + BS + 'tPlace: Kolhapur")'


def rep(a, b):
    global s
    assert a in s, a[:80]
    s = s.replace(a, b)


rep('// ---------------------------------------------------------------- front pages\n', '''// ---------------------------------------------------------------- front pages
const STUDENTS = [
  "Rutvik S. Jagtap  (Roll No. 18)", "Vaibhav T. Lad  (Roll No. 57)", "Tanmay T. Salokhe  (Roll No. 46)",
  "Pranav P. Sathe  (Roll No. 47)", "Rahul Suryavanshi  (Roll No. 51)",
];
''')
rep('  center("[College / University Name]", { size: 32, bold: true, color: DARK, before: 600 }),\n  center("[Department of Data Science Engineering]", { size: 26, after: 700 }),',
    '  center("D. Y. Patil School of Engineering and Management", { size: 32, bold: true, color: DARK, before: 600, after: 40 }),\n  center("Kolhapur", { size: 28, bold: true, color: DARK, after: 60 }),\n  center("Department of Data Science Engineering", { size: 26, after: 700 }),')
rep('  center("[Student Name 1]  ([Roll No.])", { size: 26, after: 40 }),\n  center("[Student Name 2]  ([Roll No.])", { size: 26, after: 40 }),\n  center("[Student Name 3]  ([Roll No.])", { size: 26, after: 500 }),',
    '  ...STUDENTS.map((t, i) => center(t, { size: 26, after: i === STUDENTS.length - 1 ? 500 : 40 })),')
rep('center("[Guide Name, Designation]", { size: 26, after: 500 }),', 'center("Prof. Ajit Patil", { size: 26, after: 500 }),')
rep('center("Academic Year: [20__ - 20__]", { size: 26, after: 80 }),\n  center("Date: 8 October 2026", { size: 26 }),',
    'center("Academic Year: 2026 - 2027", { size: 26, after: 80 }),\n  center("Date: 12 October 2026", { size: 26 }),')
rep('students of the [Department of Data Science Engineering], [College / University Name], in partial fulfilment',
    'students of the Department of Data Science Engineering, D. Y. Patil School of Engineering and Management, Kolhapur, in partial fulfilment')
rep('during the academic year [20__ - 20__]."),', 'during the academic year 2026 - 2027."),')
rep('  ...["[Student Name 1]  ([Roll No.])", "[Student Name 2]  ([Roll No.])", "[Student Name 3]  ([Roll No.])"].map((t) => center(t, { after: 40 })),',
    '  ...STUDENTS.map((t) => center(t, { after: 40 })),')
rep('children: [run("[Guide Name]"), ' + TAB_HOD, 'children: [run("Prof. Ajit Patil"), ' + TAB_HOD)
s = s.replace('run("Date: [__ / __ / ____]"), ' + TAB_PLACE_OLD, 'run("Date: 12 / 10 / 2026"), ' + TAB_PLACE_NEW)
rep('carried out under the guidance of [Guide Name].', 'carried out under the guidance of Prof. Ajit Patil.')
rep('  ...["[Student Name 1]  ([Roll No.])", "[Student Name 2]  ([Roll No.])", "[Student Name 3]  ([Roll No.])"].map((t) => new Paragraph(',
    '  ...STUDENTS.map((t) => new Paragraph(')
open("build_srs.js", "w", encoding="utf-8").write(s)
print("patched")
