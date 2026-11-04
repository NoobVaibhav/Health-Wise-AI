import { PageTitle } from "../../components/Feedback";
import AssistantChat from "../../components/assistant/AssistantChat";

// The page fills the screen (see Layout): the chat scrolls inside its own card and the input bar stays at the bottom.
export default function PatientAssistant() {
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2 sm:gap-4">
      <div className="sr-only lg:not-sr-only"><PageTitle title="Ask HealthWise" subtitle="Ask about your reports, medicines and appointments. Type or speak, and listen to the answer." /></div>
      <AssistantChat />
    </div>
  );
}
