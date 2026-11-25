import {
  LayoutDashboard,
  Mic,
  Users,
  CalendarDays,
  Library,
  History,
  ChartNoAxesCombined,
  Settings,
} from "lucide-react";

export const navigation = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "voice", label: "Live Voice Agent", icon: Mic },
  { id: "leads", label: "Leads", icon: Users },
  { id: "appointments", label: "Appointments", icon: CalendarDays },
  { id: "knowledge", label: "Knowledge Base", icon: Library },
  { id: "history", label: "Call History", icon: History },
  { id: "analytics", label: "Analytics", icon: ChartNoAxesCombined },
  { id: "settings", label: "Settings", icon: Settings },
];
