import { Navigate, Route, Routes } from "react-router-dom";
import { ROLE_HOME, useAuth } from "./context/AuthContext";
import ProtectedRoute from "./routes/ProtectedRoute";
import RoleRoute from "./routes/RoleRoute";
import Layout from "./components/Layout";

import Login from "./pages/auth/Login";
import Register from "./pages/auth/Register";
import ChangePassword from "./pages/auth/ChangePassword";
import Profile from "./pages/shared/Profile";
import MyHealthHistory from "./pages/patient/MyHealthHistory";
import PatientAssistant from "./pages/patient/Assistant";
import TakeHistory from "./pages/doctor/TakeHistory";
import EmergencyCardPage from "./pages/patient/EmergencyCardPage";

import Appointments from "./pages/shared/Appointments";
import PatientsList from "./pages/shared/PatientsList";
import ReportsList from "./pages/shared/ReportsList";
import ReportDetails from "./pages/shared/ReportDetails";

import AdminDashboard from "./pages/admin/Dashboard";
import Users from "./pages/admin/Users";
import StaffManager from "./pages/admin/StaffManager";
import AuditLogs from "./pages/admin/AuditLogs";
import Settings from "./pages/admin/Settings";

import DoctorDashboard from "./pages/doctor/Dashboard";
import PatientDetails from "./pages/doctor/PatientDetails";
import ReportReview from "./pages/doctor/ReportReview";
import DoctorNotes from "./pages/doctor/DoctorNotes";
import DoctorRecommendations from "./pages/doctor/Recommendations";
import DoctorPrescriptions from "./pages/doctor/Prescriptions";

import EmployeeDashboard from "./pages/employee/Dashboard";
import RegisterPatient from "./pages/employee/RegisterPatient";
import UploadReport from "./pages/employee/UploadReport";

import PatientDashboard from "./pages/patient/Dashboard";
import MyReports from "./pages/patient/MyReports";
import HealthHistory from "./pages/patient/HealthHistory";
import PatientNotes from "./pages/patient/DoctorNotes";
import PatientRecommendations from "./pages/patient/Recommendations";
import PatientPrescriptions from "./pages/patient/Prescriptions";

import TestOrders from "./pages/lab/TestOrders";
import LabWorklist from "./pages/lab/Worklist";
import TraineeDashboard from "./pages/trainee/Dashboard";
import TraineeTakeHistory from "./pages/trainee/TakeHistory";
import TraineeSelectDoctor from "./pages/trainee/SelectDoctor";
import TraineeReferrals from "./pages/trainee/MyReferrals";
import DoctorReferrals from "./pages/doctor/Referrals";
import EmergencyAccess from "./pages/doctor/EmergencyAccess";
import Hospital from "./pages/admin/Hospital";
import OpdDesk from "./pages/employee/OpdDesk";
import OpdQueue from "./pages/doctor/OpdQueue";
import Consultation from "./pages/doctor/Consultation";
import Inpatients, { InpatientDetail } from "./pages/doctor/Inpatients";
import ReferralRequests from "./pages/doctor/ReferralRequests";
import Emergency from "./pages/shared/Emergency";
import Beds from "./pages/shared/Beds";
import { NurseChart, NurseDashboard } from "./pages/nurse/Nurse";
import PharmacyDashboard from "./pages/pharmacy/Dashboard";
import Billing from "./pages/pharmacy/Billing";
import Bills from "./pages/pharmacy/Bills";
import PharmacyPrescriptions from "./pages/pharmacy/Prescriptions";
import Dispensing from "./pages/pharmacy/Dispensing";
import DispensingHistory from "./pages/pharmacy/DispensingHistory";
import Inventory from "./pages/pharmacy/Inventory";

function HomeRedirect() {
  const { user } = useAuth();
  return <Navigate to={ROLE_HOME[user.role]} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      <Route element={<ProtectedRoute />}>
        <Route path="/change-password" element={<ChangePassword />} />
        <Route path="/emergency-card" element={<RoleRoute roles={["PATIENT"]} />}>
          <Route index element={<EmergencyCardPage />} />
        </Route>
        <Route element={<Layout />}>
          <Route path="/" element={<HomeRedirect />} />

          <Route path="/admin" element={<RoleRoute roles={["ADMIN"]} />}>
            <Route index element={<AdminDashboard />} />
            <Route path="users" element={<Users />} />
            <Route path="doctors" element={<StaffManager kind="doctors" />} />
            <Route path="employees" element={<StaffManager kind="employees" />} />
            <Route path="pharmacy-staff" element={<StaffManager kind="pharmacy-staff" />} />
            <Route path="lab-staff" element={<StaffManager kind="lab-staff" />} />
            <Route path="trainees" element={<StaffManager kind="trainees" />} />
            <Route path="nurses" element={<StaffManager kind="nurses" />} />
            <Route path="beds" element={<Beds />} />
            <Route path="profile" element={<Profile />} />
            <Route path="patients" element={<PatientsList />} />
            <Route path="appointments" element={<Appointments />} />
            <Route path="reports" element={<ReportsList base="/admin/reports" title="Reports" subtitle="Report status only. Clinical values are visible to doctors and the patient." />} />
            <Route path="reports/:id" element={<ReportDetails />} />
            <Route path="audit-logs" element={<AuditLogs />} />
            <Route path="settings" element={<Settings />} />
            <Route path="hospital" element={<Hospital />} />
          </Route>

          <Route path="/doctor" element={<RoleRoute roles={["DOCTOR"]} />}>
            <Route index element={<DoctorDashboard />} />
            <Route path="patients" element={<PatientsList />} />
            <Route path="patients/:id" element={<PatientDetails />} />
            <Route path="patients/:id/take-history" element={<TakeHistory />} />
            <Route path="appointments" element={<Appointments />} />
            <Route path="reports" element={<ReportsList base="/doctor/reports" pendingOnly title="Reports to Review" subtitle="Reports waiting for your review" />} />
            <Route path="reports/:id" element={<ReportReview />} />
            <Route path="referrals" element={<DoctorReferrals />} />
            <Route path="emergency-access" element={<EmergencyAccess />} />
            <Route path="queue" element={<OpdQueue />} />
            <Route path="consultation/:encounterId" element={<Consultation />} />
            <Route path="inpatients" element={<Inpatients />} />
            <Route path="inpatients/:id" element={<InpatientDetail />} />
            <Route path="emergency" element={<Emergency />} />
            <Route path="referral-requests" element={<ReferralRequests />} />
            <Route path="beds" element={<Beds />} />
            <Route path="notes" element={<DoctorNotes />} />
            <Route path="recommendations" element={<DoctorRecommendations />} />
            <Route path="prescriptions" element={<DoctorPrescriptions />} />
            <Route path="profile" element={<Profile />} />
          </Route>

          <Route path="/employee" element={<RoleRoute roles={["EMPLOYEE"]} />}>
            <Route index element={<EmployeeDashboard />} />
            <Route path="patients" element={<PatientsList />} />
            <Route path="opd" element={<OpdDesk />} />
            <Route path="emergency" element={<Emergency />} />
            <Route path="beds" element={<Beds />} />
            <Route path="register" element={<RegisterPatient />} />
            <Route path="upload" element={<UploadReport />} />
            <Route path="appointments" element={<Appointments />} />
            <Route path="reports" element={<ReportsList base="/employee/reports" title="Reports" subtitle="Upload status of reports. Clinical values are visible to the doctor and the patient." />} />
            <Route path="reports/:id" element={<ReportDetails />} />
            <Route path="tests" element={<TestOrders />} />
            <Route path="profile" element={<Profile />} />
          </Route>

          <Route path="/nurse" element={<RoleRoute roles={["NURSE"]} />}>
            <Route index element={<NurseDashboard />} />
            <Route path="chart/:id" element={<NurseChart />} />
            <Route path="emergency" element={<Emergency />} />
            <Route path="beds" element={<Beds />} />
            <Route path="profile" element={<Profile />} />
          </Route>

          <Route path="/trainee" element={<RoleRoute roles={["TRAINEE"]} />}>
            <Route index element={<TraineeDashboard />} />
            <Route path="take-history" element={<TraineeTakeHistory />} />
            <Route path="take-history/:patientId" element={<TraineeTakeHistory />} />
            <Route path="select-doctor/:historyId" element={<TraineeSelectDoctor />} />
            <Route path="referrals" element={<TraineeReferrals />} />
            <Route path="profile" element={<Profile />} />
          </Route>

          <Route path="/lab" element={<RoleRoute roles={["LAB"]} />}>
            <Route index element={<LabWorklist />} />
            <Route path="advised" element={<TestOrders />} />
            <Route path="profile" element={<Profile />} />
          </Route>

          <Route path="/patient" element={<RoleRoute roles={["PATIENT"]} />}>
            <Route index element={<PatientDashboard />} />
            <Route path="reports" element={<MyReports />} />
            <Route path="reports/:id" element={<ReportDetails />} />
            <Route path="history" element={<HealthHistory />} />
            <Route path="assistant" element={<PatientAssistant />} />
            <Route path="health-history" element={<MyHealthHistory />} />
            <Route path="notes" element={<PatientNotes />} />
            <Route path="recommendations" element={<PatientRecommendations />} />
            <Route path="prescriptions" element={<PatientPrescriptions />} />
            <Route path="appointments" element={<Appointments />} />
            <Route path="profile" element={<Profile />} />
          </Route>

          <Route path="/pharmacy" element={<RoleRoute roles={["PHARMACY"]} />}>
            <Route index element={<PharmacyDashboard />} />
            <Route path="billing" element={<Billing />} />
            <Route path="profile" element={<Profile />} />
            <Route path="bills" element={<Bills />} />
            <Route path="prescriptions" element={<PharmacyPrescriptions />} />
            <Route path="dispensing/:id" element={<Dispensing />} />
            <Route path="history" element={<DispensingHistory />} />
            <Route path="inventory" element={<Inventory />} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
