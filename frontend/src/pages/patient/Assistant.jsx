import { PageTitle } from "../../components/Feedback";
import AssistantChat from "../../components/assistant/AssistantChat";

export default function PatientAssistant() {
  return (
    <div className="space-y-4">
      <PageTitle title="Ask HealthWise" subtitle="Ask about your last checkup, reports, medicines and appointments. Type or speak, and listen to the answer." />
      <AssistantChat />
    </div>
  );
}
