import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AuthProvider } from "./context/AuthContext";
import { ToastProvider } from "./components/Toast";
import ErrorBoundary from "./components/ErrorBoundary";
import LaunchGate from "./components/LaunchScreen";
import "./utils/nativeSpeech";
import { startNativeBack } from "./utils/nativeBack";
import "./index.css";

startNativeBack().catch((e) => console.warn("The Android back button could not be set up:", e?.message || e));

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <ToastProvider>
        <AuthProvider>
          <ErrorBoundary>
            <App />
          </ErrorBoundary>
          <LaunchGate />
        </AuthProvider>
      </ToastProvider>
    </BrowserRouter>
  </React.StrictMode>
);
