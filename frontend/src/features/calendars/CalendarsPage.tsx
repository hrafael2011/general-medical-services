import { useNavigate } from "react-router-dom";
import { CalendarList } from "./CalendarList";

export function CalendarsPage() {
  const navigate = useNavigate();
  return <CalendarList onSelect={id => navigate(`/calendars/${id}`)} />;
}
