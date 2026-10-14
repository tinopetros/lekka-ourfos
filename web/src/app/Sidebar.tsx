import { BookOpen, Car, ClipboardList, FileX, HandCoins, type LucideIcon } from 'lucide-react';
import { NavLink } from 'react-router';
import { useForms } from '@/lib/api/queries';
import { cn } from '@/lib/utils';
import { useUi } from '@/stores/ui';

const ICONS: Record<string, LucideIcon> = {
  requisition: ClipboardList,
  vehicle_log: Car,
  loan_approval: HandCoins,
  write_off: FileX,
};

function Item({ to, label, icon: Icon }: { to: string; label: string; icon: LucideIcon }) {
  const setMenuOpen = useUi((s) => s.setMenuOpen);
  return (
    <NavLink
      to={to}
      onClick={() => {
        setMenuOpen(false);
      }}
      className={({ isActive }) =>
        cn(
          'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
          isActive
            ? 'bg-sidebar-accent text-sidebar-accent-foreground'
            : 'text-sidebar-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground',
        )
      }
    >
      <Icon className="size-4 shrink-0" />
      {label}
    </NavLink>
  );
}

/** Each form's list, then the journal. The forms come from the API, so a new form needs no change here. */
export function Navigation() {
  const { data: forms = [] } = useForms();
  return (
    <nav className="flex flex-col gap-0.5 px-2 py-3">
      <p className="px-3 pb-1 text-xs font-medium text-muted-foreground">Forms</p>
      {forms.map((f) => (
        <Item key={f.key} to={`/forms/${f.key}`} label={f.title} icon={ICONS[f.key] ?? ClipboardList} />
      ))}
      <p className="px-3 pt-4 pb-1 text-xs font-medium text-muted-foreground">Mifos</p>
      <Item to="/journal" label="Journal entries" icon={BookOpen} />
    </nav>
  );
}

export function Sidebar() {
  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r bg-sidebar md:flex">
      <div className="flex h-14 items-center border-b px-5">
        <span className="text-sm font-semibold tracking-wide text-sidebar-foreground">OurFOS</span>
      </div>
      <Navigation />
    </aside>
  );
}
