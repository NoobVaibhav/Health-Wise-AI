import { Component } from "react";
import { AlertTriangle, Home, LogOut, RotateCcw } from "lucide-react";

// If a page fails while it is being drawn (for example the server sent data in a shape the page did not expect), React would leave a blank screen.
// This shows what happened in plain words and a way out instead. `inFrame` is used inside the page frame, so the menu stays usable.
export default class ErrorBoundary extends Component {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error) {
    // The message stays in the browser console for support. Nothing is sent anywhere and no patient data is written.
    console.error("A page could not be shown:", error?.message);
  }

  tryAgain = () => this.setState({ failed: false });

  goHome = () => { window.location.assign("/"); };

  logOut = () => {
    try { localStorage.removeItem("healthwise_token"); } catch { /* storage may be blocked */ }
    window.location.assign("/login");
  };

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div role="alert" className={`mx-auto max-w-lg rounded-3xl border border-amber-200 bg-amber-50 p-6 text-center shadow-sm ${this.props.inFrame ? "my-6" : "my-24"}`}>
        <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-amber-100 text-amber-700"><AlertTriangle size={28} /></span>
        <h2 className="mt-3 text-xl font-extrabold text-slate-900">Something went wrong on this page</h2>
        <p className="mt-1 text-slate-600">The page could not be shown. Your information is safe. You can try again, or go back to your home page.</p>
        <div className="mt-4 flex flex-wrap justify-center gap-2">
          <button type="button" onClick={this.tryAgain} className="inline-flex items-center gap-1.5 rounded-xl bg-brand-600 px-4 py-2.5 font-bold text-white hover:bg-brand-700"><RotateCcw size={16} /> Try again</button>
          <button type="button" onClick={this.goHome} className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-4 py-2.5 font-bold text-slate-700 hover:bg-slate-50"><Home size={16} /> Home page</button>
          <button type="button" onClick={this.logOut} className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-4 py-2.5 font-bold text-slate-700 hover:bg-slate-50"><LogOut size={16} /> Log out</button>
        </div>
      </div>
    );
  }
}
