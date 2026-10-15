// Builds the college-format SRS as a Word file. Run: node build_srs.js
const fs = require("fs");
const D = require("docx");
const C = require("./content.js");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle, AlignmentType,
  ImageRun, PageBreak, Footer, Header, PageNumber, NumberFormat, LevelFormat, TableOfContents, PageOrientation, VerticalAlign, TabStopType,
} = D;

const FONT = "Times New Roman";
const BRAND = "0E7490";
const DARK = "0F2A3D";
const PAGE_W = 9026; // A4 portrait with 1 inch margins, in DXA

// ---------------------------------------------------------------- small helpers
const run = (text, o = {}) => new TextRun({ text, font: FONT, size: 24, ...o });
// text with [placeholders] highlighted so they are easy to find and replace
const rich = (text, o = {}) => text.split(/(\[[^\]]+\])/).filter(Boolean).map((t) => /^\[.*\]$/.test(t) ? run(t, { ...o, highlight: "yellow" }) : run(t, o));
const P = (text, o = {}) => new Paragraph({ spacing: { after: 120, line: 300 }, alignment: AlignmentType.JUSTIFIED, ...o.p, children: rich(text, o.r) });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: t })] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun({ text: t })] });
const H3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun({ text: t })] });
const bullets = (items, o = {}) => items.map((t) => new Paragraph({ numbering: { reference: "bul", level: 0 }, spacing: { after: 60, line: 288 }, children: rich(t, o) }));
const numbered = (items, ref) => items.map((t) => new Paragraph({ numbering: { reference: ref, level: 0 }, spacing: { after: 60, line: 288 }, children: rich(t) }));
const PK = (t) => P(t, { p: { keepNext: true } });
const spacer = (after = 120) => new Paragraph({ spacing: { after }, children: [] });
const pageBreak = () => new Paragraph({ children: [new PageBreak()] });
const center = (text, o = {}) => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: o.after ?? 120, before: o.before ?? 0 }, children: rich(text, { size: o.size ?? 24, bold: o.bold, color: o.color, italics: o.italics }) });

const border = { style: BorderStyle.SINGLE, size: 4, color: "9FB6C0" };
const borders = { top: border, bottom: border, left: border, right: border };
const cell = (content, w, o = {}) => new TableCell({
  borders, width: { size: w, type: WidthType.DXA }, verticalAlign: VerticalAlign.TOP,
  shading: o.fill ? { fill: o.fill, type: ShadingType.CLEAR, color: "auto" } : undefined,
  margins: { top: 60, bottom: 60, left: 100, right: 100 },
  children: (Array.isArray(content) ? content : [content]).map((t) => new Paragraph({ spacing: { after: 40 }, keepNext: !!o.keepNext, alignment: o.align || AlignmentType.LEFT, children: rich(String(t), { size: o.size ?? 20, bold: o.bold, color: o.color }) })),
});
/** A table with a shaded header row that repeats on every page. widths must add up to the table width. */
function table(widths, head, rows, o = {}) {
  const total = widths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: widths,
    rows: [
      new TableRow({ tableHeader: true, cantSplit: true, children: head.map((h, i) => cell(h, widths[i], { fill: "D6EDF3", bold: true, size: o.size })) }),
      ...rows.map((r) => new TableRow({ cantSplit: true, children: r.map((c, i) => cell(c, widths[i], { size: o.size, bold: o.boldFirst && i === 0 })) })),
    ],
  });
}
/** Two-column label / value table (used for use cases). */
function kv(rows) {
  const w = [2300, PAGE_W - 2300];
  return new Table({
    width: { size: PAGE_W, type: WidthType.DXA }, columnWidths: w,
    rows: rows.map(([k, v], i) => new TableRow({ cantSplit: true, children: [cell(k, w[0], { fill: "E8F5F8", bold: true, size: 21, keepNext: i < rows.length - 1 }), cell(v, w[1], { size: 21, keepNext: i < rows.length - 1 })] })),
  });
}

// PNG size is read from the file so that images keep their shape
function png(file, dir = "img") {
  const b = fs.readFileSync(__dirname + "/" + dir + "/" + file);
  return { data: b, w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}
function figure([caption, file], maxW, maxH, dir) {
  const im = png(file, dir);
  let w = maxW, h = (maxW * im.h) / im.w;
  if (h > maxH) { h = maxH; w = (maxH * im.w) / im.h; }
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 }, keepNext: true, children: [new ImageRun({ type: "png", data: im.data, transformation: { width: Math.round(w), height: Math.round(h) }, altText: { title: caption, description: caption, name: file } })] }),
    center(caption, { size: 21, italics: true, after: 200 }),
  ];
}

// ---------------------------------------------------------------- front pages
const STUDENTS = [
  "Rutvik S. Jagtap  (Roll No. 18)", "Vaibhav T. Lad  (Roll No. 57)", "Tanmay T. Salokhe  (Roll No. 46)",
  "Pranav P. Sathe  (Roll No. 47)", "Rahul Suryavanshi  (Roll No. 51)",
];
const cover = [
  center("D. Y. Patil School of Engineering and Management", { size: 32, bold: true, color: DARK, before: 600, after: 40 }),
  center("Kolhapur", { size: 28, bold: true, color: DARK, after: 60 }),
  center("Department of Data Science Engineering", { size: 26, after: 700 }),
  center("Project Title", { size: 22, color: "5B6B78", after: 60 }),
  center("HealthWise AI", { size: 52, bold: true, color: BRAND, after: 60 }),
  center("Hospital Management System with Report Analysis", { size: 30, bold: true, color: DARK, after: 700 }),
  center("SOFTWARE REQUIREMENTS SPECIFICATION", { size: 34, bold: true, color: DARK, after: 700 }),
  center("Submitted by", { size: 22, color: "5B6B78", after: 80 }),
  ...STUDENTS.map((t, i) => center(t, { size: 26, after: i === STUDENTS.length - 1 ? 500 : 40 })),
  center("Under the guidance of", { size: 22, color: "5B6B78", after: 80 }),
  center("Prof. Ajit Patil", { size: 26, after: 500 }),
  center("Academic Year: 2026 - 2027", { size: 26, after: 80 }),
  center("Date: 12 October 2026", { size: 26 }),
];

const certificate = [
  center("CERTIFICATE", { size: 32, bold: true, color: DARK, before: 300, after: 300 }),
  P("This is to certify that the Software Requirements Specification entitled \"HealthWise AI: Hospital Management System with Report Analysis\" has been prepared by the following students of the Department of Data Science Engineering, D. Y. Patil School of Engineering and Management, Kolhapur, in partial fulfilment of the requirements for the degree of Bachelor of Technology in Data Science Engineering during the academic year 2026 - 2027."),
  spacer(80),
  ...STUDENTS.map((t) => center(t, { after: 40 })),
  spacer(80),
  P("To the best of our knowledge, the work is original and has not been submitted elsewhere for any other degree or diploma."),
  spacer(500),
  new Paragraph({ tabStops: [{ type: TabStopType.RIGHT, position: PAGE_W }], children: [run("Prof. Ajit Patil"), run("\t[Head of Department]")] }),
  new Paragraph({ tabStops: [{ type: TabStopType.RIGHT, position: PAGE_W }], children: [run("Project Guide", { size: 22, color: "5B6B78" }), run("\tHead of Department", { size: 22, color: "5B6B78" })] }),
  spacer(300),
  new Paragraph({ tabStops: [{ type: TabStopType.RIGHT, position: PAGE_W }], children: [run("Date: 12 / 10 / 2026"), run("\tPlace: Kolhapur")] }),
  pageBreak(),
  center("DECLARATION", { size: 32, bold: true, color: DARK, before: 300, after: 300 }),
  P("We hereby declare that this Software Requirements Specification is the result of our own work, carried out under the guidance of Prof. Ajit Patil. The requirements, diagrams and tables in this document were prepared by us for the HealthWise AI project. Where we have used ideas, standards or text from other sources, they are listed in the References (section 1.7)."),
  P("We also declare that the project is meant for education and demonstration. It is not a medical device and does not diagnose disease or prescribe medicine."),
  spacer(500),
  ...STUDENTS.map((t) => new Paragraph({ tabStops: [{ type: TabStopType.RIGHT, position: PAGE_W }], spacing: { after: 160 }, children: [run(t), run("\tSignature: ____________")] })),
  spacer(200),
  new Paragraph({ tabStops: [{ type: TabStopType.RIGHT, position: PAGE_W }], children: [run("Date: 12 / 10 / 2026"), run("\tPlace: Kolhapur")] }),
  pageBreak(),
  center("TABLE OF CONTENTS", { size: 30, bold: true, color: DARK, after: 200 }),
  new TableOfContents("Table of Contents", { hyperlink: true, headingStyleRange: "1-2" }),
];

// ---------------------------------------------------------------- 1. Introduction
const ch1 = [
  H1("1. Introduction"),
  H2("1.1 Project Overview"),
  P("HealthWise AI is a web-based hospital management system. A hospital's staff upload a patient's medical report (a laboratory report, an X-ray report, an ECG, a discharge summary and so on) as a PDF, a photo or a text file. The system reads the file, finds the results and explains them in plain language. It then gives the treating doctor a short list of key findings, red flags and suggestions, and it prepares general tips for the patient."),
  P("Nothing reaches the patient until the doctor has reviewed it. After the review the doctor can add notes, follow-up advice and a prescription; the pharmacy dispenses the medicine and keeps the stock; the patient can follow the whole story in a timeline and compare reports over time. Five roles use the system: Admin, Doctor, Employee, Patient and Pharmacy Staff, and each role sees only what it needs."),
  P("Analysis is rule-based. The system calls a result Within, Above or Below only by comparing it with the normal range printed in the same report. An optional language model may reword the text, but it never decides anything and never sees personal details."),
  H2("1.2 Purpose of the System"),
  P("The system is being developed to solve the following problems of a typical hospital:"),
  ...bullets([
    "Medical reports arrive in many layouts and formats; reading them by hand is slow and error-prone.",
    "Patients receive numbers they cannot understand, and doctors have little time to explain.",
    "Reports, notes, prescriptions and dispensing records are kept in separate places, so the patient's story is hard to follow.",
    "Patient information must be seen only by the right people, and there must be a record of who did what.",
  ]),
  P("The purpose of this SRS is to state clearly what the system shall do, so that the development team, the guide and the testers share one understanding, and so that every requirement can be traced to a use case and a test."),
  H2("1.3 Scope of the Project"),
  P("Included:", { r: { bold: true } }),
  ...bullets([
    "Login for five roles, forced password change and role-based access.",
    "Staff creation, department management and patient registration.",
    "Report upload (PDF, JPG, JPEG, PNG, WEBP, TXT, CSV), text reading and OCR.",
    "Rule-based analysis of laboratory results using the printed reference range.",
    "Insights for any type of medical report: key findings, red flags, suggestions for doctors and tips for patients.",
    "Mandatory doctor review before the patient sees an analysis; notes, advice and medical history.",
    "Prescriptions, pharmacy dispensing and medicine stock.",
    "Appointments, patient timeline, report comparison and trend charts.",
    "Dashboards, in-app notifications and an audit log.",
  ]),
  P("Not included:", { r: { bold: true } }),
  ...bullets([
    "Diagnosis or prediction of disease, and any choice of medicine by the system.",
    "Billing, insurance and payroll.",
    "Tele-consultation (video calls), ward or bed management.",
    "Email and SMS messages (notifications are shown inside the application).",
    "Exchange of data with other hospital systems (for example HL7 or FHIR).",
    "Native mobile apps (the web application works in a phone browser).",
  ]),
  H2("1.4 Objectives"),
  ...numbered([
    "To read uploaded reports of different layouts and formats and to extract real values from each file.",
    "To classify each result using only the range printed in the report, so that no range is ever invented.",
    "To give doctors insights and suggestions for any type of report, and give patients clear tips, within seconds for a text report.",
    "To make sure that a doctor reviews every report before the patient sees its analysis (100% of reports).",
    "To connect report, review, notes, prescription and dispensing in one workflow.",
    "To provide role-based access so that each user sees only permitted data, and to record important actions in an audit log.",
    "To show the patient's history over time with comparison and trend charts.",
    "To keep the system verifiable: all 108 automated tests pass.",
  ], "obj"),
  H2("1.5 Intended Users"),
  ...bullets([
    "Administrator: manages staff accounts and reads the audit log.",
    "Doctor: reviews reports, writes notes and prescriptions.",
    "Hospital Employee: registers patients, uploads reports, books appointments.",
    "Patient: views reviewed reports, tips, prescriptions and history.",
    "Pharmacy Staff: dispenses medicine and manages stock.",
    "Readers of this document: the project guide, faculty reviewers, developers and testers.",
  ]),
  H2("1.6 Definitions, Acronyms and Abbreviations"),
  table([2200, PAGE_W - 2200], ["Term", "Meaning"], C.definitions, { boldFirst: true }),
  spacer(),
  H2("1.7 References"),
  ...numbered(C.references, "ref"),
];

// ---------------------------------------------------------------- 2. Overall description
const ch2 = [
  H1("2. Overall Description"),
  P("This chapter gives a high-level view of the complete system."),
  H2("2.1 Product Perspective"),
  P("HealthWise AI is a new, self-contained system. It replaces the manual way of keeping paper reports, reading numbers by eye and passing notes and prescriptions between desks. It is not an extension of an older software product."),
  P("The system has three tiers: a React web application in the user's browser, a FastAPI server that holds all business rules, and a relational database (SQLite or PostgreSQL). Two outside services are used and both are replaceable: the Tesseract OCR engine (to read scans) and an optional language model (to reword text). Figure 7.1 shows the system and its surroundings."),
  H2("2.2 Product Functions"),
  P("The major functions of the system are summarised below. Chapter 3 describes each in detail."),
  table([2600, PAGE_W - 2600], ["Function group", "Summary"], C.productFunctions, { boldFirst: true }),
  spacer(),
  H2("2.3 User Classes"),
  table([2200, PAGE_W - 2200], ["User", "Responsibilities"], C.userClasses, { boldFirst: true }),
  spacer(),
  P("Appendix D gives the full role-permission matrix."),
  H2("2.4 Operating Environment"),
  P("Hardware", { r: { bold: true } }),
  table([2600, 3213, 3213], ["Item", "Server (minimum)", "Client (minimum)"], [
    ["Processor", "2 cores", "Dual-core, any modern CPU"],
    ["RAM", "4 GB (8 GB if OCR is used often)", "4 GB"],
    ["Storage", "10 GB plus space for uploaded reports", "Not needed"],
    ["Internet connection", "Needed only for the optional AI model and for access from other computers", "Network access to the server"],
  ]),
  spacer(),
  P("Software", { r: { bold: true } }),
  table([2600, PAGE_W - 2600], ["Component", "Technology"], C.techTable, { boldFirst: true }),
  spacer(),
  H2("2.5 Design and Implementation Constraints"),
  ...bullets([
    "The system must use a relational database (SQLite for development, PostgreSQL for production).",
    "Only authenticated users can use the application; every private function needs a valid token.",
    "Passwords must not be stored as plain text.",
    "The application must work on current versions of Chrome, Edge and Firefox.",
    "Reference ranges must come only from the report; the system must not invent medical values.",
    "The system must not diagnose, predict disease or choose medicine; AI text must pass a safety filter.",
    "Scanned files can be read only if the Tesseract OCR engine is installed on the server.",
  ]),
  H2("2.6 Assumptions and Dependencies"),
  ...bullets([
    "Reports contain results with numbers and units, and usually print a reference range.",
    "Doctors check the system's output before the patient sees it; the system supports the doctor and does not replace the doctor.",
    "The hospital creates all accounts; there is no public registration.",
    "Users have network access to the server, and the database server is available.",
    "Patient information entered at registration is correct.",
    "The optional AI model and Tesseract are separate services; the system works without the AI model.",
  ]),
];

// ---------------------------------------------------------------- 3. Functional requirements
const ch3 = [H1("3. Functional Requirements"), P("The requirements are divided by module. Each requirement has a unique ID, which is used again in the use cases, acceptance criteria and the traceability matrix (chapters 6, 10 and 11).")];
for (const [title, reqs] of C.modules) {
  ch3.push(H2(title));
  for (const [id, text] of reqs) ch3.push(new Paragraph({ spacing: { after: 80, line: 288 }, alignment: AlignmentType.JUSTIFIED, indent: { left: 1000, hanging: 1000 }, children: [run(id + ":", { bold: true, color: BRAND }), run("\t" + text)], tabStops: [{ type: TabStopType.LEFT, position: 1000 }] }));
}

// ---------------------------------------------------------------- 4. Non-functional requirements
const ch4 = [H1("4. Non-Functional Requirements"), P("These describe how well the system should work, rather than what functions it performs.")];
for (const [title, kind, intro, items] of C.nfr) {
  ch4.push(H2(title));
  if (intro) ch4.push(P(intro));
  if (items.length) ch4.push(...bullets(items));
}

// ---------------------------------------------------------------- 5. External interfaces
const ch5 = [
  H1("5. External Interface Requirements"),
  H2("5.1 User Interface"),
  P("The user interface is a responsive web application in a calm teal theme, written for non-technical users. The main screens are listed below. Screenshots of each screen can be inserted in Appendix B."),
  table([3000, PAGE_W - 3000], ["Screen", "What it shows"], C.screens, { boldFirst: true }),
  spacer(),
  P("Common rules for all screens: every page shows the medical disclaimer; status words are written in plain language; dates appear as Today, Tomorrow or 2 hours ago; and long lists are shown as cards or grouped rows instead of dense tables."),
  H2("5.2 Hardware Interface"),
  P("The system needs no special hardware. A user may take a photo of a printed report with a phone camera or use an ordinary scanner and then upload the file. No fingerprint reader, RFID reader, IoT device or GPS device is used."),
  H2("5.3 Software Interface"),
  table([2800, PAGE_W - 2800], ["Software", "Use"], [
    ["SQLite / PostgreSQL", "Stores all data (SQLAlchemy 2 is the access layer)."],
    ["Tesseract OCR (pytesseract)", "Reads text from scanned PDFs and images."],
    ["pypdf, pypdfium2, Pillow", "Read PDF text, render PDF pages and prepare images."],
    ["Optional language model (HTTP API)", "Rewords insights after personal details are removed; the answer is safety-filtered."],
    ["Browser", "Runs the React application."],
  ], { boldFirst: true }),
  spacer(),
  P("No payment gateway, email service, SMS service or map service is used in this version."),
  H2("5.4 Communication Interface"),
  ...bullets([
    "The browser and the server talk over HTTP (HTTPS in production) using a REST API with JSON, under the path /api. The API documents itself at /docs.",
    "Each private request carries a JWT in the Authorization header.",
    "File uploads use multipart form data.",
    "In development the Vite server forwards /api to the backend, so no cross-origin settings are needed.",
    "The server reaches the database and the optional AI model over TCP/IP. No email or SMS communication is used.",
  ]),
];

// ---------------------------------------------------------------- 6. Use case requirements
const ch6 = [
  H1("6. Use Case Requirements"),
  P("Use cases are the link between a requirement and its test, so they are written step by step."),
  H2("6.1 Actors"),
  table([2500, 2300, PAGE_W - 4800], ["Actor", "Who", "Role in the system"], C.actors, { boldFirst: true }),
  spacer(),
  H2("6.2 Use Case Diagram"),
  P("Figure 6.1 shows the use case diagram. Each actor has its own coloured lane; use cases shared by all actors (login, change password, dashboard) are shown in the dashed box."),
  ...figure(C.figures.usecase, 6.2 * 96, 7.0 * 96),
  H2("6.3 Use Case Descriptions"),
];
for (const u of C.useCases) {
  ch6.push(H3(`${u.id}  ${u.name}`));
  ch6.push(kv([["Use Case ID", u.id], ["Use Case", u.name], ["Actor", u.actor], ["Precondition", u.pre], ["Main Flow", u.main], ["Alternative Flow", u.alt], ["Postcondition", u.post]]));
  ch6.push(spacer(160));
}

// ---------------------------------------------------------------- 7. System models
const ch7a = [
  H1("7. System Models"),
  P("The diagrams below show the system from different viewpoints. All of them describe the system as it is built."),
  H2("7.1 Context Diagram"),
  PK("The context diagram shows the whole system as one process, with the people and services that exchange data with it."),
  ...figure(C.figures.context, 6.2 * 96, 6.6 * 96),
  H2("7.2 DFD"),
  PK("Level 0 splits the system into six processes and five data stores."),
  ...figure(C.figures.dfd0, 6.2 * 96, 7.2 * 96),
  PK("Level 1 expands process 3.0 (Report Analysis) into its six steps."),
  ...figure(C.figures.dfd1, 6.2 * 96, 7.2 * 96),
  H2("7.3 Activity Diagram"),
  PK("The swimlane diagram follows a report from upload by the employee, through the system's checks and the doctor's review, to the patient's view and the pharmacy."),
  ...figure(C.figures.activity, 6.2 * 96, 8.0 * 96),
  H2("7.4 Sequence Diagram"),
  PK("The sequence diagram shows the messages between the browser, the server, the analysis engine and the database for the same workflow."),
  ...figure(C.figures.sequence, 6.2 * 96, 7.8 * 96),
];
const ch7b = [
  H2("7.5 Class Diagram"),
  PK("The classes are shown in two parts so that the text stays readable on a normal printed page. Part 1 shows the people and their roles; part 2 shows reports, prescriptions and the pharmacy."),
  ...figure(C.figures.classa, 6.2 * 96, 6.4 * 96),
  ...figure(C.figures.classb, 6.2 * 96, 5.2 * 96),
  H2("7.6 ER Diagram"),
  PK("The 18 tables are shown in two parts. Only the main relationships are drawn; Chapter 8 lists every column."),
  ...figure(C.figures.era, 6.2 * 96, 4.8 * 96),
  ...figure(C.figures.erb, 6.2 * 96, 4.8 * 96),
];

// ---------------------------------------------------------------- 8. Data requirements
const ch8 = [
  H1("8. Data Requirements"),
  P("The system stores its data in 18 relational tables. Every table has an integer primary key named id. A foreign key links a row to its parent. The table below gives a short purpose for each table; the data dictionary then lists every column."),
  H2("8.1 Database Tables"),
  table([2900, PAGE_W - 2900 - 900, 900], ["Table", "Purpose", "Columns"],
    Object.keys(C.schema).map((t) => [t, C.tableInfo[t], String(C.schema[t].length)]), { boldFirst: true }),
  spacer(),
  H2("8.2 Data Dictionary"),
  P("Key: PK = primary key, FK = foreign key (the parent table is named in the description), NULL = may be empty."),
];
const order = ["users", "departments", "doctors", "employees", "pharmacy_staff", "patients", "appointments", "health_reports", "health_parameters", "report_comparisons", "doctor_notes", "doctor_recommendations", "medical_history", "prescriptions", "prescription_items", "medicine_inventory", "medicine_dispensing", "audit_logs"];
order.forEach((t, i) => {
  ch8.push(H3(`8.2.${i + 1} ${t}`));
  ch8.push(table([2300, 1800, 1100, PAGE_W - 5200], ["Field", "Data Type", "Key", "Description"], C.schema[t].map((c) => {
    const key = c.pk ? "PK" : c.fk.length ? "FK" : c.unique ? "Unique" : c.null ? "NULL" : "";
    let d = C.describeCol(t, c.name);
    if (c.fk.length) d = `${d} (${c.fk[0].split(".")[0]})`;
    return [c.name, c.type, key, d];
  }), { size: 19 }));
  ch8.push(spacer(120));
});

// ---------------------------------------------------------------- 9-12
const ch9 = [
  H1("9. System Constraints"),
  P("The following limits apply to the project."),
  ...bullets([
    "Only registered users can use the system; there is no public sign-up, and the five roles are fixed.",
    "Uploaded files may be at most 10 MB and must be PDF, JPG, JPEG, PNG, WEBP (optionally TXT or CSV).",
    "Scanned reports can be read only if the Tesseract OCR engine is installed; otherwise the user gets a clear message.",
    "Accuracy of reading depends on the quality of the file; a poor scan may be rejected.",
    "Ranges come only from the report. A value without a printed range is shown as Unknown, never judged.",
    "The system does not diagnose, predict disease or suggest medicines; it supports the doctor, who stays responsible.",
    "A prescription is valid for 30 days; a prescription with undispensed medicine after that is treated as Expired.",
    "The system depends on the availability of the database. SQLite suits a small installation; PostgreSQL is recommended for many users.",
    "The optional AI model needs an internet connection; without it the system uses its built-in text.",
    "The project is for education and demonstration and is not certified as a medical device.",
    "Only authorised doctors can change clinical content; employees and administrators cannot see clinical values.",
  ]),
];
const ch10 = [
  H1("10. Acceptance Criteria"),
  P("The system is accepted when all of the following can be shown. The last column links each criterion to the functional requirements of chapter 3."),
  table([1500, PAGE_W - 1500 - 1300, 1300], ["Requirement", "Acceptance Criteria", "Related FR"], C.acceptance),
];

// RTM: one row per requirement, with the use case and the test (test names are real pytest functions)
const rtmRows = [];
for (const [, reqs] of C.modules) for (const [id, text, uc, tests] of reqs) {
  const short = text;
  rtmRows.push([id, short, uc, tests.map((t, i) => `TC-${id.slice(3)}${tests.length > 1 ? String.fromCharCode(97 + i) : ""}: ${t}`)]);
}
const ch11 = [
  H1("11. Requirements Traceability Matrix"),
  P("The matrix links each requirement to its use case and to the test that checks it. This gives a direct chain: SRS, use case, design, test case."),
  P("Test cases marked with a test name are automated pytest functions in the backend/tests folder (108 tests in total); they are run with the command pytest. A test case that says 'Manual test' is checked by hand."),
  table([760, 3700, 900, PAGE_W - 5360], ["Req. ID", "Requirement", "Use Case", "Test Case"], rtmRows, { size: 18 }),
];


const appendixB = [
  ["Login page", "login"], ["Admin dashboard", "admin_dashboard"], ["Admin: doctors list (staff management)", "admin_staff"], ["Admin: audit log", "admin_audit"],
  ["Employee dashboard", "employee_dashboard"], ["Employee: register patient", "employee_register"], ["Employee: upload report", "employee_upload"],
  ["Doctor dashboard", "doctor_dashboard"], ["Doctor: report review, key numbers of a laboratory report", "doctor_review_lab"], ["Doctor: report review, key numbers of a Holter report", "doctor_review_holter"], ["Doctor: report review (chest X-ray, insights for the doctor)", "doctor_review_xray"],
  ["Doctor: patient details", "doctor_patient"], ["Doctor: prescriptions", "doctor_prescriptions"], ["Appointments", "appointments"],
  ["Patient dashboard", "patient_dashboard"], ["Patient: my reports", "patient_reports"], ["Patient: reviewed report with tips", "patient_report_detail"],
  ["Patient: health timeline", "patient_history"], ["Patient: my medicines", "patient_prescriptions"],
  ["Pharmacy dashboard", "pharmacy_dashboard"], ["Pharmacy: prescriptions to dispense", "pharmacy_prescriptions"], ["Pharmacy: medicine stock", "pharmacy_inventory"],
].flatMap(([title, f], i) => figure([`Figure B.${i + 1} ${title}`, f + ".png"], 5.4 * 96, 3.5 * 96, "shots_doc"));
const ch12 = [
  H1("12. Appendices"),
  H2("Appendix A: Glossary"),
  P("The terms used in this document are defined in section 1.6. Further terms:"),
  table([2400, PAGE_W - 2400], ["Term", "Meaning"], [
    ["Within / Above / Below / Unknown", "The four statuses of a result: inside the printed range, higher than it, lower than it, or no range printed."],
    ["Waiting for doctor", "A saved report that the doctor has not reviewed yet; the patient cannot see its analysis."],
    ["Reviewed", "A report the doctor has approved, modified or clarified; it becomes visible to the patient."],
    ["Safety filter", "A check that blocks diagnosis, doses and other unsafe wording in automatic text."],
    ["Audit log", "A permanent record of important actions, readable by the administrator."],
    ["Patient code", "A readable patient number printed on registration, for example for searching."],
  ], { boldFirst: true }),
  spacer(),
  H2("Appendix B: Sample Forms and Screens"),
  P("The screens below were captured from the running application with demonstration data (the fictional patient Rahul Patil and demo staff accounts). The list of screens is in section 5.1."),
  ...appendixB,
  spacer(),
  H2("Appendix C: Sample Reports"),
  P("The folder sample_reports in the project holds files for testing and for the demonstration."),
  table([3800, PAGE_W - 3800], ["File", "What it shows"], C.sampleReports, { boldFirst: true }),
  spacer(),
  H2("Appendix D: Role-Permission Matrix"),
  table([3226, 1100, 1100, 1200, 1100, 1300], ["Function", "Admin", "Doctor", "Employee", "Patient", "Pharmacy"], C.permissionMatrix, { size: 18, boldFirst: true }),
  spacer(),
  H2("Appendix E: Database Schema"),
  P("Chapter 8 lists every table and column; Figures 7.8 and 7.9 show the main relationships. The foreign keys of the database are:"),
  table([3400, 2600, PAGE_W - 6000], ["Table", "Column", "Refers to"],
    order.flatMap((t) => C.schema[t].filter((c) => c.fk.length).map((c) => [t, c.name, c.fk[0].replace(".", " . ")])), { size: 18 }),
  P("The complete SQL script is in backend/schema.sql of the project."),
  spacer(),
  pageBreak(),
  H2("Appendix F: Sample Questionnaire"),
  P("This is a sample form for the user-acceptance survey. It has not been used yet, and no answers are reported in this document."),
  table([600, PAGE_W - 600 - 3300, 3300], ["No.", "Statement", "1 (disagree) ... 5 (agree)"], C.questionnaire.map((q, i) => [String(i + 1), q, "1    2    3    4    5"])),
  spacer(),
  H2("Appendix G: References"),
  P("See section 1.7."),
];

// ---------------------------------------------------------------- document
const hdr = (txt) => new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: BRAND, space: 4 } }, children: [run(txt, { size: 18, color: "5B6B78" })] })] });
const ftr = () => new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [run("Page ", { size: 18, color: "5B6B78" }), new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 18, color: "5B6B78" })] })] });
const A4P = { page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, bottom: 1300, left: 1440, right: 1440, header: 600, footer: 500 } } };
const A4L = { page: { size: { width: 11906, height: 16838, orientation: PageOrientation.LANDSCAPE }, margin: { top: 900, bottom: 800, left: 1000, right: 1000, header: 400, footer: 350 } } };
const hd = hdr("HealthWise AI: Software Requirements Specification");

const doc = new Document({
  creator: "HealthWise AI project team",
  title: "HealthWise AI: Software Requirements Specification",
  description: "SRS in the college format",
  styles: {
    default: { document: { run: { font: FONT, size: 24 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FONT, size: 34, bold: true, color: BRAND }, paragraph: { spacing: { before: 0, after: 220 }, keepNext: true, pageBreakBefore: true, outlineLevel: 0, border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: BRAND, space: 4 } } } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FONT, size: 28, bold: true, color: DARK }, paragraph: { spacing: { before: 280, after: 120 }, keepNext: true, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FONT, size: 25, bold: true, color: BRAND }, paragraph: { spacing: { before: 200, after: 100 }, keepNext: true, outlineLevel: 2 } },
    ],
  },
  numbering: {
    config: [
      { reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      ...["obj", "ref"].map((r) => ({ reference: r, levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 400 } } } }] })),
    ],
  },
  sections: [
    { properties: { ...A4P, titlePage: true }, children: cover },
    { properties: { ...A4P, page: { ...A4P.page, pageNumbers: { start: 1, formatType: NumberFormat.LOWER_ROMAN } } }, headers: { default: hd }, footers: { default: ftr() }, children: certificate },
    { properties: { ...A4P, page: { ...A4P.page, pageNumbers: { start: 1, formatType: NumberFormat.DECIMAL } } }, headers: { default: hd }, footers: { default: ftr() },
      children: [...ch1, ...ch2, ...ch3, ...ch4, ...ch5, ...ch6, ...ch7a, ...ch7b, ...ch8, ...ch9, ...ch10, ...ch11, ...ch12] },
  ],
});

Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(__dirname + "/HealthWise_AI_SRS.docx", buf); console.log("written", buf.length); });
