import { BedDouble, ListOrdered, Siren, Share2, UserCheck, CircleUser, Briefcase, CalendarClock, ClipboardList, ReceiptText, FileSearch, FlaskConical, Plug, ScanLine, BadgeCheck, Boxes, Droplets, Scissors, Warehouse, FileText, GraduationCap, History, Hospital as HospitalIcon, Send, ShieldAlert, LayoutDashboard, ListChecks, MessageCircle, NotebookPen, Package, Pill, ScrollText, Settings, Stethoscope, Upload, UserPlus, UserRound, Users } from "lucide-react";

// Icon lookup (only the icons used in menus are bundled).
export const ICONS = { Plug, Boxes, Droplets, Scissors, Warehouse, ScanLine, BadgeCheck, BedDouble, ListOrdered, Siren, Share2, UserCheck, CircleUser, Briefcase, CalendarClock, ClipboardList, ReceiptText, FileSearch, FlaskConical, FileText, GraduationCap, History, HospitalIcon, Send, ShieldAlert, LayoutDashboard, ListChecks, MessageCircle, NotebookPen, Package, Pill, ScrollText, Settings, Stethoscope, Upload, UserPlus, UserRound, Users };

// Sidebar menu for each role: [path, label, icon name]. The backend enforces the same permissions.
export const NAV = {
  ADMIN: [
    ["/admin", "Dashboard", "LayoutDashboard"],
    ["/admin/users", "People", "Users"],
    ["/admin/doctors", "Doctors", "Stethoscope"],
    ["/admin/employees", "Employees", "Briefcase"],
    ["/admin/pharmacy-staff", "Pharmacy Staff", "Pill"],
    ["/admin/lab-staff", "Laboratory Staff", "FlaskConical"],
    ["/admin/integrations", "Integrations", "Plug"],
    ["/admin/radiology-staff", "Radiology Staff", "ScanLine"],
    ["/admin/nurses", "Nurses", "Stethoscope"],
    ["/admin/patients", "Patients", "UserRound"],
    ["/admin/appointments", "Appointments", "CalendarClock"],
    ["/admin/reports", "Reports", "FileText"],
    ["/admin/audit-logs", "Activity Log", "ScrollText"],
    ["/admin/hospital", "Hospital", "HospitalIcon"],
    ["/admin/settings", "Settings", "Settings"],
    ["/admin/profile", "My Profile", "CircleUser"],
  ],
  DOCTOR: [
    ["/doctor", "Dashboard", "LayoutDashboard"],
    ["/doctor/patients", "My Patients", "UserRound"],
    ["/doctor/appointments", "Appointments", "CalendarClock"],
    ["/doctor/queue", "Today's Queue", "ListOrdered"],
    ["/doctor/inpatients", "Inpatients", "BedDouble"],
    ["/doctor/emergency", "Emergency", "Siren"],
    ["/doctor/referral-requests", "Referral requests", "Share2"],
    ["/doctor/beds", "Bed board", "BedDouble"],
    ["/doctor/referrals", "Trainee Referrals", "Send"],
    ["/doctor/emergency-access", "Emergency access", "ShieldAlert"],
    ["/doctor/reports", "Reports to Review", "FileSearch"],
    ["/doctor/notes", "Doctor Notes", "NotebookPen"],
    ["/doctor/recommendations", "Recommendations", "ListChecks"],
    ["/doctor/prescriptions", "Prescriptions", "Pill"],
  ],
  EMPLOYEE: [
    ["/employee", "Dashboard", "LayoutDashboard"],
    ["/employee/patients", "Patients", "UserRound"],
    ["/employee/opd", "OPD desk", "UserCheck"],
    ["/employee/emergency", "Emergency", "Siren"],
    ["/employee/beds", "Bed board", "BedDouble"],
    ["/employee/register", "Register Patient", "UserPlus"],
    ["/employee/upload", "Upload Report", "Upload"],
    ["/employee/appointments", "Appointments", "CalendarClock"],
    ["/employee/reports", "Reports", "FileText"],
    ["/employee/tests", "Tests Advised", "FlaskConical"],
    ["/employee/profile", "My Profile", "CircleUser"],
  ],
  PATIENT: [
    ["/patient", "Dashboard", "LayoutDashboard"],
    ["/patient/assistant", "Ask HealthWise", "MessageCircle"],
    ["/patient/health-history", "My Health History", "ClipboardList"],
    ["/patient/reports", "My Reports", "FileText"],
    ["/patient/bills", "My Bills", "ReceiptText"],
    ["/patient/history", "My Timeline", "History"],
    ["/patient/notes", "Doctor's Notes", "NotebookPen"],
    ["/patient/recommendations", "Doctor's Advice", "ListChecks"],
    ["/patient/prescriptions", "My Medicines", "Pill"],
    ["/patient/appointments", "Appointments", "CalendarClock"],
    ["/patient/profile", "My Profile", "CircleUser"],
  ],
  PHARMACY: [
    ["/pharmacy", "Dashboard", "LayoutDashboard"],
    ["/pharmacy/billing", "Sell & Bill", "ReceiptText"],
    ["/pharmacy/bills", "Bills", "FileText"],
    ["/pharmacy/prescriptions", "Prescriptions", "ClipboardList"],
    ["/pharmacy/history", "Medicine History", "History"],
    ["/pharmacy/inventory", "Medicine Stock", "Package"],
    ["/pharmacy/profile", "My Profile", "CircleUser"],
  ],
  NURSE: [
    ["/nurse", "Ward worklist", "ClipboardList"],
    ["/nurse/emergency", "Emergency", "Siren"],
    ["/nurse/beds", "Bed board", "BedDouble"],
    ["/nurse/profile", "My Profile", "CircleUser"],
  ],
  RADIOLOGY: [
    ["/radiology", "Scan work list", "ScanLine"],
    ["/radiology/profile", "My Profile", "CircleUser"],
  ],
  LAB: [
    ["/lab", "Work list", "FlaskConical"],
    ["/lab/approvals", "Approvals", "BadgeCheck"],
    ["/lab/advised", "Tests advised", "ClipboardList"],
    ["/lab/profile", "My Profile", "CircleUser"],
  ],
};

export const ROLE_LABEL = { ADMIN: "Admin", DOCTOR: "Doctor", EMPLOYEE: "Hospital Employee", PATIENT: "Patient", PHARMACY: "Pharmacy staff", LAB: "Laboratory staff", NURSE: "Nurse", RADIOLOGY: "Radiology staff" };

// Menu items added to the doctor menu by grade: a junior doctor gets the history and referral workspace, a consultant gets the countersign queue.
export const JUNIOR_MENU = [
  ["/trainee", "My Work", "ClipboardList"],
  ["/trainee/take-history", "Take History", "FileText"],
  ["/trainee/referrals", "My Referrals", "Send"],
  ["/doctor/countersign", "Pending Approval", "ListChecks"],
];
export const CONSULTANT_MENU = [["/doctor/countersign", "Awaiting my countersign", "ListChecks"]];

// Pages that follow what a person may do (their permissions), whatever login they use: [permissions that open it, path, label, icon].
export const PERMISSION_MENU = [
  [["stock.view", "stock.manage"], "/stock", "Stock control", "Boxes"],
  [["procure.request", "procure.order", "procure.approve", "inventory.manage"], "/procurement", "Procurement", "Warehouse"],
  [["ot.view", "ot.schedule", "ot.record"], "/ot", "Operation theatre", "Scissors"],
  [["bloodbank.manage"], "/bloodbank", "Blood bank", "Droplets"],
  [["transfusion.give"], "/transfusions", "Transfusions", "Droplets"],
  [["nursing.chart", "ipd.notes"], "/ward-requests", "Medicines for ward", "Pill"],
  [["billing.view", "billing.create", "billing.collect", "billing.approve"], "/billing", "Billing", "ReceiptText"],
  [["claims.manage"], "/claims", "Insurance claims", "ShieldAlert"],
  [["billing.report"], "/finance-reports", "Finance reports", "ScrollText"],
];

/** The sidebar of a person: their role menu, the extra items of a doctor's grade, and the pages their permissions open. */
export function menuFor(user) {
  let menu = NAV[user.role] || [];
  if (user.role === "DOCTOR") {
    const extra = !user.grade || user.grade === "CONSULTANT" ? CONSULTANT_MENU : JUNIOR_MENU;
    menu = [...menu.slice(0, 1), ...extra, ...menu.slice(1)];
  }
  const mine = user.permissions || [];
  const have = new Set(menu.map(([to]) => to));
  const added = PERMISSION_MENU.filter(([perms, to]) => perms.some((p) => mine.includes(p)) && !have.has(to)).map(([, to, label, icon]) => [to, label, icon]);
  return added.length === 0 ? menu : [...menu.slice(0, -1), ...added, ...menu.slice(-1)];
}
