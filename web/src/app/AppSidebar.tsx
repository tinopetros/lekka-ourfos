import type { ReactNode } from 'react';
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
import { useForms } from '@/lib/api/queries';

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

// Collapsed, its headings give way to lines, and every icon says what it is on hover
function Section({ label, children }: { label: string; children: ReactNode }) {
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

export function AppSidebar({ version }: { version: string }) {
  const { data: forms = [] } = useForms();
  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="flex-row items-center justify-between group-data-[collapsible=icon]:justify-center">
        <span className="px-2 text-sm font-semibold group-data-[collapsible=icon]:hidden">OurFOS</span>
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
          <Item to="/journal" label="Journal entries" icon={BookOpen} />
        </Section>
      </SidebarContent>
      <SidebarFooter>
        <Tip label={`The build you're on: ${version}`}>
          <span className="truncate px-2 font-mono text-xs text-muted-foreground group-data-[collapsible=icon]:px-0 group-data-[collapsible=icon]:text-center group-data-[collapsible=icon]:text-[10px]">
            {version}
          </span>
        </Tip>
      </SidebarFooter>
    </Sidebar>
  );
}
