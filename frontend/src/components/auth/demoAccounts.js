// The demo accounts of the sample hospital (shown on the login page only while running `npm run dev`, never in a production build).
// One shared demo password. Each account also has a fake mobile number so the "mobile code" sign-in can be tried.
export const DEMO_PASSWORD = "Demo@12345";

export const DEMO_GROUPS = [
  ["Care team", [
    ["Patient", "Rahul Patil", "rahul.patil@healthwise.demo.com", "9000000001"],
    ["Consultant", "Dr. Anjali Sharma", "anjali.sharma@healthwise.demo.com", "9000000101"],
    ["PG resident", "Dr. Arjun Deshmukh", "pg.student@healthwise.demo.com", "9000000107"],
    ["Intern", "Neha Kulkarni", "intern@healthwise.demo.com", "9000000106"],
    ["Nurse", "Meera Pawar", "nurse@healthwise.demo.com", "9000000105"],
  ]],
  ["Front desk and finance", [
    ["Reception", "Priya Joshi", "priya.joshi@healthwise.demo.com", "9000000102"],
    ["Billing", "Bina Shah", "billing@healthwise.demo.com", "9000000115"],
    ["Billing 2", "Bhanu Mehta", "billing2@healthwise.demo.com", "9000000116"],
    ["Accountant", "Asha Nair", "accounts@healthwise.demo.com", "9000000117"],
    ["Insurance / TPA", "Indu Verma", "tpa@healthwise.demo.com", "9000000118"],
  ]],
  ["Diagnostics", [
    ["Lab technician", "City Lab Technician", "lab@healthwise.demo.com", "9000000104"],
    ["Pathologist", "Dr. Kavita Rane", "pathologist@healthwise.demo.com", "9000000108"],
    ["Radiology tech", "Sunil Gaikwad", "radiology.tech@healthwise.demo.com", "9000000109"],
    ["Radiologist", "Dr. Vikram Nair", "radiologist@healthwise.demo.com", "9000000110"],
  ]],
  ["Pharmacy, stores, theatre, blood", [
    ["Pharmacy", "MediCare Pharmacy Staff", "pharmacy@healthwise.demo.com", "9000000103"],
    ["Store manager", "Ila Joshi", "inventory@healthwise.demo.com", "9000000111"],
    ["OT staff", "Omkar Patil", "ot@healthwise.demo.com", "9000000112"],
    ["Blood bank", "Bela Kulkarni", "bloodbank@healthwise.demo.com", "9000000113"],
    ["Blood bank 2", "Bimal Rao", "bloodbank2@healthwise.demo.com", "9000000114"],
  ]],
  ["Administration", [
    ["Admin", "Hospital Admin", "admin@healthwise.demo.com", "9000000100"],
  ]],
];
export const ALL_DEMO = DEMO_GROUPS.flatMap(([group, rows]) => rows.map(([role, name, email, phone]) => ({ group, role, name, email, phone })));
