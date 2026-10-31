import { CircleUser, Briefcase, CalendarClock, ClipboardList, ReceiptText, FileSearch, FlaskConical, FileText, GraduationCap, History, Send, LayoutDashboard, ListChecks, MessageCircle, NotebookPen, Package, Pill, ScrollText, Settings, Stethoscope, Upload, UserPlus, UserRound, Users } from "lucide-react";

// Icon lookup (only the icons used in menus are bundled).
export const ICONS = { CircleUser, Briefcase, CalendarClock, ClipboardList, ReceiptText, FileSearch, FlaskConical, FileText, GraduationCap, History, Send, LayoutDashboard, ListChecks, MessageCircle, NotebookPen, Package, Pill, ScrollText, Settings, Stethoscope, Upload, UserPlus, UserRound, Users };

// Sidebar menu for each role: [path, label, icon name]. The backend enforces the same permissions.
export const NAV = {
  ADMIN: [
    ["/admin", "Dashboard", "LayoutDashboard"],
    ["/admin/users", "People", "Users"],
    ["/admin/doctors", "Doctors", "Stethoscope"],
    ["/admin/employees", "Employees", "Briefcase"],
    ["/admin/pharmacy-staff", "Pharmacy Staff", "Pill"],
    ["/admin/lab-staff", "Laboratory Staff", "FlaskConical"],
    ["/admin/trainees", "Interns & PG", "GraduationCap"],
    ["/admin/patients", "Patients", "UserRound"],
    ["/admin/appointments", "Appointments", "CalendarClock"],
    ["/admin/reports", "Reports", "FileText"],
    ["/admin/audit-logs", "Activity Log", "ScrollText"],
    ["/admin/settings", "Settings", "Settings"],
    ["/admin/profile", "My Profile", "CircleUser"],
  ],
  DOCTOR: [
    ["/doctor", "Dashboard", "LayoutDashboard"],
    ["/doctor/patients", "My Patients", "UserRound"],
    ["/doctor/appointments", "Appointments", "CalendarClock"],
    ["/doctor/referrals", "Trainee Referrals", "Send"],
    ["/doctor/reports", "Reports to Review", "FileSearch"],
    ["/doctor/notes", "Doctor Notes", "NotebookPen"],
    ["/doctor/recommendations", "Recommendations", "ListChecks"],
    ["/doctor/prescriptions", "Prescriptions", "Pill"],
  ],
  EMPLOYEE: [
    ["/employee", "Dashboard", "LayoutDashboard"],
    ["/employee/patients", "Patients", "UserRound"],
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
  TRAINEE: [
    ["/trainee", "Dashboard", "LayoutDashboard"],
    ["/trainee/take-history", "Take History", "ClipboardList"],
    ["/trainee/referrals", "My Referrals", "Send"],
    ["/trainee/profile", "My Profile", "CircleUser"],
  ],
  LAB: [
    ["/lab", "Work list", "FlaskConical"],
    ["/lab/advised", "Tests advised", "ClipboardList"],
    ["/lab/profile", "My Profile", "CircleUser"],
  ],
};

export const ROLE_LABEL = { ADMIN: "Admin", DOCTOR: "Doctor", EMPLOYEE: "Hospital Employee", PATIENT: "Patient", PHARMACY: "Pharmacy staff", LAB: "Laboratory staff", TRAINEE: "Intern / PG student" };
