import { BedDouble } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import BedBoard from "../../components/BedBoard";
import { PageTitle } from "../../components/Feedback";

export default function Beds() {
  const { user } = useAuth();
  const link = user.role === "NURSE" ? (id) => `/nurse/chart/${id}` : user.role === "DOCTOR" ? (id) => `/doctor/inpatients/${id}` : null;
  return (
    <div className="space-y-5">
      <PageTitle title="Bed board" subtitle="Every ward and bed, live. Tap a bed to see the patient or change its state." icon={BedDouble} />
      <BedBoard admissionLink={link} />
    </div>
  );
}
