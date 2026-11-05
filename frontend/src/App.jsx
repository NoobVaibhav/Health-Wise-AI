import { Suspense, lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { ROLE_HOME, useAuth } from "./context/AuthContext";
import ProtectedRoute from "./routes/ProtectedRoute";
import RoleRoute from "./routes/RoleRoute";
import Layout from "./components/Layout";
import { Loading } from "./components/Feedback";

import Login from "./pages/auth/Login";
const Register = lazy(() => import("./pages/auth/Register"));
const ChangePassword = lazy(() => import("./pages/auth/ChangePassword"));
const Profile = lazy(() => import("./pages/shared/Profile"));
const MyHealthHistory = lazy(() => import("./pages/patient/MyHealthHistory"));
const PatientAssistant = lazy(() => import("./pages/patient/Assistant"));
const TakeHistory = lazy(() => import("./pages/doctor/TakeHistory"));
const EmergencyCardPage = lazy(() => import("./pages/patient/EmergencyCardPage"));

const Appointments = lazy(() => import("./pages/shared/Appointments"));
const PatientsList = lazy(() => import("./pages/shared/PatientsList"));
const ReportsList = lazy(() => import("./pages/shared/ReportsList"));
const ReportDetails = lazy(() => import("./pages/shared/ReportDetails"));

const AdminDashboard = lazy(() => import("./pages/admin/Dashboard"));
const Users = lazy(() => import("./pages/admin/Users"));
const StaffManager = lazy(() => import("./pages/admin/StaffManager"));
const AuditLogs = lazy(() => import("./pages/admin/AuditLogs"));
const Settings = lazy(() => import("./pages/admin/Settings"));

const DoctorDashboard = lazy(() => import("./pages/doctor/Dashboard"));
const PatientDetails = lazy(() => import("./pages/doctor/PatientDetails"));
const ReportReview = lazy(() => import("./pages/doctor/ReportReview"));
const DoctorNotes = lazy(() => import("./pages/doctor/DoctorNotes"));
const DoctorRecommendations = lazy(() => import("./pages/doctor/Recommendations"));
const DoctorPrescriptions = lazy(() => import("./pages/doctor/Prescriptions"));

const EmployeeDashboard = lazy(() => import("./pages/employee/Dashboard"));
const RegisterPatient = lazy(() => import("./pages/employee/RegisterPatient"));
const UploadReport = lazy(() => import("./pages/employee/UploadReport"));

const PatientDashboard = lazy(() => import("./pages/patient/Dashboard"));
const MyReports = lazy(() => import("./pages/patient/MyReports"));
const HealthHistory = lazy(() => import("./pages/patient/HealthHistory"));
const PatientNotes = lazy(() => import("./pages/patient/DoctorNotes"));
const PatientRecommendations = lazy(() => import("./pages/patient/Recommendations"));
const PatientPrescriptions = lazy(() => import("./pages/patient/Prescriptions"));

const TestOrders = lazy(() => import("./pages/lab/TestOrders"));
const LabWorklist = lazy(() => import("./pages/lab/Worklist"));
const LabApprovals = lazy(() => import("./pages/lab/Approvals"));
const RadiologyWorklist = lazy(() => import("./pages/radiology/Worklist"));
import PermissionRoute from "./routes/PermissionRoute";
const StockControl = lazy(() => import("./pages/stock/StockControl"));
const Procurement = lazy(() => import("./pages/stock/Procurement"));
const WardRequests = lazy(() => import("./pages/stock/WardRequests"));
const OtSchedule = lazy(() => import("./pages/ot/Schedule"));
const BloodBank = lazy(() => import("./pages/bloodbank/BloodBank"));
const Transfusions = lazy(() => import("./pages/bloodbank/Transfusions"));
const FinanceBilling = lazy(() => import("./pages/finance/Billing"));
const Claims = lazy(() => import("./pages/finance/Claims"));
const FinanceReports = lazy(() => import("./pages/finance/FinanceReports"));
const MyBills = lazy(() => import("./pages/patient/MyBills"));
const Integrations = lazy(() => import("./pages/admin/Integrations"));
const TraineeDashboard = lazy(() => import("./pages/trainee/Dashboard"));
const TraineeTakeHistory = lazy(() => import("./pages/trainee/TakeHistory"));
const TraineeSelectDoctor = lazy(() => import("./pages/trainee/SelectDoctor"));
const TraineeReferrals = lazy(() => import("./pages/trainee/MyReferrals"));
const DoctorReferrals = lazy(() => import("./pages/doctor/Referrals"));
const EmergencyAccess = lazy(() => import("./pages/doctor/EmergencyAccess"));
const Hospital = lazy(() => import("./pages/admin/Hospital"));
const OpdDesk = lazy(() => import("./pages/employee/OpdDesk"));
const OpdQueue = lazy(() => import("./pages/doctor/OpdQueue"));
const Consultation = lazy(() => import("./pages/doctor/Consultation"));
import Inpatients, { InpatientDetail } from "./pages/doctor/Inpatients";
const ReferralRequests = lazy(() => import("./pages/doctor/ReferralRequests"));
const Countersign = lazy(() => import("./pages/doctor/Countersign"));
const Emergency = lazy(() => import("./pages/shared/Emergency"));
const Beds = lazy(() => import("./pages/shared/Beds"));
import { NurseChart, NurseDashboard } from "./pages/nurse/Nurse";
const PharmacyDashboard = lazy(() => import("./pages/pharmacy/Dashboard"));
const Billing = lazy(() => import("./pages/pharmacy/Billing"));
const Bills = lazy(() => import("./pages/pharmacy/Bills"));
const PharmacyPrescriptions = lazy(() => import("./pages/pharmacy/Prescriptions"));
const Dispensing = lazy(() => import("./pages/pharmacy/Dispensing"));
const DispensingHistory = lazy(() => import("./pages/pharmacy/DispensingHistory"));
const Inventory = lazy(() => import("./pages/pharmacy/Inventory"));

function HomeRedirect() {
  const { user } = useAuth();
  return <Navigate to={ROLE_HOME[user.role]} replace />;
}

export default function App() {
  return (
    <Suspense fallback={<Loading />}>
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
            <Route path="radiology-staff" element={<StaffManager kind="radiology-staff" />} />
            <Route path="integrations" element={<Integrations />} />
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
            <Route path="countersign" element={<Countersign />} />
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

          <Route path="/trainee" element={<RoleRoute roles={["DOCTOR"]} />}>
            <Route index element={<TraineeDashboard />} />
            <Route path="take-history" element={<TraineeTakeHistory />} />
            <Route path="take-history/:patientId" element={<TraineeTakeHistory />} />
            <Route path="select-doctor/:historyId" element={<TraineeSelectDoctor />} />
            <Route path="referrals" element={<TraineeReferrals />} />
            <Route path="profile" element={<Profile />} />
          </Route>

          <Route element={<PermissionRoute any={["stock.view", "stock.manage"]} />}><Route path="/stock" element={<StockControl />} /></Route>
          <Route element={<PermissionRoute any={["procure.request", "procure.order", "procure.approve", "inventory.manage"]} />}><Route path="/procurement" element={<Procurement />} /></Route>
          <Route element={<PermissionRoute any={["ot.view", "ot.schedule", "ot.record"]} />}><Route path="/ot" element={<OtSchedule />} /></Route>
          <Route element={<PermissionRoute any={["bloodbank.manage"]} />}><Route path="/bloodbank" element={<BloodBank />} /></Route>
          <Route element={<PermissionRoute any={["billing.view", "billing.create", "billing.collect", "billing.approve"]} />}><Route path="/billing" element={<FinanceBilling />} /></Route>
          <Route element={<PermissionRoute any={["claims.manage", "billing.view"]} />}><Route path="/claims" element={<Claims />} /></Route>
          <Route element={<PermissionRoute any={["billing.report"]} />}><Route path="/finance-reports" element={<FinanceReports />} /></Route>
          <Route element={<PermissionRoute any={["transfusion.give"]} />}><Route path="/transfusions" element={<Transfusions />} /></Route>
          <Route element={<PermissionRoute any={["nursing.chart", "ipd.notes"]} />}><Route path="/ward-requests" element={<WardRequests />} /></Route>

          <Route path="/radiology" element={<RoleRoute roles={["RADIOLOGY"]} />}>
            <Route index element={<RadiologyWorklist />} />
            <Route path="profile" element={<Profile />} />
          </Route>

          <Route path="/lab" element={<RoleRoute roles={["LAB"]} />}>
            <Route index element={<LabWorklist />} />
            <Route path="approvals" element={<LabApprovals />} />
            <Route path="advised" element={<TestOrders />} />
            <Route path="profile" element={<Profile />} />
          </Route>

          <Route path="/patient" element={<RoleRoute roles={["PATIENT"]} />}>
            <Route index element={<PatientDashboard />} />
            <Route path="bills" element={<MyBills />} />
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
    </Suspense>
  );
}
