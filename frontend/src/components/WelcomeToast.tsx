import { useEffect, useRef, useState } from "react";
import { Hand } from "lucide-react";

interface WelcomeToastProps {
  userName: string;
  onDone: () => void;
}

export function WelcomeToast({ userName, onDone }: WelcomeToastProps) {
  const [visible, setVisible] = useState(false);
  const [exiting, setExiting] = useState(false);
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  useEffect(() => {
    const enterTimer = requestAnimationFrame(() => setVisible(true));

    const exitTimer = setTimeout(() => {
      setExiting(true);
    }, 5000);

    const doneTimer = setTimeout(() => {
      onDoneRef.current();
    }, 5600);

    return () => {
      cancelAnimationFrame(enterTimer);
      clearTimeout(exitTimer);
      clearTimeout(doneTimer);
    };
  }, []);

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
