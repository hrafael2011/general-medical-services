import { useEffect, useState } from "react";
import { Hand } from "lucide-react";

interface WelcomeToastProps {
  userName: string;
  onDone: () => void;
}

export function WelcomeToast({ userName, onDone }: WelcomeToastProps) {
  const [visible, setVisible] = useState(false);
  const [exiting, setExiting] = useState(false);

  useEffect(() => {
    // Trigger enter animation on next frame
    const enterTimer = requestAnimationFrame(() => setVisible(true));

    // Start exit after 5s
    const exitTimer = setTimeout(() => {
      setExiting(true);
    }, 5000);

    // Fire onDone after exit animation completes (600ms)
    const doneTimer = setTimeout(() => {
      onDone();
    }, 5600);

    return () => {
      cancelAnimationFrame(enterTimer);
      clearTimeout(exitTimer);
      clearTimeout(doneTimer);
    };
  }, [onDone]);

  return (
    <div className={`welcome-toast ${visible ? "welcome-toast--visible" : ""} ${exiting ? "welcome-toast--exit" : ""}`}>
      <div className="welcome-toast-icon">
        <Hand size={22} />
      </div>
      <div className="welcome-toast-body">
        <p className="welcome-toast-greeting">Bienvenido de vuelta,</p>
        <p className="welcome-toast-name">{userName}</p>
        <p className="welcome-toast-subtitle">Que tengas un excelente día</p>
      </div>
    </div>
  );
}
