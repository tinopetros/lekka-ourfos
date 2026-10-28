import { ArrowRight, BookOpen, Car, ClipboardList, FileX, HandCoins, type LucideIcon } from 'lucide-react';
import { Link } from 'react-router';
import { useCan, useMe, useReadableForms } from '@/lib/api/queries';
import { firstName } from '@/lib/greeting';

const ICONS: Record<string, LucideIcon> = {
  requisition: ClipboardList,
  vehicle_log: Car,
  loan_approval: HandCoins,
  write_off: FileX,
};

function Card({ to, title, icon: Icon }: { to: string; title: string; icon: LucideIcon }) {
  return (
    <Link
      to={to}
      className="flex items-center gap-2 rounded-xl border p-4 font-medium transition-colors hover:bg-accent"
    >
      <Icon className="size-4 shrink-0" /> <span className="truncate">{title}</span>
      <ArrowRight className="size-4 shrink-0 text-muted-foreground" />
    </Link>
  );
}

// Where everything starts: a greeting, and a way into each list. Starting a new one is on each list's own page
export function HomePage() {
  const { data: me } = useMe();
  const forms = useReadableForms();
  const can = useCan();
  return (
    <div className="mx-auto max-w-4xl space-y-8 py-4">
      <h1 className="text-2xl font-semibold">Hi {me ? firstName(me.email) : ''}</h1>
      {/* Search, back when it searches: ids, response numbers and subjects, one kind of record at a time. A search
          box that does nothing misleads, so it waits
      <div className="flex gap-2">
        <select className="h-9 rounded-md border bg-background px-2 text-sm" aria-label="What to search">
          {forms.map((f) => (
            <option key={f.key}>{f.title}</option>
          ))}
        </select>
        <div className="relative flex-1">
          <Search className="absolute top-2.5 left-2.5 size-4 text-muted-foreground" />
          <Input className="pl-8" placeholder="Search by #482, an ID, or a subject" />
        </div>
      </div>
      */}
      {forms.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm text-muted-foreground">Workflows</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {forms.map((f) => (
              <Card key={f.key} to={`/forms/${f.key}`} title={f.title} icon={ICONS[f.key] ?? ClipboardList} />
            ))}
          </div>
        </section>
      )}
      {can('journal_entries:read') && (
        <section className="space-y-3">
          <h2 className="text-sm text-muted-foreground">Accounts</h2>
          <div className="grid gap-3 sm:grid-cols-2">
            <Card to="/journal" title="Journal entries" icon={BookOpen} />
          </div>
        </section>
      )}
    </div>
  );
}
