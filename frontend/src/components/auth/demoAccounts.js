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
    ["Nurse 2", "Kavya Naik", "nurse2@healthwise.demo.com", "9000000123"],
  ]],
  ["Doctors by department", [
    ["Cardiology", "Dr. Kavya Menon", "kavya.menon@healthwise.demo.com", "9000000202"],
    ["Cardiology", "Dr. Rohan Mehta", "rohan.mehta@healthwise.demo.com", "9000000121"],
    ["Cardiology (Senior resident)", "Dr. Tarun Bose", "tarun.bose@healthwise.demo.com", "9000000203"],
    ["Dentistry", "Dr. Zoya Fernandes", "zoya.fernandes@healthwise.demo.com", "9000000220"],
    ["Dermatology", "Dr. Siddharth Malhotra", "siddharth.malhotra@healthwise.demo.com", "9000000210"],
    ["ENT", "Dr. Deepa Chandran", "deepa.chandran@healthwise.demo.com", "9000000211"],
    ["Emergency Medicine", "Dr. Naveen Reddy", "naveen.reddy@healthwise.demo.com", "9000000223"],
    ["Endocrinology", "Dr. Mitali Ghosh", "mitali.ghosh@healthwise.demo.com", "9000000218"],
    ["Gastroenterology", "Dr. Ganesh Pawar", "ganesh.pawar@healthwise.demo.com", "9000000215"],
    ["General Medicine", "Dr. Sana Khan", "sana.khan@healthwise.demo.com", "9000000122"],
    ["General Medicine", "Dr. Vivek Oak", "vivek.oak@healthwise.demo.com", "9000000201"],
    ["General Surgery", "Dr. Prakash Wagh", "prakash.wagh@healthwise.demo.com", "9000000224"],
    ["General Surgery", "Dr. Sunita Kamat", "sunita.kamat@healthwise.demo.com", "9000000225"],
    ["Gynecology & Obstetrics", "Dr. Lakshmi Narayanan", "lakshmi.narayanan@healthwise.demo.com", "9000000209"],
    ["Nephrology", "Dr. Tanvi Desai", "tanvi.desai@healthwise.demo.com", "9000000216"],
    ["Neurology", "Dr. Aarav Iyer", "aarav.iyer@healthwise.demo.com", "9000000204"],
    ["Neurology (PG resident)", "Dr. Nisha Pillai", "nisha.pillai@healthwise.demo.com", "9000000205"],
    ["Oncology", "Dr. Rajeev Nambiar", "rajeev.nambiar@healthwise.demo.com", "9000000219"],
    ["Ophthalmology", "Dr. Manoj Varma", "manoj.varma@healthwise.demo.com", "9000000212"],
    ["Orthopedics", "Dr. Harpreet Gill", "harpreet.gill@healthwise.demo.com", "9000000206"],
    ["Pathology", "Dr. Charu Mittal", "charu.mittal@healthwise.demo.com", "9000000222"],
    ["Pediatrics", "Dr. Ananya Rao", "ananya.rao@healthwise.demo.com", "9000000207"],
    ["Pediatrics (Senior resident)", "Dr. Pooja Hegde", "pooja.hegde@healthwise.demo.com", "9000000208"],
    ["Psychiatry", "Dr. Shruti Banerjee", "shruti.banerjee@healthwise.demo.com", "9000000213"],
    ["Pulmonology", "Dr. Yash Saxena", "yash.saxena@healthwise.demo.com", "9000000214"],
    ["Radiology", "Dr. Abhay Joglekar", "abhay.joglekar@healthwise.demo.com", "9000000221"],
    ["Urology", "Dr. Kunal Bhide", "kunal.bhide@healthwise.demo.com", "9000000217"],
  ]],
  ["More patients", [
    ["Patient", "Sneha Kulkarni", "sneha.kulkarni@healthwise.demo.com", "9822200011"],
    ["Patient", "Mohan Deshpande", "mohan.deshpande@healthwise.demo.com", "9822200021"],
    ["Patient", "Farida Shaikh", "farida.shaikh@healthwise.demo.com", "9822200031"],
    ["Patient", "Kiran Rao", "kiran.rao@healthwise.demo.com", "9822200041"],
    ["Patient", "Lata Pawar", "lata.pawar@healthwise.demo.com", "9822200051"],
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
