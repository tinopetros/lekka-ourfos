import { ArrowRight, BookOpen, Car, ClipboardList, FileX, HandCoins, Search, type LucideIcon } from 'lucide-react';
import { Link } from 'react-router';
import { CreateButton } from '@/components/CreateButton';
import { Input } from '@/components/ui/input';
import { useForms, useMe } from '@/lib/api/queries';
import { firstName } from '@/lib/greeting';

const ICONS: Record<string, LucideIcon> = {
  requisition: ClipboardList,
  vehicle_log: Car,
  loan_approval: HandCoins,
  write_off: FileX,
};

function Card({ to, title, icon: Icon, noun }: { to: string; title: string; icon: LucideIcon; noun?: string }) {
  return (
    <div className="flex items-center gap-3 rounded-xl border p-4 transition-colors hover:bg-accent">
      <Link to={to} className="flex min-w-0 flex-1 items-center gap-2 font-medium">
        <Icon className="size-4 shrink-0" /> <span className="truncate">{title}</span>
        <ArrowRight className="size-4 shrink-0 text-muted-foreground" />
      </Link>
      {noun && <CreateButton noun={noun} />}
    </div>
  );
}

// Where everything starts: a greeting, a search, and a way into each list, or straight to creating one
export function HomePage() {
  const { data: me } = useMe();
  const { data: forms = [] } = useForms();
  return (
    <div className="mx-auto max-w-4xl space-y-8 py-4">
      <h1 className="text-2xl font-semibold">Hi {me ? firstName(me.email) : ''}</h1>
      {/* A look only, for now: ids, response numbers and subjects, one kind of record at a time */}
      <div className="flex gap-2">
        <select className="h-9 rounded-md border bg-background px-2 text-sm" aria-label="What to search" disabled>
          {forms.map((f) => (
            <option key={f.key}>{f.title}</option>
          ))}
        </select>
        <div className="relative flex-1">
          <Search className="absolute top-2.5 left-2.5 size-4 text-muted-foreground" />
          <Input className="pl-8" placeholder="Search by #482, an ID, or a subject: coming soon" disabled />
        </div>
      </div>
      <section className="space-y-3">
        <h2 className="text-sm text-muted-foreground">Workflows</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          {forms.map((f) => (
            <Card
              key={f.key}
              to={`/forms/${f.key}`}
              title={f.title}
              icon={ICONS[f.key] ?? ClipboardList}
              noun={f.title.toLowerCase().replace(/s$/, '')}
            />
          ))}
        </div>
      </section>
      <section className="space-y-3">
        <h2 className="text-sm text-muted-foreground">Accounts</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <Card to="/journal" title="Journal entries" icon={BookOpen} />
        </div>
      </section>
    </div>
  );
}
