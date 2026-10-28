import { LogOut } from 'lucide-react';
import type { CSSProperties } from 'react';
import { Outlet } from 'react-router';
import { Button } from '@/components/ui/button';
import { SidebarInset, SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar';
import { Tip } from '@/components/Tip';
import type { Me } from '@/lib/api/types';
import { firstName } from '@/lib/greeting';
import { useUi } from '@/stores/ui';
import { AppSidebar } from './AppSidebar';
import { EnvironmentBanner } from './EnvironmentBanner';
import { useOnRecord } from './useOnRecord';
import { useScrollArea } from './useScrollArea';

export function Layout({ me }: { me: Me }) {
  const onRecord = useOnRecord();
  const { expanded, pinned, setSidebar } = useUi();
  const scrolling = useScrollArea();
  return (
    <div
      className="flex h-dvh flex-col bg-background"
      style={{ '--banner-height': me.environment === 'prod' ? '0px' : '1.5rem' } as CSSProperties}
    >
      <EnvironmentBanner environment={me.environment} />
      <SidebarProvider
        className="min-h-0 flex-1"
        open={onRecord ? pinned : expanded}
        onOpenChange={(open) => {
          setSidebar(open, onRecord);
        }}
      >
        <AppSidebar version={me.version} />
        <SidebarInset className="min-w-0">
          <header className="flex h-12 shrink-0 items-center gap-3 border-b px-4 md:px-6">
            <SidebarTrigger className="md:hidden" aria-label="Menu" />
            <span className="ml-auto truncate text-sm text-muted-foreground" title={me.email}>
              Hi {firstName(me.email)}
            </span>
            {/* IAP's own sign-out: it clears its cookie, and the next page asks Google who you are. None locally */}
            {me.environment !== 'local' && (
              <Tip label="Sign out">
                <Button variant="ghost" size="icon-sm" asChild>
                  <a href="/?gcp-iap-mode=CLEAR_LOGIN_COOKIE" aria-label="Sign out">
                    <LogOut />
                  </a>
                </Button>
              </Tip>
            )}
          </header>
          {/* relative: what's positioned inside, like a switch's hidden input, stays in here, not the page's scroll */}
          <main ref={scrolling} className="relative min-h-0 flex-1 overflow-auto p-4 md:p-6">
            <Outlet />
          </main>
        </SidebarInset>
      </SidebarProvider>
    </div>
  );
}
