import { Children, type ReactNode } from 'react';
import { BookOpen, Car, ClipboardList, FileX, HandCoins, Home, type LucideIcon } from 'lucide-react';
import { NavLink, useLocation } from 'react-router';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
  SidebarTrigger,
} from '@/components/ui/sidebar';
import { Tip } from '@/components/Tip';
import { HoverCard, HoverCardContent, HoverCardTrigger } from '@/components/ui/hover-card';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { useCan, useReadableForms } from '@/lib/api/queries';
import { FLAGS, type Flag, setFlag, useFlag } from '@/lib/flags';

const ICONS: Record<string, LucideIcon> = {
  requisition: ClipboardList,
  vehicle_log: Car,
  loan_approval: HandCoins,
  write_off: FileX,
};

function Item({ to, label, icon: Icon, end }: { to: string; label: string; icon: LucideIcon; end?: boolean }) {
  const { pathname } = useLocation();
  const active = end ? pathname === to : pathname === to || pathname.startsWith(`${to}/`);
  return (
    <SidebarMenuItem>
      <SidebarMenuButton asChild isActive={active} tooltip={label}>
        <NavLink to={to}>
          <Icon />
          <span>{label}</span>
        </NavLink>
      </SidebarMenuButton>
    </SidebarMenuItem>
  );
}

// Collapsed, its headings give way to lines, and every icon says what it is on hover. Gone, with nothing in it
function Section({ label, children }: { label: string; children: ReactNode }) {
  if (Children.toArray(children).length === 0) return null;
  return (
    <>
      <SidebarSeparator className="hidden group-data-[collapsible=icon]:block" />
      <SidebarGroup>
        <SidebarGroupLabel>{label}</SidebarGroupLabel>
        <SidebarMenu>{children}</SidebarMenu>
      </SidebarGroup>
    </>
  );
}

const VERSION =
  'truncate px-2 font-mono text-xs text-muted-foreground group-data-[collapsible=icon]:px-0 group-data-[collapsible=icon]:text-center group-data-[collapsible=icon]:text-[10px]';

function FlagSwitch({ flag }: { flag: Flag }) {
  const on = useFlag(flag);
  const id = `flag-${flag}`;
  return (
    <div className="flex items-center justify-between gap-4">
      <Label htmlFor={id} className="font-normal">
        {FLAGS[flag].label}
      </Label>
      <Switch
        id={id}
        checked={on}
        onCheckedChange={(next) => {
          setFlag(flag, next);
        }}
      />
    </div>
  );
}

// The build you're on. Whoever may switch features sees it underlined, and on hover, the switches: this browser's alone
function Version({ version }: { version: string }) {
  const can = useCan();
  if (!can('features:edit'))
    return (
      <Tip label={`The build you're on: ${version}`}>
        <span className={VERSION}>{version}</span>
      </Tip>
    );
  return (
    <HoverCard openDelay={200}>
      <HoverCardTrigger asChild>
        <button
          type="button"
          className={`${VERSION} cursor-pointer text-left underline decoration-dotted underline-offset-2`}
        >
          {version}
        </button>
      </HoverCardTrigger>
      <HoverCardContent side="right" align="end" className="w-80 space-y-3 text-sm">
        <div>
          <div className="font-medium">Features</div>
          <div className="text-xs text-muted-foreground">
            Build {version}. Off until switched on, in this browser only
          </div>
        </div>
        {(Object.keys(FLAGS) as Flag[]).map((flag) => (
          <FlagSwitch key={flag} flag={flag} />
        ))}
      </HoverCardContent>
    </HoverCard>
  );
}

export function AppSidebar({ version }: { version: string }) {
  const forms = useReadableForms();
  const can = useCan();
  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="flex-row items-center justify-between group-data-[collapsible=icon]:justify-center">
        <span className="px-2 text-sm font-semibold group-data-[collapsible=icon]:hidden">Ourfos</span>
        <Tip label="Collapse or expand the sidebar">
          <SidebarTrigger />
        </Tip>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarMenu>
            <Item to="/" label="Home" icon={Home} end />
          </SidebarMenu>
        </SidebarGroup>
        <Section label="Workflows">
          {forms.map((f) => (
            <Item key={f.key} to={`/forms/${f.key}`} label={f.title} icon={ICONS[f.key] ?? ClipboardList} />
          ))}
        </Section>
        <Section label="Accounts">
          {can('journal_entries:read') && <Item to="/journal" label="Journal entries" icon={BookOpen} />}
        </Section>
      </SidebarContent>
      <SidebarFooter>
        <Version version={version} />
      </SidebarFooter>
    </Sidebar>
  );
}
